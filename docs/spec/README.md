# CSPM Spec Folder

This folder is the machine-readable planning and operating contract for future contributors and AI agents.

## How to use
1. Read `docs/BIBLE.md` first for product intent.
2. Read all `.yaml` files in this folder before planning implementation.
3. Treat these files as source-of-truth for scope, sequence, and constraints.

## Active execution tracks
1. `no_placeholder_21_step_execution.yaml` is the live checkpoint for the 21-step placeholder-elimination plan.
2. `backup_restore_policy.yaml` is the live contract for active workbook protection, Git cloud backup/restore behavior, data integrity gates, and support diagnostics.
3. `pre_live_security_gate.yaml` is the required confidential-data security gate before live workbook use, Git cloud backup with real data, restore drills, or external support sharing.
4. `professional_client_contracts.yaml` is the framework-neutral Option 3 shell, workflow, and local-service contract for the current QML Professional prototype and future Flutter/React Native migration.
5. `docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md` is the required long-term
   product reference when planning SQL storage, trust, GST/HST, tax, household,
   or family-finance work. It is intentionally outside the active implementation
   queue until the 10/10 quality gate is complete or the owner authorizes a
   narrow discovery task.
6. Generated UI registry artifacts for the placeholder-elimination plan:
   - `ui_control_registry.csv`
   - `ui_control_registry_summary.md`
   - `ui_control_contract_matrix.csv`
   - `ui_control_contract_matrix.md`

## Operator docs
1. `docs/PRODUCTION_BACKUP_CHAIN.md` is the user/admin runbook for runtime snapshots, active workbook Git backups, offsite/cloud retention, encrypted backup expectations, restore steps, and restore testing cadence.

## Update rule
When behavior changes, update both:
1. Code
2. Relevant spec files here (plus `docs/BIBLE.md` if principles or scope changed)

## Backup rule
All files in this folder are included in the project snapshot backup/restore chain.
