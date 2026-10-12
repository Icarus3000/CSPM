# Governed production-write activation gate

Cory requests ordinary daily docketing/billing through the installed main,
subject to authoritative freshness, preservation, exclusive ownership,
synthetic save/publication/release verification and retained read-only sessions.
This request authorizes normal operation after the gates; it does not authorize
reconciliation, applying the 119 findings, or changing financial records during
verification. Animation development is outside this task.

## Installed main and read-only controls

At the initial activation audit, canonical clean source and live remote main were
`528e1cbbe646b02d76f7a5ff261450b90301b49c`.
Installed main is `C:/Programs/CSPM/CSPM.exe`, SHA-256
`AF792032D7DA0007A865648B8209066853B843F3A0C2C66854377AD1A0E23271`;
native DLL SHA-256 remains
`D60D55E3E72F2E8D928C363EE7AE15FD1DB5D448B81E31B5FB168A7303EF6578`.
The complete immutable runtime audit passes. Accepted animation, lifecycle,
normal launcher, installation and all existing worktrees remain preserved.

The one normal Start-menu entry uses the private verification launcher. It
requires read-only deployment/profile policy, supplies
`CSPM_VERIFY_DATA_READ_ONLY=1` and `--verify-data-read-only`, and holds Windows
read handles denying write/delete on the separate local replica during the
child session. `main.py` latches CLI/environment verification before repository
construction; `AppController` also latches saved `readOnlyVerification=true`.
Repository/AP/legacy save boundaries and `SyncService` consequently refuse
workbook writes, migration, writer checkout, synchronization and publication.
A false settings value cannot undo an explicit process-wide verification latch.
Thus removing one flag alone does not create a supported writable session.

## Authoritative identity and freshness

The recovered private selectors identify the existing governed shared source
and a separate local replica. Their complete SHA-256 pair and archived release
match identity `0E9EAFA287B6`, release
`20261006T222837Z_8c6f1469_7cd1b27b`:

- CSPM: `8E1D489816B7939553E74DD5D54F86913AAF21C434E369F65CA8395C8EA4DC5A`
- Dockets: `350CCB492C8030635983EEE96FFDBFA40788236C127E82EDA9AD74C6E24E4D8A`

All 59 locally available governed manifests are reviewed, with no newer locally
declared release. Schema migration is unnecessary. Population remains 151
clients, 228 matters, 830 time entries, 207 invoice rows and 190 receivables.
The last canonical docket date is October 5. Eighteen XML-row checks confirm six
original dockets intact. No checkout/recovery/Excel marker is present. Normal
sync state is absent; an identical pair permits the supported first checkout to
establish the hash common ancestor without inventing timestamps or overwriting
divergent data. Old normal settings describe empty setup, not a recovered
authoritative writer profile.

This is a locally verified identity, not current server freshness. The correctly
mapped OneDrive account has an October 11 account-wide diagnostic snapshot;
its zero pending counts, placeholder metadata and running processes do not
identify today's server release manifests or pair revisions/hashes. Current
authenticated cloud access is required to enumerate the governed release folder
and verify server bytes against its manifest and the local pair. The available
SharePoint plugin is unconnected and exposes no original-file download contract
in this session. Connecting it alone is therefore not a qualified byte-level
verification mechanism. No cloud credentials/tokens are read from local caches.
No current server revision is inferred from filesystem times.

The supported alternative is Microsoft Graph PowerShell Authentication, saved
privately from the PowerShell Gallery at version `2.41.1`. Microsoft documents
delegated `Files.Read` for folder enumeration and original `driveItem/content`
downloads. A private acquisition worker uses `Connect-MgGraph` with the existing
LPN account/tenant pins, `LoginHint`, `ContextScope Process` and read-only scopes.
Authentication takes place in Microsoft's native account picker/browser sign-in
interface. Passwords, tokens and preauthenticated download URLs are never sent
to chat or written to audit reports. The worker validates the authenticated
account/tenant and Business drive mapping before any acquisition. Current
manifests and original canonical/archive XLSM streams go to a new private
evidence directory, with before/after item-version and release-list checks.
Neither cloud files nor production replicas are overwritten.

Official contracts: [authentication](https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.authentication/connect-mggraph?view=graph-powershell-1.0),
[original content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0),
[folder enumeration](https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0).

## Preservation and synthetic workflow evidence

Brief source deny-write/delete protection covers a new byte-exact original
pair/manifest snapshot. The current complete main runtime and private
configuration are preserved as a hash-verified nonlaunchable rollback archive;
each immutable runtime manifest record is checked. No extra launchable CSPM
application executable is introduced. Historical rollback evidence remains.

