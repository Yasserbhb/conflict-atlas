"""Structured conflict-data anchors (ARCHITECTURE.md §8) — a verified dataset row fed straight
in as a CandidateEvent(source_kind="structured"), skipping the Extractor LLM call entirely (the
row is already structured: date/actors/place/fatalities, nothing to extract from raw text).

Same Protocol+factory+Null convention as search.py/geocode.py.
"""
from __future__ import annotations

from typing import Optional, Protocol

from .schema import CandidateEvent


class StructuredSource(Protocol):
    def fetch(self, period_start: str, period_end: str, region: Optional[str] = None) -> list[CandidateEvent]:
        ...


class UcdpStructuredSource:
    """Pulls UCDP Georeferenced Event Dataset (GED) rows as CandidateEvents.

    NOT YET LIVE-VERIFIED: the exact UCDP GED API endpoint and response shape need checking
    against UCDP's current API docs before this can be pointed at the real service — the request/
    parsing logic below is a placeholder shape, not a confirmed integration. Wire the real HTTP
    call here once that's verified; until then this raises to fail loudly rather than silently
    returning fabricated data.
    """

    def __init__(self, base_url: str = "https://ucdpapi.pcr.uu.se/api/gedevents/latest"):
        self._base_url = base_url

    def fetch(self, period_start: str, period_end: str, region: Optional[str] = None) -> list[CandidateEvent]:
        raise NotImplementedError(
            "UcdpStructuredSource: UCDP GED API shape not yet verified against live docs — "
            "see structured_source.py's class docstring. Use NullStructuredSource (the default) "
            "until this is wired for real."
        )


class NullStructuredSource:
    """No-op backend — the default. No structured-source events are fetched."""

    def fetch(self, period_start: str, period_end: str, region: Optional[str] = None) -> list[CandidateEvent]:
        return []


def get_structured_source(settings) -> StructuredSource:
    if getattr(settings, "structured_source_backend", "none") == "ucdp":
        return UcdpStructuredSource()
    return NullStructuredSource()
