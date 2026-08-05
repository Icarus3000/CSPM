# Phase 7: Statements of Account and Ledgers Task List

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

## Invoice Builder Restoration (2026-08-05)

- [x] Restore the Invoice Builder master-detail layout: line items at left, HTML preview at upper right, and fixed settings/actions controls at lower right.
- [x] Theme every Invoice Builder dropdown with an explicit popup and delegate that reads the application light/dark state.
- [x] Add persisted custom-fee reconciliation choices and payload rules for visible discount-line versus hidden adjustment behavior.
- [x] Correct Discount Line invoice rendering so Legal Services Rendered shows the full docketed service amount before the Courtesy Discount reduces it to the agreed flat fee.
- [x] Tie the transparent native splash fade-out to successful root-QML construction rather than a blind startup timeout.
- [ ] Manual foreground verification: launch with .\launch.ps1, confirm the Invoice Builder in both themes, exercise every dropdown popup, and verify the splash handoff with WebEngine enabled.
