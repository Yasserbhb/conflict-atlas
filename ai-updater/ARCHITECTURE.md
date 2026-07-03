# AI Updater — Architecture

> Multi-agent pipeline that keeps the Conflict Atlas dataset current **and** trustworthy.
> Deterministic code does the cheap, certain work (fetch, shape, age, dedup, merge). LLM
> agents do **only judgment**, each in a narrow lane. A human approves every merge.

This document is the design of record. Per-agent contracts live in [`agents/`](agents/),
data shapes in [`schema/`](schema/), tunables in [`config/`](config/). The loop order is
encoded (as a no-op) in [`orchestrator.stub.js`](orchestrator.stub.js).

Status: **scaffold** — design + skeleton only. No live API calls yet. See "Build roadmap".

---

## Why this shape

Three properties matter more than cleverness:

1. **Never prematurely close — and never over-resolve.** A pause is not an end; quiet is not a
   settlement. If the activity resumes, the conflict reopens — and this holds for *every* type,
   not just wars. A frozen border dispute, a suspended sanction, and a paused occupation each
   behave differently from a ceasefire, so the model is **type-aware** (see Lifecycle).
   Regressions ("broken promises") are first-class data.
2. **Don't churn on noise.** A deliberate **settling lag** keeps just-emerging, unconfirmed
   reports out of the dataset until they age and corroborate.
3. **Consistency + auditability.** Every classification follows the *same written rubric* the
   app documents (`src/utils/taxonomy.js`), and every change carries its sources and the trail
   of which agents approved it.

The way to get all three cleanly is **separation of concerns**: many small single-purpose
agents instead of one clever mega-prompt. Each is independently testable and tunable.

---

## The loop

```
  fetch (ACLED / UCDP)                         ── deterministic, no LLM
      │
  normalize + cluster by conflict              ── deterministic
      │
  pending buffer  ◄──────── settling lag ──────── observations wait until aged + corroborated
      │  (promote when cleared)
      ▼
  EXTRACTOR agent  ──► change proposal (structured diff + citations)
      │
  deterministic GATES  (shape · age · source-count · dedup)   ── fail fast, cheap
      │  (pass)
      ▼
  VERIFIERS in parallel   (classification · severity · lifecycle · corroboration)   ── LLM critics
      │  (verdicts: pass | fail | uncertain  + confidence + reasons + evidenceRefs)
      ▼
  RECONCILER agent  ──► decision + rationale ──► review queue        (NEVER writes seed.json)
      │
   [ human approves ]
      ▼
  MERGER (deterministic) ──► seed.json + version bump + validate ──► PR to main

  WATCHER (parallel daily pass): re-checks every NON-RESOLVED conflict (active/easing/
  suspended/dormant) for regression / escalation / closure, independent of the new-event flow.
```

The Watcher is what catches *"a deal was signed, then fighting resumed the next day"* — it does
not wait for a fresh news cluster; it actively re-examines everything still `active`/`ceasefire`.

---

## Components

### Deterministic gates (code, not LLM — run first)
Cheap, certain checks that fail fast before spending a single token:

| Gate | Checks |
|------|--------|
| **Shape** | valid `type` enum, `severity` ∈ 1–5, every `countryId` is a real ISO-3 in `seed.json.countries`, `involvedCountries` equals the parties' ids |
| **Age** | the observation cluster has cleared the **settling lag** (`T_settle`), or is corroborated across ≥ X days |
| **Source-count** | ≥ `N_min` distinct allow-listed sources (credibility-weighted) |
| **Dedup** | fuzzy-match the proposal against existing conflicts (title / aliases / parties / region) → attach to an existing conflict, or flag genuinely-new |

### Producer — [Extractor](agents/extractor.md)
Reads a promoted cluster (plus the current dataset entry, if any) and emits a **structured
change proposal**: a typed diff with a candidate record and **inline citations** tying each
field to the source items that support it. It *proposes*; it does not decide.

### Verifier critics (LLM, parallel) — one mandate each
Each returns `{ verdict: pass | fail | uncertain, confidence, reasons[], evidenceRefs[] }`.
No verifier knows about the others — clean separation means you can test and tune one at a time.

