# Client Ledger (Dockets Layout) Implementation Plan

## Status and authority

This document records the owner-approved product, accounting, architecture,
privacy, and delivery contract for the CSPM Client Ledger (Dockets Layout)
feature. It is authoritative for this feature unless Cory expressly revises it.

Implementation has two milestones followed by a separate release gate. The
current assignment is Milestone 1 only. Existing Client Ledger and Matter Time
Ledger routes and behaviour must remain intact.

## Product outcome

Add a separate report entry named **Client Ledger (Dockets Layout)**. Its
displayed report title is **Client Ledger**. It reproduces the verified legacy
Dockets ledger information architecture using native CSPM data, branding,
themes, navigation, report conventions, and window conventions.

The result comprises:

- a native CSPM report workspace;
- a dedicated Zen View;
- a read-only calculation and reconciliation service;
- an immutable completed-report snapshot shared by the workspace and Zen;
- later Milestone 2 exports that consume the accepted Milestone 1 snapshot
  rather than creating another data pipeline.

This feature does not redesign the existing Client Ledger or Matter Time
Ledger.

## Report contract

The report operates on exactly one selected client. A fresh menu launch uses
**All History**. The workspace supports standard date presets plus manually
typed and calendar-selected From and To dates.

The detail table has exactly these eight columns in this order:

1. Date
2. Description
3. Inv #
4. Time
5. Rate
6. Disbs
7. Fees
8. Credits

Detail activity is chronological with deterministic same-date ordering and
stable row identities. Descriptions are complete and wrapped, with
content-driven row height. The presentation distinguishes billed work, WIP,
cash receipts, and non-cash adjustments without changing their accounting
meaning.

Two summaries immediately follow the final detail row:

1. **Unbilled Work in Progress** — Fees, Disbursements, Total before tax.
2. **Billing History & A/R** — cumulative authoritative billing and collection
   facts through the applicable report end date.

Empty detail may coexist with a non-empty cumulative Billing History & A/R
summary.

## Date semantics

Supported presets are:

- All History
- Today
- This Week
- Last Week
- This Month
- Last Month
- Last 30 Days
- Last 90 Days
- YTD
- Custom

Rules:

- All History clears both boundaries; no arbitrary starting year is used.
- Users may type dates or use calendar selectors.
- Editing either boundary changes the preset to Custom.
- Invalid syntax and From later than To are rejected clearly.
- A fresh menu launch defaults to All History.
- A deliberate contextual handoff from the existing Client Ledger may provide
  its selected client, From, To, and applicable preset.
- Contextual handoff never changes the fresh-menu default.
- An already open workspace preserves its current controls and completed
  snapshot.
- Generate or Refresh resolves relative preset boundaries and stores the
  resolved dates in the completed payload.
- Zen and future exports consume those stored dates and never independently
  recalculate a relative preset after midnight.
- Detail and WIP respond to the selected detail range.
- With a bounded range, detail is inclusive of From and To.
- Billing history ignores From and remains cumulative through To.
- With no To boundary, billing history includes all valid invoice and receipt
  dates and WIP evaluates all known valid invoice references.
- With a bounded To date, the billing label is
  `Through [end date] — all billing history`; without one it is
  `All billing history`.

## Financial and reconciliation rules

Python owns all money arithmetic and classification. Use `Decimal` and the
repository's documented currency rounding.

### Fees

- Use authoritative stored `AmountToYou` or the equivalent governed CSPM
  value where available.
- Preserve direct fees, approved overrides, hours, rate, allocation share, and
  authoritative posted values.
- Never substitute gross client fees, tax-inclusive values, current invoice
  totals, or a reconstruction that applies an allocation percentage twice.
- The deterministic fee fixture is `0.3 × $350 × 70% = $73.50`.
- A missing authoritative fee may use a documented Decimal fallback based on
  hours, rate, and share, with the share applied once and a safe internal
  reconciliation issue recorded.
- Missing, inapplicable, and valid numeric zero are distinct states.

### Receipts, credits, and adjustments

- Dated posted receipt allocations are authoritative where supported.
- Count every posted allocation exactly once.
- A bank receipt split across invoices must not be duplicated from another
  table or represented as each invoice's lifetime `AmountPaid`.
- Preserve the allocation date and appropriate client-facing reference.
- Distinguish cash receipts, write-offs, credit adjustments, invoice
  corrections, and other non-cash adjustments.
- Never display a non-cash adjustment as a cash receipt.
- Do not combine Transactions Master, Receivables, Ledger, and allocation
  records in a way that double-counts one economic event.
- Where an adjustment affects A/R, preserve transparent arithmetic in a
  conditional summary component or concise explanation.

### Historical WIP

The detail is activity history and must not reproduce synthetic charge or WIP
relief rows from the existing Client Ledger.

Determine WIP historically as of the applicable report end date. Cover blank
invoice references, literal `BILLED` markers, unresolved legacy references,
invoices before/on/after the end date, Draft or Ready, Billed, Merged,
Reconciled, reversals, custom-fee adjustments, and absent or invalid invoice
references.

