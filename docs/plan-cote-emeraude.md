# Plan — multi-area support: Croatia + Côte d'Émeraude

Revised plan, checked against `CLAUDE.md` rules 1 to 8. Branch: `feat/cote-emeraude`.

## Context
The app is hard-wired to the Split / Middle Dalmatia area. The goal is a second area, then more later. Switching area shows a new map centred on it, with no preloaded route. Croatia must keep working exactly as it does today (rule 3).

## Vision
Later the app will switch between any number of areas with a polished UI. So the area registry stays **generic**: adding an area means adding a profile, not changing code. The step 4 switcher stays simple; the polished UI will come on a separate branch.

## Approach: one area profile per area, chosen at load via `?area=`
Nearly everything derived from the area is computed **once at load** (`const`), and the Leaflet map is created once. Reloading the page with the chosen area is far safer than switching live.

1. **Area registry.** `AREAS.<id>` = one profile per area. Croatia's data (`DATA`, `ISLAND_POLYGONS`, `ISLAND_LABELS`, `ISLAND_LABEL_POS`, `ISLAND_NAME_POS`, `DEFAULT_ROUTE_WAYPOINTS`, `ARCHIVE_ETE_2026`) **moves verbatim** into its profile: the lines are moved byte for byte, not edited.
2. **Area selection** at the top of the script: `?area=<id>` if it exists in `AREAS`, otherwise Croatia. The existing globals (`DATA`, `ISLAND_POLYGONS`…) are then read from the selected profile, so the rest of the code is unchanged. With no parameter, Croatia loads exactly as today.
3. **Remove the hard-coded values**, each replaced by a profile field: `SEA_GRID` (Croatia keeps its literal lists, so the same floats), `'Marina Agana'` fallbacks, SVG map and legend → `baseStop`; "Continent (Split)" → `mainlandLabel`; `<title>`/`<h1>` → `title`; ICS `,Croatia` → `country`; export file names → `fileSlug`; Open-Meteo time zone → `timezone`; island list → keys of `ISLAND_LABELS`; Leaflet centre/zoom → `center`/`zoom` (default: stop midpoint, zoom 11); archive map view → `archiveView`. The static HTML keeps the Croatia texts.
4. **Archive** shown only if the profile has one (tabs, hint, "pre-filled from summer 2026" texts).
5. **Area switcher** in the header: a simple `<select>` built from `AREAS`, which asks for confirmation (in-memory state is lost) then reloads with `?area=<id>` (Croatia = no parameter). **No `localStorage`:** without `?area=`, the app always opens Croatia.
6. **Exports tagged per area:** JSON exports carry `"area": "<id>"`. `importRoutesJSON` refuses a file from another area; a file without the field (old export) counts as Croatia. In-memory keys (`routeEdits`) are never renamed. Excel and ICS stay identical for Croatia.

## The new area: Côte d'Émeraude – Channel Islands (`?area=emeraude`)
Dinard / Saint-Malo / Cap Fréhel / Jersey / Guernsey, base **Dinard**, **empty area for now** (no stop other than the base).
- `title` "Émeraude Sailing Assistant", `country` "France", `mainlandLabel` "Continent (Saint-Malo)", `timezone` "Europe/Paris".
- `DATA.stops`: Dinard only (48.6327 N / 2.0552 W, coordinates given by the user), scores `null`.
- `DATA.route`: skeleton only, J0 at Dinard and the return to Dinard on J6.
- Fixed extent: `bounds` lat 48.55–49.55, lon −2.75 to −1.85, `center` [48.65, −2.025] (Saint-Malo), `zoom` 8, used by Leaflet while the route has a single stop (bounds otherwise avoid a division by zero in `project()`).
- Empty pools: the planner must not crash; it shows « Aucune escale définie pour cette zone ».
- **Out of scope, flagged for later:** tides (range up to 12–13 m) and currents (Raz Blanchard, Déroute), not in the nav-time model (≈ 6 kn, wind only); customs formalities for Jersey/Guernsey.

## Steps (one commit per step, in French, full diff shown before each commit)
Diffs that touch the huge one-line JSON are shown as `git diff --stat` + a cut-down diff + a hash check that the moved lines are byte-identical (agreed by the user).

| Step | Work | What you see in the app |
|---|---|---|
| 0 | Branch `feat/cote-emeraude`; this plan in `docs/`; `CLAUDE.md` rule 8: sources per area (`Sources/<area>`), dated copy in `Versions` only if `index.html` changed; Croatia reference captured (outside the repo). | Nothing changes. |
| 1 | Area registry + `?area=` selection, Croatia only. Compare with the reference. | Identical, also with `?area=croatia` and `?area=xyz`. |
| 2 | Remove the hard-coded values (profile fields). Compare again. | Still identical. |
| 3 | Émeraude profile. | No parameter: Croatia. `?area=emeraude`: title "Émeraude Sailing Assistant", map centred on Saint-Malo / Jersey / Guernsey, a single marker at Dinard, itinerary with the base only, no Archive tab, planner message « Aucune escale définie pour cette zone », no console error. |
| 4 | Simple area switcher. | A « Zone » dropdown in the header; changing area asks for confirmation then reloads. With no parameter, always Croatia. |
| 5 | Exports tagged per area. | Croatia JSON exports gain `"area": "croatia"`; importing another area's file is refused with a French message; old files still import; Excel/ICS unchanged. |
| 6 | Before the merge: `croatia-guardian` (no difference), push, PR; the user merges on GitHub. | After the merge, the public site shows the switcher; Croatia otherwise unchanged. |
| 7 | On "merged": `main` + pull, compare `index.html` with the latest file in `Versions`; copy as Update N+1 only if it differs. | — |

## Verification
- **Croatia unchanged:** a headless reference (constants, rendered HTML of each tab, four planner scenarios, SVG map, Leaflet centre, Excel/ICS/JSON exports, `SEA_GRID`) taken on `main`, compared after each step, with no parameter, `?area=croatia` and `?area=xyz`.
- **New area:** centred map, base-only itinerary, planner message, no Archive tab, no console error, offline SVG map works.
- **Default URL:** no parameter → Croatia, even right after visiting `?area=emeraude`.
