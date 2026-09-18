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


class _FakeStructuredSource:
    def __init__(self, events):
        self._events = events

    def fetch(self, period_start, period_end, region=None):
        return list(self._events)

BASE = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR", "PSE"],
                     start=2023, status="active")]
ITEMS = [
    RawItem(title="Israel strikes Gaza City", url="http://a", snippet="dozens killed",
            outlet="reuters.com", alignment="independent"),
    RawItem(title="Gaza City hit", url="http://b", snippet="strike reported",
            outlet="aljazeera.com", alignment="arab"),
    RawItem(title="Strike on Gaza City confirmed", url="http://c", snippet="strike reported",
            outlet="apnews.com", alignment="independent"),
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


def _req(period=("1800-01-01", "2030-12-31")):
    # Deliberately wide. scan() now drops candidates dated outside the request window (it used to
    # be a prompt instruction with nothing enforcing it), and most tests here are about slug
    # collisions, capping or status — not dates. A window that spans their fixtures keeps them
    # testing what they are about. The filter itself is covered by its own tests below.
    return ScanRequest(period_start=period[0], period_end=period[1])


def _scan(responses, base=BASE, settings=None, geocode=None, period=("1800-01-01", "2030-12-31"),
          items=None, cand_sources=None):
    if cand_sources is not None:
        ev = responses[ExtractorOutput].events[0]
        responses = dict(responses)
        responses[ExtractorOutput] = ExtractorOutput(
            events=[ev.model_copy(update={"source_urls": cand_sources})])
    return scan(_req(period), llm=FakeLLM(responses), search=FakeSearch(items or ITEMS), base=base,
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
    """A NEW conflict on ONE outlet is held, however confident the fact-check was.

    Founding a conflict is harder to undo than attaching an event — a wrong id, title, type and
    party list all enter the atlas at once — so it needs corroboration the attach path does not.
    The bar is NEW_CONFLICT_MIN_SOURCES distinct outlets, currently 2; one is below it.
    """
    res = _scan(_happy({
        ResolverOutput: ResolverOutput(decision="new"),
        EnrichOutput: _enrich(conflict_type="war"),
    }), cand_sources=["http://only-one-outlet"])
    p = res.proposals[0]
    assert p.kind == "new_conflict" and p.new_conflict is not None
    assert p.needs_human is True
    assert p.new_conflict.type == "war"
    assert p.new_conflict.events and p.new_conflict.events[0].kind == "attack"


def test_strongly_corroborated_new_conflict_can_auto_approve():
    # Three DISTINCT outlets across two alignments actually exist in ITEMS — the bar is met by
    # the evidence, not by the model saying so.
    res = _scan(_happy({
        ResolverOutput: ResolverOutput(decision="new"),
        EnrichOutput: _enrich(conflict_type="war"),
        VerifyOutput: _verify(confidence=0.95, decision="auto_approve"),
    }), cand_sources=["http://a", "http://b", "http://c"])
    p = res.proposals[0]
    assert p.kind == "new_conflict" and p.needs_human is False
    assert p.verify.independent_sources == 3


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


def test_enrich_receives_lifecycle_profile_context_for_a_known_type():
    # BASE has no `type` set — use a war-typed parent so config/lifecycle.yml's "war" profile matches.
    base_war = [BaseConflict(id="seed_gaza", title="Gaza War", type="war",
                             involved_countries=["ISR", "PSE"], start=2023, status="active")]
    captured = {}

    def _capture_enrich(user):
        captured["user"] = user
        return _enrich()

    _scan(_happy({EnrichOutput: _capture_enrich}), base=base_war)
    assert "Lifecycle profile for type=war" in captured["user"]
    assert "dwell_days=45" in captured["user"]
    assert "hostilities resumed" in captured["user"]


def test_structured_event_bypasses_verify_and_auto_approves():
    structured_cand = CandidateEvent(
        date="2024-03-01", title="UCDP-sourced clash", actors=["Israel", "Palestine"],
        place="Gaza", source_urls=["https://ucdp.uu.se/event/123"], significance=3,
        source_kind="structured",
    )
    fake_llm = FakeLLM(_happy({ExtractorOutput: ExtractorOutput(events=[])}))
    res = scan(_req(), llm=fake_llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
              geocode=FakeGeocode(), structured=_FakeStructuredSource([structured_cand]))

    assert len(res.proposals) == 1
    p = res.proposals[0]
    assert p.needs_human is False
    assert p.verify is None
    assert "VerifyOutput" not in fake_llm.calls  # Verify's LLM call is skipped entirely


def test_structured_event_still_escalates_on_resolver_ambiguity():
    structured_cand = CandidateEvent(
        date="2024-03-01", title="Unclear which conflict", actors=["A", "B"],
        source_urls=["https://ucdp.uu.se/event/456"], significance=3, source_kind="structured",
    )
    fake_llm = FakeLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[]),
        ResolverOutput: ResolverOutput(decision="ambiguous"),
    }))
    res = scan(_req(), llm=fake_llm, search=FakeSearch(ITEMS), base=BASE, settings=Settings(),
              geocode=FakeGeocode(), structured=_FakeStructuredSource([structured_cand]))

    assert res.proposals[0].needs_human is True  # identity ambiguity still needs a human
    assert "VerifyOutput" not in fake_llm.calls


