# Phase 7: Statements of Account and Ledgers Task List

## Governed Historic Financial Synchronization (2026-08-06)

- [x] Build a source-controlled synchronization service that treats `C:\Users\cschn\OneDrive - LPN\__Invoices (1)\Dockets.xlsm` as the historic financial authority while preserving CSPM-native records after the source snapshot cutoff.
- [x] Normalize legacy receivable footer/duplicate/credit-sign artefacts with ledger and Invoice Log cross-checks; never import vendor expense references as A/R.
- [x] Build an isolated candidate and audit report before any promotion; require source-owned A/R, ledger, and productivity totals to reconcile within $0.02 / 0.01 hours.
- [x] Gate the actual CSPM Financial Dashboard and Productivity Dashboard calculations against independent candidate values, including exclusion of A/R set-offs from cash banked totals.
- [x] Add an explicit promotion command that checks the original target hash and creates a recoverable pre-sync backup; it refuses to proceed while CSPM holds the workbook open.
- [ ] With CSPM closed and after reviewing the candidate audit, promote the approved candidate and manually inspect the dashboard, the paid LIHDC settlement, and the partial $376.13 balance on invoice `26-0069`.

## Portable Current Data and Explicit Data Locations (2026-08-06)

- [x] Replace the repository's older `data/CSPM.xlsm` with the verified current LocalAppData workbook, including the repaired invoice `26-0080`; `Dockets.xlsm` was verified identical.
- [x] Rename the Settings controls to **Shared Data Source Folder** and **Local Save Folder** so their roles are clear on every computer.
- [x] Require a selected shared source to contain valid `CSPM.xlsm` and `Dockets.xlsm` files, and defer either location change until a clean restart so the active session cannot push into an unpulled/new location.
- [x] Rebuild and promote the revised `dist/CSPM/CSPM.exe`; the active package remains outside quarantine.
- [ ] On the second computer, manually choose the desired shared source package and local save package from Settings, restart, and confirm the current invoices, clients, and dockets appear.

## Repository Build-Artifact Quarantine (2026-08-06)
- [x] Move seven confirmed stale PyInstaller distribution/build artifacts into `to_delete/` for review rather than permanent deletion.
- [x] Update the release builder to quarantine a replaced package and any unpromoted default staging output instead of deleting it or leaving it at the repository root.
- [x] User approved permanent deletion of the reviewed `to_delete/` quarantine; remove its contents while leaving the active package, live workbooks, and source tree untouched.

## Direct-Fee Invoice Finalization Integrity Repair (2026-08-06)
- [x] Diagnose invoice `26-0080` as a direct-fee finalization defect: a valid `$5,000.00` gross fee / `$5,650.00` total had zero net/HST fields, which propagated into Invoice Log, Receivables, and Ledger.
- [x] Harden draft creation, recalculation, and finalization so direct-fee rows recover net/HST from their positive gross amount and finalization recalculates totals before posting accounting records.
- [x] Add a targeted accounting repair service for historical finalized invoices and validate both the prevention and repair paths against a disposable in-memory workbook.
- [x] With CSPM closed, create a reversible active-workbook backup and repair invoice `26-0080`; confirm the live Invoice Log, Receivables, Revenue ledger, and linked fee entry now show Fees `$5,000.00`, HST `$650.00`, and Balance `$5,650.00`.
- [x] Rebuild and promote the revised `dist/CSPM/CSPM.exe`; the previous release is retained in `to_delete/dist__manual_replaced_release_20260806_103020/`.
- [ ] Manually confirm Invoice Directory/Reverse Invoice show the repaired totals, the high-DPI compact layout, and the separate Directory-to-Reversal flow.
- [ ] Manually delete a draft and confirm the only notification is `Draft <number> deleted` (no preview error).
- [ ] Manually launch `dist/CSPM/CSPM.exe` and confirm that only the native PNG splash appears, the main shell's first visible frame appears beneath it, the PNG begins fading out in that same handoff, and CSPM is foregrounded on its target monitor after the PNG closes.

## Native PNG-Only Splash and Matter Selector Repair (2026-08-06)

