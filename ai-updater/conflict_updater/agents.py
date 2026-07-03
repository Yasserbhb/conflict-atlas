"""The agent team. Each function is one agent: it builds a user prompt from typed
inputs and asks the LLMClient for a typed output. No agent knows about the others.
"""
from __future__ import annotations

import json
from typing import Optional

from .llm import LLMClient
from . import prompts as P
from .store import BaseConflict
from .schema import (
    ScanRequest, RawItem, CandidateEvent,
    ScoperOutput, ExtractorOutput, ResolverOutput, ClassifyOutput, SeverityOutput,
    RolesOutput, GeoOutput, SummaryOutput, LifecycleOutput, FactCheckOutput, ReconcilerOutput,
    Event, Status, ConflictType,
)


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


def resolver(llm: LLMClient, cand: CandidateEvent,
             candidates: list[tuple[BaseConflict, float]]) -> ResolverOutput:
    cand_list = [
        {
            "id": c.id, "title": c.title, "aliases": c.aliases, "match_score": round(s, 2),
            # the conflict's EXISTING events, so the resolver can tell known-vs-gap
            "existing_events": [f"{e.get('date')}: {e.get('title')}" for e in c.events][:30],
        }
        for c, s in candidates
    ]
    user = f"Candidate event:\n{_j(cand)}\n\nPossible existing conflicts (with their events):\n{_j(cand_list)}"
    return llm.structured(ResolverOutput, P.RESOLVER_SYS, user)


def classifier(llm: LLMClient, cand: CandidateEvent, is_new_conflict: bool) -> ClassifyOutput:
    user = f"is_new_conflict={is_new_conflict}\nEvent:\n{_j(cand)}"
    return llm.structured(ClassifyOutput, P.CLASSIFIER_SYS, user)


def severity(llm: LLMClient, cand: CandidateEvent, items: list[RawItem]) -> SeverityOutput:
    user = f"Event:\n{_j(cand)}\n\nEvidence snippets:\n{_j([i.snippet for i in items][:8])}"
    return llm.structured(SeverityOutput, P.SEVERITY_SYS, user)


def roles(llm: LLMClient, cand: CandidateEvent) -> RolesOutput:
    return llm.structured(RolesOutput, P.ROLES_SYS, f"Event:\n{_j(cand)}")


def geolocator(llm: LLMClient, cand: CandidateEvent) -> GeoOutput:
    return llm.structured(GeoOutput, P.GEO_SYS, f"Event:\n{_j(cand)}")


def summarizer(llm: LLMClient, cand: CandidateEvent, items: list[RawItem]) -> SummaryOutput:
    user = f"Event:\n{_j(cand)}\n\nEvidence:\n{_j([i.snippet for i in items][:6])}"
    return llm.structured(SummaryOutput, P.SUMMARY_SYS, user)


def lifecycle(llm: LLMClient, cand: CandidateEvent, conflict_type: Optional[str],
              current_status: Optional[str]) -> LifecycleOutput:
    user = (
        f"conflict_type={conflict_type}\ncurrent_status={current_status or 'active'}\n"
        f"New event:\n{_j(cand)}"
    )
    return llm.structured(LifecycleOutput, P.LIFECYCLE_SYS, user)


def factcheck(llm: LLMClient, event: Event, items: list[RawItem]) -> FactCheckOutput:
    used = [i.model_dump() for i in items if i.url in {s.url for s in event.sources}] or \
           [i.model_dump() for i in items]
    user = f"Event:\n{_j(event)}\n\nSource items (with outlet/alignment/lang):\n{_j(used)}"
    return llm.structured(FactCheckOutput, P.FACTCHECK_SYS, user)


def reconciler(llm: LLMClient, event: Event, fc: FactCheckOutput,
               is_new_conflict: bool) -> ReconcilerOutput:
    user = (
        f"is_new_conflict={is_new_conflict}\nEvent:\n{_j(event)}\n\nFact-check:\n{_j(fc)}"
    )
    return llm.structured(ReconcilerOutput, P.RECONCILER_SYS, user)
