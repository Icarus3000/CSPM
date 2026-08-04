# CSPM Handoff Index

- Current status: `_cspm_workspace/CURRENT_STATUS.md`
- Workspace plan: `_cspm_workspace/WORKSPACE_PLAN.md`
- Accounts Payable lifecycle repair: `_cspm_workspace/handoff/AP_LIFECYCLE_REPAIR_20260723.md`
- AP/disbursements history: `_cspm_workspace/AP_DISBURSEMENTS_HANDOFF.md`
- Manual UI audit playbook: `docs/MANUAL_SCREEN_REPORT_AUDIT.md`
- Deployment and Installer Guide: `docs/DEPLOYMENT_GUIDE.md`
- Phase 9 Git Reconciliation: `_cspm_workspace/PHASE_9_RECONCILIATION.md`
- Phase 9 A+ Validation Plan: `_cspm_workspace/PHASE_9_A_PLUS_VALIDATION_PLAN.md`
- Phase 9 Gate B Evidence: `_cspm_workspace/PHASE_9_GATE_B_EVIDENCE.md`
- Template Discovery Checklist: `docs/CSPM_Template_Discovery_Checklist.md`

## Architecture Documents
- Contextual Action: `_cspm_workspace/architecture/contextual-action-architecture.md`
- Reporting: `_cspm_workspace/architecture/reporting-architecture.md`
- Global Search: `_cspm_workspace/architecture/global-search-architecture.md`
- Command & Navigation: `_cspm_workspace/architecture/command-and-navigation-architecture.md`
- Document Generation: `_cspm_workspace/architecture/document-generation-architecture.md`
- Privacy: `_cspm_workspace/architecture/privacy-architecture.md`
- Future Microsoft Integration: `_cspm_workspace/architecture/future-microsoft-integration-roadmap.md`

- System Tray & Offline Sync: _cspm_workspace/HANDOFF_20260730_SYSTEM_TRAY_OFFLINE_SYNC.md


### Phase 9 Status Update (2026-07-30)
- **Settings-Precedence Regression**: RESOLVED (authoritative path C:\Users\cschn\AppData\Local\CSPM\user_settings.json).
- **Professional-Interface Launch**: VISUALLY CONFIRMED BY CORY (approx. 18s).
- **Full Automated Suite**: PASS (393 passed, 12 skipped, 0 failed).
- **Production Build**: DEFERRED BY CORY (CSPM is in active development, not yet distributed).
- **Phase 9 A+ Status**: NOT YET CLAIMED (Cory has additional bugs to address).
- **Phase 10 Ask CSPM**: PAUSED.
- **SQL and SQLite**: PAUSED.
- **System-Tray Timekeeping**: Deferred until application is stabilized.
- **Gate B**: Evidence preserved, but production/installer readiness is deferred.


### Phase 9 Icon Repair Update (2026-07-30)
- **Stale CSPM.exe Discovered**: The previous CSPM.exe (approx. 16:28 PM) predated the settings repair and was stale.
- **Previous Executable Timestamp**: Thu Jul 30 16:28:50 2026 (SHA-256: 16edeb1b4dd75d2046b8ddc51be55ce759fe30b72c76ac5859cc69745a6c0e64)
- **Fresh Candidate Timestamp**: Thu Jul 30 18:06:48 2026 (SHA-256: 85B87AABC454A2470EBD483C51DE6FEA614763F029512C2125C6D2A6E36C9C80)
- **Icon Root Cause**: The PyInstaller build configuration (scripts/build_release.py) was completely missing the --icon argument for the main application, causing Windows to fall back to generic icons or cached stale icons.
- **Repairs**: Added --icon=src/assets/app_icon.ico to the cmd_main build command.
- **Test Results**: Focused icon identity test passed. Full suite passed (398 passed, 12 skipped, 0 failed).
- **Candidate Build Result**: A fresh, disposable candidate build was successfully generated. Packaged templates do not match live workbooks.
- **Visual Status**: Cory visual status is PENDING (needs to inspect the uniquely named executable).
- **Production Status**: Production readiness and Phase 9 A+ are NOT CLAIMED.
