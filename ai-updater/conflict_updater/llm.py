"""LLM client abstraction. Agents depend on this interface, not on any provider —
so the provider is swappable and tests inject a fake.
"""
from __future__ import annotations

import json
import re
from typing import Protocol, Type, TypeVar
from pydantic import BaseModel

from .cache import cache_key, NullCache

_NULL_CACHE = NullCache()

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def structured(self, model: Type[T], system: str, user: str) -> T:
        """Return an instance of `model`, filled by the LLM from system+user prompts."""
        ...


class LangChainLLM:
    """Real backend. LangChain is imported lazily so importing this module (and running
    the offline tests) needs no provider installed.

    Two structured-output strategies:
      - native  (openai, google): the provider enforces the JSON schema server-side.
      - prompted (openrouter):     many free/reasoning models ignore native response_format
                                   and emit markdown/prose, so we ask for JSON in the prompt
                                   and parse it ourselves — tolerant of fences and reasoning noise.
    """

    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini",
                 temperature: float = 0.0, cache=None):
        self._provider = provider
        self._temperature = temperature
        self._cache = cache if cache is not None else _NULL_CACHE
        # LLM_MODEL accepts a comma-separated fallback chain. A single pinned free slug is how
        # nine consecutive weekly runs died: OpenRouter withdrew the ":free" variant and there
        # was nothing to fall back to. Later entries are tried only when the earlier one is
        # gone or exhausted -- never for a bad prompt, which would just burn a second quota.
        self._models = [m.strip() for m in str(model).split(",") if m.strip()] or [str(model)]
        self._clients: dict[str, object] = {}
        if provider not in ("openai", "google", "gemini", "openrouter"):
            raise ValueError(f"unknown LLM_PROVIDER={provider!r}; wire it in llm.py")
        # Many free/reasoning models ignore native response_format and emit markdown or
        # reasoning prose, so OpenRouter asks for JSON in the prompt and parses it here.
        self._prompted = provider == "openrouter"

    def _client(self, model: str):
        """Build (and memoize) the provider client for one model. Lazy, so a fallback model
        that is never reached never costs an import or a constructor."""
        if model in self._clients:
            return self._clients[model]
        provider = self._provider
        if provider == "openai":
            from langchain_openai import ChatOpenAI  # lazy
            c = ChatOpenAI(model=model, temperature=self._temperature)
        elif provider in ("google", "gemini"):
            from langchain_google_genai import ChatGoogleGenerativeAI  # lazy; reads GOOGLE_API_KEY
            c = ChatGoogleGenerativeAI(model=model, temperature=self._temperature)
        else:  # openrouter -- OpenAI-API-compatible
            import os
            from langchain_openai import ChatOpenAI
            c = ChatOpenAI(
                model=model, temperature=self._temperature,
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                max_tokens=8000,  # reasoning models spend tokens thinking before the JSON
            )
        self._clients[model] = c
        return c

    def structured(self, model: Type[T], system: str, user: str) -> T:
        last = None
        for i, name in enumerate(self._models):
            try:
                return self._structured_one(name, model, system, user)
            except Exception as e:  # noqa: BLE001
                last = e
                if i == len(self._models) - 1 or not _should_failover(e):
                    raise
                print(f"  ... model {name!r} unavailable ({type(e).__name__}); "
                      f"falling back to {self._models[i + 1]!r}")
        raise last  # unreachable: the loop either returns or raises

    def _structured_one(self, name: str, model: Type[T], system: str, user: str) -> T:
        """One model, cache-aware. The cache key includes the exact prompt text, so editing a
        prompt invalidates precisely the calls that prompt affects and nothing else."""
        if self._prompted:
            return self._structured_prompted(name, model, system, user)
        from langchain_core.messages import SystemMessage, HumanMessage  # lazy
        key = cache_key(self._provider, name, system, user)
        hit = self._cache.get(key)
        if hit is not None:
            try:
                return model.model_validate_json(hit)
            except Exception:
                pass  # stale/garbage entry -- fall through and call for real
        chain = self._client(name).with_structured_output(model)
        msgs = [SystemMessage(content=system), HumanMessage(content=user)]
        out = _with_backoff(lambda: chain.invoke(msgs))
        try:
            self._cache.put(key, self._provider, name, out.model_dump_json())
        except Exception:
            pass
        return out

    def _structured_prompted(self, name: str, model: Type[T], system: str, user: str) -> T:
        from langchain_core.messages import SystemMessage, HumanMessage  # lazy
        schema = json.dumps(model.model_json_schema())
        sys = (
            system
            + "\n\nRespond with ONE JSON object that validates against this JSON Schema. "
            + "Output JSON only — no markdown fences, no commentary, no reasoning.\n"
            + "SCHEMA:\n" + schema
        )
        key = cache_key(self._provider, name, sys, user)
        hit = self._cache.get(key)
        if hit is not None:
            try:
                return model.model_validate_json(hit)
            except Exception:
                pass  # stale/garbage entry -- fall through and call for real
        client = self._client(name)
        last_err = None
        for attempt in range(2):
            msgs = [SystemMessage(content=sys), HumanMessage(content=user)]
            resp = _with_backoff(lambda: client.invoke(msgs))
            text = resp.content if hasattr(resp, "content") else str(resp)
            try:
                parsed = model.model_validate(_extract_json(text))
                try:
                    self._cache.put(key, self._provider, name, parsed.model_dump_json())
                except Exception:
                    pass
                return parsed
            except Exception as e:  # noqa: BLE001
                last_err = e
                # An EMPTY reply is not malformed JSON — the model produced nothing, usually
                # because the task was too big for it. Scolding it about JSON and re-sending
                # the whole prompt just pays the input tokens again for the same outcome, so
                # fail fast and let the model fallback chain take its turn. Measured: one
                # failing extraction re-sent a ~32k-token prompt four times (two retries
                # here, twice over after failover) to learn nothing.
                if not (text or "").strip():
                    raise ValueError(
                        f"model did not return schema-valid JSON for {model.__name__}: "
                        f"empty model reply") from e
                sys += "\n\nYour previous reply was not valid JSON for the schema. Return ONLY the JSON object."
        raise ValueError(f"model did not return schema-valid JSON for {model.__name__}: {last_err}")


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a possibly-noisy model reply (fences, prose, reasoning).

    Uses the decoder's raw_decode from each '{' so it tolerates prose/reasoning before or
    after the object, and stray braces in that prose — rather than a naive first-brace..
    last-brace slice that breaks on either.
    """
    if not text:
        raise ValueError("empty model reply")
    dec = json.JSONDecoder()

    # prefer a fenced ```json ... ``` block if the model used one
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        try:
            return dec.raw_decode(m.group(1).strip())[0]
        except ValueError:
            pass

    # otherwise scan each '{' and return the first that decodes to a complete JSON object
    idx = text.find("{")
    while idx != -1:
        try:
            obj, _ = dec.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        idx = text.find("{", idx + 1)
    raise ValueError(f"no JSON object found in reply: {text[:120]!r}")


def _with_backoff(call, *, retries: int = 5, base: float = 8.0):
    """Retry on rate-limit / quota errors (free tiers throttle hard). Exponential backoff."""
    import time
    for attempt in range(retries + 1):
        try:
            return call()
        except Exception as e:  # provider-agnostic: match by message
            msg = str(e).lower()
            transient = any(s in msg for s in ("429", "resource_exhausted", "rate limit", "quota", "overloaded", "503"))
            if not transient or attempt == retries:
                raise
            wait = base * (2 ** attempt)
            print(f"  … rate-limited, waiting {wait:.0f}s (attempt {attempt + 1}/{retries})")
            time.sleep(wait)


def _should_failover(e: Exception) -> bool:
    """True when trying a DIFFERENT model could plausibly help.

    Three cases: the model is gone, its quota is spent, or it could not produce the structured
    output at all. That last one was originally excluded on the grounds that a bad prompt would
    fail identically everywhere — but that is not what it turned out to mean in practice. A model
    returning an EMPTY reply after two prompted retries is a capability failure on a hard
    structured task (extracting every event from an article pool), and a different model really
    does succeed where one returns nothing. Measured, not assumed.
    """
    msg = str(e).lower()
    if "did not return schema-valid json" in msg or "empty model reply" in msg:
        return True
    return any(t in msg for t in (
        "404", "not found", "no endpoints", "unavailable", "decommissioned", "deprecated",
        "is not a valid model", "does not exist", "no allowed providers",
        "insufficient_quota", "exceeded your current quota", "billing",
        "429", "rate limit", "resource_exhausted",   # only reached after _with_backoff gave up
    ))


def get_llm(settings) -> LLMClient:
    from .cache import get_cache
    return LangChainLLM(provider=settings.llm_provider, model=settings.llm_model,
                        cache=get_cache(settings))
