"""The day cursor: have we checked this day already?

All pure — no clock, no network, no argparse. `today` is always supplied.
"""
from datetime import date

from conflict_updater.cursor import (
    attempts, is_done, latest_eligible, next_days, parse_start, progress,
)

TODAY = date(2026, 2, 1)


def _row(day: str, status: str = "found", region=None, topic=None) -> dict:
    return {"period": f"{day}..{day}", "status": status, "region": region or "(any)", "topic": topic}


def _day(d: str):
    return (d, d)


# ---- the settle horizon --------------------------------------------------------------------
# Scanning a day that is already settle_days old is what lets the pipeline write at all: anything
# newer is marked provisional and excluded from the applied set.

def test_horizon_is_settle_days_behind_today():
    assert latest_eligible(TODAY, 7) == date(2026, 1, 25)


def test_never_offers_a_day_inside_the_settle_lag():
    days = next_days([], date(2026, 1, 20), TODAY, settle_days=7, max_days=50)
    assert max(days) == date(2026, 1, 25), "a day newer than the horizon would only ever be provisional"


def test_nothing_eligible_yet_returns_empty():
    assert next_days([], date(2026, 3, 1), TODAY, settle_days=7) == []


# ---- skip what we already checked ----------------------------------------------------------

def test_empty_ledger_starts_at_the_start_date():
    assert next_days([], date(2026, 1, 10), TODAY, settle_days=7) == [date(2026, 1, 10)]


def test_a_found_day_is_skipped():
    days = next_days([_row("2026-01-10")], date(2026, 1, 10), TODAY, settle_days=7)
    assert days == [date(2026, 1, 11)]


def test_a_quiet_day_is_also_done():
    # searched a real article pool and genuinely found nothing — that IS a conclusion
    days = next_days([_row("2026-01-10", "quiet")], date(2026, 1, 10), TODAY, settle_days=7)
    assert days == [date(2026, 1, 11)]


def test_gaps_are_filled_oldest_first():
    # Two of the three slots go to the oldest gaps; the third is the reserved newest day.
    ledger = [_row("2026-01-10"), _row("2026-01-12")]
    days = next_days(ledger, date(2026, 1, 10), TODAY, settle_days=7, max_days=3)
    assert days == [date(2026, 1, 11), date(2026, 1, 13), date(2026, 1, 25)]


def test_max_days_caps_the_batch():
    assert len(next_days([], date(2026, 1, 1), TODAY, settle_days=7, max_days=3)) == 3


# ---- don't forget --------------------------------------------------------------------------

def test_a_failed_day_is_retried():
    days = next_days([_row("2026-01-10", "failed")], date(2026, 1, 10), TODAY, settle_days=7)
    assert days == [date(2026, 1, 10)], "a crashed day must come back around"


def test_a_blind_day_is_retried():
    # blind = search returned nothing, so we know nothing about that day — not a conclusion
    days = next_days([_row("2026-01-10", "blind")], date(2026, 1, 10), TODAY, settle_days=7)
    assert days == [date(2026, 1, 10)]


# ---- don't stall ---------------------------------------------------------------------------

def test_a_permanently_blind_day_stops_blocking_after_max_attempts():
    ledger = [_row("2026-01-10", "blind") for _ in range(3)]
    days = next_days(ledger, date(2026, 1, 10), TODAY, settle_days=7, max_attempts=3)
    assert days == [date(2026, 1, 11)], "one un-searchable day must not stall every day behind it"


def test_attempts_counts_every_outcome():
    ledger = [_row("2026-01-10", "blind"), _row("2026-01-10", "failed")]
    assert attempts(ledger, _day("2026-01-10")) == 2
    assert is_done(ledger, _day("2026-01-10"), max_attempts=3) is False
    assert is_done(ledger, _day("2026-01-10"), max_attempts=2) is True


# ---- scope is part of a day's identity ------------------------------------------------------

def test_a_region_scoped_scan_does_not_mark_the_day_globally_done():
    ledger = [_row("2026-01-10", region="Algeria")]
    days = next_days(ledger, date(2026, 1, 10), TODAY, settle_days=7)
    assert days == [date(2026, 1, 10)], "scanning one region tells us nothing about the rest"


