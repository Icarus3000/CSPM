# OmniBook installed-resource repair — October 13, 2026

The user reports that invoice preview cannot find `Concept_A2.html` on
OmniBook and requests related setup repairs plus all current Git cloud changes.
The actual runtime log reproduces the error. The complete invoice templates
already exist in the installed `_internal/src/templates/invoices` directory;
the normal launcher sets `CSPM_EXECUTABLE_ROOT` to the writable profile, and the
invoice factory incorrectly used that selector for application resources.

The source is fast-forwarded from `a8a32e5` to remote-confirmed `d1d6475`, retaining
the statement preview/header and invoice/statement filtering fixes. Existing
local release-note sections are preserved and integrated with newer cloud
documentation. Exact original local notes and a Git stash remain recoverable.
The latest cloud repository push observed before this repair is
`2026-10-13T12:05:06Z` (Tuesday, October 13, 8:05:06 a.m. Toronto/EDT);
`d1d6475` was committed at 8:05:04 a.m. EDT. The API push timestamp is distinct
from the Git commit timestamp. This repair has no remote-push instruction.

`InvoiceDocumentService` defaults to immutable source/PyInstaller templates,
and its application factory uses that default. `AppPaths.resource_root()`
separates installed resources from writable settings/data/output locations while
preserving injected development fixture roots. Schema, theme, runtime docs,
approved empty-workbook recognition, version metadata and report-logo defaults
use the resource location. Custom logos remain supported. The installed recovery
action launches the existing sibling Recovery executable rather than searching
for an unbundled Python script in the writable profile.

Missing Word layouts now fail before touching an export and recommend PDF.
`Concept_A2`, B, C and Agency have HTML layouts but no equivalent shipped Word
template. Do not silently map A2 to legacy A: the older Word template's billing
fields/calculations require a separate parity repair. Existing available Word
layouts are not newly certified by this resource fix.

Sandbox-safe validation passes 156 focused installed-resource, controller,
invoice-accounting, checkout/read-only, statement/directory-filter and offscreen
QML/header checks. Seven changed Python files compile in memory, all 35 release
dependencies match the lock, and whitespace checks pass. Real packaged invoice
HTML/JavaScript/PDF, immutable-source audit, frozen startup/input/orderly exit,
installation and preservation results are recorded after the clean-source build
in private ignored `outputs/omnibook_assets_20261013/` evidence and the durable
planning ledger. No production workbook edits or motion changes are required.

Foreground acceptance remains the same reported workflow: reopen CSPM normally,
open the affected draft's preview and export PDF. Legacy-import delegate/type
warnings are separate pending UI findings; stay on the invoice acceptance gate.