| Agent | Single mandate | Guards against |
|-------|----------------|----------------|
| [V1 Classification](agents/verifier-classification.md) | `type` + each party `role` match the definitions in `taxonomy.js`? | mislabeling (calling a war a "genocide", wrong roles) |
| [V2 Severity](agents/verifier-severity.md) | `severity` 1–5 matches `SEVERITY_LEVELS` given the cited intensity/casualty evidence? | over/under-stating; recency bias |
| [V3 Lifecycle](agents/verifier-lifecycle.md) **(guardrail)** | Is the **status transition** legal for *this conflict's type* (per its lifecycle profile)? Is a claimed close a genuine settlement or just a pause / mere quiet? Any **regression**? | **premature closure / over-resolution**; missing a reignition; applying war logic to a border dispute or a sanction |
| [V4 Corroboration](agents/verifier-corroboration.md) | Do the cited sources *actually* support each claim? Independent, ideally **cross-language** agreement? Credibility-weighted? | single-source rumor; circular reporting |

### Judge — [Reconciler](agents/reconciler.md)
Aggregates gate results + all verifier verdicts into a decision:
- all pass, high confidence → queue as **auto-approved** (still human-visible)
- any fail / low confidence / **verifiers disagree** → **needs-human**, objections surfaced
- writes to the **review queue only** — never mutates `seed.json`.

### Merge (deterministic, human-triggered) — Merger
On human approval: applies the proposal to `seed.json`, bumps `version`, re-runs the Shape
validator, appends a changelog line, opens a **PR to `main`**. This is the only step that
writes the dataset, and a human triggers it.

### Watcher (deterministic scheduler + Extractor/V3 on each ongoing conflict)
A daily pass over every **non-`resolved`** conflict (i.e. `active` / `easing` / `suspended` /
`dormant` — including long-frozen border disputes): pull latest, run it through the same
Extractor → gates → verifiers path with a bias toward **status** questions (regression,
escalation, closure). `resolved` conflicts are re-checked on a slow cadence, since even a
settlement can break down. Updates `lastCheckedAt`.

---

## Lifecycle — generic phases, per-type profiles

A single war-centric "ceasefire → violation" machine is wrong for most types. So status is a
small **generic phase set**, and each conflict `type` carries a **profile** (in
[`config/lifecycle.example.yml`](config/lifecycle.example.yml)) that defines its legal
transitions, evidence bar, dwell timer, default terminal, and the *words* shown to a reader.

Generic phases (`status`):

| phase | meaning | watched? |
|-------|---------|----------|
| `active` | happening now | yes |
| `easing` | de-escalating, still happening | yes |
| `suspended` | an explicit, **reversible** pause (ceasefire, truce, sanctions temporarily lifted) — *not* a settlement | yes, closely |
| `dormant` | inactive but **unresolved** — a frozen dispute / claim persists | yes |
| `ended` | the acts have ceased; nothing formal left to settle (war concluded, genocide stopped) | occasionally |
| `resolved` | settled by a **positive terminal event** (treaty, withdrawal, sanctions lifted, recognition) | occasionally |

**The core guardrail, generalized — _quiet ≠ resolved_:**
> Sustained quiet may move a conflict to `dormant` or `ended` (still watched, can snap back). It
> **never** yields `resolved`. `resolved` requires positive evidence of a genuine terminal event.
> Even `resolved` can regress.

**Regression** (generalizes "violation"): any credible, corroborated evidence that the activity
resumed snaps status back to `active`, resets the dwell timer, and logs an event. The *label* is
per type — hostilities resumed (war), ceasefire broken (civil war), re-occupation (occupation),
re-imposed / tightened (sanctions), funding resumed (funding), flare-up / new claim (disputed
territory).

```
 active ⇄ easing ──► suspended ──(dwell, per type)──► dormant  or  ended     (still watched)
   ▲                                                     │
   └─────────── regression (per-type label) ─────────────┘

 resolved  ◄── positive terminal event ONLY (treaty / withdrawal / lifted); rare regression still possible
```

Because it's parameterized by the type profile, **V3 Lifecycle is one generic verifier** that
applies the right vocabulary, evidence bar, and dwell timer per type — instead of assuming
everything is a war. Example profiles:

```yaml
disputed_territory:
  default_terminal: dormant           # quiet → frozen, NOT resolved
  resolved_requires: [treaty, demarcation, recognized_settlement]
  regression_label: "flare-up / renewed clashes"
  dwell_days: 180                     # border tensions simmer slowly
war:
  default_terminal: ended
  resolved_requires: [peace_treaty, decisive_conclusion]
  regression_label: "hostilities resumed"
  dwell_days: 45
sanctions:
  labels: { suspended: "temporarily lifted", resolved: "lifted" }
  default_terminal: resolved
  resolved_requires: [formally_lifted]
  regression_label: "re-imposed / tightened"
  dwell_days: 30
```

---

## State & queues (plain JSON files, no DB)

