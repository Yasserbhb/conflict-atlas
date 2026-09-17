"""Backtest the pipeline against the atlas it already has.

`seed.json` holds 489 hand-curated, fully-sourced events. That is a labelled evaluation set
that cost nothing to produce — so pipeline quality is measurable today, without annotating
anything new.

The method: pick a window, **remove** every event dated inside it from the base the pipeline
reads, run a scan over that window, and compare what comes back against what was removed.

Two things make or break the honesty of the numbers, and both are handled here:

  * **Hold-out is mandatory.** If the gold events are still in the base, the Resolver correctly
    answers "known" and drops them, and the run measures nothing at all. `prune()` takes them
    out, and drops any conflict left with no events (which would otherwise hand the pipeline a
    free attach target it did not have to earn).
  * **Expectations differ per event.** An event whose conflict survives pruning should be
    ATTACHED to that conflict; one whose conflict vanished entirely should found a NEW one.
    Scoring the two identically would punish the pipeline for being right.

What this measures well: resolution and enrichment. What it measures only loosely: extraction
on historical windows, because searching the web today for 1962 returns retrospective
encyclopaedia coverage rather than contemporaneous reporting. Recent windows are the honest
test of the full weekly path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional


from .dates import in_window, span as _span  # single source of date meaning

_WORD = re.compile(r"[a-z0-9]+")


def _norm(s: str) -> str:
    return " ".join(_WORD.findall((s or "").lower()))


def _year(d: str) -> Optional[str]:
    m = re.match(r"(\d{4})", str(d or ""))
    return m.group(1) if m else None


@dataclass
class GoldEvent:
    conflict_id: str
    conflict_title: str
    date: str
    title: str
    kind: Optional[str] = None
    severity: Optional[int] = None
    # "attach" if the parent conflict survives pruning, "new" if it was removed entirely.
    expected_decision: str = "attach"


@dataclass
class Scored:
    gold: list[GoldEvent] = field(default_factory=list)
    matched: list[tuple] = field(default_factory=list)      # (GoldEvent, Proposal)
    missed: list[GoldEvent] = field(default_factory=list)
    spurious: list = field(default_factory=list)            # proposals matching no gold event



def extract_gold(seed: dict, start: str, end: str) -> list[GoldEvent]:
    out: list[GoldEvent] = []
    for c in seed.get("conflicts", []):
        for e in c.get("events", []) or []:
            if e.get("date") and in_window(e["date"], start, end):
                out.append(GoldEvent(
                    conflict_id=c["id"], conflict_title=c.get("title", ""),
                    date=e["date"], title=e.get("title", ""),
                    kind=e.get("kind"), severity=e.get("severity"),
                ))
    return out


def prune(seed: dict, start: str, end: str) -> tuple[dict, list[GoldEvent]]:
    """Return (seed without the in-window events, gold events with expectations set)."""
    import copy
    pruned = copy.deepcopy(seed)
    gold = extract_gold(seed, start, end)

    survivors = {}
    kept_conflicts = []
    for c in pruned.get("conflicts", []):
        before = c.get("events", []) or []
        after = [e for e in before if not (e.get("date") and in_window(e["date"], start, end))]
        if before and not after:
            continue                       # conflict existed only inside the window — drop it
        c["events"] = after
        kept_conflicts.append(c)
        survivors[c["id"]] = True
    pruned["conflicts"] = kept_conflicts

    for g in gold:
        g.expected_decision = "attach" if survivors.get(g.conflict_id) else "new"
    return pruned, gold


def same_event(gold: GoldEvent, ev, title_floor: float = 0.45) -> bool:
    """A proposal event matches a gold event when the dates agree to the precision both carry
    and the titles are recognisably the same. Deliberately lenient on wording — the pipeline
    writes its own headline and will never reproduce a curator's phrasing verbatim."""
    gy, ey = _year(gold.date), _year(getattr(ev, "date", ""))
    if not gy or not ey or gy != ey:
        return False
    gp, ep = str(gold.date).split("-"), str(ev.date).split("-")
    if len(gp) >= 2 and len(ep) >= 2 and gp[1] != ep[1]:
        return False                        # both state a month and they disagree
    a, b = _norm(gold.title), _norm(getattr(ev, "title", ""))
    if not a or not b:
        return False
    if SequenceMatcher(None, a, b).ratio() >= title_floor:
        return True
    ta, tb = set(a.split()), set(b.split())
    return bool(ta and tb) and len(ta & tb) / min(len(ta), len(tb)) >= 0.6


