# Statement preview and invoice filters — October 13, 2026

The user approves the reviewed statement and directory changes together and
requests unattended implementation, Git publication and executable recompilation.
This scoped request supersedes the manual audit sequence for these changes;
accepted window motion and the Option 3 architecture remain unchanged.

## Statement of Account

The preview's hidden tint source was incorrectly treated as an absent logo when
positioning firm text. Preview spacing now uses logical logo presence, shows the
ordinary logo in light mode and custom branding, and tints the built-in mark in
dark mode. The header rule clears both branding and page metadata. The saved and
printed header renderer, branding assets and logo dimensions are unchanged.

The invoice selector offers Open (default), Paid and All invoices. Open includes
partially paid invoices; fully settled accounts are available in billing-client
choices. Optional inclusive Invoice date From/To filters default to all dates.
These select invoice issuance dates after the complete A/R stream is calculated
through the independent Statement Date. Dated later payments, adjustments and
their signed reversals are restored for a historical cutoff. Existing undated
legacy rounding adjustments retain their private client-facing treatment.

Only checked eligible invoices reach the preview/PDF/CSV. Paid-only statements
are valid with zero due. Filter changes clear old rows, selections and request
correlation; request IDs include a view-instance key, and overlapping client and
statement reads retain loading state. Filter/client state survives work-tab
capture/restore. Captions, detail titles and date scope accurately describe the
selected invoice set; PDF header composition stays intact.

## Invoice Directory

One existing background bulk read enriches Invoice Log rows with authoritative
current Receivables balances, actual payments and credits. Blank, invalid or
ambiguous balances remain unavailable rather than being inferred as paid.

A valid bare number or currency amount searches only current balance owing in
an inclusive ten-percent interval, using integer cents. The displayed interval
explains the search, and full hyphenated invoice references remain text searches.
Existing Payment Entry's independent search tolerance is unchanged.

All, Paid, Partially paid and Balance owing filters combine with search. Paid
means confirmed zero owing after settlement; Partially paid requires an actual
payment and positive balance; Balance owing includes every positive balance.
Each list entry shows status and balance. Payment, receipt, correction and
finalization refreshes retain filters, while lifecycle-inactive invoices remain
excluded. Search, status and selected-invoice state survive host capture/restore.

## Validation and release

Sandbox-safe checks pass 162 focused synthetic tests, including actual offscreen
QML filtering, selection/state behavior, historical statement balances, invoice
accounting/reversal, payments, ledger reports and 72 preview-header layouts.
Changed Python compiles in memory; all 35 release dependencies match the lock.
Governed QML lint exits zero with existing warning diagnostics, and whitespace
checks pass. No financial records are written by this implementation.

Outside-sandbox native Windows/GPU rendering passes the same 72 preview layouts;
light/dark framebuffer captures are visually reviewed. Executable build,
immutable package checks, actual packaged WebEngine and frozen startup/lifecycle
results are recorded after packaging. Those automated checks do not assert
foreground user acceptance or a new motion-quality assessment. Raw evidence,
runtime captures and release manifests remain in ignored local evidence folders.
