"""Keep the suite offline.

`Settings()` loads ai-updater/.env, so a developer's real JUDGE_BACKEND=jev and TYPESAFE_API_KEY
leaked straight into every test: scan() built a real JevJudge and called the live service for
triage, significance, resolution, enrichment and verification. The tests still passed — every
judge path falls back to the LLM — so nothing looked wrong except the clock: the suite went from
1.6s to 90s, every run burned real quota, and a machine with no key exercised a different code
path than a developer's laptop.

Offline is a property the fakes only give you if nothing reaches past them.
"""
import pytest


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    # The judge is the one backend a test can reach by accident, because scan() constructs it
    # itself when none is passed. Tests that want one inject a fake explicitly.
    monkeypatch.setenv("JUDGE_BACKEND", "none")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("LLM_CACHE", "off")
