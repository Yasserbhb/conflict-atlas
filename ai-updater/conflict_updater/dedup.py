"""Deterministic candidate finder — the cheap first half of the Resolver.

It narrows the whole base down to a few plausible existing conflicts (by name/alias
overlap, shared actors, and date proximity) so the LLM only reasons over a handful.
Pure Python, no LLM — fully unit-tested."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from .store import BaseConflict
from .schema import CandidateEvent

# \w with re.UNICODE (the default for str patterns) rather than [a-z0-9]. The old class treated
# every non-Latin character as a separator, so an Arabic, Cyrillic or Chinese conflict title
# tokenised to the EMPTY SET and could never match anything — while config/sources.yml lists 65
# outlets across 9 languages. casefold() rather than lower() for the same reason.
_WORD = re.compile(r"\w+")


def _norm(s: str) -> str:
    return " ".join(_WORD.findall((s or "").casefold()))


def _tokens(s: str) -> set[str]:
    return set(_WORD.findall((s or "").casefold()))


def _norm_id(s: str) -> str:
    """Normalised text with the generic words removed, for fuzzy comparison.

    Comparing raw strings scores "Civil war fighting continues" at 0.42 against "Sudan Civil War"
    purely on the shared generic words — enough to put an unrelated Myanmar event on Sudan's
    candidate list. Only the identity-bearing words should decide whether two names are the same
    name."""
    return " ".join(w for w in _WORD.findall((s or "").casefold()) if w not in _EMPTY)


def _year(date: str):
    m = re.match(r"(\d{4})", date or "")
    return int(m.group(1)) if m else None


# A token that carries no identity: it appears in half the conflict titles in the atlas, so
# matching on it is noise. Kept tiny and obvious rather than a real stopword list.
_EMPTY = {
    # what KIND of conflict it is — the atlas has a `type` enum for exactly these, so they say
    # nothing about WHICH conflict. Leaving "genocide" in scored the Gaza War against the Darfur
    # Genocide at 0.50, and "invasion" scored it against Russia's invasion of Ukraine at 0.45.
    "war", "wars", "conflict", "crisis", "civil", "genocide", "invasion", "insurgency",
    "occupation", "uprising", "revolt", "rebellion", "massacre", "campaign", "operation",
    "sanctions", "dispute", "blockade", "intervention", "annexation", "coup",
    # states of affairs, not names
    "violence", "fighting", "hostilities", "unrest", "tensions", "situation",
    "ongoing", "current", "recent", "between",
    # function words, incl. the few languages the source list actually uses
    "the", "a", "an", "of", "in", "and", "at", "on",
    "de", "la", "le", "les", "el", "los", "guerre", "krieg", "война",
}


def clean_name(text: str, max_words: int = 8) -> str:
    """A conflict name lifted from source prose, or "" if there isn't one in there.

    `context` comes from an article, so it arrives as "the Second World War" or, when the model
    over-answers, as a whole clause. Normalising here keeps the alias list usable: an alias that
    is a sentence never matches anything and makes every later comparison slower.

    Rejects anything that is only generic words -- "the ongoing conflict" names nothing, and
    storing it would make every conflict in the atlas look alike.
    """
    t = re.sub(r"^\s*(the|a|an|le|la|les|el|los)\s+", "", (text or "").strip(), flags=re.I)
    t = t.strip().strip(chr(46) + chr(44) + chr(59) + chr(58) + chr(34) + chr(39) + "()[]").strip()
    if not t or len(t.split()) > max_words or len(t) > 70:
        return ""
    return "" if not (_tokens(t) - _EMPTY) else t


def _date_term(conflict: BaseConflict, cand: CandidateEvent, this_year: int) -> float:
    """How plausible this event's date is for this conflict, as a signed adjustment.

    The old version was binary: +0.1 anywhere inside the span, -0.2 anywhere outside, so an event
    one year past the end scored exactly as badly as one three centuries away. Worse, an ongoing
    conflict was given `end = 2100`, which made every date "inside" and the term meaningless for
    precisely the conflicts a daily scan is about.
    """
    y = _year(cand.date)
    if y is None or conflict.start is None:
        return 0.0
    end = conflict.end if conflict.end is not None else max(conflict.start, this_year)
    if conflict.start <= y <= end:
        return 0.12
    gap = conflict.start - y if y < conflict.start else y - end
    if gap <= 2:
        return 0.06                      # just outside — spans in the atlas are year-granular
    if gap <= 15:
        return 0.0                       # plausible neighbourhood, no opinion either way
    return -0.30                         # a different era


def _event_proximity(conflict: BaseConflict, cand: CandidateEvent) -> float:
    """1.0 when this event sits right on top of one the conflict already has, decaying to 0 over
    roughly two years. A conflict's OWN events say more about where it is active than its declared
    span does, and the span is only year-granular anyway."""
    y = _year(cand.date)
    if y is None:
        return 0.0
    years = [_year(e.get("date")) for e in (conflict.events or [])]
    years = [v for v in years if v is not None]
    if not years:
        return 0.0
    gap = min(abs(y - v) for v in years)
    return max(0.0, 1.0 - gap / 2.0)


def score(conflict: BaseConflict, cand: CandidateEvent, this_year: int = 2026) -> float:
    """0..1 similarity between a candidate event and an existing conflict.

    Four signals, none of which the previous version had in usable form:

      * **What the article called it.** `cand.context` is the source's own framing — "the ongoing
        conflict between Israel and Hezbollah" — and it names the parent far more reliably than an
        event headline does. Scored alongside the title, best of the two.
      * **Who is involved.** Previously an actor only counted if its name appeared INSIDE the
        conflict's title, so an event by "United States" scored zero against a conflict called
        "Operation Prosperity Guardian" that lists USA in its parties. `BaseConflict` has carried
        `involved_countries` and `parties` all along; now they are read.
      * **When.** Proximity rather than a binary in-span flag, plus distance to the conflict's own
        nearest event.

    This matters most from a cold start: a conflict founded by one incident is named after that
    incident, so nothing later matches it on the title alone. Context and actors are what let the
    second event find the first.
    """
    names = [n for n in [conflict.title, *conflict.aliases] if n]
    name_tok = set().union(*(_tokens(n) for n in names)) if names else set()
    # Identity tokens only. Without this, every conflict with "War" in its title matches every
    # event that mentions a war.
    name_id = name_tok - _EMPTY

    probes = [p for p in (cand.title, getattr(cand, "context", "") or "", cand.action) if p]
    # Character similarity AND token overlap, because they fail differently: SequenceMatcher rates
    # "world i" against "world ii" at 0.93 (two short strings, one character apart — World War I
    # and World War II are NOT the same war), while token overlap alone misses word-order and
    # spelling variants entirely. Taking the lower of the two on short names kills that case.
    fuzzy = 0.0
    for pr in probes:
        a = _norm_id(pr)
        if not a:
            continue
        for n in names:
            b = _norm_id(n)
            if not b:
                continue
            chars = SequenceMatcher(None, a, b).ratio()
            ta, tb = set(a.split()), set(b.split())
            toks = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
            fuzzy = max(fuzzy, min(chars, toks) if max(len(ta), len(tb)) <= 3 else
                        (chars + toks) / 2)

    cand_tok = _tokens(" ".join([*probes, cand.action, cand.place or "", *cand.actors]))
    overlap = len(cand_tok & name_id) / len(name_id) if name_id else 0.0

    # An actor counts if it shows up in the conflict's names OR in the countries the conflict
    # actually lists. `country_names` is resolved from involvedCountries at load time.
    #
    # SYMMETRIC, not one-way coverage. Every European war involves Germany, France or Britain, so
    # "all of this event's actors appear somewhere in this conflict" was true for dozens of
    # unrelated conflicts at once and swamped every other signal. Jaccard asks the harder question:
    # are these the same belligerents, not merely overlapping ones.
    c_tok = (set().union(*(_tokens(n) for n in conflict.country_names))
             if conflict.country_names else set()) | name_id
    c_tok -= _EMPTY
    a_tok = set().union(*(_tokens(a) for a in cand.actors)) if cand.actors else set()
    a_tok -= _EMPTY
    actor_hit = len(a_tok & c_tok) / len(a_tok | c_tok) if (a_tok | c_tok) else 0.0

    # Name evidence identifies a conflict. Actors and dates only corroborate — an event sharing a
    # belligerent and a decade with a conflict is consistent with it, not evidence that it IS it.
    # Weighted accordingly, or the atlas collapses into whichever conflicts have the most members.
    s = (0.58 * fuzzy
         + 0.18 * overlap
         + 0.14 * actor_hit
         + 0.10 * _event_proximity(conflict, cand))
    return max(0.0, min(1.0, s + _date_term(conflict, cand, this_year)))


def find_candidates(base: list[BaseConflict], cand: CandidateEvent,
                    k: int = 8, floor: float = 0.18):
    """Return up to k (conflict, score) pairs above `floor`, best first.

    Deliberately high-recall. The Resolver decides with a calibrated Choice that has an explicit
    "none of these" option, so a wrong candidate on the list costs one more option to weigh — but a
    MISSING one is unrecoverable: the resolver founds a duplicate conflict and nothing ever merges
    them. k and floor are settings (DEDUP_K / DEDUP_FLOOR) so this can be tuned without a code edit.
    """
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