- [x] Disable every QML splash creation path; retain only a native PNG centered on the target monitor. The main QML load waits for its visible eased fade-in to finish; at the main window's first painted pixel, the main frame is visible beneath it and the PNG starts its eased fade-out in the same handoff. Restore main-window foreground only after the PNG closes.
- [x] Replace the raw bulk-docket matter dropdowns with searchable, light/dark themed controls that display `Client | Matter Description | Matter Number`.
- [x] Rebuild and promote the repaired `dist/CSPM/CSPM.exe`; preserve the immediately replaced package at `to_delete/dist__replaced_release_20260806_105321/`.
- [ ] Manually verify the PNG-only startup, post-splash foreground focus, selector filtering, and selector appearance in both themes.

## Professional No-Open-Tabs Default (2026-08-06)

- [x] Replace the automatic Professional `Practice Briefing` startup tab with the native Professional no-open-tabs background and its existing quick tiles; preserve explicitly routed starts and already-open workspaces.
- [x] Keep the console-style `HomeGrid` exclusive to its existing non-Professional shell rather than overlaying the Professional home.
- [x] Replace the static no-tabs tiles with a responsive, no-scroll Daily Operations home: daily deadline/time/WIP/A/R KPIs, the four primary daily pathways, a capped priority queue, recent work, and WTD/YTD productivity. It reuses the existing Practice Briefing payload and does not open a workspace tab.
- [x] Rebuild the release and place the complete runnable package at the requested `dist/cspm.exe` path; the immediately prior package is recoverably retained at `to_delete/dist__replaced_release_20260806_124516/`.
- [x] Correct the last-tab close path: choosing **Discard** for unsaved Time Docket Entry changes now removes that tab and transitions to the native no-tabs Daily Operations home instead of recreating the same docket tab.
- [ ] Manually launch CSPM normally and confirm the Professional no-open-tabs background/tiles are the first main-app surface with no Practice Briefing tab opened.

## Tray-Only Relaunch Wake-Up (2026-08-06)

- [x] Have the primary instance listen on `CSPM_IPC_SERVER` and route a duplicate executable launch through the exact same `TrayController.open_cspm()` path as the tray's `Open CSPM` action.
- [x] Do not construct a native splash for `--tray-only`; a duplicate executable detects the existing instance before QApplication/splash startup and only wakes that instance.
- [x] Rebuild and promote the updated `dist/CSPM/CSPM.exe`; Windows denied the builder's directory rename, so the verified candidate was copied into the empty `dist/` after the prior package was moved intact to `to_delete/dist__manual_replaced_release_20260806_111120/`. The built candidate remains intact in `to_delete/` as a recovery copy.
- [x] Rebuild and promote the splash/home revision; the verified `2026-08-06 11:21` candidate was copy-promoted after Windows again denied the builder's final directory rename. The replaced release is retained at `to_delete/dist__manual_replaced_release_20260806_112200/` and the candidate remains intact in `to_delete/dist_staging_20652__unpromoted_build_20260806_112140/`.
- [x] Rebuild and promote the Professional-home correction; the verified `2026-08-06 11:27` candidate was copy-promoted after the same Windows rename denial. The replaced release is retained at `to_delete/dist__manual_replaced_release_20260806_112840/` and the candidate remains intact in `to_delete/dist_staging_18240__unpromoted_build_20260806_112751/`.
- [ ] Manually start `dist/CSPM/CSPM.exe --tray-only`, relaunch `dist/CSPM/CSPM.exe`, and confirm the existing app opens without any splash.

## Backend Canonical Account-Balance Engine
- `[/]` Implement canonical account-balance engine in `excel_repo.py`
  - `[ ]` Create `_canonical_ar_ledger(filters)` method
  - `[ ]` Support parsing parameters (client, billing client, matter, date ranges, open-items only toggle)
  - `[ ]` Correctly merge chronological AR transactions (Invoices, Payments, Credits, Write-offs)
  - `[ ]` Apply progressive balance calculations (Opening Balance + Charges - Credits = Running Balance)
- `[ ]` Refactor `get_client_ledger_report` to consume the engine for accurate UI balances.
- `[ ]` Refactor `statement_of_account_report` to consume the engine for robust external payloads.

## QML UI for Statement of Account
- `[ ]` Build `StatementOfAccountView.qml`
- `[ ]` Wire progressive disclosure options (Scope picker, Date range picker, Open items toggle)
- `[ ]` Implement robust layout matching the Professional theme (Semantic colors, standardized tables)

## Contextual Integration
- `[ ]` Wire context pathways to trigger Statement generation from:
  - `[ ]` `ClientProfilePanel`
  - `[ ]` `MatterProfilePanel`
  - `[ ]` `PracticeBriefingView` (optional/advanced)

