# Professional Theme Implementation Plan

## Goal

Add a durable two-style production system and make the Professional style the
reference path toward a more modern application shell:

- `Console`: existing animated, glossy, bubbly, sound-rich CSPM experience.
- `Professional`: restrained premium business UI with flatter geometry, cleaner forms, muted motion, minimal/no sound, and the new Option 3 shell architecture.
- `Expert`: a separate outside-QML prototype/client tier, based on the
  Professional Option 3 wireframe, intended for a future Flutter or React Native
  implementation without replacing the current QML app.

Both styles must use the same backend, data model, routes, permissions, reports, docketing logic, and persistence.

## Core Principle

Use one shared application with style tokens and selective structural swaps.

Do not duplicate the app. Do not fork business logic. Do not create two versions of every QML file.

## Historic Financial Synchronization Boundary

Historic `Dockets.xlsm` finance is synchronized through a governed backend service rather than through QML forms or the generic incremental importer. The service reads the OneDrive workbook as a dated source snapshot, produces a read-only plan, writes only an isolated candidate, and allows a separately confirmed promotion only after backup, hash, integrity, ledger/A/R, productivity, and Executive Dashboard reconciliation gates pass. Native CSPM activity after the source cutoff remains preserved. This keeps both interface styles on the same financial data model and prevents a dashboard-only correction from diverging from the ledger.

## Long-Term Target

Professional mode is not just a QML skin. It is the reference implementation for
the future Expert client tier in Flutter or React Native.

That means the QML Professional implementation should be treated as:

- a design and workflow prototype for the future professional client,
- a way to cleanly separate business logic from UI behavior,
- a proving ground for durable screen contracts, view models, and data payloads,
- a bridge that keeps the current app usable while the eventual client architecture is prepared.

Console can remain QML-native and expressive. Professional should steadily move toward a portable client model where screens consume explicit backend contracts instead of reaching deep into QML globals or embedding business rules in view files.

Do not treat the first outside-QML wireframes as an irreversible Flutter versus
React Native platform decision. The React Native Web prototype remains useful as
a fast browser sketch, and the native Flutter prototype now exists as a Windows
desktop candidate with automated setup through `launch.ps1`. The durable client
boundary remains local loopback HTTP JSON for commands/queries plus WebSocket
events, and framework tradeoffs should still be judged against real workflows.

The canonical product brief for this destination is saved at:

```text
docs/CSPM_Option_3_Interface_Rebuild_Brief.md
```

Future agents should treat that brief as the durable UI architecture direction unless
the user explicitly supersedes it.

## 1. Single Source Of Truth

Keep the existing setting:

```json
"appStyle": "Console" | "Professional"
```

Do not introduce `appTheme` unless we fully migrate and remove `appStyle`.

The Python backend should normalize missing/legacy values:

```text
missing/invalid -> Console
Professional -> Professional
Console -> Console
```

Settings Menu updates `appStyle`, saves it, and emits the change to QML.

All settings load paths must restore the saved `appStyle`, including normal startup,
deferred settings load, and any helper such as `_apply_settings_payload()`. No load path
should overwrite a saved Professional preference with the default Console value.

## 2. Style Token Engine

Expand the existing style infrastructure instead of adding a competing system.

Primary style layers:

- `VisualRules.qml`: motion, radius, shadow, chrome behavior, sound policy.
- `SemanticTheme.js`: role-based colors for surfaces, text, borders, accents.
- Shared controls: consume semantic tokens instead of hardcoded colors.

Before refactoring components, define the token contract clearly:

- `VisualRules.qml` owns behavior and metrics: radius, shadow, motion, chrome, sound policy.
- `SemanticTheme.js` owns semantic colors: surfaces, ink, borders, accents, status tones.
- Shared QML controls consume those rules/tokens and should not hardcode theme-specific styling.
- View-level `appStyle` checks are allowed only for true structural/layout differences.

Tokens should be semantic:

