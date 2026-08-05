# Navigation Activation Matrix (NP-03)

Generated: 2026-02-28 00:45:00 UTC

Scope: Home menu, lane navigation, omni search routing, cross-lane jumps, detached window docking/undocking.

## Canonical Route Topology

- Tile-to-lane mapping is data-driven from `ModulePathways.laneTitles()` and `ModulePathways.laneConfigs()`.
  - Source: `src\qml\views\MainContent.qml:45`, `src\qml\views\MainContent.qml:46`, `src\qml\views\MainContent.qml:282`
- Lane and node catalogs are declared in one place:
  - Clients & Matters: `A01-A15`
  - Docketing & Deadlines: `B01-B15`
  - Billing, Payments & Tax: `C01-C17`
  - Finance, Reports & Operations: `D01-D16`, cross-cutting `X01-X12`
  - Source: `src\qml\standards\ModulePathways.js:30`

| Tile Index | Stack Index | Lane Key | Default Node | Panel Host |
|---|---:|---|---|---|
| 0 | 1 | `clients_matters` | `A01` | `PlaceholderSubmenuView` |
| 1 | 2 | `docketing_deadlines` | `B01` | `TimeDocketView` |
| 2 | 3 | `billing_tax` | `C01` | `PlaceholderSubmenuView` |
| 3 | 4 | `finance_ops` | `D01` | `PlaceholderSubmenuView` |

Primary mapping functions:
- `stackIndexForTile(tileIndex)` and `tileIndexForStack(stackIndex)` guarantee deterministic tile/stack conversion.
  - Source: `src\qml\views\MainContent.qml:334`, `src\qml\views\MainContent.qml:340`

## Activation Matrix

