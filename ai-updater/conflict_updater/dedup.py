"""Deterministic candidate finder — the cheap first half of the Resolver.

It narrows the whole base down to a few plausible existing conflicts (by name/alias
overlap, shared actors, and date proximity) so the LLM only reasons over a handful.
Pure Python, no LLM — fully unit-tested."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from .store import BaseConflict
from .schema import CandidateEvent

_WORD = re.compile(r"[a-z0-9]+")


def _norm(s: str) -> str:
    return " ".join(_WORD.findall((s or "").lower()))


def _tokens(s: str) -> set[str]:
    return set(_WORD.findall((s or "").lower()))


def _year(date: str):
    m = re.match(r"(\d{4})", date or "")
    return int(m.group(1)) if m else None


def score(conflict: BaseConflict, cand: CandidateEvent) -> float:
    """0..1 similarity between a candidate event and an existing conflict."""
    names = [conflict.title, *conflict.aliases]
    cand_text = " ".join([cand.title, cand.action, cand.place or "", *cand.actors])
    cand_tok = _tokens(cand_text)

    # best fuzzy ratio of the event title against any conflict name/alias
    fuzzy = max((SequenceMatcher(None, _norm(cand.title), _norm(n)).ratio() for n in names), default=0.0)

    # token overlap of the whole candidate text against names
    name_tok = set().union(*(_tokens(n) for n in names)) if names else set()
    overlap = len(cand_tok & name_tok) / len(name_tok) if name_tok else 0.0

    # actor names appearing in the conflict names (e.g. "Israel", "Iran")
    actor_hit = 0.0
    if cand.actors and name_tok:
        hits = sum(1 for a in cand.actors if _tokens(a) & name_tok)
        actor_hit = hits / len(cand.actors)

    s = 0.55 * fuzzy + 0.25 * overlap + 0.20 * actor_hit

    # date plausibility: event should fall within (or just around) the conflict's span
    y = _year(cand.date)
    if y is not None and conflict.start is not None:
        end = conflict.end if conflict.end is not None else 2100
        if conflict.start - 1 <= y <= end + 1:
            s += 0.1
        else:
            s -= 0.2
    return max(0.0, min(1.0, s))


def find_candidates(base: list[BaseConflict], cand: CandidateEvent, k: int = 5, floor: float = 0.25):
    """Return up to k (conflict, score) pairs above `floor`, best first."""
    scored = [(c, score(c, cand)) for c in base]
    scored = [(c, sc) for c, sc in scored if sc >= floor]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
