"""One place that knows what a date means.

The pipeline handles mixed-precision ISO dates — "1965", "1965-06", "1965-06-02" — and it used to
answer "what does this date mean" in four different modules with three different semantics:

  * ordering said a bare year sorts BEFORE January 1 of that year (zero-padding),
  * containment said a bare year spans the whole year,
  * recency said a bare year is not a real date at all.

That is survivable when a scan covers a decade. It is not survivable when the unit of work is a
single day, because every one of those questions is asked about the same date within one run.

So: **ordering and containment are different questions and both are right.** `key()` answers "which
came first" and deliberately keeps the zero-padding that `merge.apply` and `derive_span` rely on.
`span()` answers "what range could this mean" and is what containment must use. Having them in one
module with that stated makes the difference a choice instead of an inconsistency.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Iterator, Optional

_YEAR = re.compile(r"(\d{4})")
# A full ISO calendar date. Deliberately stricter than merge.validate's shape check: the cursor
# does real date arithmetic and must refuse anything it cannot actually construct.
_ISO_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def year(d) -> Optional[int]:
    """Leading 4-digit year, or None. Replaces four near-identical private copies that disagreed
    about whether to return a str or an int."""
    m = _YEAR.match(str(d or ""))
    return int(m.group(1)) if m else None


def key(d: Optional[str]) -> str:
    """Total-order sort key for mixed-precision dates.

    Missing parts are zero-padded, so "1871" < "1871-05-01". That makes a bare year sort to the
    START of its year, which is what you want for ordering and NOT what you want for containment —
    use span() for that. Callers that need ordering (merge.apply's latest-event check,
    derive_span's min/max) depend on exactly this behaviour.
    """
    p = (d or "").split("-")
    y = (p[0] if p and p[0] else "0000").zfill(4)
    m = (p[1] if len(p) > 1 else "00").zfill(2)
    day = (p[2] if len(p) > 2 else "00").zfill(2)
    return f"{y}-{m}-{day}"


def span(d) -> tuple[str, str]:
    """The [earliest, latest] a mixed-precision date could mean.

    "1965" -> ("1965-01-01", "1965-12-31"); "1965-06" -> ("1965-06-01", "1965-06-31");
    a full date -> itself twice. Unparseable -> a range that overlaps nothing.

    The month upper bound is "-31" even for short months: it is a string comparison bound, never
    a real date, and no real day sorts above it within that month.
    """
    parts = [x for x in str(d or "").split("-") if x != ""]
    if not parts or not _YEAR.fullmatch(parts[0] or ""):
        return ("9999-99-99", "0000-00-00")
    y = parts[0].zfill(4)
    if len(parts) == 1:
        return (f"{y}-01-01", f"{y}-12-31")
    m = parts[1].zfill(2)
    if len(parts) == 2:
        return (f"{y}-{m}-01", f"{y}-{m}-31")
    return (f"{y}-{m}-{parts[2].zfill(2)}",) * 2


def in_window(d, start, end) -> bool:
    """True when `d` could fall inside [start, end], at whatever precision each side gives.

    This is the containment question, and it is why span() exists: keyed comparison would put a
    bare "1965" outside its own year.
    """
    lo, hi = span(d)
    wlo, _ = span(start)
    _, whi = span(end)
    return lo <= whi and wlo <= hi


def as_day(d) -> Optional[date]:
    """A real `date` for a full YYYY-MM-DD, else None.

    Strict on purpose. The day cursor steps through the calendar and records which days are done;
    a value it cannot construct must not be silently coerced into one that sorts plausibly.
    """
    m = _ISO_DAY.match(str(d or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None          # e.g. 2026-02-31


def day_period(d: date) -> tuple[str, str]:
    """The (start, end) a single-day scan uses. Both ends are that day, so the window is the day
    itself rather than a 2-day range with an overlapping boundary."""
    iso = d.isoformat()
    return (iso, iso)


def days_between(start: date, end: date) -> Iterator[date]:
    """Every day from `start` to `end` inclusive, oldest first.

    Oldest-first is load-bearing, not a convention: status may only move on the chronologically
    latest event, so backfilling March after September must not reopen a war that has ended.
    """
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


# ---- how wide a scan window should be, by era -----------------------------------------------
# Day-by-day is right for this year and wrong for 1823. Two reasons, both about sources rather
# than taste:
#
#   * A query for a specific day in 1823 does not return that day's reporting — there isn't any
#     online. It returns retrospective encyclopedia pages, which describe a period. Asking for a
#     decade asks the question the sources can actually answer.
#   * Event density collapses with age. The atlas holds 489 events across five centuries; walking
#     the 1700s a day at a time is ~36,500 scans to find a handful of events, at two Tavily
#     credits per query.
#
# So the window widens with age. Boundaries are derived from the window's own start date, so they
# are deterministic and the coverage ledger's "start..end" keys stay stable between runs.
# Changing this table re-cuts those windows and previously-scanned periods stop matching — which
# is recoverable (they simply get rescanned) but not free.
_ERAS = [
    (2000, 1),        # this century: one day
    (1950, 7),        # a week
    (1900, 30),       # a month
    (1800, 91),       # a quarter
    (1500, 365),      # a year
]
_DEEP = 3652         # before 1500: a decade


def window_days(year: int) -> int:
    """How many days one scan should cover, for a window starting in `year`."""
    for floor, n in _ERAS:
        if year >= floor:
            return n
    return _DEEP


def windows_between(start: date, horizon: date):
    """Successive scan windows from `start` up to `horizon`, each sized for its own era.

    Yields (first_day, last_day) inclusive. Consecutive and non-overlapping, so every day between
    the two ends is covered exactly once.
    """
    cur = start
    while cur <= horizon:
        end = min(cur + timedelta(days=window_days(cur.year) - 1), horizon)
        yield cur, end
        cur = end + timedelta(days=1)
