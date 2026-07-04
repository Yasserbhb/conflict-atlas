"""scan(period, region?, topic?) — the one operation. Human-typed or cron-supplied,
a week or a century: same path. Returns proposals; a human approves the uncertain ones.
"""
from __future__ import annotations

import re
from datetime import date

from .config import Settings, load_settings
from .llm import LLMClient, get_llm
from .search import SearchClient, get_search
from .store import BaseConflict, load_base
from . import agents, dedup
from .schema import (
    ScanRequest, ScanResult, Proposal, Event, Source, Conflict, RawItem, CandidateEvent,
)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:40] or "unnamed"


def _year(d: str):
    m = re.match(r"(\d{4})", d or "")
    return m.group(1) if m else None


def _is_recent(d: str, days: int) -> bool:
    parts = (d or "").split("-")
    try:
        if len(parts) == 3:
            dt = date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif len(parts) == 2:
            dt = date(int(parts[0]), int(parts[1]), 1)
        else:
            return False  # year-only → not "breaking news"
        return (date.today() - dt).days <= days
    except Exception:
        return False


def _dedupe_items(items: list[RawItem]) -> list[RawItem]:
    seen, out = set(), []
    for it in items:
        if it.url and it.url not in seen:
            seen.add(it.url)
            out.append(it)
    return out


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", (s or "").lower())}


def _gather_sources(cand: CandidateEvent, items: list[RawItem]) -> list[Source]:
    """Attach EVERY fetched item that corroborates this event (not just the one it was
    extracted from), carrying outlet/lang/alignment — so the fact-checker can actually count
    independent, cross-language sources instead of seeing a single URL."""
    want = set(cand.source_urls or [])
    toks = _tokens(f"{cand.title} {cand.action} {' '.join(cand.actors)} {cand.place or ''}")
    yr = _year(cand.date)
    out: list[Source] = []
    seen: set[str] = set()
    for it in items:
        if not it.url or it.url in seen:
            continue
        take = it.url in want
        if not take:
            overlap = len(toks & _tokens(f"{it.title} {it.snippet}"))
            yr_ok = yr is None or yr in f"{it.title} {it.snippet} {it.date or ''}"
            take = overlap >= 3 and yr_ok
        if take:
            seen.add(it.url)
            out.append(Source(url=it.url, outlet=it.outlet, lang=it.lang, alignment=it.alignment))
    for u in want:  # never drop the extractor's own citations
        if u not in seen:
            out.append(Source(url=u))
            seen.add(u)
    return out[:8]


def _is_latest_event(cand: CandidateEvent, parent) -> bool:
    """True if this event is the most recent in its conflict — only then may it move status."""
    if not parent or not parent.events:
        return True
    return (cand.date or "") >= max((e.get("date") or "") for e in parent.events)