def test_existing_historical_rows_are_invisible_to_the_cursor():
    # the real ledger carries rows like this; they must need no migration
    ledger = [{"period": "1870..1900", "status": "found", "region": "Algeria", "topic": None}]
    assert next_days(ledger, date(2026, 1, 10), TODAY, settle_days=7) == [date(2026, 1, 10)]


def test_topic_is_part_of_the_identity():
    ledger = [_row("2026-01-10", topic="sanctions")]
    assert is_done(ledger, _day("2026-01-10")) is False
    assert is_done(ledger, _day("2026-01-10"), topic="sanctions") is True


# ---- progress ------------------------------------------------------------------------------

def test_progress_counts_the_backlog():
    ledger = [_row("2026-01-10"), _row("2026-01-11")]
    p = progress(ledger, date(2026, 1, 10), TODAY, settle_days=7)
    assert p["done"] == 2
    assert p["eligible"] == 16          # 2026-01-10 .. 2026-01-25 inclusive
    assert p["remaining"] == 14
    assert p["horizon"] == "2026-01-25"


def test_progress_when_nothing_is_eligible_yet():
    p = progress([], date(2026, 3, 1), TODAY, settle_days=7)
    assert p == {"eligible": 0, "done": 0, "remaining": 0,
                 "start": "2026-03-01", "horizon": "2026-01-25"}


# ---- start date ----------------------------------------------------------------------------

def test_parse_start_reads_an_iso_day():
    assert parse_start("2025-06-01") == date(2025, 6, 1)


def test_a_bad_start_date_falls_back_instead_of_killing_the_run():
    assert parse_start("not-a-date", default="2026-01-01") == date(2026, 1, 1)
    assert parse_start("2026-02-31", default="2026-01-01") == date(2026, 1, 1)
    assert parse_start(None, default="2026-01-01") == date(2026, 1, 1)


# ---- the loop actually closes ---------------------------------------------------------------
# The cursor is only useful if a scan it drives is recorded in a form the NEXT run reads back as
# "done". That round trip goes through store.append_coverage, so test it for real rather than
# against a hand-built ledger.

def _result(day: str, items=5, candidates=2):
    from conflict_updater.schema import ScanResult, ScanRequest
    return ScanResult(
        request=ScanRequest(period_start=day, period_end=day),
        stats={"items": items, "candidates": candidates, "proposals": candidates, "dropped": 0},
    )


def test_a_scanned_day_is_skipped_on_the_next_run(tmp_path):
    from conflict_updater.store import append_coverage, load_coverage
    ledger_path = tmp_path / "coverage.json"
    start, today = date(2026, 1, 10), TODAY

    first = next_days(load_coverage(ledger_path), start, today, settle_days=7)
    assert first == [date(2026, 1, 10)]

    append_coverage(ledger_path, _result("2026-01-10"), applied=1, held=0)

    second = next_days(load_coverage(ledger_path), start, today, settle_days=7)
    assert second == [date(2026, 1, 11)], "the day just scanned must not be scanned again"


def test_a_day_that_found_nothing_is_still_done(tmp_path):
    # items>0 but no candidates -> "quiet": we looked at a real article pool and there was
    # genuinely nothing. That is a conclusion, so the day must not be re-scanned forever.
    from conflict_updater.store import append_coverage, load_coverage
    ledger_path = tmp_path / "coverage.json"
    append_coverage(ledger_path, _result("2026-01-10", items=40, candidates=0), applied=0, held=0)
    rows = load_coverage(ledger_path)
    assert rows[0]["status"] == "quiet"
    assert next_days(rows, date(2026, 1, 10), TODAY, settle_days=7) == [date(2026, 1, 11)]


