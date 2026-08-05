# CSPM Full UI Audit Ledger - 2026-06-11

## Purpose

Durable audit ledger for a Professional-first review of every user-visible CSPM
screen, window, popup, and report, followed by targeted Console regression
checks. This ledger implements the full UI audit plan requested on 2026-06-11
and should be updated one observed problem at a time.

Screenshot target directory:

```text
logs/audit/20260611/
```

`logs/` is git-ignored, so screenshots are local evidence rather than tracked
source artifacts.

## Audit Rules

- Source of truth for workspace inventory: `src/qml/standards/ModulePathways.js`.
- Scope: Home, Clients & Matters, Docketing & Deadlines, Billing & Invoicing,
  Finance & Ledger, Reports, Admin / Settings, detached windows, report windows,
  modals, popups, settings/theme surfaces, taskbar-visible windows, and startup.
- Order: Professional first, then Console spot-checks on shared controls,
  workflows with findings, reports, and dialogs.
- Stop rule: when a confirmed defect is found, stop broad auditing and follow
  the one-problem loop from `docs/MANUAL_SCREEN_REPORT_AUDIT.md`.

## Wireframe Standard

- Text font: `Segoe UI`; glyph/icon font: `Segoe MDL2 Assets` only.
- Professional shell hierarchy:
  - Top header: 72 px.
  - Work-tab bar: 38 px.
  - Breadcrumb/header bar: 44 px.
- Each workspace should have one clear title zone near the top-left under the
  breadcrumb/header area.
- Subtitles sit directly below titles, smaller and muted.
- Section headings, form labels, table headers, status badges, and action rows
  should align consistently and should not duplicate shell breadcrumbs.
- Reports may retain print-document typography inside report pages, while
  report-window chrome, filters, buttons, and dialogs should follow the same UI
  hierarchy as the rest of the app.

## Validation Modes

| Mode | Meaning |
|---|---|
| Static | Code/docs inspection only. |
| Offscreen runtime | QML or PySide runtime smoke without foreground WebEngine/window validation. |
| Live foreground | Real `.\launch.ps1` GUI validation with the app visible and interactive. |
| Not validated | Not checked yet in this audit ledger. |

## Current Audit State

| Field | Value |
|---|---|
| Requested scope | Full workflow audit, Professional first, audit ledger deliverable |
| Ledger created | 2026-06-11 |
| Canonical route count | 72 workspaces |
| Static inventory status | Complete |
| Static formatting cleanup status | Pass 1 started |
| Static UI contract status | Passing |
| Offscreen runtime status | Pending this audit run |
| Live foreground status | Not validated in this environment |
| Active stop-rule finding | AUD-20260611-001 |

## Active Findings

| ID | Severity | Mode | Surface | Finding | Evidence | Next action |
|---|---|---|---|---|---|---|
| AUD-20260611-001 | High | Static | Reports > Productivity & Utilization Report (`D10`) | `ModulePathways.js` labels `D10` as Productivity & Utilization Report, but `PlaceholderSubmenuView.activeIsDocketActivityReport()` also keys `D10` and hosts `DocketActivityReportPanel`; this likely routes the Productivity report surface to the Docket Activity report UI. | `src/qml/standards/ModulePathways.js`; `src/qml/views/PlaceholderSubmenuView.qml` lines around `activeIsDocketActivityReport()` and `DocketActivityReportPanel`. | Live-confirm Professional Reports > Productivity & Utilization Report. If it opens Docket Activity Report, fix this single routing/workflow defect before continuing the broad report audit. |

## Resolved Findings