Use dated events where available instead of projecting today's status
backward. When reliable reconstruction is impossible, record a safe internal
reconciliation issue and show an understandable warning only when needed.
Never fabricate a historical value or silently substitute today's receivable
state.

### Billing History & A/R

Calculate Billing History & A/R independently from visible detail rows using
authoritative posted invoice fees, posted invoice disbursements, invoice tax,
posted receipt allocations, valid corrections, credits, write-offs, and
applicable adjustments. Do not reconstruct posted invoices by summing docket
entries: discounts, custom fees, overrides, corrections, allocation
differences, and tax treatment remain authoritative posted facts.

### Client scope

Use stable client and billing-party identities. A shared billing party must not
cause work belonging to another client to enter the selected client's detail.
Synthetic coverage must include two clients sharing a biller, a separate
biller, a second client with disbursements, and split receipts. Safe real-data
comparison may use the documented A2B case, but no private identity or value may
enter committed fixtures, logs, reports, documentation, or responses.

## Read-only data boundary

Generating, displaying, refreshing, navigating to, opening Zen, or closing Zen
must not:

- invoke Microsoft Excel;
- execute VBA;
- import records;
- initialize a missing workbook;
- repair a workbook or schema;
- update report state inside a workbook;
- modify financial or client data;
- alter WIP, invoices, receipts, payments, dockets, ledger entries,
  receivables, or application production state.

The service performs an explicit non-writing existence and schema preflight.
Unavailable or incompatible source data returns an actionable report-load
error. Production paths never silently substitute mock data.

Automated tests use deterministic synthetic fixtures, never the production
workbook.

## Report-service architecture

Create a small service consistent with current CSPM service architecture. The
provisional location is
`src/python/services/client_ledger_report_service.py`; actual repository
conventions control if inspection identifies a better boundary.

Python owns:

- date parsing and preset resolution;
- client and billing-party scope;
- money arithmetic and rounding;
- financial, WIP, invoice, receipt, credit, and adjustment classification;
- deterministic ordering;
- reconciliation metadata;
- completed-payload construction.

QML must not duplicate these rules.

Read required source tables as one consistent, read-only snapshot where the
repository supports it safely. Potential sources are Clients, Client Profiles,
Parents, Time Entries, Disbursements, Invoice Log, Ledger, Receivables, and
authoritative allocation/adjustment records proven necessary by the actual
model.

The service returns a versioned immutable completed-report payload containing,
at minimum:

- payload version and report identity;
- selected client stable ID and safe display name;
- useful billing-party information;
- selected preset and resolved From/To dates;
- detail-period and billing-history-period labels;
- ordered entries with stable source IDs, row type/date, full description,
  display reference, decimal time, rate, disbursements, fees, credits, and
  presentation state;
- WIP summary and billing summary;
- row count and generation timestamp;
- source revision/snapshot identity;
- safe internal reconciliation issues;
- request token or equivalent correlation value.

Asynchronous generation uses stable request tokens. A late response cannot
replace the current selection. Editing controls does not mutate the displayed
completed snapshot; Generate or Refresh deliberately replaces it.

## Report identity

Subject to final collision verification, the approved identifiers are:

- Screen code: `D19`
- Route: `/reports/client-ledger-dockets`
- Report identity: `client_ledger_dockets`
- Tab key: `report:D19`

## Navigation and contextual entry

Wire the report beside existing ledger links under
**Finance & Ledger → Dashboards & Ledgers** in:

- Professional navigation;
- Console navigation;
- command search and global search aliases where applicable;
- route registration, tab opening/reuse, and state restoration.

Add an explicit entry from the existing Client Ledger toolbar. It may hand off
the current client and date context; it must not rely on hidden global state or
affect an unrelated fresh menu opening. Existing Client Ledger and Matter Time
Ledger routes remain unchanged.

## Native workspace

Build a native CSPM report panel following actual naming and location
conventions. Required controls are compact Client, Preset, From, To, calendar
access, Generate/Refresh, and Zen View controls. The report result, not a large
permanent control area, receives most of the workspace.

Required states:

- initial;
- loading;
- complete;
- empty detail;
- actionable failure;
- stale response safely ignored.

The table uses the exact eight columns, full wrapped descriptions,
content-driven row heights, decimal time, aligned money, stable row identity,
deterministic ordering, real invoice references, literal `BILLED` where the
contract requires it, blank reference for eligible WIP, restrained dashes for
inapplicable values, and distinct display for financially meaningful zero.

Billed rows use approved muted/italic treatment, receipts restrained green,
WIP a clear professional distinction, and adjustments an accurate restrained
treatment. Use CSPM semantic theme tokens, not arbitrary colour literals. The
layout must avoid clipping, overlap, unexplained truncation, or drifting
columns across supported window sizes and DPI settings.

