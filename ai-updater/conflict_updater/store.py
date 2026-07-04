"""Read the app's seed.json into a lightweight index for dedup, and write the
pipeline's output (proposals + a human-readable review queue)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from .schema import ScanResult, Proposal, Conflict


class BaseConflict(BaseModel):
    """Just enough of an existing conflict for the Resolver to match against, and for the
    enrichers to stay consistent with (type + existing party roles)."""
    id: str
    title: str
    type: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    involved_countries: list[str] = Field(default_factory=list)
    parties: list[dict] = Field(default_factory=list)  # [{countryId, role}] — for structural roles
    tags: list[str] = Field(default_factory=list)
    start: Optional[int] = None
    end: Optional[int] = None
    status: str = "active"
    events: list[dict] = Field(default_factory=list)  # compact [{date, title}] for gap detection


def _year(s) -> Optional[int]:
    if not s:
        return None
    m = re.match(r"(\d{4})", str(s))
    return int(m.group(1)) if m else None


def _default_status(c: dict) -> str:
    """Most conflicts predate the `status` field and have it missing (not null) — don't just
    assume 'active'. Fall back to what the app already tracks (`ongoing`/`endDate`) instead,
    or a long-finished conflict silently poisons the lifecycle agent's current_status."""
    s = c.get("status")
    if s:
        return s
    if c.get("ongoing") is True:          # an explicit ongoing flag wins over a stale endDate
        return "active"
    if c.get("ongoing") is False or c.get("endDate"):
        return "ended"
    return "active"


def date_key(d: Optional[str]) -> str:
    """Total-order key for mixed-precision ISO dates so '1871' and '1871-05-01' compare
    correctly ('1871' < '1871-05-01' lexicographically, but a bare year should mean the
    whole year — pad the unknown parts)."""
    p = (d or "").split("-")
    y = (p[0] if p and p[0] else "0000").zfill(4)
    m = (p[1] if len(p) > 1 else "00").zfill(2)
    day = (p[2] if len(p) > 2 else "00").zfill(2)
    return f"{y}-{m}-{day}"


def load_base(seed_json: Path) -> list[BaseConflict]:
    data = json.loads(Path(seed_json).read_text(encoding="utf-8"))
    out: list[BaseConflict] = []
    for c in data.get("conflicts", []):
        out.append(BaseConflict(
            id=c["id"],
            title=c.get("title", ""),
            type=c.get("type"),
            aliases=c.get("aliases", []),
            involved_countries=c.get("involvedCountries", []),
            parties=c.get("parties", []),
            tags=c.get("tags", []),
            start=_year(c.get("startDate")),
            end=_year(c.get("endDate")),
            status=_default_status(c),
            events=[{"date": e.get("date"), "title": e.get("title")} for e in c.get("events", [])],
        ))
    return out


def pending_to_base(c: Conflict) -> BaseConflict:
    """View an in-memory, not-yet-saved Conflict (created earlier in THIS scan) as a
    BaseConflict — so the Resolver/dedup can see it and a second event for the same new
    conflict attaches to it instead of spawning a duplicate new conflict."""
    return BaseConflict(
        id=c.id,
        title=c.title,
        type=c.type,
        aliases=list(c.aliases),
        involved_countries=list(c.involved_countries),
        parties=[{"countryId": p.country_id, "role": p.role} for p in c.parties],
        tags=list(c.tags),
        start=_year(c.start_date),
        end=_year(c.end_date),
        status=c.status,
        events=[{"date": e.date, "title": e.title} for e in c.events],
    )


def load_seed_dict(seed_json: Path) -> dict:
    return json.loads(Path(seed_json).read_text(encoding="utf-8"))


def write_seed_dict(seed_json: Path, data: dict) -> None:
    Path(seed_json).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_proposals(path: Path) -> list[Proposal]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("proposals", data) if isinstance(data, dict) else data
    return [Proposal.model_validate(p) for p in raw]