| ID | Severity | Mode | Surface | Finding | Resolution | Validation | Live follow-up |
|---|---|---|---|---|---|---|---|
| AUD-20260611-002 | Medium | Static plus user screenshot | Docketing & Deadlines > Deadline Master Calendar (`B07`) and Deadline Entry Editor (`B08`) | Professional hosted deadline screens suppressed the shared in-frame workspace header, so controls began directly under the shell breadcrumb with no title/subtitle inside the main frame. | Removed the deadline-specific compact chrome suppression in `TimeDocketView.qml`; the shared workspace header remains visible and uses the standard Professional title/subtitle typography. | Focused `test_time_docket_professional_hosted_layout_uses_compact_margins_and_taller_fields` and `test_practice_briefing_home_module_is_wired` passed; `scripts/qmllint.ps1` on `TimeDocketView.qml` exited successfully with existing warnings; broad UI guard pair passed with 75 tests; `git diff --check` reported line-ending warnings only. | Run `.\launch.ps1`, open `B07` and `B08`, and capture `logs/audit/20260611/B07_deadline_master_calendar_professional.png` / `B08_deadline_entry_editor_professional.png` after visual confirmation. |

## Startup, Shell, And Window Surfaces

| Surface | Style | Screenshot | Title/header status | Font status | Workflow/window status | Severity | Finding | Next action |
|---|---|---|---|---|---|---|---|---|
| Professional startup splash | Professional | `logs/audit/20260611/startup_professional_splash.png` | Not validated | Not validated | Not validated |  |  | Run `.\launch.ps1`; confirm one splash, no flash, correct monitor, main window once. |
| Console startup splash | Console | `logs/audit/20260611/startup_console_splash.png` | Not validated | Not validated | Not validated |  |  | Switch to Console; run `.\launch.ps1`; confirm legacy splash/jelly/audio unchanged. |
| Option 3 shell chrome | Professional | `logs/audit/20260611/option3_shell_chrome.png` | Static partial | Static partial | Offscreen pending |  | Professional shell owns header/rail/tab/breadcrumb boundaries and metrics in code. | Live-check rail/flyout/tabs/breadcrumb, normal/maximized/narrow widths. |
| Settings menu and theme picker | Both | `logs/audit/20260611/settings_theme_picker.png` | Not validated | Not validated | Not validated |  |  | Live-check settings, style toggle persistence, menu placement, and Console regression. |
| Detached workspace window | Professional | `logs/audit/20260611/detached_workspace_professional.png` | Static partial | Static partial | Offscreen pending |  | Detached top header exists in code; taskbar icon still needs live check. | Right-click work tab > Open in new window; verify focus, taskbar icon, close, Return to Dock. |
| Report window chrome | Professional | `logs/audit/20260611/report_window_chrome_professional.png` | Offscreen pending | Offscreen pending | Offscreen pending |  |  | Run report-window smoke and then live-check taskbar icon/focus/export. |
| Modal/popup baseline | Both | `logs/audit/20260611/modal_popup_baseline.png` | Not validated | Not validated | Not validated |  |  | Audit close guards, validation popups, import progress, duplicate prompts, and destructive confirmations. |

## Workspace Inventory

