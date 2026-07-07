import dataclasses
from conflict_updater.config import Settings
from conflict_updater.store import BaseConflict
from conflict_updater.pipeline import scan
from conflict_updater.schema import (
    ScanRequest, RawItem, SearchQuery,
    ScoperOutput, ExtractorOutput, CandidateEvent, ResolverOutput,
    EnrichOutput, VerifyOutput, Party, Location,
)
from fakes import FakeLLM, FakeSearch, FakeGeocode

BASE = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR", "PSE"],
                     start=2023, status="active")]
ITEMS = [
    RawItem(title="Israel strikes Gaza City", url="http://a", snippet="dozens killed",
            outlet="reuters.com", alignment="independent"),
    RawItem(title="Gaza City hit", url="http://b", snippet="strike reported",
            outlet="aljazeera.com", alignment="arab"),
]


def _enrich(**kw):
    base = dict(
        event_kind="attack", severity=4,
        parties=[Party(country_id="ISR", role="aggressor"), Party(country_id="PSE", role="victim")],
        location=Location(lat=31.5, lng=34.47, label="Gaza"),
        summary="An Israeli strike hit Gaza City.", status="active", start_date="2023",
    )
    base.update(kw)
    return EnrichOutput(**base)


def _verify(**kw):
    base = dict(verdict="pass", confidence=0.9, independent_sources=2,
                cross_alignment=True, decision="auto_approve")
    base.update(kw)
    return VerifyOutput(**base)


def _happy(override=None):
    r = {
        ScoperOutput: ScoperOutput(queries=[SearchQuery(query="gaza strike 2024")],
                                   watch_conflict_ids=["seed_gaza"]),
        ExtractorOutput: ExtractorOutput(events=[CandidateEvent(
            date="2024-05-01", title="Israeli strike on Gaza City",
            actors=["Israel", "Palestine"], place="Gaza",
            source_urls=["http://a", "http://b"])]),
        ResolverOutput: ResolverOutput(decision="attach", conflict_id="seed_gaza"),
        EnrichOutput: _enrich(),
        VerifyOutput: _verify(),
    }
    if override:
        r.update(override)
    return r


def _req():
    return ScanRequest(period_start="2024-01-01", period_end="2024-12-31")


def _scan(responses, base=BASE, settings=None, geocode=None):
    return scan(_req(), llm=FakeLLM(responses), search=FakeSearch(ITEMS), base=base,
                settings=settings or Settings(), geocode=geocode or FakeGeocode())


def test_happy_path_attaches_and_auto_approves():
    res = _scan(_happy())
    assert len(res.proposals) == 1
    p = res.proposals[0]
    assert p.kind == "attach" and p.target_conflict_id == "seed_gaza"
    assert p.needs_human is False
    assert p.event.kind == "attack" and p.event.severity == 4
    assert p.event.parties == ["ISR", "PSE"]
    assert p.event.location and p.event.location.label == "Gaza"
    assert p.provisional is False
    assert res.stats["auto_approved"] == 1


def test_uncertain_verify_routes_to_human():
    res = _scan(_happy({VerifyOutput: _verify(verdict="uncertain", confidence=0.4, decision="needs_human")}))
    assert res.proposals[0].needs_human is True


def test_thinly_sourced_new_conflict_needs_human():
    # 2 independent sources is below the higher bar a NEW conflict needs (default 3) → held.
    res = _scan(_happy({
        ResolverOutput: ResolverOutput(decision="new"),
        EnrichOutput: _enrich(conflict_type="war"),
    }))
    p = res.proposals[0]
    assert p.kind == "new_conflict" and p.new_conflict is not None
    assert p.needs_human is True
    assert p.new_conflict.type == "war"
    assert p.new_conflict.events and p.new_conflict.events[0].kind == "attack"


def test_strongly_corroborated_new_conflict_can_auto_approve():
    res = _scan(_happy({
        ResolverOutput: ResolverOutput(decision="new"),
        EnrichOutput: _enrich(conflict_type="war"),
        VerifyOutput: _verify(confidence=0.95, independent_sources=3, cross_alignment=True,
                              decision="auto_approve"),
    }))
    p = res.proposals[0]
    assert p.kind == "new_conflict" and p.needs_human is False


def test_verify_can_still_veto_a_strongly_corroborated_new_conflict():
    res = _scan(_happy({
        ResolverOutput: ResolverOutput(decision="new"),
        EnrichOutput: _enrich(conflict_type="war"),
        VerifyOutput: _verify(confidence=0.95, independent_sources=3, cross_alignment=True,
                              decision="needs_human", open_question="who started it?"),
    }))
    assert res.proposals[0].needs_human is True


def test_new_conflict_span_comes_from_sources_not_just_the_event():
    # founding event is 2024; sources say the conflict began 2023 and is ongoing.
    res = _scan(_happy({
        ResolverOutput: ResolverOutput(decision="new"),
        EnrichOutput: _enrich(conflict_type="war", start_date="2023", end_date=None, status="active"),
    }))
    nc = res.proposals[0].new_conflict
    assert nc.start_date == "2023" and nc.end_date is None and nc.ongoing is True


