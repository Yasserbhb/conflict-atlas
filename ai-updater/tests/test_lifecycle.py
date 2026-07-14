from pathlib import Path
from conflict_updater import lifecycle


def test_load_profiles_parses_the_real_config():
    profiles = lifecycle.load_profiles(Path(__file__).resolve().parent.parent / "config" / "lifecycle.yml")
    assert profiles["war"]["default_terminal"] == "ended"
    assert profiles["war"]["dwell_days"] == 45
    assert profiles["disputed_territory"]["resolved_requires"] == ["treaty", "demarcation"]


def test_load_profiles_missing_file_returns_empty():
    assert lifecycle.load_profiles(Path("/nonexistent/lifecycle.yml")) == {}


def test_load_profiles_unparseable_file_returns_empty(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("not: [valid: yaml: at: all", encoding="utf-8")
    assert lifecycle.load_profiles(bad) == {}
