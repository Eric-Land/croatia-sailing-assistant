# CLAUDE.md

Guidance for Claude Code in this repository.

## Rules

1. **Branches.** Every change, tooling included (`CLAUDE.md`, `.claude/`, `.gitignore`), goes on a branch created from `main` (`feat/…`, `fix/…`, `chore/…`). Never commit or push to `main`. The user merges into `main` on GitHub.
2. **Commit and push.** `.claude/settings.json` makes `git commit` and `git push` ask for approval every time. Before asking, show the full `git diff` of what will be committed.
3. **Croatia stays unchanged.** Covers the area (Marina Agana, Šolta, Brač, Hvar, Vis), its data (`DATA`, `ISLAND_POLYGONS`, `DEFAULT_ROUTE_WAYPOINTS`, `ARCHIVE_ETE_2026`) and its behaviour (planner, wind, map rendering). To add something, put it beside Croatia, e.g. in a new area profile. Croatia data may move into a profile only with identical values. The data is checked automatically: `.claude/hooks/check-croatia.py` runs as a Stop hook whenever `index.html` differs from `main`, compares every Croatia data block and the `AREAS.croatia` profile settings value by value, and blocks stopping (exit 2) on any difference, which must then be fixed. Run it by hand with `python3 .claude/hooks/check-croatia.py --fichier index.html`. Behaviour (planner, wind, maps) is checked by the `croatia-guardian` agent: before proposing a merge, run it; it must report no difference.
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

Single-file web app (`index.html`, ~3,760 lines, ~280 KB) for planning a sailing loop. Several sailing areas, one profile each: Croatia (central Dalmatian islands from Marina Agana, the default) and Côte d'Émeraude (Dinard, empty for now). No package manager, linter or tests: run it with `open index.html`. CDN dependencies: Leaflet 1.9.4, SheetJS 0.18.5. Runtime services: Open-Meteo (wind), Esri World Street Map (tiles; direct OSM tiles are blocked).

Some lines hold huge inline JSON: read the file by line range or `grep -n`, never whole.

## Layout

1. `<style>` (~lines 6–362).
2. Markup: pirate SVG background, header (area switcher added at boot, total NM, changes, J0 date), left column (crew sliders, constraints), tabs via `TAB_DEFS`/`switchTab()`: `itin`, `escales`, `carte`, `archItin`, `archCarte`. The static HTML is written for Croatia; `applyAreaTexts()` swaps its texts for another area and removes the archive tabs when the area has no archive.
3. One `<script>` (~line 774):
   - **Area registry** (~lines 775–905): `AREAS.croatia` is an IIFE holding Croatia's data literals verbatim (`DATA` on one huge line, `ISLAND_POLYGONS`, `ISLAND_LABELS`, `ISLAND_LABEL_POS`, `ISLAND_NAME_POS`, `DEFAULT_ROUTE_WAYPOINTS`, `ARCHIVE_ETE_2026`) and returns the profile; `AREAS.emeraude` follows. Then `AREA_ID` (from `?area=`, unknown or missing = `DEFAULT_AREA_ID` `'croatia'`), `AREA`, and `const DATA = AREA.DATA`.
   - The rest of the code reads the usual globals (`DATA`, `ISLAND_POLYGONS`, `ISLAND_LABELS`, `ISLAND_NAME_POS`, `DEFAULT_ROUTE_WAYPOINTS`, `AREA_ARCHIVE`), each set from `AREA` where it was defined before.
   - Ends with the boot sequence (`applyAreaTexts(); buildAreaSwitcher(); buildCheckpointSelect(); render(); …; preloadWindForecast();`).

## Data

- **Areas**: one profile per area in `AREAS`; adding an area = adding a profile, no code change. Fields (all optional except `DATA`, `title`, `baseStop`) are listed in a comment above `const AREAS`: `name`, `title`, `country`, `fileSlug`, `timezone`, `baseStop`, `mainlandLabel`, `farExamples`, `prefill`, `checkpointSeq`, `seaGrid` or `bounds`, `center`/`zoom`, `archiveView`, the data globals below, `archive`. Switching area reloads the page (`switchArea()`, nothing is stored). JSON exports carry `"area"`; `importRoutesJSON` refuses another area's file (untagged = Croatia).
- **`DATA`**: `stops` (escales with scores, role, water, mooring, `excluded`…), `route` (legs `{seq, day, stop, category: 'Base'|'Pause'|'Night', locked?}`), `protection`, `reviewSynthesis`, `mapping`, `islandAnchors`. Lookups: `stopByName`, `protByName`.
- **`ISLAND_POLYGONS`**: coastlines as `[lon, lat]`, used by `findSeaRoute`/`segCrossesIslandGPS`.
- **`DEFAULT_ROUTE_WAYPOINTS`**: hand-corrected routes keyed `"StopA|StopB"`, points as `[lat, lon]` (note the reversed order), preloaded into `routeEdits`.
- **`ARCHIVE_ETE_2026`**: Croatia's frozen (`deepFreeze`) snapshot of the trip sailed in summer 2026, exposed as `AREA_ARCHIVE` (null for an area without archive) and rendered only by `arch*` functions. Never make it read live state.

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
