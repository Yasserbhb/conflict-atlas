# Conflict Atlas

An interactive vector world map for exploring geopolitical conflicts, genocides, occupations, and atrocities across history — from 1490 to the present (2026).

Built as a personal learning tool: browse the map, dig into any country's involvements, read the structure of a single conflict, scrub a timeline through history, and add or edit your own entries.

## Features

- **Vector world map** (D3-geo, 50m Natural Earth data) with scroll-to-zoom and drag-to-pan.
- **Three reading modes**, each with a clear legend:
  - **Overview** — countries shaded by conflict severity (a heatmap of where the world is hot).
  - **Country** — click a country to see thin "reach" lines radiating to every conflict it's involved in, colored by its role (solid = attacks, dashed = backs/involved).
  - **Conflict** — focus one conflict and every party country fills with its role color (aggressor · victim · funder · sanctioner · mediator).
- **Timeline slider (1490–2026)** with a play button to watch conflicts rise and fall.
- **Edit mode** — add/edit conflicts (type, severity, dates, parties with roles, description, tags) and personal notes per country.
- **Network graph** view of a country's connections.
- **Export / import** your whole dataset as JSON.
- **~160 pre-loaded conflicts** across every region and era, with descriptions, parties, and roles.

> **Note on borders:** the map always shows *modern* borders. Historical events are mapped onto the country that occupies that territory today (e.g. the Spanish Conquest -> modern Mexico/Peru). Successor states use aliases (Russia = USSR, Turkey = Ottoman Empire, etc.).

## Tech stack

- React 19 + Vite 5
- D3 (geo, zoom, force) + TopoJSON
- IndexedDB (via `idb`) for local persistence — no server, runs fully offline
- CSS Modules

## Running it

```bash
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build into dist/
```

## Data model

Conflicts, countries, and notes live in IndexedDB, seeded once from `src/data/seed.json`. Seed data is versioned: bumping `seed.json`'s `version` re-imports new entries without overwriting your own edits. Seed entries use IDs prefixed `seed_`; your own use `user_`.

Each conflict has: `type`, `severity` (1-5), `startDate`/`endDate`/`ongoing`, a `description`, and `parties` (each a country + role). Roles drive the map colors.

## Versions

See `CHANGELOG.md` for the version history.
