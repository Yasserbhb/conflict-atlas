"""The model fallback chain — the direct fix for the outage that killed nine weekly runs.

OpenRouter withdrew the `:free` variant of the pinned model; the pipeline 404'd and had
nothing to fall back to. These tests pin the behaviour that stops that recurring.
"""
import pytest
from pydantic import BaseModel

from conflict_updater.cache import LLMCache, cache_key
from conflict_updater.llm import LangChainLLM, _should_failover


class Out(BaseModel):
    value: str


# ---- which errors justify trying a different model ----

@pytest.mark.parametrize("msg", [
    "Error code: 404 - This model is unavailable for free",
    "No endpoints found for openai/gpt-oss-120b:free",
    "model has been decommissioned",
    "insufficient_quota",
    "429 rate limit exceeded",
])
def test_failover_on_model_gone_or_exhausted(msg):
    assert _should_failover(Exception(msg)) is True


@pytest.mark.parametrize("msg", [
    "did not return schema-valid JSON for ScoperOutput",
    "Connection reset by peer",
    "invalid api key",
])
def test_no_failover_on_errors_another_model_would_also_hit(msg):
    # A bad prompt or a broken key fails identically on the next model, so falling over
    # would just burn a second quota for the same failure.
    assert _should_failover(Exception(msg)) is False


# ---- the chain itself ----

def _llm(models, behaviour, cache=None):
    """LangChainLLM with its provider clients stubbed — no network, no langchain import."""
    llm = LangChainLLM(provider="openai", model=models, cache=cache)

    class _Stub:
        def __init__(self, name):
            self.name = name

        def with_structured_output(self, _model):
            return self

        def invoke(self, _msgs):
            return behaviour(self.name)

    llm._client = lambda name: _Stub(name)
    return llm


def test_falls_through_to_the_next_model_when_the_first_is_gone():
    tried = []

    def behaviour(name):
        tried.append(name)
        if name == "gone:free":
            raise Exception("Error code: 404 - This model is unavailable for free")
        return Out(value=name)

    out = _llm("gone:free,works:free", behaviour).structured(Out, "sys", "user")
    assert out.value == "works:free"
    assert tried == ["gone:free", "works:free"]


def test_stops_at_the_first_working_model():
    tried = []

    def behaviour(name):
        tried.append(name)
        return Out(value=name)

    out = _llm("first,second,third", behaviour).structured(Out, "sys", "user")
    assert out.value == "first"
    assert tried == ["first"], "later models must not be called once one succeeds"


def test_a_prompt_error_propagates_instead_of_burning_the_next_quota():
    tried = []

    def behaviour(name):
        tried.append(name)
        raise Exception("did not return schema-valid JSON for Out")

    with pytest.raises(Exception, match="schema-valid"):
        _llm("first,second", behaviour).structured(Out, "sys", "user")
    assert tried == ["first"], "must not try the second model for a non-failover error"


def test_raises_the_last_error_when_every_model_is_gone():
    def behaviour(name):
        raise Exception(f"404 not found: {name}")

    with pytest.raises(Exception, match="404 not found: b"):
        _llm("a,b", behaviour).structured(Out, "sys", "user")


def test_whitespace_and_single_model_still_work():
    assert _llm(" solo ", lambda n: Out(value=n))._models == ["solo"]


# ---- caching ----

def test_second_identical_call_is_served_from_cache(tmp_path):
    cache = LLMCache(tmp_path / "c.sqlite3")
    calls = []

    def behaviour(name):
        calls.append(name)
        return Out(value="fresh")

    llm = _llm("m", behaviour, cache=cache)
    a = llm.structured(Out, "sys", "user")
    b = llm.structured(Out, "sys", "user")
    assert a.value == b.value == "fresh"
    assert len(calls) == 1, "identical prompt must not hit the provider twice"
    assert cache.stats["hits"] == 1
    cache.close()


def test_a_changed_prompt_misses_the_cache(tmp_path):
    cache = LLMCache(tmp_path / "c.sqlite3")
    calls = []

    def behaviour(name):
        calls.append(name)
        return Out(value="v")

    llm = _llm("m", behaviour, cache=cache)
    llm.structured(Out, "sys", "user")
    llm.structured(Out, "sys EDITED", "user")
    assert len(calls) == 2, "editing a prompt must invalidate exactly that call"
    cache.close()


def test_a_corrupt_cache_entry_falls_through_to_a_real_call(tmp_path):
    cache = LLMCache(tmp_path / "c.sqlite3")
    cache.put(cache_key("openai", "m", "sys", "user"), "openai", "m", "{not json")
    llm = _llm("m", lambda n: Out(value="recovered"), cache=cache)
    assert llm.structured(Out, "sys", "user").value == "recovered"
    cache.close()
