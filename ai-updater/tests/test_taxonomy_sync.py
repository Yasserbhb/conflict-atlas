"""Catches taxonomy drift between the pipeline's schema.py and the app's source-of-truth JS
files — the exact bug class CHANGELOG.md documents (a stray `funding` type existing in one
place but not the other). Regex key-extraction is enough for these small, hand-authored,
consistently-formatted object literals — not a general JS parser."""
from __future__ import annotations

import re
import typing
from pathlib import Path

from conflict_updater.schema import ConflictType, Role, EventKind, Status

_APP_SRC = Path(__file__).resolve().parent.parent.parent / "src"


def _js_object_keys(js_text: str, const_name: str) -> set[str]:
    """Extract the top-level string keys of `export const <const_name> = { ... };`."""
    m = re.search(rf"export const {const_name} = \{{(.*?)\n\}};", js_text, re.S)
    assert m, f"could not find `export const {const_name}` block"
    body = m.group(1)
    return set(re.findall(r"^\s*(\w+):", body, re.M))


def _read(path: str) -> str:
    return (_APP_SRC / path).read_text(encoding="utf-8")


def test_conflict_type_matches_taxonomy_js():
    keys = _js_object_keys(_read("utils/taxonomy.js"), "TYPE_DEFINITIONS")
    assert set(typing.get_args(ConflictType)) == keys


def test_role_matches_taxonomy_js():
    keys = _js_object_keys(_read("utils/taxonomy.js"), "ROLE_DEFINITIONS")
    assert set(typing.get_args(Role)) == keys


def test_event_kind_matches_taxonomy_js():
    keys = _js_object_keys(_read("utils/taxonomy.js"), "KIND_DEFINITIONS")
    assert set(typing.get_args(EventKind)) == keys


def test_status_matches_taxonomy_js():
    keys = _js_object_keys(_read("utils/taxonomy.js"), "STATUS_DEFINITIONS")
    assert set(typing.get_args(Status)) == keys


def test_conflict_type_matches_conflict_colors_js():
    # This is where the real, live `funding` drift sat (CHANGELOG v1.16.0) — TYPE_LABELS is the
    # map actually consumed by the map/side-panel UI, so it must stay in lockstep with schema.py too.
    keys = _js_object_keys(_read("utils/conflictColors.js"), "TYPE_LABELS")
    assert set(typing.get_args(ConflictType)) == keys


def test_role_matches_conflict_colors_js():
    keys = _js_object_keys(_read("utils/conflictColors.js"), "ROLE_LABELS")
    assert set(typing.get_args(Role)) == keys
