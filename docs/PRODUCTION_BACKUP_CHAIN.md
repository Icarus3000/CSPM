# CSPM Production Backup Chain

Updated: 2026-06-03

This is the operator runbook for protecting CSPM production data. The machine-readable policy lives in `docs/spec/backup_restore_policy.yaml`; this document explains the practical chain a user or administrator should follow.

## Scope

The production data set includes:

- `data/CSPM.xlsm`, the active workbook database.
- Canonical database artifacts under `data/` and `src/python/data/`.
- Runtime state under `data/state/`, excluding volatile runtime session recovery files from canonical Git backup.
- Specs, schema, imports, and settings included by project snapshots.

Live workbook data can contain confidential legal and financial information. Before real production data is committed to Git, restored from Git, sent to support, or copied offsite, the pre-live security gate in `docs/spec/pre_live_security_gate.yaml` must be complete or explicitly excepted.

## Backup Layers

### 1. Runtime Project Snapshots

Runtime snapshots are the first protection layer for normal app usage and local recovery.

- Default cadence: every 15 minutes.
- Environment override: `CSPM_AUTOBACKUP_MINUTES`.
- `0` disables scheduled snapshots.
- Values below 5 minutes are clamped to 5 minutes.
- Snapshot location: `backups/snapshots/<timestamp>/`.
- Manifest: `manifest.json` with file list, restore order, SHA-256 hashes, and summary.

Snapshot scope includes the active workbook, `data/state/`, `docs/BIBLE.md`, `docs/spec/`, `schema/`, import folders when present, `docs/ROADMAP.md`, `docs/CHANGELOG.md`, `user_settings.json`, and `session_draft_snapshot.json` when present.

Manual snapshots should be triggered before risky work, release validation, migrations, and restore attempts through:

```text
createProjectSnapshot(reason)
```

Runtime snapshots are not a substitute for offsite backups. They protect local working state and provide a fast rollback point.

### 2. Active Workbook Integrity Gate

Run the workbook integrity check before release, before restore, after restore, and before support sharing:

```powershell
.\scripts\check_workbook_integrity.ps1
```

The release gate command also runs workbook integrity:

```powershell
.\scripts\run_quality_gates.ps1
```

The checker validates workbook openability, canonical sheets and Excel table objects, required columns, primary-key uniqueness, sequence collisions, required fields, date sanity, core references, and basic financial reconciliation.

Production policy:

- Errors block live release and post-restore acceptance unless there is a signed exception.
- Warnings must be reviewed and recorded.
- Integrity reports generated around restore are kept under `logs/workbook_integrity/`.

### 3. Git Cloud Active Workbook Backup

Git cloud backup is the canonical cloud/offsite source for the active workbook and database artifacts.

Use only an approved private remote. Do not push live workbook data to a public, personal, or unreviewed remote.

Typical command:

```powershell
.\git_backup_to_cloud.ps1 -Remote origin -Message "Production backup YYYY-MM-DD"
```

The script:

- Force-adds `data/CSPM.xlsm` even though workbook files are generally ignored.
- Discovers and force-adds every file under `data/` and `src/python/data/` while temporary full-database Git backup mode is active.
- Force-adds `git_backup_to_cloud.ps1` and `git_restore_from_cloud.ps1` so the backup contains the scripts needed to restore it.
- Warns that workbook commits may contain confidential legal and financial data.
- Verifies the active workbook, full database artifact set, and backup/restore scripts are present in `HEAD`.
- Pushes the current branch, all branches, and tags.

Record the Git commit SHA, active workbook SHA-256, remote name, operator, date/time, and integrity-check result in the backup evidence log.

### 4. Pre-Restore Safety Copies

Before destructive Git restore operations, CSPM must preserve the current local data state.

`git_restore_from_cloud.ps1` creates safety copies outside the repo under:

```text
..\__CSPM_restore_safety\
```

Expected safety-copy families:

- `restore_*` for the active workbook.
- `database_restore_*` for the full current database artifact set and backup/restore scripts.

Do not delete these safety copies until the restored workbook has passed integrity checks, the app has opened successfully, and the user has confirmed the restored data is the intended data set.

### 5. Git Cloud Restore

