# CSPM 10/10 Execution Roadmap

## Purpose

This is the execution companion to the Professional/Option 3 roadmap. Its goal is
not simply to add features or make screenshots look better. It defines the work
required for CSPM to deserve a **10/10 overall quality rating** as the primary
desktop practice-management system for Cory Schneider Law Office.

At 10/10, CSPM must be:

- financially correct and reconcilable;
- reliable in real daily use, with no recurring first-party runtime errors;
- fast and calm enough for a busy office;
- visually polished, consistent, and legible in both supported styles;
- safe to update, back up, recover, and use with the configured shared-data
  arrangement; and
- proven by evidence, not by an absence of reported bugs.

This plan preserves the established architecture:

- **Professional** remains the canonical Qt/QML Option 3 interface;
- **Console** remains supported and uses the same business/data logic;
- a future Flutter/React Native **Expert** tier may clone the mature
  Professional experience, but it is not a prerequisite for CSPM 10/10; and
- Excel remains the production-authoritative data store unless the owner
  explicitly approves a storage migration.

The canonical interface destination remains
`docs/CSPM_Option_3_Interface_Rebuild_Brief.md`. This document does not replace
that brief; it turns quality, financial trust, and release readiness into an
ordered checklist.

## How the roadmap is run

### Quality rules

1. **Correctness before polish.** A beautiful payment screen that can create an
   incorrect balance is not acceptable.
2. **One reported defect at a time.** Follow the manual-audit stop rule: fix,
   run sandbox-safe checks, have Cory retest the exact problem in the real app,
   then record the result before moving on.
3. **No silent money changes.** Any repair, historic synchronization, or data
   migration needs a read-only plan, a verified backup, reconciliation evidence,
   and explicit authorization before the active workbook is changed.
4. **A clean log is a product requirement.** First-party QML/worker/traceback
   errors in a supported workflow are defects, even when the visible screen
   appears usable.
5. **A packaged release is a separate artifact.** Source tests passing is not
   evidence that `dist/cspm.exe` is correct. Each promoted package must be
   checked independently.
6. **Both styles share the same outcome.** Professional and Console may look
   different, but neither may have different accounting, persistence, report,
   or navigation correctness.

### Severity and release rules

| Severity | Meaning | Release treatment |
|---|---|---|
| P0 | Data loss/corruption, incorrect money posting, security/privacy breach, or app cannot start | Stop all unrelated work; no release until fixed and recovered. |
| P1 | Core workflow fails, produces a runtime error, or cannot be completed reliably | Fix before the next normal release; require live retest. |
| P2 | Important workflow is confusing, inconsistent, slow, or lacks a safe recovery path | Schedule in the current quality milestone before 10/10 sign-off. |
| P3 | Cosmetic, wording, or non-blocking enhancement | Triage; complete during the final polish pass if it affects a daily surface. |

**10/10 release rule:** there can be no known P0, P1, or unresolved P2 defect
in a primary workflow. P3 items may remain only when documented, harmless, and
outside the quality promise of the shipped workflow.

## Current baseline

The latest promoted executable is `dist/cspm.exe` with SHA-256:

```text
7688024CF76F5B41F1E60B9BC91EF44BD155C524260217D06C45BF368671DBA7
```

The current baseline is feature-rich and visually promising, but it is not yet
10/10 because the following work is open:

- Runtime evidence identifies a WIP row-selection call to the nonexistent
  `SemanticTheme.tableSelectedBackground()` function.
- Invoice Builder treats the `draftFinalized` map payload as a string invoice
  number, has an unmatched `onDraftFinalizationError` handler, and is asked to
  run an `applyInitialState()` method it does not expose.
- The canonical A/R ledger work remains incomplete; statements, client ledger,
  payments, credits, and write-offs need one authoritative chronological
  accounting view.
- Historical LIHDC invoices `26-0066` and `26-0069` still require a governed
  correction and real-app verification before set-off use.
- The full Professional-first manual audit is still pending, beginning with
  New Matter's Client dropdown and New Client handoff.
