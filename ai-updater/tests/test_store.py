import json
from conflict_updater.store import load_base


def _seed(conflicts):
    return {"version": "1.0.0", "conflicts": conflicts}


def test_missing_status_infers_ended_from_ongoing_false(tmp_path):
    # most conflicts predate the `status` field entirely — must not default to "active"
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(_seed([
        {"id": "seed_x", "title": "X", "startDate": "1830", "endDate": "1962", "ongoing": False},
    ])), encoding="utf-8")
    base = load_base(path)
    assert base[0].status == "ended"


def test_missing_status_infers_active_when_ongoing_true(tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(_seed([
        {"id": "seed_y", "title": "Y", "startDate": "2022", "ongoing": True},
    ])), encoding="utf-8")
    base = load_base(path)
    assert base[0].status == "active"


def test_explicit_status_is_kept_even_if_ongoing_conflicts():
    from conflict_updater.store import default_status
    assert default_status({"status": "suspended", "ongoing": True}) == "suspended"


def test_ongoing_true_wins_over_a_stale_enddate():
    from conflict_updater.store import default_status
    assert default_status({"ongoing": True, "endDate": "1962"}) == "active"


def test_date_key_orders_mixed_precision_dates():
    from conflict_updater.store import date_key
    assert date_key("1871") == "1871-00-00"
    assert date_key("1871-05") == "1871-05-00"
    assert date_key("1871-05-01") == "1871-05-01"
    # a bare year sorts before any dated event in that same year (whole-year → start-of-year)
    assert date_key("2024") < date_key("2024-03-01")
    assert date_key("2024-12-31") > date_key("2024-03-01")


def test_coverage_status_distinguishes_the_three_cases():
    from conflict_updater.store import _coverage_status
    assert _coverage_status({"items": 0, "candidates": 0}) == "blind"    # search returned nothing
    assert _coverage_status({"items": 40, "candidates": 0}) == "quiet"   # searched, nothing found
    assert _coverage_status({"items": 40, "candidates": 3}) == "found"   # events surfaced


def test_coverage_ledger_appends_and_persists(tmp_path):
    from conflict_updater.store import append_coverage, load_coverage, render_coverage
    from conflict_updater.schema import ScanResult, ScanRequest
    path = tmp_path / "coverage.json"
    r = ScanResult(request=ScanRequest(period_start="1870", period_end="1900", region="Algeria"),
                   stats={"items": 40, "candidates": 3, "proposals": 2, "dropped": 1})

    entry = append_coverage(path, r, limited=6)
    assert entry["region"] == "Algeria" and entry["status"] == "found" and entry["limited_to"] == 6

    led = load_coverage(path)
    assert len(led) == 1 and led[0]["period"] == "1870..1900"

    append_coverage(path, r)                        # a second scan of the same cell
    assert len(load_coverage(path)) == 2            # ledger keeps history, doesn't overwrite
    assert "Algeria" in render_coverage(load_coverage(path))


def test_load_coverage_missing_file_is_empty(tmp_path):
    from conflict_updater.store import load_coverage, render_coverage
    assert load_coverage(tmp_path / "nope.json") == []
    assert "nothing has been searched" in render_coverage([])


def test_write_digest_reports_added_and_held(tmp_path):
    from conflict_updater.store import write_digest
    from conflict_updater.schema import ScanResult, ScanRequest, Proposal, Event
    added = Proposal(kind="attach", target_conflict_id="seed_gaza",
                     event=Event(date="2026-07-02", title="Strike", kind="attack", severity=4),
                     needs_human=False)
    held = Proposal(kind="attach", target_conflict_id="seed_gaza",
                    event=Event(date="2026-07-03", title="Rumoured raid", kind="attack", severity=2),
                    needs_human=True)
    res = ScanResult(request=ScanRequest(period_start="2026-07-01", period_end="2026-07-08"),
                     proposals=[added, held], dropped=["already known: 2026-07-01 X"],
                     stats={"proposals": 2})
    path = write_digest(tmp_path, res, [added], ok=True)
    text = path.read_text(encoding="utf-8")
    assert "Added to the atlas (1)" in text and "Strike" in text
    assert "Held" in text and "Rumoured raid" in text
    assert "Already in the atlas" in text


