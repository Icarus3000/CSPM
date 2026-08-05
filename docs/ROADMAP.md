# CSPM Roadmap

Updated: 2026-06-04
Status: Active

## Sprint 0: Platform Pivot (Current)
Goal: establish durable foundation before adding large feature scope.

Deliverables:
1. Bible and machine-readable spec baseline.
2. Project snapshot backup/restore chain including data + specs.
3. Auto backup cadence for core database protection.
4. Canonical implementation order based on user-frequency workflows.
5. Active workbook integrity checks wired into release gates, Git cloud restore validation, and support diagnostics.
6. Production backup-chain operator runbook for snapshots, Git cloud backup/restore, offsite retention, encryption expectations, and restore-drill cadence.
7. Professional client contract baseline covering the Option 3 shell plus Clients, Docketing, Billing, Finance, and Reports workflows.
8. Professional client transport boundary selected: local loopback HTTP JSON for queries/actions plus WebSocket events. The secure explicit-start HTTP proof now drives the real Excel-backed Client Directory/Profile workflow while WebSocket delivery and a visual external client remain pending.

Remaining trust gates before live use:
1. Controlled Git cloud backup and restore drill with workbook hashes/manifests, following `docs/PRODUCTION_BACKUP_CHAIN.md`.
2. Complete the pre-live security evidence packet required by `docs/spec/pre_live_security_gate.yaml`.
3. Decision on whether the known legacy `TEST_CAT` workbook warning must be repaired before production.

## Sprint 1: Daily Data Entry Core
1. Client/matter context selection and persistence.
2. Time capture workflow hardening (timer, narration, validation).
3. Unsaved/running-state crash-safe autosave and restore.
4. WIP queue with edit/approve/hold statuses.

## Sprint 2: Billing Pipeline
1. Invoice drafting from approved WIP.
2. Pricing controls (hourly defaults, flat-fee support).
3. Invoice lifecycle state machine.
4. PDF/print export baseline for invoice docs.

## Sprint 3: A/R and Payments
1. Payment posting and allocation.
2. Aging buckets and collection workflows.
3. Cash projection and risk indicators.
4. Client-facing payment UX hooks.

## Sprint 4: Trust and Accounting Guardrails
1. Double-entry ledger primitives.
2. Trust overdraft prevention rules.
3. Three-way reconciliation report engine.
4. Audit and exception trail exports.

## Sprint 5: Reporting Studio
1. WIP, A/R, productivity, and billing-quality report families.
2. Fun, modern on-screen report layouts with drill-down navigation.
3. Premium PDF export styles and print templates.
4. Report presets and scheduled generation.

## Sprint 6+: Advanced Automation and Integrations
1. Communication-to-time conversion.
2. Passive context tracking enhancements.
3. Document/email hub, OCR, and signature workflows.
4. IP-specific integrations and monitoring.
5. SQL adapter + API layer for mobile and portal expansions.
6. Complete the Professional client proof by adding WebSocket event delivery and a small Flutter or React Native visual client on top of the proven local HTTP Client Directory/Profile workflow.

## Future Data Architecture: SQLite, OneDrive Snapshots, and Azure

<!-- CSPM_FUTURE_DATA_ARCHITECTURE_V1 -->

**Status:** Approved future requirement. Not authorized during the current Excel-backed trust milestone.

**Sequence:** stabilize current workflows, migrate authoritative structured data to local SQLite, add validated OneDrive snapshot transfer for single-user one-computer-at-a-time use, then later consider Azure SQL behind a secure API and Microsoft sign-in.

**Non-negotiable:** never open the live SQLite database from OneDrive. OneDrive stores only completed validated snapshots and associated manifests, checksums, locks, and recovery history.

Full requirement: `docs/FUTURE_DATA_ARCHITECTURE.md`.