def test_corroboration_is_counted_from_the_sources_not_claimed_by_the_model():
    # The model asserts 4 independent sources; only 2 distinct outlets actually back the event.
    # These numbers gate new-conflict auto-approval, so the count has to win.
    res = _scan(_happy({VerifyOutput: _verify(independent_sources=4, cross_alignment=False)}))
    p = res.proposals[0]
    assert p.event.independent_sources == 2, "a hallucinated count must not reach the atlas"
    assert p.event.cross_alignment is True, "reuters(independent) + aljazeera(arab) really is cross-aligned"
    assert p.verify.independent_sources == 2, "the gate sees the counted value too"


def test_one_outlet_cited_twice_counts_once():
    res = _scan(_happy({VerifyOutput: _verify()}), items=[
        RawItem(title="Strike", url="http://a1", snippet="x", outlet="reuters.com", alignment="independent"),
        RawItem(title="Strike", url="http://a2", snippet="x", outlet="reuters.com", alignment="independent"),
    ], cand_sources=["http://a1", "http://a2"])
    p = res.proposals[0]
    assert p.event.independent_sources == 1, "two URLs from one outlet are one voice"
    assert p.event.cross_alignment is False


def test_enrich_gets_no_lifecycle_context_when_parent_type_is_unknown():
    # BASE (module-level fixture) has no `type` set at all — profiles.get(None) finds nothing.
    captured = {}

    def _capture_enrich(user):
        captured["user"] = user
        return _enrich()

    _scan(_happy({EnrichOutput: _capture_enrich}))
    assert "Lifecycle profile" not in captured["user"]


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


# ---- failure isolation -------------------------------------------------------------------
# Before this, the per-candidate loop had no try/except: an LLM failure on candidate 7 of 12
# discarded candidates 1-6 as well, along with the quota already spent on them. That is why
# nine consecutive weekly runs produced nothing at all instead of partial results.

class _FlakyLLM(FakeLLM):
    """Raises on the Nth Enrich call, succeeds otherwise."""

    def __init__(self, responses, fail_on_title: str):
        super().__init__(responses)
        self.fail_on_title = fail_on_title

    def structured(self, model, system, user):
        if model.__name__ == "EnrichOutput" and self.fail_on_title in user:
            raise RuntimeError("provider exploded")
        return super().structured(model, system, user)


def _two_candidates():
    return _happy({
        ExtractorOutput: ExtractorOutput(events=[
            CandidateEvent(date="2024-05-01", title="GOOD strike on Gaza City",
                           actors=["Israel"], place="Gaza", source_urls=["http://a"]),
            CandidateEvent(date="2024-05-02", title="BOOM strike on Gaza City",
                           actors=["Israel"], place="Gaza", source_urls=["http://b"]),
        ]),
    })


def test_one_failing_candidate_does_not_discard_the_others():
    llm = _FlakyLLM(_two_candidates(), fail_on_title="BOOM")
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode())
    assert len(res.proposals) == 1, "the healthy candidate must still produce a proposal"
    assert "GOOD" in res.proposals[0].event.title
    assert res.stats["failed"] == 1
    assert len(res.failed) == 1 and "RuntimeError" in res.failed[0]


def test_failed_candidates_are_named_in_the_result():
    llm = _FlakyLLM(_two_candidates(), fail_on_title="BOOM")
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode())
    assert "BOOM" in res.failed[0], "the failure must say which candidate it was"
    assert "provider exploded" in res.failed[0]


def test_a_clean_scan_reports_no_failures():
    res = _scan(_happy())
    assert res.failed == [] and res.stats["failed"] == 0


# ---- the window is enforced in code, not asked for in a prompt ------------------------------

def test_an_out_of_window_candidate_never_reaches_the_resolver():
    # The extractor is TOLD the window, but nothing used to check. Over 365 daily runs that drift
    # is how one event gets recorded on several days.
    llm = FakeLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[
            CandidateEvent(date="2024-05-01", title="Inside the window",
                           actors=["Israel"], place="Gaza", source_urls=["http://a"]),
            CandidateEvent(date="2019-01-01", title="Years outside the window",
                           actors=["Israel"], place="Gaza", source_urls=["http://b"]),
        ]),
    }))
    res = scan(ScanRequest(period_start="2024-01-01", period_end="2024-12-31"),
               llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode())
    assert [p.event.title for p in res.proposals] == ["Inside the window"]
    assert res.stats["out_of_window"] == 1
    assert llm.calls.count("ResolverOutput") == 1, "the dropped candidate must cost no LLM calls"


