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
Independent unconstrained text measurements prevent a logo-width/text-height
binding cycle during initial fully branded creation, preserving actual fonts
and line spacing.

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
light/dark framebuffer captures are visually reviewed. The first packaged QML
check exposed the initial branding cycle; its failed evidence is retained. The
stronger regression now begins fully branded and rejects binding-loop and
undefined/type errors. The corrected source is separately committed and built.

Feature source `ba85e8fa1021044ee7ed7ae76f0effd8fc72d781` and header initialization
repair `33e328ea088eac99641d41b92df9426a6b10b819` are pushed and independently
remote-verified on main. Both final executables are rebuilt from clean source
`33e328e` using CPython 3.14.7 and the exact locked dependencies, approved empty
templates and unchanged verified native DLL. Immutable candidate source/assets,
native ABI, package privacy and provenance audits pass.

Candidate, installed `C:/Programs/CSPM` and repository `dist/CSPM` runtime copies
match all 4,254 runtime files and 677,669,324 bytes. Runtime manifest SHA-256:
`FABD4D68BFE853DFA72FB8CFD46AD972E8DC70F6F0EC3F767815FE65E38BE84F`.
Main executable SHA-256:
`A84886F2EFFF81627B118E1FABFC51B70E6BFAAE9EB6B8B467260D0CB970DEF8`.
The repository's complete distribution also matches its staged source across
4,256 files, including both approved empty seed workbooks. Installation retains
and verifies the previous runtime/configuration as rollback and preserves all
existing private files. Legitimate installed local profiles are verified through
runtime identity and preservation checks; the pristine deployable-package audit
correctly rejects those profiles rather than treating them as release assets.

Outside-sandbox final candidate and installed checks pass actual packaged
statement/directory/header QML in both themes and at three preview zoom levels,
with zero QML warning messages. Both actual packaged WebEngine HTML/JavaScript/PDF
checks pass with Chromium sandbox enabled; a known nonfatal DirectComposition
diagnostic is retained. Frozen startup reaches input readiness in 16.836/11.025
seconds respectively, navigates through accessible search and completes one
normal X-close/tray teardown with exit zero. Disposable read-only approved-empty
workbook hashes, checkout markers and sync state remain unchanged. No production
profile is launched and no financial records are mutated.

These automated checks do not assert foreground user acceptance or a new
motion-quality assessment. Pre-existing local documentation edits are preserved
and excluded from this task's commits. Raw evidence, runtime captures and release
manifests remain in ignored local evidence folders.
