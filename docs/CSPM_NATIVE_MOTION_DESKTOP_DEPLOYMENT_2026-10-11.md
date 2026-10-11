# CSPM native motion desktop deployment handoff — 2026-10-11

Canonical repository: https://github.com/Icarus3000/CSPM.git

Promotion branch: promotion/cspm-native-motion-20261011

Exact promoted build source / desktop deployment pin:
4237e7d1f5b4aab89a016f068c1620566f5d70d8

Accepted visual runtime source:
19d030d9516ef026da158e610db432a434335966

All runtime Python, QML and native C++ are identical to the accepted checkpoint.
The promotion is based on approved primary f96880be888032ac10cd94696b5287335a817159,
preserving its business logic. Packaging/documentation changes do not change motion.
The publication follow-up contains this handoff; use the immutable build pin above
for the desktop build. Keep the handoff outside that detached build worktree.

## Prerequisites and exact build

Windows x64; Python 3.14.7; existing Visual Studio MSVC x64 C++ build tools
(OmniBook validated 14.44.35207) and Windows SDK (10.0.26100.0). No security
policy or Qt/Chromium sandbox bypass is required. The exact Python environment
is requirements-release-windows.lock.txt. Qt/PySide 6.10.3 and PyInstaller 6.22.3
are pinned there. Install dependencies in a fresh local virtual environment.

From a cloned canonical repository, fetch the promotion branch and create a
fresh detached build worktree at the full source pin. Never reset existing work.

```powershell
git fetch origin promotion/cspm-native-motion-20261011
git worktree add ../CSPM-desktop-build 4237e7d1f5b4aab89a016f068c1620566f5d70d8
Set-Location ../CSPM-desktop-build
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -c "import sys; assert sys.version_info[:3] == (3, 14, 7), sys.version"
./.venv/Scripts/python.exe -m pip install -r requirements-release-windows.lock.txt
./scripts/patch_qmllint_popup.ps1
./scripts/build_cleanroom_native.ps1 -ValidateContracts
./.venv/Scripts/python.exe -m compileall -q src/python
./.venv/Scripts/python.exe -m pytest tests/test_auto_backup_timer_contract.py tests/test_native_motion_runtime.py tests/test_native_motion_diagnostics.py tests/test_native_candidate_safety.py tests/test_native_motion_deployment.py
./.venv/Scripts/python.exe scripts/build_release.py --validate --no-deploy
```

Use the ordinary governed builder command above. The native-candidate option
requires an isolated diagnostic profile and must not be used for main installation.
The runnable package is dist/CSPM/CSPM.exe; inspect
`dist/CSPM/_internal/release-provenance.json` for its source SHA, native DLL hash
and ordinary native-default policy.

If the Python version assertion fails, select an installed Python 3.14.7 interpreter
and recreate only this new virtual environment before installing dependencies.

OmniBook reused the verified visually accepted native DLL after independently
passing a fresh native build and both call/probe contracts. Accepted DLL SHA-256:
D60D55E3E72F2E8D928C363EE7AE15FD1DB5D448B81E31B5FB168A7303EF6578.
The fresh OmniBook native rebuild hash differed despite identical source. PE/link
and PyInstaller outputs are not promised byte-identical across computers/builds.
The desktop must build locally and validate its own resulting hashes and ABI;
do not copy the OmniBook executable or substitute a newer source variant.

Verified installed OmniBook EXE SHA-256:
E3A86FF11A215013B002DE6E98C3D01161043E67A3F2063097DA35F3D22EE622.
Its installed runtime manifest SHA-256 is
BFBBC63F4B116844DC0B9A10343C4A028D45CB10BB31EB644D37D4C6B56E7CE0
(4,250 files; 677,597,232 bytes, excluding private runtime state/data).
These hashes identify OmniBook artifacts; record the desktop's own local hashes.

## Preserve, validate, install and restore

Close CSPM and confirm no process uses either package. Before any replacement,
create an immutable rollback using the helper. Choose a new local audit folder
and a new rollback location. Review the captured manifest, preserve the current
shortcut and configuration, then launch the rollback EXE with an independently
isolated test profile and approved empty templates. Do not copy production data
into rollback. The helper refuses an existing rollback directory.

