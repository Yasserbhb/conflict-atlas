# AI updater — architecture review and evaluation plan

Analysis only; nothing in this document has been implemented. Written against the pipeline as
it stands on `main` (2107 lines of Python across `conflict_updater/`, 81 passing tests).

Everything below is grounded in the code as read, not in assumptions. Where I'm uncertain,
I say so.

---

## 1. Verdict up front

The architecture is **sound and unusually disciplined for a hobby pipeline**. The agent split is
clean, the deterministic/LLM boundary is drawn in the right place, and the trust gating is more
careful than most production systems I've seen.

The problems are not architectural. They are:

1. **No evaluation of any kind.** Nothing measures whether the pipeline is right. This is the
   single biggest gap and everything in §5 is about closing it.
2. **No failure isolation.** One bad LLM call discards the whole scan.
3. **Failures are invisible.** Nine consecutive dead weeks left no trace in the ledger that
   exists specifically to record coverage gaps.

Nothing here calls for a rewrite. The fixes are additive.

---

## 2. Stack assessment — are we using reasonable libraries?

| Library | Verdict | Notes |
|---|---|---|
| **pydantic** ≥2.7 | **Right tool.** | 5 import sites. Models double as LLM output schemas and as the seed.json contract. This is exactly what pydantic is for. |
| **langchain-core / -openai / -google-genai** | **Working, but very thinly used.** | See below. |
| **langchain-community** | **Dead — remove.** | Declared in `requirements.txt`, **zero import sites**. Pulls a large transitive tree for nothing. |
| **tavily-python** | Fine. | Single integration point behind a Protocol, swappable, faked in tests. |
| **httpx / python-dotenv / pyyaml** | Fine. | Each used, each small. |
| **fastapi / uvicorn** | Fine, and correctly scoped. | Local control panel only; never on the cron path. |
| **pytest** | Fine. | 81 tests, fully offline/keyless. |

### How much LangChain are we actually using?

Measured, not guessed — the entire surface is **five symbols**:

```
ChatOpenAI · ChatGoogleGenerativeAI · SystemMessage · HumanMessage · with_structured_output
```

And `with_structured_output` is used on **one** code path. The OpenRouter path sets
`self._prompted = True` and bypasses LangChain's structured output entirely in favour of
hand-rolled JSON extraction (`_extract_json`, `llm.py:82`) — because free models ignore native
`response_format`.

So LangChain is earning its place as **a provider-shaped adapter and nothing else**. Two honest
options:

- **(a) Keep it.** It works, maintenance is near-zero, and swapping providers is a one-line
  config change. The dependency weight is the only cost, and it isn't currently hurting anything.
- **(b) Drop it** for direct `openai` + `google-genai` SDK calls. Removes three packages and a
  heavy transitive tree at a cost of roughly 40 lines in `llm.py`.

**Recommendation: (a), keep it** — but delete `langchain-community`. Option (b) is defensible
cleanup, not a fix; it buys dependency hygiene and no functional improvement, and `llm.py` is
already the most carefully-written module in the package. Don't spend risk there.

### Should we move to LangGraph?

**No.** Being specific about why, since it's a fair question.

LangGraph exists to manage **state machines with branching, cycles, and durable checkpoints**.
The scan flow is none of those things — it is strictly linear with one loop:

```
scoper → extractor(+structured) → sort/cap → for each candidate:
                                               resolver → enrich → [verify] → proposal
                                           → merge.validate → write
```

There is no conditional routing between agents, no agent that calls another, no cycle, no
negotiation. `pipeline.py:scan()` is a readable 180-line function that any developer can follow
top to bottom. Rewriting it into a graph DSL would make it *harder* to read in exchange for
capabilities it doesn't use.

Two LangGraph features *would* genuinely apply, and both are cheaper to get directly:

- **Durable checkpointing** — maps onto the "one failure kills the scan" bug (§3.1). A
  `try/except` around the candidate loop solves it in ~6 lines.
- **Human-in-the-loop interrupts** — maps onto `needs_human`. But that's already implemented as
  a file-based review queue (`review_*.md` + `--approve N M`), which is inspectable, diffable,
  and survives a process restart. A framework interrupt would be a downgrade.

**Verdict: adopting LangGraph here would be resume-driven architecture.** Revisit only if agents
ever need to call each other or re-run conditionally.

---

## 3. What's broken

### 3.1 One failure discards the entire scan — *highest severity*

`pipeline.py:140` — the per-candidate loop has **no `try/except`**. If the LLM fails on candidate
7 of 12, candidates 1–6 are thrown away along with the API quota already spent on them.

This is not hypothetical. It is why every weekly run since 2026-07-20 produced nothing at all
rather than partial results.

**Fix shape:** wrap the loop body; on exception, record the candidate in `dropped` with the error
and continue. Roughly 6 lines. A partial scan is enormously more useful than no scan.

### 3.2 The coverage ledger cannot see failures — *highest severity*

`cli.py:97-98`:

```python
result = scan(...)              # raises
append_coverage(...)            # never reached
```

