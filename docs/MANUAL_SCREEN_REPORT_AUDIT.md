# Manual Screen, Window, And Report Audit Playbook

Updated: 2026-06-11

## Mandatory Next-Agent Handoff

After completing the required startup reading from `AGENTS.md`, the next agent
must open this file before continuing UI work. This file is the active manual
audit handoff for the screen-by-screen, window-by-window, report-by-report review.

The next agent must not skip ahead to broad refactors. The operating mode is:

```text
one observed problem -> one diagnosis -> one scoped fix -> safe checks -> user
manual confirmation -> next observed problem
```

Do not move to the next problem until the user explicitly confirms the previous
problem is fixed in the real application.

Current static formatting note, 2026-06-11: the first Professional formatting
cleanup pass added shared typography tokens and applied them to the common
placeholder-hosted and docketing-hosted workspace title zones. Follow-up static
UI contracts now pass, but this still needs foreground screenshot validation
through the normal audit loop.

## Audit Goal

Complete a human-guided audit of every user-visible CSPM surface while preserving
the current architecture direction:

- `Console` keeps the expressive legacy experience.
- `Professional` continues toward the Option 3 shell:
  compact module rail, flyout module menus, top work tabs, breadcrumb/header,
  full-width workspace, and contextual drawers.
- Both styles must use the same backend, workbook data, permissions, reports,
  imports, docketing logic, persistence, and save/export behavior.

The audit is not only visual. Each screen must be checked for:

- navigation entry and return paths,
- data loading from the active workbook,
- create/edit/save/cancel behavior,
- dirty-tab and close-guard behavior where applicable,
- detached-window behavior where applicable,
- report drilldown/export behavior where applicable,
- readable controls, labels, tables, popups, and error states in both styles.

## Strict Review Loop

Use this loop for every issue:

1. Tell the user the next narrow thing to test.
2. The user tests it in the foreground with `.\launch.ps1`.
3. At the first failure, the user stops and reports only that problem.
4. Reproduce by code inspection, static checks, targeted tests, or a focused GUI
   smoke only if useful and safe.
5. Fix only the reported problem and the smallest supporting contract needed.
6. Run sandbox-safe/static checks first:
   - Python compile checks for touched Python files.
   - `scripts/qmllint.ps1` or repo-root `qmllint.ps1` only for QML.
   - Targeted unit/UI guard tests when they exist.
   - `git diff --check`.
7. Ask the user to retest the exact same issue with `.\launch.ps1`.
8. If the user says it is not fixed, continue on the same problem.
9. If the user confirms it is fixed, update `task.md` and `implementation.md`
   if the fix changes status or leaves a new manual check.
10. Only then choose the next audit item.

Do not batch unrelated fixes unless one root cause clearly blocks the current
issue. If a second issue is noticed while fixing the first, record it as pending
and return to it later.

## User Problem Report Template

Ask the user to report failures in this shape:

```text
Screen/window/report:
Style: Console | Professional | both
Steps:
Expected:
Actual:
First bad moment:
Screenshot/log path, if any:
Can continue testing after this? yes/no
```

If the user gives a screenshot, inspect the visible symptom first, then map it to
the smallest likely component or data path.

## Required Test Split

Follow the repository WebEngine policy:

- Static/safe checks can run in the agent environment.
- Do not treat sandboxed WebEngine startup failures as app-logic failures.
- Real splash/WebEngine/window/focus behavior must be validated outside the
  sandbox or by the user through `.\launch.ps1`.

Every result report must explicitly separate:

- checks that were static or sandbox-safe only,
- real outside-sandbox/WebEngine/manual checks completed by the user or agent,
- GUI/WebEngine checks not yet validated.

## Known Starting Point

Start the next manual audit with:

```text
Audit 1: New Matter Client dropdown and New Client handoff
```

Steps:

1. Launch with `.\launch.ps1`.
2. Test Professional first.
3. Open `Clients & Matters`.
4. Open `New Matter`.
5. Open the `Client` dropdown.
6. Confirm workbook-backed clients appear.
7. Select the final `new client` command option.
8. Confirm `New Client Wizard` opens or focuses.
9. Save a safe test client or cancel, based on user preference.
10. Confirm focus returns to `New Matter`.
11. If saved, confirm the saved client is selected and billing/matter-number
    autopopulation refreshes.
12. Repeat in Console.
13. Repeat from a detached New Matter window after the tab/window path is stable.

This is the first audit target because current docs already mark the live
coordinate-click smoke as inconclusive and the focused human session as pending.

## Audit Order

Work in this order unless the user reports a more urgent blocking defect.

1. Startup and style selection
   - Professional splash once, no flash, correct monitor, main window once.
   - Console startup unchanged.
   - Settings style toggle persists across restart.

2. Option 3 shell and window lifecycle
   - Module rail opens flyouts by click.
   - Flyout selections open or activate work tabs.
   - Breadcrumb matches active screen/record.
   - Generic tabs are single-instance.
   - Record tabs are entity-keyed where record identity exists.
   - Right-click tab detach opens a focused detached window.
   - Closing detached windows and Return to Dock behave predictably.
   - Dirty tabs show indicators and close guard works.

3. Clients & Matters
   - Client Directory.
   - Client Profile.
   - New Client Wizard.
   - Matter Directory.
   - Matter Profile.
   - New Matter Wizard.
   - New Matter -> New Client -> New Matter handoff.
   - Global Search client/matter opening paths.

4. Docketing & Deadlines
   - Time Docket Entry.
   - Fee Docket Entry if present.
   - Deadline/calendar workflows.
   - Docket Activity Report drilldown to time-entry edit.
   - Trademark Directory.
   - Trademark Filing.
   - External CIPO links through Edge.