## Testing and Verification
- `[ ]` Add UI automated tests (`test_statement_of_account_ui.py`) to verify progressive disclosure and display.
- `[ ]` Create backend unit tests (`test_canonical_ar_ledger.py`) to verify calculations for partial/multi-invoice payments.


### Phase 9 Status Update (2026-07-30)
- **Settings-Precedence Regression**: RESOLVED (authoritative path C:\Users\cschn\AppData\Local\CSPM\user_settings.json).
- **Professional-Interface Launch**: VISUALLY CONFIRMED BY CORY (approx. 18s).
- **Full Automated Suite**: PASS (393 passed, 12 skipped, 0 failed).
- **Production Build**: DEFERRED BY CORY (CSPM is in active development, not yet distributed).
- **Phase 9 A+ Status**: NOT YET CLAIMED (Cory has additional bugs to address).
- **Phase 10 Ask CSPM**: PAUSED.
- **SQL and SQLite**: PAUSED.
- **System-Tray Timekeeping**: Deferred until application is stabilized.
- **Gate B**: Evidence preserved, but production/installer readiness is deferred.


### Phase 9 Icon Repair Update (2026-07-30)
- **Stale CSPM.exe Discovered**: The previous CSPM.exe (approx. 16:28 PM) predated the settings repair and was stale.
- **Previous Executable Timestamp**: Thu Jul 30 16:28:50 2026 (SHA-256: 16edeb1b4dd75d2046b8ddc51be55ce759fe30b72c76ac5859cc69745a6c0e64)
- **Fresh Candidate Timestamp**: Thu Jul 30 18:06:48 2026 (SHA-256: 85B87AABC454A2470EBD483C51DE6FEA614763F029512C2125C6D2A6E36C9C80)
- **Icon Root Cause**: The PyInstaller build configuration (scripts/build_release.py) was completely missing the --icon argument for the main application, causing Windows to fall back to generic icons or cached stale icons.
- **Repairs**: Added --icon=src/assets/app_icon.ico to the cmd_main build command.
- **Test Results**: Focused icon identity test passed. Full suite passed (398 passed, 12 skipped, 0 failed).
- **Candidate Build Result**: A fresh, disposable candidate build was successfully generated. Packaged templates do not match live workbooks.
- **Visual Status**: Cory visual status is PENDING (needs to inspect the uniquely named executable).
- **Production Status**: Production readiness and Phase 9 A+ are NOT CLAIMED.

### Phase 9 Active Data Routing Repair (2026-07-31)
- **Startup Logic Contract**: Refactored `AppController.__init__` to load `localDataDir` synchronously and apply `override_data_dir` BEFORE repository and facade instantiation.
- **Empty-Data Safety Barrier**: Implemented strict Phase 4 checks. CSPM.exe will no longer silently seed a blank LocalAppData practice if the configured `localDataDir` is unavailable, or if a valid known project data folder exists (detects frozen/packaged context).
- **Settings Integrity**: Verified that `localDataDir` overrides are not overwritten by the deferred settings load.
- **Verification**: Wrote `test_data_routing_guards.py`. All deterministic path-resolution assertions pass.

## Client Directory Backend-Boot Repair (2026-08-05)

- [x] Prevent the deferred settings worker from starving or being dropped before the critical workbook backend boot runs.
- [x] Rebuild the packaged `dist/CSPM/CSPM.exe` after the repair; only governed blank templates are bundled, and the active LocalAppData workbook remains untouched.
- [x] Historical check: `leviathan` returned 26 rows; this exposed the now-corrected broad metadata/parent-client search defect.

## Directory Metrics & Profile Navigation Repair (2026-08-05)

- [x] Expose the live dashboard summary as a QML slot and push the live payload into the module header after backend boot.
- [x] Restrict Client Directory search to client identity and contact fields, excluding shared parent-client metadata and operational notes.
- [x] Route a Client Directory double-click directly into the populated Edit Client Profile form, with Return/Cancel leading back to the selected Client Profile 360.
- [ ] Manual foreground verification: launch `dist/CSPM/CSPM.exe`; confirm `Leviathan Private Network` returns exactly one row, the badge reads `Active Matters: 192 (Clients: 113)`, and double-clicking that row opens its populated `Edit Client Profile` form.

