import pytest
from conflict_updater.structured_source import NullStructuredSource, UcdpStructuredSource, get_structured_source
from dataclasses import dataclass


def test_null_structured_source_returns_empty():
    assert NullStructuredSource().fetch("2024-01-01", "2024-12-31") == []


def test_ucdp_structured_source_not_yet_wired():
    # deliberately not live-verified yet (see structured_source.py's class docstring) — should
    # fail loudly, not silently return fabricated data.
    with pytest.raises(NotImplementedError):
        UcdpStructuredSource().fetch("2024-01-01", "2024-12-31")


@dataclass
class _Settings:
    structured_source_backend: str = "none"


def test_get_structured_source_defaults_to_null():
    assert isinstance(get_structured_source(_Settings()), NullStructuredSource)


def test_get_structured_source_ucdp_backend():
    assert isinstance(get_structured_source(_Settings(structured_source_backend="ucdp")), UcdpStructuredSource)
