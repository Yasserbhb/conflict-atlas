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


# ---- duplicate / continuation guard --------------------------------------------------------
# A weekly scan rarely saw the same event twice. A daily one does constantly: the same strike is
# reported for days, and an ongoing operation generates near-identical headlines every morning.
# Nothing in merge.apply checked for this — it appended unconditionally — so duplicate prevention
# rested entirely on the Resolver LLM answering "known".
#
# "Continuation" is not a separate concept: it is this same check with a date tolerance instead of
# exact-day equality. That is deliberate. Giving Event a duration would ripple into seed.json and
# the React app for a problem a comparison already solves.

def _title_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def duplicate_of(existing: list[dict], date: str, title: str, kind: str | None = None,
                 continuation_days: int = 3, floor: float = 0.85) -> dict | None:
    """The existing event this one repeats, or None.

    Two bands, because they are different mistakes:
      * **same day** — a straightforward duplicate; titles must match at `floor`.
      * **within `continuation_days`** — the ongoing-operation case. Held to a stricter title
        match AND the same `kind`, so a genuine escalation ("ceasefire" after days of "attack")
        is not swallowed as more of the same.

    Floors are deliberately high. This runs as a precision guard — suppressing a real distinct
    event is worse than letting one through to the Resolver, which gets the same judgement anyway.
    Note `evaluate.same_event` looks similar but is tuned for recall in scoring (0.45/0.6); using
    it here would drop genuinely different same-day events.
    """
    from .dates import as_day
    d = as_day(date)
    for e in existing or []:
        etitle = e.get("title") or ""
        if not etitle:
            continue
        edate = e.get("date")
        if edate == date:
            if _title_ratio(title, etitle) >= floor:
                return e
            continue
        ed = as_day(edate)
        if d is None or ed is None:
            continue
        if abs((d - ed).days) <= continuation_days:
            if _title_ratio(title, etitle) >= max(floor, 0.9) and (kind is None or e.get("kind") == kind):
                return e
    return None
