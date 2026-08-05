# Changelog

## 2026-06-03 - Active Workbook Integrity Wiring
### Added
1. Active workbook integrity now runs inside `scripts/run_quality_gates.ps1` as a pre-release gate.
2. Git cloud restore now records pre-restore and post-restore workbook integrity JSON reports.
3. Support diagnostics can now be collected with `scripts/run_support_diagnostics.ps1`.

### Changed
1. Backup/restore policy now maps workbook integrity checks to release, restore, post-restore, and support diagnostic command paths.
2. Durable implementation notes now track the remaining restore-drill validation separately from completed command wiring.

## 2026-02-22 - Sprint 0 Platform Pivot
### Added
1. Project snapshot service with manifest hashing and restore support.
2. Scheduled auto backup support in `AppController`.
3. Manual snapshot/list/restore slots on `AppController`.
4. New machine-readable spec pack in `docs/spec/`.
5. Canonical workbook schema draft in `schema/workbook_schema.yml`.
6. Updated Bible and Roadmap aligned to user-frequency implementation order.

### Changed
1. `WorkspaceDumpService` now writes to `dumps/workspace/` via `AppPaths`.
2. `AppPaths` now includes snapshot/spec helper paths and a top-level dumps path.
3. Close-session snapshot now writes to project-root managed path consistently.