- Recent Statement of Account and Invoice Directory/Payment Entry work have
  focused static coverage, but require foreground validation in the packaged
  application.

The ordered phases below deliberately address these risks before expanding the
feature set.

---

## Phase 0 — Establish the quality baseline

### 0.1 Create a living defect register

- [ ] Create `docs/audit/quality_register.md` with one record per P0/P1/P2
  issue: identifier, owner, discovery date, reproduction steps, screen/style,
  expected result, actual result, source/log evidence, test coverage, and
  retest status.
- [ ] Seed the register with the known WIP semantic-theme error, Invoice Builder
  finalization/state errors, canonical A/R work, historical LIHDC correction,
  and all current manual-audit blockers.
- [ ] Link each register entry to its relevant `task.md` item; do not duplicate
  long prose in multiple planning files.
- [ ] Add a short “known status” label to user-facing release notes: stable,
  candidate, or blocked. Never describe a candidate as production-ready.

**Acceptance:** every currently known P0/P1/P2 issue has an unambiguous owner,
reproduction path, and next verification step.

### 0.2 Capture reproducible baseline evidence

- [ ] With the application closed, hash the active local workbook(s), shared
  source workbook(s), and current `dist/cspm.exe`; record only hashes/paths,
  not client data, in the audit evidence.
- [ ] On the primary office computer, measure three cold starts and record:
  process launch to splash, first application pixel, first usable input, and
  backend-ready time.
- [ ] Capture a clean-start runtime log and a representative log after one
  Billing/WIP/Invoice Builder session. Classify every error by source and
  severity.
- [ ] Capture baseline screenshots for the Daily Operations home, New Matter,
  Time Docket Entry, WIP-to-Bill, Invoice Builder, Invoice Directory, Payment
  Entry, Statement of Account, A/R Aging, and Client/Matter profiles.
- [ ] Record the test monitor resolution, Windows scaling, application style,
  and data-source path used for each manual finding.

**Acceptance:** later performance, visual, and reliability claims can be
compared to a dated baseline rather than recollection.

### 0.3 Freeze risky expansion temporarily

- [ ] Do not start unrelated large modules, storage migrations, or Expert-tier
  work until all Phase 1 P1 defects are fixed and live-retested.
- [ ] Continue small user-requested improvements only when they do not obscure
  the ability to reproduce, test, or release the critical billing workflows.

**Acceptance:** the team can trace each deployed change to a specific quality
goal and regression test.

---

## Phase 1 — Make billing and financial data unquestionable

This is the highest-priority phase. A 10/10 law-office platform cannot have
ambiguous balances, duplicate payment evidence, or a finalization flow that
fails at runtime.

### 1.1 Repair WIP selection and invoice-draft entry

- [ ] Add the missing semantic-theme selected-row function/value, or replace
  the WIP call with the correct existing semantic token. Do not add a
  one-off literal color in the WIP view.
- [ ] Add a focused QML guard test proving that selecting and deselecting a WIP
  row produces no QML exception and that the visual state is accessible in both
  Professional and Console.
- [ ] Verify Select All, Clear, filtering by client/billing client, right-click
  delete docket, and Create Draft Invoice with zero selections.
- [ ] Confirm that a selected time, fee, and disbursement entry flows to one
  draft invoice with the correct fee, tax, client, billing client, and matter
  context.

**Live acceptance:** a user can select ordinary WIP, direct-fee WIP, and a
historical manual time docket without errors or incorrect totals.

### 1.2 Repair Invoice Builder finalization contracts

- [ ] Define the exact `draftFinalized` payload schema in Python and QML. At a
  minimum specify `ok`, `invoiceNum`, `message`, and final PDF path if known.
- [ ] Change Invoice Builder to consume that map intentionally rather than
  assigning the entire map to a string property.
- [ ] Remove the unmatched `onDraftFinalizationError` handler or add a matching
  backend signal; no dead signal handler may remain.