def test_a_single_day_window_keeps_only_that_day():
    llm = FakeLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[
            CandidateEvent(date="2024-05-01", title="That day", actors=["X"], source_urls=["http://a"]),
            CandidateEvent(date="2024-05-02", title="The next day", actors=["X"], source_urls=["http://b"]),
        ]),
    }))
    res = scan(ScanRequest(period_start="2024-05-01", period_end="2024-05-01"),
               llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode())
    assert [p.event.title for p in res.proposals] == ["That day"]


def test_candidates_are_processed_oldest_first_regardless_of_significance():
    # Status may only move on the chronologically latest event, so execution order must be by
    # date even though SELECTION (what survives --limit) is by significance.
    seen = []

    class _OrderLLM(FakeLLM):
        def structured(self, model, system, user):
            if model.__name__ == "ResolverOutput":
                seen.append("2024-01-05" if "2024-01-05" in user else "2024-07-07")
            return super().structured(model, system, user)

    llm = _OrderLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[
            # Both clear the significance bar — otherwise the trivial one is dropped before the
            # loop and this stops testing ordering. Selection order is still significance-first.
            CandidateEvent(date="2024-07-07", title="Later but less consequential",
                           actors=["X"], source_urls=["http://a"], significance=3),
            CandidateEvent(date="2024-01-05", title="Earlier and major",
                           actors=["X"], source_urls=["http://b"], significance=5),
        ]),
    }))
    scan(ScanRequest(period_start="2024-01-01", period_end="2024-12-31"),
         llm=llm, search=FakeSearch(ITEMS), base=BASE,
         settings=Settings(), geocode=FakeGeocode())
    assert seen == ["2024-01-05", "2024-07-07"]


# ---- duplicates cost nothing to reject ------------------------------------------------------

def test_an_event_the_conflict_already_has_is_dropped_before_any_llm_spend():
    base = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR", "PSE"],
                         start=2023, status="active",
                         events=[{"date": "2024-05-01", "title": "Israeli strike on Gaza City"}])]
    llm = FakeLLM(_happy())
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=base,
               settings=Settings(), geocode=FakeGeocode())
    assert res.proposals == []
    assert any("already recorded" in d for d in res.dropped)
    assert "ResolverOutput" not in llm.calls, "a known duplicate must not cost Resolver/Enrich/Verify"


def test_a_continuing_operation_is_not_recorded_again_the_next_day():
    base = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR"],
                         start=2023, status="active",
                         events=[{"date": "2024-04-30", "title": "Israeli strike on Gaza City",
                                  "kind": "attack"}])]
    llm = FakeLLM(_happy())          # candidate is 2024-05-01, same title, same kind
    res = scan(_req(), llm=llm, search=FakeSearch(ITEMS), base=base,
               settings=Settings(), geocode=FakeGeocode())
    assert res.proposals == [], "day two of the same operation is the same thread, not a new event"


def test_a_genuinely_different_event_on_the_same_day_still_gets_through():
    base = [BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR"],
                         start=2023, status="active",
                         events=[{"date": "2024-05-01", "title": "Ceasefire talks open in Cairo",
                                  "kind": "milestone"}])]
    res = _scan(_happy(), base=base)
    assert len(res.proposals) == 1, "the guard is precision-tuned; it must not swallow real events"


# ---- consequence, not violence --------------------------------------------------------------

def test_a_routine_event_is_dropped_before_anything_is_spent_on_it():
    """The atlas's flood control, and the reason it exists.

    A live day produced five proposals, three of them routine overnight drone strikes in an
    ongoing war. The atlas gives the whole of WWII 15 events; at that rate a year of scanning
    would add three times the entire five-century dataset in war reporting.

    Routine events must not reach Resolver/Enrich/Verify at all — gating them after a fact check
    is both wasted spend and the wrong question, since significance is a property of the event
    rather than a tiebreak among things that already passed.
    """
    llm = FakeLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[CandidateEvent(
            date="2024-05-01", title="Routine exchange of fire", actors=["Israel"],
            place="Gaza", source_urls=["http://a"], significance=1)]),
    }))
    res = scan(_req(("1800-01-01", "2030-12-31")), llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode())
    assert res.proposals == [], "a routine incident must not become a proposal"
    assert res.stats["routine"] == 1
    assert any("routine (significance 1" in d for d in res.dropped),         "and it must be logged, so a bar set too high looks different from a quiet day"
    assert "ResolverOutput" not in llm.calls, "nothing should have been spent resolving it"


