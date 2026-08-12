# Phase 7: Statements of Account and Ledgers Task List

## Payment Entry Selection Stability and Form Fit (2026-08-11)

- [x] Preserve the selected invoice as a scalar invoice key across payment-list refreshes, rather than relying on a replaceable table-row object.
- [x] Prevent automatic payment-list refreshes from clearing the active invoice, history, or in-progress partial-payment amount.
- [x] Include the complete Payment Entry state in the parent work-tab checkpoint/restore contract, including selection, payment amount, adjustment amount, and adjustment reason.
- [x] Compact the right-side form slightly so its evidence/status wording remains visible in the normal Professional window without making the fields cramped.
- [x] Commit a payment or payment amendment as one atomic macro-workbook replacement, rather than separately rewriting Transactions, Ledger, Receivables, Time, and Disbursements.
- [x] Use an isolated, unique temporary workbook and bounded retry schedule for a transient Windows file lock; a final lock error now confirms that the attempted change was not saved.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `38CBA00E2D1F7E48517BA0D16D20BF2FB8837B41A730A29C82F8B82A048DE087`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_204651/`. The promoted executable has no `Zone.Identifier` downloaded-file marker.
- [ ] Manually choose an invoice, enter a partial payment, wait through any background refresh, and confirm the selection and entered values remain intact. Confirm the lower status/evidence wording is visible without vertical scrolling at the normal window size. Post a test payment with Excel closed and confirm the worker completes promptly; if an external lock is deliberately held, confirm the retry ends with the clear no-save error and no duplicate payment.

## Invoice Finalization Throughput and UI Responsiveness (2026-08-11)

- [x] Eliminate the serial full-workbook save chain during invoice finalization: calculate the final totals in memory and commit Time, Disbursements, Receivables, Invoice Log, Ledger, and Drafts as one atomic macro-workbook replacement.
- [x] Apply the same one-commit rule when reclaiming a voided invoice number for a correction/reissue, so the internal supersession records cannot cause another multi-save pause.
- [x] Keep Chromium's required PDF render on its GUI thread, but move page-number/header post-processing to the worker pool and give every export its own temporary PDF path.
- [x] Keep CSPM in the foreground during finalization; the success view has its own **Open Final PDF** action, so finalization no longer auto-launches an external reader mid-handoff.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `32A907A81614326AF36F256CF95458D75F5D4362293C9A5C7881A5E2BAAB4B3D`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_202431/`. The promoted executable has no `Zone.Identifier` downloaded-file marker.
- [ ] Manually finalize one ordinary invoice and one correction/reissue invoice from the real package. Confirm the active stage remains visible, Windows never reports CSPM as not responding, the success/check view appears promptly, and **Return to WIP** works after each.

## Matter Financial Safeguards and Visibility (2026-08-11)

- [x] Prevent an existing matter from being moved to **On Hold**, **Closed**, or **Archived** while it has unbilled WIP or unpaid invoices; enforce the rule in the Excel repository, not only in the screen.
- [x] Make permanent deletion a true last resort: block it server-side whenever the matter has linked records, with a specific financial explanation where WIP or unpaid invoices are present.
- [x] Correct the Matter delete-confirmation buttons so both retain usable fixed dimensions, and keep the dialog open with an inline reason when deletion is refused.
- [x] Add a live **WIP & unpaid invoices** panel to both Matter Profile 360 and the editable Matter screen, including a matter-filtered **Open WIP Ledger** tab and direct invoice links that open each invoice in a new Invoice Directory tab.
- [x] Add regression coverage proving that the financial summary follows the work matter rather than the billing client, and that deletion is blocked by active WIP/A/R.
- [x] Treat legacy Dockets matter rows as fallback-only in Statements of Account: when a current time/disbursement row already resolves an invoice's matter, do not append a stale reversed/pre-reissue legacy association.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `CC1BC203D975F0E3A0B0688BFA5E0D44C4CB473B75E319514FF988DC9FA0B149`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_155245/`.
- [ ] Manual foreground verification: open a matter with WIP and unpaid invoices; confirm the card amounts/list, the WIP and invoice links, rejection of On Hold/Closed/Archived, and the corrected delete-dialog button sizing. Then resolve all work and confirm the status/deletion rules permit the appropriate next step.

## Matter Rename Save Verification (2026-08-11)

- [x] Prevent a dirty **Edit Matter** form from returning to Matter Profile 360 through **Cancel** without an explicit discard decision.
- [x] Rename the edit action to **Save Matter & Return** and, before returning, re-read the saved matter by ID and verify its Matter Name and Display Name exactly match the submitted values.
- [x] Keep the editor open with a clear error if the post-save verification cannot establish the saved name pair.
- [x] Add regression coverage for the protected cancel and verified save/return contract.
- [ ] Manual foreground verification: edit a test matter's Matter Name and Display Name, select **Save Matter & Return**, and confirm the profile heading, selector, and field values show the new names. Then make another edit, select **Cancel**, and confirm the discard confirmation offers **Keep Editing** and **Discard Changes**.

## Tab Transition Performance Audit (2026-08-11)

