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


def test_thinly_sourced_new_conflict_needs_human():
    # _happy()'s FactCheck has only 2 independent sources — below the higher bar a NEW
    # conflict needs (default 3) — so it's held for review even though a plain attach with
    # the same evidence would auto-approve (see test_happy_path_attaches_and_auto_approves).
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


def test_strongly_corroborated_new_conflict_can_auto_approve():
    # a founding event isn't ALWAYS forced to human review — strong, cross-aligned,
    # multi-source evidence can clear the (higher) bar and auto-create it.
    over = {
        ResolverOutput: ResolverOutput(decision="new"),
        ClassifyOutput: ClassifyOutput(event_kind="attack", conflict_type="war"),
        FactCheckOutput: FactCheckOutput(verdict="pass", confidence=0.95,
                                         independent_sources=3, cross_alignment=True),
    }
    res = scan(_req(), llm=FakeLLM(_happy(over)), search=FakeSearch(ITEMS),
               base=BASE, settings=Settings(), geocode=FakeGeocode())
    p = res.proposals[0]
    assert p.kind == "new_conflict"
    assert p.needs_human is False


def test_reconciler_can_still_veto_a_strongly_corroborated_new_conflict():
    # being new no longer auto-blocks, but the reconciler may still route to a human on a
    # genuine objection (contested roles/classification) even with strong sourcing.
    over = {
        ResolverOutput: ResolverOutput(decision="new"),
        ClassifyOutput: ClassifyOutput(event_kind="attack", conflict_type="war"),
        FactCheckOutput: FactCheckOutput(verdict="pass", confidence=0.95,
                                         independent_sources=3, cross_alignment=True),
        ReconcilerOutput: ReconcilerOutput(decision="needs_human", open_question="who started it?"),
    }
    res = scan(_req(), llm=FakeLLM(_happy(over)), search=FakeSearch(ITEMS),
               base=BASE, settings=Settings(), geocode=FakeGeocode())
    assert res.proposals[0].needs_human is True


def test_two_same_slug_new_conflicts_get_distinct_ids():
    # two foundings whose titles slugify identically must not share an id (which would make
    # the merger silently drop the second one's event).
    c1 = CandidateEvent(date="1900-01-01", title="Border Clash!", actors=["A", "B"],
                        place="X", source_urls=["http://a"])
    c2 = CandidateEvent(date="1950-01-01", title="Border Clash?", actors=["C", "D"],
                        place="Y", source_urls=["http://b"])
    responses = _happy({
        ExtractorOutput: ExtractorOutput(events=[c1, c2]),
        ResolverOutput: ResolverOutput(decision="new"),  # force both to be new
    })
    res = scan(_req(), llm=FakeLLM(responses), search=FakeSearch(ITEMS), base=[],
               settings=Settings(), geocode=FakeGeocode())
    new_ids = [p.new_conflict.id for p in res.proposals if p.kind == "new_conflict"]
    assert new_ids == ["seed_new_border_clash", "seed_new_border_clash_2"]


def test_second_event_attaches_to_a_pending_new_conflict_instead_of_duplicating():
    # two events for the SAME undeclared conflict, found in one scan — the second must
    # attach to the first's pending conflict, not spawn a duplicate "new" one.
    cand1 = CandidateEvent(date="1871-03-15", title="Mokrani Revolt begins",
                           actors=["France", "Algeria"], place="Kabylie", source_urls=["http://a"])
    cand2 = CandidateEvent(date="1871-05-01", title="Mokrani Revolt is crushed by France",
                           actors=["France", "Algeria"], place="Kabylie", source_urls=["http://b"])

    def resolver_fn(user):
        if "seed_new_mokrani_revolt_begins" in user:
            return ResolverOutput(decision="attach", conflict_id="seed_new_mokrani_revolt_begins")
        return ResolverOutput(decision="new")

    responses = _happy({
        ExtractorOutput: ExtractorOutput(events=[cand1, cand2]),
        ResolverOutput: resolver_fn,
    })
    llm = FakeLLM(responses)
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=[], settings=Settings(),
               geocode=FakeGeocode())

    kinds = [p.kind for p in res.proposals]
    assert kinds.count("new_conflict") == 1   # not two duplicate new conflicts
    assert kinds.count("attach") == 1
    attach_p = next(p for p in res.proposals if p.kind == "attach")
    assert attach_p.target_conflict_id == "seed_new_mokrani_revolt_begins"


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
