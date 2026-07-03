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

    t_settle_days: int = int(_get("T_SETTLE_DAYS", "7"))
    n_min_sources: int = int(_get("N_MIN_SOURCES", "2"))
    auto_approve_confidence: float = float(_get("AUTO_APPROVE_CONFIDENCE", "0.8"))

    seed_json: Path = Path(_get("SEED_JSON", str(_HERE.parent / "src" / "data" / "seed.json")))
    output_dir: Path = Path(_get("OUTPUT_DIR", str(_HERE / "out")))


def load_settings() -> Settings:
    # optional .env support without a hard dependency
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(_HERE / ".env")
    except Exception:
        pass
    return Settings()
