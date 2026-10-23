# Client Ledger — Dockets Layout: Implementation Plan

Prepared: 2026-09-28. Status: planning only; implementation has not started.

## Requested outcome

Add a dedicated **Client Ledger (Dockets Layout)** navigation link and report workspace. Its title is **Client Ledger**. Reproduce the information, column order, chronological presentation, and two closing summaries in the supplied Dockets report, using CSPM's branding and header.

Deliver the native on-screen table and **Zen View** first. Add the usual **Save PDF**, **CSV**, **Print**, and **Copy** actions after the display and calculations have been verified. The existing Client Ledger and Matter Time Ledger retain their own routes.

The report is a read-only view of the active CSPM data. Dockets is the comparison reference during development; generating the new report does not require Excel, run VBA, import records, or modify financial data.

## 1. Confirmed legacy report contract

The original `ModClientLedger.bas` was read directly from `data/Dockets.xlsm` without executing macros. Relevant procedure: `GenerateClientLedger`, module lines 46–387. These findings refine the earlier screenshot-based assessment.

| Element | Verified Dockets behavior | CSPM implementation |
| --- | --- | --- |
| Selection | One client; start and end date, inclusive | Client selector plus From/To calendars; **All History** by default, with presets and any manually selected date range |
| Detail rows | Dockets, disbursements, and receipts, ordered by date | Merge the corresponding CSPM source records into one chronological table |
| Columns | Date, Description, Inv #, Time, Rate, Disbs, Fees, Credits | Preserve these eight labels and their order |
| Fees | Dockets column H, `Amount to CS` | Use the stored `AmountToYou` value, preserving direct fees and approved overrides |
| Credits | Positive `Ledger.Collected`, on the ledger date, retaining description and reference | Use dated receipt/allocation records; do not substitute each invoice's lifetime AmountPaid |
| Invoice reference | Show the reference for billed entries; blank for WIP as of the end date | Preserve real references and the literal `BILLED` marker |
| WIP | Within the selected detail range; reference blank, unresolved, or linked to an invoice after the end date | Apply this historical invoice-date rule, with explicit handling for native CSPM statuses |
| WIP summary | Fees + Disbs = Total, before tax | Sum eligible unbilled detail entries |
| Billing summary | Invoice Log fees + disbursements + tax − Ledger receipts = A/R Balance | Use invoice and receipt facts through the end date, independently of visible docket totals |
| Billing period | All available history through the end date; start date is ignored | Label **Through [end date] — all billing history**; the old macro incorrectly repeats the detail date range beneath this summary |
| Styling | Wrapped descriptions, muted/italic billed entries, green receipts, alternating pale rows | Apply equivalent readable treatments using CSPM theme tokens |

Example checked against the supplied sample: 0.3 hours × $350 × 70% = $73.50 in Fees. Neither gross client fees nor the inclusive-of-HST amount is a substitute for that value.

The detail is an activity history. It does not include the current Client Ledger's synthetic invoice charge and WIP-relief rows. Billed totals come from invoices, so invoice discounts and custom fees must not be replaced by a sum of historical docket values.

### User clarification: default and date controls

The 2026-09-28 clarification supersedes the original macro's 2025-01-01 default:

- A fresh workspace starts on **All History**, with no lower or upper date restriction, matching CSPM's existing All Time control. Do not hard-code a first year or silently restore a previously narrow range as the new default.
- Offer **All History**, **Today**, **This Week**, **Last Week**, **This Month**, **Last Month**, **Last 30 Days**, **Last 90 Days**, and **YTD**, using CSPM's calendar conventions.
- Allow typed dates and calendar selection for any custom From/To range. Editing either date marks the selection **Custom**; validate date syntax and reject From later than To. Returning to All History clears both boundaries.
- Keep the user's current selection when switching between the report tab and Zen, exporting, or returning to an already open workspace. An explicit contextual navigation handoff may supply a range; a fresh menu launch defaults to All History.
- With All History selected, detail, WIP, and billing summaries use all eligible records. With a custom range or preset, detail/WIP use that range and billing history remains cumulative through the selected end date, labelled accordingly. With no end boundary, include all invoice/receipt dates and evaluate WIP against all known valid invoice references.
- Capture the resolved preset dates in the completed report payload, so Zen and exports do not re-evaluate a relative preset after midnight.

## 2. Calculation and data preparation

