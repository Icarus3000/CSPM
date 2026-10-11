# CSPM accepted native motion promotion — 2026-10-11

Cory visually accepted the repaired packaged native maximize/restore candidate
for current use and authorized its reversible promotion to the main OmniBook
application. This closes the visual acceptance request for this exact candidate.
It does not certify every historical diagnostic gate, eliminate every native
readiness failure, or authorize financial reconciliation.

## Source and executable identity

Canonical repository: https://github.com/Icarus3000/CSPM.git

Promotion branch: `promotion/cspm-native-motion-20261011`.

| Identity | Exact value |
| --- | --- |
| Visually accepted runtime source | `19d030d9516ef026da158e610db432a434335966` |
| Approved primary baseline | `f96880be888032ac10cd94696b5287335a817159` |
| Bounded promoted build source | `4237e7d1f5b4aab89a016f068c1620566f5d70d8` |
| Accepted candidate EXE SHA-256 | `8C46F7CD0065A94145FE384A77547B21BEF8AF5DA946D6BF01938E6C91C3A5A9` |
| Ordinary promoted package EXE SHA-256 | `E3A86FF11A215013B002DE6E98C3D01161043E67A3F2063097DA35F3D22EE622` |
| Accepted and ordinary packaged native DLL SHA-256 | `D60D55E3E72F2E8D928C363EE7AE15FD1DB5D448B81E31B5FB168A7303EF6578` |
| Immutable deployment SHA published on the promotion branch | `4237e7d1f5b4aab89a016f068c1620566f5d70d8` |

The promotion is bounded on the approved primary line; it is not a whole-branch
experimental merge. All 66 runtime Python modules, all 171 QML-tree files and
the native C++ source match the accepted runtime. Embedded Python code comparison
ignores only checkout filenames; committed source comparison normalizes checkout
line endings. Primary business functionality remains preserved. Later diagnostic
work and the original experimental branches remain separately recoverable.

The ordinary package differs from the accepted candidate in deployment packaging,
not animation implementation. It omits the diagnostic candidate marker and
private profile sidecar, retains approved empty templates and required runtime
assets, and embeds `release-provenance.json` with the exact build source and DLL
hash. Historical evidence outputs, private datasets and disposable fixtures are
excluded from ordinary runtime packaging. Historical native exports remain in
the exact accepted DLL but are not selected or called by ordinary motion dispatch.
Runtime documentation required by project snapshots remains available.

A fresh governed native compilation and both native call/probe contracts pass.
Its DLL SHA-256 is
`B30089646F4B0BC0C22313C597F6E762C43163D471914850E4FEBAE0538D03D1`.
That binary is not byte-identical to the accepted DLL despite identical source.
The OmniBook package therefore preserves the independently verified accepted
DLL. Native timing, easing, readiness limits and ownership contracts are unchanged.
Cross-machine PE/PyInstaller byte identity is not promised; the desktop must
build the exact pinned source locally and record its own artifact hashes and ABI
results. The desktop must not copy the OmniBook executable blindly.

## Motion policy and immediate fallback

Native motion is the ordinary default when the local preference is absent or
invalid. The stale disabled-backup flag/zero-interval timer repair is included.
The legacy implementation remains functional. Windows reduced-motion preference
remains authoritative. Before motion, failed native readiness may select legacy
for that operation. After visibility transfer or started motion, a failure
recovers directly to the requested live state and input; it is not counted as
native completion or a new legacy animation. Diagnostics retain these distinctions.
Ordinary launches do not display intrusive motion diagnostic UI.

Close CSPM, select an engine, and relaunch using the normal shortcut:

```powershell
& 'C:/Programs/CSPM/CSPM.exe' --set-motion-engine legacy
```

Use `--set-motion-engine native` to return to native, or
`--set-motion-engine reduced` for immediate motion. `--motion-settings` opens the
supported chooser. The preference is independent of workbook configuration at
the normal launch profile's `LOCALAPPDATA/CSPM-Motion/motion.json`.

Installed main engine selection is **native**, explicitly selected through the
installed executable's supported command and verified in the normal profile.
The read-only Windows client-area-animation query reports reduced motion off.

## Rollback preservation

Preserved prior installation:
`C:/Programs/CSPM-Rollback/before-native-motion-20261011`.

- Prior EXE SHA-256:
  `3F4B8A450AF5D02E9780ECC1E22D1560DDF689E926188CCE4459144D3BFE4527`.
