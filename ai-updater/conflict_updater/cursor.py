"""Which day to look at next.

The whole daily design is one question asked once per day: **have we already checked this day?**
If yes, skip it. If no, and it is old enough to have settled, scan it.

Everything here is a pure function over the coverage ledger — no clock reads, no I/O, no argparse —
so the scheduling logic is fully testable offline without an API key. The caller supplies `today`.

Two properties this has to guarantee, because they are the "don't forget" and "don't stall" halves
of the same problem:

  * **A day that failed is retried.** "Done" means a row exists that actually reached a conclusion
    (`found` or `quiet`). A `failed` row — or a `blind` one, where search returned nothing and we
    therefore know nothing — does not count, so the next run picks the day up again.
  * **A day that can never succeed does not block the queue forever.** After `max_attempts` tries
    the day is treated as done regardless of outcome. Without this, one permanently un-searchable
    date stalls the cursor and no later day is ever reached.

Days are always returned oldest-first. That is load-bearing rather than tidy: status may only move
on the chronologically latest event, so a backfilled March must not be applied after a September
that already closed the war.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from .dates import as_day, day_period, days_between

# A ledger row records region as "(any)" when the scan was unscoped — see store.append_coverage.
ANY_REGION = "(any)"

# Ledger statuses that mean we actually learned something about the day.
# `blind` (search returned zero results) and `failed` (the scan errored) both mean "unknown",
# so neither settles the day.
CONCLUSIVE = {"found", "quiet"}


def _norm_region(region: Optional[str]) -> str:
    return (region or ANY_REGION).strip() or ANY_REGION


def _matches(row: dict, period: tuple[str, str], region: Optional[str], topic: Optional[str]) -> bool:
    """Does this ledger row describe the same scan we are about to run?

    Region and topic are part of the identity: a `--region Algeria` scan of a day tells us nothing
    about the rest of the world that day, so it must not mark the day globally done. This is also
    why the existing historical rows (`1870..1900`, region `Algeria`) are invisible to the cursor
    without any migration — they match neither the period shape nor the scope.
    """
    return (
        row.get("period") == f"{period[0]}..{period[1]}"
        and _norm_region(row.get("region")) == _norm_region(region)
        and (row.get("topic") or None) == (topic or None)
    )


def attempts(ledger: list[dict], period: tuple[str, str],
             region: Optional[str] = None, topic: Optional[str] = None) -> int:
    """How many times this exact scan has been recorded, whatever the outcome."""
    return sum(1 for row in ledger if _matches(row, period, region, topic))


def is_done(ledger: list[dict], period: tuple[str, str], region: Optional[str] = None,
            topic: Optional[str] = None, max_attempts: int = 3) -> bool:
    """True when this day should be skipped: either it reached a conclusion, or we have tried
    enough times that retrying it again would just stall everything behind it."""
    tried = 0
    for row in ledger:
        if not _matches(row, period, region, topic):
            continue
        tried += 1
        if row.get("status") in CONCLUSIVE:
            return True
    return tried >= max_attempts


def latest_eligible(today: date, settle_days: int) -> date:
    """The newest day we are allowed to scan.

    Scanning a day that is already `settle_days` old is what makes the daily pipeline able to write
    at all. The recency gate marks anything newer than that provisional, and provisional proposals
    are excluded from the applied set — so a job that scans *today* every day would run forever and
    never add a single event. The lag also means claims have had time to be corroborated or
    retracted before they are recorded, which suits a historical atlas rather than a news ticker.
    """
    return today - timedelta(days=max(0, settle_days))


def next_days(ledger: list[dict], start: date, today: date, settle_days: int = 7,
              max_days: int = 1, region: Optional[str] = None, topic: Optional[str] = None,
              max_attempts: int = 3, keep_current: bool = True) -> list[date]:
    """The next days to scan: oldest first, never newer than the settle horizon, capped at
    `max_days`. Returns [] when everything eligible has been checked.

    `keep_current` reserves ONE of those slots for the NEWEST eligible day, spending the rest on
    the oldest unchecked ones. Without it a strictly oldest-first cursor starves the present: a
    hundred-day backlog means a hundred days before the atlas shows anything from this month,
    which is the opposite of what a daily job is for. With it, the most recent settled day is
    always covered and history fills in behind it.

    This is safe to do only because chronology is enforced where the data is written, not by the
    order days happen to be scanned in: `merge.apply` recomputes `is_latest` from the conflict's
    own events, so a backfilled June event arriving after September already landed cannot move
    the status backwards. The span self-corrects the same way.
    """
    horizon = latest_eligible(today, settle_days)
    if start > horizon or max_days <= 0:
        return []
    pending = [d for d in days_between(start, horizon)
               if not is_done(ledger, day_period(d), region, topic, max_attempts)]
    if not keep_current or max_days < 2 or len(pending) <= max_days:
        return pending[:max_days]
    # oldest (max_days - 1), plus the newest. `pending` is ordered, so this stays oldest-first.
    return pending[:max_days - 1] + [pending[-1]]


def progress(ledger: list[dict], start: date, today: date, settle_days: int = 7,
             region: Optional[str] = None, topic: Optional[str] = None,
             max_attempts: int = 3) -> dict:
    """How far through the backlog we are — for the run summary and the Pipeline page."""
    horizon = latest_eligible(today, settle_days)
    if start > horizon:
        return {"eligible": 0, "done": 0, "remaining": 0,
                "start": start.isoformat(), "horizon": horizon.isoformat()}
    eligible = done = 0
    for d in days_between(start, horizon):
        eligible += 1
        if is_done(ledger, day_period(d), region, topic, max_attempts):
            done += 1
    return {
        "eligible": eligible,
        "done": done,
        "remaining": eligible - done,
        "start": start.isoformat(),
        "horizon": horizon.isoformat(),
    }


def parse_start(value, default: str = "2026-01-01") -> date:
    """`PIPELINE_START_DATE` as a real date. Falls back to the default rather than raising, so a
    typo in the environment degrades to a sane window instead of killing the scheduled run."""
    return as_day(value) or as_day(default) or date(2026, 1, 1)
