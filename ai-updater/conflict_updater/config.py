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
    # The coverage ledger lives in the TRACKED app data, not in the gitignored out/ dir.
    # It used to be written to out/coverage.json and copied into src/data at commit time, which
    # silently destroyed it: out/ is gitignored, so a CI checkout starts with no ledger,
    # load_coverage() returns [], and the run publishes a one-row file over the whole history.
    # It is also the state a day-cursor reads to know which days are already done, so it has to
    # survive between runs.
    coverage_json: Path = field(
        default_factory=lambda: Path(_get("COVERAGE_JSON", str(_HERE.parent / "src" / "data" / "coverage.json"))))
    lifecycle_yml: Path = field(
        default_factory=lambda: Path(_get("LIFECYCLE_YML", str(_HERE / "config" / "lifecycle.yml"))))
    sources_yml: Path = field(
        default_factory=lambda: Path(_get("SOURCES_YML", str(_HERE / "config" / "sources.yml"))))
    structured_source_backend: str = _f("STRUCTURED_SOURCE_BACKEND", "none")  # none | ucdp
    # Cache LLM responses by prompt hash. Off for weekly runs (every week is new content, so
    # it would only ever miss); on for evaluation and backtests, where the same prompts are
    # replayed constantly and re-paying for them makes measurement too expensive to repeat.
    llm_cache: str = _f("LLM_CACHE", "off")  # off | on

    # ---- daily cursor + duplicate guard ----
    # The unit of work is one day. The cursor walks forward from this date, skipping days the
    # coverage ledger already records as checked.
    pipeline_start_date: str = _f("PIPELINE_START_DATE", "2026-01-01")
    # Days processed per run. 1 keeps pace once current; raise to drain a backlog, bounded by
    # quota (each day costs roughly 2 + 3 x --limit LLM calls).
    pipeline_max_days_per_run: int = field(default_factory=lambda: int(_get("PIPELINE_MAX_DAYS_PER_RUN", "1")))
    # After this many inconclusive attempts a day is left behind, so one permanently
    # un-searchable date cannot stall every day queued behind it.
    coverage_max_attempts: int = field(default_factory=lambda: int(_get("COVERAGE_MAX_ATTEMPTS", "3")))
    # An event within this many days of an existing one, with a near-identical title and the same
    # kind, is the same continuing operation rather than a new event.
    continuation_days: int = field(default_factory=lambda: int(_get("CONTINUATION_DAYS", "3")))
    duplicate_title_floor: float = field(default_factory=lambda: float(_get("DUPLICATE_TITLE_FLOOR", "0.85")))
    # Minimum historical CONSEQUENCE (not violence) for an event to be applied without review.
    # significance and severity are different fields: a ceasefire is severity 1, significance 5.
    min_significance_auto: int = field(default_factory=lambda: int(_get("MIN_SIGNIFICANCE_AUTO", "3")))


def load_settings() -> Settings:
    # optional .env support without a hard dependency
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(_HERE / ".env")
    except Exception:
        pass
    return Settings()
