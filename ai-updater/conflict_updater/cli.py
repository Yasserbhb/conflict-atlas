"""CLI: `python -m conflict_updater "1990..2003" --region Africa`.

Period accepts "start..end" (any ISO precision) or "YYYY-YYYY".
The weekly cron just calls this with the last 7 days.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta

from .config import load_settings
from .llm import get_llm
from .search import get_search
from .store import load_base, write_result
from .schema import ScanRequest
from .pipeline import scan


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="conflict_updater")
    ap.add_argument("period", help='"1990..2003" | "2026-06-01..2026-06-30" | "YYYY-YYYY" | "week"')
    ap.add_argument("--region")
    ap.add_argument("--topic")
    args = ap.parse_args(argv)

    start, end = _parse_period(args.period)
    settings = load_settings()
    req = ScanRequest(period_start=start, period_end=end, region=args.region, topic=args.topic)

    base = load_base(settings.seed_json)
    result = scan(req, llm=get_llm(settings), search=get_search(settings), base=base, settings=settings)
    pjson, md = write_result(result, settings.output_dir)

    print(f"scan {start}..{end}: {result.stats}")
    print(f"proposals → {pjson}")
    print(f"review    → {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