5. Billing & Invoicing
   - WIP-to-Bill Workbench.
   - Pre-Bill Editor.
   - Invoice Builder.
   - Invoice reversal/credit memo.
   - Payment Entry.
   - Write-off/Adjustment Entry.
   - Collections Queue.
   - Transaction-backed billing flows.

6. Finance & Ledger
   - Transactions Master.
   - Vendor and expense/category setup.
   - Payment method/reference setup.
   - HST/GST remittance and tax filing register.
   - Ledger views and finance dashboards.

7. Reports and exports
   - Reports module entry/flyout/work-tab behavior.
   - Each report opens in the correct shell/window context.
   - Filters load real options and validate bad input.
   - Tables are readable and resizable.
   - Empty states are clear.
   - Drilldowns preserve record identity.
   - Export commands produce expected files and permissions.
   - Detached report windows keep the app icon and correct focus behavior.

8. Admin, Settings, and operations
   - Settings and theme picker.
   - Legacy Dockets import source dropdown/recent paths.
   - Legacy Dockets Analyze -> Import progress handoff.
   - Duplicate prompt choices.
   - Confirmed cancellation and rollback result.
   - Support diagnostics.
   - Backup/restore visible command surfaces if present.

9. Secondary surfaces
   - Edge dialogs.
   - Confirmation dialogs.
   - Error states.
   - Empty states.
   - Tooltips.
   - Resize, maximize, minimize, restore.
   - Taskbar icon for main, detached, report, and dialog windows.

## Per-Screen Checklist

For each screen, verify both `Console` and `Professional` unless the screen is
explicitly Professional-only:

- The screen is reachable from the expected module flyout/pathway.
- The screen title, breadcrumb, and active tab label are correct.
- Initial data loads from the active workbook or documented static model.
- Loading, empty, and error states are visible and readable.
- All dropdowns contain real options and no stale demo data.
- Required fields are obvious and validation messages are actionable.
- Labels do not overflow, clip awkwardly, or escape their controls.
- Tables show headers, rows, selection, sorting/filtering if available, and
  horizontal/vertical scrolling without hiding controls.
- Primary actions are present, enabled only when valid, and produce clear
  success/failure feedback.
- Save/cancel/close behavior does not lose data silently.
- Dirty state is reflected in work tabs where applicable.
- Keyboard focus order and obvious keyboard actions work.
- Resizing narrow/wide windows does not collapse forms into unusable columns.
- Professional uses restrained tokens; Console keeps the expressive styling.

## Per-Window Checklist

For every main, detached, report, modal, and popup window:

- Opens on the expected monitor and in a sensible geometry.
- Gets foreground focus when opened intentionally.
- Does not steal focus after being closed or docked.
- Uses the saved CSPM icon in the Windows taskbar.
- Minimize/restore works.
- Maximize/restore works where supported.
- Close behavior is guarded when dirty or destructive.
- Detached windows preserve record/report identity.
- Modal overlays block only the intended workspace and leave required taskbar
  access available.

## Per-Report Checklist

For every report:

- Opens from the Reports module or expected workflow action.
- Opens or activates the correct work tab/window.
- Filter controls load real options and validate dates/ranges.
- Running the report gives visible progress or a clear wait state.
- No-data results are explicit and not blank/confusing.
- Result rows align under headers and remain readable.
- Currency, date, duration, and status formatting are consistent.
- Drilldown actions open the correct record with explicit entity identity.
- Export/print/save commands work and explain destination/failure.
- Detached report windows preserve taskbar icon, focus, and return/dock behavior.

## Finding Severity

Use these buckets:

- `Blocker`: prevents launch, navigation to a whole module, save, restore, or
  safe data use.
- `High`: wrong data, data loss risk, broken save/export, broken report
  drilldown, impossible-to-use form/table.
- `Medium`: visible workflow break, styling severe enough to impede use, focus
  or window lifecycle issue with workaround.
- `Low`: polish, minor alignment, awkward copy, tooltip, minor visual mismatch.

Fix blockers and high severity first. Do not polish around a broken workflow.

## Audit Ledger Guidance

Use `task.md` for checklist status and `implementation.md` for implementation
and validation notes. If a long audit ledger becomes necessary, create it under
`docs/audit/` and link it from this file plus `task.md`.

Current full-audit ledger:

```text
docs/audit/full_ui_audit_20260611.md
```

The current ledger is Professional-first, covers the 72 canonical workspaces
from `ModulePathways.js`, reserves screenshot paths under
`logs/audit/20260611/`, and records the active stop-rule finding before broad
report auditing continues.

For each confirmed fix, record:

- date,
- screen/window/report,
- defect summary,
- files changed,
- static checks,
- real `.\launch.ps1`/manual checks,
- remaining risk or follow-up.

## Current Pending Manual Checks

The following are already known to need focused manual validation:

- New Client Parent Client dropdown in both styles.
- New Matter Client, Parent, Matter Type, Status, and Billing Arrangement
  dropdowns in both styles.
- New Matter `new client` save/cancel return flow in Console, Professional
  tabbed mode, and detached New Matter window.
- Time Docket Client and Matter dropdowns in both styles.
- Professional Docket Activity Report row drilldown to populated time-entry edit.
- Detached/report/dialog taskbar icon smoke.
- Legacy Dockets import foreground progress, Analyze-to-Import handoff,
  duplicate prompts, minimize/restore, completion, cancellation, and rollback.
- Legacy Dockets imported review-required matters and finance-row warnings.
- Form visual no-overflow pass for New Client Wizard, New Matter Wizard,
  Transactions Master, and Trademark Filing.

Start with the first item unless the user supplies a more urgent current defect.