- [x] Measure the live Leviathan Statement path and identify the material cold-read costs: schema validation, CSPM workbook parsing, and an unnecessary legacy-Dockets fallback.
- [x] Read Statement-related workbook tables in one opening, cache a verified schema for the unchanged workbook, and skip the legacy Dockets workbook when current records already resolve every requested invoice's matter.
- [x] Move Statement client-list, open-invoice, and preview requests to existing QThreadPool workers; load the Statement component only when its D17 route is active; and remove redundant Option 3 state reapplications during routed workspace opens.
- [x] Add runtime timing for all Option 3 workspace opens and Statement background requests, so the next manual run produces concrete route evidence in `logs/cspm.log`.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the performance repair (SHA-256 `9F90122E5B0E1EBDF420B22FF7F900B8804C2CFB2B56A80A636A8BDB6CC70391`); the preceding release is recoverable at `to_delete/dist__replaced_release_20260811_151733/`.
- [ ] Manual foreground verification: open **Finance & Ledger → Statement of Account** from a cold launch. The tab shell must appear immediately with a loading state, remain responsive while choices/invoices load, and still generate the same 21 Leviathan open invoices. Then open several other modules and inspect new `[PERF] MainContent workspace-open-*` entries in `logs/cspm.log` before choosing the next screen-specific optimization.
- [ ] Complete the application-wide transition audit one route at a time using those timings; prioritize the remaining large eager QML views and synchronous workbook calls. Do not migrate the production datastore until those UI and query baselines are recorded.

## Invoice Builder Preview Responsiveness (2026-08-11)

- [x] Profile the live draft-preview path and identify the actual cold-read cost: synchronous draft selection and repeated macro-workbook parsing, rather than HTML rendering.
- [x] Add a signature-validated streaming read path for cached workbook table layouts; warm the seven tables required by Invoice Builder from one immutable snapshot.
- [x] Move Invoice Builder draft selection to one background workspace request that returns the draft, its line items, and rendered preview together.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the preview responsiveness repair (SHA-256 `35030BD17EB952C7AE95089BE83B4A397483596AAEB1AD1BB6D60E13B4A93D34`); the preceding release is recoverable at `to_delete/dist__replaced_release_20260811_195859/`.
- [ ] Manual foreground verification: from a cold launch, open WIP-to-Bill then Invoice Builder, select a draft, and confirm the shell remains interactive while a preview is prepared; reselect the same draft and confirm it paints essentially immediately.

## Statement-to-Record Navigation (2026-08-11)

- [x] Make each Statement of Account invoice number a direct link that opens the selected invoice in its own Invoice Directory workspace, without replacing the statement tab.
- [x] Preserve each resolved Matter_ID in the statement data contract and make the individual matter name within `Client & Matter` a direct Matter Profile 360 link; unresolved historic text remains non-clickable rather than guessing a record.
- [x] Add regression coverage for the Matter_ID-bearing statement row contract and verify all 21 current Leviathan open invoices expose a resolvable matter link in a read-only live-workbook check.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `9A3181C405787F614DC3BDF45D53C8E36F73E854F95BD57EB197C7110F191484`); the preceding package is recoverable at `to_delete/CSPM__replaced_release_20260811_144319/`.
- [ ] Manual foreground verification: from Statement of Account, select an invoice number and a matter name. Confirm the original statement remains open, the invoice opens in a distinct Invoice Directory tab, and the matter opens its correct Matter Profile 360 record where **Edit Matter** allows a rename.

## Daily Operations A/R Metric Clarity (2026-08-11)

- [x] Replace the ambiguous Daily Operations headline `Overdue A/R` with the authoritative total open A/R from the same Receivables-based authority as A/R Aging & Detail.
- [x] Retain overdue exposure as the secondary line, including its dollar amount and invoice count, using the user's configured overdue grace period.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `487E3F85C38FF22EA78EA7FEFFDEEA2AB8AED6812FB4AA78AC0B6597F9659D17`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_125058/`.
- [ ] Manual foreground verification: confirm Daily Operations now reads `Total A/R` with an `Overdue: $… · … invoices` secondary line, and that selecting it still opens A/R Aging & Detail.

## WIP-to-Bill Performance and Responsiveness (2026-08-11)

