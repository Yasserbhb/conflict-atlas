# Changelog

All notable changes to Conflict Atlas are tracked here. Each tagged version is a meaningful milestone.

## v1.4.0 — 2026-06-27

Full visual redesign — "green glass."

- Theme shifted from navy/blue to a **greener-dark base with an acid-green accent**, frosted-glass surfaces (backdrop-blur), hairline borders, and slightly sharper corners throughout.
- **Side-panel conflict cards redesigned**: type glyph in a tinted square, country **flag chips**, a role pill, a segmented severity gauge, hover lift.
- Restyled every surface — nav, top bar, View/Edit toggle, search, timeline slider, the Conflicts/Stats/Timeline/Help views, the map filter bar/legend/zoom controls, and all modals (edit form, graph, data).
- **Map recolored**: deep green-black ocean and greenish calm-land instead of navy blue; data colors (severity, type, role) unchanged since they encode meaning.
- Added a flags utility (ISO-2 → emoji) and per-type glyphs.

## v1.3.0 — 2026-06-26

Turned the single-map page into a real multi-section app.

- **Left sidebar nav** with five views: Map, Conflicts, Stats, Timeline, Help.
- **Conflicts view** — browse all ~180 in a searchable, sortable, filterable list (by type, region, severity, ongoing); click a row to open it on the map.
- **Stats view** — headline counts + bar charts (by type, most-involved countries, by era, by severity).
- **Timeline view** — per-year density histogram of active conflicts (1490–2026), click/scrub to a year, see the active list, jump to the map.
- **Help/About view** — explains the three map modes, the severity/type/role color systems, navigation, and the data disclaimer.
- **Map filter bar** — filter the map by type / severity / ongoing; the whole map (heatmap, arcs, highlights, side panel) recomputes as if only the filtered conflicts exist.

Fixes & polish:
- Map TopoJSON now parsed once and cached → switching views and back is instant; "Loading map…" hint on first load.
- Severity scale relabeled (5 = "Catastrophic", not "Genocide") and given a cleaner gradient.
- Selected country = bold blue outline; related countries = thin white outline (no more arbitrary blue fill hiding the data).
- Fixed unmapped territories (Greenland, Antarctica) falsely rendering as "selected".
- Opening a conflict from a list now moves the timeline into its window so the side panel matches.
- Fixed side-panel cards squishing/overlapping (flexbox scroll bug).

## v1.2.1 — 2026-06-26

Fixed the side panel: with many conflicts the cards were squished into thin overlapping strips and the selected one's text was clipped. Caused by a flexbox scroll bug — the list lacked `min-height: 0` and the cards lacked `flex-shrink: 0`, so the column compressed the cards instead of scrolling. Now the list scrolls and every card keeps its full height.

## v1.2.0 — 2026-06-26

Professionalization pass — cleaned up for sharing.

- **package.json**: real name/description/author/keywords; removed leftover platform-locked deps (`rolldown`, rollup/rolldown win32 bindings as hard deps) that broke cross-platform `npm install`. Windows rollup binary moved to `optionalDependencies` (skipped on macOS/Linux).
- Removed dead Vite boilerplate (`App.css`, `index.css`, `src/assets/`, `icons.svg`, old default favicon, unused 110m map).
- New project favicon + page title, description, and Open Graph meta tags.
- Added **MIT LICENSE**.
- README expanded: features, data disclaimer (educational, figures debated), Natural Earth/D3 attribution, deploy guide, troubleshooting.
- Added `netlify.toml` for one-click deploy (Vercel zero-config; GH Pages noted).

## v1.1.0 — 2026-06-26

Filled the sparse early-modern era (1490–1865), which had only ~1–2 conflicts per period. Now ~180 conflicts total with a balanced spread across the centuries.

Added: Sengoku Japan, Eighty Years' War, Thirty Years' War, Qing conquest of China, English Civil War, Cromwellian conquest of Ireland, Ottoman wars in Europe, Mughal expansion, War of the Spanish Succession, Great Northern War, Dzungar genocide, Seven Years' War, British conquest of India, American Revolution, French Revolution & Terror, Haitian Revolution, Napoleonic Wars, Russo-Turkish Wars, Mexican–American War, Circassian genocide, American Civil War.

## v1.0.0 — 2026-06-26

First saved version. A complete, working app.

### App
- Interactive D3-geo vector world map (50m Natural Earth), scroll-to-zoom + drag-to-pan, non-scaling borders so small countries stay legible.
- Three reading modes with a contextual legend:
  - **Overview**: severity heatmap.
  - **Country**: "reach" lines from the selected country to its conflicts, colored by role; solid = attacks, dashed = backs/involved.
  - **Conflict (focus)**: every party country filled by its role color.
- Timeline slider 1490–2026 with play/animate.
- Edit mode: add/edit conflicts and per-country notes, stored in IndexedDB.
- Country search, network graph view, JSON export/import.
- Versioned seed import (never overwrites user edits).

### Data — ~160 conflicts, 130 countries, 1490–2026
- Colonial occupations logged from their real start dates (French Algeria from 1830, British Raj from 1757, Spanish conquest from 1492, Belgian Congo, Italian Libya, Dutch Indonesia, British Egypt, etc.).
- Major genocides and atrocities across every region (Herero, Holocaust, Holodomor, Nanjing, Bengal Famine, Partition, Great Leap Forward, Cambodia, Rwanda, Srebrenica, East Timor, Bangladesh 1971, Anfal, Uyghur, Rohingya, apartheid, Native American, Aboriginal Australian, and more).
- Wars and proxy conflicts worldwide and across eras (Taiping, Opium Wars, Boxer, Sino-Japanese, world wars, Cold War proxies, Operation Condor, Sahel, and many more).
- Up to date through mid-2026: Ukraine, Gaza (Oct 2025 ceasefire), Sudan, DRC/M23 (2025 peace deal), fall of Assad (Dec 2024), Israel–Hezbollah and Israel–Iran wars (2025–26), and the US capture of Maduro in Venezuela (Jan 2026).

> Casualty figures for several older events (Spanish conquest, Bengal Famine, Great Leap Forward, Congo Free State) use commonly-cited historical ranges that scholars still debate.
