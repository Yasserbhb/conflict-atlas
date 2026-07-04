"""Web-search abstraction. Provider is swappable; tests inject a fake."""
from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse
from .schema import RawItem


def _outlet(url: str) -> str:
    """Bare domain as the outlet name (e.g. 'reuters.com'), so the fact-checker can count
    independent outlets and cross-outlet corroboration."""
    net = urlparse(url or "").netloc.lower()
    return net[4:] if net.startswith("www.") else net


class SearchClient(Protocol):
    def search(self, query: str, lang: str = "en", max_results: int = 8) -> list[RawItem]:
        ...


class TavilySearch:
    """Real backend (lazy import)."""

    def __init__(self):
        from tavily import TavilyClient  # lazy
        import os
        self._client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    def search(self, query: str, lang: str = "en", max_results: int = 8) -> list[RawItem]:
        resp = self._client.search(query=query, max_results=max_results)
        out: list[RawItem] = []
        for r in resp.get("results", []):
            out.append(RawItem(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                outlet=_outlet(r.get("url", "")),
                lang=lang,
            ))
        return out


class NullSearch:
    """No-op backend for dry runs."""

    def search(self, query: str, lang: str = "en", max_results: int = 8) -> list[RawItem]:
        return []


def get_search(settings) -> SearchClient:
    if settings.search_backend == "tavily":
        return TavilySearch()
    return NullSearch()