`append_coverage()` runs *after* `scan()` returns, so a crashed scan writes **nothing**.

The consequence is worse than a missing row. The Help page's "Data coverage" table — the feature
built specifically to show users where coverage is thin — currently displays three rows dated
**2026-07-05** and gives no indication the pipeline has been dead for two months. It is
silently asserting completeness it doesn't have.

Evidence:

```
src/data/coverage.json   3 entries, all 2026-07-05, all manual historical scans
ai-updater/log/          1 digest:  2026-07-06_2026-07-13.md
GitHub Actions           runs #3–#11 (2026-07-20 → 2026-09-14) all failure
```

Nine dead weeks, zero trace.

**Fix shape:** move `append_coverage()` into a `finally`, and give the ledger a `status: "failed"`
state carrying the error. The three-state vocabulary (`found`/`quiet`/`blind`) already has a
natural slot for it — a failed scan is the truest possible "blind".

### 3.3 Nothing alerts on failure

Nine consecutive red runs went unnoticed for two months. GitHub emails on workflow failure by
default, so the signal exists but isn't reaching anyone. Cheapest durable fix: a step with
`if: failure()` that writes a `status: failed` ledger entry and commits it — the failure then
surfaces on the site itself rather than only in an inbox.

### 3.4 Single pinned model, no fallback

`LLM_MODEL=openai/gpt-oss-120b:free`. OpenRouter withdrew the `:free` variant, the pipeline
404'd, and there was no secondary to fail over to. A provider/model fallback chain (try the free
slug, fall back to a second free model, then to a paid one if a key is present) would have
degraded rather than died.

---

## 4. What's good — keep it

Worth stating plainly, because these are the parts a rewrite would be likely to destroy:

- **Deterministic-first dedup.** `dedup.py` narrows 240 conflicts to ≤5 candidates with pure
  Python (fuzzy title match, token overlap, actor hits, date plausibility) *before* any LLM sees
  the problem. Cheap, unit-tested, and it makes the Resolver's job tractable.
- **Tiered trust.** Founding a new conflict requires a strictly higher bar than attaching an
  event to an existing one (`new_conflict_min_confidence` 0.9 + `min_sources` 3 +
  `cross_alignment`, vs `auto_approve_confidence` 0.8). The asymmetry is correct — a wrong new
  conflict is much harder to undo than a wrong event.
- **The coherence gate.** `merge.validate()` runs before *and* after apply, and writes only if
  the diff introduces no new issues, while tolerating pre-existing ones. This is a genuinely
  good pattern — it blocks regressions without demanding the dataset already be perfect.
- **Status transitions are constrained.** Only the latest event may move a conflict's status
  (`_is_latest_event`), so backfilling old events can't resurrect a finished war.
- **Protocol + factory + Null across every external service.** Search, geocode, structured
  source, LLM. Every one is swappable and faked in tests, which is why 81 tests run offline
  with no API keys.
- **Everything is reversible.** Git history is the undo log.

---

## 5. Evaluation — the real gap

**Nothing currently measures whether any of this is correct.** The 81 tests verify plumbing
(does `merge.apply` emit the right keys?), not judgement (is the severity right? did we attach
to the right conflict?). Every quality claim about the pipeline today rests on spot-checking.

### 5.1 Ragas is mostly the wrong frame

Ragas is built for RAG question-answering, and its headline metrics assume a retrieval corpus
with relevance labels and a question/answer pair. Mapping honestly:

| Ragas metric | Applies here? |
|---|---|
| `faithfulness` — is the answer supported by retrieved context? | **Yes, directly.** "Is this event summary supported by its cited sources?" is exactly the Verify agent's job, and an independent judge scoring it would tell you whether Verify works. |
| `answer_relevancy` | Weakly. There's no user question to be relevant to. |
| `context_precision` / `context_recall` | **No.** These need per-query relevance labels over a fixed corpus. The pipeline searches the live web; there is no corpus and no labels. |
| `answer_correctness` | Partially — becomes useful once there's a gold set (§5.2). |

So: borrow **faithfulness**, and build the rest around the fact that each stage is a
**standard ML task with a standard metric**, not a RAG query.

### 5.2 The unlock: seed.json is already a gold set

This is the most important point in the document.

```
240 conflicts · 489 events · 489/489 events carry sources
by century:  15xx 7 · 16xx 14 · 17xx 26 · 18xx 59 · 19xx 276 · 20xx 107
```

Every one of those events was hand-curated and source-verified. That is a labelled evaluation set
that already exists and **cost nothing to produce**.

**The backtest:** hold out every event in a window (say 1962–1968), remove those events from the
seed the pipeline reads, run a scan scoped to that window, and measure what it recovers.

Two caveats that must be designed around, or the numbers will lie:

- **Hold-out is mandatory.** If the events are still in the seed, the Resolver correctly answers
  "known" and drops them — you'd measure nothing. The eval harness must run against a pruned copy
  of the seed, never the live one.