| Module | Section | Node | Workspace | Route | Type | Style scope | Screenshot | Title/header status | Font status | Workflow status | Severity | Finding | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Home | Home | H01 | Practice Briefing | /home/practice-briefing | home | Professional first; Console spot-check pending | logs/audit/20260611/H01_practice_briefing_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Clients | A01 | Client Directory | /clients/directory | screen | Professional first; Console spot-check pending | logs/audit/20260611/A01_client_directory_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Clients | A02 | New Client Wizard | /clients/new | screen | Professional first; Console spot-check pending | logs/audit/20260611/A02_new_client_wizard_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Clients | A03 | Client Profile 360 | /clients/profile | client | Professional first; Console spot-check pending | logs/audit/20260611/A03_client_profile_360_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Clients | A04 | Client Contacts & Roles | /clients/contacts | screen | Professional first; Console spot-check pending | logs/audit/20260611/A04_client_contacts_and_roles_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Clients | A06 | Client ID/KYC Record | /clients/kyc | screen | Professional first; Console spot-check pending | logs/audit/20260611/A06_client_id_kyc_record_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Clients | A08 | Conflict Check | /clients/conflict-check | screen | Professional first; Console spot-check pending | logs/audit/20260611/A08_conflict_check_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Relationships | A05 | Parent-Child Link Manager | /clients/relationships | screen | Professional first; Console spot-check pending | logs/audit/20260611/A05_parent_child_link_manager_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Relationships | A15 | Duplicate Merge Tool | /clients/duplicate-merge | screen | Professional first; Console spot-check pending | logs/audit/20260611/A15_duplicate_merge_tool_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Matters | A09 | Matter Directory | /matters/directory | screen | Professional first; Console spot-check pending | logs/audit/20260611/A09_matter_directory_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Matters | A10 | New Matter Wizard | /matters/new | screen | Professional first; Console spot-check pending | logs/audit/20260611/A10_new_matter_wizard_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Matters | A11 | Matter Profile 360 | /matters/profile | matter | Professional first; Console spot-check pending | logs/audit/20260611/A11_matter_profile_360_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Clients & Matters | Matters | A14 | Matter Reassignment | /matters/reassignment | screen | Professional first; Console spot-check pending | logs/audit/20260611/A14_matter_reassignment_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Time & Docketing | B01 | Time Docket Entry | /docketing/time-entry | screen | Professional first; Console spot-check pending | logs/audit/20260611/B01_time_docket_entry_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Time & Docketing | B02 | Fee Docket Entry | /docketing/fee-entry | screen | Professional first; Console spot-check pending | logs/audit/20260611/B02_fee_docket_entry_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Time & Docketing | B03 | Timer Console | /docketing/timer | screen | Professional first; Console spot-check pending | logs/audit/20260611/B03_timer_console_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Time & Docketing | B04 | Docket Activity Report | /docketing/activity-report | report | Professional first; Console spot-check pending | logs/audit/20260611/B04_docket_activity_report_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Time & Docketing | B05 | Docket Adjustment/Void | /docketing/adjustments | screen | Professional first; Console spot-check pending | logs/audit/20260611/B05_docket_adjustment_void_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Time & Docketing | B06 | Batch Docket Entry | /docketing/batch-entry | screen | Professional first; Console spot-check pending | logs/audit/20260611/B06_batch_docket_entry_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Deadlines | B07 | Deadline Master Calendar | /deadlines/calendar | calendar | Professional first; Console spot-check pending | logs/audit/20260611/B07_deadline_master_calendar_professional.png | Static fixed; live pending | Static fixed; live pending | Not validated | Resolved Medium | In-frame title/subtitle header had been suppressed in Professional hosted deadline chrome. | Live foreground screenshot required to confirm title zone and control spacing. |
| Docketing & Deadlines | Deadlines | B08 | Deadline Entry Editor | /deadlines/editor | screen | Professional first; Console spot-check pending | logs/audit/20260611/B08_deadline_entry_editor_professional.png | Static fixed; live pending | Static fixed; live pending | Not validated | Resolved Medium | In-frame title/subtitle header had been suppressed in Professional hosted deadline chrome. | Live foreground screenshot required to confirm title zone, form spacing, and footer actions. |
| Docketing & Deadlines | Deadlines | B09 | Deadline Rules Library | /deadlines/rules | screen | Professional first; Console spot-check pending | logs/audit/20260611/B09_deadline_rules_library_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Deadlines | B10 | Jurisdiction Profiles | /deadlines/jurisdictions | screen | Professional first; Console spot-check pending | logs/audit/20260611/B10_jurisdiction_profiles_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Deadlines | B11 | Tickler Scheduler | /deadlines/ticklers | screen | Professional first; Console spot-check pending | logs/audit/20260611/B11_tickler_scheduler_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Deadlines | B12 | Reminder Escalation Center | /deadlines/escalations | screen | Professional first; Console spot-check pending | logs/audit/20260611/B12_reminder_escalation_center_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Deadlines | B13 | Filing Checklist | /deadlines/filing-checklist | screen | Professional first; Console spot-check pending | logs/audit/20260611/B13_filing_checklist_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Deadlines | B14 | Deadline Risk Board | /deadlines/risk-board | screen | Professional first; Console spot-check pending | logs/audit/20260611/B14_deadline_risk_board_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Deadlines | B15 | Deadline Audit Trail | /deadlines/audit-trail | screen | Professional first; Console spot-check pending | logs/audit/20260611/B15_deadline_audit_trail_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Trademarks | B16 | Trademark Filing | /docketing/trademark-filing | screen | Professional first; Console spot-check pending | logs/audit/20260611/B16_trademark_filing_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Docketing & Deadlines | Trademarks | B17 | Trademark Directory | /docketing/trademark-directory | screen | Professional first; Console spot-check pending | logs/audit/20260611/B17_trademark_directory_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Core Billing | C01 | WIP-to-Bill Workbench | /billing/wip-to-bill | screen | Professional first; Console spot-check pending | logs/audit/20260611/C01_wip_to_bill_workbench_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Core Billing | C02 | Pre-Bill Editor | /billing/pre-bill | screen | Professional first; Console spot-check pending | logs/audit/20260611/C02_pre_bill_editor_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Core Billing | C03 | Invoice Builder | /billing/invoice-builder | screen | Professional first; Console spot-check pending | logs/audit/20260611/C03_invoice_builder_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Core Billing | C06 | Invoice Reversal/Credit Memo | /billing/reversal-credit | screen | Professional first; Console spot-check pending | logs/audit/20260611/C06_invoice_reversal_credit_memo_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Payments & Adjustments | C07 | Payment Entry | /billing/payment-entry | screen | Professional first; Console spot-check pending | logs/audit/20260611/C07_payment_entry_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Payments & Adjustments | C09 | Write-off/Adjustment Entry | /billing/write-off-adjustment | screen | Professional first; Console spot-check pending | logs/audit/20260611/C09_write_off_adjustment_entry_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Payments & Adjustments | C10 | Collections Queue | /billing/collections | screen | Professional first; Console spot-check pending | logs/audit/20260611/C10_collections_queue_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Transactions & Setup | C11 | Transactions Master | /billing/transactions-master | screen | Professional first; Console spot-check pending | logs/audit/20260611/C11_transactions_master_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Transactions & Setup | C12 | Vendor & Expense Category Manager | /billing/vendors-expenses | screen | Professional first; Console spot-check pending | logs/audit/20260611/C12_vendor_and_expense_category_manager_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Transactions & Setup | C13 | Disbursement Rebill Queue | /billing/disbursement-rebill | screen | Professional first; Console spot-check pending | logs/audit/20260611/C13_disbursement_rebill_queue_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Transactions & Setup | C16 | Payment Method & Reference Register | /billing/payment-references | screen | Professional first; Console spot-check pending | logs/audit/20260611/C16_payment_method_and_reference_register_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Transactions & Setup | C17 | Bank Deposit Matching | /billing/bank-deposit-matching | screen | Professional first; Console spot-check pending | logs/audit/20260611/C17_bank_deposit_matching_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Tax | C14 | HST/GST Remittance Center | /tax/hst-gst-remittance | screen | Professional first; Console spot-check pending | logs/audit/20260611/C14_hst_gst_remittance_center_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Billing & Invoicing | Tax | C15 | Tax Filing Register | /tax/filing-register | screen | Professional first; Console spot-check pending | logs/audit/20260611/C15_tax_filing_register_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Finance & Ledger | Dashboards | D01 | Executive Dashboard | /finance/executive-dashboard | dashboard | Professional first; Console spot-check pending | logs/audit/20260611/D01_executive_dashboard_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Finance & Ledger | Dashboards | D02 | Revenue Dashboard | /finance/revenue-dashboard | dashboard | Professional first; Console spot-check pending | logs/audit/20260611/D02_revenue_dashboard_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Finance & Ledger | Dashboards | D03 | Expense Dashboard | /finance/expense-dashboard | dashboard | Professional first; Console spot-check pending | logs/audit/20260611/D03_expense_dashboard_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Finance & Ledger | Dashboards | D04 | Net Income & Cash Increase | /finance/net-income-cash | dashboard | Professional first; Console spot-check pending | logs/audit/20260611/D04_net_income_and_cash_increase_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Finance & Ledger | Dashboards | D05 | WIP Dashboard/Report | /finance/wip-dashboard | dashboard | Professional first; Console spot-check pending | logs/audit/20260611/D05_wip_dashboard_report_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D06 | A/R Aging & Detail | /reports/ar-aging | report | Professional first; Console spot-check pending | logs/audit/20260611/D06_a_r_aging_and_detail_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D07 | Client Ledger Report | /reports/client-ledger | report | Professional first; Console spot-check pending | logs/audit/20260611/D07_client_ledger_report_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D08 | Matter Ledger Report | /reports/matter-ledger | report | Professional first; Console spot-check pending | logs/audit/20260611/D08_matter_ledger_report_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D09 | Parent Ledger Report | /reports/parent-ledger | report | Professional first; Console spot-check pending | logs/audit/20260611/D09_parent_ledger_report_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D10 | Productivity & Utilization Report | /reports/productivity-utilization | report | Professional first; Console spot-check pending | logs/audit/20260611/D10_productivity_and_utilization_report_professional.png | Static concern | Not validated | Static concern | High | Navigation labels D10 as Productivity & Utilization Report, but PlaceholderSubmenuView.activeIsDocketActivityReport() also keys D10 and hosts DocketActivityReportPanel. | Live-confirm Reports > Productivity & Utilization Report; if it opens Docket Activity Report, fix D10 routing before continuing broad report audit. |
| Reports | Reports | D11 | Earnings Report | /reports/earnings | report | Professional first; Console spot-check pending | logs/audit/20260611/D11_earnings_report_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D13 | Top Client Concentration | /reports/top-client-concentration | report | Professional first; Console spot-check pending | logs/audit/20260611/D13_top_client_concentration_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D14 | Quarterly Performance Pack | /reports/quarterly-pack | report | Professional first; Console spot-check pending | logs/audit/20260611/D14_quarterly_performance_pack_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D15 | Forecasting & Scenarios | /finance/forecasting | dashboard | Professional first; Console spot-check pending | logs/audit/20260611/D15_forecasting_and_scenarios_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Reports | Reports | D16 | Export/Print Packager | /reports/export-print | screen | Professional first; Console spot-check pending | logs/audit/20260611/D16_export_print_packager_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X01 | Global Search Results | /operations/global-search | screen | Professional first; Console spot-check pending | logs/audit/20260611/X01_global_search_results_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X02 | Notifications Center | /operations/notifications | screen | Professional first; Console spot-check pending | logs/audit/20260611/X02_notifications_center_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X03 | Tasks & Approvals Inbox | /operations/tasks-approvals | screen | Professional first; Console spot-check pending | logs/audit/20260611/X03_tasks_and_approvals_inbox_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X04 | Document Workspace Browser | /operations/documents | screen | Professional first; Console spot-check pending | logs/audit/20260611/X04_document_workspace_browser_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X05 | Template Manager | /operations/templates | screen | Professional first; Console spot-check pending | logs/audit/20260611/X05_template_manager_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X06 | User Roles & Permissions | /operations/roles-permissions | screen | Professional first; Console spot-check pending | logs/audit/20260611/X06_user_roles_and_permissions_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X07 | Audit Log Viewer | /operations/audit-log | screen | Professional first; Console spot-check pending | logs/audit/20260611/X07_audit_log_viewer_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X08 | Number Sequence Manager | /operations/number-sequences | screen | Professional first; Console spot-check pending | logs/audit/20260611/X08_number_sequence_manager_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X09 | Reference Data Manager | /operations/reference-data | screen | Professional first; Console spot-check pending | logs/audit/20260611/X09_reference_data_manager_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X10 | Integration Settings | /operations/integrations | screen | Professional first; Console spot-check pending | logs/audit/20260611/X10_integration_settings_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X11 | Backup/Restore & Retention | /operations/backup-restore | screen | Professional first; Console spot-check pending | logs/audit/20260611/X11_backup_restore_and_retention_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X12 | Data Quality Exceptions | /operations/data-quality | screen | Professional first; Console spot-check pending | logs/audit/20260611/X12_data_quality_exceptions_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |
| Admin / Settings | Operations | X13 | Legacy Dockets Import | /operations/dockets-import | import | Professional first; Console spot-check pending | logs/audit/20260611/X13_legacy_dockets_import_professional.png | Not validated | Not validated | Not validated |  |  | Live foreground audit required |