- [x] Eliminate the automatic 300 ms WIP-load delay and the repeated full reload triggered by workspace state restoration.
- [x] Cache the WIP projection in memory for the current workbook signature; serve a tab re-entry from that cache and prevent concurrent duplicate loads.
- [x] Read the five WIP lookup/data tables from one macro-workbook opening rather than opening and parsing it once per table.
- [x] Keep the prior verified WIP list visible if a manual refresh fails, and show an inline `Loading` / `Ready` / cached status beside the explicit Refresh control.
- [x] Add focused regression coverage for the one-snapshot read and signature-checked cache path.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after this WIP responsiveness repair (SHA-256 `8EC1CF44EF6542351FAA0A182A5FE784E8B7CB42DE17573991C96135067F8AB8`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_121600/` and the validated build candidate remains at `to_delete/dist_staging_32820__unpromoted_build_20260811_121443/`.
- [ ] Manual foreground verification: open WIP-to-Bill Workbench twice without changing data (the second opening should be effectively immediate and say `cached`); click Refresh once and confirm the screen remains responsive while it updates.

## Invoice 26-0057 Reversal and Single-Docket Correction (2026-08-10)

- [x] Repair the Invoice Reversal service/UI signature mismatch that caused reversals to fail before changing workbook data.
- [x] Make a reversal return only its linked WIP to the canonical unbilled state, void its receivable, and retain one auditable `-V` contra record in Invoice Log, Ledger, and Transactions.
- [x] Exclude void/reversal invoice lines from Client Ledger while retaining the returned WIP docket.
- [x] With CSPM and Excel closed, create a verified candidate then promote the repair for only `T_e6d43292a1` (2026-05-05) from 965 Canada to AL ADVISOR / Tax Planning. The recoverable pre-repair backup is at `C:\Users\CorySchneider\AppData\Local\CSPM\backups\CSPM\al_advisor_may5_20260810_182534\CSPM.before-al-advisor-may5-repair.xlsm`.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the correction (SHA-256 `91291C6D0125C710E82E3DFED1B8EDBA00B9BD1CA923AF5C82F66FC93C0CF916`); the previous package is recoverable at `to_delete/CSPM__replaced_release_20260810_183823/`.
- [ ] Manual foreground verification: in AL ADVISOR's Client Ledger, confirm the May 5 time entry is WIP and there are no active invoice lines for 26-0057; confirm no other 965 Canada docket moved.
- [ ] Decide and perform the separate authoritative `Dockets.xlsm` correction before the next historic financial sync, otherwise that sync will restore the old historic 26-0057 state.

## Correct and Reissue Invoice Workflow (2026-08-10)

- [x] Add a supported **Correct & Reissue** path for an unpaid, uncredited invoice: return only its linked WIP, preserve the original/reversal as internal audit evidence, and carry the original invoice number as a suggested replacement.
- [x] Let the returned WIP be reassigned before it is redrafted; keep the original number as an editable suggestion at finalization rather than a hard lock. Removing a docket from a correction draft releases the suggestion so it can be billed independently.
- [x] Keep internal `-SUPERSEDED` and `-V` audit entries out of Client Ledger and recipient-facing statements.
- [x] Add regression coverage for reversing, suggesting, reassigning/redrafting, choosing a different valid final number, and releasing removed WIP for separate billing.
- [x] Let Finalize Invoice reclaim a previously voided, unpaid/uncredited number in-app: show clear guidance, archive the former record only at confirmed finalization, and then issue the corrected replacement under the original number.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `B29F723E80AD0EAF0B39FB681003C80090E00E09FB194F2C8E522D9CD0F0FDC4`); retain the prior package at `to_delete/dist__replaced_release_20260811_101916/`.
- [x] Redesign the Correct / Reverse modal so its instructions scroll inside a responsive card while **Cancel**, **Correct & Reissue**, and **Reverse Only** remain visible at the bottom of the window.
- [x] Make PDF handling genuinely optional: **Keep PDF** is the default, and Move/Delete require the user to select a real source PDF. Validate that selection before changing financial records; never overwrite an existing archived PDF.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` with the modal repair (SHA-256 `A6853F5CA92EC5A61511BA101141AAAAA8F8012303E22B3C8B7C9BAE342B5B00`); the prior package is recoverable at `to_delete/dist__replaced_release_20260811_181606/`.
- [x] Move Invoice Directory list/detail reads and Correct & Reissue / Reverse workbook work to background workers so the QML event loop can paint and remain interactive throughout the operation.
- [x] Make a statement-routed Invoice Directory selection refresh its detail card automatically once the invoice list arrives; show explicit loading state rather than temporary zero-dollar results.
- [x] Replace the unreliable modal radio controls with direct, mutually exclusive PDF-action rows and a visible non-blocking working state.
- [x] Move final-invoice number lookup, final HTML preparation, and post-finalization draft refreshes off the QML thread; present the active finalization phase while each background step completes.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the Invoice Directory and finalization responsiveness repairs (SHA-256 `5FF8C7112C90638F8C379A8AC453E4F38BD3DFF0F77C9DDA64DD6295AFF2C8B0`); the prior complete release is recoverable at `to_delete/dist__replaced_release_20260811_190908/`.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after making correction numbers suggestions rather than locks and releasing the split Concierge Club 26-0092 docket (SHA-256 `A3C66B3AFFD0BA0D7FF1BA4E55E1E4F30F3A44C31B06E0EEC7566A475269211C`); the preceding package is recoverable at `to_delete/dist__replaced_release_20260811_192907/`.
- [ ] Manually verify a full correction-and-reissue cycle in the real application.
- [ ] Manual foreground verification: open an invoice link from Statement of Account and confirm the directory card populates without deselecting/reselecting. In Correct & Reissue, choose each PDF option once and confirm only that option is visibly selected. Choose **Delete selected PDF permanently** with a selected test PDF, select **Correct & Reissue**, and confirm the modal reports progress while the app remains responsive.
- [ ] Manually verify a corrected draft prefills its former invoice number as a suggestion, accepts another unused number, and keeps a removed docket as ordinary WIP for a separate invoice.

## Statement of Account Internal Adjustments (2026-08-10)

- [x] Keep historic background CreditsAdj rounding/write-off entries out of the recipient-facing Paid / Credits column.
- [x] Render the client-facing invoice total net of the internal adjustment, while preserving the original receivable, payment, and adjustment audit values in the workbook.
- [x] Add a regression test for invoice 26-0055-style one-cent background adjustments.
- [x] Rebuild and promote dist/CSPM/CSPM.exe (SHA-256 3050A8578A9BC65953072F8DBD7CA0715670DB839CF089BFA5B31B1D74AD7374); retain the replaced package at to_delete/CSPM__replaced_release_20260810_174719/.
- [ ] Manually confirm invoice 26-0055 displays $2,361.70 / no payment credit / $2,361.70 and the Leviathan statement total is $53,474.49.

## LIHDC Settlement Set-off Reconstruction (2026-08-10)

- [x] Diagnose the six 2026-07-29 LIHDC settlement allocations incorrectly imported as CIBC Chequing → AMEX / Costco transfers.
- [x] With user confirmation and CSPM closed, create recoverable local-workbook backups and reconstruct the governed A/R–A/P set-off payment, ledger evidence, A/P bill state, clearing-account transaction references, and voided duplicate settlement expense.
- [x] Route Invoice Directory settlement links to a record-specific Accounts Payable set-off tab instead of Transactions Master.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` with the governed set-off detail workspace (SHA-256 `115D03EBA9800DF4B7E5B9F2C3DD4F0542909FC135C2509E610CF1680899238C`); retain the replaced package at `to_delete/CSPM__replaced_release_20260810_130505/`.
- [ ] Manual foreground verification: open invoice `26-0069`, select the $2,649.44 settlement set-off, and confirm a new tab shows the LIHDC set-off, its six allocations, no bank account, and the reversal/replacement action.

## Invoice Directory Card Density and Payment-Tab Handoff (2026-08-10)

- [x] Increase the Invoice Directory summary cards symmetrically, make the invoice-status pill more noticeable, and tighten the Payment & Ledger card's internal hierarchy. User visually confirmed the revised presentation is better.
- [/] Make payment IDs, amount/date links, and the Payment Entry action open record-specific payment work tabs without replacing the Invoice Directory tab.
- [/] Add each linked matter's plain-English description as a compact, hover-expandable third line in the Invoice Directory sidebar.
- [x] Rebuild and promote the complete runnable package at `dist/CSPM/CSPM.exe` after the Invoice Directory changes.
- [ ] Manually confirm the matter-description line is readable and that payment ID, amount/date, and Payment Entry each route to the intended payment tab while the Invoice Directory remains open.

## Native Splash Loader Refinement (2026-08-10)

- [/] Replace the native splash's narrow, exponential pseudo-progress line with a visible zero-percent hold, elapsed-time progress, and a wider plasma-style loader.
- [x] Anchor splash progress to the first post-startup paint rather than process startup, extend the zero hold, and slow the normal advance so the initial visible frame cannot be near full.
- [ ] Manually launch CSPM and confirm the splash opens at a visible 0%, advances smoothly, reaches 100% during the main-window handoff, and reads clearly against the logo in the real app.

## Data Folder Automatic Restart (2026-08-10)

- [x] Replace the broken immediate relaunch after Data Folder Setup with a delayed restart that waits for the active CSPM process and its single-instance lock to exit first.
- [x] Rebuild and promote the complete runnable package at `dist/CSPM/CSPM.exe` after the splash and auto-restart repairs.
- [ ] Manually complete the final Data Folder Setup step and confirm CSPM closes and automatically reopens using the selected Shared Data Source and Local Working folders.

## Selectable Billing-Client Statements (2026-08-10)

- [x] Add an explicit Billing Client selector that lists bill-to parties with open receivables.
- [x] Load unpaid and partially paid invoices by billing client and statement date, selecting every open invoice by default.
- [x] Let the user manually include/exclude invoices, select all/clear, and see the selected balance update before generation; the selection never changes A/R data.
- [x] Replace the generic statement PDF path with a dedicated branded Statement of Account layout, including bill-to details, selected invoices, amount-due callout, and payment-contact note.
- [x] Add focused regression coverage and promote the runnable package at `dist/cspm.exe` (SHA-256 `8B3F64D8C9072B5B94845DDAC21777D1A0B768E32788FD0B7C59CAB2452DD381`); the replaced package is recoverably retained under `to_delete/`.
- [x] Remove inherited generic placeholder controls from the live `D17` statement route, require an explicit billing-client selection, default the statement date to today, and use the Professional semantic input/button controls.
- [x] Rebuild and promote the revised package at `dist/CSPM/CSPM.exe` (SHA-256 `18BD4913E9E69F185E8AC732CD9930841E8E87F0FE3A37FE41EA41EEAA765CFD`); the prior package is retained at `to_delete/CSPM__replaced_release_20260810_135556/`.
- [x] Resolve every statement line to the actual client and plain-English matter receiving the work, including historical companion-docket evidence. Never substitute the billing client as the work recipient.
- [x] Replace the ambiguous preview `Value` heading with `Details`, and make the primary action open the completed statement preview directly; the preview itself owns Save, CSV, and Print.
- [x] Rebuild and promote the corrected full package at `dist/CSPM/CSPM.exe` (SHA-256 `35A16BAA2A48139EEDC38FAF34054B2EDAAE9C884BFB05CBDED3C0D0291F9085`); the replaced package is recoverable at `to_delete/CSPM__replaced_release_20260810_154508/`.
- [x] Make report CSV export visibly acknowledge its start and outcome, including the exact `CSV Exported. Saved here:` message followed by the destination folder as an inline Explorer link, and a prominent failure notice.
- [x] Rebuild and promote the CSV-feedback package at `dist/CSPM/CSPM.exe` (SHA-256 `5BE3DBA92D634966699417601468954BC1C5ACAF42B90BEF692A079C3A9431FA`); the replaced package is recoverable at `to_delete/CSPM__replaced_release_20260810_162444/`.
- [ ] Manual foreground verification: open **Reports → Statement of Account**, choose a billing client, confirm each `Client & Matter` is the work recipient rather than the billing client, deselect at least one unpaid invoice, select **Preview Statement**, and confirm the preview's Save/CSV/Print actions contain only the selected invoices and matching amount due.

## Governed Historic Financial Synchronization (2026-08-06)

- [x] Build a source-controlled synchronization service that treats `C:\Users\cschn\OneDrive - LPN\__Invoices (1)\Dockets.xlsm` as the historic financial authority while preserving CSPM-native records after the source snapshot cutoff.
- [x] Normalize legacy receivable footer/duplicate/credit-sign artefacts with ledger and Invoice Log cross-checks; never import vendor expense references as A/R.
- [x] Build an isolated candidate and audit report before any promotion; require source-owned A/R, ledger, and productivity totals to reconcile within $0.02 / 0.01 hours.
- [x] Gate the actual CSPM Financial Dashboard and Productivity Dashboard calculations against independent candidate values, including exclusion of A/R set-offs from cash banked totals.
- [x] Add an explicit promotion command that checks the original target hash and creates a recoverable pre-sync backup; it refuses to proceed while CSPM holds the workbook open.
- [ ] With CSPM closed and after reviewing the candidate audit, promote the approved candidate and manually inspect the dashboard, the paid LIHDC settlement, and the partial $376.13 balance on invoice `26-0069`.

## Matter Merging & Data Integrity (2026-08-09)
- [x] Identify duplicate matters (e.g. LITE - tax planning) and merge them into an authoritative record by reparenting time entries.
- [x] Identify orphaned matters in time entries (e.g. BORK - Custom Fee) and recreate them in the Matters table.
- [x] Eliminate "ghost" matters by resolving all duplicates and orphans.
- [x] Backend: Expose `mergeMatters` function via `AppController` that links to `ClientRepo` and `ExcelRepo`.
- [x] Backend: Update `_merge_duplicate_matters` to reassign disbursements alongside time and transactions.
- [x] QML: Add **Merge Matter** dialog to the matter profile view (`MatterProfilePanel.qml`).
- [ ] Manual foreground verification: Launch the application and test the UI merge of "CRA Audit" into "Legacy Matter EASY-LEVI-TAX-26-0021" for the Easy 4.0 client.
## Portable Current Data and Explicit Data Locations (2026-08-06)

- [x] Replace the repository's older `data/CSPM.xlsm` with the verified current LocalAppData workbook, including the repaired invoice `26-0080`; `Dockets.xlsm` was verified identical.
- [x] Rename the Settings controls to **Shared Data Source Folder** and **Local Save Folder** so their roles are clear on every computer.
- [x] Require a selected shared source to contain valid `CSPM.xlsm` and `Dockets.xlsm` files, and defer either location change until a clean restart so the active session cannot push into an unpulled/new location.
- [x] Rebuild and promote the revised `dist/CSPM/CSPM.exe`; the active package remains outside quarantine.
- [ ] On the second computer, manually choose the desired shared source package and local save package from Settings, restart, and confirm the current invoices, clients, and dockets appear.

## Repository Build-Artifact Quarantine (2026-08-06)
- [x] Move seven confirmed stale PyInstaller distribution/build artifacts into `to_delete/` for review rather than permanent deletion.
- [x] Update the release builder to quarantine a replaced package and any unpromoted default staging output instead of deleting it or leaving it at the repository root.
- [x] User approved permanent deletion of the reviewed `to_delete/` quarantine; remove its contents while leaving the active package, live workbooks, and source tree untouched.

## Direct-Fee Invoice Finalization Integrity Repair (2026-08-06)
- [x] Diagnose invoice `26-0080` as a direct-fee finalization defect: a valid `$5,000.00` gross fee / `$5,650.00` total had zero net/HST fields, which propagated into Invoice Log, Receivables, and Ledger.
- [x] Harden draft creation, recalculation, and finalization so direct-fee rows recover net/HST from their positive gross amount and finalization recalculates totals before posting accounting records.
- [x] Add a targeted accounting repair service for historical finalized invoices and validate both the prevention and repair paths against a disposable in-memory workbook.
- [x] With CSPM closed, create a reversible active-workbook backup and repair invoice `26-0080`; confirm the live Invoice Log, Receivables, Revenue ledger, and linked fee entry now show Fees `$5,000.00`, HST `$650.00`, and Balance `$5,650.00`.
- [x] Rebuild and promote the revised `dist/CSPM/CSPM.exe`; the previous release is retained in `to_delete/dist__manual_replaced_release_20260806_103020/`.
- [ ] Manually confirm Invoice Directory/Reverse Invoice show the repaired totals, the high-DPI compact layout, and the separate Directory-to-Reversal flow.
- [ ] Manually delete a draft and confirm the only notification is `Draft <number> deleted` (no preview error).
- [ ] Manually launch `dist/CSPM/CSPM.exe` and confirm that only the native PNG splash appears, the main shell's first visible frame appears beneath it, the PNG begins fading out in that same handoff, and CSPM is foregrounded on its target monitor after the PNG closes.

## Native PNG-Only Splash and Matter Selector Repair (2026-08-06)

- [x] Disable every QML splash creation path; retain only a native PNG centered on the target monitor. The main QML load waits for its visible eased fade-in to finish; at the main window's first painted pixel, the main frame is visible beneath it and the PNG starts its eased fade-out in the same handoff. Restore main-window foreground only after the PNG closes.
- [x] Replace the raw bulk-docket matter dropdowns with searchable, light/dark themed controls that display `Client | Matter Description | Matter Number`.
- [x] Rebuild and promote the repaired `dist/CSPM/CSPM.exe`; preserve the immediately replaced package at `to_delete/dist__replaced_release_20260806_105321/`.
- [ ] Manually verify the PNG-only startup, post-splash foreground focus, selector filtering, and selector appearance in both themes.

## Professional No-Open-Tabs Default (2026-08-06)

- [x] Replace the automatic Professional `Practice Briefing` startup tab with the native Professional no-open-tabs background and its existing quick tiles; preserve explicitly routed starts and already-open workspaces.
- [x] Keep the console-style `HomeGrid` exclusive to its existing non-Professional shell rather than overlaying the Professional home.
- [x] Replace the static no-tabs tiles with a responsive, no-scroll Daily Operations home: daily deadline/time/WIP/A/R KPIs, the four primary daily pathways, a capped priority queue, recent work, and WTD/YTD productivity. It reuses the existing Practice Briefing payload and does not open a workspace tab.
- [x] Rebuild the release and place the complete runnable package at the requested `dist/cspm.exe` path; the immediately prior package is recoverably retained at `to_delete/dist__replaced_release_20260806_124516/`.
- [x] Correct the last-tab close path: choosing **Discard** for unsaved Time Docket Entry changes now removes that tab and transitions to the native no-tabs Daily Operations home instead of recreating the same docket tab.
- [ ] Manually launch CSPM normally and confirm the Professional no-open-tabs background/tiles are the first main-app surface with no Practice Briefing tab opened.

## Tray-Only Relaunch Wake-Up (2026-08-06)

- [x] Have the primary instance listen on `CSPM_IPC_SERVER` and route a duplicate executable launch through the exact same `TrayController.open_cspm()` path as the tray's `Open CSPM` action.
- [x] Do not construct a native splash for `--tray-only`; a duplicate executable detects the existing instance before QApplication/splash startup and only wakes that instance.
- [x] Rebuild and promote the updated `dist/CSPM/CSPM.exe`; Windows denied the builder's directory rename, so the verified candidate was copied into the empty `dist/` after the prior package was moved intact to `to_delete/dist__manual_replaced_release_20260806_111120/`. The built candidate remains intact in `to_delete/` as a recovery copy.
- [x] Rebuild and promote the splash/home revision; the verified `2026-08-06 11:21` candidate was copy-promoted after Windows again denied the builder's final directory rename. The replaced release is retained at `to_delete/dist__manual_replaced_release_20260806_112200/` and the candidate remains intact in `to_delete/dist_staging_20652__unpromoted_build_20260806_112140/`.
- [x] Rebuild and promote the Professional-home correction; the verified `2026-08-06 11:27` candidate was copy-promoted after the same Windows rename denial. The replaced release is retained at `to_delete/dist__manual_replaced_release_20260806_112840/` and the candidate remains intact in `to_delete/dist_staging_18240__unpromoted_build_20260806_112751/`.
- [ ] Manually start `dist/CSPM/CSPM.exe --tray-only`, relaunch `dist/CSPM/CSPM.exe`, and confirm the existing app opens without any splash.

## Backend Canonical Account-Balance Engine
- `[/]` Implement canonical account-balance engine in `excel_repo.py`
  - `[ ]` Create `_canonical_ar_ledger(filters)` method
  - `[ ]` Support parsing parameters (client, billing client, matter, date ranges, open-items only toggle)
  - `[ ]` Correctly merge chronological AR transactions (Invoices, Payments, Credits, Write-offs)
  - `[ ]` Apply progressive balance calculations (Opening Balance + Charges - Credits = Running Balance)
- `[ ]` Refactor `get_client_ledger_report` to consume the engine for accurate UI balances.
- `[ ]` Refactor `statement_of_account_report` to consume the engine for robust external payloads.

## QML UI for Statement of Account
- `[ ]` Build `StatementOfAccountView.qml`
- `[ ]` Wire progressive disclosure options (Scope picker, Date range picker, Open items toggle)
- `[ ]` Implement robust layout matching the Professional theme (Semantic colors, standardized tables)

## Contextual Integration
- `[ ]` Wire context pathways to trigger Statement generation from:
  - `[ ]` `ClientProfilePanel`
  - `[ ]` `MatterProfilePanel`
  - `[ ]` `PracticeBriefingView` (optional/advanced)

## Testing and Verification
- `[ ]` Add UI automated tests (`test_statement_of_account_ui.py`) to verify progressive disclosure and display.
- `[ ]` Create backend unit tests (`test_canonical_ar_ledger.py`) to verify calculations for partial/multi-invoice payments.


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

### Phase 9 Active Data Routing Repair (2026-07-31)
- **Startup Logic Contract**: Refactored `AppController.__init__` to load `localDataDir` synchronously and apply `override_data_dir` BEFORE repository and facade instantiation.
- **Empty-Data Safety Barrier**: Implemented strict Phase 4 checks. CSPM.exe will no longer silently seed a blank LocalAppData practice if the configured `localDataDir` is unavailable, or if a valid known project data folder exists (detects frozen/packaged context).
- **Settings Integrity**: Verified that `localDataDir` overrides are not overwritten by the deferred settings load.
- **Verification**: Wrote `test_data_routing_guards.py`. All deterministic path-resolution assertions pass.

## Client Directory Backend-Boot Repair (2026-08-05)

- [x] Prevent the deferred settings worker from starving or being dropped before the critical workbook backend boot runs.
- [x] Rebuild the packaged `dist/CSPM/CSPM.exe` after the repair; only governed blank templates are bundled, and the active LocalAppData workbook remains untouched.
- [x] Historical check: `leviathan` returned 26 rows; this exposed the now-corrected broad metadata/parent-client search defect.

## Directory Metrics & Profile Navigation Repair (2026-08-05)

- [x] Expose the live dashboard summary as a QML slot and push the live payload into the module header after backend boot.
- [x] Restrict Client Directory search to client identity and contact fields, excluding shared parent-client metadata and operational notes.
- [x] Route a Client Directory double-click directly into the populated Edit Client Profile form, with Return/Cancel leading back to the selected Client Profile 360.
- [ ] Manual foreground verification: launch `dist/CSPM/CSPM.exe`; confirm `Leviathan Private Network` returns exactly one row, the badge reads `Active Matters: 192 (Clients: 113)`, and double-clicking that row opens its populated `Edit Client Profile` form.

## Invoice Builder Restoration (2026-08-05)

- [x] Restore the Invoice Builder master-detail layout: line items at left, HTML preview at upper right, and fixed settings/actions controls at lower right.
- [x] Theme every Invoice Builder dropdown with an explicit popup and delegate that reads the application light/dark state.
- [x] Add persisted custom-fee reconciliation choices and payload rules for visible discount-line versus hidden adjustment behavior.
- [x] Correct Discount Line invoice rendering so Legal Services Rendered shows the full docketed service amount before the Courtesy Discount reduces it to the agreed flat fee.
- [x] Tie the transparent native splash fade-out to successful root-QML construction rather than a blind startup timeout.
- [ ] Manual foreground verification: launch with .\launch.ps1, confirm the Invoice Builder in both themes, exercise every dropdown popup, and verify the splash handoff with WebEngine enabled.

## Direct Fee Docket Entry & Professional Splash (2026-08-05)

- [x] Add `Fee Docket Entry` directly below `Time Docket Entry` in the Docketing & Deadlines flyout and route it to its own B02 workspace tab.
- [x] Add a matter-linked direct-fee form that saves a positive zero-hour/zero-rate WIP entry, preserving the normal WIP, draft, and invoice pipeline.
- [x] Keep fee entries separate from the time-docket daily aggregation, and verify in a temporary workbook that a fee-only matter produces a flat-fee invoice payload.
- [x] Remove the Professional splash one-shot path that hid the logo and completed immediately; keep a native logo fallback visible while the animated renderer warms up.
- [ ] Manual foreground verification: launch `dist/CSPM/CSPM.exe`, confirm `Fee Docket Entry` appears directly below `Time Docket Entry`, save a fee against a matter, and confirm the Professional splash logo visibly dissolves in and out before the main window opens.

## WIP Empty-Selection Guard & Packaged Splash Assets (2026-08-05)

- [x] Keep `Create Draft Invoice` clickable with no WIP selection and show a clear, non-blocking explanation instead of starting a build operation.
- [x] Reject empty draft requests in both the billing controller and invoice-draft service, preventing blank invoices from any call path.
- [x] Bundle the root `assets/` folder in release builds and fail the release build if required CSPM splash assets are absent.
- [x] Rebuild and promote the normal `dist/CSPM/CSPM.exe` with the required `CS.svg` and `splash_logo.svg` assets present.
- [ ] Manual foreground verification: click `Create Draft Invoice` with no selected WIP and confirm the warning leaves the builder responsive; then launch `dist/CSPM/CSPM.exe` and confirm the CSPM logo visibly fades in and out before the main window appears.

## Invoice Service Client & Matter Context (2026-08-06)

- [x] Clearly distinguish the invoice `Bill To` recipient from the client receiving legal services.
- [x] Show the actual billed-entry client and matter number/name in a persistent `Legal Services For` block on every invoice, including direct-fee / flat-fee invoices.
- [ ] Manual foreground verification: preview an ordinary invoice and a fee-only invoice; confirm `Bill To`, `Client`, and `Matter` are each visible and accurately identify the work.

## Invoice Date & Close-to-Tray Preference (2026-08-06)

- [x] Make the invoice date explicit in the Invoice Builder, supporting typed `YYYY-MM-DD` values and calendar selection.
- [x] Move the date control into the active `InvoiceBuilderWorkspace` billing-controls panel; the first implementation was in an explicitly hidden legacy fallback layout.
- [x] Validate and persist the selected draft date, invalidate the cached payload, and regenerate the HTML preview immediately.
- [x] Add a persisted Settings toggle for `Close to tray`; use it in the main-window close path instead of unconditionally quitting CSPM.
- [ ] Manual foreground verification: select a draft invoice and verify the blue `Invoice date` panel directly below the preview accepts `YYYY-MM-DD` typing and `Choose date` opens the calendar; set `Close to tray` On, close the main window, and confirm the tray remains usable and restores CSPM; then set it Off and confirm close exits CSPM.

## Invoice Line-Item Field Clarity & Fee Editing (2026-08-06)

- [x] Add light-gray contextual placeholders for blank Date, Description, Hours, and Hourly Rate inputs in the Invoice Builder line-item editor.
- [x] Identify direct fee entries in the draft-line payload and replace the time-only fields with one `Fee amount ($)` input when editing a fee.
- [x] Identify the actual service client and use the matter's plain-English Description (falling back safely to Matter Name) in its place.
- [x] Render third-party service context compactly as `Matter: <client name> | <matter description>` on one line; retain the normal two-field context for ordinary invoices.
- [ ] Manual foreground verification: preview a third-party invoice and confirm the `Legal Services For` block renders `Matter: <service-client name> | <plain-English matter description>` with no coded matter number.

## A/P Settlement Set-Off (2026-08-06)

- [x] Add a linked, non-cash A/P set-off payment method that allocates one supplier-bill settlement against one or more existing receivables, including partial invoice allocations.
- [x] Validate every allocation before saving and post A/P, A/R, ledger, time-entry payment state, expense clearing account, and audit evidence in one atomic workbook replacement.
- [x] Add a matching whole-set-off reversal that restores the A/P bill and all affected receivables together.
- [x] Rebuild and promote the runnable package at `dist/cspm.exe`; preserve its flat executable/_internal/data/recovery layout for future builds.
- [x] Allow an A/P bill total to be entered as the authoritative amount; derive subtotal/HST safely for taxable and HST-exempt bills.
- [x] Make the set-off allocation editor independently vertically scrollable so every allocation can be pasted and reviewed.
- [x] Rebuild and promote the A/P usability repair at `dist/cspm.exe` (SHA-256 `39CA22521371289F5A2E1700CFB9A1F613241C2AA2E2A16660078713B04AE763`).
- [x] Replace raw worker tracebacks in A/P with their concise validation message.
- [x] Stop automatically applying the LIHDC agency share to dockets whose `AmountToYou` is already net of that share.
- [x] Replace typed A/R set-off allocations with a searchable receivable-selection workflow that supports full or partial allocations and an in-dialog balancing total.
- [ ] With CSPM closed, create a recoverable backup and repair the pre-existing double-split balances for invoices 26-0066 and 26-0069 from the supplied July settlement schedule before posting the set-off.
- [ ] Manually verify the set-off workflow in CSPM against a copy of the production workbook before entering the July 2026 settlement.

## Startup Focus Safety Repair (2026-08-06)

- [x] Remove the main-window startup focus lock and every automatic Win32 foreground/topmost escalation.
- [x] Limit splash handoff to one regular Qt activation request and prevent delayed startup timers from reclaiming focus.
- [x] Add a regression test that rejects topmost or foreground-stealing code in the main startup path.
- [x] Limit the settled native window to the visible canvas after confirming the previous release's actual native window covered the full 2380x1500 monitor.
- [x] Restore the backend-boot trigger as a settlement lifecycle action; confirm read-only that the live workbook retains 115 clients, 194 matters, and 682 time entries.
- [x] Rebuild and promote `dist/cspm.exe` (SHA-256 `C2416E8B54FF464ACF37F44B35C615C3E66C985BCFDEAAC944BC725622330791`).
- [ ] Manually confirm that the visible dashboard loads existing data and that another app and the taskbar remain clickable on CSPM's monitor.

## Finalized Preview & UI Polish (2026-08-08)
- [x] Fix HTML Preview Loading UX: Add an animated BusyIndicator cycling circle and tie it to isPreviewLoading.
- [x] Fix Finalized Preview State: Ensure the preview updates to hide the DRAFT tag after finalization.
- [ ] Manual verification: Finalize an invoice and confirm the new success overlay appears, PDF-open buttons work, and the preview removes the DRAFT tag.

## Invoice Directory Matter & Payment Detail (2026-08-10)
- [x] Show each invoice's linked matter with its plain-English description; include time, disbursement, and transaction matter links, with a conservative single-matter historic fallback.
- [x] Show dated payment activity in the ledger card, preserve multiple partial payments, and avoid duplicate transaction/ledger evidence or invoice-creation revenue.
- [x] Refresh an open Invoice Directory immediately after a payment is saved, so the dated history, paid total, and balance update without reselection.
- [x] Enforce all three invoice cards at the 25%-taller height, with balanced flexible top/bottom space rather than an advisory preferred height that the layout may ignore.
- [x] Make the Unpaid status pill 25% more prominent and route it directly to Payment Entry for that invoice.
- [x] Present ledger payments as aligned `Payment | Amount | Date` columns, and let the amount or date open that exact editable payment record; an update adjusts the existing payment rather than creating a second payment.
- [x] Recognize explicitly recorded invoice-linked Transfer set-offs as `Settlement set-off` activity rather than claiming no payments are recorded; include the settlement note and open the editable Transaction Master record in a new tab.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the settlement-set-off correction (SHA-256 `0F69B493A3487812FD7F0C32297834128D9FCE5813C02871CB8D7AC823EAFF40`); retain the replaced package at `to_delete/CSPM__replaced_release_20260810_121803/`.
- [x] Rebuild and promote `dist/cspm.exe` after the update (SHA-256 `7688024CF76F5B41F1E60B9BC91EF44BD155C524260217D06C45BF368671DBA7`); retain the replaced release at `to_delete/dist__replaced_release_20260810_092700/`.
- [ ] Manual foreground verification: select invoice `26-0061` in Invoice Directory; confirm `Commercial Contracts Review`, the Jun 30, 2026 EFT payment, the aligned payment columns, and the taller balanced cards are visible. Confirm an Unpaid pill opens Payment Entry for its invoice, and that clicking a payment amount/date opens that payment for editing. For invoice `26-0069`, confirm the card says `Settlement set-off — LIHDC settlement 2026-07-29` rather than `No payments recorded`; click it and confirm a new editable Transaction Master tab opens for `TXN_e0add4a5d6` while Invoice Directory remains open. Then post two partial payments against a test invoice and confirm both payment dates/amounts remain listed and one can be amended without duplication.

