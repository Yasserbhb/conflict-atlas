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


def test_the_real_source_config_is_not_silently_empty():
    # load_source_config swallows YAML errors and returns {} — which means one missing space
    # after a colon disables ALL alignment tagging with no error anywhere. That exact typo
    # happened twice in this repo. An empty config is never correct, so assert it isn't.
    from pathlib import Path
    cfg = load_source_config(Path(__file__).resolve().parent.parent / "config" / "sources.yml")
    assert len(cfg) >= 20, "the outlet list parsed to almost nothing — check the YAML"
    assert all("alignment" in v for v in cfg.values()), "every outlet needs an alignment"


def test_the_outlet_list_spans_genuinely_opposed_perspectives():
    # The cross-alignment check only means something if the list covers more than one side.
    # Two outlets agreeing is not corroboration if they share a vantage point.
    from pathlib import Path
    cfg = load_source_config(Path(__file__).resolve().parent.parent / "config" / "sources.yml")
    alignments = {v["alignment"] for v in cfg.values()}
    for opposed in (("russian", "ukrainian"), ("israeli", "palestinian"), ("iranian", "western")):
        assert set(opposed) <= alignments, f"{opposed} — only one side of this is represented"
    assert len({v["lang"] for v in cfg.values()}) >= 5, "multilingual sourcing needs languages"


def test_lifecycle_config_is_not_silently_empty():
    from pathlib import Path
    from conflict_updater.lifecycle import load_profiles
    profiles = load_profiles(Path(__file__).resolve().parent.parent / "config" / "lifecycle.yml")
    assert len(profiles) >= 5, "lifecycle.yml parsed to almost nothing — check the YAML"
