"""The agent team. Each function is one agent: it builds a user prompt from typed
inputs and asks the LLMClient for a typed output. No agent knows about the others.
"""
from __future__ import annotations

import json
from typing import Optional

from .llm import LLMClient
from . import prompts as P
from .store import BaseConflict
from . import judge as J
from .schema import (
    Party, ScanRequest, RawItem, CandidateEvent,
    ScoperOutput, ExtractorOutput, ResolverOutput, EnrichOutput, VerifyOutput, Event,
)


# Sentinel options for the resolver choice, prefixed so they cannot collide with a
# real conflict id.
NEW = "__new_conflict__"
KNOWN = "__already_recorded__"


def _j(obj) -> str:
    from pydantic import BaseModel
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=2)
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def scoper(llm: LLMClient, req: ScanRequest, watch_ids: list[str]) -> ScoperOutput:
    user = (
        f"Window: {req.period_start} .. {req.period_end}\n"
        f"Region: {req.region or 'any'}\nTopic: {req.topic or 'any'}\n"
        f"Existing conflict ids that might have events here: {watch_ids[:60]}"
    )
    return llm.structured(ScoperOutput, P.SCOPER_SYS, user)


def extractor(llm: LLMClient, items: list[RawItem], req: ScanRequest) -> ExtractorOutput:
    user = (
        f"Only events dated within {req.period_start}..{req.period_end}.\n\n"
        f"Source items:\n{_j([i.model_dump() for i in items])}"
    )
    return llm.structured(ExtractorOutput, P.EXTRACTOR_SYS, user)


def _nearest_events(events: list[dict], around: str, k: int) -> list[dict]:
    """The k events closest in time to `around`, returned in date order."""
    from .dates import key as date_key
    target = date_key(around)
    closest = sorted(events or [], key=lambda e: abs_key(date_key(e.get("date")), target))[:k]
    return sorted(closest, key=lambda e: date_key(e.get("date")))


def abs_key(a: str, b: str) -> int:
    """Crude distance between two padded date keys — good enough to rank nearness, and it needs
    no real date parsing so mixed-precision and malformed dates can't raise here."""
    return abs(int(a.replace("-", "") or 0) - int(b.replace("-", "") or 0))


def resolver(llm: LLMClient, cand: CandidateEvent,
             candidates: list[tuple[BaseConflict, float]],
             judge=None, ambiguous_below: float = 0.5) -> ResolverOutput:
    cand_list = [
        {
            "id": c.id, "title": c.title, "aliases": c.aliases, "match_score": round(s, 2),
            # the conflict's EXISTING events, so the resolver can tell known-vs-gap
            # Nearest the candidate's date, not the first 30 in seed order. For a conflict with
            # hundreds of events the recent ones — exactly what a duplicate would match — used to
            # fall outside the slice, which made "known" unreachable and let duplicates through.
            "existing_events": [f"{e.get('date')}: {e.get('title')}"
                                for e in _nearest_events(c.events, cand.date, 30)],
        }
        for c, s in candidates
    ]
    user = f"Candidate event:\n{_j(cand)}\n\nPossible existing conflicts (with their events):\n{_j(cand_list)}"

    # A judge answers this as ONE choice: which existing conflict does this belong to, is it
    # already recorded, or is it new. Ambiguity then falls out of LOW CONFIDENCE rather than
    # being a label the model volunteers about itself — which is the point of having a
    # calibrated distribution over the options instead of a generated string.
    if judge is not None:
        options = {c["id"]: c["title"] for c in cand_list}
        options[NEW] = "None of these — this event belongs to a conflict not in the list"
        options[KNOWN] = "This exact event is already recorded in one of these conflicts"
        ans = judge.ask(
            {"candidate_event": cand.model_dump(), "existing_conflicts": cand_list},
            {"match": J.choice(
                "Which existing conflict does `candidate_event` belong to? Match on meaning, not "
                "wording — the same war is named differently across sources and languages. Check "
                "`existing_events` before answering: an event already listed there is recorded.",
                options)},
        )["match"]
        if ans.value is not None:
            if ans.confidence is not None and ans.confidence < ambiguous_below:
                return ResolverOutput(decision="ambiguous",
                                      reason=f"judge confidence {ans.confidence:.2f}")
            if ans.value == KNOWN:
                return ResolverOutput(decision="known")
            if ans.value == NEW:
                return ResolverOutput(decision="new")
            return ResolverOutput(decision="attach", conflict_id=ans.value)

    return llm.structured(ResolverOutput, P.RESOLVER_SYS, user)


