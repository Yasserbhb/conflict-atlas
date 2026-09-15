"""Tests for the backtest harness. A measurement tool that lies is worse than no tool, so the
hold-out logic and the matcher are pinned hard here.
"""
from conflict_updater.evaluate import (
    GoldEvent, extract_gold, prune, same_event, score, calibration, in_window, render,
)
from conflict_updater.schema import Event, Proposal, ScanResult, ScanRequest, VerifyOutput


def _seed():
    return {
        "conflicts": [
            {   # straddles the window — survives pruning, so its event should be ATTACHED
                "id": "seed_long_war", "title": "Long War",
                "events": [
                    {"date": "1960-03-01", "title": "Opening offensive", "kind": "offensive", "severity": 4},
                    {"date": "1965-06-02", "title": "Siege of the capital", "kind": "battle", "severity": 5},
                ],
            },
            {   # lives entirely inside the window — removed, so its event should found a NEW one
                "id": "seed_brief", "title": "Brief Uprising",
                "events": [{"date": "1965-09-09", "title": "Palace revolt", "kind": "milestone", "severity": 3}],
            },
            {   # wholly outside the window — untouched
                "id": "seed_other", "title": "Other War",
                "events": [{"date": "1999-01-01", "title": "Border clash", "kind": "attack", "severity": 2}],
            },
        ]
    }


# ---- window arithmetic ----

def test_bare_year_counts_as_the_whole_year():
    assert in_window("1965", "1965-01-01", "1965-12-31")
    assert in_window("1965-06-02", "1965-01-01", "1965-12-31")
    assert not in_window("1964-12-31", "1965-01-01", "1965-12-31")
    assert not in_window("1966-01-01", "1965-01-01", "1965-12-31")


# ---- gold extraction and hold-out ----

def test_extract_gold_takes_only_in_window_events():
    gold = extract_gold(_seed(), "1965-01-01", "1965-12-31")
    assert {g.title for g in gold} == {"Siege of the capital", "Palace revolt"}


def test_prune_removes_the_gold_events_from_the_base():
    pruned, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    remaining = {e["title"] for c in pruned["conflicts"] for e in c["events"]}
    assert "Siege of the capital" not in remaining, "hold-out failed — Resolver would answer 'known'"
    assert "Palace revolt" not in remaining
    assert "Opening offensive" in remaining, "out-of-window events must stay"


def test_prune_drops_a_conflict_left_with_no_events():
    # Otherwise the pipeline gets a free attach target it never had to earn.
    pruned, _ = prune(_seed(), "1965-01-01", "1965-12-31")
    assert {c["id"] for c in pruned["conflicts"]} == {"seed_long_war", "seed_other"}


def test_expected_decision_differs_per_event():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    by_title = {g.title: g for g in gold}
    assert by_title["Siege of the capital"].expected_decision == "attach"
    assert by_title["Palace revolt"].expected_decision == "new"


def test_prune_does_not_mutate_the_caller_seed():
    original = _seed()
    prune(original, "1965-01-01", "1965-12-31")
    titles = {e["title"] for c in original["conflicts"] for e in c["events"]}
    assert "Siege of the capital" in titles, "prune must deep-copy, not edit the live seed"


# ---- matching ----

def _gold(date="1965-06-02", title="Siege of the capital"):
    return GoldEvent(conflict_id="c", conflict_title="C", date=date, title=title)


def _ev(date, title, severity=4, kind="battle"):
    return Event(date=date, title=title, severity=severity, kind=kind)


def test_matches_reworded_titles():
    # The pipeline writes its own headline; it will never reproduce a curator's phrasing.
    assert same_event(_gold(), _ev("1965-06-02", "Siege of the Capital begins"))


def test_matches_when_one_side_gives_only_a_year():
    assert same_event(_gold(date="1965"), _ev("1965-06-02", "Siege of the capital"))


def test_rejects_a_different_year():
    assert not same_event(_gold(), _ev("1966-06-02", "Siege of the capital"))


def test_rejects_a_different_stated_month():
    assert not same_event(_gold(), _ev("1965-11-02", "Siege of the capital"))


def test_rejects_an_unrelated_event_in_the_same_month():
    assert not same_event(_gold(), _ev("1965-06-02", "Currency devaluation announced"))


# ---- scoring ----

def _proposal(ev, kind="attach", target="seed_long_war", confidence=0.9):
    return Proposal(kind=kind, target_conflict_id=target, event=ev,
                    verify=VerifyOutput(verdict="pass", confidence=confidence,
                                        independent_sources=2, cross_alignment=True,
                                        decision="auto_approve"),
                    needs_human=False)


def _result(proposals):
    return ScanResult(request=ScanRequest(period_start="1965-01-01", period_end="1965-12-31"),
                      proposals=proposals)