```text
surfaceApp
surfacePanel
surfaceInput
surfaceRaised
inkPrimary
inkMuted
borderSubtle
borderStrong
accentPrimary
radiusPanel
radiusControl
shadowPanel
motionFast
motionNormal
soundProfile
```

Avoid raw tokens like `gray100`, `blue500`, or one-off color literals scattered through views.

## 3. Professional Design Direction

Start with one Professional style: clean light UI.

Recommended baseline:

- Background: light slate/white, not cream.
- Panels: white or near-white.
- Borders: subtle blue-gray.
- Accent: navy/slate, used sparingly.
- Radius: 0-4px for controls, max 6px for panels.
- Shadows: minimal or none.
- Typography: system sans first; later consider bundled Inter/Roboto if needed.
- Motion: short fades/snaps, no jelly, no bounce, no glow pulse.
- Sound: default off or extremely subtle.

Premium dark can become a future `ProfessionalDark` after light is coherent.

## 4. Component Strategy

Refactor shared components first:

- `PillButton.qml`
- `ModernTextField.qml`
- `ModernComboBox.qml`
- panels/cards/modals
- sidebar/nav rows
- table/report components
- settings controls

Each component should read style tokens and render both Console and Professional correctly.

Keep view-specific styling only when a view genuinely needs unique layout behavior.

For Professional-specific work, prefer architecture that can later be mirrored in Flutter or React Native:

- explicit screen state objects,
- explicit command/action methods,
- DTO-shaped payloads instead of ad hoc QML object mutation,
- reusable view-model helpers in Python or a transport-neutral service layer,
- minimal direct dependency on QML context globals.

## 5. Conditional Layout Swaps

Use `Loader` swaps only for major structural differences.

Good candidates:

- Startup splash
- Home/dashboard landing experience
- Main navigation shell if needed
- Possibly large module home grids

Bad candidates:

- Basic forms
- Buttons
- Inputs
- Comboboxes
- Tables
- Reports
- Dialogs

Those should remain shared and themed.

## 6. Splash And Startup

Professional splash should be native QML, not WebEngine.

Requirements:

- Appears once.
- No disappear/reappear.
- Main window appears once.
- No jelly/drop animation.
- No GPU warmup visibility flash.
- The CSPM splash must fully close/disappear before the main window is shown.
- The main window may preload while hidden, but first-pixel visibility must not be used to release the splash.

Console keeps the existing animated splash and jelly behavior.

## 7. Animation And Audio Policy

Centralize motion and sound decisions in `VisualRules`.

Example policies:

```text
Console:
  jellyEnabled: true
  glowEnabled: true
  hoverScaleEnabled: true
  soundProfile: expressive

Professional:
  jellyEnabled: false
  glowEnabled: false
  hoverScaleEnabled: false
  soundProfile: muted/off
```

Components should ask the rules layer instead of checking `appStyle` everywhere.

## 8. Migration Boundary

Before a Flutter or React Native client can be practical, Professional screens need a stable local service boundary.

Target boundary:

```text
Professional UI -> loopback service adapter -> explicit actions/queries/events -> backend/view-model service -> data/store
```

Avoid this:

```text
Professional UI -> scattered QML globals -> mixed UI/business logic -> implicit state
```

The QML phase should gradually extract:

- screen-level state snapshots,
- command names and payload schemas,
- async loading/error contracts,
- validation results,
- navigation intents,
- report/export contracts.

The selected v1 boundary is:

```text
Queries/actions: local HTTP JSON RPC bound to 127.0.0.1
Events: WebSocket event stream on the same local backend process
Security: random per-launch port, per-session token, no LAN/public binding
First proof workflow: Client Directory/Profile
```

The machine-readable baseline for these contracts lives at:

```text
docs/spec/professional_client_contracts.yaml
```

Keep that spec framework-neutral until Flutter versus React Native is chosen deliberately.

When those contracts are stable, the Professional UI can be rebuilt in Flutter or React Native module by module without rewriting the backend.

## 9. Option 3 Application Shell

Professional mode should evolve toward the Option 3 shell:

```text
Compact module rail
+ flyout module menus
+ top work-tab bar
+ full-width central workspace
+ optional contextual drawers/panels
```

