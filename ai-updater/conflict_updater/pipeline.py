"""scan(period, region?, topic?) — the one operation. Human-typed or cron-supplied,
a week or a century: same path. Returns proposals; a human approves the uncertain ones.
"""
from __future__ import annotations

import re
from datetime import date

from .config import Settings, load_settings
from .llm import LLMClient, get_llm
from .search import SearchClient, get_search
from .geocode import GeocodeClient, get_geocode
from .store import BaseConflict, load_base, pending_to_base, date_key, derive_span
from . import agents, dedup
from .schema import (
    ScanRequest, ScanResult, Proposal, Event, Source, Conflict, RawItem, CandidateEvent,
)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:40] or "unnamed"


def _unique_new_id(title: str, *taken) -> str:
    """A `seed_new_<slug>` id guaranteed not to collide with any existing or pending conflict,
    so two same-scan foundings whose titles slugify identically don't share an id (which would
    make the merger silently drop the second one's event)."""
    base_id = f"seed_new_{_slug(title)}"
    def used(cid): return any(cid in t for t in taken)
    if not used(base_id):
        return base_id
    n = 2
    while used(f"{base_id}_{n}"):
        n += 1
    return f"{base_id}_{n}"


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
    return date_key(cand.date) >= max(date_key(e.get("date")) for e in parent.events)


def scan(req: ScanRequest, *, llm: LLMClient, search: SearchClient,
         base: list[BaseConflict], settings: Settings,
         geocode: GeocodeClient | None = None) -> ScanResult:
    geocode = geocode or get_geocode(settings)
    by_id = {c.id: c for c in base}
    # New conflicts founded EARLIER IN THIS SCAN aren't in `base` yet (that only reflects
    # seed.json as of scan start) — track a BaseConflict view of each so a second event for
    # the same undeclared conflict attaches to the first instead of spawning a duplicate.
    pending_bases: dict[str, BaseConflict] = {}

    # 1. SCOPER — window → queries (multi-language) + which existing conflicts to re-check
    plan = agents.scoper(llm, req, [c.id for c in base])

    # 2. FETCHER — run the queries
    items: list[RawItem] = []
    for q in plan.queries:
        items.extend(search.search(q.query, q.lang))
    items = _dedupe_items(items)

    # 3. EXTRACTOR — items → discrete candidate events, most consequential first so a
    #    --limit cap keeps the important events (a revolt), not the footnotes (a decree).
    cands = agents.extractor(llm, items, req).events
    cands.sort(key=lambda c: c.significance, reverse=True)
    if settings.max_candidates and len(cands) > settings.max_candidates:
        cands = cands[: settings.max_candidates]

    proposals: list[Proposal] = []
    dropped: list[str] = []

    for i, cand in enumerate(cands, 1):
        print(f"  [{i}/{len(cands)}] {cand.date} {cand.title[:60]}")
        # 4. RESOLVER — dedup lookup (code) then decide (LLM). Pending new conflicts from
        # earlier in this same scan are included so a follow-up event attaches to them.
        pool = base + list(pending_bases.values())
        candidates = dedup.find_candidates(pool, cand)
        res = agents.resolver(llm, cand, candidates)

        if res.decision == "known":
            dropped.append(f"already known: {cand.date} {cand.title}")
            continue

        is_new = res.decision == "new" or (
            res.decision == "attach"
            and res.conflict_id not in by_id and res.conflict_id not in pending_bases
        )
        target_id = res.conflict_id if not is_new else None
        ambiguous = res.decision == "ambiguous"

        # 5. RECENCY gate (per event, by its date)
        provisional = _is_recent(cand.date, settings.t_settle_days)

        # 6. ENRICHERS  (parent context keeps type/roles consistent; not re-derived per event)
        # target_id may point at a conflict already in seed.json OR one founded earlier in
        # this same scan (pending) — both are equally valid "parents" for context purposes.
        if is_new:
            parent = None
        elif target_id in pending_bases:
            parent = pending_bases[target_id]
        else:
            parent = by_id.get(target_id)
        parent_type = parent.type if parent else None

        cls = agents.classifier(llm, cand, is_new, parent_type=parent_type)
        sev = agents.severity(llm, cand, items)
        rls = agents.roles(llm, cand, parent_type=parent_type,
                           parent_parties=(parent.parties if parent else None))
        geo = agents.geolocator(llm, cand)
        location = geo.location
        if location and location.label:
            # Real lookup, not model memory: an LLM recalls famous cities accurately but
            # silently collapses smaller/specific places to "the nearest big place it
            # remembers" (verified live — see geocode.py). A geocoder looks it up instead.
            real = geocode.lookup(location.label)
            if real:
                location = real
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
            location=location,
            parties=[p.country_id for p in rls.parties],
            description=summ.text,
            sources=_gather_sources(cand, items),
        )

        # 7. FACT-CHECK (anti-bias corroboration)
        fc = agents.factcheck(llm, event, items)

        # 8. RECONCILER
        rec = agents.reconciler(llm, event, fc, is_new)

        if ambiguous:
            needs_human = True
        elif is_new:
            # Founding a brand-new conflict is riskier than attaching to one that already
            # exists — wrong id/title/type/parties are harder to undo later. So it needs a
            # HIGHER, but not infinite, bar: strong multi-source, cross-aligned corroboration
            # can still auto-create; anything thinner goes to a human. Not an absolute block.
            strongly_corroborated = (
                fc.verdict == "pass"
                and fc.confidence >= settings.new_conflict_min_confidence
                and fc.independent_sources >= settings.new_conflict_min_sources
                and fc.cross_alignment
            )
            needs_human = (not strongly_corroborated) or rec.decision == "needs_human"
        else:
            needs_human = (
                rec.decision == "needs_human"
                or fc.verdict != "pass"
                or fc.confidence < settings.auto_approve_confidence
            )

        new_conflict = None
        if is_new:
            sp = agents.span(llm, cand, items)          # read the conflict's stated span from sources
            if sp.end_date and status not in ("ended", "resolved"):
                status = "ended"                        # sources show the conflict concluded
            start_date, end_date = derive_span([event.date], status, sp.start_date, sp.end_date)
            new_conflict = Conflict(
                id=_unique_new_id(cand.title, by_id, pending_bases),
                title=cand.title,               # provisional — a human renames on review
                type=cls.conflict_type or "war",
                severity=sev.severity,
                start_date=start_date,          # earliest of the sourced span and the events
                end_date=end_date,
                ongoing=status not in ("ended", "resolved"),
                status=status,
                description=summ.text,
                parties=rls.parties,
                involved_countries=[p.country_id for p in rls.parties],
                aliases=res.new_aliases,
                events=[event],
            )
            # visible (as a BaseConflict) to later candidates in this same scan
            pending_bases[new_conflict.id] = pending_to_base(new_conflict)

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