def test_new_conflict_with_a_sourced_end_date_is_closed_and_marked_ended():
    cand = CandidateEvent(date="1885-06-01", title="War breaks out", actors=["A", "B"],
                          place="X", source_urls=["http://a"])
    res = _scan(_happy({
        ExtractorOutput: ExtractorOutput(events=[cand]),
        ResolverOutput: ResolverOutput(decision="new"),
        EnrichOutput: _enrich(event_kind="battle", conflict_type="war",
                              start_date="1881", end_date="1899", status="active"),
    }))
    nc = res.proposals[0].new_conflict
    assert nc.start_date == "1881" and nc.end_date == "1899"
    assert nc.ongoing is False and nc.status == "ended"


def test_cap_keeps_the_most_significant_events():
    footnote = CandidateEvent(date="1870-10-24", title="A decree", actors=["FRA"], place="X",
                              source_urls=["http://a"], significance=1)
    revolt = CandidateEvent(date="1871-03-15", title="Major revolt", actors=["DZA", "FRA"],
                            place="Kabylie", source_urls=["http://b"], significance=5)
    minor = CandidateEvent(date="1872-01-01", title="A minor measure", actors=["FRA"], place="Y",
                           source_urls=["http://a"], significance=2)
    res = _scan(_happy({
        ExtractorOutput: ExtractorOutput(events=[footnote, revolt, minor]),
        ResolverOutput: ResolverOutput(decision="attach", conflict_id="seed_gaza"),
    }), settings=dataclasses.replace(Settings(), max_candidates=1))
    assert len(res.proposals) == 1
    assert res.proposals[0].event.title == "Major revolt"


def test_two_same_slug_new_conflicts_get_distinct_ids():
    c1 = CandidateEvent(date="1900-01-01", title="Border Clash!", actors=["A", "B"],
                        place="X", source_urls=["http://a"])
    c2 = CandidateEvent(date="1950-01-01", title="Border Clash?", actors=["C", "D"],
                        place="Y", source_urls=["http://b"])
    res = _scan(_happy({
        ExtractorOutput: ExtractorOutput(events=[c1, c2]),
        ResolverOutput: ResolverOutput(decision="new"),
    }), base=[])
    new_ids = [p.new_conflict.id for p in res.proposals if p.kind == "new_conflict"]
    assert new_ids == ["seed_new_border_clash", "seed_new_border_clash_2"]


def test_second_event_attaches_to_a_pending_new_conflict_instead_of_duplicating():
    cand1 = CandidateEvent(date="1871-03-15", title="Mokrani Revolt begins",
                           actors=["France", "Algeria"], place="Kabylie", source_urls=["http://a"])
    cand2 = CandidateEvent(date="1871-05-01", title="Mokrani Revolt is crushed by France",
                           actors=["France", "Algeria"], place="Kabylie", source_urls=["http://b"])

    def resolver_fn(user):
        if "seed_new_mokrani_revolt_begins" in user:
            return ResolverOutput(decision="attach", conflict_id="seed_new_mokrani_revolt_begins")
        return ResolverOutput(decision="new")

    res = _scan(_happy({
        ExtractorOutput: ExtractorOutput(events=[cand1, cand2]),
        ResolverOutput: resolver_fn,
    }), base=[])
    kinds = [p.kind for p in res.proposals]
    assert kinds.count("new_conflict") == 1 and kinds.count("attach") == 1
    attach_p = next(p for p in res.proposals if p.kind == "attach")
    assert attach_p.target_conflict_id == "seed_new_mokrani_revolt_begins"


def test_event_gathers_all_corroborating_sources_with_metadata():
    res = _scan(_happy())
    srcs = res.proposals[0].event.sources
    assert {s.url for s in srcs} == {"http://a", "http://b"}
    assert any(s.alignment for s in srcs)


def test_backfill_event_keeps_its_conflicts_status():
    base = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR", "PSE"],
                         start=2023, status="suspended",
                         events=[{"date": "2025-01-01", "title": "a later event"}])]
    # candidate is 2024-05-01 → older than the 2025 event → a backfill; enrich says "active"
    res = _scan(_happy({EnrichOutput: _enrich(status="active")}), base=base)
    p = res.proposals[0]
    assert p.status == "suspended"   # the conflict's current status is kept, not the enrich verdict


def test_known_event_is_dropped():
    res = _scan(_happy({ResolverOutput: ResolverOutput(decision="known", conflict_id="seed_gaza")}))
    assert res.proposals == []
    assert res.dropped and "already known" in res.dropped[0]


def test_geocode_overrides_the_llms_guessed_coordinates():
    real = Location(lat=31.5017, lng=34.4668, label="Gaza")
    geo = FakeGeocode(table={"Gaza": real})
    res = _scan(_happy(), geocode=geo)
    assert res.proposals[0].event.location == real
    assert geo.calls == ["Gaza"]


def test_geocode_miss_falls_back_to_llms_guess():
    res = _scan(_happy(), geocode=FakeGeocode())
    assert res.proposals[0].event.location.lat == 31.5
