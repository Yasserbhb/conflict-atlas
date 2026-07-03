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
    """Just enough of an existing conflict for the Resolver to match against."""
    id: str
    title: str
    aliases: list[str] = Field(default_factory=list)
    involved_countries: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    start: Optional[int] = None
    end: Optional[int] = None
    status: str = "active"


def _year(s) -> Optional[int]:
    if not s:
        return None
    m = re.match(r"(\d{4})", str(s))
    return int(m.group(1)) if m else None


def load_base(seed_json: Path) -> list[BaseConflict]:
    data = json.loads(Path(seed_json).read_text(encoding="utf-8"))
    out: list[BaseConflict] = []
    for c in data.get("conflicts", []):
        out.append(BaseConflict(
            id=c["id"],
            title=c.get("title", ""),
            aliases=c.get("aliases", []),
            involved_countries=c.get("involvedCountries", []),
            tags=c.get("tags", []),
            start=_year(c.get("startDate")),
            end=_year(c.get("endDate")),
            status=c.get("status", "active"),
        ))
    return out


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
