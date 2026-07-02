# AI Updater — daily conflict-ingest pipeline

> **This branch (`ai-updater`) is the home of the automated updater.** It is built as a
> **standalone part** first, then coupled to the app later. If you're working in this
> branch, you're working on the pipeline — not the React app. Keep app changes on `main`.

The Conflict Atlas dataset is currently hand-curated. The goal of this pipeline is to keep
it **current and sourced automatically**: each day, scan credible multi-language sources to
detect new conflicts, ended ones, escalations/de-escalations, and fresh citations — then
propose reviewed updates to the dataset with clear summaries, an assessed severity + type,
and sources.

This is the credibility leap: world-class = data rigor, not UI.

---

## Guardrails (the non-negotiables)

These are the design rules that make this trustworthy rather than a rumour amplifier:

1. **Never prematurely close a conflict.** A ceasefire / "deal to stop" is an *event*, not an
   end. Model status as a state machine (below). If fighting resumes, it reopens. Track
   **ceasefire violations / broken promises** as first-class data.
2. **~1-week settling lag.** Treat breaking news as *provisional*. Only promote a change into
   the dataset after it survives a settling window, so just-emerging noise doesn't churn the map.
3. **Corroborate before acting.** A status/severity/type change needs **N independent,
   credibility-weighted sources** agreeing — ideally across languages. Store every source used.
4. **Human-in-the-loop.** Proposed changes land in a **review queue as a diff you approve**,
   never auto-merged into the dataset. AI must not silently rewrite an atlas of atrocities.
5. **Follow the existing rubric.** Severity/type/role assessment uses the *same definitions*
   the app documents in `src/utils/taxonomy.js` — machine and human classify identically.

---

## Status state machine (guardrail #1, made concrete)

```
                 escalation
   active ─────────────────────────► active (severity ↑)
     │  ▲
     │  │ violation / resumption (snaps back)
     │  │
     ▼  │
 ceasefire_declared ──dwell timer──► holding ──sustained quiet──► ended
```

- A conflict only advances toward `ended` after a **dwell timer** of sustained quiet.
- Any credible report of renewed fighting **snaps it back to `active`** and logs the violation.
- `ended` is reversible if fighting later resumes (a conflict can reignite).

---

## Pipeline stages

1. **Schedule** — daily job (GitHub Action cron). No server required; matches the current
   deploy model.
2. **Fetch + translate** — pull from a fixed allowlist of ~20 credible outlets across
   languages. Prefer **structured conflict datasets** where possible (they're pre-curated):
   - [ACLED](https://acleddata.com/) — Armed Conflict Location & Event Data
   - [UCDP](https://ucdp.uu.se/) — Uppsala Conflict Data Program
   - Wire services (Reuters, AFP, AP) + regional press in Arabic / French / Russian / Spanish / etc.
3. **Extract + assess** — LLM reads each item against `taxonomy.js`, proposing type, severity,
   affected countries + roles, and a longer summary. Cite sources inline.
4. **Corroborate** — require multi-source agreement before a change is eligible.
5. **Dedup / entity-resolution** — is this an *existing* conflict (many names, many languages)
   or genuinely new? Match against `seed.json` by title/aliases/`involvedCountries`. This is
   the hard, unglamorous core — budget time for it.
6. **Review queue** — emit a human-readable diff (proposed adds / status changes / new sources).
7. **Merge** — approved diffs update the dataset, bump the seed version; the app refreshes on
   next load.

---

## Data contract with the app (how coupling will work later)

The app reads `src/data/seed.json`. The pipeline's output must conform to that schema so
merging is a data change, not a code change.

- Top-level `version` (string). **Bumping it triggers the app to re-import `seed_` conflicts.**
  (`src/db/seed.js` overwrites `seed_`-prefixed entries on a version bump, leaves `user_` ones.)
- Each conflict:
  ```jsonc
  {
    "id": "seed_<slug>",            // pipeline-owned entries stay seed_-prefixed
    "title": "...",
    "type": "war | civil_war | genocide | occupation | proxy_war | sanctions | funding | disputed_territory",
    "severity": 1-5,                // INTENSITY per taxonomy.js SEVERITY_LEVELS
    "startDate": "YYYY", "endDate": "YYYY | null", "ongoing": bool,
    "description": "...",           // pipeline should write LONGER, sourced summaries
    "parties": [{ "countryId": "ISO3", "role": "<role>" }],
    "involvedCountries": ["ISO3"],  // MUST equal parties' countryIds (app relies on this)
    "tags": ["..."],
    "sources": ["https://..."]      // populate this — the app flags entries with none
  }
  ```
- Country IDs must exist in `seed.json.countries` (ISO 3166-1 alpha-3). Validate before merge.
- Definitions for type / severity / role live in `src/utils/taxonomy.js` — treat it as the
  shared spec between app and pipeline.

**Extensions likely needed** (design here, add to the app when coupling): a `status` field for
the state machine, a `statusHistory` / `events` log (ceasefires, violations), `lastCheckedAt`,
and per-claim source attribution.

---

## Suggested first slice (don't boil the ocean)

Prove the loop end-to-end on a tiny scope before scaling:

1. **One source** (ACLED) + **one ongoing conflict**.
2. Implement the **status state machine** + dwell timer on that one conflict.
3. Produce a **review-queue diff** file (no auto-merge).
4. Only then: add more sources, translation, dedup, corroboration.

---

## Tech (proposed, not fixed)

- Node (matches the repo). Standalone entrypoint under `ai-updater/`.
- LLM via API for extraction/assessment (latest Claude model).
- GitHub Action cron for scheduling.
- Output: a proposed-changes artifact + a validation step against the schema above.

## Cost & safety notes

- 20 sources × daily × LLM assessment adds up — cache aggressively, only re-assess what changed.
- The review queue is the safety valve. Keep it.
- Log every source and every automated decision for auditability.

---

*Status: scaffolding. Nothing built yet — this README scopes the work. See the project memory
note `project_agentic_pipeline` for the origin of these requirements.*