Git restore is a controlled recovery operation and may reset/clean the working tree. Close CSPM and Excel before running it.

Typical command:

```powershell
.\git_restore_from_cloud.ps1 -Remote origin -DefaultBranch main -MaxCommits 25
```

The script:

- Fetches remote branches and tags.
- Shows recent restore candidate commits.
- Refuses commits that do not contain `data/CSPM.xlsm`.
- Refuses commits that do not contain the selected commit's full database artifact set.
- Refuses commits that do not contain `git_backup_to_cloud.ps1` and `git_restore_from_cloud.ps1`.
- Creates pre-restore safety copies.
- Runs a pre-restore workbook integrity report.
- Resets/cleans the repo to the selected commit.
- Synchronizes local branches with the remote.
- Verifies restored workbook, full database artifact, and backup/restore script Git blobs and SHA-256 hashes.
- Runs a post-restore workbook integrity report.

Post-restore acceptance requires:

- Restored artifact hash/blob verification passed.
- Post-restore workbook integrity has no blocking errors.
- CSPM launches and reaches the expected data set.
- The operator records the selected commit, safety-copy paths, integrity report paths, and outcome.

### 6. Support Diagnostics

Use support diagnostics when packaging local state for troubleshooting:

```powershell
.\scripts\run_support_diagnostics.ps1
```

Diagnostics are written under:

```text
logs\support_diagnostics\diagnostics_<timestamp>\
```

Review and redact diagnostic bundles before external sharing. Support data can include workbook health, Git context, paths, and operational clues that may reveal client or matter information.

## Offsite And Retention Expectations

Production backups must have at least two independent layers:

- Local runtime snapshots for fast local recovery.
- Private cloud/offsite Git backup for disaster recovery.

Recommended retention baseline until a firm-specific policy supersedes it:

- Daily production backup evidence for 30 days.
- Weekly retained backup points for 12 weeks.
- Monthly retained backup points for 12 months.
- Restore-drill evidence retained for at least 12 months.

Offsite storage must be encrypted at rest. The workstation should use full-disk encryption, and any external backup provider must support access control, auditability, and recovery from account compromise.

## Encryption And Access Rules

Minimum production expectations:

- Approved private Git remote only.
- Multi-factor authentication on the remote account.
- No credentials or API secrets stored in the workbook, repo, screenshots, logs, or support bundles.
- Full-disk encryption on the workstation.
- Encrypted offsite storage for exported backup evidence, safety copies, or support bundles.
- Access limited to the operator and approved support/admin roles.
- Backup locations and retention windows recorded in the pre-live evidence packet.

## Restore Testing Cadence

Run and record a controlled restore drill:

- Before live deployment.
- After changes to backup, restore, workbook integrity, or database artifact scripts.
- After major workbook schema or data migration changes.
- Monthly during pre-live buildout while production data handling is being hardened.
- Quarterly after live deployment, or more often if firm policy requires it.

Each drill must include:

- A workbook-inclusive Git backup commit.
- A pre-restore safety copy.
- A selected restore commit.
- Pre-restore and post-restore workbook integrity reports.
- Hash/blob verification evidence.
- App launch/data sanity confirmation.
- A written outcome: passed, failed, or passed with signed exception.

## Operator Checklist

Before a production backup:

1. Confirm the pre-live security gate is complete or explicitly excepted.
2. Run `.\scripts\check_workbook_integrity.ps1`.
3. Confirm the Git remote is private and approved.
4. Run `.\git_backup_to_cloud.ps1 -Remote origin -Message "Production backup YYYY-MM-DD"`.
5. Record commit SHA, workbook SHA-256, operator, date/time, and any warnings.

Before a production restore:

1. Confirm CSPM and Excel are closed.
2. Confirm the restore is authorized and the selected remote is approved.
3. Run `.\scripts\run_support_diagnostics.ps1` if the current state may need troubleshooting evidence.
4. Run `.\git_restore_from_cloud.ps1 -Remote origin -DefaultBranch main -MaxCommits 25`.
5. Record selected commit, safety-copy paths, integrity report paths, hash verification, and result.
6. Launch CSPM and confirm the restored data set is correct.

Do not run a production Git restore casually. It is intentionally powerful recovery tooling, not a normal navigation or undo feature.