- Preserved runtime manifest SHA-256:
  `CAEE998EDDC4C0EDF86F7E71F3C4A1E3C25F3122976E8A60FC7D924FBC6326AC`
  (4,294 runtime files; the manifest digest is distinct from the JSON file hash).
- Prior configuration and motion preference state are preserved separately.
  No private dataset was copied into the rollback package.
- Isolated rollback launch passes startup and graceful shutdown with exit 0;
  no forced termination. The initial failed harness result remains preserved.

With CSPM closed, restore through the governed helper from the pinned repository:

```powershell
./.venv/Scripts/python.exe scripts/deploy_native_motion_release.py --restore 'C:/Programs/CSPM-Rollback/before-native-motion-20261011' --target 'C:/Programs/CSPM' --report '../cspm-rollback-audit/restore.json'
```

The helper verifies the preserved package, preserves the newer installation in
a fresh sibling rollback before restoring code, retains current workbooks and
settings, and restores the saved motion preference. The original rollback is
never overwritten. The helper and restoration wrapper are verified; main installation
matches its clean runtime manifest and the prior rollback remains hash-verified.

On OmniBook, the prepared one-action wrapper is
`C:/Programs/CSPM-Rollback/Restore-Main-CSPM.ps1`. With CSPM fully exited, run:

```powershell
& 'C:/Programs/CSPM-Rollback/Restore-Main-CSPM.ps1'
```

It uses the preserved local build environment and helper, creates a new private
report for each invocation, and applies no execution-policy bypass. Its syntax
and the helper's ten safety tests pass; a destructive restore is not performed
as part of promotion verification.

## Focused validation

Static checks below are sandbox-safe. Desktop package checks run on the
unrestricted Windows desktop with real Qt; no Qt/Chromium sandbox is disabled.
The focused promotion scope does not reopen broad historical qualification.

| Check | Result and classification |
| --- | --- |
| Focused runtime and deployment tests | 136 focused tests plus 10 deployment tests pass |
| Python compilation | Pass |
| Governed native compilation, DLL load and contracts | Pass; both native contracts pass; accepted packaged DLL retained |
| Ordinary packaging governance/privacy smoke | Pass; approved templates and required assets included; private data excluded |
| Rollback startup and normal close lifecycle | Pass; exit 0 without termination; existing tray behavior disclosed below |
| Ordinary native five maximize/restore pairs | 7 native completions and 3 safely recovered post-transfer failures; exact endpoints, visible/enabled live input and overlay retirement pass |
| Explicit legacy selection | Two completed transitions, no watchdog; safe legacy fallback |
| Native selected with bridge unavailable | Two explicit safe legacy fallbacks, both complete |
| Actual native pre-motion source-readiness rejection | Pass; source outside monitor work area selects explicit legacy, followed by a native restore |
| Reduced motion | Pass; two immediate reduced transitions, exact endpoints/input/overlay retirement, normal close and exit 0 |
| Opening, minimize/taskbar return and post-motion input/navigation | Pass in native, legacy, missing-bridge and readiness runs; reduced run covers opening/input/navigation/close |
| Representative populated read/navigation | Pass using independent protected derivatives; original and working workbook hashes unchanged |
| Packaged WebEngine synthetic HTML/JavaScript/PDF | Pass; actual archived package modules and native Qt/helper/resources, matching local Python host, valid 37,208-byte PDF; separate frozen application startup verified |
| Main installation, shortcut and installed startup | Pass; ordinary main installed, normal Desktop/Start Menu shortcuts verified, startup 10.805 s; one native completion and one safely recovered post-transfer miss; endpoints/input/navigation/close/exit 0 pass |
| Final staged privacy review and remote preservation | Bounded source scan passes; publication follow-up contains only this report, desktop handoff and task/implementation closeout; complete remote head is verified and recorded in the workstation dashboard after push |

The preserved ordinary startup behavior restores `keepTrayAlive=true`. Normal
title-bar Close animates and hides the main window while retaining the tray
session. The isolated harness verifies this close animation, then sends ordinary
`WM_CLOSE` only to its owned Qt windows to end the session with exit 0. This is
graceful session shutdown, not forced process termination or a claim that
title-bar Close independently exits the event loop. No animation change was
made to alter that existing behavior.

