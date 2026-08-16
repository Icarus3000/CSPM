# CSPM Future Data Architecture

<!-- CSPM_FUTURE_DATA_ARCHITECTURE_V1 -->

## Status and approved sequence

This is an approved future architecture requirement only. Do not implement it without later express authorization.

1. Complete and prove existing Excel-backed financial and operational workflows.
2. Migrate authoritative structured data from Excel and CSV to local SQLite.
3. After SQLite is stable, implement controlled OneDrive transfer and backup using validated closed snapshots.
4. Later consider Azure SQL behind a secure API and Microsoft sign-in.

## Interim usage model

- One CSPM user.
- Only one authorized computer modifies the database at a time.
- Multiple authorized computers may run CSPM at different times.
- Each computer keeps its active SQLite database outside OneDrive.
- OneDrive transfers and retains completed snapshots, manifests, locks, and recovery history.

## Non-negotiable safety rule

The live SQLite database must never be opened from a OneDrive-synchronized folder. WAL, SHM, and rollback-journal files must not be synchronized as independent active state. A raw copy of an open database is not a valid backup.

## Target workflow

```text
Computer A local SQLite database
    -> transactionally consistent SQLite backup
    -> integrity check, manifest, checksum, and completion state
    -> publish completed snapshot to OneDrive
    -> OneDrive synchronizes
    -> Computer B verifies and restores snapshot locally
    -> Computer B uses only its local SQLite database
```

On startup CSPM compares local identity and revision, the latest completed cloud snapshot and manifest, previous session information, checkout state, and schema/application compatibility. It must refuse automatic replacement if it detects divergence, a conflict copy, missing or invalid metadata, checksum or integrity failure, another active computer, revision rollback, incomplete publication, an online-only file, or incompatible versions.

On normal close CSPM commits transactions, coordinates connections, creates a consistent SQLite backup, validates it, runs an integrity check, creates a manifest and checksum, publishes with an incomplete-versus-complete protocol, retains historical snapshots, and clears checkout state only after successful local publication. The UI must distinguish local commit, local backup, publication into the local OneDrive folder, and confirmed OneDrive synchronization.

## Snapshot identity and manifest

Each snapshot should record:

- unique database ID;
- schema version;
- application version;
- snapshot ID;
- parent snapshot ID;
- monotonically increasing data revision;
- UTC creation time;
- source computer ID;
- source application session ID;
- integrity result;
- file size;
- cryptographic checksum; and
- publication status.

Filesystem timestamps alone must never determine authority or freshness.

## Conflict prevention

Required protections include persistent computer identity, unique session identity, a OneDrive-visible checkout marker, revision verification, controlled stale-lock override with an audit reason, conflicting-history detection, no last-file-wins replacement, no silent financial-data merge, and an explicit recovery path.

This is not a multi-user merge architecture. It prevents simultaneous or divergent editing.

## OneDrive behavior

The designated folder should normally be kept locally available. The design must account for delayed or offline synchronization, pending uploads after close, files and manifests arriving separately, conflict copies, shutdown before upload completion, and online-only placeholders. A snapshot is not available merely because its filename appears.

## User interface

The future status surface should show:

- active database location;
- database health;
- local revision;
- latest OneDrive snapshot revision;
- cloud status: current, pending, offline, failed, or conflict;
- last successful backup and integrity check;
- active or last-used computer; and
- whether it is safe to change computers.

## Failure, retention, and recovery

OneDrive failure must never corrupt, replace, or roll back the healthy local database. CSPM remains locally usable but clearly warns that cloud state is stale and changing computers is unsafe.

OneDrive should retain a latest completed snapshot and manifest, timestamped historical snapshots and manifests, and a defined retention policy. Recovery must verify compatibility, integrity, and checksums, make a safety copy before restore, and record restoration as an auditable event. OneDrive version history is supplementary, not the only backup.

## Financial and audit requirements

The future database must support durable transactions, stable IDs, audit events, correction and reversal workflows, reconciliation, governed migrations, tested backup and restore, incomplete-migration detection, deterministic import/export, and rollback protection.

It must also carry an explicit financial context on every financial record and
report. The initial required contexts are Client Trust, Sole Proprietor
Practice, future Professional Corporation, and Household. They are separate
ledgers and reporting scopes, not category labels. The SQL schema and migration
must prevent their silent commingling, retain source/evidence identity, and
preserve tax registrant, period, allocation, approval, and correction history.
Trust, GST/HST, and income-tax workpapers must be generated from versioned,
source-linked records rather than a second set of spreadsheet calculations.

## Excel and CSV after migration

Excel and CSV remain supported for legacy import, controlled export, accountant schedules, reconciliation, reports, archives, and interoperability. After a dataset moves to SQLite, Excel and CSV must not remain parallel editable sources of truth.

## Storage abstraction and Azure phase

```text
CSPM UI and business logic
    -> repository or data-service interface
        -> current Excel repository
        -> future local SQLite repository
        -> future secure API repository
```

The UI and business logic must not depend directly on SQLite paths or OneDrive behavior. A later target may use Microsoft sign-in, a secure CSPM API, and Azure SQL, while OneDrive or SharePoint continues to hold documents, exports, reports, and backup packages.

The detailed product sequencing for SQL migration, Ontario trust accounting,
GST/HST, income-tax workpapers, and household/family financial management is
`docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md`.

## Current blockers to monitor

1. ExcelRepo combines storage, schema, normalization, reporting, and workflow responsibilities.
2. Controllers and services contain workbook-specific dependencies.
3. Financial facts are projected across overlapping tables.
4. Some workflows assume immediate local workbook access.
5. Backup concepts are workbook-focused and lack database lineage semantics.
6. Database, schema, application, computer, session, and snapshot identity are not yet coordinated.
7. Current status surfaces do not distinguish commit, backup, publication, and cloud confirmation.

These blockers guide incremental design but do not authorize a broad refactor before the trust milestone.

## Questions before implementation

- local database location and protection;
- database and snapshot encryption;
- OneDrive folder discovery;
- truthful synchronization-confirmation method;
- retention policy;
- checkout and stale-lock override policy;
- computer authorization and retirement;
- revision and parent-snapshot lineage;
- schema compatibility and rollback policy;
- recovery UX for divergence and conflict copies;
- filesystem publication versus Microsoft Graph;
- SQLite WAL and backup coordination;
- dataset migration order and reconciliation gates; and
- criteria for later migration to Azure SQL.

## Current-phase instruction

Complete and stabilize Excel-backed workflows, derive the future SQL schema from proven workflows, separate business logic from workbook storage where practical, and avoid new coupling that obstructs SQLite or a future API. Do not implement SQLite migration or OneDrive synchronization without express authorization.
