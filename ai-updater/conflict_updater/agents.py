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
    ScoperOutput, ExtractorOutput, ResolverOutput, EnrichOutput, VerifyOutput, Event,
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


def enrich(llm: LLMClient, cand: CandidateEvent, items: list[RawItem], is_new: bool, today: str,
           parent_type: Optional[str] = None, parent_parties: Optional[list] = None,
           current_status: Optional[str] = None) -> EnrichOutput:
    """One call: kind, type (if new), severity, roles, location, summary, status, span. Replaces the
    seven per-field enricher calls — same guidance, one round-trip."""
    ctx = ""
    if parent_type or parent_parties:
        ctx = ("\nParent conflict (keep type & roles consistent — do not flip):\n"
               f"  type={parent_type}\n  existing_parties={_j(parent_parties or [])}\n"
               f"  current_status={current_status or 'active'}")
    user = (
        f"today={today}\nis_new_conflict={is_new}{ctx}\n\n"
        f"Event:\n{_j(cand)}\n\nEvidence snippets:\n{_j([i.snippet for i in items][:8])}"
    )
    return llm.structured(EnrichOutput, P.ENRICH_SYS, user)


def verify(llm: LLMClient, event: Event, items: list[RawItem], is_new: bool) -> VerifyOutput:
    """One call: fact-check the event against its sources AND decide auto_approve vs needs_human."""
    used = [i.model_dump() for i in items if i.url in {s.url for s in event.sources}] or \
           [i.model_dump() for i in items]
    user = (f"is_new_conflict={is_new}\nEvent:\n{_j(event)}\n\n"
            f"Source items (with outlet/lang):\n{_j(used)}")
    return llm.structured(VerifyOutput, P.VERIFY_SYS, user)
