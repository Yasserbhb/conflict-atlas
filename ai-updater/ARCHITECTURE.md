# AI Updater — Architecture (design of record)

> A team of narrow AI agents + web search that keeps the Conflict Atlas dataset current **and**
> honest — and can also **fill the past** on demand. Deterministic code does the cheap/certain
> work (fetch, shape-check, dedup lookup, merge); LLM agents do **only judgment**, each in one
> lane. **Every uncertain path ends at a human review queue — never a silent guess or a dead end.**

Status: **design locked; the full `scan → review → apply` loop is implemented in Python**
(`conflict_updater/`, offline-tested with fake LLM/search — a live run needs an API key). Agent
prompts live in `conflict_updater/prompts.py`, the typed models in `conflict_updater/schema.py`,
and the coherent merger in `conflict_updater/merge.py`.

---

## 0. The one non-negotiable invariant (the "no dead-end" rule)

At **every** decision node below there are exactly three possible outcomes, never a fourth:

1. **Confident + corroborated** → proceed to the next stage.
2. **Confident it's noise / already-known / unsupported** → drop (logged, with reason).
3. **Anything else** (ambiguous, contested, single-source, low-confidence, sources disagree,
   role unclear, doesn't match the rubric) → **escalate to the human review queue** with the
   specific question.

So the pipeline can *always* answer "what do I do here?": if it isn't sure, a human decides.
Nothing merges without a human, and nothing is ever silently invented or dropped.

---

## 1. The atomic model — events, then conflicts

The app now models a **conflict as an aggregation of `events[]`** (shipped 2026-07). The pipeline
is built on the same unit:

> The **event** is the atomic, sourced thing the agents produce. Each event either **attaches to
> an existing conflict** or, if it has no home, **triggers a new conflict**. A conflict's
> `severity`/`status` are **derived** from its event stream.

Event shape (matches the app): `{ date, title, kind, severity 1-5, location:{lat,lng,label}|null,
parties:[ISO3], description, sources:[{url,lang,outlet}] }`. Conflict shape adds `type`,
`aliases[]`, top-level `parties` (country + role), `status`, and derived summary fields.

This is why the pipeline is dual-use: **"a new thing happened today" and "something happened in
1975 that we're missing" are the same operation** — produce a sourced event, resolve it against
the base, attach or create. Only the *trigger* and *time rules* differ (§2).

---

## 2. One operation: scan a period

The whole pipeline is **a single function with a single input** — a time window (plus optional
region/topic). There is no "backfill vs live"; there is only:

```
scan(period, region?, topic?)  →  proposed events & conflicts for that window
```

It does not matter whether the window is a century or a week — **same input, same protocol,
same agents**:

- `scan([1924, 2024], region: "Africa")` — fill a hundred years of African conflicts
- `scan([2003, 2005], topic: "Darfur")` — deepen one conflict's history
- `scan([last_monday, today])` — the routine weekly update

The **weekly job is just an automatic caller of the same function** with `period = the last 7
days`. Whether a human types the window or cron supplies it changes **nothing** downstream.

The only thing that varies is **per-event recency** (a property of an event's date, not of how
the run was triggered): any candidate event dated within the last `T_settle` days is **provisional**
— held until it ages and corroborates — because breaking news is unreliable. A century-scan never
produces provisional events; a weekly scan does. One rule, applied to each event by its date (§7).

---

## 3. The pipeline — one entry, each agent in its lane

Every run — human or cron — enters the same top and flows straight down. Each box is **one agent
with one job**. The only branches out are the `─► HUMAN` escapes (the "no dead-end" rule).

```
              scan(period, region?, topic?)              ◄── the ONLY input
                          │
   ┌──────────────────────▼──────────────────────────────────────────────────┐
   │ SCOPER     turn the window into concrete, multi-language search queries.  │
   │            For recent windows, also emit a targeted "is X still quiet /   │
   │            did it flare?" query for each non-resolved conflict.           │
   └──────────────────────┬──────────────────────────────────────────────────┘
                          ▼
   FETCHER    (code) web search + ACLED/UCDP → raw items tagged {lang, outlet, alignment}
                          ▼
   EXTRACTOR  raw items → discrete candidate EVENTS (date · actor · action · place) + citations
                          ▼
   RESOLVER   already in the base?  ── already-known → drop (keep any new sources)
              (dedup / identity)    ── attach to conflict X
                          │         ── new conflict
                          │         ── ambiguous ─────────────────────────────► HUMAN
                          ▼
   RECENCY    event within the last T_settle days? → hold as provisional (age + corroborate)
                          ▼
   ENRICHERS  (parallel — one lane each)
        ├ CLASSIFIER   event kind, and a new conflict's type        (taxonomy.js)
        ├ SEVERITY     1–5 from the rubric + cited evidence
        ├ ROLES        each country's role (aggressor / funder / victim / mediator / …)
        ├ GEOLOCATOR   lat / lng / label — or null for a place-less event
        ├ SUMMARIZER   neutral, attributed prose
        └ LIFECYCLE    status (active/easing/suspended/dormant/ended/resolved); quiet ≠ resolved
                          ▼
   FACT-CHECK  do the sources support each field? ≥ N independent, cross-language,
               cross-alignment?              ── not enough / disagree ─────────► HUMAN
                          ▼
   RECONCILER  all pass + confident → auto-queue      else ─────────────────────► HUMAN
                          ▼
   HUMAN REVIEW   approve / edit / reject             ◄── the one required human step
                          ▼
   MERGER     (code) write events[] → seed.json · bump version · validate · PR to main
```

---

## 4. The agent team

Deterministic (code, no tokens): **Fetcher**, **Resolver lookup**, **Merger**, the **Watcher
scheduler**, and all shape/enum/coordinate range checks. LLM agents below — each a single focused
prompt with strict JSON out (`{verdict|value, confidence, reasons[], evidenceRefs[]}`), and none
knows about the others (so each is separately testable/tunable).

| Agent | Its one job | Key output |
|-------|-------------|-----------|
| **Scoper** *(backfill)* | turn "period + region + topic" into concrete research queries in the region's languages | query plan |
| **Extractor** | pull discrete **events** (date · actor · action · place) out of fetched items; discard opinion/analysis | candidate events + citations |
| **Resolver** *(LLM + code)* | match each candidate against the base by title/**aliases**/parties/region/date-overlap → *already-known* / *attach to conflict X* / *new* / *ambiguous* | routing decision |
| **Classifier** | event `kind` (attack/atrocity/ceasefire/…) and, for a new conflict, its `type` — strictly per `src/utils/taxonomy.js` | kind + type |
| **Severity** | `severity` 1–5 from the rubric given the cited human toll/intensity | 1–5 + evidence |
| **Roles** | each involved country's `role` (aggressor/defender/victim/funder/proxy/occupier/mediator/sanctioner/sanctioned) — per event and rolled up to the conflict | party→role map |
| **Geolocator** | resolve the event's `location` to lat/lng/label; **null** for genuinely place-less events (nationwide famine) | coords or null |
| **Summarizer** | write the neutral 1–2 sentence event description and, for a new conflict, its longer summary | prose |
| **Lifecycle** *(guardrail)* | is the proposed **status** change legal for this conflict's **type** (§6)? end vs de-escalation vs dormant vs regression | status + transition |
| **Fact-check / Corroboration** | do the cited sources actually support each field? ≥ N independent, **cross-language, cross-alignment** sources? (§8) | pass/fail + credibility |
| **Reconciler** | fold every verdict into one decision; route to auto-queue or human | decision + rationale |

---

## 5. Decision tables — where each branch goes (the "logically full" part)

**5a. Is the fetched item an event?**
| Situation | Action |
|---|---|
| has a date + actor + concrete action | → candidate event |
| analysis / opinion / rumor with no concrete act | drop (logged) |
| concrete but undated | → human ("date it or discard") |

**5b. Resolver — does it already exist?**
| Situation | Action |
|---|---|
| near-duplicate of an existing event (same date±window, place, act) | drop, but **merge in any new sources** |
| clearly an event of one existing conflict | **attach** |
| matches an existing conflict under a **different name** | attach + record the new **alias** |
| matches **no** conflict | → NEW-CONFLICT path (5c) |
| matches **several** conflicts, or match is borderline | → human |

**5c. New-conflict path — is it really new?**
| Check | If yes | If no |
|---|---|---|
| an existing conflict is the same thing under another alias? | attach + alias (not a new conflict) | continue |
| a conflict founded **earlier in this same scan** (not yet in seed.json) is the same thing? | **attach to that pending conflict** — not a second duplicate "new" | continue |
| enough corroboration to stand up a conflict? (§8) | derive type/severity/parties+roles/dates/summary → propose new conflict | hold in pending / → human |

Founding a conflict is riskier than attaching to one that already exists (a wrong
id/title/type/parties is harder to undo), so it needs a **higher**, not infinite, bar:
`fact-check pass` + confidence ≥ `NEW_CONFLICT_MIN_CONFIDENCE` (default 0.9) + independent
sources ≥ `NEW_CONFLICT_MIN_SOURCES` (default 3) + cross-alignment → auto-approve is allowed.
Anything thinner → human. This is *not* an unconditional "new conflicts always need a human"
rule — that would make the review queue scale with how much history is missing rather than
with how uncertain any given founding claim actually is.

**5d. Any enricher is unsure** (role contested, type genuinely dual, severity evidence thin,
location unknown-but-expected): attach the field **provisionally**, mark low-confidence, and the
Reconciler routes the whole proposal to **human** — never ship a contested value silently.

**5e. Lifecycle** (see §6): if it's unclear whether something truly ended → **do not close**
(stay `active`/`dormant`); `resolved` requires positive evidence; any doubt → human.

**5f. Reconciler:** all enrichers pass + corroborated + high confidence → **auto-queue**
(still human-visible). Otherwise → **needs-human**, with the exact objection attached.

Terminal fallback everywhere: **human review queue.** That is the guarantee there is no
"idk what to do" state.

### 5g. What the pipeline knows vs how it stays unbiased

The atlas's **existing data is used for one thing only — dedup/identity.** The Resolver sees the
matched conflict *and its existing events*, so it can tell "already have this" from "this fills a
gap", and never re-adds what you have. But **assessment is independent**: the Classifier, Severity,
Roles, Geolocator, Summarizer and Fact-check agents judge each event **from its sources**, and are
*not* shown your existing type/severity/role labels — so a scan never conforms new events to your
(possibly wrong) prior framing. And because a scan covers the **whole window/region**, it also
surfaces conflicts you *don't* have (routed `new`), not only events of the one you asked about.

---

## 6. Lifecycle — generic phases, per-type profiles (kept, now event-driven)

Status is **derived from the event stream** and governed by a small generic phase set; each
`type` carries a profile (`config/lifecycle.yml`) with its legal transitions, evidence bar,
dwell timer, default terminal, and the *words* shown.

`active` · `easing` (de-escalating) · `suspended` (explicit reversible pause) · `dormant`
(inactive but unresolved / frozen) · `ended` (acts ceased, nothing to settle) · `resolved`
(positive terminal event).

**Core guardrail — _quiet ≠ resolved_:** sustained quiet only ever reaches `dormant`/`ended`
(still watched, can snap back); **`resolved` needs a positive terminal event** (treaty,
withdrawal, sanctions lifted). A **regression** (a new event after quiet) snaps status back to
`active`, per-type label (hostilities resumed / re-occupation / re-imposed / flare-up …).

```yaml
war:                { default_terminal: ended,   resolved_requires: [peace_treaty], dwell_days: 45,  regression: "hostilities resumed" }
disputed_territory: { default_terminal: dormant, resolved_requires: [treaty,demarcation], dwell_days: 180, regression: "flare-up" }
sanctions:          { default_terminal: resolved, resolved_requires: [formally_lifted], dwell_days: 30, labels: { suspended: "temporarily lifted" } }
genocide:           { default_terminal: ended,   resolved_requires: [accountability,cessation], dwell_days: 90, regression: "killings resumed" }
```

This directly answers the "call it *ended* vs just *de-escalation*" question: the agent picks the
phase the **evidence + type profile** allow, and defaults toward *not* closing.

---

## 7. Time rules

| Param | Meaning | Default |
|---|---|---|
| `T_settle` | **per event, by its date** — an event within the last N days is provisional (held until it ages + corroborates). A long-past scan never triggers it. | 7 days |
| `T_dwell` | sustained quiet before a conflict leaves `active` — **per type**; only reaches `dormant`/`ended`, never `resolved` | 45 d war · 180 d disputed |
| `N_min` | independent credible sources to corroborate (higher for status changes & new conflicts) | 2–3 |
| `cron` | how often the automatic caller runs `scan([last 7 days])` | weekly |

None of these are "modes" — they're rules keyed off an **event's own date**, so a century-scan
and a weekly-scan run the identical code and simply hit them differently.

---

## 8. Sources — multilingual + anti-bias ("anti-brainwashing")

The whole point is a dataset you can trust, so sourcing is adversarial by design:

- **Original-language sources, not just English.** For each region the Fetcher pulls outlets in
  the local language(s) — Arabic, Persian, Russian, Ukrainian, Hebrew, French (Sahel/Central
  Africa), Spanish (Latin America), etc. Claude reads the original; we store original + outlet +
  language on every source. Config: `config/sources.yml` (allowlist with `lang`, `region`,
  `alignment`, `credibility`).
- **Cross-alignment corroboration.** A contested claim (casualty counts, *who started it*, the
  "genocide" label) may only enter if corroborated across sources of **different alignment** —
  not just multiple outlets echoing one wire. Structured datasets (ACLED, UCDP) anchor the facts.
- **Attribute, don't adopt.** Where sources genuinely disagree, the record states the range and
  **attributes** each framing ("Israel says… ; the UN Commission found…") rather than picking a
  side. The Summarizer is instructed to neutral, attributed prose.
- **Credibility weighting.** Structured feeds & wires high; state/partisan media usable but
  down-weighted and never sufficient alone. Single-source or same-alignment-only → held, not shipped.

This is the concrete mechanism behind "fact-checking from sources, no brainwashing": diversity of
language and alignment is *required*, not optional.

---

## 9. State, queues, human review (plain JSON files, no DB)

```
ai-updater/state/
  conflicts/<id>.json   # pipeline state: status, statusHistory, lastCheckedAt, aliases, provenance
  pending/<hash>.json   # watch-mode observations aging in the settling buffer
  proposals/<date>/     # emitted change proposals (schema/proposal.schema.json)
  review/<date>.md      # human-readable diff digest to approve/edit/reject
  known-false.json      # rejected claims, so the same bad item isn't re-proposed
```

The **review queue** is the product surface: each item shows the proposed diff, the sources
(with language/alignment), the agents' verdicts, and the open question if any. Human choices
(approve / edit / reject) are logged and **feed back** — rejections tune prompts and populate
`known-false.json`.

---

## 10. Data contract with the app

Output conforms to `src/data/seed.json` so a merge is a **data** change:
- Pipeline entries stay `seed_`-prefixed; `src/db/seed.js` refreshes `seed_` on a `version` bump,
  never touches `user_`. Each event carries a Wikipedia/source URL; the app already flags
  source-less conflicts.
- `involvedCountries` == parties' ISO-3s (must exist in `seed.countries`); `type`/`severity`/
  `role`/event `kind` per `src/utils/taxonomy.js` + `utils/eventKinds.js`.
- **App-side additions to add when coupling:** `status`, `statusHistory`, `aliases`,
  `lastCheckedAt`. The app can then show "ceasefire / reignited / dormant" and the source trail.
- Every source URL is **existence-verified** before merge (MediaWiki API for Wikipedia, HTTP 200
  otherwise) — the same check already used by hand (~2.5% of guessed slugs were wrong).

---

## 11. Tech (implemented)

- **Python** (`conflict_updater/` package), pydantic models, plain JSON-file output (a DB later).
- **LLM via LangChain**, provider-swappable in `llm.py` — **OpenAI by default** (`gpt-4o-mini`),
  any langchain provider otherwise. Each agent = one prompt (`prompts.py`) + a strict pydantic
  output schema; the model does the multilingual reading directly.
- **Web search** via a swappable `SearchClient` (`search.py`, Tavily default) for discovery +
  fact-check; ACLED/UCDP as structured anchors (later phase).
- **Two entrypoints, one loop:**
  - `scan(period, region?, topic?)` → CLI `python -m conflict_updater "1990..2003"` (bare period ==
    scan; the weekly cron calls `scan week`). Output = a proposals JSON + a human-review markdown.
  - `apply(proposals, seed)` (`merge.py`) → CLI `python -m conflict_updater apply out/proposals_*.json`.
    Folds only **approved, non-provisional** proposals into `seed.json`, then `validate()`s the whole
    dataset; if any invariant fails it writes nothing and exits non-zero. `--dry-run` reports only.
- **The merger's coherence rules** (every case has one): attach appends the event, re-sorts by date,
  **raises** conflict severity to the event's (never lowers), unions `involvedCountries`, adds any new
  party+role (never clobbering an existing role), unions aliases, and lets `status` change **only from
  the latest event** — a backfilled old battle can't reopen a resolved war. `validate()` enforces the
  hard invariants: `parties ⊆ involvedCountries`, every event party is a listed country, ISO dates,
  severity 1–5, and no `ongoing && status∈{ended,resolved}`.
- **Tested offline:** a fake LLM + fake search drive the whole pipeline under `pytest` with no API
  key (19 tests green, incl. merge + a JSON round-trip). A live run needs `OPENAI_API_KEY`
  (+ `TAVILY_API_KEY`). DB migration later, once the file queues get messy.

---

## 12. Build roadmap

- **Phase 0 (design):** this doc + agent specs + schemas + config templates. ✅ *done*
- **Phase 1 — `scan()` on one past window:** Scoper + Extractor + Resolver + enrichers +
  Reconciler, web-search only, run on **one region/decade**; emits a `review/*.md` diff, **no
  merge**. A settled historical window is the safest first target — the answer is checkable.
  ✅ *implemented + offline-tested (needs a live keyed run to trust-test against known history)*
- **Phase 2 — the Merger + apply CLI:** `merge.apply()` + `merge.validate()` fold approved,
  non-provisional proposals into `seed.json` coherently (all rules in §11), human-gated.
  `scan → review → apply` is now a closed loop. ✅ *implemented + offline-tested.* Remaining:
  source-existence verification wired into the gate before an auto-approve.
- **Phase 3 — automate it:** the recency gate + lifecycle dwell timers, then the **weekly cron**
  that just calls `scan([last 7 days])`. Same code, now unattended.
- **Phase 4:** multilingual source expansion + ACLED/UCDP anchors + cross-alignment corroboration
  hardening; app surfaces `status`.

The order is deliberate: a past window trust-tests the whole agent team against known history
before the **identical function** is ever pointed at "this week" and run on a schedule.
```