def test_a_low_severity_but_high_consequence_event_still_publishes():
    # A ceasefire is severity 1 and significance 5. Gating on severity would throw away exactly
    # the events a historical atlas most wants.
    res = _scan(_happy({
        ExtractorOutput: ExtractorOutput(events=[CandidateEvent(
            date="2024-05-01", title="Ceasefire signed", actors=["Israel"], place="Gaza",
            source_urls=["http://a", "http://b"], significance=5)]),
        EnrichOutput: _enrich(event_kind="ceasefire", severity=1),
    }))
    p = res.proposals[0]
    assert p.event.severity == 1 and p.needs_human is False


def test_significance_is_judged_not_taken_from_the_extractor():
    """The bug this whole gate existed to prevent, and didn't.

    CandidateEvent.significance DEFAULTS to 3 and the gate was `< 3`, so anything the Extractor
    did not explicitly score landed exactly on the pass side of its own threshold. The question
    was built in judge.py, tested there, and never called — so every typed score went to the
    judge except the one the flood control depended on.
    """
    from conflict_updater.judge import Judgement

    class _SigJudge:
        """Answers significance only; abstains on everything else, as NullJudge does."""

        def __init__(self, score):
            self.score = score
            self.asked = []

        def ask(self, state, questions):
            self.asked.append(questions)
            return {q: Judgement(self.score if q.startswith("c") else None) for q in questions}

    # The Extractor claims this matters (5). The judge says it is routine continuation (1).
    j = _SigJudge(1)
    llm = FakeLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[CandidateEvent(
            date="2024-05-01", title="Overnight drone strikes continue", actors=["Russia"],
            place="Kyiv", source_urls=["http://a"], significance=5)]),
    }))
    res = scan(_req(("1800-01-01", "2030-12-31")), llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode(), judge=j)
    assert res.stats["routine"] == 1, "the judge's score must win over the extractor's claim"
    assert res.proposals == []
    # and the reverse: a judge that rates it consequential lets it through
    j2 = _SigJudge(4)
    llm2 = FakeLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[CandidateEvent(
            date="2024-05-01", title="Ceasefire signed", actors=["Israel"], place="Gaza",
            source_urls=["http://a", "http://b"], significance=1)]),
    }))
    res2 = scan(_req(("1800-01-01", "2030-12-31")), llm=llm2, search=FakeSearch(ITEMS), base=BASE,
                settings=Settings(), geocode=FakeGeocode(), judge=j2)
    assert res2.stats["routine"] == 0, "a low extractor score must not veto a judged-major event"
    assert len(res2.proposals) == 1


def test_a_judge_outage_does_not_silently_empty_the_scan():
    """A TypeSafe outage must look like "no judge", not like "no events".

    `system_one` used to be called outside any try, so a rate limit or a network blip propagated
    out of JevJudge.ask and failed every candidate in resolver/enrich/verify — a red run with an
    empty atlas, indistinguishable from a genuinely quiet day. The guard belongs inside ask(),
    which is the single point all five agents route through.
    """
    from conflict_updater.judge import JevJudge

    class _DeadClient:
        def system_one(self, **kw):
            raise RuntimeError("503 from the judge")

    broken = JevJudge.__new__(JevJudge)          # bypass __init__: no SDK, no key, no network
    broken._client, broken._model = _DeadClient(), None
    assert all(v.value is None for v in
               broken.ask({}, {"x": __import__("conflict_updater.judge", fromlist=["judge"])
                               .significance_q()}).values())

    _Broken = lambda: broken  # noqa: E731 - the pipeline just needs something with .ask

    llm = FakeLLM(_happy({
        ExtractorOutput: ExtractorOutput(events=[CandidateEvent(
            date="2024-05-01", title="Ceasefire signed", actors=["Israel"], place="Gaza",
            source_urls=["http://a", "http://b"], significance=4)]),
    }))
    res = scan(_req(("1800-01-01", "2030-12-31")), llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode(), judge=_Broken())
    assert len(res.proposals) == 1, "a judge outage must not look like a quiet day"


def test_a_run_records_when_it_fell_back_to_another_model():
    """A degraded run must not look like a clean one.

    The failover prints a line and carries on, so a scan half-answered by the free backup is
    indistinguishable in the ledger from one answered entirely by the model you configured.
    Measured live: z-ai/glm-5.3-flash intermittently returns an empty reply on structured calls.
    """
    llm = FakeLLM(_happy())
    res = scan(_req(("1800-01-01", "2030-12-31")), llm=llm, search=FakeSearch(ITEMS), base=BASE,
               settings=Settings(), geocode=FakeGeocode())
    assert res.stats["model_failovers"] == 0

    llm.failovers = 2
    res2 = scan(_req(("1800-01-01", "2030-12-31")), llm=llm, search=FakeSearch(ITEMS), base=BASE,
                settings=Settings(), geocode=FakeGeocode())
    assert res2.stats["model_failovers"] == 2