Create a small report service, provisionally `src/python/services/client_ledger_report_service.py`, supplied with records by `ExcelRepo`. Reuse existing party resolution, invoice validity, payment-allocation, and status helpers where their behavior matches the verified contract. Keep arithmetic and financial classification in Python.

Read Clients/Client Profiles/Parents, Time Entries, Disbursements, Invoice Log, Ledger, and Receivables as one consistent report snapshot. Use the bulk-read path with an existence/schema preflight: the current helper can call `ensure_schema()` if the workbook is missing, so calling it unconditionally is not sufficient to guarantee read-only behavior. Missing data must produce an actionable load error instead of initializing or repairing a workbook.

Return a versioned payload containing:

- Client identity and display name; selected dates; distinct billing party only where useful.
- Ordered entries with stable source IDs, date, full description, display reference, time, rate, disbursements, fees, credits, and billed/WIP/receipt presentation state.
- WIP summary and its period.
- Billing summary and its independent through-date basis.
- Row count, generation timestamp, source revision, and any unresolved reconciliation issues.

Use decimal money arithmetic and documented rounding. Distinguish missing amounts from valid zero amounts. Any fallback for an absent legacy fee must use the recorded hours/rate/share and be identified during reconciliation; never apply the share percentage twice.

Resolve these cases before accepting the financial results:

1. **Client scope:** match the legacy Client selection to CSPM's stable client/billing-party relationships. A shared billing party must not cause unrelated work clients to enter the report. Test A2B as well as one client billed through another entity.
2. **Receipts:** count each posted invoice allocation once. A single bank receipt allocated across invoices must not be counted again from Transactions Master or Receivables. Preserve receipt dates and legacy descriptions such as `Client Fees`.
3. **Historical WIP:** test blank references, `BILLED`, valid invoices before/after the end date, and unresolved legacy references. Treat native Draft/Ready, Billed, Merged, Reconciled, and reversed records according to their actual lifecycle; the existing ledger's simple non-billed-to-WIP conversion is insufficient.
4. **Native adjustments:** honor posted invoice corrections and credit/write-off effects without representing non-cash adjustments as cash receipts. When present, add a clearly labelled adjustment explanation or conditional summary component so the A/R arithmetic remains visible. Ordinary reports retain the two familiar summary blocks.
5. **Custom fees:** recognize native internal reconciliation rows and respect existing hidden-adjustment presentation rules. Retain genuine work history and use the authoritative posted invoice for billing totals. Do not expose internal audit markers as ordinary client-facing narratives.
6. **Historical limitations:** use dated events for end-date reconstruction where available. Do not silently treat today's receivable totals or current void status as proof of every past state. Record any case the available history cannot reconstruct reliably during the comparison stage.

## 3. Native report workspace — first implementation milestone

Register **D19**, route `/reports/client-ledger-dockets`, unique report identity `client_ledger_dockets`, and tab key `report:D19`, adjacent to the existing ledger links in **Finance & Ledger → Dashboards & Ledgers**. D19 was unused when inspected; recheck before implementation. Wire both Professional and Console entry points, tab reuse, and command search. Add a matching button to the current Client Ledger toolbar that passes the selected client and dates to the new report.

Build `ClientLedgerDocketsPanel.qml` with:

- Compact Client, From, and To controls; Generate/Refresh action; useful date presets.
- CSPM branding/header, report title, selected client, and detail period.
- Eight-column table with fixed headers, full wrapping descriptions, content-driven row heights, decimal time, aligned money columns, and dashes for inapplicable amounts.
- Chronological order with deterministic same-date ordering and stable source identity.
- The two closing summary blocks directly after the final row. Billing history carries its separate through-date label.
- Clear initial, loading, empty, and failure states. Empty detail still permits a cumulative billing summary when earlier invoices/receipts exist.
- Asynchronous loading with request tokens. A late response for a previously selected client must not replace the current result. Export actions must use a completed snapshot matching the displayed filters.

Keep the first report controls focused on client and dates. Additional filtering must not make a full-client A/R summary look like a total of an arbitrarily filtered subset.

Integration points: `ModulePathways.js`, `PlaceholderSubmenuView.qml` (lazy loading, generic-content suppression, filter state capture/restore, and explicit non-dirty report state), `omni_search.py`, and `docs/spec/professional_client_contracts.yaml`. Follow the worker/request-token conventions in `docketing_controller.py`. The current Matter Time Ledger's fixed-height, elided row delegate is not suitable for this report's full narratives.

## 4. Zen View — included in the first milestone