# ---- coverage ledger must record failures -------------------------------------------------
# append_coverage() used to run only AFTER scan() returned, so a crashed scan wrote nothing.
# Nine dead weeks left zero trace while the public coverage table kept showing stale rows.

def test_failed_scan_is_recorded_as_a_blind_window(tmp_path):
    from conflict_updater.store import append_coverage_failure, load_coverage
    from conflict_updater.schema import ScanRequest

    ledger = tmp_path / "coverage.json"
    req = ScanRequest(period_start="2026-09-07", period_end="2026-09-14", region="Africa")
    entry = append_coverage_failure(ledger, req, RuntimeError("model 404"), limited=12)

    assert entry["status"] == "failed"
    assert entry["period"] == "2026-09-07..2026-09-14"
    assert entry["region"] == "Africa"
    assert "RuntimeError: model 404" in entry["error"]
    assert entry["limited_to"] == 12
    assert load_coverage(ledger) == [entry], "must be persisted, not just returned"


def test_failure_entries_append_rather_than_overwrite(tmp_path):
    from conflict_updater.store import append_coverage_failure, load_coverage
    from conflict_updater.schema import ScanRequest

    ledger = tmp_path / "coverage.json"
    for wk in ("2026-09-07", "2026-09-14"):
        append_coverage_failure(ledger, ScanRequest(period_start=wk, period_end=wk), OSError("down"))
    assert len(load_coverage(ledger)) == 2, "each dead week needs its own row"


def test_every_entry_is_stamped_with_the_prompt_version(tmp_path):
    from conflict_updater.store import append_coverage_failure
    from conflict_updater.prompts import prompt_version
    from conflict_updater.schema import ScanRequest

    entry = append_coverage_failure(tmp_path / "c.json",
                                    ScanRequest(period_start="a", period_end="b"), ValueError("x"))
    assert entry["prompt_version"] == prompt_version()


def test_error_text_is_truncated_so_a_huge_traceback_cannot_bloat_the_ledger(tmp_path):
    from conflict_updater.store import append_coverage_failure
    from conflict_updater.schema import ScanRequest

    entry = append_coverage_failure(tmp_path / "c.json",
                                    ScanRequest(period_start="a", period_end="b"),
                                    RuntimeError("x" * 5000))
    assert len(entry["error"]) <= 300


def test_ledger_row_links_to_its_actions_run(tmp_path, monkeypatch):
    # A failed row is only actionable if you can reach that run's actual log output from it.
    from conflict_updater.store import append_coverage_failure
    from conflict_updater.schema import ScanRequest

    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Yasserbhb/conflict-atlas")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    entry = append_coverage_failure(tmp_path / "c.json",
                                    ScanRequest(period_start="a", period_end="b"), OSError("x"))
    assert entry["run_url"] == "https://github.com/Yasserbhb/conflict-atlas/actions/runs/42"


def test_run_url_is_absent_when_not_running_in_ci(tmp_path, monkeypatch):
    from conflict_updater.store import append_coverage_failure
    from conflict_updater.schema import ScanRequest

    for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"):
        monkeypatch.delenv(k, raising=False)
    entry = append_coverage_failure(tmp_path / "c.json",
                                    ScanRequest(period_start="a", period_end="b"), OSError("x"))
    assert entry["run_url"] is None, "a local run has no Actions URL to point at"


# ---- the run summary the app renders ------------------------------------------------------
# The Pipeline page shows last week's findings in-app rather than sending you to GitHub, so
# this JSON is what a reader actually sees.

