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

## Deploying

It's a static single-page app (all data lives in the browser via IndexedDB), so it hosts anywhere:

- **Netlify** — connect the repo; `netlify.toml` is already set up (`npm run build` → `dist/`).
- **Vercel** — zero config; it auto-detects Vite.
- **GitHub Pages** — set `base: '/<repo-name>/'` in `vite.config.js`, then publish `dist/`.

## Troubleshooting

- **`Cannot find module @rollup/rollup-win32-x64-msvc` on Windows** — a known npm bug ([npm/cli#4828](https://github.com/npm/cli/issues/4828)) that sometimes skips optional native binaries. Fix: `rm -rf node_modules package-lock.json && npm install`. (It's listed under `optionalDependencies` and is harmless/skipped on macOS & Linux.)

## Data, sources & disclaimer

This is an **educational tool**, not an authoritative record. The seeded conflicts are compiled from widely-available historical summaries to give a starting point — they are deliberately concise and, for some events, casualty figures and even classifications (e.g. what counts as a "genocide") are **genuinely debated by historians**. Pre-modern events are mapped onto modern successor states, which is a simplification.

Treat every entry as a prompt for your own further reading, and use **Edit mode** to correct, refine, and add sources as you learn. Nothing here represents an official position.

- Map geometry: [Natural Earth](https://www.naturalearthdata.com/) via [world-atlas](https://github.com/topojson/world-atlas) (public domain).
- Built with [D3](https://d3js.org/), [React](https://react.dev/), and [Vite](https://vite.dev/).

## License

[MIT](LICENSE) © Yasser Bouhai. Note: the license covers the **code**; historical facts themselves are not copyrightable.

## Versions

See [CHANGELOG.md](CHANGELOG.md) for the version history.