def enrich(llm: LLMClient, cand: CandidateEvent, items: list[RawItem], is_new: bool, today: str,
           parent_type: Optional[str] = None, parent_parties: Optional[list] = None,
           current_status: Optional[str] = None, lifecycle_profile: Optional[dict] = None,
           judge=None) -> EnrichOutput:
    """One call: kind, type (if new), severity, roles, location, summary, status, span. Replaces the
    seven per-field enricher calls — same guidance, one round-trip."""
    ctx = ""
    if parent_type or parent_parties:
        ctx = ("\nParent conflict (keep type & roles consistent — do not flip):\n"
               f"  type={parent_type}\n  existing_parties={_j(parent_parties or [])}\n"
               f"  current_status={current_status or 'active'}")
    if lifecycle_profile:
        p = lifecycle_profile
        ctx += (
            f"\nLifecycle profile for type={parent_type} (config/lifecycle.yml — use THIS instead of a "
            f"generic rule of thumb):\n"
            f"  default_terminal={p.get('default_terminal')}  (what sustained quiet settles into, never 'resolved')\n"
            f"  resolved_requires={p.get('resolved_requires')}  ('resolved' needs one of these, not just quiet)\n"
            f"  dwell_days={p.get('dwell_days')}  (roughly how long quiet must last before leaning terminal)\n"
            f"  regression_label={p.get('regression', 'resumed')!r}  (if this event follows a quiet/terminal phase)"
        )
    user = (
        f"today={today}\nis_new_conflict={is_new}{ctx}\n\n"
        f"Event:\n{_j(cand)}\n\nEvidence snippets:\n{_j([i.snippet for i in items][:8])}"
    )
    out = llm.structured(EnrichOutput, P.ENRICH_SYS, user)
    if judge is None:
        return out

    # The LLM keeps `summary` — that is prose. Everything else here is a choice or a score, so a
    # judge answers them instead, all in ONE parallel call. Asking a text generator to emit one
    # of thirteen event kinds and hoping it stays inside the vocabulary is the long way round.
    qs = {"kind": J.event_kind_q(), "severity": J.severity_q(), "status": J.status_q()}
    if is_new:
        qs["type"] = J.conflict_type_q()
    actors = [pp.country_id for pp in out.parties]
    for a in actors:
        qs[f"role::{a}"] = J.role_q(a)

    ans = judge.ask(
        {"event": cand.model_dump(),
         "evidence": [i.snippet for i in items][:8],
         "parent_conflict": {"type": parent_type, "current_status": current_status or "active"},
         "today": today},
        qs)

    upd = {}
    if ans["kind"].value:
        upd["event_kind"] = ans["kind"].value
    if ans["severity"].value:
        upd["severity"] = ans["severity"].value
    if ans["status"].value:
        upd["status"] = ans["status"].value
    if is_new and ans.get("type") is not None and ans["type"].value:
        upd["conflict_type"] = ans["type"].value
    roles = [Party(country_id=a, role=ans[f"role::{a}"].value)
             for a in actors if ans.get(f"role::{a}") is not None and ans[f"role::{a}"].value]
    if roles:
        upd["parties"] = roles
    return out.model_copy(update=upd) if upd else out


def verify(llm: LLMClient, event: Event, items: list[RawItem], is_new: bool,
           judge=None, auto_approve_confidence: float = 0.8) -> VerifyOutput:
    """Fact-check the event against its sources and report how sure that verdict is.

    With a judge this is a Choice plus a Noul and costs no LLM call. Two things leave the model's
    hands on that path, both deliberately:

      * **The confidence becomes a real one.** An LLM's `confidence: 0.85` is a token it
        generated; nothing ties it to being right 85% of the time, and this pipeline publishes on
        exactly that number. A judge derives it from the distribution over the verdicts.
      * **The decision becomes code.** We used to ask the model for `auto_approve|needs_human`
        AND a confidence, then apply our own threshold on top — the model making policy we then
        second-guessed. Now the model judges and Python decides.

    `independent_sources`/`cross_alignment` are filled in by the caller, which counts them from
    the sources rather than asking anyone.
    """
    used = [i.model_dump() for i in items if i.url in {s.url for s in event.sources}] or            [i.model_dump() for i in items]

    if judge is not None:
        ans = judge.ask(
            {"event": event.model_dump(), "sources": used, "is_new_conflict": is_new},
            {"verdict": J.choice(
                "Do `sources` actually support what `event` claims — the date, the actors, and "
                "what happened?",
                {"pass": "The sources support the event as described",
                 "uncertain": "The sources are thin, partial, or disagree with each other",
                 "fail": "The sources contradict the event, or do not describe it at all"}),
             "supported": J.noul(
                 "Is every factual claim in the event's description backed by at least one of "
                 "`sources`?")},
        )
        v = ans["verdict"]
        if v.value is not None:
            conf = v.confidence if v.confidence is not None else 0.0
            ok = v.value == "pass" and conf >= auto_approve_confidence
            supported = ans["supported"].value
            why = None
            if not ok:
                # Templated, but it names what actually stopped it, which is the useful part.
                why = (f"fact-check returned {v.value!r} at confidence {conf:.2f}"
                       + (f"; only {supported:.0%} of its claims are backed by the cited sources"
                          if isinstance(supported, float) and supported < 0.9 else ""))
            return VerifyOutput(verdict=v.value, confidence=conf,
                                decision="auto_approve" if ok else "needs_human",
                                open_question=why)

    user = (f"is_new_conflict={is_new}\nEvent:\n{_j(event)}\n\n"
            f"Source items (with outlet/lang):\n{_j(used)}")
    return llm.structured(VerifyOutput, P.VERIFY_SYS, user)
