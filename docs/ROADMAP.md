# CSPM Master Roadmap

Updated: 2026-08-16
Status: active; rebaselined around financial correctness, regulatory readiness,
and a controlled transition away from Excel.

## Governing Direction

CSPM is a premium legal-practice-management system. Its purpose is to make daily
legal work efficient while keeping money, records, reports, and recovery
trustworthy.

The roadmap has two horizons:

1. **Current execution:** achieve the 10/10 quality, financial-correctness,
   operational-resilience, and manual-audit gate while Excel remains the
   production data store.
2. **Post-10/10 expansion:** create the financial-context foundation; move to
   SQL-backed authoritative data; then deliver Ontario trust accounting,
   per-registrant GST/HST, personal/sole-proprietor and future-PC tax
   workpapers, household/family financial management, and later ecosystem
   integrations.

The detailed long-term compliance direction is canonical in
`docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md`. The current release gate is
canonical in `docs/CSPM_10_10_EXECUTION_ROADMAP.md`.

## Current Execution — 10/10 Gate

The current priority is not a storage migration or new regulated module. It is
to prove that CSPM's existing legal-office workflows are financially correct,
stable, safe, and polished in the real packaged application.

Immediate order:

1. Repair and prove financial posting, A/R, payment, reversal, invoice, WIP,
   and historic-correction behavior.
2. Complete the Professional-first manual audit under the one-observed-defect
   stop rule, beginning with New Matter Client dropdown / New Client handoff.
3. Complete backup, restore, shared-data, security, supportability, performance,
   release-candidate, and office-pilot evidence.
4. Certify only when no relevant P0/P1/P2 issue remains and real-app evidence
   supports the result.

Until that gate is passed, a broad SQLite/SQL migration, full trust accounting,
tax preparation, direct filing integration, and unrelated large modules are
deferred. A read-only requirements/discovery task may proceed only with express
owner authorization and must not obscure the current validation queue.

## Professional And Expert Client Direction

- **Console** remains the expressive Qt/QML experience.
- **Professional** remains the canonical restrained Qt/QML Option 3 interface:
  compact module rail, temporary flyouts, work tabs, breadcrumb, and full-width
  workspace.
- **Expert** is a separate future Flutter or React Native client tier that
  clones the mature Professional experience through framework-neutral local
  service contracts. It does not replace Professional QML without an explicit
  owner decision.

The interface and client-contract sources are
`docs/CSPM_Option_3_Interface_Rebuild_Brief.md`,
`implementation_plan.md`, and
`docs/spec/professional_client_contracts.yaml`.

## Post-10/10 Dependency Order

```text
10/10 current-product certification
    -> financial-context and compliance-rule specification
    -> repository/service separation and local SQLite migration preparation
    -> governed SQLite cutover, parity, backup, recovery, and OneDrive snapshot proof
    -> Ontario trust-accounting ledger, monthly close, Form 9A, and compliance packages
    -> GST/HST reporting, calendar tasks, and CRA line/box workpapers per registrant
    -> personal/sole-proprietor and future-PC income-tax workpapers
    -> household/family finance, budgets, and attributed tax-preparation workpapers
    -> Azure SQL/secure API, Expert-client expansion, web portal, and integrations
```

The ordering is deliberate: regulated reporting cannot safely be built on
ambiguous financial data, and SQL cutover cannot safely be built before the
existing workflows, IDs, audit rules, and recovery path are proven.

## Post-10/10 Workstreams

### 1. Financial Context And Compliance Rules

Establish the durable separation of Client Trust, Sole Proprietor Practice,
future Professional Corporation, and Household contexts. Every posting, report,
deadline, tax treatment, source document, allocation, approval, and export must
identify its context. Trust, operating, corporate, and household funds must
never share a ledger or be blended in a report.

Create versioned regulatory rules and requirements matrices before implementing
a trust, HST, or income-tax write path. Outputs begin as review-ready workpapers
and evidence packs; direct external filing is a later security/certification
decision.

### 2. SQL-Backed Authoritative Data

Move from Excel to local SQLite only through a governed candidate migration.
The live database remains outside OneDrive. OneDrive transfers completed,
validated snapshots and manifests only. Azure SQL behind a secure API is a later
multi-user/cloud option.

No dataset may remain editable in both Excel and SQL after its controlled
cutover. Stable IDs, financial/audit semantics, reconciliation, backup, restore,
and report parity are acceptance gates.

### 3. Ontario Trust Accounting

Deliver a detailed, compliance-oriented By-Law 9 trust subsystem: client/matter
liabilities, journals, transfer records, bank evidence, monthly
reconciliations/comparisons, exception handling, retention, Form 9A work
packages, and annual-report support. Maintain human authorization and
professional review; no generated form is automatically an executed transfer or
filed report.

### 4. GST/HST Reporting And Calendar

Deliver separate GST/HST registrant profiles for the sole-proprietor practice
and future PC; accurate tax/ITC/adjustment evidence; line/box-mapped CRA
workpapers; and a close/review/file/pay task calendar. The calendar calculates
deadlines from the configured reporting period and official rule set, with
configurable early reminders. It must not hard-code a generic 30-day rule.

### 5. Income-Tax Workpapers

Provide separate workflows for personal and sole-proprietor professional
activity, the future PC, and household/family members. Start with source-linked,
review-ready T1/T2125 and T2/GIFI/schedule-oriented workpapers, entity-specific
deadlines, instalments, and correction history. Do not claim tax-preparation
software certification or automate CRA submission without a separate decision.

### 6. Household And Family Financial Management

Build the dedicated household context: members, accounts, budgets, recurring
plans, goals, personal income/expenses, allocations, dashboards, and
privacy-aware reports. Personal transactions remain excluded from business
GST/HST and ITC calculations unless an explicit, reviewed allocation is
configured.

### 7. Ecosystem And Secure Connectivity

After the financial-data, security, and API boundaries are proven:

- complete the Expert client proof and expand it module by module;
- consider Azure SQL and a secure API with Microsoft identity;
- add a secure client portal for invoice delivery, payments, and document
  intake; and
- add Outlook/Graph deadline and matter-email workflows, public intake,
  pipeline, automation, and web-first deployment only after access control,
  privacy, audit, and data-residency requirements are defined.

## Delivery Rules

- Implement in the order users perform work: client/matter context, docketing,
  WIP, billing, A/R, trust/reconciliation, reporting, compliance, automation.
- No silent money changes, silent tax classifications, or silent data merges.
- Build one regulated workflow at a time: requirement matrix, DTO/data contract,
  read-only workpaper, synthetic fixtures, controlled write path, real-app
  confirmation, and release evidence.
- Keep every tax/trust rule, form/line mapping, and deadline source versioned by
  effective date; historical packages must remain reproducible.
- Keep live confidential client, trust, family, and tax data out of public
  repositories and unapproved remote services.
- Preserve Console and Professional business/data parity throughout every
  migration.

## Supporting References

- `docs/CSPM_10_10_EXECUTION_ROADMAP.md`
- `docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md`
- `docs/FUTURE_DATA_ARCHITECTURE.md`
- `docs/PRODUCTION_BACKUP_CHAIN.md`
- `docs/CSPM_Option_3_Interface_Rebuild_Brief.md`
- `docs/spec/professional_client_contracts.yaml`
