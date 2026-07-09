# AI Updater — Architecture (design of record)

> A team of narrow AI agents + web search that keeps the Conflict Atlas dataset current **and**
> honest — and can also **fill the past** on demand. Deterministic code does the cheap/certain
> work (fetch, shape-check, dedup lookup, merge); LLM agents do **only judgment**, each in one
> lane. **Every uncertain path ends at a human review queue — never a silent guess or a dead end.**

Status: **implemented end-to-end and running.** The `scan → review → apply` loop, a local browser
**control panel** (`serve`), a hands-off **weekly cron** (`auto` + GitHub Actions), and the
coverage/digest logs are all in `conflict_updater/` — offline-tested (fakes, no key) and
live-verified on real windows (dedup, continuation, tight-window quality). LLM calls are **batched
to 3 per candidate** (resolver + enrich + verify). Prompts live in `prompts.py`, typed models in
`schema.py`, the coherent merger in `merge.py`.

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
   ENRICH     ONE call: event kind + (new) conflict type · severity 1–5 · country roles ·
              location label · neutral summary · conflict status · (new) span dates (taxonomy.js)
                          ▼   then, in code: Nominatim turns the label into real coords;
                          ▼   _gather_sources links every corroborating fetched article
   VERIFY     ONE call: do the sources support it (≥N independent, cross-outlet/language)?
              AND decide auto-approve vs human   ── thin / contested / low-confidence ──► HUMAN
                          ▼
   REVIEW / AUTO   manual: approve in the panel   ·   cron: auto-apply the confident, log the rest
                          ▼
   MERGER     (code) write events[] → seed.json · re-derive span · bump version · validate
