"""Fold APPROVED proposals into the app's seed.json, coherently.

This is where every case has an explicit rule, and where the dataset invariants
(`involvedCountries == the parties' ids`, severity never silently lowered, a status
only ever changes from the LATEST event, etc.) are enforced. Pure Python, unit-tested.

A proposal is applied only if it is approved (`needs_human == False`) and not held by
the recency gate (`provisional == False`, unless include_provisional). Everything else
stays in the review queue.
"""
from __future__ import annotations

import re
from datetime import date
from .schema import Proposal, Event, Conflict
from .store import date_key, derive_span, default_status

_TERMINAL = {"ended", "resolved"}


def _event_to_app(e: Event, eid: str) -> dict:
    loc = None if e.location is None else {"lat": e.location.lat, "lng": e.location.lng, "label": e.location.label}
    return {
        "id": eid, "date": e.date, "title": e.title, "kind": e.kind, "severity": e.severity,
        "location": loc, "parties": list(e.parties), "description": e.description,
        "sources": [s.url for s in e.sources],
        "independentSources": e.independent_sources, "crossAlignment": e.cross_alignment,
    }


def _conflict_to_app(c: Conflict) -> dict:
    return {
        "id": c.id, "title": c.title, "type": c.type, "severity": c.severity,
        "startDate": c.start_date, "endDate": c.end_date, "ongoing": c.ongoing, "status": c.status,
        "statusHistory": [{"status": h.status, "date": h.date, "eventId": h.event_id} for h in c.status_history],
        "lastCheckedAt": c.last_checked_at,
        "description": c.description,
        "parties": [{"countryId": p.country_id, "role": p.role} for p in c.parties],
        "involvedCountries": list(c.involved_countries),
        "aliases": list(c.aliases), "tags": list(c.tags),
        "events": [_event_to_app(e, e.id or f"{c.id}_e{i + 1}") for i, e in enumerate(c.events)],
    }


def _bump(v: str) -> str:
    parts = (v or "0.0.0").split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except ValueError:
        parts.append("1")
    return ".".join(parts)


def apply(proposals: list[Proposal], seed: dict, *, include_provisional: bool = False):
    """Mutate `seed` in place with the approved proposals. Returns (seed, report)."""
    by_id = {c["id"]: c for c in seed.get("conflicts", [])}
    report: list[str] = []
    applied = 0

    # A "new_conflict" proposal must land BEFORE any "attach" proposal that targets it (a
    # second event for the same not-yet-saved conflict, founded earlier in the same scan) —
    # process founding proposals first regardless of the order they happen to arrive in.
    ordered = sorted(proposals, key=lambda p: 0 if p.kind == "new_conflict" else 1)

    for p in ordered:
        if p.needs_human:
            report.append(f"skip (needs human): {p.event.date} {p.event.title}")
            continue
        if p.provisional and not include_provisional:
            report.append(f"hold (provisional): {p.event.date} {p.event.title}")
            continue

        if p.kind == "attach":
            c = by_id.get(p.target_conflict_id)
            if not c:
                is_pending_new = str(p.target_conflict_id or "").startswith("seed_new_")
                why = "its founding new_conflict proposal wasn't approved" if is_pending_new else "conflict not found"
                report.append(f"skip ({why} — target {p.target_conflict_id}): {p.event.title}")
                continue
            events = c.setdefault("events", [])
            ev = _event_to_app(p.event, f"{c['id']}_e{len(events) + 1}")
            events.append(ev)
            # is this now the most recent event? (only the latest may change current status)
            is_latest = all(date_key(ev["date"]) >= date_key(e.get("date")) for e in events)
            events.sort(key=lambda e: date_key(e.get("date")))

            c["severity"] = max(c.get("severity", 0), p.event.severity)   # never lowered
            inv = c.setdefault("involvedCountries", [])
            for cid in p.event.parties:
                if cid not in inv:
                    inv.append(cid)
            parties = c.setdefault("parties", [])
            have = {pp.get("countryId") for pp in parties}
            for r in p.roles:                                            # add new parties, keep existing roles
                if r.country_id not in have:
                    parties.append({"countryId": r.country_id, "role": r.role})
                    have.add(r.country_id)
            al = c.setdefault("aliases", [])
            for a in p.new_aliases:
                if a not in al:
                    al.append(a)
            if p.status and is_latest and p.status != c.get("status"):    # status changes only from the latest event
                c.setdefault("statusHistory", []).append(
                    {"status": p.status, "date": ev["date"], "eventId": ev["id"]})
                c["status"] = p.status
                c["ongoing"] = p.status not in _TERMINAL
            c["lastCheckedAt"] = date.today().isoformat()                 # touched by this scan, status or not
            # span self-corrects from the (now updated) events + status: an earlier event pulls
            # startDate back; a terminal event closes endDate. Source-stated span is preserved.
            c["startDate"], c["endDate"] = derive_span(
                [e.get("date") for e in events], default_status(c),
                stated_start=c.get("startDate"), stated_end=c.get("endDate"),
            )
            applied += 1
            report.append(f"attach → {c['id']}: {p.event.title}")

        else:  # new_conflict
            if not p.new_conflict:
                report.append("skip (new_conflict has no body)")
                continue
            if p.new_conflict.id in by_id:
                report.append(f"skip (id already exists {p.new_conflict.id})")
                continue
            app = _conflict_to_app(p.new_conflict)
            seed.setdefault("conflicts", []).append(app)
            by_id[app["id"]] = app
            applied += 1
            report.append(f"NEW conflict {app['id']}: {app['title']}")

    if applied:
        seed["version"] = _bump(seed.get("version", "0.0.0"))
    report.insert(0, f"applied {applied}/{len(proposals)}; version → {seed.get('version')}")
    return seed, report


def validate(seed: dict) -> list[str]:
    """Invariants the merged dataset must satisfy. Empty list == coherent."""
    issues: list[str] = []
    for c in seed.get("conflicts", []):
        inv = set(c.get("involvedCountries", []))
        party_ids = {p.get("countryId") for p in c.get("parties", [])}
        if party_ids - inv:
            issues.append(f"{c['id']}: parties {party_ids - inv} missing from involvedCountries")
        for e in c.get("events", []):
            for cid in e.get("parties", []):
                if cid not in inv:
                    issues.append(f"{c['id']}/{e.get('id')}: event party {cid} not in involvedCountries")
            if not re.match(r"^\d{4}(-\d{2}){0,2}$", e.get("date", "")):
                issues.append(f"{c['id']}/{e.get('id')}: bad date {e.get('date')!r}")
            sev = e.get("severity")
            if not (isinstance(sev, int) and 1 <= sev <= 5):
                issues.append(f"{c['id']}/{e.get('id')}: bad severity {sev}")
        if c.get("ongoing") and c.get("status") in _TERMINAL:
            issues.append(f"{c['id']}: ongoing=true but status={c.get('status')}")
    return issues