- [ ] On unsuccessful finalization, leave the draft recoverable, stop all busy
  indicators, show a concise user-safe error, and retain enough state to retry
  or correct the draft.
- [ ] On successful finalization, remove the DRAFT presentation, show the
  correct final invoice number, refresh WIP/Invoice Directory/A/R state, and
  open the saved PDF only when requested.
- [ ] Add a real `applyInitialState()` contract to Invoice Builder or guard all
  callers so opening the Builder from WIP, a draft link, search, or a detached
  window never invokes a missing method.
- [ ] Add targeted tests for success, failure, retry, deep-link state, and
  final-preview state.

**Live acceptance:** finalize a safe test draft from WIP-to-Bill, verify the
invoice number and PDF, close/reopen Invoice Directory, and confirm the exact
financial result with no QML error in the fresh log.

### 1.3 Complete the canonical A/R engine

- [ ] Implement `_canonical_ar_ledger(filters)` as the only service that
  assembles invoice charges, payments, credits, write-offs, reversals, and
  set-offs into a chronological invoice/account event stream.
- [ ] Define event fields: stable event ID, effective date/time, invoice ID,
  billing client, service client, matter, event type, charge, credit, source
  table/row, and running balance.
- [ ] Establish deterministic ordering for same-day events and document it.
- [ ] Make event IDs idempotent so a matching Transaction and Ledger entry are
  recognized as one payment, while genuine separate partial payments remain
  separate.
- [ ] Refactor Client Ledger, A/R Aging, Statement of Account, Invoice
  Directory summary, and Payment Entry balance checks to consume that engine.
- [ ] Preserve report “as of date” behavior: a later payment must not alter a
  historical statement balance.
- [ ] Add fixture-based tests for:
  - [ ] invoice with no payment;
  - [ ] one full payment;
  - [ ] multiple partial payments on different dates;
  - [ ] credit/write-off;
  - [ ] reversal;
  - [ ] set-off;
  - [ ] third-party billing client/service client;
  - [ ] legacy transaction-only payment;
  - [ ] duplicate ledger/transaction representation;
  - [ ] historical “as of” statement date.
- [ ] Add property-style invariants: no invoice balance below zero unless an
  explicit unapplied credit is represented; charge minus credits equals balance;
  closed/paid state agrees with zero balance; totals reconcile across every
  consuming report.

**Acceptance:** independent test fixtures and a read-only production workbook
probe agree for all selected invoices, clients, and billing clients.

### 1.4 Govern historical corrections

- [ ] Produce a read-only correction plan for invoices `26-0066` and `26-0069`
  that identifies each source row, original value, expected value, and every
  dependent table to be changed.
- [ ] Reconcile the plan to the supplied settlement schedule and ensure the
  expected `26-0069` balance is `$376.13` before requesting approval.
- [ ] With CSPM closed, make a versioned active-workbook backup and verify the
  backup can be opened and hashed.
- [ ] Apply only the approved correction through a reversible service; never
  edit cells manually in the production workbook.
- [ ] Re-open the repaired candidate, reconcile Invoice Log, Receivables,
  Ledger, linked docket rows, A/R Aging, Client Ledger, Statement of Account,
  Financial Dashboard, and Productivity Dashboard.
- [ ] Promote only after Cory explicitly approves the read-only plan and the
  post-repair reconciliation report.

**Acceptance:** the correction is recoverable, fully reconciled, and visible
correctly in the live app without changing unrelated records.

### 1.5 Prove payment edit behavior end to end

- [ ] Verify a zero timer is ignored and an entered historic time value
  calculates fees continuously as `hours × rate × bill percentage` before save.
- [ ] Verify saving a docket persists the calculated value and updates WIP,
  draft, invoice, and report paths correctly.
- [ ] Verify Invoice Directory’s Unpaid status pill opens Payment Entry for the
  selected invoice without opening another invoice.
- [ ] Verify a payment amount and date open the exact payment in edit mode.
- [ ] Change one partial payment and confirm the transaction, ledger,
  receivable, linked time/disbursement payment state, Amount Paid, Balance
  Owing, and statement balance update exactly once.
