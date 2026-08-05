# CSPM Module Pathways (Authoritative)

Purpose: define a stable 4-tile navigation model and the downstream sub-window pathways for all core workflows.

Status: design baseline for implementation and dump/restore traceability.

## 1) Four Home Tiles (Lanes)

1. Clients & Matters
2. Docketing & Deadlines
3. Billing, Payments & Tax
4. Finance, Reports & Operations

## 2) Sub-Window Inventory

### A. Clients & Matters
- A01 Client Directory
- A02 New Client Wizard
- A03 Client Profile 360
- A04 Client Contacts & Roles
- A05 Parent-Child Link Manager
- A06 Client ID/KYC Record
- A07 Client Notes
- A08 Conflict Check
- A09 Matter Directory
- A10 New Matter Wizard
- A11 Matter Profile 360
- A12 Matter Billing Terms
- A13 Matter Open/Close/Reopen
- A14 Matter Reassignment
- A15 Duplicate Merge Tool

### B. Docketing & Deadlines
- B01 Time Docket Entry
- B02 Fee Docket Entry
- B03 Timer Console
- B04 Docket Review Queue
- B05 Docket Adjustment/Void
- B06 Batch Docket Entry
- B07 Deadline Master Calendar
- B08 Deadline Entry Editor
- B09 Deadline Rules Library
- B10 Jurisdiction Profiles
- B11 Tickler Scheduler
- B12 Reminder Escalation Center
- B13 Filing Checklist
- B14 Deadline Risk Board
- B15 Deadline Audit Trail
- B16 Trademark Filing

### C. Billing, Payments & Tax
- C01 WIP-to-Bill Workbench
- C02 Pre-Bill Editor
- C03 Invoice Builder
- C04 Proforma/Sample Invoice
- C05 Invoice Finalization & Numbering
- C06 Invoice Reversal/Credit Memo
- C07 Payment Entry
- C08 Open Invoice Selector
- C09 Write-off/Adjustment Entry
- C10 Collections Queue
- C11 Expense Entry
- C12 Vendor & Expense Category Manager
- C13 Disbursement Rebill Queue
- C14 HST/GST Remittance Center
- C15 Tax Filing Register
- C16 Payment Method & Reference Register
- C17 Bank Deposit Matching

### D. Finance, Reports & Operations
- D01 Executive Dashboard
- D02 Revenue Dashboard
- D03 Expense Dashboard
- D04 Net Income & Cash Increase
- D05 WIP Dashboard/Report
- D06 A/R Aging & Detail
- D07 Client Ledger Report
- D08 Matter Ledger Report
- D09 Parent Ledger Report
- D10 Productivity Report
- D11 Earnings Report
- D12 Utilization/Realization Report
- D13 Top Client Concentration
- D14 Quarterly Performance Pack
- D15 Forecasting & Scenarios
- D16 Export/Print Packager

### Cross-Cutting
- X01 Global Search Results
- X02 Notifications Center
- X03 Tasks & Approvals Inbox
- X04 Document Hub Browser
- X05 Template Manager
- X06 User Roles & Permissions
- X07 Audit Log Viewer
- X08 Number Sequence Manager
- X09 Reference Data Manager
- X10 Integration Settings
- X11 Backup/Restore & Retention
- X12 Data Quality Exceptions

## 3) User Workflow Pathways (Requested Coverage)

1. New client
- A02 -> A03 -> A04/A05/A06/A07

2. New matter
- A10 -> A11 -> A12

3. Record payment for invoice
- C07 -> C08 -> C09 (optional)

4. Record expenses
- C11 -> C12 -> C13

5. Time docketing
- B01/B03 -> B04

6. Fee docketing
- B02 -> B04

7. HST remittances
- C14 -> C15

8. Invoicing and reversal
- C01 -> C02 -> C03/C04 -> C05 -> C06

9. Client ledgers
- D07/D08/D09

10. Productivity reports
- D10

11. Earnings reports
- D11

12. A/R reports
- D06 + C10

13. Executive dashboard
- D01/D02/D03/D04/D05/D06/D13/D14

14. Deadline tracking
- B07/B08/B09/B10/B11/B12/B14

15. WIP reports
- D05 + C01

16. Additional critical functions
- A08 Conflict checks
- X07 Audit logs
- C17 Bank matching
- X03 Approvals
- X06 Permissions
- X11 Backup/retention
- X12 Data quality exceptions

## 4) Current Tile-to-Module Mapping (Runtime Baseline)

Current runtime module indexes in `src/qml/views/MainContent.qml`:
- 0: Time & Dockets
- 1: Fee Entries
- 2: Billing & Invoices
- 3: Disbursements & Expenses
- 4: Clients & Matters
- 5: Deadlines & Ticklers
- 6: Payments & A/R
- 7: Reports & Productivity

Home tile hub grouping in `src/qml/views/HomeGrid.qml`:
- Matter Status & Task Tracking -> [4, 5]
- Financial Forecaster -> [0, 1, 2, 3, 6, 7]
- Critical Dates & Docketing -> [5]
- Document Hub -> [7]

## 5) Dump/Restore Requirement

This file is mandatory for chatpack generation.
- `scripts/31_dump_chatpack.ps1` must fail if this file is missing.
- Chatpack output must include top-level convenience copy `09_MODULE_PATHWAYS.md`.
- `scripts/35_make_copilot_upload_set.ps1` must copy `09_MODULE_PATHWAYS.md` into `copilot_upload`.
- Generated `copilot_upload/restore.py` should verify that `docs/MODULE_PATHWAYS.md` exists after restore.
