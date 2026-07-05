# AI Updater — Pipeline Diagram

The whole `scan → review → apply` loop at a glance. Details live in [ARCHITECTURE.md](ARCHITECTURE.md).

**Legend:** `[box]` = LLM agent · `([rounded])` = deterministic code · `{{hex}}` = external API ·
`[(cyl)]` = file on disk · `{diamond}` = branch · `-->` data flow · `-.->` context supplied alongside.

```mermaid
flowchart TD
    IN[["scan(period, region?, topic?)"]]
    SEED[("seed.json")] --> BASE(["load_base()"])
    IN -.-> SCOPER
    BASE -.->|watch ids| SCOPER

    SCOPER["① Scoper — multi-lang queries"] --> FETCH
    TAVILY{{Tavily}} --> FETCH(["② Fetcher"])
    FETCH --> EXTRACT["③ Extractor — dated events"]
    EXTRACT --> DEDUP(["④ dedup"])
    DEDUP --> RESOLVE["④ Resolver"]
    BASE -.->|existing events| RESOLVE

    RESOLVE -->|known| DROP(["⛔ dropped"])
    RESOLVE -->|ambiguous| HUMAN["🧑 human review"]
    RESOLVE -->|attach / new| GATE{"⑤ too recent?"}
    GATE -->|yes| PROV(["provisional"])
    GATE --> ENRICH(("⑥ enrich"))
    PROV --> ENRICH

    subgraph ENR["enrichers — one lane each"]
        CLS["Classifier — kind/type"]
        SEV["Severity — 1–5"]
        ROL["Roles — structural"]
        GEO["Geolocator — place"]
        SUM["Summarizer"]
        LIFE["Lifecycle — status"]
        SPAN["Span — dates, new only"]
    end
    ENRICH --> CLS & SEV & ROL & GEO & SUM & LIFE & SPAN
    BASE -.->|parent type / roles / status| ROL
    GEO --> NOM{{Nominatim}} --> LOC(["real coords"])
    FETCH -.->|all items| SRC(["_gather_sources()"])

    EVENT[["Event"]]
    CLS & SEV & ROL & LOC & SUM & SRC & LIFE --> EVENT
    EVENT --> FC["⑦ Fact-check"] --> REC["⑧ Reconciler"] --> DEC{"needs_human?"}
    DEC -->|no| AUTO(["✅ auto-approved"])
    DEC -->|yes| HUMAN

    AUTO --> PROP[["Proposal"]]
    HUMAN --> PROP
    SPAN -.->|new-conflict dates| PROP
    PROP --> OUT[("out/proposals + review")]

    OUT -.->|you approve| MERGE(["🔀 merge.apply → validate"])
    MERGE -->|pass| SEEDOUT[("seed.json ✔ version bump")]
    MERGE -->|fail| REJ(["❌ nothing written"])
```

## Does each agent know the goal? (the "is it blind?" table)

| Agent | Atlas framing? | Extra context it gets |
|---|---|---|
| Scoper | ✓ | existing conflict ids to watch |
| Extractor | ✗ | the window's date bounds |
| Resolver | ✓ | candidate conflicts + **their existing events** |
| Classifier | ✗ | parent conflict's **type** |
| Severity | ✗ | evidence snippets |
| Roles | ✗ | parent **type + existing parties/roles** |
| Geolocator | ✗ | — (names a place; Nominatim gives the coords) |
| Summarizer | ✓ | evidence snippets |
| Lifecycle | ✗ | today, event date, conflict start/end, status |
| Span | ✗ | source snippets (new conflicts only) |
| Fact-check | ✗ | the sources linked to the event |
| Reconciler | ✗ | the fact-check verdict |

Only 3 of 12 steps state the mission explicitly — a shared mission preamble is a possible follow-up.

## Tools

| Tool | Used by | Cost |
|---|---|---|
| **LLM** (OpenRouter / Gemini / OpenAI, swappable) | every agent | free tier or pennies |
| **Tavily** | Fetcher | free tier (~1000/mo) |
| **Nominatim (OpenStreetMap)** | coordinate lookup | free, no key |

## Data flow

`RawItem` → `CandidateEvent` → `Event` → `Proposal` → folded into `seed.json` by `merge.py`.

**The invariant:** every exit (`dropped`, `human review`, `nothing written`) is named and logged —
never a silent guess. Nothing reaches `seed.json` without `merge.validate()`, and nothing
auto-approves without passing fact-check + the reconciler.
