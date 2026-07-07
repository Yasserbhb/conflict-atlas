"""Runtime configuration, read from environment (.env). No secrets in code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent  # the ai-updater/ dir


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    llm_provider: str = _get("LLM_PROVIDER", "openai")
    llm_model: str = _get("LLM_MODEL", "gpt-4o-mini")
    search_backend: str = _get("SEARCH_BACKEND", "tavily")
    search_depth: str = _get("SEARCH_DEPTH", "advanced")            # tavily: basic (1 credit) | advanced (2, fuller)
    search_max_results: int = int(_get("SEARCH_MAX_RESULTS", "12"))  # articles per query (Tavily default is 8)
    geocode_backend: str = _get("GEOCODE_BACKEND", "nominatim")  # nominatim | none

    t_settle_days: int = int(_get("T_SETTLE_DAYS", "7"))
    n_min_sources: int = int(_get("N_MIN_SOURCES", "2"))
    auto_approve_confidence: float = float(_get("AUTO_APPROVE_CONFIDENCE", "0.8"))
    max_candidates: int = int(_get("MAX_CANDIDATES", "0"))  # 0 = no cap; >0 caps per scan (quota)

    # Founding a brand-new conflict is riskier than attaching an event to one that already
    # exists (wrong id/title/type/parties are harder to undo), so it needs a HIGHER bar to
    # auto-approve — not an unconditional human-review flag regardless of evidence quality.
    new_conflict_min_confidence: float = float(_get("NEW_CONFLICT_MIN_CONFIDENCE", "0.9"))
    new_conflict_min_sources: int = int(_get("NEW_CONFLICT_MIN_SOURCES", "3"))

    seed_json: Path = Path(_get("SEED_JSON", str(_HERE.parent / "src" / "data" / "seed.json")))
    output_dir: Path = Path(_get("OUTPUT_DIR", str(_HERE / "out")))
    log_dir: Path = Path(_get("LOG_DIR", str(_HERE / "log")))  # committed weekly digests (not out/)


def load_settings() -> Settings:
    # optional .env support without a hard dependency
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(_HERE / ".env")
    except Exception:
        pass
    # read env HERE, after .env is loaded (dataclass field defaults bind at import — too early)
    return Settings(
        llm_provider=_get("LLM_PROVIDER", "openai"),
        llm_model=_get("LLM_MODEL", "gpt-4o-mini"),
        search_backend=_get("SEARCH_BACKEND", "tavily"),
        search_depth=_get("SEARCH_DEPTH", "advanced"),
        search_max_results=int(_get("SEARCH_MAX_RESULTS", "12")),
        geocode_backend=_get("GEOCODE_BACKEND", "nominatim"),
        t_settle_days=int(_get("T_SETTLE_DAYS", "7")),
        n_min_sources=int(_get("N_MIN_SOURCES", "2")),
        auto_approve_confidence=float(_get("AUTO_APPROVE_CONFIDENCE", "0.8")),
        max_candidates=int(_get("MAX_CANDIDATES", "0")),
        new_conflict_min_confidence=float(_get("NEW_CONFLICT_MIN_CONFIDENCE", "0.9")),
        new_conflict_min_sources=int(_get("NEW_CONFLICT_MIN_SOURCES", "3")),
        seed_json=Path(_get("SEED_JSON", str(_HERE.parent / "src" / "data" / "seed.json"))),
        output_dir=Path(_get("OUTPUT_DIR", str(_HERE / "out"))),
        log_dir=Path(_get("LOG_DIR", str(_HERE / "log"))),
    )
