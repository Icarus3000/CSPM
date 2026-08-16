# CSPM Regulatory, Tax, Trust, And Financial-Context Roadmap

Updated: 2026-08-16  
Status: approved long-term product direction; implementation is deferred until
the current Excel-backed quality and financial-trust gates are complete.

## Purpose

This roadmap brings together CSPM's approved long-term financial direction:

1. replace Excel as the authoritative operational database with SQL-backed
   storage, beginning with local SQLite;
2. provide detailed Ontario legal-practice trust accounting and the records,
   reconciliation packages, and working forms needed to support compliance;
3. provide detailed GST/HST preparation, deadline tracking, and return
   workpapers; and
4. provide separated personal, sole-proprietor professional-practice,
   professional-corporation, and household/family financial and tax workflows.

It is a product and engineering roadmap, not legal, tax, accounting, or filing
advice. Current Law Society of Ontario (LSO), CRA, and applicable accounting
requirements must be checked and versioned before a compliance output is made
available for real use. CSPM may prepare reconciled workpapers and controlled
form packages; it must never claim that a generated output is complete, filed,
or compliant without the required human review and authorization.

This document complements, rather than displaces:

- `docs/CSPM_10_10_EXECUTION_ROADMAP.md` for the current stability and
  financial-correctness gate;
- `docs/FUTURE_DATA_ARCHITECTURE.md` for the approved storage-migration
  sequence;
- `docs/CSPM_Option_3_Interface_Rebuild_Brief.md` for the Professional QML
  interface; and
- `implementation_plan.md` for the two-style UI and future Expert-client
  direction.

## Current Execution Boundary

Nothing in this document authorizes a broad database migration, a live trust
module, tax filing, or a new financial data source during the current
Excel-backed stabilization milestone.

Before any workstream below begins, CSPM must meet the relevant 10/10 gates:

- financial posting, A/R, reversal, and payment behavior are reconciled and
  foreground-validated;
- the active-workbook integrity, backup, restore, shared-data, security, and
  audit requirements have evidence;
- the Professional-first manual audit has progressed under its one-defect
  stop rule; and
- the owner expressly authorizes the next workstream.

The next current execution item remains the manual **New Matter Client
dropdown / New Client handoff** audit. Long-term compliance work must not be
used to bypass that current quality discipline.

## Non-Negotiable Financial Context Model

Every financial record, report, deadline, and export must have an explicit,
immutable-at-posting financial context. Contexts cannot be inferred solely from
a category name or screen.

```text
FinancialContext
├── ClientTrust
│   └── client/matter trust liabilities and trust-bank evidence only
├── SoleProprietorPractice
│   └── Cory's unincorporated professional-practice income and expenses
├── ProfessionalCorporation
│   └── future PC books, tax year, accounts, and tax registrations
└── Household
    └── personal/family-member income, expenses, budgets, and goals
```

Required dimensions include:

- legal/reporting entity and display name;
- owner, household member, or responsible licensee where applicable;
- tax registrant and registration number only where applicable;
- fiscal year, reporting period, currency, and jurisdiction;
- account, category, tax treatment, source evidence, and allocation method;
- client/matter linkage only where it is real and permitted; and
- immutable audit identity, posted timestamp, actor, and reversal linkage.

Rules:

- Trust funds, general operating funds, future PC funds, and household funds
  must use separate ledgers, accounts, balances, reports, and access controls.
- Household/personal transactions are not a `BusinessUnit`, receive no
  business ITC by default, and are excluded from business GST/HST reporting.
- A mixed-use transaction requires an explicit, reviewable allocation; the
  source amount is never silently split or overwritten.
- A future PC is a separate legal and tax entity. CSPM must not relabel or
  migrate historical sole-proprietor activity into the PC without an approved,
  auditable conversion/cutover workflow.
- Reports must always state their context, entity/registrant, period, method,
  source version, and any unresolved exception.

## Workstream A — SQL-Backed Authoritative Data

### Target sequence