def test_perfect_run_scores_1():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    props = [
        _proposal(_ev("1965-06-02", "Siege of the capital", 5, "battle")),
        _proposal(_ev("1965-09-09", "Palace revolt", 3, "milestone"),
                  kind="new_conflict", target=None),
    ]
    m = score(_result(props), gold)
    assert m["matched"] == 2 and m["missed"] == 0 and m["spurious"] == 0
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    assert m["resolution_accuracy"] == 1.0
    assert m["kind_accuracy"] == 1.0
    assert m["severity_within_1"] == 1.0


def test_a_missed_event_lowers_recall_not_precision():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    m = score(_result([_proposal(_ev("1965-06-02", "Siege of the capital"))]), gold)
    assert m["matched"] == 1 and m["missed"] == 1 and m["spurious"] == 0
    assert m["recall"] == 0.5 and m["precision"] == 1.0


def test_an_invented_event_lowers_precision_not_recall():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    props = [
        _proposal(_ev("1965-06-02", "Siege of the capital")),
        _proposal(_ev("1965-09-09", "Palace revolt"), kind="new_conflict", target=None),
        _proposal(_ev("1965-04-04", "Entirely fabricated skirmish")),
    ]
    m = score(_result(props), gold)
    assert m["recall"] == 1.0
    assert m["spurious"] == 1 and m["precision"] < 1.0


def test_attaching_to_the_wrong_conflict_is_caught():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    props = [_proposal(_ev("1965-06-02", "Siege of the capital"), target="seed_other")]
    m = score(_result(props), gold)
    assert m["matched"] == 1
    assert m["resolution_accuracy"] == 0.0, "right event, wrong conflict must not count as resolved"


def test_founding_a_new_conflict_when_it_should_have_attached_is_caught():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    props = [_proposal(_ev("1965-06-02", "Siege of the capital"),
                       kind="new_conflict", target=None)]
    m = score(_result(props), gold)
    assert m["resolution_accuracy"] == 0.0


def test_severity_tolerance_is_plus_or_minus_one():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    # gold severity for the siege is 5; 4 is within tolerance, 2 is not
    near = score(_result([_proposal(_ev("1965-06-02", "Siege of the capital", severity=4))]), gold)
    far = score(_result([_proposal(_ev("1965-06-02", "Siege of the capital", severity=2))]), gold)
    assert near["severity_within_1"] == 1.0
    assert far["severity_within_1"] == 0.0


# ---- calibration ----

def test_calibration_flags_overconfidence():
    # Four proposals all claiming 0.95 confidence; only one is actually right.
    matched = [(None, _proposal(_ev("1965-06-02", "x"), confidence=0.95))]
    spurious = [_proposal(_ev("1965-01-0%d" % i, "y"), confidence=0.95) for i in (1, 2, 3)]
    rows = calibration(matched, spurious)
    row = next(r for r in rows if r["range"].startswith("0.90"))
    assert row["n"] == 4
    assert row["observed"] == 0.25, "1 of 4 correct while stating 0.95 — clearly overconfident"
    assert row["stated_mid"] > row["observed"]


def test_calibration_skips_empty_buckets():
    rows = calibration([(None, _proposal(_ev("1965-06-02", "x"), confidence=0.95))], [])
    assert all(r["n"] > 0 for r in rows)
    assert len(rows) == 1


def test_render_produces_a_readable_report():
    _, gold = prune(_seed(), "1965-01-01", "1965-12-31")
    m = score(_result([_proposal(_ev("1965-06-02", "Siege of the capital"))]), gold)
    text = render("1965-01-01..1965-12-31", m)
    assert "Backtest" in text and "precision" in text and "recall" in text


def test_year_only_events_are_not_silently_dropped_from_gold():
    # Regression: date_key() pads a bare year to "1965-00-00", which sorts before
    # "1965-01-01" — so year-only events (most of the pre-1900 atlas) fell outside their own
    # year and never entered the gold set, making the backtest measure the wrong events.
    seed = {"conflicts": [{"id": "c", "title": "C",
                           "events": [{"date": "1712", "title": "A year-only event"}]}]}
    gold = extract_gold(seed, "1712-01-01", "1712-12-31")
    assert [g.title for g in gold] == ["A year-only event"]


def test_month_only_events_are_included():
    seed = {"conflicts": [{"id": "c", "title": "C",
                           "events": [{"date": "1965-06", "title": "A month-only event"}]}]}
    assert len(extract_gold(seed, "1965-06-01", "1965-06-30")) == 1
    assert len(extract_gold(seed, "1965-07-01", "1965-07-31")) == 0


def test_a_year_only_window_covers_the_whole_year():
    seed = {"conflicts": [{"id": "c", "title": "C",
                           "events": [{"date": "1965-06-02", "title": "Mid-year"}]}]}
    assert len(extract_gold(seed, "1965", "1965")) == 1
