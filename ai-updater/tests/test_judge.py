"""Typed decisions: choices, scores and confidences.

Offline throughout — FakeJudge stands in for the service, exactly as fakes.py does for the LLM,
search and geocoder. The live shape these fakes imitate was verified against typesafe-sdk 0.6.0:
Choice returns an option plus a confidence and a distribution; Noul returns a probability of yes
and no separate confidence; Score returns a probability-weighted float over ZERO-indexed levels.
"""
import pytest

from conflict_updater import judge as J
from conflict_updater.judge import Judgement, NullJudge, get_judge


class FakeJudge:
    """Answers from a canned {question_id: Judgement} table. Records what it was asked."""

    def __init__(self, answers: dict):
        self.answers = answers
        self.asked: list[dict] = []
        self.states: list[dict] = []

    def ask(self, state, questions):
        self.asked.append(questions)
        self.states.append(state)
        return {qid: self.answers.get(qid, Judgement(None)) for qid in questions}


# ---- the question builders mirror the schema, so they cannot drift from it ------------------

def test_vocabularies_come_from_the_schema_literals():
    import typing
    from conflict_updater.schema import ConflictType, EventKind, Role, Status
    assert set(J.event_kind_q()["criteria"]) == set(typing.get_args(EventKind))
    assert set(J.conflict_type_q()["criteria"]) == set(typing.get_args(ConflictType))
    assert set(J.status_q()["criteria"]) == set(typing.get_args(Status))
    assert set(J.role_q("France")["criteria"]) == set(typing.get_args(Role))


def test_scores_describe_concrete_situations_not_numbers():
    # "3" is not a level a model can reason about; "an organised armed clash" is.
    for q in (J.severity_q(), J.significance_q()):
        assert len(q["criteria"]) == 5
        assert all(isinstance(c, str) and len(c) > 12 for c in q["criteria"])


def test_severity_and_significance_ask_different_questions():
    # The whole flood-control design rests on these being distinct: a ceasefire is severity 1 and
    # significance 5.
    assert J.severity_q()["criteria"] != J.significance_q()["criteria"]
    assert "not severity" in J.significance_q()["instructions"]


# ---- the null backend keeps everything offline ----------------------------------------------

def test_null_judge_has_no_opinion():
    a = NullJudge().ask({}, {"kind": J.event_kind_q()})
    assert a["kind"].value is None, "no opinion must be distinguishable from a confident answer"


def test_factory_defaults_to_null():
    class _S:
        judge_backend = "none"
    assert isinstance(get_judge(_S()), NullJudge)


# ---- resolver: one choice, ambiguity from low confidence -------------------------------------

def _cands():
    from conflict_updater.store import BaseConflict
    return [(BaseConflict(id="seed_gaza", title="Gaza War", start=2023,
                          events=[{"date": "2026-01-10", "title": "Strike on Khan Younis"}]), 0.8),
            (BaseConflict(id="seed_ukraine", title="Ukraine War", start=2022, events=[]), 0.3)]


def _cand():
    from conflict_updater.schema import CandidateEvent
    return CandidateEvent(date="2026-01-14", title="Strike on Gaza City", actors=["Israel"])


def test_resolver_attaches_to_the_chosen_conflict_without_an_llm():
    from conflict_updater import agents
    j = FakeJudge({"match": Judgement("seed_gaza", 0.95)})
    out = agents.resolver(None, _cand(), _cands(), judge=j)   # llm=None proves it is unused
    assert out.decision == "attach" and out.conflict_id == "seed_gaza"


def test_resolver_low_confidence_becomes_ambiguous_rather_than_a_guess():
    from conflict_updater import agents
    j = FakeJudge({"match": Judgement("seed_gaza", 0.31)})
    out = agents.resolver(None, _cand(), _cands(), judge=j, ambiguous_below=0.5)
    assert out.decision == "ambiguous", "an unsure attach must go to a human, not into the atlas"
    assert "0.31" in out.reason


def test_resolver_recognises_an_event_already_recorded():
    from conflict_updater import agents
    j = FakeJudge({"match": Judgement(J.__dict__.get("KNOWN") or "__already_recorded__", 0.9)})
    from conflict_updater.agents import KNOWN
    j = FakeJudge({"match": Judgement(KNOWN, 0.9)})
    assert agents.resolver(None, _cand(), _cands(), judge=j).decision == "known"


def test_resolver_no_match_founds_a_new_conflict():
    from conflict_updater import agents
    from conflict_updater.agents import NEW
    j = FakeJudge({"match": Judgement(NEW, 0.9)})
    assert agents.resolver(None, _cand(), _cands(), judge=j).decision == "new"


def test_the_resolver_choice_always_offers_a_no_match_option():
    # "the model cannot choose an omitted value" — without this it would be forced to attach.
    from conflict_updater import agents
    from conflict_updater.agents import KNOWN, NEW
    j = FakeJudge({"match": Judgement("seed_gaza", 0.9)})
    agents.resolver(None, _cand(), _cands(), judge=j)
    options = j.asked[0]["match"]["criteria"]
    assert NEW in options and KNOWN in options
    assert "seed_gaza" in options and "seed_ukraine" in options


