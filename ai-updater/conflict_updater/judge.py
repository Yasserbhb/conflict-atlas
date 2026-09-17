"""Typed decisions — the parts of the pipeline that are a choice, a score, or a confidence.

The rule this module exists to enforce: **anything that picks from a fixed set of options, rates
a degree, or reports a confidence goes to a System One model. The LLM keeps only prose.**

That split is not stylistic. A confidence an LLM emits is a *token it generates* — nothing
connects "0.85" to being right 85% of the time, yet `auto_approve_confidence` gates everything
this pipeline publishes on exactly that number. TypeSafe's Jev returns a probability distribution
over the options you defined and derives confidence from its shape, which is a mechanism rather
than a plausible-looking float. Same reason for the rest: a 13-way event-kind is a classification,
and asking a text generator to emit one and hoping it stays inside the vocabulary is the long way
round.

What stays on the LLM, deliberately: search queries, event titles, the one-sentence summary, and
the open question attached to a held event. Those are genuinely writing.

Shape follows search.py / geocode.py / structured_source.py — Protocol + real + Null + factory —
so the whole suite still runs offline with no keys.

VERIFIED LIVE against typesafe-sdk 0.6.0: Choice returns the option string plus a
confidence and a full distribution; Noul returns a probability of yes and NO separate
confidence; Score returns a probability-weighted float over ZERO-indexed levels
(legend {0: ..., 4: ...}), so a 1-5 field needs +1 after rounding.
"""
from __future__ import annotations

from typing import Optional, Protocol

from .schema import ConflictType, EventKind, Role, Status


class Judgement:
    """One typed answer plus how sure the model is.

    `confidence` is None for a yes/no (a Noul carries its probability in `value` and has no
    separate confidence), and for the Null backend, where "no opinion" must be distinguishable
    from "confidently unsure".
    """

    __slots__ = ("value", "confidence", "probabilities", "raw")

    def __init__(self, value, confidence: Optional[float] = None,
                 probabilities: Optional[dict] = None, raw=None):
        self.value = value
        self.confidence = confidence
        self.probabilities = probabilities or {}
        # For a Score: the un-rounded position, e.g. 2.8. Worth keeping — "nearly a 4" and
        # "barely a 3" are the same rounded level but not the same event.
        self.raw = raw

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Judgement({self.value!r}, confidence={self.confidence!r})"


class Judge(Protocol):
    def ask(self, state: dict, questions: dict) -> dict[str, Judgement]:
        """Answer several independent questions about the same state in ONE call.

        Questions are a dict of `{id: spec}` where spec is one of the builders below. They are
        answered in parallel and cannot see each other's answers, so anything that depends on a
        previous answer needs a second call.
        """
        ...


# ---- question builders ---------------------------------------------------------------------
# Thin dicts rather than SDK objects so the pipeline can describe a question without importing
# typesafe_sdk — which keeps the offline tests dependency-free.

def choice(instructions: str, options: dict[str, Optional[str]]) -> dict:
    """Pick exactly one of `options` ({value: what it means})."""
    return {"kind": "choice", "instructions": instructions, "criteria": options}


def noul(instructions: str) -> dict:
    """Does this condition hold? Answer is a probability of yes."""
    return {"kind": "noul", "instructions": instructions}


def score(instructions: str, levels: list[str]) -> dict:
    """Where on an ordered scale, `levels` low to high. Each level must describe a concrete
    situation and stand on its own — "3" is not a level, "an organised armed clash" is."""
    return {"kind": "score", "instructions": instructions, "criteria": levels}


# ---- the vocabularies, as questions ---------------------------------------------------------
# These mirror schema.py's Literals. The taxonomy sync test already guards those against the
# app's taxonomy.js; building the options FROM the Literals means this layer cannot drift either.

def _opts(literal) -> dict[str, None]:
    import typing
    return {v: None for v in typing.get_args(literal)}