# ---- coverage ledger: a persistent record of what we've searched, so "we looked and found
#      nothing" is distinguishable from "search returned nothing" and from "never scanned" ----

def _coverage_status(stats: dict) -> str:
    if stats.get("items", 0) == 0:
        return "blind"    # search returned 0 results — UNKNOWN, not proven empty (source gap)
    if stats.get("candidates", 0) == 0:
        return "quiet"    # searched a real article pool, nothing extractable — genuinely quiet/covered
    return "found"        # events surfaced


def load_coverage(ledger_path: Path) -> list[dict]:
    p = Path(ledger_path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def append_coverage(ledger_path: Path, result: ScanResult, limited: int = 0) -> dict:
    """Record one scan attempt in the ledger. Returns the entry."""
    s = result.stats
    entry = {
        "scanned_at": date.today().isoformat(),
        "region": result.request.region or "(any)",
        "topic": result.request.topic,
        "period": f"{result.request.period_start}..{result.request.period_end}",
        "items": s.get("items", 0),           # articles the search returned
        "events_found": s.get("candidates", 0),
        "proposals": s.get("proposals", 0),
        "dropped": s.get("dropped", 0),        # already-known events
        "status": _coverage_status(s),
    }
    if limited:
        entry["limited_to"] = limited          # a capped scan is NOT evidence of completeness
    ledger = load_coverage(ledger_path)
    ledger.append(entry)
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def render_coverage(ledger: list[dict]) -> str:
    if not ledger:
        return "No scans logged yet — nothing has been searched.\n"
    rows = sorted(ledger, key=lambda e: (str(e.get("region")), str(e.get("period"))))
    head = f"{'REGION':<16} {'PERIOD':<22} {'SCANNED':<11} {'ITEMS':>5} {'EVENTS':>6} {'PROP':>4}  STATUS"
    lines = [head, "-" * len(head)]
    for e in rows:
        cap = f" (cap {e['limited_to']})" if e.get("limited_to") else ""
        lines.append(
            f"{str(e.get('region'))[:15]:<16} {str(e.get('period'))[:21]:<22} "
            f"{str(e.get('scanned_at', '')):<11} {e.get('items', 0):>5} {e.get('events_found', 0):>6} "
            f"{e.get('proposals', 0):>4}  {e.get('status', '')}{cap}"
        )
    lines += [
        "",
        "status: found = events surfaced | quiet = searched, nothing found (genuinely quiet/covered)",
        "        blind = search returned 0 results (UNKNOWN — a source gap, not proven empty)",
    ]
    return "\n".join(lines) + "\n"


def write_result(result: ScanResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{result.request.period_start}_{result.request.period_end}"
    pjson = output_dir / f"proposals_{stamp}.json"
    pjson.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    md = output_dir / f"review_{stamp}.md"
    md.write_text(_render_review(result), encoding="utf-8")
    return pjson, md


def _render_review(result: ScanResult) -> str:
    auto = [p for p in result.proposals if not p.needs_human]
    human = [p for p in result.proposals if p.needs_human]
    lines = [
        f"# Review — scan {result.request.period_start}–{result.request.period_end}",
        "",
        f"- {len(auto)} auto-approved · **{len(human)} need review** · {len(result.dropped)} dropped",
        "",
        "## Needs human review",
    ]
    lines += [_render_proposal(p) for p in human] or ["_(none)_"]
    lines += ["", "## Auto-approved (spot-check)"]
    lines += [_render_proposal(p) for p in auto] or ["_(none)_"]
    return "\n".join(lines) + "\n"


def _render_proposal(p: Proposal) -> str:
    where = f"→ attach to `{p.target_conflict_id}`" if p.kind == "attach" else "→ **NEW conflict**"
    q = f"  \n  ❓ {p.reconcile.open_question}" if (p.reconcile and p.reconcile.open_question) else ""
    prov = " _(provisional — too recent)_" if p.provisional else ""
    return f"- **{p.event.date} — {p.event.title}** [{p.event.kind}, sev {p.event.severity}] {where}{prov}{q}"
