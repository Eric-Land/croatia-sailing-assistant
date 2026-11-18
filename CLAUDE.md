# CLAUDE.md

Guidance for Claude Code in this repository.

## Rules

1. **Branches.** Every change, tooling included (`CLAUDE.md`, `.claude/`, `.gitignore`), goes on a branch created from `main` (`feat/…`, `fix/…`, `chore/…`). Never commit or push to `main`. The user merges into `main` on GitHub.
2. **Commit and push.** `.claude/settings.json` makes `git commit` and `git push` ask for approval every time. Before asking, show the full `git diff` of what will be committed.
3. **Croatia stays unchanged.** Covers the area (Marina Agana, Šolta, Brač, Hvar, Vis), its data (`DATA`, `ISLAND_POLYGONS`, `DEFAULT_ROUTE_WAYPOINTS`, `ARCHIVE_ETE_2026`) and its behaviour (planner, wind, map rendering). To add something, put it beside Croatia, e.g. in a new area profile. Croatia data may move into a profile only with identical values. Before proposing a merge, run the `croatia-guardian` agent; it must report no difference.
4. **Single file.** The app is only `index.html`, with no build step (GitHub Pages serves it from `main`). Put new CSS and JS inline in `index.html`, not in new files, `package.json` or a bundler.
5. **External libraries.** Propose any external library (CDN script, library or external service) first, with its name, version, URL and why, and wait for the user's OK before adding it.
6. **No secrets.** The repo is public: no API key, token or password in any file. Use keyless services, or ask the user.
7. **French.** UI text, code comments and commit messages are in French.
8. **Sources and versions.** Source documents (maps, extracts, notes) are per area, in
   "~/Library/Mobile Documents/com~apple~CloudDocs/Documents/0 - 0 Next move/0 - 0 - IA/Croatie Sailing Assistant/Sources/<area>"
   (`Sources/Croatie`, `Sources/Cote-Emeraude`, one folder per new area).
   Read them there; never copy them into the repo (it is public).
   When the user says "merged": switch to main and pull, then compare index.html with the
   highest-numbered file in the "Versions" folder next to "Sources". Only if it differs, copy it there as
   "AAAA MM JJ - Croatia Sailing Assistant - Update N.html" (N = that highest number + 1);
   otherwise make no copy and say so. Never overwrite a file there.

## Overview

Single-file web app (`index.html`, ~3,600 lines, ~270 KB) for planning a sailing loop around the central Dalmatian islands from Marina Agana. No package manager, linter or tests: run it with `open index.html`. CDN dependencies: Leaflet 1.9.4, SheetJS 0.18.5. Runtime services: Open-Meteo (wind), Esri World Street Map (tiles; direct OSM tiles are blocked).

Some lines hold huge inline JSON: read the file by line range or `grep -n`, never whole.

## Layout

1. `<style>` (~lines 6–362).
2. Markup: pirate SVG background, header (total NM, changes, J0 date), left column (crew sliders, constraints), tabs via `TAB_DEFS`/`switchTab()`: `itin`, `escales`, `carte`, `archItin`, `archCarte`.
3. One `<script>` (~line 774): starts with `const DATA = {...}` on one line, ends with the boot sequence (`buildCheckpointSelect(); render(); …; preloadWindForecast();`).

## Data

- **`DATA`**: `stops` (escales with scores, role, water, mooring, `excluded`…), `route` (legs `{seq, day, stop, category: 'Base'|'Pause'|'Night', locked?}`), `protection`, `reviewSynthesis`, `mapping`, `islandAnchors`. Lookups: `stopByName`, `protByName`.
- **`ISLAND_POLYGONS`**: coastlines as `[lon, lat]`, used by `findSeaRoute`/`segCrossesIslandGPS`.
- **`DEFAULT_ROUTE_WAYPOINTS`**: hand-corrected routes keyed `"StopA|StopB"`, points as `[lat, lon]` (note the reversed order), preloaded into `routeEdits`.
- **`ARCHIVE_ETE_2026`**: frozen (`deepFreeze`) snapshot of the trip sailed in summer 2026, rendered only by `arch*` functions. Never make it read live state.

## State and render

State is in memory only (no localStorage). Persistence is via JSON export/import (`exportDataJSON`, `exportRoutesJSON`, `importRoutesJSON`); also `exportToExcel`, `exportToCalendar`.

Mutable globals: `crewPrefs`, `maxNavNM`, `waterDays`, `checkpointSeq`, `actualOverrides`, `manualOverrides`, `lastComputed`, `scoreOverrides`, `roleOverrides`, `mustKeepSet`, `discardSet`, `routeEdits`, `dayDeparture`/`dayDepartureUser`. Every setter calls `render()`.

`render()` → `resolveRoute()` → `planRoute()` (`generatePlan()` if `plannerActive`, else `DATA.route`) → wind check and alternatives (`findAlternative`, `isProtected`, `computeCrewFit`) → `resolvedRoute` → table, totals, map.

- **Modes**: summer route by default; moving a slider calls `activatePlanner()`; `resetToSummerPrefill()` goes back.
- **Planner scoring**: `generatePlan()` builds a Pause+Night skeleton per day, scoring stops by crew fit, rating, distance to the daily target (`effectiveDayTarget()`), the `maxNavNM` cap and water availability.
- **Score inheritance**: `getScore`/`getRole`/`isDiscarded` fall back to the parent stop via `baseScoreOwner()`.
- **Wind**: `preloadWindForecast()` makes one batched Open-Meteo call (forecast up to J+15, archive for past dates) into `windCache[stop][day].{morning|afternoon}`. Pause legs use morning, Night legs afternoon. J0 is `CRUISE_START`.
- **Maps**: `renderMap()` (offline SVG) and `renderLeafletMarkers()` (Leaflet, editable via `toggleRouteEdit`). `initMapSystem()` switches to Leaflet on the first tile load, otherwise stays on SVG.

## Conventions

- Keep rule/defect tags in comments (`R1`, `R3`, `DEF1`–`DEF4`; e.g. `DEF1`: `maxNavNM` is a hard cap) when editing that logic.
- HTML is built with template strings and inline `onclick`: escape JS attribute values with `escJsAttr()`, archive text with `archEsc()`.
- Dates use local time via `fmtISODate`, not `toISOString` (UTC shifts the day).
