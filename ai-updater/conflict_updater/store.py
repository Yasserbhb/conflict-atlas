"""Read the app's seed.json into a lightweight index for dedup, and write the
pipeline's output (proposals + a human-readable review queue)."""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from .schema import ScanResult, Proposal, Conflict
# Ordering semantics live in dates.py; re-exported here because merge.py and
# pipeline.py import date_key from store.
from .dates import key as date_key  # noqa: F401


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


def default_status(c: dict) -> str:
    """Most conflicts predate the `status` field and have it missing (not null) — don't just
    assume 'active'. Fall back to what the app already tracks (`ongoing`/`endDate`) instead,
    or a long-finished conflict silently poisons the enricher's current_status context."""
    s = c.get("status")
    if s:
        return s
    if c.get("ongoing") is True:          # an explicit ongoing flag wins over a stale endDate
        return "active"
    if c.get("ongoing") is False or c.get("endDate"):
        return "ended"
    return "active"



def derive_span(event_dates, status, stated_start=None, stated_end=None):
    """A conflict's (startDate, endDate), derived in ONE place from its events plus any span the
    sources stated. start = earliest known date; end = latest known date ONLY when the conflict
    has ended (positive evidence), else None. Self-corrects as more events are attached."""
    starts = [d for d in event_dates if d]
    if stated_start:
        starts.append(stated_start)
    start = min(starts, key=date_key) if starts else stated_start
    if status in ("ended", "resolved"):
        ends = [d for d in event_dates if d]
        if stated_end:
            ends.append(stated_end)
        end = max(ends, key=date_key) if ends else stated_end
    else:
        end = None
    return start, end


def load_base(seed_json: Path) -> list[BaseConflict]:
    return base_from_seed(json.loads(Path(seed_json).read_text(encoding="utf-8")))


def base_from_seed(data: dict) -> list[BaseConflict]:
    """Same as load_base but from an already-loaded dict — lets the backtest build a base from
    a pruned copy of the seed without writing it to disk first."""
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
            status=default_status(c),
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


def accept_reviewed(proposals: list[Proposal], indices=None, approve_all: bool = False) -> int:
    """Flip needs_human=False on the chosen 'needs review' items. `indices` are 1-based and refer
    to the numbering in review_*.md (the needs-human items, in order). Returns how many were flipped."""
    human = [p for p in proposals if p.needs_human]
    if approve_all:
        for p in human:
            p.needs_human = False
        return len(human)
    n = 0
    for i in indices or []:
        if 1 <= i <= len(human):
            human[i - 1].needs_human = False
            n += 1
    return n


# ---- coverage ledger: a persistent record of what we've searched, so "we looked and found
#      nothing" is distinguishable from "search returned nothing" and from "never scanned" ----

def _run_url() -> Optional[str]:
    """Deep link to the GitHub Actions run that produced this entry, when running in CI.

    This is what turns the ledger from a summary into something you can act on: a failed row in
    the app links straight to that run's own log output, instead of leaving you to hunt for it
    in the Actions tab. Absent when run locally, and the UI simply omits the link.
    """
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def _prompt_version() -> str:
    """Imported lazily so store.py stays importable without the prompts module loaded."""
    try:
        from .prompts import prompt_version
        return prompt_version()
    except Exception:
        return "unknown"


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