| Trigger Surface | Entry Handler | Target Resolution | State Transfer | Deterministic Return Path | Guard/Fallback Behavior | Source |
|---|---|---|---|---|---|---|
| Home lane tile click | `onTileClicked -> launchTileFromHome(idx, geom)` | Tile index -> stack index (`idx + 1`) | No forced state unless pre-cached in `dockedStateByTile` | Reverse transition to Main Menu (`startPortalReverseTransition`) from lane panels | Invalid tile index returns `false`; direct stack set used if animation cannot start | `src\qml\views\MainContent.qml:1680`, `src\qml\views\MainContent.qml:458`, `src\qml\views\MainContent.qml:1722` |
| Home hub card click (single module) | `onHubClicked -> openHubSelection(...)` | If one module, launches same as tile | Uses launch origin rect for transition continuity | Same as tile launch return path | Empty module set ignored; fallback launches first module | `src\qml\views\MainContent.qml:1684`, `src\qml\views\MainContent.qml:498` |
| Home hub card click (multi-module) | `openHubSelection(...) -> hub chooser -> launchHubChooserRow(tileIndex)` | Selected chooser row tile | Chooser preserves origin rect for visual continuity | Same as tile launch return path | If chooser fails to open, first module is launched | `src\qml\views\MainContent.qml:498`, `src\qml\views\MainContent.qml:531`, `src\qml\views\MainContent.qml:1942` |
| Home quick action (query-backed) | `quickTap.onTapped -> omniSearchRequested(commandQuery)` | Backend route (`tileIndex`, optional `subwindowId`) then lane launch | `applyStateToTile(idx, routeState)` stores query, type, focus node | Return remains lane cancel -> Main Menu; detached close if detached mode | If backend route unavailable, title contains fallback scan runs; no match returns `false` | `src\qml\views\HomeGrid.qml:47`, `src\qml\views\HomeGrid.qml:1241`, `src\qml\views\MainContent.qml:539` |
| Omni search backend routing | `appRef.handleOmniSearchCommand(query)` | Exact route via subwindow catalog / lane aliases / global lookup fallback | Route payload includes `queryType`, `queryText`, `subwindowId`, `subwindowTitle` | Same as standard lane return semantics | Empty query returns `ok:false`; unmatched queries route to `tile=3, node=X01` | `src\python\backend\app_controller.py:715`, `src\python\backend\app_controller.py:813`, `src\python\backend\app_controller.py:908` |
| Placeholder lane left-nav node click | `onTapped: gotoNode(navRow.modelData.id)` | Active node = clicked nav row ID | Node ID persisted in `snapshotState().focusNodeId` | Cancel button emits `cancelRequested(snapshotState())`; main host returns to menu | `ensureActiveNode()` guarantees valid node and defaults if invalid/missing | `src\qml\views\PlaceholderSubmenuView.qml:223`, `src\qml\views\PlaceholderSubmenuView.qml:244`, `src\qml\views\PlaceholderSubmenuView.qml:2449` |
| Time docket left-nav node click | `onTapped: root.activeSubwindowId = navRow.id` | Active subwindow ID (`Bxx`) | `snapshotState().focusNodeId` and form payload restored through `applyInitialState` | Return/Cancel emits `returnRequested(snapshotState())` | `ensureActiveSubwindow()` defaults to `B01` and clamps invalid IDs | `src\qml\views\TimeDocketView.qml:152`, `src\qml\views\TimeDocketView.qml:175`, `src\qml\views\TimeDocketView.qml:1300`, `src\qml\views\TimeDocketView.qml:1775` |
| Cross-lane jump via lane chips | `moduleJumpRequested(targetTile, snapshotState())` | `MainContent` receives and launches target tile | Source state cached on current tile; optional `_targetTileState` applied to destination | Destination cancel returns to Main Menu using standard reverse transition | Ignored in detached mode; invalid target indices rejected | `src\qml\views\PlaceholderSubmenuView.qml:2391`, `src\qml\views\MainContent.qml:1744` |
| Global search result open | `openGlobalSearchResult(row)` | Row maps to route tile/node (`routeTileIndex`, `routeNodeId`) | Builds `_targetTileState` with selected entity/query context | After jump, normal lane cancel/return applies | Invalid route tile coerced to tile `3` | `src\qml\views\PlaceholderSubmenuView.qml:1332`, `src\qml\views\PlaceholderSubmenuView.qml:1357` |
| Docket report row edit jump | `openDocketReportEntryForEdit(row)` | Hard jump to tile `1`, node `B01` | `_targetTileState` primes docket fields (date/client/matter/time/rate/status/seconds) | Returns via docket return button to Main Menu | Missing/invalid numeric fields normalized before jump | `src\qml\views\PlaceholderSubmenuView.qml:1378`, `src\qml\views\PlaceholderSubmenuView.qml:1403` |
| Timer lock-holder jump | `jumpToLockHolder()` | Jump target tile from lock holder, fallback tile `1` | `_targetTileState.focusNodeId = B01` | Standard lane return path | Invalid lock-holder tile falls back to `1` | `src\qml\views\TimeDocketView.qml:572` |
| In-main undock from active module | `requestUndockFromActiveModule(sourceRect)` | Emits `undockRequested(tile, title, state, originRect)` to window host | Captures lane snapshot before undocking; records telemetry | Return path is explicit dock request from detached window | Disabled in detached mode or when stack not on a module page | `src\qml\views\MainContent.qml:677`, `src\qml\views\MainContent.qml:702`, `src\python\backend\app_controller.py:911` |
| Tear-away button in module | `requestTearAwayForTile(tile, state)` | Emits `tearAwayRequested(...)` to `DetachedShellWindow` host | Uses remembered tile launch geometry or fallback rect | From detached panel, `Return to Dock` path calls dock flow | Invalid tile coerced to active tile, then tile `0` | `src\qml\views\MainContent.qml:599`, `src\qml\DetachedShellWindow.qml:6776` |
| Detached window launch | `launchDetachedPanel(tile, title, state, originRect, sourceContentRef)` | Creates new `DetachedShellWindow` with detached initial tile/state | Passes `detachedInitialTileIndex` and `detachedInitialPanelState` | Source panel completes reverse/tear-away transition; detached window owns flow | Component status checked; fails safely with `false` | `src\qml\DetachedShellWindow.qml:830`, `src\qml\DetachedShellWindow.qml:862`, `src\qml\DetachedShellWindow.qml:897` |
| Return to dock from detached | `handleReturnToDock(tile, title, state, originRect)` | If main shell in Main Menu: direct `requestDockIngest`; else prompt + auto-return route | Dock request queued through `queuePendingDockCommit`, then committed after close | Deterministic docking target by tile; optional auto return to Main Menu then dock | If main shell missing or not ready, redock prompt is shown; no silent drop | `src\qml\DetachedShellWindow.qml:1403`, `src\qml\DetachedShellWindow.qml:1285`, `src\qml\DetachedShellWindow.qml:1310`, `src\qml\views\MainContent.qml:872`, `src\qml\views\MainContent.qml:902` |

## Deterministic Return Rules

1. `Main window module -> Main Menu`
   - Module cancel/return handlers call reverse transition; if animation fails, stack index is forced to `0`.
   - Source: `src\qml\views\MainContent.qml:1722`, `src\qml\views\MainContent.qml:1790`, `src\qml\views\MainContent.qml:1838`, `src\qml\views\MainContent.qml:1897`
2. `Detached module -> Docked module`
   - Detached panel return requests resolve to `handleReturnToDock`, then `requestDockIngest` (direct) or `autoReturnToMenuThenDock` (queued).
   - Source: `src\qml\DetachedShellWindow.qml:1403`, `src\qml\DetachedShellWindow.qml:1324`, `src\qml\views\MainContent.qml:872`, `src\qml\views\MainContent.qml:902`
3. `Detached module -> Close detached shell`
   - Cancel in detached mode closes detached shell when redock is not requested.
   - Source: `src\qml\views\MainContent.qml:1723`, `src\qml\views\MainContent.qml:1780`

## Coverage Statement (NP-03 Gate)

Navigation is normalized around three deterministic contracts:
- `Home actions` always resolve to a tile index (`launchTileFromHome`), optionally with routed node/state.
- `Lane nav actions` always resolve to a node ID (`gotoNode` or `activeSubwindowId`) backed by `ModulePathways` nav catalogs.
- `Window transitions` (`undock`, `tear-away`, `dock`) always preserve panel state and follow explicit ingest/return handlers with guarded fallbacks.

This satisfies NP-03 completion gate: each menu/navigation action has an explicit activation target and a deterministic return path.
