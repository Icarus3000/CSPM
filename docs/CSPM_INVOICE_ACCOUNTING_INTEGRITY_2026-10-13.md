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

Packaging must use the committed source in an isolated clean worktree, the
existing exact locked release environment, approved empty templates and the
unchanged verified native DLL. Candidate and installed package checks must
verify source identity, synthetic invoice accounting/document parity and actual
WebEngine HTML/JavaScript/PDF rendering outside the sandbox. The final release
evidence records their completed status separately. Real user acceptance should
reopen Invoice Directory and LIHDC A/R in the installed application.