## Invoice Builder Restoration (2026-08-05)

- [x] Restore the Invoice Builder master-detail layout: line items at left, HTML preview at upper right, and fixed settings/actions controls at lower right.
- [x] Theme every Invoice Builder dropdown with an explicit popup and delegate that reads the application light/dark state.
- [x] Add persisted custom-fee reconciliation choices and payload rules for visible discount-line versus hidden adjustment behavior.
- [x] Correct Discount Line invoice rendering so Legal Services Rendered shows the full docketed service amount before the Courtesy Discount reduces it to the agreed flat fee.
- [x] Tie the transparent native splash fade-out to successful root-QML construction rather than a blind startup timeout.
- [ ] Manual foreground verification: launch with .\launch.ps1, confirm the Invoice Builder in both themes, exercise every dropdown popup, and verify the splash handoff with WebEngine enabled.

## Direct Fee Docket Entry & Professional Splash (2026-08-05)

- [x] Add `Fee Docket Entry` directly below `Time Docket Entry` in the Docketing & Deadlines flyout and route it to its own B02 workspace tab.
- [x] Add a matter-linked direct-fee form that saves a positive zero-hour/zero-rate WIP entry, preserving the normal WIP, draft, and invoice pipeline.
- [x] Keep fee entries separate from the time-docket daily aggregation, and verify in a temporary workbook that a fee-only matter produces a flat-fee invoice payload.
- [x] Remove the Professional splash one-shot path that hid the logo and completed immediately; keep a native logo fallback visible while the animated renderer warms up.
- [ ] Manual foreground verification: launch `dist/CSPM/CSPM.exe`, confirm `Fee Docket Entry` appears directly below `Time Docket Entry`, save a fee against a matter, and confirm the Professional splash logo visibly dissolves in and out before the main window opens.

## WIP Empty-Selection Guard & Packaged Splash Assets (2026-08-05)

- [x] Keep `Create Draft Invoice` clickable with no WIP selection and show a clear, non-blocking explanation instead of starting a build operation.
- [x] Reject empty draft requests in both the billing controller and invoice-draft service, preventing blank invoices from any call path.
- [x] Bundle the root `assets/` folder in release builds and fail the release build if required CSPM splash assets are absent.
- [x] Rebuild and promote the normal `dist/CSPM/CSPM.exe` with the required `CS.svg` and `splash_logo.svg` assets present.
- [ ] Manual foreground verification: click `Create Draft Invoice` with no selected WIP and confirm the warning leaves the builder responsive; then launch `dist/CSPM/CSPM.exe` and confirm the CSPM logo visibly fades in and out before the main window appears.

## Invoice Service Client & Matter Context (2026-08-06)

- [x] Clearly distinguish the invoice `Bill To` recipient from the client receiving legal services.
- [x] Show the actual billed-entry client and matter number/name in a persistent `Legal Services For` block on every invoice, including direct-fee / flat-fee invoices.
- [ ] Manual foreground verification: preview an ordinary invoice and a fee-only invoice; confirm `Bill To`, `Client`, and `Matter` are each visible and accurately identify the work.

## Invoice Date & Close-to-Tray Preference (2026-08-06)

- [x] Make the invoice date explicit in the Invoice Builder, supporting typed `YYYY-MM-DD` values and calendar selection.
- [x] Move the date control into the active `InvoiceBuilderWorkspace` billing-controls panel; the first implementation was in an explicitly hidden legacy fallback layout.
- [x] Validate and persist the selected draft date, invalidate the cached payload, and regenerate the HTML preview immediately.
- [x] Add a persisted Settings toggle for `Close to tray`; use it in the main-window close path instead of unconditionally quitting CSPM.
- [ ] Manual foreground verification: select a draft invoice and verify the blue `Invoice date` panel directly below the preview accepts `YYYY-MM-DD` typing and `Choose date` opens the calendar; set `Close to tray` On, close the main window, and confirm the tray remains usable and restores CSPM; then set it Off and confirm close exits CSPM.

## Invoice Line-Item Field Clarity & Fee Editing (2026-08-06)

