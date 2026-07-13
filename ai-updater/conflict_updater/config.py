"""Runtime configuration, read from environment (.env). No secrets in code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent  # the ai-updater/ dir


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _f(name: str, default: str):
    """A dataclass default whose env lookup runs at Settings() instantiation, not at
    class-definition time — so it sees .env vars loaded by load_settings() beforehand."""
    return field(default_factory=lambda: _get(name, default))


@dataclass(frozen=True)
class Settings:
    llm_provider: str = _f("LLM_PROVIDER", "openai")
    llm_model: str = _f("LLM_MODEL", "gpt-4o-mini")
    search_backend: str = _f("SEARCH_BACKEND", "tavily")
    search_depth: str = _f("SEARCH_DEPTH", "advanced")            # tavily: basic (1 credit) | advanced (2, fuller)
    search_max_results: int = field(default_factory=lambda: int(_get("SEARCH_MAX_RESULTS", "12")))  # articles/query
    geocode_backend: str = _f("GEOCODE_BACKEND", "nominatim")  # nominatim | none

    t_settle_days: int = field(default_factory=lambda: int(_get("T_SETTLE_DAYS", "7")))
    n_min_sources: int = field(default_factory=lambda: int(_get("N_MIN_SOURCES", "2")))
    auto_approve_confidence: float = field(default_factory=lambda: float(_get("AUTO_APPROVE_CONFIDENCE", "0.8")))
    max_candidates: int = field(default_factory=lambda: int(_get("MAX_CANDIDATES", "0")))  # 0 = no cap (quota)

    # Founding a brand-new conflict is riskier than attaching an event to one that already
    # exists (wrong id/title/type/parties are harder to undo), so it needs a HIGHER bar to
    # auto-approve — not an unconditional human-review flag regardless of evidence quality.
    new_conflict_min_confidence: float = field(
        default_factory=lambda: float(_get("NEW_CONFLICT_MIN_CONFIDENCE", "0.9")))
    new_conflict_min_sources: int = field(
        default_factory=lambda: int(_get("NEW_CONFLICT_MIN_SOURCES", "3")))

    seed_json: Path = field(
        default_factory=lambda: Path(_get("SEED_JSON", str(_HERE.parent / "src" / "data" / "seed.json"))))
    output_dir: Path = field(default_factory=lambda: Path(_get("OUTPUT_DIR", str(_HERE / "out"))))
    log_dir: Path = field(default_factory=lambda: Path(_get("LOG_DIR", str(_HERE / "log"))))  # committed digests


def load_settings() -> Settings:
    # optional .env support without a hard dependency
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(_HERE / ".env")
    except Exception:
        pass
    return Settings()