Place both summaries directly below the final detail row. The header uses CSPM
branding, report title, selected client, detail period, cumulative billing
basis, and restrained snapshot context.

Milestone 1 must not wire export actions. If shared toolbar infrastructure
unavoidably shows them, leave them disabled and clearly unavailable until
Milestone 2.

## Zen View

Compose the report body for separate normal-workspace and Zen instances; never
reparent one live QML item between windows.

Zen:

- consumes the exact same completed payload;
- performs no independent financial query merely by opening;
- preserves rows, order, dates, totals, summaries, and selected client;
- opens on the initiating monitor;
- uses native window controls and sensible minimum dimensions;
- supports maximize/restore and repeated open/close/reopen;
- closes cleanly and returns to unchanged workspace state;
- receives a deliberately refreshed shared snapshot after Refresh;
- uses available width without clipping or overlap;
- remains a continuous on-screen ledger without paper pagination.

## Testing and reconciliation matrix

Deterministic synthetic tests must cover:

1. `$73.50` fee calculation.
2. Stored fee override, direct fee, zero fee, missing-fee fallback, and share
   applied once.
3. Disbursements.
4. Receipt allocation, partial payment, and one receipt split across invoices.
5. Receipt after end date.
6. Invoice before/on/after end date.
7. Blank invoice reference and literal `BILLED`.
8. Unresolved legacy invoice reference.
9. Draft/Ready, Billed, Merged, and Reconciled status.
10. Reversal, discount, custom fee, credit, write-off, and non-cash adjustment.
11. Shared biller without client-scope leakage and a second client with
    disbursements.
12. All History including pre-2025 data.
13. Every standard preset and a manual custom range.
14. Invalid date, reversed range, and return to All History.
15. Detail responds to From; billing history ignores From and respects To.
16. Empty detail with non-empty cumulative billing history.
17. Deterministic same-date ordering, Decimal precision, and missing versus
    zero.
18. Report load performs no workbook writes.
19. Missing workbook and invalid schema produce actionable read-only errors
    without initialization or repair.
20. Stale responses are ignored.
21. Zen performs no query and matches the main completed payload.
22. Fresh launch, preserved workspace state, and contextual handoff.
23. Existing Client Ledger and Matter Time Ledger remain unchanged.

Where governance permits, perform safe read-only reference comparison against
the documented A2B example from a complete common source snapshot. Distinguish
source-data, calculation, presentation, and historical-data differences. If a
safe real-data check is unavailable, do not fabricate parity; retain it as a
foreground acceptance item. Never commit private reconciliation output.

## Validation split

Sandbox-safe validation includes focused service, financial, ledger,
invoice/payment-allocation, route, navigation/search, date, stale-response,
read-only/no-write, QML component/import, privacy, secret, and regression
tests; Python compilation; governed `scripts/qmllint.ps1`; and complete diff
checks.

Real foreground validation, where safe, covers navigation, D19 tab reuse,
presets and calendars, validation errors, wrapped rows, all columns and states,
summaries, rapid selection changes, theme behaviour, supported sizes/DPI, Zen
monitor placement/maximize/restore/reopen, main/Zen equality, and absence of
workbook writes. WebEngine, external-window, multi-monitor, or unsafe data
boundaries that cannot be exercised must be reported accurately for manual
acceptance.

## Milestones and stop gates

### Milestone 1 — current assignment

- calculation and reconciliation service;
- versioned completed-report payload;
- deterministic fixtures and safe reconciliation;
- D19 navigation, search, routing, tab reuse, and contextual entry;
- date controls;
- native eight-column report and two summaries;
- dedicated Zen View using the same payload;
- automated validation;
- safe foreground acceptance preparation/validation;
- governing documentation;
- bounded feature-branch commits and remote preservation.

### Milestone 2 — explicitly excluded now

- Save PDF;
- CSV;
- Print;
- Copy;
- export preview;
- export dispatch and output-opening behaviour;
- confirmation that all exports use the accepted completed snapshot.

### Final release gate — explicitly excluded now

- complete regression and final foreground acceptance;
- final documentation completion;
- packaging or installer changes;
- production installation or deployment;
- installed-build smoke testing.

Do not begin SQL, SQLite, database migration, broad Client Ledger redesign,
Matter Time Ledger redesign, unrelated billing/accounting changes, packaging,
or deployment under this assignment.

## Privacy, Git, and delivery controls

- Never modify or test against production workbooks.
- Do not commit workbooks, private logs, client documents/data, generated
  reports, application state, credentials, build trees, or unpublished legal
  work product.
- Use synthetic identities and values in committed tests/fixtures.
- Preserve unrelated worktrees, local changes, and stashes.
- Before commit, review the full diff and staged diff, run required validation,
  privacy/secret scans, and confirm application worktrees outside this feature
  worktree were not changed.
- Push without force to `feature/client-ledger-dockets-layout` and verify the
  exact remote commit.
- Do not merge into main automatically.