- [ ] Verify that the edit cannot overpay the invoice or silently create a
  second payment.
- [ ] Verify two partial payments remain separately dated and editable.

**Acceptance:** all money figures reconcile before and after a payment edit,
and the fresh runtime log is clean.

---

## Phase 2 — Prove the daily legal-office workflows

### 2.1 Clients and matters

- [ ] Audit New Client, Client Directory, Client Profile 360, New Matter,
  Matter Directory, and Matter Profile 360 in Professional and Console.
- [ ] Start with the mandated New Matter Client dropdown/New Client handoff:
  load workbook clients, open the New Client command, save/cancel, return to
  New Matter, and confirm selection/billing/matter-number refreshes.
- [ ] Test Client, Parent Client, Matter Type, Status, and Billing Arrangement
  dropdowns in normal tabs and detached New Matter windows.
- [ ] Test merge-matter workflow on a safe copy or designated safe test client;
  verify time, disbursement, transaction, invoice/report references remain
  correct and no orphan/ghost matter is created.
- [ ] Add search exactness tests so a billing parent/metadata term does not
  incorrectly return unrelated client rows.

### 2.2 Docketing and deadlines

- [ ] Test Time Docket Entry: manual historic date, timer start/pause/reset,
  timer-zero behavior, fee calculation, bill percentage, Draft/Ready/Billed
  status, save/cancel, recent entries, and dirty-tab close guard.
- [ ] Test Fee Docket Entry: positive fee, zero hours/rate, matter link, WIP
  flow, invoice finalization, and exclusion from time-only daily totals.
- [ ] Test deadline/calendar refresh, edit, save, cancellation, and report
  drilldown in both styles.
- [ ] Test docket right-click delete only on safe draft entries; require a
  clear confirmation and verify WIP, totals, and recent-entry state refresh.

### 2.3 Billing, invoice, and collections workflow

- [ ] Test WIP filtering, sorting, selection, selection totals, empty-state
  explanation, right-click delete docket, and draft creation.
- [ ] Test Invoice Builder: client/matter/billing-client context, fee and time
  line editing, discount and reconciliation options, date entry/calendar,
  draft deletion, preview loading, finalization, PDF generation, and reopen.
- [ ] Test Invoice Directory: search, selection retention, matter description,
  payment column alignment, payments/adjustments, reversal route, and PDF
  access.
- [ ] Test Payment Entry: cash payment, EFT/reference, adjustment/write-off,
  partial payment, payment edit, validation errors, and return navigation.
- [ ] Test A/R Aging and Collections Queue: filter, drilldown, statement route,
  balance consistency, and closed/void/reversed invoice treatment.
- [ ] Test A/P settlement set-off only against a safe copy until the historic
  correction is approved; verify allocation balancing, reversal, and full
  ledger reconciliation.

### 2.4 Reports and documents

- [ ] Test the selectable Billing-Client Statement of Account: billing-client
  choice, invoice deselection, selected total, statement date, branded PDF,
  matching invoice list, and no mutation of receivables.
- [ ] Test Client Ledger, A/R Aging, productivity, financial dashboard, docket
  activity, and deadline reports against the canonical A/R engine and known
  fixture totals.
- [ ] Audit every print/PDF output for branding, page breaks, address block,
  matter/client wording, amount formatting, dates, footer, and professional
  whitespace.
- [ ] Ensure report drilldowns open the intended populated record, not an empty
  or generic form.

**Phase 2 acceptance:** each daily pathway has a documented happy path, one
meaningful validation/error path, and a user-confirmed real-app result in both
styles where the screen exists in both.

---

## Phase 3 — Make the interface consistently premium

### 3.1 Enforce the Professional design system

- [ ] Inventory shared controls, cards, tables, dialogs, tooltips, side/nav
  rows, and report panels.
- [ ] Move repeated colors, radii, borders, typography, spacing, motion, and
  status treatment into `VisualRules.qml` and `SemanticTheme.js` semantic
  tokens; remove one-off theme literals from high-traffic views.
