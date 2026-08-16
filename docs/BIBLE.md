# CSPM Project Bible

Updated: 2026-06-03
Owner: Product + Engineering
Status: Active Source of Truth

## 1) Mission
CSPM is a premium legal practice command console that combines:
- Fast daily data entry
- Bulletproof financial controls
- Long-term Ontario trust-accounting and regulatory-reporting readiness
- Delightful, high-end user experience
- Reliable backup/restore so no meaningful work is lost

The system must stay portable from Excel-first desktop workflows to SQL-backed multi-platform deployment.

## 2) Product Principles
1. User-first flow: implement features in the order users perform work each day.
2. Data safety first: every phase must include crash-resilient persistence and recoverability.
3. UX quality is mandatory: style, motion, sound, readability, and print/PDF output quality are requirements, not polish.
4. Architecture portability: no dead-end design choices that block SQL/mobile migration.
5. Auditability: key workflows must be inspectable and reproducible through logs, manifests, and reports.
6. Context separation: client trust, sole-proprietor practice, a future
   professional corporation, and household/family activity must never be
   silently commingled in ledgers, tax reports, or permissions.
7. Regulatory truth: trust, GST/HST, and income-tax outputs must be
   source-linked, versioned, reviewable, and governed by current official rules
   rather than hard-coded assumptions.

## 3) User-Frequency Delivery Order
The implementation sequence must follow this operational path:
1. Matter selection and context setup (client, matter, task).
2. Time capture and docketing (start/pause/resume/submit).
3. WIP management (review, edit, hold, approve).
4. Billing and invoice generation.
5. A/R and payment application.
6. Trust-safe ledger flows and reconciliation.
7. Reporting and productivity intelligence.
8. Regulated trust, GST/HST, and income-tax preparation after the underlying
   financial records are proven.
9. Household/family financial management as a separate context.
10. Advanced automation and integrations.

## 4) Architecture Direction
1. Phase 1: Windows + Excel-first using strict tabular schemas.
2. Phase 1.5: in-memory row processing, never cell-by-cell loops for business logic.
3. Phase 2: SQL adapter replacement behind repository interfaces.
4. Phase 3: mobile-capable front-end with shared domain services and APIs.

The approved storage sequence is Excel stabilization -> local SQLite outside
OneDrive -> validated OneDrive snapshots -> possible Azure SQL behind a secure
API. The detailed regulated financial roadmap is
`docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md`.

Canonical machine-readable specs are stored in `docs/spec/`.
The Professional client migration boundary is defined in `docs/spec/professional_client_contracts.yaml`; use the selected local loopback HTTP JSON plus WebSocket event boundary while keeping Flutter versus React Native intentionally undecided. The explicit-start HTTP leg is proven against the real Excel-backed Client Directory/Profile workflow; WebSocket delivery and a visual external client remain pending.

## 5) Non-Negotiable Data Protection
Core database and working state must be protected continuously.

### Required backup chain
1. Scheduled project snapshots during runtime.
2. Manual snapshot trigger before high-risk operations.
3. Pre-restore safety snapshot before applying any restore.
4. Snapshot manifest with file hashes and restore order.
5. Active workbook integrity checks before release, before restore, after restore, and during support diagnostics.
6. Pre-live confidential-data security gate before production workbook use, Git cloud backup with real data, restore drills, or external support sharing.
7. User/admin backup-chain runbook at `docs/PRODUCTION_BACKUP_CHAIN.md` for production backup, restore, offsite retention, encryption, and drill cadence.
8. Snapshot scope includes:
   - `data/CSPM.xlsm` (core database)
   - `data/state/` and runtime draft state
   - `docs/BIBLE.md` and `docs/spec/`
   - `schema/`

### Recovery expectation
1. Crash recovery must preserve partial form data and timer state where technically possible.
2. Restore operations must be deterministic and documented.
3. Git cloud restore must verify selected commits contain the workbook and canonical database artifacts, preserve pre-restore safety copies, verify restored hashes/blobs, and run post-restore workbook integrity before reporting success.
4. Live confidential workbook data must not be committed, backed up, restored, exported, or shared outside the workstation until `docs/spec/pre_live_security_gate.yaml` is complete or explicitly excepted.
5. Production operators must follow `docs/PRODUCTION_BACKUP_CHAIN.md` for backup evidence, restore steps, offsite retention, and restore drill cadence.

## 6) Reporting Vision
Reports are a core product pillar, not an afterthought.

Minimum report families:
1. Productivity reports (time trends, realization, utilization, pipeline velocity).
2. A/R reports (aging buckets, expected collections, delinquency analysis).
3. WIP reports (unbilled inventory by matter/client/age/risk).
4. Billing quality reports (write-downs, leakage, margin drivers).
5. Trust and compliance reports (three-way reconciliation, exception logs).
6. Ontario trust-accounting records, monthly-close evidence, Form 9A support,
   and annual-report support packages after formal requirements validation.
7. Per-registrant GST/HST return workpapers, filing/payment task reminders, and
   separate personal/sole-proprietor, future-PC, and household tax workpapers.

UX requirements for every report:
1. Visually engaging on-screen layout (clear hierarchy, modern styling).
2. Export quality suitable for PDF sharing and client-facing decks.
3. Print-ready formatting with controlled pagination and readable typography.
4. Interactive summaries with drill-downs where appropriate.

## 7) UX Standard Across Every Stage
Every workflow stage must maintain:
1. Strong readability and contrast.
2. Motion that communicates state changes, not noise.
3. Purposeful sound feedback.
4. Low-friction confirmation and safety dialogs for risky actions.
5. Consistent visual language from data entry to reporting and print exports.

## 8) AI Handoff Protocol
Future AI contributors must:
1. Read this file first.
2. Read all files in `docs/spec/` before implementation planning.
3. Read `docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md` before planning a data,
   trust, tax, household, or compliance-related change.
4. Update both Bible and relevant spec files when behavior changes.
5. Keep runtime backup/restore behavior aligned with spec documents.
