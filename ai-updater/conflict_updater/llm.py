"""LLM client abstraction. Agents depend on this interface, not on any provider —
so the provider is swappable and tests inject a fake.
"""
from __future__ import annotations

from typing import Protocol, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def structured(self, model: Type[T], system: str, user: str) -> T:
        """Return an instance of `model`, filled by the LLM from system+user prompts."""
        ...


class LangChainLLM:
    """Real backend. LangChain is imported lazily so importing this module (and running
    the offline tests) needs no provider installed."""

    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini", temperature: float = 0.0):
        if provider == "openai":
            from langchain_openai import ChatOpenAI  # lazy
            self._llm = ChatOpenAI(model=model, temperature=temperature)
        elif provider in ("google", "gemini"):
            from langchain_google_genai import ChatGoogleGenerativeAI  # lazy; reads GOOGLE_API_KEY
            self._llm = ChatGoogleGenerativeAI(model=model, temperature=temperature)
        else:
            raise ValueError(f"unknown LLM_PROVIDER={provider!r}; wire it in llm.py")

    def structured(self, model: Type[T], system: str, user: str) -> T:
        from langchain_core.messages import SystemMessage, HumanMessage  # lazy
        chain = self._llm.with_structured_output(model)
        return chain.invoke([SystemMessage(content=system), HumanMessage(content=user)])


def get_llm(settings) -> LLMClient:
    return LangChainLLM(provider=settings.llm_provider, model=settings.llm_model)