The current two-sidebar structure is transitional only:

```text
Top header
+ major-module sidebar
+ permanent Pathway map sidebar
+ workspace
```

The permanent `Pathway map` sidebar should be removed from the default
Professional layout. Its module tool lists should move into temporary flyout menus.

Canonical permanent shell elements:

- `TopHeader`: logo/app identity, global search/command entry, settings/window controls.
- `ModuleRail`: compact left rail for major modules only.
- `WorkTabBar`: active workspaces, not module categories.
- `BreadcrumbBar`: module/screen/record orientation for the active tab.
- `WorkspaceHost`: full-width active screen area.

Canonical temporary/contextual shell elements:

- `ModuleFlyout`: replaces the permanent pathway sidebar.
- `RightDrawer`: contextual detail/action panel for selected records.
- `CommandPalette`: power-user search and command execution.
- `Modal dialogs`: focused confirmations and edit flows.

The left rail should contain only major modules such as:

- Clients & Matters
- Docketing & Deadlines
- Billing & Invoicing
- Finance & Ledger
- Reports
- Admin / Settings

The top work tabs must represent active work, for example:

- `Time Docket Entry`
- `WIP-to-Bill Workbench`
- `Client: Wild Bunch`
- `Matter: M-2025-001`
- `Invoice Draft #1042`

They must not become module tabs like `Clients | Docket | Billing | Finance`.

Generic tools should usually be single-instance tabs. Record-specific workspaces can
open multiple tabs keyed by entity ID. Dirty tabs must show an unsaved indicator and
guard close actions with save/discard/cancel choices.

The shell state model should be explicit and portable:

```text
activeModule
activeFlyoutModule
openTabs
activeTabId
pinnedTabs
dirtyTabs
rightDrawerState
railPinned
railExpanded
```

Reusable component targets:

- `AppShell`
- `TopHeader`
- `ModuleRail`
- `ModuleFlyout`
- `WorkTabBar`
- `WorkspaceHost`
- `BreadcrumbBar`
- `RightDrawer`
- `CommandPalette`
- `DirtyTabGuard`

This shell can be prototyped in QML first, but it should be designed as if the same
navigation model, tab model, routes, and workspace contracts will later be consumed
by Flutter or React Native.

## 10. Rollout Phases

### Phase 1: Foundation
- Normalize and persist `appStyle`.
- Audit every settings load path to ensure saved `appStyle` is restored.
- Ensure Settings Menu toggles style reliably.
- Define the `VisualRules` / `SemanticTheme` token contract.
- Expand `VisualRules` / `SemanticTheme` into the canonical token layer.
- Add basic tests for setting save/load.

### Phase 2: Startup And Shell
- Finish Professional one-shot QML splash.
- Finish Professional fast-open main window path.
- Professional sidebar/nav styling.
- Confirm Console startup behavior unchanged.

### Phase 2.5: Option 3 Shell Architecture
- Save and preserve the Option 3 rebuild brief as the canonical UI architecture reference.
- Define the shared navigation/module model from current pathway-map screens.
- Build a Professional shell prototype with compact rail, module flyouts, work tabs, breadcrumb bar, and workspace host.
- Move pathway-map navigation into flyouts for Professional mode.
- Add explicit work-tab opening logic, including single-instance generic screens and multi-instance record screens.
- Add dirty-tab indication and guarded close behavior.
- Keep existing QML screens mostly intact inside `WorkspaceHost` while shell behavior is proven.
- Keep Console shell behavior intact unless the user explicitly requests otherwise.

### Phase 3: Shared Controls
- Refactor buttons, text fields, comboboxes, popups, cards, tables.
- Remove pill/glow/jelly styling from Professional.
- Keep Console visuals intact.

### Phase 3.5: QML Architecture Hardening
- Split oversized QML views into smaller screen/component boundaries.
- Move Professional workflow state toward explicit screen state objects.
- Reduce direct QML global access in Professional paths.
- Create reusable Professional scaffolds for work surfaces, side navigation, forms, tables, dialogs, and reports.
- Document backend calls, payloads, events, and navigation intents per major workflow.
- Treat this as migration prep for Flutter/React Native, not a cosmetic cleanup.