At exact main source, a separate populated synthetic pair passes exclusive
writer A acquisition, writer B refusal, fabricated docket and billing save/
reopen, invoice/A/R/ledger consistency, draining an accepted queued save before
ordinary `AppController.shutdown`, complete immutable paired release/manifest
hash verification, local canonical publication, marker removal, post-release
write refusal, B refresh/common-ancestor/record verification and no-change release.
Separate read-only process checks refuse write/checkout/publication/setup and
preserve workbook/cache/state/foreign marker hashes. These tests use a private
isolated local folder only. They do not prove OneDrive upload or another physical
computer's arrival. Two early probe field-constant errors remain failed evidence.

The safety audit reproduces two existing issues using only synthetic data:

- A legitimate small populated CSPM workbook below 50 KB was classified as an
  empty seed by byte size. Publication safely refuses with conflict and releases
  the marker; saved local records remain preserved. A later checkout can replace
  that local package with the shared template while retaining a recovery copy.
- AP repository mutation checked explicit verification mode but omitted the
  shared writer lease. A second synthetic session denied checkout could still
  create/save an AP bill locally before a later guarded operation refused.

An isolated repair branch addresses seed recognition through approved-template
identity/payload verification of both existing workbooks and AP writes through
the same writer guard used
by the ordinary repository, checked at mutation entry and again immediately
before each physical save. Focused regression and genuine small-template
workflow tests validate the candidate without altering production main or data.
Forty-nine AP/verification checks and 40 checkout/verification regressions
pass, including initial empty checkout/no-change close and preservation of an
unknown seed difference after recorded ancestry. Approved or missing CSPM with
populated Dockets is refused without changing either pair. Actual fabricated small-template
docket/billing publication passes without workbook padding. An actual two-profile
AP probe confirms the blocked writer and post-release writer cannot change bytes;
the owner saves, reopens and publishes a complete hash-verified pair. Initial
test-harness isolation failures remain preserved and excluded from passing results.
These are safe local tests. Real WebEngine and motion checks from the unchanged
installed checkpoint remain historical evidence; neither is rerun for this task.
The exact clean writer-safety commit is
`7f6e4bbd2917ac7558e55c5c5bf9dbc9f4e1d6ff`. A second narrow review passes 72 unique
focused offscreen tests and in-memory compilation of all 101 runtime Python
modules. All runtime AP construction paths are reviewed; the remaining unguarded
construction reads payment history only. The complete nine-file intended delta
passes the exact-index privacy/credential guard. Canonical main integrates this
commit by ordinary fast-forward, preserving its history. Live remote publication
and the final source pin are recorded privately after publication; installed
main remains the preserved `528e1cb` package while authentication is pending.
The fixes must be cleanly packaged and deployed before ordinary writes rely on
them. Accepted motion/native/QML code remains unchanged. No animation development
or installation change is performed as part of source publication.

## Activation boundary and remaining action

Production normal writes are not enabled at this gate. After current server
identity/freshness is proved and the writer-safety candidate is deployed, preserve
the current private verification profile/launcher independently, retain the
stable machine identity, use supported private shared/local selectors and a
separate writable local replica, and remove verification-specific CLI/environment/
OS handles from the writable process only. Keep a distinct verification launch
policy. Do not clear the shared source selector or fall back to an ungoverned
local-only session. The ordinary `SyncService` must acquire its own exclusive
marker, compare recorded pair hashes, drain accepted saves, publish a verified
complete release, and release the marker. Re-check conflicts at each save.

The 119 findings remain unchanged. Routine checkout/publication does not invoke
the historical financial reconciliation gate; synthetic routine-workflow proof
does not resolve or accept those findings. Never combine newer historical
workbooks or alter records as part of activation. Desktop propagation remains
untested and requires separate participation on that computer.

The single external prerequisite is authenticated access to the current governed
OneDrive/SharePoint server folder/release evidence. The actionable interface is
the Microsoft Graph PowerShell sign-in dialog initiated by the private worker;
the user completes sign-in using the existing LPN account. This replaces the
earlier unqualified SharePoint-plugin suggestion. After authentication, compare
the current server manifest, original pair hashes and stable item versions with
the local governed pair. A discrepancy preserves both copies and blocks
activation; it does not trigger overwrite, merge or financial reconciliation.
Then build/deploy the clean published writer fixes, retain the independent
read-only verification command, configure the supported normal writer profile,
and verify no-edit exclusive checkout/orderly close. Keep one normal Start-menu
entry. Synthetic save/publication proof remains separate from production upload
and physical desktop propagation. Operational status, source publication,
runtime archive and evidence remain outside Git in the workstation
production-activation evidence and dashboard.
