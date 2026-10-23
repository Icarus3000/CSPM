# Desktop build and data check — 2026-10-12

The user identifies this workstation as Desktop and authorizes building and
installing the complete canonical main package, retaining Desktop's own machine
identity and working replica, and checking both workbooks against the confirmed
shared folder after OneDrive synchronization. This is a workstation deployment,
not a financial reconciliation or another motion implementation.

## Source and complete installed package

The clean checkout is switched from the preserved historical production branch
to local `main`, then fast-forwarded to independently fetched/remote-verified
`466876796563d245ee0d0e6aba1f6cb61cc318b9`. Other branches and experimental
worktrees remain preserved. No runtime source is changed.

Desktop builds a fresh x64 native bridge using the governed
`scripts/build_cleanroom_native.ps1 -ValidateContracts` path. MSVC 14.50.35717,
compiler 19.50.35723.0 and Windows SDK 10.0.26100.0 are already installed.
Both native call/probe contracts and the actual ABI/null-rejection checks pass.
The rebuilt DLL's binary identity is specific to this computer/toolchain;
cross-computer native or executable binary equality is not required.

A separate ignored release environment uses official CPython 3.14.7 and all 35
exact dependencies in `requirements-release-windows.lock.txt`. The existing
development environment remains available. The PySide qmllint popup patch is
applied to the new environment; local VS Code lint paths remain no-op wrappers.

The ordinary governed builder packages both CSPM and Recovery with
`--validate --no-deploy`. Approved-template and confidentiality gates pass.
The builder preserves the prior dist package and promotes the new package
through its supported fallback after Windows denies the directory rename.
Package provenance records the exact source pin above, clean source, native
default and no candidate-profile requirement.

Installed target: `C:/Programs/CSPM/CSPM.exe`.

| Artifact | Desktop SHA-256 |
| --- | --- |
| Main executable | `D6B531E415265A44A4BDC19A58AF45BA16D30AE101F1B9EE44BE382F34F080D4` |
| Recovery executable | `85979B4820878083E6139CB1FB5E23C79355551B84AC03F428517DEB8EA3A6F9` |
| Native motion DLL | `ACC241365B71B8BD5D2F8C0F1A4912EE7BE4D6197E8F820182961734025899C8` |
| Runtime manifest | `966C77712113D4CBF41969E85EE8E933A10C8F3DAFC16682E950B3E6C2F29844` |

Dist and installed runtime match all 4,254 files / 677,639,356 bytes, excluding
preserved private data/state. The final comparison after the normal writer
session also matches. The audit compares 67 embedded project modules and the
entry point against immutable source, ignoring checkout filenames only; all
251 packaged/source assets, including 173 QML-tree files, match. Package
privacy, approved empty seeds, provenance and native ABI gates pass. The
private audit explicitly pins Desktop's locally rebuilt DLL instead of the
audit helper's historical OmniBook binary constant.

## Preservation and normal Desktop profile

The governed deployment helper first preserves and verifies the previous
installed runtime plus configuration, without copying practice datasets.
A disposable copy of that rollback reaches visible input readiness and exits
zero. Its older tray retention needs an orderly WM_QUIT sent only to its owned
GUI thread after WM_CLOSE; no process is killed. The immutable rollback stays
unchanged and remains usable. No duplicate-executable cleanup is authorized
or performed during this Desktop deployment.

Installation uses `scripts/deploy_native_motion_release.py`, verifies the
complete runtime manifest and preserves every existing private installation
file. Stale ordinary Start-menu and taskbar shortcuts previously pointed at a
nonexistent project-folder executable. Their original bytes are preserved
privately and their targets are repaired to the installed package. A second
existing taskbar shortcut already selected the correct package.

Desktop's existing writer settings already select its own separate LocalAppData
working replica and the confirmed OneDrive shared-data folder. Its stable
machine identity remains unchanged; no OmniBook identity, profile or replica is
copied. The current-main read-only schema probe reports no required migration.
Local, shared, immutable release and common-ancestor hashes agree for both
`CSPM.xlsm` and `Dockets.xlsm`, retaining governed pair identity `0E9EAFA287B6`.
OOXML ZIP integrity checks pass without changing any workbook.

The real installed normal writer session acquires the canonical checkout with
Desktop's existing identity, computer name and the exact launched PID. Startup
logs report an unchanged pair and the visible banner identifies the verified
local replica. The diagnostic's accessibility close lookup later fails; this
failed attempt is preserved. An ordinary Windows WM_CLOSE to that owned main
window completes one close animation, tray teardown and exit zero. Shutdown
reports the unchanged pair, refreshes common ancestry and removes the checkout.
Final workbook/archive and identity hashes remain unchanged; required profile
selectors/style/writer policy remain preserved. No financial command is issued.

## Validation split and evidence limits

Sandbox-safe checks: all 101 runtime Python modules compile in memory; 131
focused ownership/checkout/AP/read-only/launcher/About/native/deployment tests
pass. Native builds, contracts, ABI/dependency inspection, package source/privacy
comparison, workbook/schema/hash checks and whitespace review are safe checks.
They are executed in this unrestricted environment without opening WebEngine.

Outside-sandbox checks: historical rollback startup, actual frozen candidate and
installed startup/lifecycle/search/X-exit, the installed no-edit normal writer
session, and actual packaged WebEngine HTML/JavaScript/PDF rendering. Candidate
retry reaches input-ready in 16.238 seconds; installed reaches it in 23.918
seconds; normal writer startup reaches it in 17.510 seconds including diagnostic
preflight. Candidate and installed WebEngine each produce a verified 47,017-byte
PDF without disabling the Chromium sandbox. The nonfatal DirectComposition
interface diagnostic remains disclosed.

The first candidate lifecycle diagnostic incorrectly requires a populated
governed-source banner from exact approved empty templates. CSPM correctly
shows the empty-practice read-only banner. The failed evidence and orderly X
cleanup remain preserved; the private retry changes only this fixture
expectation and asserts exact empty-template hashes. It passes both directions,
search and orderly exit. Its two native handoffs use safe recovery; the final
installed pair completes both directions natively with restored bounds/input
intact. These functional checks do not establish new subjective smoothness or
physical multi-monitor acceptance.

OneDrive's available account diagnostic records zero pending transfer
files/bytes at 19:12:53 EDT. A fresh post-session Windows Cloud Files query at
20:07:57–58 EDT uses read-attributes-only handles and
[`CfGetPlaceholderInfo`](https://learn.microsoft.com/en-us/windows/win32/api/cfapi/nf-cfapi-cfgetplaceholderinfo).
Both shared workbooks return `CF_IN_SYNC_STATE_IN_SYNC`, all bytes validated and
zero modified bytes; their local/shared hashes still exactly match the baseline.
The governed release manifest is also in sync. Checkout remains absent, common
ancestry matches and protected hashes are unchanged. No provider state is set or
repaired. This confirms current OneDrive file-provider status and Desktop's
local/shared convergence. Authenticated server item revisions and independent
physical OmniBook workbook hashes are outside this check.

Private build, native, rollback, package, installation, shortcut, lifecycle,
WebEngine and data evidence is retained under ignored
`outputs/desktop_release_20261012/`; no raw logs, configurations or practice data
are added to Git. This handoff and task/implementation entries are documentation
after the immutable build, so they do not change the embedded runtime source pin.