Initial reduced physical-click/minimize probes failed a timeout, an occluded click,
and an unavailable accessible minimize control. They remain preserved as harness/
environment limitations. The focused reduced replay uses existing accessible
maximize/restore/close controls and excludes minimize, which passed independently
in the other engine runs. The initial WebEngine helper used the wrong Python API;
the corrected package-assets smoke passes. No accepted runtime code changed.
The first installed replay also encountered an occluded physical minimize click
after two safely recovered native deadline misses. The final installed replay
uses accessible maximize/restore/close, passes, and leaves the separately verified
package minimize/taskbar results intact.

## Data safety and production profile

No interrupted reconciliation was applied by this promotion. The governed
authoritative pair and protected original/candidate file hashes remain unchanged;
all six independently checked original dockets remain intact, and
the retained content checks cover 18 workbook XML parts. No invoice, receivable,
ledger, payment, linked balance or old-credit correction was applied. None of
the 119 pre-existing findings was acted on. Original records remain unresolved
where they were unresolved before promotion. Server freshness is unverified.

The final recheck detected a separate historical shared Dockets workbook saved
at 2026-10-11 18:23:55 UTC, after all nine files passed at 18:21:28 UTC. Its
container and 53 resolved cell values/formulas differ from the preserved historical
snapshot. Cory subsequently confirmed editing that historical workbook at the
reported time. Both historical versions are preserved privately. The other eight
proof files and all 18 docket XML checks still match.
No promotion process launched against that historical shared path, no cloud master
folder was configured in the tests, and no authoritative workbook write or restore
was performed. This exception prevents a claim that every shared file stayed
unchanged throughout the session. The save is confirmed user activity, not a
promotion write; it does not authorize reconciliation, validate the changed
financial content, or permit a blind overwrite of the newly saved file.

The recovered prior accepted installation used its isolated development profile
with approved empty templates. A saved ordinary production configuration was
not found on this OmniBook. The normal shortcut therefore uses the standard
ordinary empty/setup workflow; the separate development shortcut is preserved.
Promotion must not silently repoint either profile to authoritative records.
Populated validation uses independent protected derivatives, an empty master
folder and cloud publishing disabled. No first authoritative launch is claimed.
Any newly required automatic reconciliation or schema migration must be assessed
before a first authoritative launch and stopped before a new write.

Private datasets are excluded from the promoted tracked tree and package;
approved empty templates are retained. Prior branches/history contained workbook
artifacts and remain untouched. This is not a claim that all historical Git
objects are dataset-free. Private rows, logs and machine-specific private paths
are not published in this promotion report.

## Remaining limits and desktop continuation

Intermittent native target-readiness/GPU-transfer deadline misses remain known
limitations with safe live-state recovery. Acceptance does not establish that
every historical native-motion failure is eliminated. Physical mixed-DPI and
multi-monitor scenarios remain untested on this OmniBook. Historical unit/type/
QML gate failures and the 119 financial findings remain open.

The committed desktop continuation is
[CSPM_NATIVE_MOTION_DESKTOP_DEPLOYMENT_2026-10-11.md](CSPM_NATIVE_MOTION_DESKTOP_DEPLOYMENT_2026-10-11.md).
It gives the canonical repository, immutable build pin, dependency lock, native
prerequisites, governed build/package commands, installation and rollback steps,
focused smokes, data boundaries and the requirement to retain legacy fallback.

Final local installation status: **NATIVE-MOTION CSPM PROMOTED AS MAIN OMNIBOOK BUILD**
at `C:/Programs/CSPM/CSPM.exe`. The installed runtime contains 4,250 files,
677,597,232 bytes, with canonical runtime manifest SHA-256
`BFBBC63F4B116844DC0B9A10343C4A028D45CB10BB31EB644D37D4C6B56E7CE0`.
An independent installed audit verifies every runtime record and unchanged private
files. Existing development launcher/shortcut and separate profiles remain intact.

Exact remote desktop deployment pin:
`4237e7d1f5b4aab89a016f068c1620566f5d70d8` on
`promotion/cspm-native-motion-20261011`. The docs-only publication follow-up does
not alter packaged runtime; its complete branch-head SHA is recorded separately
in the workstation dashboard after live remote verification, avoiding a
self-referential commit identifier in this document.

Remote main remains `562e24d5a565198a630b2a57984012b3051e53e3`; approved primary
remains `f96880be888032ac10cd94696b5287335a817159`. The experimental branch,
qualification reference, original worktrees, local accepted checkpoint and prior
rollback references are retained. No force push, whole-branch merge, history
rewrite or source-work deletion is performed.