- [x] Add light-gray contextual placeholders for blank Date, Description, Hours, and Hourly Rate inputs in the Invoice Builder line-item editor.
- [x] Identify direct fee entries in the draft-line payload and replace the time-only fields with one `Fee amount ($)` input when editing a fee.
- [x] Persist a time line's changed hourly rate as well as hours; persist a fee line's amount while preserving its zero-hour/zero-rate shape.
- [ ] Manual foreground verification: edit one time docket and one direct fee line in an invoice draft; confirm the time line shows Hours/Rate while the fee line shows only Fee amount, then save and confirm the preview total changes.

## Bulk Docket Move Between Matters (2026-08-06)

- [x] Add a Docketing & Deadlines workspace for reviewing and moving multiple time or direct-fee dockets from one matter to another over an inclusive date range.
- [x] Allow the destination matter to belong to another client; move selected dockets to that matter's client and billing-parent relationship as part of the same update.
- [x] Protect invoice-linked dockets (draft or finalized) from reassignment; allow selected or all eligible unbilled dockets and write a durable audit note for every move.
- [x] Replace the raw Qt matter popups with searchable application-themed selectors. Matter choices now display as `Client | Matter Description | Matter Number`.
- [ ] Manual foreground verification: open `Move Dockets Between Matters` in both light and dark themes, search/select source and destination matters, move a selected subset and then all eligible dockets for a date range including a cross-client destination; confirm the destination matter/client display and that invoice-linked entries are excluded.

## Third-Party Billing Invoice Context (2026-08-06)

- [x] When the bill-to client differs from the service client, omit the internal matter-number code from the invoice service context and matter headings.
- [x] Identify the actual service client and use the matter's plain-English Description (falling back safely to Matter Name) in its place.
- [x] Render third-party service context compactly as `Matter: <client name> | <matter description>` on one line; retain the normal two-field context for ordinary invoices.
- [ ] Manual foreground verification: preview a third-party invoice and confirm the `Legal Services For` block renders `Matter: <service-client name> | <plain-English matter description>` with no coded matter number.

## A/P Settlement Set-Off (2026-08-06)

- [x] Add a linked, non-cash A/P set-off payment method that allocates one supplier-bill settlement against one or more existing receivables, including partial invoice allocations.
- [x] Validate every allocation before saving and post A/P, A/R, ledger, time-entry payment state, expense clearing account, and audit evidence in one atomic workbook replacement.
- [x] Add a matching whole-set-off reversal that restores the A/P bill and all affected receivables together.
- [x] Rebuild and promote the runnable package at `dist/cspm.exe`; preserve its flat executable/_internal/data/recovery layout for future builds.
- [x] Allow an A/P bill total to be entered as the authoritative amount; derive subtotal/HST safely for taxable and HST-exempt bills.
- [x] Make the set-off allocation editor independently vertically scrollable so every allocation can be pasted and reviewed.
- [x] Rebuild and promote the A/P usability repair at `dist/cspm.exe` (SHA-256 `39CA22521371289F5A2E1700CFB9A1F613241C2AA2E2A16660078713B04AE763`).
- [x] Replace raw worker tracebacks in A/P with their concise validation message.
- [x] Stop automatically applying the LIHDC agency share to dockets whose `AmountToYou` is already net of that share.
- [x] Replace typed A/R set-off allocations with a searchable receivable-selection workflow that supports full or partial allocations and an in-dialog balancing total.
- [ ] With CSPM closed, create a recoverable backup and repair the pre-existing double-split balances for invoices 26-0066 and 26-0069 from the supplied July settlement schedule before posting the set-off.
- [ ] Manually verify the set-off workflow in CSPM against a copy of the production workbook before entering the July 2026 settlement.

## Startup Focus Safety Repair (2026-08-06)

- [x] Remove the main-window startup focus lock and every automatic Win32 foreground/topmost escalation.
- [x] Limit splash handoff to one regular Qt activation request and prevent delayed startup timers from reclaiming focus.
- [x] Add a regression test that rejects topmost or foreground-stealing code in the main startup path.
- [x] Limit the settled native window to the visible canvas after confirming the previous release's actual native window covered the full 2380x1500 monitor.
- [x] Restore the backend-boot trigger as a settlement lifecycle action; confirm read-only that the live workbook retains 115 clients, 194 matters, and 682 time entries.
- [x] Rebuild and promote `dist/cspm.exe` (SHA-256 `C2416E8B54FF464ACF37F44B35C615C3E66C985BCFDEAAC944BC725622330791`).
- [ ] Manually confirm that the visible dashboard loads existing data and that another app and the taskbar remain clickable on CSPM's monitor.