### Phase 4: Primary Workflows
- Docketing & deadlines.
- Clients & matters.
- Billing & invoicing.
- Finance & ledger.
- Reports/export screens.
- Legacy Dockets Upload Feature: On-demand Excel parsing with fuzzy client matching, durable recent-source history, and explicit All Records / Missing Records Only workflows accessible in both styles.
  - Missing Records Only must scan every source sheet, including undated rows, and determine new/changed/already-imported/review-required status from stable source identity plus a persistent import ledger instead of relying on record dates.
  - Remember previously selected/used source workbooks in most-recent-first order, auto-populate the last used source, and keep Browse available for local or OneDrive/SharePoint-synced workbook files. Direct SharePoint web links require an authenticated download path before replacing local file selection.
  - Start reconciliation with a read-only row review table showing counts and checkboxes for new rows, then commit only explicitly selected rows through an `Add Selected` action.
  - Before record writes begin, show a real source-versus-current-data analysis stage from the isolated importer, then hand off to planned per-sheet write progress. Keep the workspace protected by the import modal while allowing the entire app to minimize to and restore from the taskbar.
  - Allow the user to confirm cancellation at any cancellable import stage. An accepted cancellation must terminate the isolated worker, release any pending duplicate prompt, discard staging, restore the dedicated pre-import snapshot if necessary, and verify the active workbook hash before reporting cancellation complete.
  - Run workbook-heavy imports in an isolated staged process and replace the active workbook atomically only after full success, so a parser/runtime crash cannot take down CSPM or leave production data half-imported.
  - Keep staged imports accurate while reducing workbook I/O: accumulate already-validated canonical mutations inside the staged process, persist changed tables in one staged-workbook save, reopen and semantically verify every changed table, then run the full workbook-integrity gate before atomic replacement.
  - Retain per-phase import timing metrics so future performance work can target measured bottlenecks without weakening validation, duplicate handling, cancellation, or rollback guarantees.
  - Resolve docket `Matter_ID` values through the matters imported or selected earlier in the same run, preserve legacy matter IDs as matter numbers, and route blank/unmapped references into clearly named review-required matters instead of committing client-only time entries.
  - Require the staged workbook to pass the canonical workbook-integrity check before atomic replacement; preserve failed staging data for diagnosis and leave the active workbook unchanged.

### Phase 5: Secondary Views And Polish
- Settings.
- Edge dialogs.
- Empty states.
- Error states.
- Tooltips.
- Resize/maximize/minimize behavior.
- Optional Professional icons/counts.

### Phase 5.5: Pre-Live Trust, Security, And Data Protection
- Define mandatory data integrity checks for the active workbook before live use:
  workbook openability, schema/table presence, stable IDs, duplicate IDs, number
  sequence collisions, required fields, financial/report reconciliation, and
  copies, Git cloud workbook backups, offsite/cloud retention, and tested
  recovery steps.
- Temporary Git cloud data mode: until the configurable external database
  location exists, Git cloud backup/restore must include the backup/restore
  scripts themselves and the full database artifact tree under `data/` and
  `src/python/data/`.
- Future live-data location: make the active database path user-configurable,
  with a likely SharePoint/OneDrive folder target. After that is implemented
  and covered by its own backup/restore policy, Git cloud backups should stop
  storing live database files and return to source/spec/script history only.

### Phase 6: Professional Client Migration Prep
- Build the Expert wireframe/client outside QML from the Professional Option 3
  shell: compact rail, flyouts, work tabs, breadcrumb/header, full workspace, and
  contextual drawer.
- Keep React Native Web as the quick browser Expert sketch and Flutter as the
  native Windows desktop Expert candidate.
