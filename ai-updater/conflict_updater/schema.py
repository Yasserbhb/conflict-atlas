"""Typed models for the pipeline.

Domain models mirror the app (`src/utils/taxonomy.js`, `utils/eventKinds.js`) so a
proposal drops straight into `seed.json`. Agent I/O models are what each agent emits;
they are used directly as LLM structured-output schemas.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

# ---- controlled vocabularies (must match the app) ----
ConflictType = Literal[
    "war", "civil_war", "genocide", "occupation",
    "proxy_war", "sanctions", "disputed_territory",
    # note: "funding" is intentionally NOT a type — it's the `funder` ROLE.
]
Role = Literal[
    "aggressor", "defender", "victim", "funder", "proxy",
    "occupier", "mediator", "sanctioner", "sanctioned",
]
EventKind = Literal[
    "attack", "battle", "offensive", "atrocity", "displacement", "ceasefire",
    "treaty", "settlement", "escalation", "intervention", "sanction",
    "annexation", "milestone",
]
Status = Literal["active", "easing", "suspended", "dormant", "ended", "resolved"]
Verdict = Literal["pass", "fail", "uncertain"]
Decision = Literal["known", "attach", "new", "ambiguous"]


# ---- domain models (shape of seed.json) ----
class Location(BaseModel):
    lat: float
    lng: float
    label: Optional[str] = None


class Source(BaseModel):
    url: str
    outlet: Optional[str] = None
    lang: str = "en"
    alignment: Optional[str] = None  # e.g. western | russian | iranian | arab | independent


class Party(BaseModel):
    country_id: str  # ISO 3166-1 alpha-3
    role: Role


class Event(BaseModel):
    id: Optional[str] = None
    date: str  # "YYYY" | "YYYY-MM" | "YYYY-MM-DD"
    title: str
    kind: EventKind = "milestone"
    severity: int = Field(3, ge=1, le=5)
    location: Optional[Location] = None  # null == place-less (e.g. nationwide famine)
    parties: list[str] = Field(default_factory=list)  # ISO3 subset
    description: str = ""
    sources: list[Source] = Field(default_factory=list)


class Conflict(BaseModel):
    id: str
    title: str
    type: ConflictType
    severity: int = Field(3, ge=1, le=5)
    start_date: str
    end_date: Optional[str] = None
    ongoing: bool = True
    status: Status = "active"
    description: str = ""
    parties: list[Party] = Field(default_factory=list)
    involved_countries: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)  # alternate names (many languages)
    tags: list[str] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)


# ---- the request ----
class ScanRequest(BaseModel):
    period_start: str  # a year or ISO date
    period_end: str
    region: Optional[str] = None
    topic: Optional[str] = None


# ---- agent I/O ----
class SearchQuery(BaseModel):
    query: str
    lang: str = "en"


class ScoperOutput(BaseModel):
    queries: list[SearchQuery]
    watch_conflict_ids: list[str] = Field(default_factory=list)  # existing conflicts to re-check


class RawItem(BaseModel):
    title: str
    url: str
    snippet: str = ""
    outlet: Optional[str] = None
    lang: str = "en"
    alignment: Optional[str] = None
    date: Optional[str] = None


class CandidateEvent(BaseModel):
    date: str
    title: str
    action: str = ""
    actors: list[str] = Field(default_factory=list)  # free-text actor names, not yet ISO3
    place: Optional[str] = None
    source_urls: list[str] = Field(default_factory=list)


class ExtractorOutput(BaseModel):
    events: list[CandidateEvent]


class ResolverOutput(BaseModel):
    decision: Decision
    conflict_id: Optional[str] = None       # set when decision == attach|known
    new_aliases: list[str] = Field(default_factory=list)
    reason: str = ""


class ClassifyOutput(BaseModel):
    event_kind: EventKind
    conflict_type: Optional[ConflictType] = None  # only when proposing a new conflict


class SeverityOutput(BaseModel):
    severity: int = Field(ge=1, le=5)
    reason: str = ""


class RolesOutput(BaseModel):
    parties: list[Party]


class GeoOutput(BaseModel):
    location: Optional[Location] = None  # null when genuinely place-less


class SummaryOutput(BaseModel):
    text: str


class LifecycleOutput(BaseModel):
    status: Status
    is_regression: bool = False
    reason: str = ""


class FactCheckOutput(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    independent_sources: int = 0
    cross_alignment: bool = False
    reasons: list[str] = Field(default_factory=list)


class ReconcilerOutput(BaseModel):
    decision: Literal["auto_approve", "needs_human"]
    rationale: str = ""
    open_question: Optional[str] = None


# ---- the pipeline's output ----
class Proposal(BaseModel):
    kind: Literal["attach", "new_conflict"]
    target_conflict_id: Optional[str] = None
    event: Event
    roles: list[Party] = Field(default_factory=list)   # per-event country roles (for conflict.parties)
    status: Optional[Status] = None                    # lifecycle verdict (for conflict.status)
    new_conflict: Optional[Conflict] = None
    new_aliases: list[str] = Field(default_factory=list)
    factcheck: Optional[FactCheckOutput] = None
    reconcile: Optional[ReconcilerOutput] = None
    needs_human: bool = True
    provisional: bool = False  # held by the recency gate


class ScanResult(BaseModel):
    request: ScanRequest
    proposals: list[Proposal] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)   # reasons things were dropped
    stats: dict = Field(default_factory=dict)
