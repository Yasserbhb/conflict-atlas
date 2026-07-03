# Events model — brainstorm

> **Branch `conflict-events`, off `main`.** Design exploration only — no code yet, nothing that
> touches the deployment. The point: figure out the *best* way to model and **present**
> sub-events before we freeze any schema (app side *and* pipeline side share this shape).

## The core idea

Today a conflict is a paragraph + parties + one severity + one date span. But real conflicts are
made of **events**: WW2 → Pearl Harbor, D-Day, Stalingrad, Hiroshima; Israel–Iran → individual
strikes; the slave trade → phases + abolition milestones.

> **The event is the atomic, sourced unit. A conflict is an aggregation of its events.**
> The conflict's headline `severity` and `status` are **derived** from the event stream.

Why this is powerful and not just more data entry:
- **severity-over-time**, **status history**, **broken ceasefires**, and **per-claim sources**
  stop being four separate lists — they're all just *events of different kinds*.
- It's exactly what the pipeline naturally emits (every ingested item **is** an event).
- It turns the app's flat views into things you can read *through time*.

---

## Data shape (draft — to interrogate)

```jsonc
{
  "id": "seed_wwii",
  "title": "World War II",
  "type": "war",
  "severity": 5,            // DERIVED summary (e.g. max/most-recent of events) — see "derive vs store"
  "status": "ended",        // derived
  "startDate": "1939", "endDate": "1945",
  "events": [
    {
      "id": "evt_...",
      "date": "1941-12-07",           // day / month / year precision all allowed
      "title": "Attack on Pearl Harbor",
      "kind": "attack",               // small controlled vocabulary (below)
      "severity": 4,                  // this event's own intensity
      "location": { "lat": 21.36, "lng": -157.95, "label": "Pearl Harbor, Hawaii" },
      "parties": ["JPN", "USA"],      // optional; subset of the conflict's parties
      "description": "...",
      "sources": ["https://..."]      // sources attach at the EVENT level
    }
  ]
}
```

**Event `kind` vocabulary (first pass):**
`attack` · `battle` · `offensive` · `atrocity/massacre` · `displacement` · `ceasefire` ·
`treaty/settlement` · `escalation` · `intervention` · `sanction` · `annexation` · `milestone`.
Each gets an icon + color. Some map to lifecycle transitions (ceasefire → `suspended`,
treaty → `resolved`) — so events and the status machine reinforce each other.

**Location matters:** events happen *somewhere specific*, often not the conflict's country set
(Pearl Harbor is in the US, but it's a JPN attack). This is what unlocks map pins. Precision
varies — some events are a city (lat/lng), some just a country, some none. Model it as optional.

### Derive vs store the summary
Two options for the headline `severity`/`status`:
- **A. Pure-derive** — compute from events on the fly. Cleanest truth, but conflicts with zero
  events need a fallback.
- **B. Store + override** — keep a stored summary (what we have now), let events *inform/suggest*
  it, allow manual override. Backwards-compatible.
- **Leaning B**: store the summary (so all 238 existing conflicts keep working untouched), and
  when a conflict *has* events, show the derived curve alongside. Graceful.

---

## Presentation brainstorm

### 1. Conflict detail = a narrative timeline  *(highest value / lowest cost)*
Turn the detail panel from a blurb into a story:
- **Intensity sparkline** at the top — severity over the lifespan, one glance at the arc.
- **Vertical event timeline** — each event a row: `date · kind-icon · title`, expand for
  description + *its own* sources.
- Existing parties / tags / sources stay below.

### 2. Map pins + timeline animation  *(the wow feature)*
- When a conflict is open, plot its events as **pins at their real coordinates**.
- Couple to the timeline: **scrub/play → events appear at their date + place.** WW2 becomes a
  war *spreading across the map*, not a static block of red.
- Pin color by `kind` or `severity`; hover → the event; click → scroll the detail timeline to it.

### 3. Global Timeline view goes macro → micro
- Keep the per-year histogram as the big picture.
- Selecting a conflict overlays **its events as ticks** on the axis; scrubbing highlights the
  active one.

### Wilder ideas (park for later)
- **"Play" a single conflict** — a mini play button that animates just this conflict's events on
  the map, start to finish.
- **Event density heat** on the timeline (where in history events cluster).
- **Cross-conflict event search** — "show every `atrocity` event in 1944."
- **Country event feed** — a country panel tab listing its events across all conflicts, chrono.

---

## Backfill — how we avoid boiling the ocean
- **Graceful degradation:** a conflict with **no events** renders exactly like today (summary
  only). Events are purely additive — nothing breaks.
- **Pipeline fills the future:** every item the AI updater ingests becomes an event, so ongoing
  conflicts accrue events automatically once that's live.
- **Marquee by hand/AI:** seed a *few* key events for the handful of famous conflicts (WW2, the
  big ones) to make the feature sing in demos. Everything else stays summary-only until it earns
  events.

---

## Pipeline tie-in (shared schema)
This is the same `events[]` the [`ai-updater`](../ai-updater/ARCHITECTURE.md) pipeline produces.
Decide the event shape **once**, here, before Phase 1 of the pipeline freezes its proposal/state
schemas. The pipeline's "regression / broken ceasefire" is literally *a new event*; its
`severityHistory` is *the events with a severity*. One model, two producers (human edits + AI).

---

## Open questions to settle before building
1. **Derive vs store** the headline severity/status? (leaning *store + override*)
2. **Event `kind`** list — is the first-pass vocabulary right? Which get map icons?
3. **Location precision** — require coordinates, or allow country-only / none?
4. **How many events** before we truncate the detail timeline (progressive disclosure)?
5. **Editing** — does Edit mode gain an event editor now, or later?
6. Do events need their own **parties/roles**, or inherit the conflict's?

## Suggested build order (when we say go)
1. Add `events[]` to the schema + seed a few for 2–3 marquee conflicts.
2. **Intensity sparkline + event list** in the conflict detail (cheap, big readability win).
3. **Map pins + timeline animation** (the showpiece).
4. Timeline-view integration + Edit-mode event editor.
