"""Content-addressed cache for LLM responses.

The pipeline calls the model at temperature 0, so the same (provider, model, system, user)
always means the same answer — which makes the call cacheable, and makes three things possible
that weren't before:

  * **Cheap evaluation.** Re-running a backtest after changing one prompt only pays for the
    calls that actually changed. Without this, every eval run costs a full quota of tokens and
    nobody runs them twice.
  * **Resumability.** A scan that dies halfway doesn't re-pay for the candidates it already
    finished — the replay is free.
  * **Reproducibility.** Two runs over the same window produce the same proposals, which is a
    precondition for trusting any A/B comparison between prompt versions.

SQLite because it's stdlib, survives thousands of entries without an inode explosion, and is a
single file you can delete to invalidate everything.
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key        TEXT PRIMARY KEY,
    provider   TEXT NOT NULL,
    model      TEXT NOT NULL,
    response   TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def cache_key(provider: str, model: str, system: str, user: str) -> str:
    """Hash the full request. The prompt text is part of the key, so editing a prompt
    invalidates exactly the calls that prompt affects and nothing else."""
    h = hashlib.sha256()
    for part in (provider, model, system, user):
        h.update(part.encode("utf-8", "replace"))
        h.update(b"\x00")          # separator, so ("ab","c") and ("a","bc") differ
    return h.hexdigest()


class LLMCache:
    """Tiny key→text store. Misses are normal; every failure mode degrades to 'no cache'."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False so a future thread pool over candidates can share it;
            # every access is already serialized by self._lock.
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.execute(_SCHEMA)
            self._conn.commit()
        except Exception:
            self._conn = None      # unwritable disk shouldn't take the pipeline down

    def get(self, key: str) -> Optional[str]:
        if self._conn is None:
            return None
        try:
            with self._lock:
                row = self._conn.execute(
                    "SELECT response FROM responses WHERE key = ?", (key,)
                ).fetchone()
        except Exception:
            return None
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return row[0]

    def put(self, key: str, provider: str, model: str, response: str) -> None:
        if self._conn is None:
            return
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO responses (key, provider, model, response) VALUES (?,?,?,?)",
                    (key, provider, model, response),
                )
                self._conn.commit()
        except Exception:
            pass                   # a cache write failing is never worth an exception

    @property
    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


class NullCache:
    """Disabled backend — the default for production runs, where every week is new content
    and a cache would only ever miss."""

    hits = 0
    misses = 0

    def get(self, key: str) -> Optional[str]:
        return None

    def put(self, key: str, provider: str, model: str, response: str) -> None:
        pass

    @property
    def stats(self) -> dict:
        return {"hits": 0, "misses": 0, "hit_rate": 0.0}

    def close(self) -> None:
        pass


def get_cache(settings):
    """Same Protocol+factory+Null shape as search/geocode/structured_source."""
    if getattr(settings, "llm_cache", "off") == "on":
        return LLMCache(Path(getattr(settings, "output_dir", ".")) / "llm_cache.sqlite3")
    return NullCache()