def test_a_day_search_could_not_see_is_retried(tmp_path):
    # items == 0 -> "blind": we know nothing about that day, so it is not done.
    from conflict_updater.store import append_coverage, load_coverage
    ledger_path = tmp_path / "coverage.json"
    append_coverage(ledger_path, _result("2026-01-10", items=0, candidates=0), applied=0, held=0)
    rows = load_coverage(ledger_path)
    assert rows[0]["status"] == "blind"
    assert next_days(rows, date(2026, 1, 10), TODAY, settle_days=7) == [date(2026, 1, 10)]


def test_a_crashed_day_is_retried_then_eventually_left_behind(tmp_path):
    from conflict_updater.store import append_coverage_failure, load_coverage
    from conflict_updater.schema import ScanRequest
    ledger_path = tmp_path / "coverage.json"
    req = ScanRequest(period_start="2026-01-10", period_end="2026-01-10")

    for attempt in range(1, 4):
        append_coverage_failure(ledger_path, req, RuntimeError("provider down"))
        rows = load_coverage(ledger_path)
        nxt = next_days(rows, date(2026, 1, 10), TODAY, settle_days=7, max_attempts=3)
        if attempt < 3:
            assert nxt == [date(2026, 1, 10)], f"attempt {attempt} must retry the same day"
        else:
            assert nxt == [date(2026, 1, 11)], "after max_attempts the queue moves on"


def test_a_backlog_drains_oldest_first(tmp_path):
    from conflict_updater.store import append_coverage, load_coverage
    ledger_path = tmp_path / "coverage.json"
    start = date(2026, 1, 10)
    seen = []
    for _ in range(4):                       # four consecutive runs, one day each
        todo = next_days(load_coverage(ledger_path), start, TODAY, settle_days=7, max_days=1)
        seen += todo
        append_coverage(ledger_path, _result(todo[0].isoformat()), applied=0, held=0)
    assert seen == [date(2026, 1, 10), date(2026, 1, 11), date(2026, 1, 12), date(2026, 1, 13)]
    assert seen == sorted(seen), "order is load-bearing: status may only move on the latest event"


# ---- one slot per run is reserved for the newest day --------------------------------------

def _d(s):
    from datetime import date
    return date.fromisoformat(s)


def test_the_newest_settled_day_is_covered_even_with_a_huge_backlog():
    # The point of the reservation: a hundred-day backfill must not mean a hundred days before
    # the atlas shows anything from this month.
    todo = next_days([], _d("2026-06-01"), _d("2026-09-17"), settle_days=7, max_days=3)
    assert todo == [_d("2026-06-01"), _d("2026-06-02"), _d("2026-09-10")]


def test_days_are_still_returned_oldest_first():
    # Load-bearing: _run_one applies them in order, and an older day must not be applied after a
    # newer one within the same run.
    todo = next_days([], _d("2026-06-01"), _d("2026-09-17"), settle_days=7, max_days=3)
    assert todo == sorted(todo)


def test_the_reserved_slot_never_scans_the_same_day_twice():
    # When the backlog is small enough that the oldest slots already reach the newest day, the
    # newest must not be appended a second time.
    todo = next_days([], _d("2026-09-08"), _d("2026-09-17"), settle_days=7, max_days=3)
    assert todo == [_d("2026-09-08"), _d("2026-09-09"), _d("2026-09-10")]
    assert len(todo) == len(set(todo))


def test_a_checked_newest_day_hands_its_slot_to_the_backlog():
    ledger = [{"period": "2026-09-10..2026-09-10", "region": "(any)", "status": "found"}]
    todo = next_days(ledger, _d("2026-06-01"), _d("2026-09-17"), settle_days=7, max_days=3)
    assert _d("2026-09-10") not in todo
    assert todo == [_d("2026-06-01"), _d("2026-06-02"), _d("2026-09-09")]


def test_keep_current_off_is_strictly_oldest_first():
    todo = next_days([], _d("2026-06-01"), _d("2026-09-17"), settle_days=7, max_days=3,
                            keep_current=False)
    assert todo == [_d("2026-06-01"), _d("2026-06-02"), _d("2026-06-03")]


def test_one_day_per_run_still_means_one_day():
    todo = next_days([], _d("2026-06-01"), _d("2026-09-17"), settle_days=7, max_days=1)
    assert todo == [_d("2026-06-01")]
