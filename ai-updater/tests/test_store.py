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
    from conflict_updater.store import _default_status
    assert _default_status({"status": "suspended", "ongoing": True}) == "suspended"


def test_ongoing_true_wins_over_a_stale_enddate():
    from conflict_updater.store import _default_status
    assert _default_status({"ongoing": True, "endDate": "1962"}) == "active"


def test_date_key_orders_mixed_precision_dates():
    from conflict_updater.store import date_key
    assert date_key("1871") == "1871-00-00"
    assert date_key("1871-05") == "1871-05-00"
    assert date_key("1871-05-01") == "1871-05-01"
    # a bare year sorts before any dated event in that same year (whole-year → start-of-year)
    assert date_key("2024") < date_key("2024-03-01")
    assert date_key("2024-12-31") > date_key("2024-03-01")
