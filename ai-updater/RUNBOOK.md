# AI Updater — Runbook (how to actually run it)

The loop is **three commands: `scan` → review → `apply`**. Nothing touches your app's
`seed.json` until *you* run `apply`. Run everything from the `ai-updater/` folder.

```
cd C:\Users\yasse\Desktop\map\ai-updater
```

---

## 0. One-time setup

```powershell
pip install -r requirements.txt
copy .env.example .env      # then edit .env: put in your LLM key + Tavily key
```

`.env` points at the real dataset by default (`SEED_JSON=../src/data/seed.json`), so
`apply` writes straight into the app. That's intended — that IS the integration.

---

## 1. SCAN — find events in a period

```powershell
python -m conflict_updater "1967..1970" --region Nigeria      # a window + optional region
python -m conflict_updater "1871..1872" --region Algeria --limit 5
python -m conflict_updater week                               # last 7 days (the routine update)
```

- **Go tight.** A 1–5 year window on a country gives far better results than a 30-year sweep —
  the queries concentrate, so you get the *important* events with more sources. (Proven: a
  1-year Algeria scan found the Mokrani Revolt with 7 sources across 3 languages; the 30-year
  scan found footnotes.)
- `--limit N` caps how many candidate events it processes (to save quota); it ranks by
  significance first, so a cap keeps the consequential events.

Each scan writes three things to `out/` and **changes nothing else**:

| File | What it is |
|---|---|
| `out/proposals_<period>.json` | the machine-readable proposals (what `apply` reads) |
| `out/review_<period>.md` | the **human queue** — read this |
| `out/coverage.json` | the ledger of what's been searched (see `coverage` below) |

---

## 2. REVIEW — decide what's worth keeping

Open `out/review_<period>.md`. It has two sections:

- **Auto-approved** — well-sourced, cross-corroborated, uncontested. These apply automatically.
  Spot-check them; nothing here *needs* you.
- **Needs human review** — numbered `[1] [2] [3]…`. These are the uncertain/contested ones
  (thin sourcing, a debatable role, a brand-new conflict). Each shows the open question.

**Why something lands in review** (any one of these):
- fact-check came back `uncertain`/`fail` (usually single-source), or confidence below the bar;
- it's founding a *new* conflict without strong multi-source, cross-aligned corroboration;
- the reconciler saw a contested role/classification;
- it's *provisional* — dated in the last ~7 days, held until it corroborates.

You don't edit JSON. You accept the numbered items you agree with in the next step.

---

## 3. APPLY — fold approved items into seed.json

```powershell
python -m conflict_updater apply out\proposals_1967_1970.json --dry-run     # preview, writes nothing
python -m conflict_updater apply out\proposals_1967_1970.json               # auto-approved only
python -m conflict_updater apply out\proposals_1967_1970.json --approve 1 3  # + review items #1 and #3
python -m conflict_updater apply out\proposals_1967_1970.json --approve-all  # + every review item
```

- With no `--approve`, only the **auto-approved** items land; the review items are skipped.
- `--approve 1 3` also accepts the numbered items you chose from the review file.
- `apply` re-checks the whole dataset and **writes nothing if it would introduce a new
  incoherence** (pre-existing seed issues are reported but don't block). On success it bumps the
  seed `version` — which is what makes the app re-import on next load.

That's the integration: `apply` edits `src/data/seed.json` in place. Commit + push it like any
data change, and the deployed app picks it up.

---

## 4. COVERAGE — what have we already looked at?

```powershell
python -m conflict_updater coverage                 # everything scanned
python -m conflict_updater coverage --region Sudan   # one region
```

`found` = events surfaced · `quiet` = searched, nothing there · `blind` = search returned
**0** (a source gap — unknown, NOT proven empty). This is your map of what's done and where the
holes are.

---

## A sensible backfill workflow (doing the past on purpose)

Don't point it at "1490→now × every country" — you'd get a huge, uneven, mostly-unreviewed pile.
Instead, go country-by-country, era-by-era, in tight windows:

```powershell
python -m conflict_updater "1954..1962" --region Algeria     # scan a slice
#  → read out\review_1954_1962.md
python -m conflict_updater apply out\proposals_1954_1962.json --approve 2 4
python -m conflict_updater coverage --region Algeria          # confirm it's logged
#  → move to the next slice
```

Match the window to the density: a busy war gets a 1–2 year scan; a quiet stretch gets a
decade. The coverage ledger keeps your place.

## The routine (forward) mode

Once you're happy, the weekly update is the *same tool* pointed at the last 7 days:

```powershell
python -m conflict_updater week
python -m conflict_updater apply out\proposals_<dates>.json    # auto-approved land; you review the rest
```

This is the piece that could later run on a schedule (a cron / GitHub Action) — same commands,
unattended, with the review queue waiting for you.