def event_kind_q() -> dict:
    return choice("What kind of event is this? Judge the event itself, not its consequences.",
                  _opts(EventKind))


def conflict_type_q() -> dict:
    return choice("What kind of conflict is this event part of?", _opts(ConflictType))


def status_q() -> dict:
    return choice(
        "Given this event, what is the conflict's state now? A pause or ceasefire is not an "
        "ending; 'resolved' needs a positive terminal settlement, not merely quiet.",
        _opts(Status))


def role_q(actor: str) -> dict:
    return choice(f"What role does {actor} play in this event?", _opts(Role))


def severity_q() -> dict:
    return score(
        "How severe is this event — the scale of violence and harm, not its historical importance.",
        ["a threat, protest or non-violent measure",
         "an isolated incident with few or no casualties",
         "an organised armed clash",
         "sustained fighting or a mass-casualty attack",
         "a massacre, siege or campaign killing very large numbers"])


def significance_q() -> dict:
    return score(
        "How historically CONSEQUENTIAL is this event — would a history of this conflict "
        "mention it? This is not severity: a ceasefire may kill nobody and still be pivotal.",
        ["routine, would not be recorded",
         "minor, of interest only in a detailed chronology",
         "notable, a history of this conflict would mention it",
         "a turning point in the conflict",
         "a defining event that shapes the whole conflict"])


# ---- backends --------------------------------------------------------------------------------

class JevJudge:
    """TypeSafe System One. All questions in one parallel request."""

    def __init__(self, model: Optional[str] = None):
        from typesafe_sdk import TypeSafeClient  # lazy: import only when actually used
        self._client = TypeSafeClient()
        self._model = model

    def _build(self, spec: dict):
        from typesafe_sdk import Choice, Noul, Score
        kind = spec["kind"]
        if kind == "choice":
            return Choice(instructions=spec["instructions"], criteria=spec["criteria"])
        if kind == "score":
            return Score(instructions=spec["instructions"], criteria=spec["criteria"])
        return Noul(instructions=spec["instructions"])

    def ask(self, state: dict, questions: dict) -> dict[str, Judgement]:
        resp = self._client.system_one(
            state=state, questions={k: self._build(v) for k, v in questions.items()})
        out: dict[str, Judgement] = {}
        for qid, spec in questions.items():
            kind = spec["kind"]
            try:
                if kind == "choice":
                    a = resp.choices[qid]
                    out[qid] = Judgement(a.choice, getattr(a, "confidence", None),
                                         getattr(a, "probabilities", None))
                elif kind == "score":
                    a = resp.scores[qid]
                    # Score is a probability-weighted position over 0-indexed levels (verified
                    # live: legend is {0: ..., 4: ...}). The pipeline's severity/significance are
                    # 1-5 ints, so shift by one after rounding.
                    lvl = int(round(a.score)) + 1
                    n = len(spec["criteria"])
                    out[qid] = Judgement(max(1, min(n, lvl)), getattr(a, "confidence", None),
                                         getattr(a, "probabilities", None), raw=a.score)
                else:
                    a = resp.nouls[qid]
                    # A Noul IS a probability of yes (verified live: 0.97), with no separate
                    # confidence — 0.5 means "as likely as not", not "medium intensity".
                    out[qid] = Judgement(a.noul, None, None, raw=a.noul)
            except Exception:
                out[qid] = Judgement(None)      # a missing answer must not take the scan down
        return out


class NullJudge:
    """No typed backend — the default. Returns no opinion for every question, which the callers
    read as "fall back to the LLM's own answer". This is what keeps the pipeline working, and the
    whole test suite offline, without a TypeSafe key."""

    def ask(self, state: dict, questions: dict) -> dict[str, Judgement]:
        return {qid: Judgement(None) for qid in questions}


def get_judge(settings) -> Judge:
    if getattr(settings, "judge_backend", "none") == "jev":
        return JevJudge(getattr(settings, "judge_model", None) or None)
    return NullJudge()