- [ ] Ensure Professional remains restrained: compact radii, sparse shadows,
  calm transitions, no accidental Console glow/jelly/audio behavior.
- [ ] Preserve Console character intentionally; do not degrade it merely to
  make Professional easier.
- [ ] Define a small set of standard components for page headers, section cards,
  form fields, table headers/rows, empty states, error states, and primary/
  secondary/destructive actions.

### 3.2 Complete the Option 3 shell experience

- [ ] Verify the permanent shell is limited to top header, compact module rail,
  work-tab bar, breadcrumb/screen title, and full workspace.
- [ ] Verify module flyouts replace the permanent Pathway map rather than
  recreating a second sidebar.
- [ ] Test tab rules: generic workspaces single-instance; record workspaces
  entity-keyed; dirty indicators; save/discard/cancel close guard; close-last-
  tab return to Daily Operations.
- [ ] Test detached window, Return to Dock, taskbar icon, minimized/restored,
  and focus behavior on the primary monitor.
- [ ] Test global search/command paths for correct routing and no duplicate tabs.

### 3.3 Responsive, accessible, and efficient interaction

- [ ] Test all primary screens at the office monitor’s actual scaling plus 100%,
  125%, 150%, and a medium-width window. Record clipping, overlap, hidden
  actions, unwanted scrolling, and excessively sparse areas.
- [ ] Ensure important form workflows can be completed with keyboard: tab order,
  Enter/Space activation, Escape dismissal, visible focus, and no focus traps.
- [ ] Ensure color is not the sole indicator for Paid/Unpaid/Closed/Overdue,
  errors, selection, or destructive actions.
- [ ] Add appropriate tooltips/help text only where labels cannot convey the
  action; remove redundant or noisy help.
- [ ] Add predictable loading, empty, success, and failure states for every
  asynchronous primary workflow.

### 3.4 Visual quality review

- [ ] Assemble a screenshot board for the 10 highest-frequency screens in both
  styles and compare spacing, alignment, typography, contrast, and visual
  hierarchy side by side.
- [ ] Fix the most visible inconsistencies first: oversized blanks, clipped
  labels, misaligned financial columns, inconsistent card height, modal
  positioning, and mismatched button hierarchy.
- [ ] Review every client-facing PDF at normal zoom and printed-page scale.

**Phase 3 acceptance:** a new staff member can identify the active module,
screen, selected record, next primary action, and any unsaved/risky state within
seconds on each core screen.

---

## Phase 4 — Operational resilience, data safety, and performance

### 4.1 Make shared-data behavior explicit and safe

- [ ] Document the supported operating model: local save path, shared source
  path, when pull occurs, when push occurs, conflict behavior, and the one-
  writer limitation if applicable.
- [ ] On the second office computer, configure the intended Shared Data Source
  Folder and Local Save Folder, restart, and verify the expected clients,
  matters, dockets, invoices, and report totals appear.
- [ ] Test a safe two-computer sequence: write on computer A, synchronize,
  open on computer B, make a separate safe change, synchronize, and verify no
  silent loss or accidental overwrite occurs.
- [ ] Add a user-visible warning/lock when the system cannot safely sync or the
  source is unavailable; never fall back to a blank practice silently.

### 4.2 Backup, restore, and disaster recovery

- [ ] Define backup cadence, retention, storage locations, and owner for local
  workbooks, shared source workbooks, release packages, and configuration.
- [ ] Produce a one-command or clearly scripted preflight that verifies backup
  freshness, workbook openability, required tables, stable IDs, and hashes.
- [ ] Perform a restore rehearsal to an isolated location: restore a known
  backup, open CSPM against it, run the integrity/reconciliation report, and
  prove the active production workbook was untouched.
- [ ] Test the packaged recovery utility and document exactly when to use it.
- [ ] Ensure release backups and source Git history never expose private client
  data unless that data backup policy is explicitly authorized.

### 4.3 Startup, lifecycle, and performance

