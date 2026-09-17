# Conflict Atlas

**🌍 Live site: [yasserbhb.github.io/conflict-atlas](https://yasserbhb.github.io/conflict-atlas/)**

An interactive vector world map for exploring geopolitical conflicts, genocides, occupations, and
atrocities across history — from 1490 to the present.

Two halves, documented together here:

- **The app** — a React + D3 map you browse, filter and scrub through time. Read-only: nobody
  hand-edits the atlas, including its author.
- **The AI updater** — a Python pipeline of narrow LLM agents that is the dataset's *only*
  author. It keeps the atlas current, backfills the past on demand, and shows its working.

---

## Contents

- [The app](#the-app)
  - [Features](#features) · [Quick start](#quick-start) · [Tech stack](#tech-stack) · [Data model](#data-model)
- [The AI updater](#the-ai-updater)
  - [What it is](#what-it-is) · [The agent team](#the-agent-team) · [What makes it trustworthy](#what-makes-it-trustworthy)
  - [Running it](#running-the-pipeline) · [Evaluation](#evaluation) · [Coverage ledger](#coverage-ledger)
  - [Architecture decisions](#architecture-decisions)
- [Deploying & operations](#deploying--operations) · [Troubleshooting](#troubleshooting) · [Disclaimer](#data-sources--disclaimer)

---

# The app

## Features

- **Vector world map** (D3-geo, 50m Natural Earth) with scroll-to-zoom, drag-to-pan, a 10°
  graticule and the projection's sphere outline.
- **Three reading modes**, each with a legend:
  - **Overview** — countries shaded by conflict severity.
  - **Country** — click a country to see reach-lines radiating to every conflict it's involved
    in, coloured by its role (solid = attacks, dashed = backs/involved).
  - **Conflict** — focus one conflict; every party country fills with its role colour.
- **Century rule (1490–2026)** — the year scrubber carries a conflict-density histogram and
  century ticks, so dragging it also shows *when* the world was most at war.
- **Relationships graph** — conflicts as nodes, edges where contemporaneous conflicts share
  belligerents. The force layout self-organises into eras.
- **Pipeline** — the agents' own operations log: what each daily run scanned, what it added,
  what it held back, and a link to that run's full output.
- **Export** the whole dataset as JSON.
- **~240 conflicts / ~490 sourced events** across every region and era.
- **Seven views**: Map, Conflicts, Stats, Timeline, Relationships, Pipeline, Help.

> **On borders:** the map always shows *modern* borders. Historical events are mapped onto the
> country occupying that territory today (the Spanish Conquest → modern Mexico/Peru). Successor
> states use aliases (Russia = USSR, Turkey = Ottoman Empire).

## Quick start

You don't need to be a developer. It runs entirely on your own computer — no account, no server.

1. **Install Node.js** (once): the LTS build from [nodejs.org](https://nodejs.org).
2. **Get the code**: *Code → Download ZIP*, or `git clone <repo-url>`.
3. **In the project folder**:

```bash
npm install
npm run dev
```

4. Open the printed link — usually **http://localhost:5173**.

`Ctrl+C` stops it. Other scripts:

```bash
npm run build     # optimized static site in dist/
npm run preview   # serve that build locally
npm run lint      # oxlint
```

> The dataset is cached in your browser (IndexedDB) on first load, so the map works offline.
> **⬇ export** in the top bar downloads the whole thing as JSON.

## Tech stack

React 19 · Vite 6 · D3 (geo, zoom, force) · TopoJSON · IndexedDB via `idb` · CSS Modules.

Fonts: Inter (UI), Newsreader (display), IBM Plex Mono (tabular figures — years and counts hold
their width while scrubbing).

**Why D3 and not a charting library.** D3 is 13 functions across 2 files here; tree-shaking
already strips everything unused, and ~73% of the JS bundle is `seed.json`, not library code.
The map renders as React `<path>` elements with D3 doing only the projection maths — which keeps
per-country CSS classes, handlers and transitions that a canvas charting library would take away.

## Data model

Conflicts, countries and notes live in IndexedDB, seeded once from `src/data/seed.json`. Seed data
is versioned: bumping `version` re-imports new entries on a returning visitor's next load.

A **conflict** aggregates **events**:

```
conflict  id · title · type · severity(1-5) · startDate/endDate/ongoing · status
          description · parties[{countryId, role}] · involvedCountries[] · aliases[] · tags[]
          statusHistory[] · lastCheckedAt
  └ event id · date · title · kind · severity(1-5) · location{lat,lng,label}
          description · sources[] · parties[] · independentSources · crossAlignment
```

This is the key structural idea: **the atomic unit is a sourced event**, which either attaches to
an existing conflict or founds a new one. "Something happened today" and "we're missing something
from 1975" become the *same operation*.

Controlled vocabularies live in `src/utils/taxonomy.js` and are mirrored by the pipeline's
`schema.py`. A test (`tests/test_taxonomy_sync.py`) fails if they drift.

---

# The AI updater

Lives in [`ai-updater/`](ai-updater/). A team of narrow LLM agents plus web search that keeps the
dataset current and honest. The credibility of this project is data rigour, not UI.

## What it is

**One operation: `scan(period, region?, topic?)`.** The only input is a time window — a day or a
century, same protocol, same agents. `scan("1924..2024", region="Africa")` fills a century;
the daily cron scans one day.

**The unit of work is a day, and the question is always the same: have we checked this one yet?**
A day the coverage ledger records as checked is skipped. A day that failed, or that search could
not see, is retried. A day that can never be searched is left behind after a few attempts so it
cannot stall everything queued behind it.

The day it scans is deliberately about a week behind today, and that is structural rather than a
delay for its own sake: an event newer than `T_SETTLE_DAYS` is marked *provisional* and excluded
from the applied set, so a job scanning "today" would run forever and never add anything. The lag
also gives claims time to be corroborated or retracted before they are recorded.

## The agent team

Five focused prompts, strict JSON out. **Three LLM calls per candidate** (plus two per scan):

| Stage | Job | Answered by |
|---|---|---|
| **Scoper** | window → search queries (multi-language) | LLM — writing |
| **Triage** | which of ~70 fetched articles report a datable event | **judge** — one parallel call |
| **Extractor** | the surviving articles → dated candidate events | LLM — writing |
| **Resolver** | which existing conflict this belongs to, or none | **judge** — one Choice |
| **Enrich** | kind · type · severity · roles · status | **judge** — all in one call |
| | the one-sentence summary | LLM — writing |
| **Verify** | verdict + how sure it is | **judge** — Choice + calibrated confidence |

**The split is the design: anything that is a choice, a score or a confidence goes to a typed
model; the LLM keeps only prose.** It is not stylistic. `AUTO_APPROVE_CONFIDENCE` gates everything
this pipeline publishes on one number, and when an LLM writes `confidence: 0.85` that is a token
it generated — nothing ties it to being right 85% of the time. A System One model derives
confidence from the probability distribution over the options. Set `JUDGE_BACKEND=none` and every
judgement falls back to the LLM.

Deterministic code — not the LLM — does fetching, candidate dedup, geocoding (Nominatim),
source-linking, span derivation and the merge. `dedup.py` narrows 240 conflicts to ≤5 plausible
matches *before* any LLM sees the problem.

## What makes it trustworthy

1. **No dead-ends.** Every decision node has exactly three outcomes: proceed, drop-as-noise, or
   escalate to the human review queue. Nothing is silently invented or dropped.
2. **Quiet ≠ resolved.** Status is a type-aware state machine (`active · easing · suspended ·
   dormant · ended · resolved`) driven by `config/lifecycle.yml`. `resolved` needs a *positive*
   terminal event; any resumption snaps back to `active`. Only the **latest** event may move
   status, so backfilling an old battle can't reopen a finished war.
3. **Tiered trust.** Founding a new conflict needs a strictly higher bar than attaching an event
   (confidence ≥ 0.9 + ≥3 independent sources + cross-alignment, vs ≥ 0.8) — a wrong new conflict
   is far harder to undo.
4. **Multilingual, anti-bias sourcing.** `config/sources.yml` tags outlets by alignment. A
   contested claim only enters if corroborated **across alignments**; disagreements are
   attributed, not adopted.
5. **Coherent writes only.** After folding proposals in, `merge.validate()` re-checks the whole
   dataset (parties ⊆ involvedCountries, ISO dates, severity 1–5, no `ongoing && ended`). On any
   issue *this run introduced*, it writes nothing and exits non-zero. Pre-existing issues are
   tolerated, so the gate blocks regressions without demanding perfection first.
6. **Everything is reversible** — git history is the undo log.

## Running the pipeline

```bash
cd ai-updater
python -m pytest                      # 136 offline tests — no API key needed

pip install -r requirements.txt
cp .env.example .env                  # add your keys

python -m conflict_updater "1990..2003" --region Africa   # scan: fill the past
python -m conflict_updater auto cursor --days 1           # the daily run
#   → read out/review_*.md, then:
python -m conflict_updater apply out/proposals_*.json --approve 1 3 5
python -m conflict_updater apply out/proposals_*.json --dry-run   # report only

python -m conflict_updater auto cursor --days 1 --limit 5 --dry-run   # what the cron runs
python -m conflict_updater coverage               # what's been searched, and how it came back
python -m conflict_updater eval "2024..2026"      # backtest against curated events
python -m conflict_updater serve                  # local control panel
```

`scan` writes to `out/`: `proposals_*.json` (machine-readable) and `review_*.md` (the human queue
— only uncertain or contested items need you).

### Configuration

Key `.env` settings:

| Variable | Notes |
|---|---|
| `LLM_PROVIDER` | `openrouter` · `openai` · `google` |
| `LLM_MODEL` | **Accepts a comma-separated fallback chain**: `primary:free,backup:free` |
| `SEARCH_BACKEND` | `tavily` · `none` |
| `AUTO_APPROVE_CONFIDENCE` | default `0.8` — see [Evaluation](#evaluation) before trusting it |
| `LLM_CACHE` | `off` (default) · `on` — content-addressed response cache |

> **Pin a fallback chain.** Nine consecutive runs once died because a single pinned free
> model slug was withdrawn by the provider and there was nothing to fall back to. Later entries in
> the chain are tried only when the earlier one is gone or exhausted — never for a bad prompt,
> which would just burn a second quota.

### Resilience

- A failure on one candidate is recorded and the scan **continues** — one bad LLM call costs a
  single event, not the whole run's spent quota.
- A scan that dies entirely still writes a `failed` row to the coverage ledger before exiting, so
  a dead day is visible rather than silent.

## Evaluation

The pipeline was well-engineered but **completely unmeasured** for a long time — writing to a
public dataset on the strength of a confidence threshold nobody had validated. That's what
`eval` is for.

**The unlock:** `seed.json` already holds ~490 hand-curated, fully-sourced events. That's a
labelled evaluation set that cost nothing to produce.

```bash
python -m conflict_updater eval "2024..2026" --limit 20
```

It removes every event in the window from the base the pipeline reads, scans that window, and
scores what comes back:

```
  extraction   precision 0.812  recall 0.640  F1 0.716
  resolution   accuracy  0.900
  event kind   accuracy  0.750
  severity     within ±1 0.850

  Verify calibration (stated vs observed):
    range        n   stated   observed
    0.80-0.90   12    0.85     0.583  << overconfident
```

Two things make or break the honesty of these numbers, and both are handled:

- **Hold-out is mandatory.** If the gold events stay in the base, the Resolver correctly answers
  "known" and drops them, and the run measures nothing. Conflicts left with no events are removed
  entirely, so the pipeline doesn't get a free attach target it never earned.
- **Expectations differ per event.** An event whose conflict survives pruning should *attach*; one
  whose conflict vanished should found a *new* one. Scoring them identically would punish the
  pipeline for being right.

**Calibration is the highest-value metric.** The whole auto-approve gate is one inequality
(`confidence >= AUTO_APPROVE_CONFIDENCE`). If the model's stated 0.8 doesn't correspond to being
right 80% of the time, that threshold is arbitrary. Free reasoning models are typically
overconfident. Measure before trusting it; the fix, if needed, is just moving the number.

What this measures well: **resolution and enrichment**. What it measures only loosely:
**extraction on historical windows** — searching the web today for 1962 returns retrospective
encyclopaedia coverage, not contemporaneous reporting. Recent windows are the honest test of the
full daily path.

Each run writes `out/eval_*.json` stamped with the **prompt version** (a hash of every prompt
constant) and model, so a change in quality can be attributed to a prompt edit. The `missed` list
names exactly which curated events the pipeline failed to rediscover — that's where prompt work
should start.

**Running one without a terminal:** Actions → *Evaluate the agents* → **Run workflow**, pick a
window, go. It publishes the headline numbers to the site's Pipeline page, prints them on the
run's own summary, and attaches the full report (including the misses) as an artifact. It also
runs itself monthly on the 15th.

It is a *separate* workflow from the daily update for quota reasons, not tidiness: a scan costs
~`2 + 3N` LLM calls, so the daily job at `--limit 5` spends ~17. Running an eval in the
same job would push a free tier past a typical ~50/day allowance and fail both.

> Turn `LLM_CACHE=on` (the default for `eval`) so replaying a backtest after a prompt tweak only
> pays for the calls that actually changed.

## Coverage ledger

Search *samples* — it can never tell you "I found everything." So every scan appends to
`out/coverage.json`, turning silence into a record:

- **found** — events surfaced.
- **quiet** — searched a real article pool, nothing extractable (genuinely quiet or already covered).
- **blind** — search returned **0** results: *unknown*, a source gap — **not** proof nothing happened.
- **failed** — the scan itself errored. The truest possible blind.

A snapshot is published to `src/data/coverage.json` and shown on the app's Help page, so the site
is honest about where its coverage is thin.

## Architecture decisions

**LangChain is kept, deliberately thinly.** Its entire surface here is five symbols
(`ChatOpenAI`, `ChatGoogleGenerativeAI`, `SystemMessage`, `HumanMessage`,
`with_structured_output`), and the OpenRouter path bypasses its structured output altogether —
many free models ignore native `response_format` and emit markdown or reasoning prose, so JSON is
requested in the prompt and parsed here. LangChain earns its place as a provider adapter and
nothing more. Dropping it for direct SDK calls is defensible cleanup, not a fix.

**LangGraph is *not* used, on purpose.** LangGraph manages state machines with branching, cycles
and durable checkpoints. This flow is strictly linear with one loop — no conditional routing
between agents, no agent calling another, no cycle. The two features that would genuinely apply
are cheaper to get directly: checkpointing is a `try/except` plus the response cache, and
human-in-the-loop is already a file-based review queue that is inspectable, diffable, and survives
a restart. Adopting it would add a DSL and subtract readability.

**Every external service sits behind Protocol + factory + Null** (`search`, `geocode`,
`structured_source`, `llm`, `cache`), which is why 136 tests run fully offline with no API keys.

**The Resolver is *not* skipped when dedup returns no candidates,** even though that would save a
call per new event. It would make a 0.25-threshold fuzzy heuristic the sole authority on founding
new conflicts — the most expensive error the pipeline can make.

### Layout

```
conflict_updater/
  schema.py           pydantic models (domain + every agent's I/O)
  prompts.py          one system prompt per agent + prompt_version()
  agents.py           the five agents
  dedup.py            deterministic candidate finder (the cheap half of the Resolver)
  pipeline.py         scan() — discovery, with per-candidate failure isolation
  merge.py            apply()/validate() — the coherent write-back into seed.json
  evaluate.py         backtest harness: hold-out, matching, metrics, calibration
  cache.py            content-addressed LLM response cache (SQLite)
  llm.py              swappable LLM client + model fallback chain
  search.py           swappable web search + outlet alignment tagging
  geocode.py          Nominatim lookup           structured_source.py  UCDP/ACLED anchors
  lifecycle.py        per-type status profiles   store.py  seed I/O + coverage ledger
  config.py           env settings               cli.py / __main__.py  entrypoints
  server.py           local control panel
config/  lifecycle.yml · sources.yml
tests/   136 offline tests with fakes
```

---

# Deploying & operations

A static single-page app — all user data lives in the browser — so it hosts anywhere:

- **GitHub Pages** — what the live site uses; `.github/workflows/deploy.yml` builds and publishes.
- **Netlify** — connect the repo; `netlify.toml` is already set up.
- **Vercel** — zero config; auto-detects Vite.

**Actions is independent of Pages.** The daily pipeline runs on a cron and commits to the repo
regardless of where the site is hosted, so changing host costs exactly one workflow file.

## Where each run's output lives

The pipeline produces three kinds of output, and they deliberately go to three different places:

| Output | Destination | Why |
|---|---|---|
| `seed.json`, `coverage.json` | **Committed to the repo** | The site bundles these at build time, so they have to be in git |
| Full digests, proposals, eval reports | **Actions artifact** (90 days) | Persistent and downloadable, but never pushed — the repo stays the dataset, not a log store |
| A rendered run report | **Actions job summary** | Read it on the run's own page; nothing is stored in git at all |

The **Pipeline view** in the app renders the committed coverage ledger as an operations log:
last run, what was applied, what's held back, which windows came back blind, and which failed.
It's visible to everyone — the atlas's claim is data rigour, and most projects making that
claim can't show their working.

### Why the dataset is in git rather than a database

Committing data feels odd, but for this project it's the right call. The dataset is ~550KB,
append-mostly, and its entire value is **provenance** — git gives versioned, attributable,
revertible history of every change for free, which is exactly the property a conflict atlas
needs. A database would buy querying, which nothing here needs (the app loads the whole dataset
into IndexedDB anyway), in exchange for infrastructure to run, secure and back up.

A container would be a step backwards for the persistence worry specifically: container
filesystems are ephemeral, so anything written inside one is lost on restart unless you attach a
volume or an external DB. Free container tiers also sleep. Git already gives durable, versioned
storage with none of that.

**When to revisit:** the moment you want shared server-side state, real authentication, or an
approve-from-the-browser review flow. That needs a backend, and the natural step is Cloudflare
Pages + Workers or Netlify Functions — not a container.

# Troubleshooting

**`Cannot find native binding` for rollup or oxlint on Windows** — a known npm bug
([npm/cli#4828](https://github.com/npm/cli/issues/4828)) that sometimes skips optional native
binaries. Both are listed under `optionalDependencies` and skipped harmlessly on macOS/Linux. The
oxlint binding is **pinned to oxlint's exact version** — they ship in lockstep and a caret range
resolves to a binding the wrapper can't load. If it breaks:

```bash
rm -rf node_modules package-lock.json && npm install
```

**A run failed** — check `src/data/coverage.json` for a `failed` row; it carries the error, and
the cursor retries that day on the next run.
The run is also red in the Actions tab.

# Data, sources & disclaimer

This is an **educational tool**, not an authoritative record. Entries are compiled from widely
available historical summaries — deliberately concise, and for some events the casualty figures
and even the classifications (what counts as a "genocide") are **genuinely debated by historians**.
Pre-modern events are mapped onto modern successor states, which is a simplification.

Treat every entry as a prompt for your own further reading, and check the cited sources rather
than the summary. Nothing here represents an official position.

- Map geometry: [Natural Earth](https://www.naturalearthdata.com/) via
  [world-atlas](https://github.com/topojson/world-atlas) (public domain).
- Built with [D3](https://d3js.org/), [React](https://react.dev/) and [Vite](https://vite.dev/).

# License

[MIT](LICENSE) © Yasser Bouhai. The licence covers the **code**; historical facts are not
copyrightable.

Version history: [CHANGELOG.md](CHANGELOG.md).
