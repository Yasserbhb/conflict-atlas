from conflict_updater.config import Settings
from conflict_updater.store import BaseConflict
from conflict_updater.pipeline import scan
from conflict_updater.schema import (
    ScanRequest, RawItem, SearchQuery,
    ScoperOutput, ExtractorOutput, CandidateEvent, ResolverOutput, ClassifyOutput,
    SeverityOutput, RolesOutput, Party, GeoOutput, Location, SummaryOutput,
    LifecycleOutput, FactCheckOutput, ReconcilerOutput,
)
from fakes import FakeLLM, FakeSearch, FakeGeocode

BASE = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR", "PSE"],
                     start=2023, status="active")]
ITEMS = [
    RawItem(title="Israel strikes Gaza City", url="http://a", snippet="dozens killed",
            outlet="Reuters", alignment="independent"),
    RawItem(title="Gaza City hit", url="http://b", snippet="strike reported",
            outlet="Al Jazeera", alignment="arab"),
]


def _happy(override=None):
    r = {
        ScoperOutput: ScoperOutput(queries=[SearchQuery(query="gaza strike 2024")],
                                   watch_conflict_ids=["seed_gaza"]),
        ExtractorOutput: ExtractorOutput(events=[CandidateEvent(
            date="2024-05-01", title="Israeli strike on Gaza City",
            actors=["Israel", "Palestine"], place="Gaza",
            source_urls=["http://a", "http://b"])]),
        ResolverOutput: ResolverOutput(decision="attach", conflict_id="seed_gaza"),
        ClassifyOutput: ClassifyOutput(event_kind="attack"),
        SeverityOutput: SeverityOutput(severity=4),
        RolesOutput: RolesOutput(parties=[Party(country_id="ISR", role="aggressor"),
                                          Party(country_id="PSE", role="victim")]),
        GeoOutput: GeoOutput(location=Location(lat=31.5, lng=34.47, label="Gaza")),
        SummaryOutput: SummaryOutput(text="An Israeli strike hit Gaza City."),
        LifecycleOutput: LifecycleOutput(status="active"),
        FactCheckOutput: FactCheckOutput(verdict="pass", confidence=0.9,
                                         independent_sources=2, cross_alignment=True),
        ReconcilerOutput: ReconcilerOutput(decision="auto_approve"),
    }
    if override:
        r.update(override)
    return r


def _req():
    return ScanRequest(period_start="2024-01-01", period_end="2024-12-31")


def test_happy_path_attaches_and_auto_approves():
    llm = FakeLLM(_happy())
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
               geocode=FakeGeocode())
    assert len(res.proposals) == 1
    p = res.proposals[0]
    assert p.kind == "attach" and p.target_conflict_id == "seed_gaza"
    assert p.needs_human is False
    assert p.event.kind == "attack" and p.event.severity == 4
    assert p.event.parties == ["ISR", "PSE"]
    assert p.event.location and p.event.location.label == "Gaza"
    assert p.provisional is False  # 2024 event vs a 2026 "today"
    assert res.stats["auto_approved"] == 1


def test_uncertain_factcheck_routes_to_human():
    llm = FakeLLM(_happy({FactCheckOutput: FactCheckOutput(verdict="uncertain", confidence=0.4)}))
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
               geocode=FakeGeocode())
    assert res.proposals[0].needs_human is True


def test_new_conflict_always_needs_human():
    over = {
        ResolverOutput: ResolverOutput(decision="new"),
        ClassifyOutput: ClassifyOutput(event_kind="attack", conflict_type="war"),
    }
    res = scan(_req(), llm=FakeLLM(_happy(over)), search=FakeSearch(ITEMS),
               base=BASE, settings=Settings(), geocode=FakeGeocode())
    p = res.proposals[0]
    assert p.kind == "new_conflict" and p.new_conflict is not None
    assert p.needs_human is True
    assert p.new_conflict.type == "war"
    assert p.new_conflict.events and p.new_conflict.events[0].kind == "attack"


def test_event_gathers_all_corroborating_sources_with_metadata():
    llm = FakeLLM(_happy())
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
               geocode=FakeGeocode())
    srcs = res.proposals[0].event.sources
    assert {s.url for s in srcs} == {"http://a", "http://b"}   # both corroborating items linked
    assert any(s.alignment for s in srcs)                      # outlet/alignment preserved for fact-check


def test_backfill_event_keeps_status_and_skips_lifecycle():
    base = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR", "PSE"],
                         start=2023, status="suspended",
                         events=[{"date": "2025-01-01", "title": "a later event"}])]
    llm = FakeLLM(_happy())  # candidate is 2024-05-01 → older than the 2025 event → a backfill
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=base, settings=Settings(),
               geocode=FakeGeocode())
    p = res.proposals[0]
    assert "LifecycleOutput" not in llm.calls   # the lifecycle agent is not called for a backfill
    assert p.status == "suspended"              # the conflict's current status is kept, not overwritten


def test_known_event_is_dropped():
    llm = FakeLLM(_happy({ResolverOutput: ResolverOutput(decision="known", conflict_id="seed_gaza")}))
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
               geocode=FakeGeocode())
    assert res.proposals == []
    assert res.dropped and "already known" in res.dropped[0]


def test_geocode_overrides_the_llms_guessed_coordinates():
    # the LLM guesses Gaza at (31.5, 34.47); a real lookup for that label finds a different,
    # more precise point — the real lookup must win, proving it isn't just LLM memory anymore.
    real = Location(lat=31.5017, lng=34.4668, label="Gaza")
    geocode = FakeGeocode(table={"Gaza": real})
    llm = FakeLLM(_happy())
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
               geocode=geocode)
    assert res.proposals[0].event.location == real
    assert geocode.calls == ["Gaza"]


def test_geocode_miss_falls_back_to_llms_guess():
    geocode = FakeGeocode()  # empty table -> lookup always misses
    llm = FakeLLM(_happy())
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
               geocode=geocode)
    assert res.proposals[0].event.location.lat == 31.5  # the LLM's own guess, unchanged
