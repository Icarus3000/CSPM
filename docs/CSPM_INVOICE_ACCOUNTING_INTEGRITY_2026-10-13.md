# Invoice accounting integrity repair — October 13, 2026

The user reports a correctly rendered invoice PDF whose directory balance remains
understated after reversal and reissue. They authorize repairing that entry,
checking all outstanding LIHDC invoices, correcting other confirmed accounting
errors, committing/pushing the logic fix and recompiling the local executable.

## Cause and prevention

Draft accounting summed `AmountToYou`, which already contains the lawyer's share,
and then applied the draft's agency deduction again. The document began with
`GrossToClient` and deducted the agency share once. Reissue reused the defective
calculation and therefore reproduced the accounting error.

`InvoiceDraftService` now calculates draft monetary totals from the client-facing
fee base, the selected discount/custom-fee terms and one agency deduction. The
document payload and finalization share that Decimal calculator, including
aggregate HST and consistent cent rounding. Finalization recalculates stale draft
totals before its atomic accounting save. Invoice Directory refreshes after
finalization and coalesces refreshes received while an older read is in progress,
suppressing the obsolete result or error.

Historic financial synchronization now refuses a plan that could replace any
invoice's audited amount or billing-owner correction. It checks source reference
overlap and the actual dated rows the historical snapshot would replace, and
repeats the guard before candidate mutation. Unrelated post-cutoff native
corrections remain eligible for the existing synchronization policy. This does
not automatically merge historical finance or rewrite the legacy source.

## Reviewed financial correction boundary

A private read-only audit compares every positive, nonvoid receivable associated
with LIHDC against saved invoice PDFs and corroborating linked WIP. Fourteen
outstanding invoices are reviewed: five have incorrect monetary totals and eight
have an incorrect billing owner, overlapping across eleven invoices. Existing
payments, credits, dates, work clients, source dockets and reversal evidence are
preserved. Historical issued tax rounding remains authoritative for repairs;
future documents use the common Decimal rule.

The repair command defaults to an isolated candidate. Applying a reviewed list
requires its expected totals, audit reasons, an owned shared checkout, unchanged
source hashes, a protected backup, verification of every table field and row
count, byte-identical macros and historical workbook, and no newly introduced
integrity errors. Only the verified candidate is atomically promoted and
published. Corrections retain timestamped before/after audit history in the
invoice billing snapshot. No practice data, PDF text, private path, workbook or
raw runtime evidence is included in Git.

The authorized eleven-invoice candidate is promoted and published successfully.
Reopened live workbook and Invoice Directory backend checks confirm all fourteen
reviewed invoices have the issued totals, preserved payments/credits and the
correct billing owner. Local/shared hashes agree for both workbooks and the
checkout is released. All historical workbook and macro bytes are preserved;
the 165 changed fields stay within the reviewed invoices and correction types.

The existing workbook has unrelated integrity findings. This scoped repair
does not certify or reconcile those findings. Raw audit, correction plan,
backup/publication evidence and release validation remain in private local
evidence folders.

## Validation and remaining acceptance

The focused synthetic billing, reversal/reissue, custom-fee, payment, WIP and
repair-scope and historical-sync gates pass 139 tests. Changed Python compiles in memory. Governed
QML lint exits zero with existing warning diagnostics and whitespace checks
pass. These checks are sandbox-safe and do not instantiate WebEngine.

The fix is committed and remote-verified on main at
`a8a32e579fae95c84619ca7365090f4b5e29506d`. Both executables are built in an
isolated clean worktree with CPython 3.14.7, the exact locked dependencies,
approved empty templates and the unchanged verified native DLL. Complete
candidate, installed and repository dist packages match all 4,254 runtime files
and 677,647,600 bytes. Runtime manifest SHA-256:
`355F528715C6ABFB180425BB126DC44F5D62A0C7A8C72F54EE168FE35AEE450F`.
Main executable SHA-256:
`AFEACE327D3BA6D4267666081E14A9F675964BF28D9F36F163434481B24F1058`.

Main app: `C:/Programs/CSPM/CSPM.exe`; matching local artifact:
`dist/CSPM/CSPM.exe`. The governed deployment preserves and verifies the previous
runtime/configuration as rollback, retains all existing private installation
files and verifies every installed runtime file. Immutable package audits match
67 embedded project modules plus main, all assets and the accepted native ABI.

Outside-sandbox checks pass actual packaged invoice HTML, JavaScript and PDF
rendering for candidate and installed packages, with the normal Chromium sandbox
enabled. One- and four-docket synthetic invoices agree across draft, PDF payload,
Invoice Log, A/R, Ledger and Directory. A valid synthetic PDF verifies the common
amount, fee and tax. Candidate and installed frozen startup, search/navigation,
restored geometry/input, one normal X-close animation, tray teardown and exit
zero pass on disposable read-only data. Both motion directions use the known
successful safe recovery; this establishes functional validation and makes no
new subjective smoothness claim. The nonfatal DirectComposition diagnostic is
retained in private evidence.

Live A/R Aging, canonical Statement of Account and billing-client choices all
reconcile the fourteen reviewed invoices; the scoped A/R report has no remaining
invoice issues or ledger difference. Both OneDrive file-provider observations
report in-sync state and zero modified bytes, with matching local/shared hashes.
These observations do not assert authenticated server revisions or another
computer's physical readback. Release checks preserve the corrected production
workbook hashes and released checkout. Real user acceptance should reopen
Invoice Directory and LIHDC A/R in the installed application.