- [ ] Fix the repeated TimeDocket/calendar refresh loop visible in the current
  startup log unless it is demonstrably intentional and harmless.
- [ ] Profile cold launch, warm launch, backend boot, first input, flyout open,
  WIP load, Invoice Builder preview, Statement generation, and report load.
- [ ] Establish documented service-level targets on the primary office computer.
  Initial targets should be reviewed after baseline capture; recommended goals
  are first usable interaction within 10 seconds on a cold start, common screen
  transitions under 500 ms, and local report generation under 3 seconds unless
  a larger document is being intentionally rendered.
- [ ] Remove unnecessary startup prewarm work, duplicate timers, and repeated
  expensive workbook reads while preserving correct data freshness.
- [ ] Test startup splash exactly once, no blank/main-window flash, no focus
  theft, correct monitor placement, normal close, Close-to-Tray, tray-only
  relaunch, and duplicate-launch wake-up.

### 4.4 Logging and supportability

- [ ] Ensure `logs/cspm.log` starts fresh per normal launch or uses an explicit
  per-session log name; stale errors must not be mistaken for current failures.
- [ ] Add a session header with build hash, app version, data-path mode, style,
  and startup timestamps.
- [ ] Categorize QML, worker, data, sync, and recovery failures; present a
  concise user-safe message while retaining technical detail in the log.
- [ ] Add a simple diagnostics/export package that excludes workbook contents
  by default but includes version, hashes, settings redacted as needed, and log
  excerpts.

**Phase 4 acceptance:** a user can recover from a failed update, unavailable
shared source, or damaged local copy without guessing or risking live data.

---

## Phase 5 — Build the evidence pipeline

### 5.1 Automated tests

- [ ] Add backend tests for every financial invariant in Phase 1.
- [ ] Add QML/source guard tests for every repaired runtime contract: WIP
  selection token, invoice-finalized map, Builder initial state, payment edit,
  and statement selection.
- [ ] Add fixture workbooks that contain no production client data but model
  time, fee, disbursement, invoice, partial-payment, credit, reversal, and
  set-off cases.
- [ ] Make test setup explicitly use disposable/temporary workbooks; prove
  tests cannot point at the active workbook.
- [ ] Keep QML lint usage behind `scripts/qmllint.ps1` only; resolve errors and
  triage warnings rather than accepting a growing warning baseline.
- [ ] Add a packaged-file check for each release: executable, recovery utility,
  QML hashes/critical strings, splash assets, governed templates, and absence
  of live-workbook hashes in the bundle.

### 5.2 Manual audit

- [ ] Execute the Professional-first audit for all 72 canonical workspaces in
  `ModulePathways.js`, then repeat the Console-specific variations.
- [ ] For every workspace, verify entry route, data load, primary action,
  cancel/return path, dirty state, error state, resize behavior, and applicable
  report/export/drilldown behavior.
- [ ] Maintain screenshot evidence for each accepted primary workflow and each
  confirmed correction.
- [ ] Do not advance to the next observed defect until Cory confirms the
  current defect in the foreground application.
- [ ] Audit detached windows, modal layering, taskbar presence, and focus as a
  separate window-lifecycle pass.

### 5.3 Error-budget gate

- [ ] Run a clean session through the primary daily workflow: launch, docket,
  WIP, draft, finalization, payment, invoice directory, statement, report,
  close/relaunch.
- [ ] Review the fresh log before declaring success.
- [ ] Require zero first-party QML exceptions, Python tracebacks, unhandled
  worker errors, unknown signal handlers, or type-conversion errors.
- [ ] Treat environmental notices (for example, unavailable sound backends) as
  documented P3 items only if the related user feature degrades gracefully.

**Phase 5 acceptance:** every claim of correctness, stability, and polish has a
named automated test, foreground test, screenshot, log, or reconciliation
artifact supporting it.

---

## Phase 6 — Candidate, office pilot, and 10/10 certification

### 6.1 Create a release candidate safely

- [ ] Confirm no CSPM process is running before promotion.
- [ ] Build into a uniquely named candidate directory, never directly over the
  active `dist` package.
