from pathlib import Path
from conflict_updater.search import load_source_config, TavilySearch, _outlet


class _FakeTavilyClient:
    """Stands in for tavily.TavilyClient — no network call."""

    def search(self, query, max_results, search_depth):
        return {"results": [
            {"title": "Reuters piece", "url": "https://www.reuters.com/a", "content": "..."},
            {"title": "Unlisted outlet piece", "url": "https://unlisted.example/b", "content": "..."},
        ]}


def test_load_source_config_parses_the_real_config():
    cfg = load_source_config(Path(__file__).resolve().parent.parent / "config" / "sources.yml")
    assert cfg["reuters.com"]["alignment"] == "independent"
    assert cfg["rt.com"]["alignment"] == "russian"


def test_load_source_config_missing_file_returns_empty():
    assert load_source_config(Path("/nonexistent/sources.yml")) == {}


def test_outlet_strips_www_prefix():
    assert _outlet("https://www.reuters.com/article/1") == "reuters.com"
    assert _outlet("https://aljazeera.com/article/1") == "aljazeera.com"


def test_tavily_search_tags_alignment_from_source_config(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key-for-test")
    ts = TavilySearch(source_config={"reuters.com": {"alignment": "independent"}})
    ts._client = _FakeTavilyClient()  # swap out the real client — no network call

    items = ts.search("test query")

    assert items[0].outlet == "reuters.com" and items[0].alignment == "independent"
    assert items[1].outlet == "unlisted.example" and items[1].alignment is None


def test_tavily_search_with_no_source_config_leaves_alignment_none(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key-for-test")
    ts = TavilySearch()  # no source_config passed — defaults to {}
    ts._client = _FakeTavilyClient()

    items = ts.search("test query")

    assert all(i.alignment is None for i in items)