1. Finish and prove current Excel-backed workflows and financial controls.
2. Extract repository/service contracts and canonical domain DTOs from
   workbook-specific controller paths.
3. Define the SQL schema from proven workflows and the financial-context
   model; do not merely mirror inconsistent workbook columns.
4. Migrate first to a local SQLite database outside OneDrive.
5. Run governed migration candidates: backup, deterministic import,
   stable-ID mapping, row/count/value reconciliation, report parity, integrity
   check, and explicit promotion.
6. After SQLite is stable, use OneDrive only for completed validated snapshots,
   manifests, checkout state, and recovery history; never open the live SQLite
   database from a synchronized folder.
7. Consider Azure SQL behind a secure API and Microsoft identity only after the
   local database, snapshot, security, and multi-user requirements are proven.

### SQL migration acceptance requirements

- No parallel editable Excel and SQL sources of truth after a dataset is
  promoted.
- Every migrated record retains a stable identity and a traceable source
  identity; corrections and reversals remain auditable.
- Trial balances, trust balances, A/R, WIP, HST, and report totals reconcile
  before and after promotion.
- Failed candidates leave the active production data unchanged and recoverable.
- Data-location, local commit, backup, publication, synchronization, conflict,
  and restore status are visible to the user.

Full storage constraints remain in `docs/FUTURE_DATA_ARCHITECTURE.md`.

## Workstream B — Ontario Trust Accounting

### Product objective

Build a compliance-oriented trust subsystem for an Ontario law practice. It
must produce complete, reviewable records and exception evidence from one
authoritative trust ledger; it must not be a cosmetic dashboard over operating
accounts.

### Required capabilities

- Separate trust account directory with institution, account designation,
  account status, source-document requirements, and effective dates.
- Client/matter trust liability ledger: every receipt, disbursement, transfer,
  adjustment, reversal, balance, purpose, payor/payee, method, document
  identifier, and supporting evidence.
- Trust receipts/disbursements journal, trust-to-trust transfer journal, client
  trust ledger, general receipts/disbursements journals, fees/billings record,
  and property-held-in-trust record as applicable.
- Bank-statement, cleared-cheque, deposit-slip, electronic-transfer, and
  invoice/billing evidence linkage with immutable hashes and retention policy.
- Period-close workflow with bank reconciliation, detailed client-liability
  listing, monthly comparison, approved difference reasons, sign-off, lock, and
  reopening only through an audited correction path.
- Hard controls: no overdraft of a client trust liability, no unapproved
  transfer, no destructive edit of posted trust events, no operating/household/
  PC transaction in the trust ledger, and no unresolved reconciliation silently
  carried into a closed period.
- Trust-to-general withdrawal workflow linked to a rendered bill, authorization,
  recipient, and appropriate supporting evidence.
- Form package generation, beginning with **LSO Form 9A — Electronic Trust
  Transfer Requisition**, with the required signatory/authorization fields,
  preserved generated document, confirmation evidence, and a clear status of
  draft/reviewed/authorized/executed. Do not represent a generated form as an
  executed bank transfer.
- Read-only monthly, matter, client, bank, exception, source-document, and
  annual-report support packages; export only after an explicit review step.

### Regulatory verification gate

Before implementation, create a versioned LSO requirements matrix that maps
each By-Law 9 requirement, current form, retention period, signature rule,
exception, and report to a CSPM data field, control, test, and output. Verify
the matrix with current official LSO materials and appropriate professional
advice. Mortgages or charges held in trust, Teranet withdrawals, and any other
specialized practice areas remain opt-in extensions rather than assumed scope.