## Per-Screen Live Checklist

Use this checklist for every row above.

- Reachable from expected Professional rail/flyout route.
- Work tab opens or activates correctly.
- Breadcrumb matches module, screen, and record where applicable.
- Title and subtitle use the standard top-left workspace title zone.
- Fonts match Professional hierarchy and do not use glyph fonts for prose.
- Initial data loads from the active workbook or documented static model.
- Loading, empty, and error states are visible and readable.
- Dropdowns contain real options and no stale demo data.
- Required fields and validation messages are clear.
- Labels, table headers, and content do not overflow or clip at normal and
  narrower widths.
- Primary actions are present, stateful, and produce success/failure feedback.
- Save/cancel/close behavior protects dirty data.
- Detach/dock preserves identity where supported.
- Console spot-check confirms shared-control regressions were not introduced.

## Validation Log

| Date | Check | Mode | Result | Notes |
|---|---|---|---|---|
| 2026-06-11 | Startup reading and audit inventory extraction | Static | Passed | Required roadmap/playbook files read; `ModulePathways.js` inventory produced 72 workspaces. |
| 2026-06-11 | Screenshot folder creation | Static | Passed | Created local ignored folder `logs/audit/20260611/`. |
| 2026-06-11 | Professional hosted workspace typography cleanup pass 1 | Static | Implemented | Added `VisualRules.qml` typography tokens; applied fixed Professional title/subtitle sizing, Segoe UI text, and non-duplicated content titles in `PlaceholderSubmenuView.qml` and `TimeDocketView.qml`; corrected placeholder-hosted responsive form grids to use actual grid width. |
| 2026-06-11 | Targeted QML lint wrapper on touched QML files | Static | Passed with warnings | Ran `scripts/qmllint.ps1` on `VisualRules.qml`, `PlaceholderSubmenuView.qml`, and `TimeDocketView.qml`; wrapper exited 0, with existing unqualified-access/missing-property warnings still present. |
| 2026-06-11 | Responsive form-grid guard | Static | Passed | `python -m pytest tests/ui/test_stability_guards.py::test_primary_forms_use_responsive_no_overflow_grids` passed. |
| 2026-06-11 | Theme/stability guard subset | Static | Failed unrelated contracts | `python -m pytest tests/ui/test_theme_legibility_contracts.py tests/ui/test_stability_guards.py` returned 70 passed / 4 failed: trademark save-status semantic tone, deadline editor date-picker hook, and two `MainContent.qml` Option 3 identity string-contract checks. |
| 2026-06-11 | Static UI contract cleanup follow-up | Static | Passed | Repaired the four red contracts from the prior row: Trademark Filing status tone, Deadline Entry Editor date-picker hook, and Option 3 entity-keyed tab identity handoff. Focused checks passed, then `python -m pytest tests/ui/test_theme_legibility_contracts.py tests/ui/test_stability_guards.py` passed with 74 tests. |
| 2026-06-11 | Professional Time Docket layout cleanup | Static | Pending live check | Reduced hosted Professional Time Docket Entry outer/canvas margins and replaced hardcoded 46px live-entry field heights with the taller Professional field metric. Focused static guard passed, then the broad theme/stability guard pair passed with 75 tests; live foreground screenshot confirmation still required. |
| 2026-06-11 | Whitespace diff check | Static | Passed | `git diff --check` exited 0; output contained line-ending normalization warnings only. |
| 2026-06-11 | Live foreground/WebEngine validation | Live foreground | Not validated | Must be run with `.\launch.ps1` in a visible foreground desktop session. |

## Next Live Audit Step

Because AUD-20260611-001 is a High static finding, the next foreground action is:

1. Run `.\launch.ps1`.
2. Confirm Professional mode is active.
3. Open Reports from the left rail.
4. Open `Productivity & Utilization Report`.
5. Capture `logs/audit/20260611/D10_productivity_and_utilization_report_professional.png`.
6. Stop if the screen is actually the Docket Activity Report UI.

If the defect is confirmed, repair only that route/workflow mismatch first, run
safe checks, then retest the same report before continuing the remaining audit
rows.