Extract the report body into a reusable `ClientLedgerDocketsTable.qml` presentation used by the normal workspace and a dedicated Zen Window. Follow the established Matter Time Ledger window pattern, including initiating-monitor placement, native window controls, sensible minimum size, and theme behavior.

Both views consume the same completed payload and formatting rules. Opening Zen requires no new data query. Use separate presentation instances rather than reparenting a live QML item between windows. Closing Zen returns to the same report and selections; reopening reuses the window cleanly. A deliberate Refresh replaces the shared completed snapshot in both views.

The screen should use the available window width and readable text. Paper pagination belongs to export/print preview; the on-screen ledger is a continuous table.

## 5. Usual exports — second implementation milestone

Wire the explicit `client_ledger_dockets` report ID through `AppController`, the report manager, and export dispatch. The existing Client Ledger document omits a report ID and currently falls through the docket-activity export path; the new report must not inherit that behavior.

All actions use the completed on-screen report snapshot, including its filters, ordering, and summaries:

- **Save PDF:** dedicated portrait renderer with CSPM branding, wrapped descriptions, repeated table headings, client/period identification, and Page X of Y. Keep each closing summary together; support narratives that continue across pages without clipping. Exact page count may differ from Excel because the header and font metrics differ.
- **CSV:** the same eight detail columns, report identity/period metadata, and clearly labelled WIP and billing summary blocks. Preserve invoice references, descriptions, zeros, and numeric precision; apply safe spreadsheet text escaping.
- **Print:** the same rendered report as PDF, opened through the established print workflow.
- **Copy:** tab-separated displayed ledger and labelled summaries for pasting into a spreadsheet or document.
- **Feedback:** CSPM's usual success/failure message and clickable output-folder link; support opening the saved PDF.

Reuse branding profiles and export controls. Do not rely on `ReportWindow.qml`'s fixed row-height/count pagination for long descriptions: give this report a content-aware preview path or preview the rendered PDF, with matching Save/Print output.

Export integration points are `AppController.saveReportPdf`, `AppController.exportReportCsv`, and the existing branding helpers in `report_pdf_exporter.py`. If the shared report window is used, also add the new identity to `MainContent.refreshReportFromWindow` with the saved filter state. The current shared toolbar's Print action opens a print-ready PDF; follow that established behavior. XLSX is not part of the existing standard export toolbar.

## 6. Verification and acceptance

### Calculation checks

- Create deterministic fixtures for the confirmed VBA rules, including the $73.50 fee example, disbursements, and receipt credits.
- Confirm detail/WIP respond to the start date while cumulative billing history does not.
- Confirm a fresh report defaults to All History, including records before 2025; exercise every preset, manually chosen ranges, invalid/reversed dates, return to All History, and filter retention across Zen/export.
- Cover partial payments, receipts after the end date, one receipt allocated to several invoices, zero/direct fees, future invoice dates, reversals, reconciled WIP, and custom-fee adjustments.
- Compare A2B for 2025-01-01 through 2026-09-28 against a complete ledger generated from the same source snapshot. The supplied pages establish presentation; matching only pages 1 and 5 is not proof of complete financial parity.
- Explain source-data differences separately from calculation differences. Use a second client with disbursements and a distinct biller to avoid accepting an A2B-only implementation.
- Assert that report loading, Zen, and exports make no financial workbook writes.

### Display/export checks

- Verify all eight columns, long descriptions, receipt/billed styling, two summaries, narrow and maximized sizes, empty results, rapid filter changes, and both themes.
- Check Zen placement on a secondary monitor, repeated open/close, native maximize/restore, and agreement with the main view.
- Confirm PDF, CSV, Copy, and Print contain the same rows and financial values as the displayed snapshot.
- Review multi-page PDF pagination, repeated headings, Page X of Y, summary placement, and the real CSPM header visually.
- Run focused Python tests and compilation, governed `scripts/qmllint.ps1`, and diff checks. Report these static/sandbox-safe checks separately from real foreground Qt/WebEngine/window validation.

## Delivery sequence

1. Lock the legacy rules, native edge-case policy, and fixture/reference comparison.
2. Build the report payload and reconcile calculations.
3. Add navigation, the native table, summaries, and Zen View; review this visual milestone in CSPM.
4. Connect Save PDF, CSV, Print, and Copy to that verified payload.
5. Complete focused regression and real-window checks, update task/implementation records, and package through the established release process when implementation reaches that stage.

This plan is the current deliverable. It does not claim that the screen, export actions, financial parity, or a new release have been implemented or validated.
