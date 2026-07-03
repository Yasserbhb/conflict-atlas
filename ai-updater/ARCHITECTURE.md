# AI Updater — Architecture (design of record)

> A team of narrow AI agents + web search that keeps the Conflict Atlas dataset current **and**
> honest — and can also **fill the past** on demand. Deterministic code does the cheap/certain
> work (fetch, shape-check, dedup lookup, merge); LLM agents do **only judgment**, each in one
> lane. **Every uncertain path ends at a human review queue — never a silent guess or a dead end.**

Status: **design locked, not built.** Per-agent contracts will live in [`agents/`](agents/),
shapes in [`schema/`](schema/), tunables in [`config/`](config/).

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

## 2. Two modes, one engine

| | **Backfill mode** (fill the past) | **Watch mode** (stay current) |
|---|---|---|
| **Trigger** | human query: *a period + region (+ topic)* — "Central Africa, 1990–2003" | weekly cron |
| **Scope** | everything in that window/region | all **non-`resolved`** conflicts + new-event scan of the feeds |
| **First step** | **pull what already exists** in the base for that scope, so it fills gaps not duplicates | same dedup lookup per candidate |
| **Settling lag** | **none** (historical events are settled) | **yes** — recent reports wait (§7) |
| **Output** | proposed new conflicts + events for the gap, as a review diff | proposed updates/regressions, as a review diff |

Everything downstream of "produce a candidate event" is **identical** in both modes. Backfill is
how the user seeds history *and stress-tests the agents* before letting the same system run
autonomously per week.

---

## 3. The loop

```
  ┌── Backfill: human scope query ──┐        ┌── Watch: weekly cron ──┐
  └──────────────┬──────────────────┘        └───────────┬───────────┘
                 ▼                                        ▼
        SCOPER agent → research plan          WATCHER → list of non-resolved
        (period/region/topic → queries)       conflicts to re-check + feed scan
                 └──────────────┬───────────────────────┘
                                ▼
   FETCHER (deterministic): web search + source APIs, MULTI-LANGUAGE, credibility-tagged
                                ▼
   EXTRACTOR agent: raw items → candidate EVENTS (date, actors, action) + citations
                                ▼
   RESOLVER (dedup/identity): does this event/conflict already exist in the base?
        │  already-known → drop (or enrich sources)
        │  attaches to exactly one conflict → ATTACH path
        │  no home → NEW-CONFLICT path            │ ambiguous → human
                                ▼
   [Watch mode only] SETTLING BUFFER — hold until aged + corroborated (§7)
                                ▼
   ENRICHERS in parallel (LLM critics, one lane each):
        CLASSIFIER (kind/type) · SEVERITY · ROLES · GEOLOCATOR · SUMMARIZER · LIFECYCLE
                                ▼
   FACT-CHECK / CORROBORATION agent: N independent, cross-language, cross-alignment sources
                                ▼
   RECONCILER (judge): all-pass+confident → auto-queue · else → needs-human (with the objection)
                                ▼
   HUMAN REVIEW QUEUE  →  [approve/edit/reject]  →  MERGER (deterministic)
                                ▼
   seed.json (events[] + derived summary) · version bump · shape-validate · PR to main
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
| enough corroboration to stand up a conflict? (§8) | derive type/severity/parties+roles/dates/summary → propose new conflict | hold in pending / → human |

**5d. Any enricher is unsure** (role contested, type genuinely dual, severity evidence thin,
location unknown-but-expected): attach the field **provisionally**, mark low-confidence, and the
Reconciler routes the whole proposal to **human** — never ship a contested value silently.

**5e. Lifecycle** (see §6): if it's unclear whether something truly ended → **do not close**
(stay `active`/`dormant`); `resolved` requires positive evidence; any doubt → human.

**5f. Reconciler:** all enrichers pass + corroborated + high confidence → **auto-queue**
(still human-visible). Otherwise → **needs-human**, with the exact objection attached.

Terminal fallback everywhere: **human review queue.** That is the guarantee there is no
"idk what to do" state.

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
| `T_settle` | **watch mode only** — a report must age/corroborate before it can change the dataset | 7 days |
| `T_dwell` | sustained quiet before a conflict leaves `active` — **per type**; only reaches `dormant`/`ended`, never `resolved` | 45 d war · 180 d disputed |
| `N_min` | independent credible sources to corroborate (higher for status changes & new conflicts) | 2–3 |
| `recheck` | Watcher cadence over non-resolved conflicts | weekly |

Backfill mode sets `T_settle = 0` (history is settled) but keeps `N_min` and every enricher.

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

## 11. Tech

- **Node**, plain JSON-file queues, no DB, no orchestration framework — a small pipeline runner.
- **Anthropic SDK** (`@anthropic-ai/sdk`), latest Claude model; each agent one prompt + strict
  JSON schema. Claude does the translation/multilingual reading directly.
- **Web search** tool for discovery + fact-check; **ACLED/UCDP** as structured anchors.
- **Backfill** = a CLI (`node ai-updater/backfill "Central Africa 1990-2003"`). **Watch** = a
  **weekly GitHub Action** that opens a **PR**, never pushes to `main`.

---

## 12. Build roadmap

- **Phase 0 (design):** this doc + agent specs + schemas + config templates. *(current)*
- **Phase 1 — backfill thin slice:** Scoper + Extractor + Resolver + the enrichers + Reconciler,
  web-search only, on **one region/decade**; emits a `review/*.md` diff, **no merge**. This
  proves the agents on settled history where the answer is checkable.
- **Phase 2:** the Merger + human-review CLI + source verification → approved diffs actually land
  (still human-gated). Backfill becomes usable.
- **Phase 3 — watch mode:** the settling buffer, Watcher, lifecycle dwell timers, `T_settle`;
  weekly cron over non-resolved conflicts.
- **Phase 4:** multilingual source expansion + ACLED/UCDP anchors + cross-alignment corroboration
  hardening; app surfaces `status`.

Backfill is deliberately Phase 1 — it's the safest place to trust-test the whole agent team,
because you can check its work against known history before it ever runs unattended.
```