def score(result, gold: list[GoldEvent]) -> dict:
    """Per-stage metrics for one backtest run."""
    s = Scored(gold=list(gold))
    unmatched = list(result.proposals)

    for g in gold:
        hit = next((p for p in unmatched if same_event(g, p.event)), None)
        if hit is None:
            s.missed.append(g)
        else:
            unmatched.remove(hit)
            s.matched.append((g, hit))
    s.spurious = unmatched

    tp, fn, fp = len(s.matched), len(s.missed), len(s.spurious)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # Resolution: did it attach to the right conflict / correctly decide to found a new one?
    res_right = 0
    for g, p in s.matched:
        got = "new" if p.kind == "new_conflict" else "attach"
        if got != g.expected_decision:
            continue
        if got == "attach" and p.target_conflict_id != g.conflict_id:
            continue                        # right call, wrong conflict
        res_right += 1

    # Enrichment: compare the fields a curator also recorded.
    kind_n = kind_right = sev_n = sev_close = 0
    for g, p in s.matched:
        if g.kind:
            kind_n += 1
            kind_right += int(p.event.kind == g.kind)
        if g.severity is not None and p.event.severity is not None:
            sev_n += 1
            sev_close += int(abs(p.event.severity - g.severity) <= 1)

    return {
        "gold": len(gold),
        "proposed": len(result.proposals),
        "matched": tp, "missed": fn, "spurious": fp,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "resolution_accuracy": round(res_right / tp, 3) if tp else None,
        "kind_accuracy": round(kind_right / kind_n, 3) if kind_n else None,
        "severity_within_1": round(sev_close / sev_n, 3) if sev_n else None,
        "calibration": calibration(s.matched, s.spurious),
        "scan_failed": len(getattr(result, "failed", [])),
    }


def calibration(matched: list[tuple], spurious: list) -> list[dict]:
    """Does a stated confidence of 0.8 actually mean right 80% of the time?

    The whole auto-approve gate is `confidence >= auto_approve_confidence`, and nothing has
    ever checked whether that number is meaningful. A matched proposal counts as correct, a
    spurious one as incorrect; bucketing by stated confidence shows over/under-confidence
    directly. Compare `observed` against the bucket midpoint — a well-calibrated model tracks
    the diagonal.
    """
    buckets = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    rows = []
    scored = [(p, True) for _, p in matched] + [(p, False) for p in spurious]
    for lo, hi in buckets:
        in_b = [(p, ok) for p, ok in scored
                if p.verify is not None and lo <= p.verify.confidence < hi]
        if not in_b:
            continue
        correct = sum(1 for _, ok in in_b if ok)
        rows.append({
            "range": f"{lo:.2f}-{min(hi, 1.0):.2f}",
            "n": len(in_b),
            "stated_mid": round((lo + min(hi, 1.0)) / 2, 2),
            "observed": round(correct / len(in_b), 3),
        })
    return rows


def render(period: str, m: dict) -> str:
    """Human-readable report."""
    L = [f"Backtest {period}", "=" * (9 + len(period)), ""]
    L.append(f"  gold events in window : {m['gold']}")
    L.append(f"  proposals produced    : {m['proposed']}")
    if m["scan_failed"]:
        L.append(f"  candidates that errored: {m['scan_failed']}")
    L.append("")
    L.append(f"  extraction   precision {m['precision']:.3f}  recall {m['recall']:.3f}  F1 {m['f1']:.3f}")
    L.append(f"               matched {m['matched']}  missed {m['missed']}  spurious {m['spurious']}")
    for label, key in (("resolution   accuracy ", "resolution_accuracy"),
                       ("event kind   accuracy ", "kind_accuracy"),
                       ("severity     within ±1", "severity_within_1")):
        v = m[key]
        L.append(f"  {label} {'n/a' if v is None else f'{v:.3f}'}")
    if m["calibration"]:
        L += ["", "  Verify calibration (stated vs observed):",
              "    range        n   stated   observed"]
        for r in m["calibration"]:
            flag = ""
            if r["n"] >= 5:
                gap = r["observed"] - r["stated_mid"]
                flag = "  << overconfident" if gap < -0.15 else ("  << underconfident" if gap > 0.15 else "")
            L.append(f"    {r['range']}  {r['n']:>3}   {r['stated_mid']:.2f}     {r['observed']:.3f}{flag}")
    return "\n".join(L)
