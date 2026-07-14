"""Per-type lifecycle profiles (config/lifecycle.yml, ARCHITECTURE.md §6). A static config
file, not a swappable backend — no Protocol/factory, just a loader."""
from __future__ import annotations

from pathlib import Path

import yaml


def load_profiles(path: Path) -> dict[str, dict]:
    """{conflict_type: {default_terminal, resolved_requires, dwell_days, regression, ...}}.
    Missing/unparseable file → empty dict (Enrich falls back to its generic wording)."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
