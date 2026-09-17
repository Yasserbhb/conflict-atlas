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
    append_coverage, append_coverage_failure, append_eval, write_run_summary, load_coverage, render_coverage, accept_reviewed, write_digest,
)
from .schema import ScanRequest
from . import cursor, dates
from .pipeline import scan
from . import merge

_SUBCOMMANDS = {"scan", "apply", "coverage", "serve", "auto", "eval"}


def _coverage_path(settings):
    return settings.coverage_json


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


def _run_one(settings, start: str, end: str, args) -> tuple[int, dict]:
    """Scan ONE window and apply what clears the bar. Returns (exit_code, summary)."""
    req = ScanRequest(period_start=start, period_end=end, region=args.region, topic=args.topic)
    base = load_base(settings.seed_json)
    try:
        result = scan(req, llm=get_llm(settings), search=get_search(settings),
                      base=base, settings=settings)
    except Exception as e:  # noqa: BLE001
        # Record the blind window before giving up. The ledger is the only record anyone sees,
        # and it is also what the cursor reads — a day that dies silently would look identical
        # to a day that was genuinely quiet, and would never be retried.
        append_coverage_failure(_coverage_path(settings), req, e, limited=settings.max_candidates)
        print(f"  scan failed: {type(e).__name__}: {e}")
        return 1, {"applied": 0, "held": 0, "status": "failed"}

    seed = load_seed_dict(settings.seed_json)
    before = set(merge.validate(seed))
    applied = [p for p in result.proposals if not p.needs_human and not p.provisional]
    seed, _ = merge.apply(result.proposals, seed,
                          continuation_days=settings.continuation_days,
                          duplicate_title_floor=settings.duplicate_title_floor)
    new_issues = sorted(set(merge.validate(seed)) - before)
    ok = not new_issues
    dry = getattr(args, "dry_run", False)
    if ok and applied and not dry:
        write_seed_dict(settings.seed_json, seed)

    write_digest(settings.log_dir, result, applied, ok)
    write_result(result, settings.output_dir)      # the proposal bodies, for `apply --approve`
    write_run_summary(settings.output_dir, result, applied, ok)
    held = sum(1 for p in result.proposals if p.needs_human)
    # After the apply, so the ledger records what actually LANDED, not just what was found.
    entry = append_coverage(_coverage_path(settings), result, limited=settings.max_candidates,
                            applied=0 if (not ok or dry) else len(applied), held=held)
    print(f"  {start}..{end}: {entry['status']} — added {0 if dry else len(applied)}, "
          f"held {held}, already-known {len(result.dropped)}"
          + ("  [dry run — seed.json untouched]" if dry else ""))
    if not ok:
        print("  apply skipped — would introduce incoherence (logged, seed untouched)")
        return 1, {"applied": 0, "held": held, "status": "incoherent"}
    return 0, {"applied": 0 if dry else len(applied), "held": held, "status": entry["status"]}


def _cmd_auto(args) -> int:
    """Hands-off: scan, AUTO-APPLY only the confidently-corroborated items, log the rest.

    `auto cursor` is what the daily cron runs. It asks one question: what is the oldest day we
    have not checked yet? Days already recorded in the coverage ledger are skipped; a day that
    failed or came back blind is retried; a day that can never be searched is left behind after
    a few attempts so it cannot stall everything queued behind it.
    """
    import dataclasses
    settings = load_settings()
    if args.limit:
        settings = dataclasses.replace(settings, max_candidates=args.limit)

    if args.period != "cursor":
        start, end = _parse_period(args.period)
        return _run_one(settings, start, end, args)[0]

    # --- cursor mode -------------------------------------------------------------------------
    ledger = load_coverage(_coverage_path(settings))
    start_date = cursor.parse_start(settings.pipeline_start_date)
    max_days = args.days or settings.pipeline_max_days_per_run
    todo = cursor.next_days(ledger, start_date, date.today(),
                            settle_days=settings.t_settle_days, max_days=max_days,
                            region=args.region, topic=args.topic,
                            max_attempts=settings.coverage_max_attempts)
    prog = cursor.progress(ledger, start_date, date.today(), settings.t_settle_days,
                           args.region, args.topic, settings.coverage_max_attempts)
    print(f"cursor: {prog['done']}/{prog['eligible']} days checked "
          f"({prog['start']} .. {prog['horizon']}), {prog['remaining']} remaining")
    # One slot per run goes to the NEWEST settled day, so the map is current immediately; the
    # rest drain the backlog oldest-first. That means the backlog closes at (max_days - 1) days
    # per run, and at max_days 1 there is no backlog slot at all and it never closes.
    if prog["remaining"] > max_days and max_days <= 1:
        print("  WARNING: --days 1 only ever covers the newest day, so this backlog will never "
              "close. Raise --days, or set PIPELINE_START_DATE closer to today.")
    elif prog["remaining"] > 30:
        gain = max(1, max_days - 1)
        print(f"  backlog of {prog['remaining']} days; the newest day is covered every run, and "
              f"at --days {max_days} the rest closes in ~{prog['remaining'] // gain} runs. "
              f"Backfill anything older with a range scan instead.")
    if not todo:
        print("nothing to do — every settled day has been checked")
        return 0

    rc = 0
    for d in todo:
        s, e = dates.day_period(d)
        code, _ = _run_one(settings, s, e, args)
        if code:
            # Stop the batch on the first failure so a dead provider doesn't burn the whole
            # day's quota. The day stays unrecorded-as-done, so the next run picks it up.
            rc = code
            break
    return rc



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
    # A compact row per run, small enough to commit and bundle so the site can show whether
    # the pipeline is actually any good — not just that it ran.
    hist_path = settings.output_dir / "eval_history.json"
    hist = append_eval(hist_path, f"{start}..{end}", m, settings.llm_model, prompt_version())
    print(f"\nreport  → {out}")
    print(f"history → {hist_path} ({hist['ran_at']})")
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
    seed, report = merge.apply(proposals, seed, include_provisional=args.include_provisional,
                               continuation_days=settings.continuation_days,
                               duplicate_title_floor=settings.duplicate_title_floor)
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
    au.add_argument("period", help='"cursor" (daily; the oldest unchecked day) | "week" | "1990..2003" | "YYYY-YYYY"')
    au.add_argument("--region")
    au.add_argument("--topic")
    au.add_argument("--limit", type=int, default=0)
    au.add_argument("--days", type=int, default=0,
                    help="cursor mode: how many unchecked days to process this run")
    au.add_argument("--dry-run", action="store_true",
                    help="scan, log and record coverage, but never write seed.json")
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