Current reference points include the LSO's
[By-Law 9 record-keeping summary](https://lso.ca/lawyers/practice-supports-and-resources/topics/managing-money/bookkeeping/summary-of-by-law-9-record-keeping-requirements),
[Financial Management Guideline](https://lso.ca/lawyers/practice-supports-and-resources/practice-management-guidelines/financial-management),
and [Form 9A](https://lso.ca/about-lso/legislation-rules/by-laws/by-law-9/form-9a-electronic-trust-transfer-requisition).
These references must be rechecked at implementation and before every release
that changes compliance logic.

### Trust acceptance requirements

- A posted trust event is idempotent, balanced, source-linked, and reversible
  only through a traceable correcting event.
- Client liability, trust-bank balance, and reconciliation/comparison totals
  agree or an approved exception is prominent and blocks period close.
- A generated Form 9A and every compliance package can be traced back to exact
  source events and evidence without editing a report manually.
- The system retains the records and audit evidence for the currently required
  period; retention configuration is versioned rather than hard-coded.
- Compliance tests use synthetic fixtures, never unprotected production client
  data.

## Workstream C — GST/HST Compliance Workspace

### Product objective

Give each GST/HST registrant a period-close and return-preparation workflow
that produces a line-by-line, source-reconciled working paper matching the
applicable CRA return path. The first release prepares and reviews data; it
does not automate submission to CRA.

### Required model and controls

- Maintain a separate registrant profile for the sole-proprietor practice and
  future PC, including registration number, fiscal period, reporting frequency,
  accounting method, effective dates, and filing profile.
- Capture taxable, zero-rated, exempt, out-of-scope, self-assessed, and
  adjustment treatment at transaction level, with ITC eligibility and explicit
  allocation evidence.
- Keep household/personal activity outside business GST/HST and ITC reports.
- Use Decimal/cents-safe tax calculations, explicit tax rates/effective dates,
  documented rounding, and adjustment/reversal links.
- Produce a versioned CRA return working paper with a line/box map, amount,
  calculation, source transaction set, exception list, and supporting-document
  drilldown. The mapping must identify the applicable return method and form
  version; it cannot assume that every registrant uses the same lines.
- Provide a close checklist: reconcile revenue, tax collected, ITCs,
  adjustments, receivables/payables, and general ledger; resolve exceptions;
  approve; then lock the prepared version while retaining correction history.

### Compliance calendar and To Do behavior

- The calendar must calculate obligations from the registrant's real reporting
  period and official rule configuration, not from a fixed `30 days` constant.
- For monthly and quarterly GST/HST filers, the current CRA reference rule is
  filing and payment one month after the period ends. A calendar-quarter period
  ending March 31 therefore targets April 30, subject to CRA recognized
  weekend/holiday treatment.
- Create recurring **Prepare**, **Reconcile**, **Reviewer sign-off**, **File**,
  and **Pay/remit** tasks. Default early-warning milestones should be
  configurable (for example 90, 60, 30, 14, and 7 days) and visibly separate
  an internal target from the legal deadline.
- Upcoming tasks must display the registrant, period, return/version, filing
  deadline, payment deadline, owner, readiness state, and any blocking
  exception.

Current official reference:
[CRA GST/HST reporting requirements and deadlines](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/file-gst-hst-return/reporting-requirements-deadlines.html)
and [CRA line-by-line return instructions](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/calculate-prepare-report/instructions-preparing-return.html).

## Workstream D — Income-Tax Preparation Workspaces

### Scope separation

1. **Personal and sole-proprietor professional practice:** personal tax
   planning plus separate professional/business income and expense workpapers.
   The initial target is a T1/T2125-oriented source package, not an assertion
   that CSPM is certified tax-preparation software.
2. **Professional corporation:** a separate corporate tax-year, books, tax
   accounts, and T2/GIFI/schedule-oriented working-paper package. It is not
   active until the PC exists and an explicit cutover has been approved.
3. **Household and family members:** separately attributed personal income,
   expenses, budgets, goals, and tax-preparation workpapers with privacy-aware
   access. They must never be merged into the lawyer's business or PC books.

### Required capabilities

- Tax-year calendar and entity-specific filing profile.
- Source-evidence register for income, expense, tax slips, invoices, receipts,
  capital assets, allocations, and adjustments.
- Versioned line/box mapping from categorization to a declared CRA form,
  schedule, and tax year; every displayed value explains its calculation and
  source records.
- Separate business, professional, employment, property, investment, and
  household/family reporting contexts where required. No automatic deduction or
  classification without an explicit configured rule and review state.
- Workpapers for business/professional income and expenses, capital-cost and
  mixed-use allocations, GST/HST interaction, owner draws/distributions, and
  PC-to-person transactions as applicable.
- Tax-period close, reviewer approval, exceptions, signed export package, and
  historical reproducibility. A correction creates a new version; it does not
  silently alter a previously reviewed filing package.

### Deadline behavior

- A self-employed individual may generally file a personal return by June 15,
  but a balance owing is generally due April 30. CSPM must model these as
  separate official deadlines.
- For the sole-proprietor personal workflow, CSPM's default internal completion
  target should be **April 30**, with configurable earlier preparation and
  reviewer milestones. It is an internal target, not a replacement for the
  legal filing rule.
- Future PC deadlines must be calculated from its actual fiscal year and
  eligibility settings. Current CRA reference material states that a corporate
  return is generally due within six months of fiscal year-end, while the
  balance-due day may be earlier.
- Individual and corporation instalments, where applicable, are separate
  recurring tasks with their own rule source and due date.

Current official reference:
[CRA personal due dates](https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/important-dates-individuals.html),
[CRA Form T2125](https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2125.html),
[CRA corporation-return guidance](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/corporations/corporation-income-tax-return.html),
and [CRA corporate balance-due rules](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/corporations/corporation-payments/paying-your-balance-corporation-tax/balance-day.html).

## Workstream E — Household And Family Financial Management

The existing household-budgeting direction remains required and expands to
support the tax-preparation context above:

- `Household`, `HouseholdMember`, `HouseholdAccount`, `Budget`,
  `BudgetPeriod`, `BudgetCategory`, `BudgetLine`, `RecurringPlan`, and
  `FinancialGoal`;
- attributed household income and expenses, actual-versus-budget reporting,
  cash-flow forecasting, and personal/family dashboards;
- explicit business draw/distribution and mixed-use allocation flows; and
- privacy-aware user/role design before anyone other than the owner can view,
  edit, export, or restore another family member's financial data.

This workstream must use the same evidence, period-close, correction, export,
and data-protection standards as the professional-practice workflows, while
remaining absolutely separate from trust and business GST/HST calculations.

## Dependency Order After the 10/10 Gate

```text
Current 10/10 quality, financial-trust, security, and manual-audit gate
    -> financial-context and compliance-rule specification
    -> service/repository separation and SQL migration preparation
    -> governed local SQLite cutover and parity/recovery proof
    -> core Ontario trust-accounting ledger and monthly-close system
    -> per-registrant GST/HST preparation and calendar workflow
    -> personal/sole-proprietor and PC income-tax workpapers
    -> household/family budgeting and tax-preparation workflows
    -> optional secure API, Azure SQL, portal, and broader ecosystem work
```

The owner may authorize a narrow discovery/specification task earlier when it
does not alter production data or obscure current 10/10 validation. Any actual
write path, database cutover, compliance output, or external filing integration
requires its corresponding gates and explicit authorization.

## Delivery Discipline

- Build one regulated workflow at a time: requirements matrix, data contract,
  read-only report/workpaper, validation fixtures, controlled write path,
  foreground review, then release evidence.
- Keep tax/trust rule sets versioned by jurisdiction, form/version, effective
  date, and source. A rules change cannot silently revise a historical filing
  package.
- Prefer review-ready export and audit evidence before direct portal/API filing
  integrations. Direct filing is a separate authorization, security, and
  certification decision.
- Use synthetic compliance fixtures and redacted diagnostics. Do not expose
  live client, trust, household, or tax data through public repositories,
  unapproved remote services, or external prototypes.
- Retain human approval and professional review gates for legal, trust, and tax
  outputs. Automation must explain, not hide, source data, assumptions, and
  exceptions.

