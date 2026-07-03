"""Offline doubles so the whole pipeline runs in tests without any API."""
from __future__ import annotations

from conflict_updater.schema import RawItem


class FakeLLM:
    """Returns a canned instance per output-model type. Records call order."""

    def __init__(self, responses: dict):
        self.responses = responses          # {ModelClass: instance | callable(user)->instance}
        self.calls: list[str] = []

    def structured(self, model, system, user):
        self.calls.append(model.__name__)
        if model not in self.responses:
            raise AssertionError(f"FakeLLM: no canned response for {model.__name__}")
        r = self.responses[model]
        return r(user) if callable(r) else r


class FakeSearch:
    def __init__(self, items: list[RawItem]):
        self.items = items

    def search(self, query: str, lang: str = "en", max_results: int = 8):
        return list(self.items)
