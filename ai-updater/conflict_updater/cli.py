"""CLI. Subcommands:

  scan      — find events in a period and emit proposals + a review queue
  apply     — fold approved proposals from a scan back into seed.json, coherently
  coverage  — show what regions/periods have already been scanned (and how they came back)

    python -m conflict_updater "1990..2003" --region Africa      # bare == scan
    python -m conflict_updater scan week
    python -m conflict_updater apply out/proposals_2026-06-01_2026-06-30.json
    python -m conflict_updater coverage --region Algeria

Period accepts "start..end" (any ISO precision), "YYYY-YYYY", or "week".
The weekly cron just calls `scan week`. Every scan appends to a coverage ledger so
"searched and empty" is never confused with "never searched".
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta

from .config import load_settings
from .llm import get_llm
from .search import get_search
from .store import (
    load_base, base_from_seed, write_result, load_seed_dict, write_seed_dict, load_proposals,
    append_coverage, append_coverage_failure, load_coverage, render_coverage, accept_reviewed, write_digest,
)
from .schema import ScanRequest
from .pipeline import scan
from . import merge

_SUBCOMMANDS = {"scan", "apply", "coverage", "serve", "auto", "eval"}


def _coverage_path(settings):
    return settings.output_dir / "coverage.json"


def _parse_period(text: str) -> tuple[str, str]:
    if text == "week":
        today = date.today()
        return (str(today - timedelta(days=7)), str(today))
    if ".." in text:
        a, b = text.split("..", 1)
        return a.strip(), b.strip()
    if re.fullmatch(r"\d{4}-\d{4}", text):
        a, b = text.split("-")
        return a, b
    raise SystemExit(f"bad period {text!r}; use 'start..end', 'YYYY-YYYY', or 'week'")


def _cmd_scan(args) -> int:
    import dataclasses
    start, end = _parse_period(args.period)
    settings = load_settings()
    if args.limit:
        settings = dataclasses.replace(settings, max_candidates=args.limit)
    req = ScanRequest(period_start=start, period_end=end, region=args.region, topic=args.topic)
    base = load_base(settings.seed_json)
    result = scan(req, llm=get_llm(settings), search=get_search(settings), base=base, settings=settings)
    pjson, md = write_result(result, settings.output_dir)
    entry = append_coverage(_coverage_path(settings), result, limited=settings.max_candidates)
    print(f"scan {start}..{end}: {result.stats}")
    print(f"proposals → {pjson}")
    print(f"review    → {md}")
    print(f"coverage  → {_coverage_path(settings)} [{entry['status']}]")
    return 0


def _cmd_coverage(args) -> int:
    settings = load_settings()
    ledger = load_coverage(_coverage_path(settings))
    if args.region:
        ledger = [e for e in ledger if (e.get("region") or "").lower() == args.region.lower()]
    print(render_coverage(ledger))
    return 0


def _cmd_serve(args) -> int:
    from .server import serve
    serve(host=args.host, port=args.port)
    return 0


def _cmd_auto(args) -> int:
    """Hands-off: scan, AUTO-APPLY only the confidently-corroborated items, log the rest.
    This is what the weekly cron runs — no human in the loop, everything reversible via git."""
    import dataclasses
    start, end = _parse_period(args.period)
    settings = load_settings()
    if args.limit:
        settings = dataclasses.replace(settings, max_candidates=args.limit)
    req = ScanRequest(period_start=start, period_end=end, region=args.region, topic=args.topic)
    base = load_base(settings.seed_json)
    try:
        result = scan(req, llm=get_llm(settings), search=get_search(settings), base=base, settings=settings)
    except Exception as e:  # noqa: BLE001
        # Log the blind window before re-raising. The ledger is the only record anyone sees;
        # a scan that dies silently is indistinguishable on the public site from a week that
        # was genuinely quiet.
        append_coverage_failure(_coverage_path(settings), req, e, limited=settings.max_candidates)
        print(f"scan failed: {type(e).__name__}: {e}")
        print("logged as a blind window in the coverage ledger; seed.json untouched")
        return 1
    append_coverage(_coverage_path(settings), result, limited=settings.max_candidates)

    # apply ONLY the auto-approved (needs_human=False, non-provisional) — the strict gate already
    # filtered these; everything uncertain is logged and held, never auto-added.
    seed = load_seed_dict(settings.seed_json)
    before = set(merge.validate(seed))
    applied = [p for p in result.proposals if not p.needs_human and not p.provisional]
    seed, _ = merge.apply(result.proposals, seed)
    new_issues = sorted(set(merge.validate(seed)) - before)
    ok = not new_issues
    if ok and applied:
        write_seed_dict(settings.seed_json, seed)

    digest = write_digest(settings.log_dir, result, applied, ok)
    held = sum(1 for p in result.proposals if p.needs_human)
    print(f"auto {start}..{end}: added {len(applied)}, held {held}, already-known {len(result.dropped)}")
    print(f"digest → {digest}")
    if not ok:
        print("apply skipped — would introduce incoherence (logged, seed untouched)")
        return 1
    return 0


def _cmd_eval(args) -> int:
    """Backtest a window against the atlas's own curated events.

    Removes the window's events from the base the pipeline reads, scans it, and scores what
    comes back. Nothing is written to seed.json — this only measures.
    """
    import dataclasses, json
    from .evaluate import prune, score, render
    from .prompts import prompt_version

    start, end = _parse_period(args.period)
    settings = load_settings()
    if args.limit:
        settings = dataclasses.replace(settings, max_candidates=args.limit)
    # Caching on by default here: a backtest is replayed constantly while tuning prompts, and
    # re-paying for every call makes measurement too expensive to repeat.
    if not args.no_cache:
        settings = dataclasses.replace(settings, llm_cache="on")

    seed = load_seed_dict(settings.seed_json)
    pruned, gold = prune(seed, start, end)
    removed = len(seed.get("conflicts", [])) - len(pruned.get("conflicts", []))
    print(f"held out {len(gold)} event(s) in {start}..{end}; "
          f"{removed} conflict(s) removed entirely, {len(pruned['conflicts'])} left in the base")
    if not gold:
        print("no curated events in that window — pick another period")
        return 1

    req = ScanRequest(period_start=start, period_end=end, region=args.region, topic=args.topic)
    result = scan(req, llm=get_llm(settings), search=get_search(settings),
                  base=base_from_seed(pruned), settings=settings)

    m = score(result, gold)
    print()
    print(render(f"{start}..{end}", m))

    # Persist the run so two prompt versions can be compared later. The misses are the most
    # useful part of the report — they name exactly which curated events the pipeline failed
    # to rediscover, which is where prompt work should start.
    from .evaluate import same_event
    matched_gold = {id(g) for g in gold
                    if any(same_event(g, p.event) for p in result.proposals)}
    payload = {
        "period": f"{start}..{end}",
        "prompt_version": prompt_version(),
        "model": settings.llm_model,
        "metrics": m,
        "missed": [
            {"date": g.date, "title": g.title, "conflict": g.conflict_title,
             "expected": g.expected_decision}
            for g in gold if id(g) not in matched_gold
        ],
    }
    out = settings.output_dir / f"eval_{start}_{end}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nreport → {out}")
    return 0


def _cmd_apply(args) -> int:
    settings = load_settings()
    seed_path = settings.seed_json
    proposals = load_proposals(args.proposals)

    # accept reviewed items without hand-editing JSON: --approve N M refers to the numbered
    # "needs human review" items in review_*.md; --approve-all accepts every one of them.
    accepted = accept_reviewed(proposals, args.approve, args.approve_all)
    if args.approve or args.approve_all:
        print(f"accepted {accepted} reviewed item(s)")

    seed = load_seed_dict(seed_path)
    before = set(merge.validate(seed))   # pre-existing issues we didn't cause
    seed, report = merge.apply(proposals, seed, include_provisional=args.include_provisional)
    new_issues = sorted(set(merge.validate(seed)) - before)   # block only on issues WE introduced

    for line in report:
        print(line)
    if before:
        print(f"\nnote: {len(before)} pre-existing coherence issue(s) in seed.json, unchanged by this apply")
    if new_issues:
        print("\nCOHERENCE ISSUES introduced by this apply — not written:")
        for i in new_issues:
            print(f"  ✗ {i}")
        return 1
    if args.dry_run:
        print("\n(dry run — seed.json not written)")
        return 0
    write_seed_dict(seed_path, seed)
    print(f"\nwrote {seed_path} (version {seed.get('version')})")
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows console defaults to cp1252; our output has → … ✗
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in _SUBCOMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "scan")  # bare period → scan

    ap = argparse.ArgumentParser(prog="conflict_updater")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="find events in a period, emit proposals")
    s.add_argument("period", help='"1990..2003" | "2026-06-01..2026-06-30" | "YYYY-YYYY" | "week"')
    s.add_argument("--region")
    s.add_argument("--topic")
    s.add_argument("--limit", type=int, default=0, help="cap candidates processed (free-tier quota)")
    s.set_defaults(func=_cmd_scan)

    a = sub.add_parser("apply", help="fold approved proposals into seed.json")
    a.add_argument("proposals", help="path to a proposals_*.json from a scan")
    a.add_argument("--approve", type=int, nargs="*", metavar="N",
                   help="accept these numbered 'needs review' items from review_*.md")
    a.add_argument("--approve-all", action="store_true", help="accept every needs-review item")
    a.add_argument("--include-provisional", action="store_true",
                   help="also apply events held by the recency gate")
    a.add_argument("--dry-run", action="store_true", help="report only; do not write seed.json")
    a.set_defaults(func=_cmd_apply)

    c = sub.add_parser("coverage", help="show what regions/periods have been scanned")
    c.add_argument("--region", help="filter to one region")
    c.set_defaults(func=_cmd_coverage)

    v = sub.add_parser("serve", help="launch the browser control panel")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8000)
    v.set_defaults(func=_cmd_serve)

    au = sub.add_parser("auto", help="hands-off: scan, auto-apply confident items, log the rest")
    au.add_argument("period", help='"week" | "1990..2003" | "YYYY-YYYY"')
    au.add_argument("--region")
    au.add_argument("--topic")
    au.add_argument("--limit", type=int, default=0)
    au.set_defaults(func=_cmd_auto)

    ev = sub.add_parser("eval", help="backtest a window against the atlas's own curated events")
    ev.add_argument("period", help='"1962..1968" | "2024-01-01..2024-12-31" | "YYYY-YYYY"')
    ev.add_argument("--region")
    ev.add_argument("--topic")
    ev.add_argument("--limit", type=int, default=0, help="cap candidates processed (free-tier quota)")
    ev.add_argument("--no-cache", action="store_true", help="bypass the LLM response cache")
    ev.set_defaults(func=_cmd_eval)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