- [ ] Verify candidate executable, recovery utility, all required runtime
  assets, packaged QML, template governance, and live-workbook confidentiality
  check.
- [ ] Promote using the recoverable candidate-to-`dist` swap; preserve the
  immediately replaced package in `to_delete` or the approved release archive.
- [ ] Re-hash `dist/cspm.exe`, record the build hash/version/commit, and confirm
  the package exactly matches the verified candidate.
- [ ] Commit source, tests, and documentation only; never add local workbooks,
  generated release packages, sync state, or unreviewed diagnostics to Git.

### 6.2 Run an office pilot

- [ ] Use the candidate for normal low-risk office work for a defined pilot
  period, initially five working days or a mutually agreed workload threshold.
- [ ] Record every interruption, odd behavior, slow operation, confusing label,
  and unexpected log entry in the quality register.
- [ ] Reconcile the daily WIP, invoices, payments, A/R, and reports against
  expected data at least once during the pilot.
- [ ] Exercise a backup and recovery check during the pilot without endangering
  the active workbook.
- [ ] Fix every P0/P1 and every meaningful P2 discovered during the pilot, then
  repeat the affected manual tests.

### 6.3 10/10 sign-off checklist

- [ ] Financial engine reconciles all tested production and fixture scenarios.
- [ ] Known historic corrections are approved, backed up, applied, and verified.
- [ ] Core daily workflows have zero known P0/P1/P2 issues.
- [ ] The fresh primary-workflow runtime log is free of first-party errors.
- [ ] The 72-workspace audit, applicable Console pass, window-lifecycle pass,
  report/PDF pass, and primary monitor/scaling pass are complete.
- [ ] Professional styling is consistent, calm, responsive, and informative;
  Console remains intentionally functional and unchanged where appropriate.
- [ ] Shared-data behavior, backup, restore, and recovery have been rehearsed.
- [ ] The final candidate executable has been verified and is reproducible from
  the recorded commit.
- [ ] Cory confirms the product feels reliable and polished during real work,
  not just a scripted demo.

**Certification outcome:** only after every item above is checked and evidence
is attached may CSPM be described as a 10/10 overall system.

---

## First execution queue

The next work should follow this order. Each item requires its own static checks
and Cory’s real-app confirmation before moving on.

1. [ ] Register and fix the WIP selected-row semantic-theme runtime error.
2. [ ] Rebuild, run the WIP selection/draft path, and inspect the fresh log.
3. [ ] Define and repair the Invoice Builder `draftFinalized` payload contract.
4. [ ] Repair Builder initial-state/deep-link handling and remove the unmatched
   finalization error handler.
5. [ ] Rebuild, finalize a safe test invoice, and confirm PDF/Invoice Directory/
   A/R results with a clean log.
6. [ ] Complete canonical A/R engine design and fixtures before changing report
   consumers.
7. [ ] Migrate one consumer at a time: Client Ledger, A/R Aging, Statement of
   Account, Invoice Directory summary, then Payment Entry validation.
8. [ ] Prepare, review, and explicitly approve the historical correction plan
   for invoices `26-0066` and `26-0069`.
9. [ ] Perform the governed correction and reconciliation only after approval.
10. [ ] Execute the New Matter Client dropdown/New Client handoff manual audit
    in Professional, Console, and detached-window paths.
11. [ ] Validate recent Invoice Directory payment editing and Statement of
    Account selection in the promoted package.
12. [ ] Continue the full audit and quality phases above until the certification
    checklist is complete.

## Explicitly out of scope until CSPM is stable

- A broad database migration or production SQLite cutover.
- Replacing the Professional QML implementation with Flutter or React Native.
- Large unrelated feature additions that make financial/stability regressions
  harder to isolate.
- Cosmetic-only rewrites that bypass semantic tokens or duplicate business
  logic.

Those initiatives can resume after the 10/10 quality gate, or earlier only with
an explicit owner decision that they are necessary to resolve a blocker.
