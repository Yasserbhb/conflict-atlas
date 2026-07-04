"""CLI. Two subcommands:

  scan   — find events in a period and emit proposals + a review queue
  apply  — fold approved proposals from a scan back into seed.json, coherently

    python -m conflict_updater "1990..2003" --region Africa      # bare == scan
    python -m conflict_updater scan week
    python -m conflict_updater apply out/proposals_2026-06-01_2026-06-30.json

Period accepts "start..end" (any ISO precision), "YYYY-YYYY", or "week".
The weekly cron just calls `scan week`.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta

from .config import load_settings
from .llm import get_llm
from .search import get_search
from .store import load_base, write_result, load_seed_dict, write_seed_dict, load_proposals
from .schema import ScanRequest
from .pipeline import scan
from . import merge

_SUBCOMMANDS = {"scan", "apply"}


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
    print(f"scan {start}..{end}: {result.stats}")
    print(f"proposals → {pjson}")
    print(f"review    → {md}")
    return 0


def _cmd_apply(args) -> int:
    settings = load_settings()
    seed_path = settings.seed_json
    proposals = load_proposals(args.proposals)
    seed = load_seed_dict(seed_path)
    seed, report = merge.apply(proposals, seed, include_provisional=args.include_provisional)
    issues = merge.validate(seed)

    for line in report:
        print(line)
    if issues:
        print("\nCOHERENCE ISSUES — not written:")
        for i in issues:
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
    a.add_argument("--include-provisional", action="store_true",
                   help="also apply events held by the recency gate")
    a.add_argument("--dry-run", action="store_true", help="report only; do not write seed.json")
    a.set_defaults(func=_cmd_apply)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