```
ai-updater/state/
  conflicts/<id>.json    # per-conflict pipeline state (see schema/conflict-state.schema.json)
  pending/<hash>.json    # observations seen but not yet aged/corroborated (settling buffer)
  proposals/<date>/      # emitted change proposals (see schema/proposal.schema.json)
  review/<date>.md       # human-readable diff digest for approval
```
(These directories are created at runtime by the pipeline; they are not part of the scaffold.)

Per-conflict pipeline state extends the app record with: `status`
(`active | easing | suspended | dormant | ended | resolved`), `statusHistory`,
`severityHistory` (severity-over-time), `regressions`, `lastCheckedAt`, `sources`,
`provenance`. See [`schema/conflict-state.schema.json`](schema/conflict-state.schema.json).

---

## Temporal parameters (see [`config/params.example.yml`](config/params.example.yml))

| Param | Meaning | Default |
|-------|---------|---------|
| `T_settle` | settling lag before an observation can change the dataset | 7 days |
| `T_dwell` | sustained quiet before a conflict leaves `active` — **per-type** via the lifecycle profile; quiet only ever reaches `dormant`/`ended`, never `resolved` | 45 d (war) · 180 d (disputed) |
| `N_min` | distinct credible sources required to corroborate | 2 (more for status changes) |
| `recheck_cadence` | how often the Watcher re-checks ongoing conflicts | daily |

---

## Data contract with the app

The pipeline's output conforms to `src/data/seed.json` so a merge is a **data** change, not code:
- Pipeline-owned entries stay `seed_`-prefixed. `src/db/seed.js` refreshes `seed_` entries on a
  `version` bump and never touches `user_` entries.
- `involvedCountries` must equal parties' `countryId`s; country ids must exist in
  `seed.json.countries`; `type` / `severity` / `role` follow `src/utils/taxonomy.js`.
- **Proposed app-side additions** (added when coupling): `status`, `statusHistory`,
  `lastCheckedAt`, richer per-claim `sources`. The app can then surface `status`
  ("ceasefire" / "reignited") alongside the "unsourced" flag it already has.

---

## Open design note — events as the atomic unit (revisit later)

A conflict should contain **sub-events**: WW2 → Pearl Harbor, D-Day, Hiroshima; Israel–Iran →
individual strikes; the slave trade → phases + abolition. The strong version of this: **the
event is the atomic, sourced unit, and a conflict is an aggregation of its events.**

This unifies several logs that currently sit parallel — `severityHistory`, `statusHistory`,
`regressions`, and per-claim `sources` are all really just **events** of different kinds. A
conflict would carry one `events[]` timeline, and its summary fields (`severity`, `status`) are
**derived** from those events.

It also fits the pipeline naturally: every ingested news/feed item *is* an event; the Extractor
attaches it to a conflict; conflict-level severity/status are recomputed from the event stream.
A "regression" is simply a new event after a quiet stretch. And it enriches the app — the map's
timeline can show a conflict's events, not just its span.

```jsonc
{ "id": "seed_wwii", "title": "World War II", "severity": 5, "status": "ended",
  "events": [
    { "id": "...", "date": "1941-12-07", "title": "Pearl Harbor", "kind": "attack",
      "severity": 4, "location": "HI", "parties": ["JPN","USA"], "sources": ["..."] }
  ] }
```

Deferred by the user ("we'll get back to this"). When taken up, it reshapes both the app data
model and the pipeline's `proposal`/`state` schemas — so decide it *before* Phase 1 schemas are
frozen.

## Tech choices

- **Node** (matches the repo). Plain JSON-file queues — no database, no orchestration framework.
- **LLM via the Anthropic SDK** (`@anthropic-ai/sdk`), latest Claude model, each agent a single
  focused prompt with a **strict JSON output** schema. (Not wired in this scaffold.)
- **Structured feeds first**: ACLED + UCDP. General news is a later corroboration/early-signal
  overlay.
- **GitHub Actions cron** to schedule; the updater opens a **PR** rather than pushing to `main`.

---

## Build roadmap

- **Phase 0 — this scaffold:** architecture, agent specs, schemas, config templates, no-op
  orchestrator. No API. *(done when this folder is reviewed.)*
- **Phase 1 — thin slice:** 1 source (ACLED) + 1 ongoing conflict; state model + **V3
  Lifecycle** + Reconciler; emit a `review/*.md` diff. Dry-run, no merge.
- **Phase 2:** add Extractor + V1 Classification + V2 Severity; corroboration over 2–3 sources.
- **Phase 3:** dedup at scale + UCDP; translation layer; news overlay.
- **Phase 4:** GitHub Action cron + auto-PR + Merger coupling to `seed.json`; app surfaces
  `status`.
