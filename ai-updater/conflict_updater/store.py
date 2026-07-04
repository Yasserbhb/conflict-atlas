"""Read the app's seed.json into a lightweight index for dedup, and write the
pipeline's output (proposals + a human-readable review queue)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from .schema import ScanResult, Proposal


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
    if c.get("ongoing") is False or c.get("endDate"):
        return "ended"
    return "active"


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


def load_seed_dict(seed_json: Path) -> dict:
    return json.loads(Path(seed_json).read_text(encoding="utf-8"))


def write_seed_dict(seed_json: Path, data: dict) -> None:
    Path(seed_json).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_proposals(path: Path) -> list[Proposal]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("proposals", data) if isinstance(data, dict) else data
    return [Proposal.model_validate(p) for p in raw]


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
