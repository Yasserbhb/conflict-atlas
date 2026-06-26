# Changelog

All notable changes to Conflict Atlas are tracked here. Each tagged version is a meaningful milestone.

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