- **Historical windows are not like live weeks.** Searching the web today for 1962 returns
  retrospective encyclopaedia coverage, not contemporaneous reporting. So backtest scores measure
  *resolution and enrichment* quality well, and *extraction* quality only loosely. Recent windows
  (2024–2026, where 107 events sit) are the honest test of the full weekly path.

### 5.3 Per-stage metrics

| Stage | Task type | Metric | Gold source |
|---|---|---|---|
| Scoper | query generation | downstream recall — did its queries surface the held-out events at all? | backtest |
| Extractor | information extraction | event-level precision / recall / F1, matched on date + fuzzy title | backtest |
| Resolver | 4-class decision (`known`/`attach`/`new`/`ambiguous`) | confusion matrix + per-class F1 | backtest — the correct conflict id is known |
| Enrich | multi-label classification | per-field accuracy: `type`, `kind`, `severity` (±1 tolerance), party roles | backtest |
| Verify | calibrated binary decision | **Brier score + calibration curve** | human approve/reject stream |
| Geocode | coordinate lookup | median km error vs the event's known location | backtest |
| End-to-end | the one that matters | % of auto-approved events that survive human review | review queue |

### 5.4 Calibration is the highest-value single metric

The entire auto-approve gate is one inequality:

```python
needs_human = ver.confidence < settings.auto_approve_confidence   # 0.8
```

**Nobody has ever checked whether the model's stated 0.8 corresponds to being right 80% of the
time.** If it's overconfident — and free reasoning models generally are — then 0.8 is an
arbitrary number and things are being written to `seed.json` on a threshold that means nothing.

This is measurable with data the pipeline *already produces*: every `needs_human` item a human
later approves or rejects is a label. Bucket by stated confidence, plot observed accuracy, and
compare to the diagonal. A few dozen labelled decisions is enough to see gross miscalibration.

If it turns out miscalibrated, the fix is trivial (move the threshold) — but you cannot know
without measuring, and the threshold is currently load-bearing for data quality.

### 5.5 Prerequisites that make evaluation cheap

Two small pieces of infrastructure turn evaluation from "expensive and irreproducible" into
"nearly free and repeatable". Both are worth having regardless.

**A response cache.** Content-address every LLM call (`hash(model + system + user) → response`)
to a local store. Consequences:
- An eval re-run after a prompt tweak only pays for the calls that actually changed.
- A crashed scan resumes without re-paying for completed candidates (also mitigates §3.1).
- Runs become reproducible, which is a precondition for trusting any A/B comparison.
- ~30 lines; `temperature=0` is already set, so caching is semantically safe.

**Prompt versioning.** `prompts.py` carries no version stamp, so a quality change today cannot be
attributed to a prompt change. Hash the prompt constants at import and record that hash in each
digest and coverage entry. Then "quality dropped in week 9" becomes answerable.

### 5.6 Suggested order

1. Fix §3.1 and §3.2 first — without failure isolation and honest coverage logging, every
   measurement downstream is taken on unreliable ground.
2. Response cache + prompt hash (§5.5) — makes everything after this cheap.
3. Calibration on the existing human-decision stream (§5.4) — highest insight per unit of work,
   needs no new infrastructure.
4. Backtest harness on a recent window (§5.2) — the real quality number.
5. Per-stage metrics (§5.3) — once the harness exists, these are mostly bookkeeping.

---

## 6. Performance / cost notes

- **Call math is `2 + 3N`** (scoper + extractor, then resolver/enrich/verify per candidate).
  At `--limit 12` that's 38 calls, all sequential — 36 serial round-trips dominate wall time.
- **Full parallelism is not available.** `pending_bases` must be visible to later candidates so
  a second event for a newly-founded conflict attaches rather than duplicating. That's a real
  ordering dependency, correctly noted in the code. A bounded thread pool over *independent*
  candidates is possible but fiddly, and free-tier rate limits blunt the benefit.
- **The Resolver is called even when `dedup.find_candidates()` returns empty.** With nothing to
  compare against it can only answer "new", so that call is largely wasted. Skipping it saves one
  call per genuinely-new event — but it also produces `new_aliases`, which would be lost. A real
  trade-off, not free; worth measuring before deciding.
- **No token or cost accounting** anywhere. Given free-tier quotas are the binding constraint,
  counting tokens per stage would show where the budget actually goes.

---

## 7. Summary

**Keep:** the architecture, the agent split, deterministic-first dedup, tiered trust, the
coherence gate, Protocol+factory+Null, pydantic.

**Remove:** `langchain-community` (dead dependency).

**Don't adopt:** LangGraph — the flow is linear; it would add a DSL and subtract readability.

**Fix:** failure isolation (§3.1), coverage-ledger blindness (§3.2), failure alerting (§3.3),
model fallback (§3.4).

**Build:** the evaluation harness (§5) — starting with calibration, because the auto-approve
threshold is load-bearing and entirely unverified.

The honest headline: this pipeline is well-engineered and completely unmeasured. It has been
writing to a public dataset on the strength of a confidence threshold nobody has ever validated.
Measuring that is worth more than any optimisation listed here.