def _summary_result():
    from conflict_updater.schema import (
        ScanResult, ScanRequest, Proposal, Event, Source, VerifyOutput,
    )
    held = Proposal(
        kind="attach", target_conflict_id="seed_gaza",
        event=Event(date="2026-09-09", title="Disputed strike reported"),
        verify=VerifyOutput(verdict="uncertain", confidence=0.4, independent_sources=1,
                            cross_alignment=False, decision="needs_human",
                            open_question="Is there independent reporting of this strike?"),
        needs_human=True,
    )
    applied = Proposal(
        kind="attach", target_conflict_id="seed_gaza",
        event=Event(date="2026-09-10", title="Corroborated strike", kind="attack", severity=4,
                    sources=[Source(url="http://a"), Source(url="http://b")]),
        verify=VerifyOutput(verdict="pass", confidence=0.95, independent_sources=3,
                            cross_alignment=True, decision="auto_approve"),
        needs_human=False,
    )
    res = ScanResult(
        request=ScanRequest(period_start="2026-09-07", period_end="2026-09-14"),
        proposals=[applied, held], dropped=["already known: x"], stats={"items": 40},
    )
    return res, [applied]


def test_run_summary_separates_what_landed_from_what_was_held(tmp_path):
    import json
    from conflict_updater.store import write_run_summary
    res, applied = _summary_result()
    path = write_run_summary(tmp_path, res, applied, ok=True)
    s = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "latest_run.json", "the app imports a fixed filename"
    assert s["period"] == "2026-09-07..2026-09-14"
    assert [e["title"] for e in s["added"]] == ["Corroborated strike"]
    assert [e["title"] for e in s["held"]] == ["Disputed strike reported"]


def test_held_events_carry_the_question_that_stopped_them(tmp_path):
    import json
    from conflict_updater.store import write_run_summary
    res, applied = _summary_result()
    s = json.loads(write_run_summary(tmp_path, res, applied, ok=True).read_text(encoding="utf-8"))
    # the single most useful line on the page: why it wasn't published
    assert s["held"][0]["question"] == "Is there independent reporting of this strike?"
    assert s["held"][0]["confidence"] == 0.4


def test_run_summary_is_overwritten_not_appended(tmp_path):
    import json
    from conflict_updater.store import write_run_summary
    res, applied = _summary_result()
    write_run_summary(tmp_path, res, applied, ok=True)
    path = write_run_summary(tmp_path, res, [], ok=True)      # a later run with nothing applied
    s = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(s, dict), "only the latest run is kept, so the bundle stays a fixed size"
    assert s["added"] == []


def test_the_ledger_keeps_the_whole_stats_dict(tmp_path):
    """The ledger is the only durable per-run record, so it must carry the cost numbers.

    `queries` is the billed-search count and `triaged_out` is what the cheap filter saved; neither
    had a home before. latest_run.json is overwritten every run and the digest footer is markdown,
    so without this a week of running leaves nothing chartable.
    """
    from conflict_updater.schema import ScanRequest, ScanResult
    from conflict_updater.store import append_coverage

    res = ScanResult(
        request=ScanRequest(period_start="2026-06-01", period_end="2026-06-01"),
        proposals=[], dropped=[], failed=[],
        stats={"queries": 6, "items": 68, "triaged_out": 59, "out_of_window": 4,
               "candidates": 5, "proposals": 5, "dropped": 1},
    )
    entry = append_coverage(tmp_path / "coverage.json", res, applied=2, held=3)
    assert entry["stats"]["queries"] == 6
    assert entry["stats"]["triaged_out"] == 59
    assert entry["stats"]["out_of_window"] == 4
    assert entry["items"] == 68, "the flat fields the table reads must still be there"
    assert entry["applied"] == 2 and entry["held"] == 3


def test_the_stored_stats_cannot_be_mutated_from_outside(tmp_path):
    # dict(s), not s — the result object outlives this call and is written to disk separately.
    from conflict_updater.schema import ScanRequest, ScanResult
    from conflict_updater.store import append_coverage

    stats = {"queries": 6, "items": 10, "candidates": 1, "proposals": 1, "dropped": 0}
    res = ScanResult(request=ScanRequest(period_start="2026-06-01", period_end="2026-06-01"),
                     proposals=[], dropped=[], failed=[], stats=stats)
    entry = append_coverage(tmp_path / "coverage.json", res)
    stats["queries"] = 999
    assert entry["stats"]["queries"] == 6