```powershell
./.venv/Scripts/python.exe scripts/deploy_native_motion_release.py --snapshot 'C:/Programs/CSPM' --rollback 'C:/Programs/CSPM-Rollback/before-native-motion-desktop' --report '../desktop-audit/rollback.json'
```

For the rollback launch, use a fresh dedicated PowerShell terminal, change directory
to the detached CSPM-desktop-build worktree, and use a new audit subfolder.
Copy the preserved runtime into that subfolder so ordinary draft-session
writes cannot alter the immutable rollback. The following uses only approved empty
templates. Exit CSPM through its tray menu, then close this terminal so its temporary
environment cannot affect normal launches.

```powershell
$ErrorActionPreference = 'Stop'
$smokeRoot = [IO.Path]::GetFullPath((Join-Path -Path (Get-Location).Path -ChildPath '../desktop-audit/rollback-smoke'))
if (Test-Path -LiteralPath $smokeRoot) { throw 'Choose a new smoke folder.' }
New-Item -ItemType Directory -Path $smokeRoot | Out-Null
Copy-Item -LiteralPath 'C:/Programs/CSPM-Rollback/before-native-motion-desktop/package' -Destination "$smokeRoot/package" -Recurse
foreach ($part in @('local','roaming','temp','working','working/data','working/logs','working/exports')) {
    New-Item -ItemType Directory -Path "$smokeRoot/$part" -Force | Out-Null
}
Copy-Item -LiteralPath 'src/templates/CSPM.xlsm','src/templates/Dockets.xlsm' -Destination "$smokeRoot/working/data"
$settings = @{ appStyle='Professional'; localDataDir="$smokeRoot/working/data"; masterDataDir=''; runAtStartup=$false; autoBackupMinutes=0; autoBackupIntervalMins=0 }
[IO.File]::WriteAllText("$smokeRoot/working/user_settings.json", ($settings | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
$env:LOCALAPPDATA="$smokeRoot/local"
$env:APPDATA="$smokeRoot/roaming"
$env:TEMP="$smokeRoot/temp"
$env:TMP=$env:TEMP
$env:CSPM_RUNTIME_DIR="$smokeRoot/working"
$env:CSPM_DATA_DIR="$smokeRoot/working"
$env:CSPM_EXECUTABLE_ROOT="$smokeRoot/working"
$env:CSPM_LOG_DIR="$smokeRoot/working/logs"
$env:CSPM_EXPORT_DIR="$smokeRoot/working/exports"
$env:CSPM_MACHINE_ID_FILE="$smokeRoot/working/smoke-machine.json"
Start-Process -FilePath "$smokeRoot/package/CSPM.exe" -WorkingDirectory "$smokeRoot/package" -WindowStyle Normal -Wait
```

Use the same independent-copy procedure for the newly built package, with a different
smoke folder and its package as the Copy-Item source. Keep all smoke configuration
and runtime artifacts outside the deployable release; validate the clean package
with the deployment helper before installation.

Run focused package smokes on independent copies before install. Only proceed
when rollback launch and material regression/privacy checks pass. Retain the
computer's existing governed data/profile workflow and normal shortcut.

```powershell
./.venv/Scripts/python.exe scripts/deploy_native_motion_release.py --install dist/CSPM --target 'C:/Programs/CSPM' --rollback 'C:/Programs/CSPM-Rollback/before-native-motion-desktop' --report '../desktop-audit/install.json'
```

One-command restoration, with CSPM closed:

```powershell
./.venv/Scripts/python.exe scripts/deploy_native_motion_release.py --restore 'C:/Programs/CSPM-Rollback/before-native-motion-desktop' --target 'C:/Programs/CSPM' --report '../desktop-audit/restore.json'
```

Restoration verifies the preserved package, first preserves the newer installation
in a fresh sibling rollback directory, restores code through the governed helper,
retains existing workbooks/settings, and restores the saved motion preference.
The original rollback package is never overwritten.

## Engine selection and focused checks

