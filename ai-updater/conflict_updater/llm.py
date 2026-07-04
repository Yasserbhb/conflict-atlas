"""LLM client abstraction. Agents depend on this interface, not on any provider —
so the provider is swappable and tests inject a fake.
"""
from __future__ import annotations

import json
import re
from typing import Protocol, Type, TypeVar
from pydantic import BaseModel

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

    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini", temperature: float = 0.0):
        self._prompted = False
        if provider == "openai":
            from langchain_openai import ChatOpenAI  # lazy
            self._llm = ChatOpenAI(model=model, temperature=temperature)
        elif provider in ("google", "gemini"):
            from langchain_google_genai import ChatGoogleGenerativeAI  # lazy; reads GOOGLE_API_KEY
            self._llm = ChatGoogleGenerativeAI(model=model, temperature=temperature)
        elif provider == "openrouter":
            import os
            from langchain_openai import ChatOpenAI  # OpenRouter is OpenAI-API-compatible
            self._llm = ChatOpenAI(
                model=model, temperature=temperature,
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                max_tokens=8000,  # reasoning models spend tokens thinking before the JSON
            )
            self._prompted = True  # don't trust native structured output on free models
        else:
            raise ValueError(f"unknown LLM_PROVIDER={provider!r}; wire it in llm.py")

    def structured(self, model: Type[T], system: str, user: str) -> T:
        if self._prompted:
            return self._structured_prompted(model, system, user)
        from langchain_core.messages import SystemMessage, HumanMessage  # lazy
        chain = self._llm.with_structured_output(model)
        msgs = [SystemMessage(content=system), HumanMessage(content=user)]
        return _with_backoff(lambda: chain.invoke(msgs))

    def _structured_prompted(self, model: Type[T], system: str, user: str) -> T:
        from langchain_core.messages import SystemMessage, HumanMessage  # lazy
        schema = json.dumps(model.model_json_schema())
        sys = (
            system
            + "\n\nRespond with ONE JSON object that validates against this JSON Schema. "
            + "Output JSON only — no markdown fences, no commentary, no reasoning.\n"
            + "SCHEMA:\n" + schema
        )
        last_err = None
        for attempt in range(2):
            msgs = [SystemMessage(content=sys), HumanMessage(content=user)]
            resp = _with_backoff(lambda: self._llm.invoke(msgs))
            text = resp.content if hasattr(resp, "content") else str(resp)
            try:
                return model.model_validate(_extract_json(text))
            except Exception as e:  # noqa: BLE001
                last_err = e
                sys += "\n\nYour previous reply was not valid JSON for the schema. Return ONLY the JSON object."
        raise ValueError(f"model did not return schema-valid JSON for {model.__name__}: {last_err}")


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a possibly-noisy model reply (fences, prose, reasoning)."""
    if not text:
        raise ValueError("empty model reply")
    # strip ```json ... ``` fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # otherwise take the outermost {...}
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start:end + 1])
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


def get_llm(settings) -> LLMClient:
    return LangChainLLM(provider=settings.llm_provider, model=settings.llm_model)