- Decide whether Flutter or React Native is the better fit after the UI/backend boundary and Option 3 shell contracts are proven against a visual client.
- Use the selected transport layer for the future client: local loopback HTTP JSON plus WebSocket events.
- Build a small Professional-client proof of concept against Client Directory/Profile and the Option 3 shell model.
- Keep Console QML behavior intact while the Professional client is developed.

### Phase 7: Module-By-Module Professional Client Replacement
- Rebuild Professional workflows outside QML one module at a time.
- Use the same backend/data contracts.
- Keep QML Professional screens available until each replacement is verified.
- Retire QML Professional modules only after parity checks pass.

## 11. Verification Plan

### Static/Sandbox-Safe
- Run `scripts/qmllint.ps1`, never direct `qmllint.exe`.
- Run Python compile checks only if Python changes.
- Run targeted unit tests for settings persistence if available.
- Run targeted backup/restore contract tests after changes to Git cloud backup
  scripts, restore scripts, workbook handling, data integrity checks, or security
  policy docs.
- Run `git diff --check`.

### Outside-Sandbox Startup Validation
Run outside sandbox:

```powershell
.\launch.ps1
```

Verify:

- Console style still uses old splash/jelly/audio behavior.
- Professional splash appears exactly once.
- Professional main window appears exactly once.
- The CSPM splash disappears before the main window appears; there is no visible overlap.
- No first-frame flash.
- Professional controls are readable, non-pill, non-bubbly.
- Theme toggle saves and restores after restart.
- Core workflows behave identically in both styles.
- In Professional mode, the permanent second `Pathway map` sidebar is gone after the Option 3 shell phase.
- Major modules open flyouts, flyout items open or activate work tabs, and active work receives most of the window width.

## My Opinionated Recommendation

Make Professional light, quiet, and almost boring in the best way: crisp forms, excellent alignment, restrained navy/slate accents, very low radius, minimal shadows, no gimmicks. Let Console be the expressive one. The more different their personalities are, the more valuable the toggle becomes.

Also: keep the migration goal honest. If Professional is eventually moving to Flutter or React Native, every major QML cleanup should either improve the current user experience or clarify the future client boundary. Pure QML elegance is not the prize; portability of the Professional experience is.

## Future Storage Architecture Constraint

<!-- CSPM_FUTURE_DATA_ARCHITECTURE_V1 -->

Current implementation remains focused on stabilizing Excel-backed workflows. Future storage is sequenced as local SQLite, then controlled OneDrive snapshot transfer, then possible Azure SQL behind a secure API.

Current decisions should preserve repository abstraction, stable IDs, audit and reversal semantics, reconciliation, and separation between business rules and workbook paths. Do not implement the future phase or undertake a broad refactor without express authorization.

Full requirement: `docs/FUTURE_DATA_ARCHITECTURE.md`.

## 12. Household Budgeting Architecture

Household budgeting remains a required, distinct CSPM product capability. It is a separate financial and reporting context that exists alongside, but not inside, the BusinessUnit and Tax domains.

### Conceptual Relationship
```text
FinancialContext
├── Household
│   └── Household and family-member attribution
└── Business
    └── BusinessUnit and HST-registrant attribution
```

### Domain Separation
A household is not a business. The architecture must strictly distinguish:
- Household or personal financial context (not a BusinessUnit).
- Household member or transaction owner.
- Legal or reporting entity.
- HST registrant.
- Account and Category.
- Budget period and budget category.

### Planned Capabilities
The roadmap reserves the following concepts for the dedicated household budgeting module:
- `Household`, `HouseholdMember`, `HouseholdAccount`
- `Budget`, `BudgetPeriod`, `BudgetCategory`, `BudgetLine`
- `RecurringPlan`, `FinancialGoal`
- Household income and expenses
- Actual-versus-budget reporting and cash-flow forecasting
- Business draws and distributions (explicit personal/business transfers)
- Mixed-use expense allocations
- Dedicated household dashboards and Excel/PDF reporting

For tax and accounting purposes, family/personal transactions require no BusinessUnit, receive 0% ITC eligibility, are explicitly excluded from all business HST calculations, and are classified as `Out of Scope` for business tax reporting.