Native is default when the local motion preference is absent/invalid. Low-performance
mode also uses immediate transitions instead of native animation. Close CSPM,
then use CSPM.exe --set-motion-engine native or --set-motion-engine legacy, and
restart. CSPM.exe --motion-settings gives a chooser. The preference is independent
of financial settings, at the launch profile's LOCALAPPDATA/CSPM-Motion/motion.json.
Use the same LOCALAPPDATA as the normal shortcut. Windows reduced-motion behavior
remains authoritative. Native pre-motion readiness failure may choose legacy for
that operation; a post-transfer failure recovers the requested live state safely.
Diagnostics distinguish native completion, legacy fallback and safe rejection.
Ordinary launches have no intrusive motion diagnostic UI.

Focused desktop smokes: ordinary startup/opening, normal close, maximize/restore,
five repeated pairs, explicit legacy selection, bridge-unavailable/pre-motion
fallback, reduced selection/system policy, minimize/taskbar return, focus/search
input/navigation, populated workspace read on an independent copy, packaged
WebEngine synthetic HTML/JavaScript/PDF where supported, exact production path
verification and unchanged authoritative hashes. Do not run broad historical
qualification. Classify each outcome as accepted native behavior, safe legacy
fallback, known limitation, promotion regression or environment limitation.
Correct a material promotion regression before replacement.

## Data boundaries and limitations

No reconciliation, financial migration, invoice/receivable/ledger/payment edits,
record deletion, or application of the 119 pre-existing findings is authorized.
Before a first authoritative launch inspect schema/automatic write requirements;
stop before any newly required reconciliation/migration. Existing sequential
checkout/hash/conflict/release safeguards remain. Never claim server freshness.

No ordinary production configuration was recovered on OmniBook. Its normal CSPM
shortcut launches the standard empty/setup workflow; the separate existing development
shortcut and isolated profile are preserved. Promotion does not invent a production
data path. Populated tests use protected original derivatives with masterDataDir
empty and cloud writes disabled. Do not silently repoint either computer to
authoritative data. The unchanged ordinary startup can call ensure_schema; inspect
schema_requires_migration read-only before an authoritative launch and stop if a
workbook is missing, unsupported, or requires migration.

No private dataset is added by promotion; data/, private deliverables and generated
reports are excluded from the promoted tracked tree/package. Governed empty
source templates are retained. Earlier Git history/branches contained workbook
artifacts and are preserved unchanged; this is not a claim that prior history is
dataset-free. All six original dockets remain intact where independently verified.

The final OmniBook audit confirms the governed authoritative pair and protected
originals unchanged. A separate historical shared Dockets file was saved during
the final checks and differs from its preserved snapshot; Cory confirmed editing
that workbook at the reported time. Both versions are retained privately and no overwrite/reconciliation
was attempted. Do not treat that historical change as accepted financial data or
claim that every shared file remained unchanged throughout promotion.

Known limits: intermittent target-readiness/GPU-transfer deadline misses can
recover to the live target; acceptance does not certify every historical gate.
Physical mixed-DPI/multi-monitor behavior remains untested on this OmniBook.
Historical unit/type/QML gate failures and the 119 financial findings remain open.
Normal title-bar close preserves the existing tray session; use the tray Exit action
to finish it before deployment or engine switching. Focused automated smokes verified
the close animation and then gracefully closed owned Qt windows, with exit zero.

OmniBook promotion validation passes compilation, 146 focused tests, both native
contracts, governed packaging, isolated prior-runtime rollback startup, ordinary
startup/close, five native pairs (7 native completions, 3 safe recoveries), legacy
and missing-bridge fallbacks, actual source-workarea readiness fallback, immediate
reduced behavior, populated read/input/navigation, minimize/taskbar return, and
packaged WebEngine HTML/JavaScript/PDF. The installed final pair has one native
completion and one safe recovery, with exact state/input/close and exit zero.
Initial harness API/control-lookup/occlusion failures are retained and disclosed
in [the promotion record](CSPM_NATIVE_MOTION_PROMOTION_2026-10-11.md); no broad
historical qualification is repeated.