```

(`ENRICH` batches what were seven per-field agents; `VERIFY` batches fact-check + reconcile —
so each candidate is **3 LLM calls** (resolver + enrich + verify), not ~9.)

---

## 4. The agent team

Deterministic (code, no tokens): **Fetcher**, **dedup**, the **Nominatim geocode**,
`_gather_sources`, `derive_span`, and the **Merger** + `validate`. **Five** LLM agents, each a
single focused prompt with strict JSON out. The seven old per-field enrichers and the
fact-check + reconciler were **batched into two calls** (`enrich`, `verify`) to cut round-trips
~3× — same guidance, one response.

| Agent | Its one job | Key output |
|-------|-------------|-----------|
| **Scoper** | turn "period + region + topic" into concrete research queries in the region's languages | query plan + conflict ids to re-check |
| **Extractor** | pull discrete **events** (date · actor · action · place) from fetched items; discard opinion; score each's **significance** 1–5 | candidate events + citations |
| **Resolver** *(LLM + code)* | match each candidate against the base by title/**aliases**/parties/region/date-overlap → *already-known* / *attach* / *new* / *ambiguous* | routing decision |
| **Enrich** | **one call** for the whole event: `kind` (+ new conflict `type`), `severity` 1–5, country `roles` (structural), `location` label, neutral `summary`, conflict `status` (as of today), and a new conflict's `span` — strictly per `taxonomy.js` | fully-described event |
| **Verify** | **one call**: do the sources support it (≥N independent, cross-outlet/language — §8)? AND decide **auto-approve vs human** | verdict + confidence + decision |

Code fills the gaps: **Nominatim** turns Enrich's place *label* into real lat/lng (an LLM
recalls famous cities but collapses smaller ones); `_gather_sources` links every corroborating
fetched article; `derive_span` reconciles the sourced span with the events' min/max so a
conflict's duration self-corrects as coverage fills in.

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

**5d. A field is contested** (role genuinely dual, type ambiguous, severity evidence thin,
location unknown-but-expected): `verify` catches it and routes the whole proposal to **human** with
the open question attached — never ship a contested value silently.

**5e. Lifecycle** (see §6): if it's unclear whether something truly ended → **do not close**
(stay `active`/`dormant`); `resolved` requires positive evidence; any doubt → human.

**5f. Verify:** well-supported + corroborated + high confidence + nothing contested → **auto-approve**.
Otherwise → **needs-human**, with the exact open question attached. Founding a *new* conflict needs a
higher bar (strong, cross-corroborated) to auto-approve; anything thinner is held.

Terminal fallback everywhere: **human review queue.** That is the guarantee there is no
"idk what to do" state.

### 5g. What the pipeline knows vs how it stays unbiased

The atlas's **existing data is used for dedup/identity and role consistency.** The Resolver sees
the matched conflict *and its existing events*, so it can tell "already have this" from "this fills
a gap". **Enrich** is shown the parent conflict's **type + existing parties/roles** so a country's
role stays structural and doesn't flip event-to-event — but the event's *facts* (severity, summary,
what happened) are judged **from its sources**, so a scan never conforms new events to your
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
  Until an explicit per-outlet alignment allowlist exists, the fact-checker uses a **measurable
  proxy**: independent **outlets** (distinct domains, populated by the fetcher) and **languages**.
  `cross_alignment` = corroboration across different outlets and/or languages, so the signal is
  real and reachable today rather than a field nothing can set.
- **Attribute, don't adopt.** Where sources genuinely disagree, the record states the range and
  **attributes** each framing ("Israel says… ; the UN Commission found…") rather than picking a
  side. `enrich` writes the summary as neutral, attributed prose.
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
- **LLM via LangChain**, provider-swappable in `llm.py` — OpenRouter / Google / OpenAI. Free models
  ignore native structured output, so the OpenRouter path uses a **prompted-JSON** strategy (embed
  the schema, parse tolerantly) + retry/backoff on 429s. **Three LLM calls per candidate** (resolver
  + enrich + verify) after batching; each is one prompt in `prompts.py` + a strict pydantic schema.
- **Web search** via a swappable `SearchClient` (`search.py`, Tavily default, advanced depth) for
  discovery + corroboration; the fetcher tags each item with outlet (domain) + language.
- **Real coordinates** via a swappable `GeocodeClient` (`geocode.py`, Nominatim/OpenStreetMap,
  free/no-key) — code, not LLM memory.
- **CLI (`cli.py`):**
  - `scan <period> [--region] [--limit]` → proposals JSON + a numbered review markdown + coverage.
  - `apply <proposals> [--approve N…] [--approve-all] [--dry-run]` → fold approved, non-provisional
    items into `seed.json`; blocks only on incoherence **it** introduces (pre-existing seed issues
    are noted, not blocking).
  - `coverage` → the honesty map (found / quiet / blind per region-period).
  - `auto <period>` → **hands-off**: scan, auto-apply only the confident items, write a digest.
  - `serve` → the **local control panel** (`server.py` + `dashboard.html`): a browser dashboard
    to run scans, review, apply, and browse the data. Local-only (holds keys, writes seed.json).
- **The merger's coherence rules** (every case has one): attach appends the event, re-sorts by date,
  **raises** conflict severity to the event's (never lowers), unions `involvedCountries`, adds any new
  party+role (never clobbering an existing role), unions aliases, lets `status` change **only from
  the latest event** — a backfilled old battle can't reopen a resolved war — and **re-derives
  `startDate`/`endDate`** from the events + any source-stated span (`derive_span`, one helper shared
  with the pipeline): an earlier event pulls the start back, a terminal event closes the end. So a
  conflict's duration is never a frozen guess — it self-corrects as coverage fills in. `validate()`
  enforces the hard invariants: `parties ⊆ involvedCountries`, every event party is a listed country,
  ISO dates, severity 1–5, and no `ongoing && status∈{ended,resolved}`.
- **Tested offline:** fake LLM + search + geocode drive the whole pipeline under `pytest` with no
  API key (dedup, merge, span/dates, coverage ledger, JSON round-trip). A live run needs an LLM key
  (+ `TAVILY_API_KEY`). DB migration later, once the file queues get messy.

---

## 12. Build roadmap

- **Phase 0 (design):** this doc + agent specs + schemas + config templates. ✅ *done*
- **Phase 1 — `scan()` on one past window:** Scoper + Extractor + Resolver + enrich + verify,
  web-search only, run on **one region/decade**; emits a `review/*.md` diff, **no merge**. A settled
  historical window is the safest first target — the answer is checkable.
  ✅ *implemented + offline-tested (needs a live keyed run to trust-test against known history)*
- **Phase 2 — the Merger + apply CLI:** `merge.apply()` + `merge.validate()` fold approved,
  non-provisional proposals into `seed.json` coherently (all rules in §11), human-gated.
  `scan → review → apply` is now a closed loop. ✅ *implemented + offline-tested.* Remaining:
  source-existence verification wired into the gate before an auto-approve.
- **Phase 3 — automate it:** ✅ the `auto` command (scan → auto-apply confident → digest) + a
  **weekly GitHub Actions cron** (`.github/workflows/pipeline-weekly.yml`) that runs it in the cloud,
  commits `seed.json` + the digest, and pushes → the live map updates. PC-independent, git-reversible.
  Reliability note: free LLM tiers get upstream-throttled — an unattended cron wants a paid model
  (~pennies/week) to be dependable.
- **Phase 4:** the coverage ledger + significance ranking are in; still open — a coverage-driven
  backfill crawler, ACLED/UCDP structured anchors, and explicit per-outlet alignment tagging.

The order held: past windows trust-tested the agent team against known history (dedup, continuation,
tight-window quality all verified live) before the **identical function** was pointed at "this week"
and put on a schedule.
```