def scan(req: ScanRequest, *, llm: LLMClient, search: SearchClient,
         base: list[BaseConflict], settings: Settings) -> ScanResult:
    by_id = {c.id: c for c in base}

    # 1. SCOPER — window → queries (multi-language) + which existing conflicts to re-check
    plan = agents.scoper(llm, req, [c.id for c in base])

    # 2. FETCHER — run the queries
    items: list[RawItem] = []
    for q in plan.queries:
        items.extend(search.search(q.query, q.lang))
    items = _dedupe_items(items)

    # 3. EXTRACTOR — items → discrete candidate events
    cands = agents.extractor(llm, items, req).events
    if settings.max_candidates and len(cands) > settings.max_candidates:
        cands = cands[: settings.max_candidates]

    proposals: list[Proposal] = []
    dropped: list[str] = []

    for i, cand in enumerate(cands, 1):
        print(f"  [{i}/{len(cands)}] {cand.date} {cand.title[:60]}")
        # 4. RESOLVER — dedup lookup (code) then decide (LLM)
        candidates = dedup.find_candidates(base, cand)
        res = agents.resolver(llm, cand, candidates)

        if res.decision == "known":
            dropped.append(f"already known: {cand.date} {cand.title}")
            continue

        is_new = res.decision == "new"
        target_id = res.conflict_id if not is_new else None
        ambiguous = res.decision == "ambiguous"

        # 5. RECENCY gate (per event, by its date)
        provisional = _is_recent(cand.date, settings.t_settle_days)

        # 6. ENRICHERS  (parent context keeps type/roles consistent; not re-derived per event)
        parent = by_id.get(target_id) if not is_new else None
        parent_type = parent.type if parent else None

        cls = agents.classifier(llm, cand, is_new, parent_type=parent_type)
        sev = agents.severity(llm, cand, items)
        rls = agents.roles(llm, cand, parent_type=parent_type,
                           parent_parties=(parent.parties if parent else None))
        geo = agents.geolocator(llm, cand)
        summ = agents.summarizer(llm, cand, items)

        # LIFECYCLE — only the latest event (or a new conflict) may set status; a backfilled
        # old event keeps the conflict's current status (and skips the call entirely).
        current_status = parent.status if parent else None
        if is_new or _is_latest_event(cand, parent):
            life = agents.lifecycle(
                llm, cand, cls.conflict_type or parent_type, current_status,
                today=date.today().isoformat(),
                conflict_start=(parent.start if parent else None),
                conflict_end=(parent.end if parent else None),
            )
            status = life.status
        else:
            status = current_status  # backfill: don't touch (or ask about) the current status

        event = Event(
            id=None,
            date=cand.date,
            title=cand.title,
            kind=cls.event_kind,
            severity=sev.severity,
            location=geo.location,
            parties=[p.country_id for p in rls.parties],
            description=summ.text,
            sources=_gather_sources(cand, items),
        )

        # 7. FACT-CHECK (anti-bias corroboration)
        fc = agents.factcheck(llm, event, items)

        # 8. RECONCILER
        rec = agents.reconciler(llm, event, fc, is_new)

        needs_human = (
            ambiguous
            or is_new                                  # new conflicts are always human-checked
            or rec.decision == "needs_human"
            or fc.verdict != "pass"
            or fc.confidence < settings.auto_approve_confidence
        )

        new_conflict = None
        if is_new:
            y = _year(cand.date) or str(req.period_start)
            new_conflict = Conflict(
                id=f"seed_new_{_slug(cand.title)}",
                title=cand.title,               # provisional — a human renames on review
                type=cls.conflict_type or "war",
                severity=sev.severity,
                start_date=y,
                ongoing=status not in ("ended", "resolved"),
                status=status,
                description=summ.text,
                parties=rls.parties,
                involved_countries=[p.country_id for p in rls.parties],
                aliases=res.new_aliases,
                events=[event],
            )

        proposals.append(Proposal(
            kind="new_conflict" if is_new else "attach",
            target_conflict_id=target_id,
            event=event,
            roles=rls.parties,
            status=status,
            new_conflict=new_conflict,
            new_aliases=res.new_aliases,
            factcheck=fc,
            reconcile=rec,
            needs_human=needs_human,
            provisional=provisional,
        ))

    stats = {
        "queries": len(plan.queries),
        "items": len(items),
        "candidates": len(cands),
        "proposals": len(proposals),
        "auto_approved": sum(1 for p in proposals if not p.needs_human),
        "needs_human": sum(1 for p in proposals if p.needs_human),
        "dropped": len(dropped),
    }
    return ScanResult(request=req, proposals=proposals, dropped=dropped, stats=stats)


def run(period_start: str, period_end: str, region=None, topic=None) -> ScanResult:
    """Convenience wrapper that loads settings/base/llm/search from the environment."""
    settings = load_settings()
    req = ScanRequest(period_start=period_start, period_end=period_end, region=region, topic=topic)
    base = load_base(settings.seed_json)
    return scan(req, llm=get_llm(settings), search=get_search(settings), base=base, settings=settings)