# ---- verify: the decision is code, the confidence is derived ----------------------------------

def _event():
    from conflict_updater.schema import Event, Source
    return Event(date="2026-01-14", title="Strike on Gaza City", description="A strike.",
                 sources=[Source(url="http://a", outlet="reuters.com")])


def test_verify_passes_only_when_confidence_clears_the_bar():
    from conflict_updater import agents
    j = FakeJudge({"verdict": Judgement("pass", 0.93), "supported": Judgement(0.98)})
    v = agents.verify(None, _event(), [], is_new=False, judge=j, auto_approve_confidence=0.8)
    assert v.verdict == "pass" and v.decision == "auto_approve"


def test_a_pass_the_model_is_unsure_about_is_still_held():
    # The threshold is applied in Python. The model judges; it does not decide policy.
    from conflict_updater import agents
    j = FakeJudge({"verdict": Judgement("pass", 0.62), "supported": Judgement(0.9)})
    v = agents.verify(None, _event(), [], is_new=False, judge=j, auto_approve_confidence=0.8)
    assert v.decision == "needs_human" and v.confidence == 0.62


def test_a_failed_fact_check_says_what_stopped_it():
    from conflict_updater import agents
    j = FakeJudge({"verdict": Judgement("fail", 1.0), "supported": Judgement(0.11)})
    v = agents.verify(None, _event(), [], is_new=False, judge=j)
    assert v.decision == "needs_human"
    assert "fail" in v.open_question and "11%" in v.open_question


def test_verify_falls_back_to_the_llm_when_the_judge_abstains():
    from conflict_updater import agents
    from conflict_updater.schema import VerifyOutput

    class _LLM:
        def structured(self, model, system, user):
            return VerifyOutput(verdict="pass", confidence=0.9, decision="auto_approve")

    j = FakeJudge({})            # every answer is Judgement(None)
    v = agents.verify(_LLM(), _event(), [], is_new=False, judge=j)
    assert v.verdict == "pass", "an unanswered question must not silently become a rejection"


# ---- enrich: judge wins on typed fields, LLM keeps the prose ----------------------------------

def test_the_judge_overrides_the_llms_typed_fields_but_not_its_summary():
    from conflict_updater import agents
    from conflict_updater.schema import EnrichOutput, Party

    class _LLM:
        def structured(self, model, system, user):
            return EnrichOutput(event_kind="milestone", severity=1, status="ended",
                                summary="A carefully written sentence.",
                                parties=[Party(country_id="ISR", role="mediator")])

    j = FakeJudge({
        "kind": Judgement("attack", 0.9),
        "severity": Judgement(4, 0.8, raw=3.2),
        "status": Judgement("active", 1.0),
        "role::ISR": Judgement("aggressor", 0.97),
    })
    out = agents.enrich(_LLM(), _cand(), [], is_new=False, today="2026-01-14", judge=j)
    assert out.event_kind == "attack"
    assert out.severity == 4
    assert out.status == "active"
    assert out.parties[0].role == "aggressor"
    assert out.summary == "A carefully written sentence.", "prose stays with the LLM"


def test_enrich_keeps_the_llms_answer_where_the_judge_has_none():
    from conflict_updater import agents
    from conflict_updater.schema import EnrichOutput

    class _LLM:
        def structured(self, model, system, user):
            return EnrichOutput(event_kind="battle", severity=3, status="active", summary="x")

    out = agents.enrich(_LLM(), _cand(), [], is_new=False, today="2026-01-14", judge=FakeJudge({}))
    assert out.event_kind == "battle" and out.severity == 3


def test_conflict_type_is_only_asked_when_founding_a_new_conflict():
    from conflict_updater import agents
    from conflict_updater.schema import EnrichOutput

    class _LLM:
        def structured(self, model, system, user):
            return EnrichOutput(event_kind="battle", severity=3, status="active", summary="x")

    j = FakeJudge({})
    agents.enrich(_LLM(), _cand(), [], is_new=False, today="2026-01-14", judge=j)
    assert "type" not in j.asked[0]
    j2 = FakeJudge({})
    agents.enrich(_LLM(), _cand(), [], is_new=True, today="2026-01-14", judge=j2)
    assert "type" in j2.asked[0]


def test_all_the_typed_questions_go_in_one_call():
    # They are independent judgements over the same state, so they are answered in parallel.
    from conflict_updater import agents
    from conflict_updater.schema import EnrichOutput, Party

    class _LLM:
        def structured(self, model, system, user):
            return EnrichOutput(event_kind="battle", severity=3, status="active", summary="x",
                                parties=[Party(country_id="ISR", role="aggressor"),
                                         Party(country_id="PSE", role="victim")])

    j = FakeJudge({})
    agents.enrich(_LLM(), _cand(), [], is_new=True, today="2026-01-14", judge=j)
    assert len(j.asked) == 1, "one round trip, not one per field"
    assert set(j.asked[0]) == {"kind", "severity", "status", "type", "role::ISR", "role::PSE"}
