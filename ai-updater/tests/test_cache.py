from conflict_updater.cache import LLMCache, NullCache, cache_key, get_cache


def test_cache_key_is_stable_and_order_sensitive():
    a = cache_key("openrouter", "m1", "sys", "user")
    assert a == cache_key("openrouter", "m1", "sys", "user")      # deterministic
    assert a != cache_key("openrouter", "m2", "sys", "user")      # model matters
    assert a != cache_key("openai", "m1", "sys", "user")          # provider matters
    assert a != cache_key("openrouter", "m1", "sys", "user2")     # prompt matters


def test_cache_key_separator_prevents_field_smearing():
    # Without a separator byte, ("ab","c") and ("a","bc") would hash identically and two
    # different prompts could collide onto one cached answer.
    assert cache_key("p", "m", "ab", "c") != cache_key("p", "m", "a", "bc")


def test_roundtrip(tmp_path):
    c = LLMCache(tmp_path / "c.sqlite3")
    k = cache_key("openrouter", "m", "s", "u")
    assert c.get(k) is None
    c.put(k, "openrouter", "m", '{"ok":true}')
    assert c.get(k) == '{"ok":true}'
    c.close()


def test_hit_and_miss_counters(tmp_path):
    c = LLMCache(tmp_path / "c.sqlite3")
    k = cache_key("p", "m", "s", "u")
    c.get(k)                       # miss
    c.put(k, "p", "m", "v")
    c.get(k)                       # hit
    assert c.stats == {"hits": 1, "misses": 1, "hit_rate": 0.5}
    c.close()


def test_survives_across_connections(tmp_path):
    path = tmp_path / "c.sqlite3"
    k = cache_key("p", "m", "s", "u")
    a = LLMCache(path)
    a.put(k, "p", "m", "persisted")
    a.close()
    b = LLMCache(path)             # a later run, e.g. resuming a crashed scan
    assert b.get(k) == "persisted"
    b.close()


def test_unwritable_path_degrades_to_no_cache(tmp_path):
    # A cache that cannot open its file must never take the pipeline down with it.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    c = LLMCache(blocker / "nested" / "c.sqlite3")
    assert c.get("k") is None
    c.put("k", "p", "m", "v")      # must not raise
    assert c.get("k") is None
    c.close()


def test_null_cache_never_stores():
    n = NullCache()
    n.put("k", "p", "m", "v")
    assert n.get("k") is None
    assert n.stats["hit_rate"] == 0.0


class _S:
    def __init__(self, llm_cache, output_dir):
        self.llm_cache = llm_cache
        self.output_dir = output_dir


def test_factory_defaults_to_null(tmp_path):
    assert isinstance(get_cache(_S("off", tmp_path)), NullCache)


def test_factory_returns_real_cache_when_on(tmp_path):
    c = get_cache(_S("on", tmp_path))
    assert isinstance(c, LLMCache)
    c.close()