def append_coverage(ledger_path: Path, result: ScanResult, limited: int = 0,
                    applied: int | None = None, held: int | None = None) -> dict:
    """Record one scan attempt in the ledger. Returns the entry.

    `applied`/`held` are the outcome of the auto-apply step and are only known by the caller,
    so they are passed in rather than read off the result. Recording them here keeps the
    ledger a complete run log — one file that answers "did it run, what did it find, and what
    actually landed" — instead of needing a second history file alongside it.
    """
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
        "prompt_version": _prompt_version(),
        "run_url": _run_url(),
    }
    # The FULL stats dict, not just the four fields above. Those four were chosen for a weekly
    # table; under a daily cursor the ledger is the only durable per-run record (latest_run.json
    # is overwritten every run, and the digest footer is markdown nobody can chart). Keeping the
    # whole dict here is what lets the site show cost and triage over time instead of one day at
    # a time — notably `queries`, which is the billed-search count, and `triaged_out`.
    entry["stats"] = dict(s)

    if limited:
        entry["limited_to"] = limited          # a capped scan is NOT evidence of completeness
    if s.get("failed"):
        entry["failed"] = s["failed"]          # partial scan — some candidates raised
    if applied is not None:
        entry["applied"] = applied             # auto-approved and written to seed.json
    if held is not None:
        entry["held"] = held                   # routed to human review, still waiting
    ledger = load_coverage(ledger_path)
    ledger.append(entry)
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def append_coverage_failure(ledger_path: Path, req, error: Exception, limited: int = 0) -> dict:
    """Record a scan that raised before it could produce a result.

    Without this the ledger is blind to exactly the gap it exists to expose: a crashed scan
    used to write nothing at all, so nine consecutive dead weeks left the public coverage
    table showing stale rows as though everything were fine. A failed scan is the truest
    possible "blind" — we know nothing about the window, and now we say so.
    """
    entry = {
        "scanned_at": date.today().isoformat(),
        "region": req.region or "(any)",
        "topic": req.topic,
        "period": f"{req.period_start}..{req.period_end}",
        "items": 0,
        "events_found": 0,
        "proposals": 0,
        "dropped": 0,
        "status": "failed",
        "error": f"{type(error).__name__}: {error}"[:300],
        "prompt_version": _prompt_version(),
        "run_url": _run_url(),
    }
    if limited:
        entry["limited_to"] = limited
    ledger = load_coverage(ledger_path)
    ledger.append(entry)
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def append_eval(history_path: Path, period: str, metrics: dict, model: str,
                prompt_version: str) -> dict:
    """Append one backtest to the eval history.

    Deliberately a few hundred bytes per run — headline numbers only, no per-event detail —
    because this file is committed and bundled into the app so quality can be shown on the
    site. The full report (including which curated events were missed) stays in out/ and is
    archived as a run artifact.
    """
    entry = {
        "ran_at": date.today().isoformat(),
        "period": period,
        "model": model,
        "prompt_version": prompt_version,
        "run_url": _run_url(),
        "gold": metrics.get("gold"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "f1": metrics.get("f1"),
        "resolution_accuracy": metrics.get("resolution_accuracy"),
        "kind_accuracy": metrics.get("kind_accuracy"),
        "severity_within_1": metrics.get("severity_within_1"),
        "calibration": metrics.get("calibration", []),
    }
    p = Path(history_path)
    try:
        history = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []
    history.append(entry)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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


def write_digest(log_dir: Path, result: ScanResult, applied: list, ok: bool) -> Path:
    """A plain-English weekly findings log — what got ADDED to the atlas, what was HELD (too
    uncertain to auto-add), what was already known. This is the thing you read; nothing to do."""
    r = result.request
    human = [p for p in result.proposals if p.needs_human]
    L = [f"# Findings — {r.period_start} .. {r.period_end}"]
    if r.region:
        L.append(f"_region: {r.region}_")
    L += ["", f"## ✅ Added to the atlas ({len(applied)})"]
    L += [f"- **{p.event.date}** {p.event.title} → `{p.target_conflict_id or 'NEW conflict'}` "
          f"[{p.event.kind}, sev {p.event.severity}]" for p in applied] or ["_(none this period)_"]
    L += ["", f"## ⏸ Held — found but too uncertain to auto-add ({len(human)})"]
    L += [f"- {p.event.date} {p.event.title}"
          + (f" — ❔ {p.verify.open_question}" if (p.verify and p.verify.open_question) else "")
          for p in human] or ["_(none)_"]
    if result.dropped:
        L += ["", f"## ↩ Already in the atlas, skipped ({len(result.dropped)})"]
        L += [f"- {d}" for d in result.dropped]
    L += ["", f"_scan: {result.stats}_"]
    if not ok:
        L += ["", "> ⚠ nothing written — applying would have introduced an incoherence; skipped."]
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{r.period_start}_{r.period_end}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def write_run_summary(out_dir: Path, result: ScanResult, applied: list, ok: bool,
                      run_id: str | None = None) -> Path:
    """The current run's findings as structured JSON, for the app to render natively.

    ACCUMULATES across the days of one run. The cursor scans several days per run and calls this
    once per day; with a fixed filename and a plain overwrite, day three silently erased days one
    and two, so the site showed a third of what the run found — three held events from a
    backfilled June day were invisible while the page looked complete. The name made sense when a
    run WAS one period; under a day cursor it quietly came to mean "last day of the last run".

    Days of one run are identified by `run_id` — the CI run URL, stable across the whole job. A
    new run id starts a fresh file, so this never grows without bound.

    The markdown digests in log/ remain the per-day archival record; this is the same content
    shaped for the page, and only the current run is kept.
    """
    r = result.request
    human = [p for p in result.proposals if p.needs_human]
    day = f"{r.period_start}..{r.period_end}"
    run_id = run_id or _run_url() or f"local-{date.today().isoformat()}"

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "latest_run.json"
    prev: dict = {}
    if path.exists():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            prev = {}                       # a corrupt file must not stop the scan
    if prev.get("run_id") != run_id:        # a different run — start over
        prev = {}

    days = sorted(set(list(prev.get("days") or []) + [day]))

    # Idempotent per day: re-writing a day replaces its entries rather than doubling them, so a
    # retry inside one run cannot make the page show an event twice.
    def _other_days(key):
        return [e for e in (prev.get(key) or []) if e.get("day") != day]

    stats = dict(prev.get("stats") or {})
    for k, v in (result.stats or {}).items():
        if isinstance(v, (int, float)):
            stats[k] = stats.get(k, 0) + v

    summary = {
        "run_id": run_id,
        # The SPAN the run covered. A cursor run mixes backfill with the newest settled day, so
        # this is deliberately not contiguous — `days` is the precise list.
        "period": f"{days[0].split('..')[0]}..{days[-1].split('..')[-1]}",
        "days": days,
        "region": r.region,
        "ran_at": date.today().isoformat(),
        "ok": bool(prev.get("ok", True)) and ok,
        "run_url": _run_url(),
        "stats": stats,
        "added": _other_days("added") + [
            {
                "day": day,
                "date": p.event.date,
                "title": p.event.title,
                "conflict": p.target_conflict_id or "new conflict",
                "kind": p.event.kind,
                "severity": p.event.severity,
                "sources": [s.url for s in p.event.sources][:4],
            }
            for p in applied
        ],
        "held": _other_days("held") + [
            {
                "day": day,
                "date": p.event.date,
                "title": p.event.title,
                # why it was held — the single most useful line in the whole digest
                "question": (p.verify.open_question if p.verify else None),
                "confidence": (p.verify.confidence if p.verify else None),
                # The held events are the ones a human actually has to adjudicate, and they were
                # the only ones shipped WITHOUT their sources — so the page could say "we are
                # unsure about this" and give you no way to check it.
                "sources": [s.url for s in p.event.sources][:4],
            }
            for p in human
        ],
        "already_known": (list(prev.get("already_known") or []) + list(result.dropped))[:60],
        "errored": (list(prev.get("errored") or []) + list(result.failed))[:20],
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_result(result: ScanResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{result.request.period_start}_{result.request.period_end}"
    pjson = output_dir / f"proposals_{stamp}.json"
    pjson.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    md = output_dir / f"review_{stamp}.md"
    md.write_text(_render_review(result, pjson.name), encoding="utf-8")
    return pjson, md


def _render_review(result: ScanResult, proposals_file: str = "proposals.json") -> str:
    auto = [p for p in result.proposals if not p.needs_human]
    human = [p for p in result.proposals if p.needs_human]
    lines = [
        f"# Review — scan {result.request.period_start}–{result.request.period_end}",
        "",
        f"- {len(auto)} auto-approved · **{len(human)} need review** · {len(result.dropped)} dropped",
        "",
        "## Needs human review",
    ]
    lines += [_render_proposal(p, i) for i, p in enumerate(human, 1)] or ["_(none)_"]
    if human:
        nums = " ".join(str(i) for i in range(1, len(human) + 1))
        lines += [
            "",
            "→ accept the ones you agree with, then apply. e.g. accept #1 and #3:",
            f"  `python -m conflict_updater apply {proposals_file} --approve 1 3`",
            f"  (or `--approve {nums}` for all of them, or `--approve-all`).",
        ]
    lines += ["", "## Auto-approved (spot-check)"]
    lines += [_render_proposal(p) for p in auto] or ["_(none)_"]
    return "\n".join(lines) + "\n"


def _render_proposal(p: Proposal, num: int | None = None) -> str:
    tag = f"**[{num}]** " if num else ""
    where = f"→ attach to `{p.target_conflict_id}`" if p.kind == "attach" else "→ **NEW conflict**"
    q = f"  \n  ❓ {p.verify.open_question}" if (p.verify and p.verify.open_question) else ""
    prov = " _(provisional — too recent)_" if p.provisional else ""
    return f"- {tag}**{p.event.date} — {p.event.title}** [{p.event.kind}, sev {p.event.severity}] {where}{prov}{q}"
