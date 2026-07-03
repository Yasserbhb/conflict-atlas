# AI Updater — the conflict-ingest pipeline

> **This branch (`ai-updater`) is the home of the automated updater**, built standalone first and
> coupled to the app later. Working here = working on the pipeline, not the React app.
> The full design of record is **[ARCHITECTURE.md](ARCHITECTURE.md)** — read that.

A team of narrow AI agents + web search that keeps the Conflict Atlas dataset **current and
honest**, and can also **fill the past** on demand. This is the credibility leap: world-class =
data rigor, not UI.

## The shape in one screen

- **Built on the events model.** The app now models a conflict as an aggregation of `events[]`.
  The pipeline's atomic output is a **sourced event** that either **attaches to an existing
  conflict** or **spawns a new one**. So "something happened today" and "we're missing something
  from 1975" are the *same operation*.

- **One operation: `scan(period, region?, topic?)`.** The only input is a time window — a week or
  a century, **same protocol, same agents**. `scan([1924,2024], "Africa")` fills a century;
  `scan([last_monday, today])` is the routine update. The weekly job is just an **automatic caller
  of the same function** with `period = last 7 days`. Recency is a per-event rule, not a mode: an
  event dated in the last ~7 days is held as *provisional* until it corroborates.

- **The agent team** (each one lane, strict JSON out): Scoper · Extractor · Resolver (dedup) ·
  Classifier (kind/type) · Severity · Roles · Geolocator · Summarizer · Lifecycle · Fact-check ·
  Reconciler. Deterministic code does fetch / shape-check / dedup-lookup / merge.

## The four things that make it trustworthy

1. **No dead-ends.** Every decision node has exactly three outcomes: proceed, drop-as-noise, or
   **escalate to a human review queue**. If it isn't sure, a human decides — nothing is silently
   invented or dropped, and nothing merges without approval.
2. **Quiet ≠ resolved.** A ceasefire/pause is not an end; status is a **type-aware** state machine
   (active · easing · suspended · dormant · ended · resolved). `resolved` needs a *positive*
   terminal event; any resumption snaps back to `active`. This is the "call it *ended* vs
   *de-escalation*" logic.
3. **Multilingual + anti-bias sourcing.** Sources in their **original languages** across the
   political spectrum; a contested claim (casualties, who-started-it, "genocide") only enters if
   corroborated **across alignments**, and disagreements are *attributed*, not adopted.
4. **Same rubric as the app.** type/severity/role/kind all follow `src/utils/taxonomy.js` +
   `utils/eventKinds.js`, so machine and human classify identically.

## Dedup is the hard core

Before creating anything, the **Resolver** asks: is this already in the base — possibly under a
different name? Match by title/**aliases**/parties/region/date-overlap → *already-known* /
*attach* / *new* / *ambiguous→human*. Same event, many languages, many names.

## Build order

Phase 1 is **backfill on one region/decade** — the safest place to trust-test the whole agent
team, because its answers are checkable against known history before it ever runs unattended.
Then merge, then watch-mode, then multilingual hardening. See ARCHITECTURE.md §12.

## Run it (Python)

The Phase-1 pipeline is implemented in `conflict_updater/`.

```bash
cd ai-updater
python -m pytest              # 12 tests, offline (fake LLM + search — no API key)

pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY (+ TAVILY_API_KEY)
python -m conflict_updater "1990..2003" --region Africa   # fill the past
python -m conflict_updater week                           # the routine update
```

Output lands in `out/`: a `proposals_*.json` (machine-readable, to feed into `seed.json`) and a
`review_*.md` (the human queue — only the uncertain/contested items need you). Layout:

```
conflict_updater/
  schema.py    pydantic models (domain + every agent's I/O)
  prompts.py   one system prompt per agent
  agents.py    the agent team (scoper/extractor/resolver/enrichers/factcheck/reconciler)
  dedup.py     deterministic candidate finder (the cheap half of the Resolver)
  pipeline.py  scan() — the one operation
  llm.py       swappable LLM client (OpenAI default)   search.py  swappable web search
  store.py     load seed.json + write proposals/review   config.py  env settings
tests/         offline tests with fakes
```

---
*Status: design locked; Phase-1 pipeline implemented in Python & offline-tested; a live run needs
an API key. Origin & requirements: project memory `project_agentic_pipeline`.*
