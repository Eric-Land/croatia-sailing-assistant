# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules

1. Never commit or push unless asked. Show `git diff` first.
2. App changes go on a feature branch, never directly on `main`.
3. The Croatia area must stay unchanged. That covers the sailing area (Marina Agana, Šolta, Brač, Hvar, Vis), its data (`DATA` stops and route, `ISLAND_POLYGONS`, `DEFAULT_ROUTE_WAYPOINTS`, `ARCHIVE_ETE_2026`) and its behaviour (planner output, wind handling, map rendering). The data may be moved into an area profile, but its values must stay the same and Croatia must behave exactly as it does now.
4. Keep the app a single `index.html` with no build step. GitHub Pages publishes it from `main`.
5. Ask before adding any dependency (CDN script, library or external service).
6. No secrets or API keys in the repo, because it is public.

## Overview

A single-file web app (`index.html`, ~3,600 lines and ~270 KB) for planning a sailing loop around the central Dalmatian islands (Šolta, Brač, Hvar, Vis) from Marina Agana. The UI, code comments and commit messages are in **French**. Keep new UI text and comments in French too.

There is no build step, package manager, linter or test suite. To run it, open `index.html` in a browser (`open index.html`). The only external dependencies load from CDNs in `<head>`: Leaflet 1.9.4 and SheetJS (xlsx) 0.18.5. At runtime the app also calls Open-Meteo for wind and Esri World Street Map for map tiles.

Because the file is large and some lines hold huge inline JSON, read it by line range or `grep -n` for function names. Don't read the whole file at once.

## File layout

1. `<style>` (lines ~6–362): all CSS.
2. Markup: a decorative pirate SVG background, a header (total NM, changes count, J0 date picker), a left column (crew preference sliders and constraints) and tabbed panels. `TAB_DEFS`/`switchTab()` map tab keys to panel IDs: `itin`, `escales`, `carte`, `archItin`, `archCarte`.
3. One `<script>` block (from ~line 774). It starts with `const DATA = {...}` on a single very long line and ends with the boot sequence: `buildCheckpointSelect(); render(); renderArchiveTable(); renderEscalesTab(); preloadWindForecast();`.

## Data

- **`DATA`** is the inline JSON dataset. `DATA.stops` holds the stops ("escales"): coordinates, island, role, wild/village/swim/restaurant/beaugossitude scores, water, seabed, mooring, contacts and `excluded`. `DATA.route` is the summer-2026 itinerary as legs `{seq, day, stop, category: 'Base'|'Pause'|'Night', locked?}`. Other keys are `protection` (sheltered wind directions per dock), `reviewSynthesis`, `mapping` and `islandAnchors`. Lookup maps `stopByName` and `protByName` are built from it.
- **`ISLAND_POLYGONS`** holds coastline polygons as `[lon, lat]`. They are used by `findSeaRoute`/`segCrossesIslandGPS` so that routes don't cross land.
- **`DEFAULT_ROUTE_WAYPOINTS`** holds hand-corrected sea routes keyed `"StopA|StopB"` with points as `[lat, lon]`. They are preloaded into `routeEdits` and take precedence over the computed `seaWaypoints`. Watch the coordinate order: the polygons are `[lon, lat]`, these waypoints are `[lat, lon]`.
- **`ARCHIVE_ETE_2026`** is a frozen snapshot (`deepFreeze`) of the trip actually sailed in summer 2026. It has its own stops and route and is independent of `DATA`, the sliders, the overrides and route editing. It renders only through the `arch*` functions. Never make it depend on live state.

## State and the render pipeline

All state lives in memory: there is no localStorage, so a reload resets everything. Users keep changes by exporting JSON (`exportDataJSON`, `exportRoutesJSON`) and importing it back (`importRoutesJSON`). Exports to Excel (`exportToExcel`) and to an `.ics` calendar file (`exportToCalendar`) also exist.

Mutable globals:
- `crewPrefs`, `maxNavNM` (a hard cap per day), `waterDays`
- `checkpointSeq`: legs before it count as already sailed ("elapsed")
- `actualOverrides`: what was really done on elapsed legs
- `manualOverrides`: stops forced by hand on future legs
- `lastComputed`
- `scoreOverrides`, `roleOverrides`
- `mustKeepSet`, `discardSet`
- `routeEdits`, `dayDeparture`/`dayDepartureUser`

Every setter changes state and then calls `render()`. The flow is:

`render()` → `resolveRoute()` → `planRoute()` → (`generatePlan()` if `plannerActive`, else `DATA.route`) → per-leg wind check and alternatives (`findAlternative`, `isProtected`, `computeCrewFit`) → fills `resolvedRoute` → table rows, totals and the map.

- **Two modes.** At first the app shows the summer-2026 route ("pré-rempli"). Moving a crew slider calls `activatePlanner()`, which sets `plannerActive = true`, clears the plan overrides and lets `generatePlan()` build a fresh loop. That loop is a Pause+Night skeleton per day, scored by crew fit, rating, distance to the daily target (`effectiveDayTarget()`), the `maxNavNM` cap and water availability. `resetToSummerPrefill()` goes back to the summer route.
- **Scores fall back to the parent stop.** `getScore`, `getRole` and `isDiscarded` use `baseScoreOwner()`, so a specific dock or pontoon inherits from its generic parent stop unless it is overridden.
- **Wind.** `preloadWindForecast()` makes one batched Open-Meteo request for all stops. It uses the forecast endpoint up to J+15 and the archive endpoint for past dates. Results are cached as `windCache[stopName][day].{morning|afternoon}`: Pause legs use the morning wind, Night legs the afternoon wind. `CRUISE_START` (J0) is changed through the header date input, for example to test with dates that have a forecast available.
- **Maps.** There are two renderers. `renderMap()` draws a schematic offline SVG using island "blobs" and `seaPath`. `renderLeafletMarkers()` draws the Leaflet map, with an editable route mode (`toggleRouteEdit`, drag handles that write into `routeEdits`). `initMapSystem()` shows the SVG map first and switches to Leaflet when the first tile loads. It stays on the SVG map if tiles fail or the browser is offline. Direct OSM tiles are blocked for this app, which is why it uses Esri tiles.

## Conventions

- Comments tag rules and defect fixes with IDs such as `R1`, `R3` and `DEF1`–`DEF4` (for example `DEF1`: `maxNavNM` is a hard cap the engine never exceeds). Keep these tags when editing the related logic.
- HTML is built as template strings with inline `onclick` handlers. Escape any value placed in a JS attribute with `escJsAttr()`, and archive HTML text with `archEsc()`.
- Dates are handled in local time with `fmtISODate`, not `toISOString`, which works in UTC and shifts the date by a day.
