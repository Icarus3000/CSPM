# CSPM new-computer continuation — 2026-10-09

This is a preservation-only closeout. No feature implementation, animation
experiment, package, installation, merge, rebase, force push, deletion or stash
application belongs to this audit. The clean-room candidate remains
**UNQUALIFIED and NOT INSTALLED**. Production retains its accepted default.

## Canonical remote and exact development checkpoints

Canonical fetch/push remote: `https://github.com/Icarus3000/CSPM.git` (`origin`).
Authenticated Git access to that repository is required on the new computer.

| Branch | Full remotely verified commit | Purpose |
| --- | --- | --- |
| `fix/invoice-billing-client-correction-20260926` | `f96880be888032ac10cd94696b5287335a817159` | Primary development/production reference; preserves the October 3 diagnostic and speed handoffs. |
| `experiment/clean-room-fluid-maximize-restore` | `d4289aa5cc37d3f4b4ea5086c9a8380d08e5a1b5` | Clean-room native motion work, latest learning record, sanitized reports and preservation tooling. |
| `main` | `562e24d5a565198a630b2a57984012b3051e53e3` | Existing main branch; not the latest motion work. |
| `wip/preserve-stash-visual-fx-handoff` | `d9bd73c84ff0ef51dcf7202a247c67f771061884` | Historical continuity branch; upstream associated during closeout. |

The archival `docs/new-computer-closeout-20261009` branch contains this document
and derives from the exact experimental checkpoint above. It is a handoff
snapshot, not another development direction. Keeping the document on that
separate branch lets it state final development SHAs without self-reference or
merging production and experiment. Its own immutable SHA is obtained from
`git ls-remote --heads origin docs/new-computer-closeout-20261009` and recorded
in the final closeout response. Future remote advancement does not invalidate
the exact audit checkpoints above.

The experimental checkpoint includes the original reported
`3c41aafa1aac3477297fab909cfa73c019c66ffc` as an ancestor. That original report
checkpoint was already live-remote verified before this closeout.

## Current objective and first continuation assignment

Reliable collector-free cold Productivity restore readiness is still blocked.
The October 8 same-source/DLL collector-free control misses the unchanged
**240 ms target-transfer deadline on its first restore**, completes zero
directions and has no accepted QML input witness after rejection. Endpoint
metadata at 351.052 ms has motion 1.0/content 0.0 and no ready target. The fixture
returns enabled/interactive flags and closes normally; that is not input or
continuous-motion qualification. Exact presentation-slot/deletion trace is
absent in this collector-free control and must not be inferred.

The three original large Home source comparisons each fail by **554 pixels**
among 1,464,384 compared pixels, in shadow/margin bounds `[865,914,913,928]`
intersecting the taskbar strip. The separate 1,550 × 850 work-area-contained
success does not erase the earlier 1,550 × 900 failure or establish its cause.

Instrumented moving controls conserve 17 executed directions, 119 fresh passes,
99 exact comparisons, three failed comparisons and 17 accepted QML input pairs.
All 361 recorded slot waits return `WAIT_OBJECT_0` within 100 ms, maximum
54.3261 ms. Their success does not establish the historical wait failure's cause,
continuous visible handoff, physical input-to-photon timing or the requested
threefold speed gain. Instrumented GUI post-start receipts and native deadline
boundaries remain distinct.

The first recommended assignment is **recover and verify the experimental
checkpoint/environment, then diagnose only collector-free populated Productivity
restore readiness without changing the 350/240/100 ms contracts**. Read logs
before diagnosis. Preserve all failed controls and the existing workspace,
full-client pixels, fixed title/glyph mapping and production defaults. Do not
start another visual state machine. Uninterrupted motion, native reduced/failure
recovery, physical input, lifecycle/mixed-DPI and Cory's real-app P0 acceptance
remain open. No package/install follows until qualification and authorization.

No exact AI model or reasoning level is specified by the repository or this
closeout request. Do not invent a mandatory model requirement. The continuation
requires careful native/Qt reasoning; any later owner-specified model/level wins.

## Required starting folder and recovery steps

Use a new project directory on the work/project drive. The example uses `Y:`;
substitute the new computer's project drive if its mapping differs. Begin in the
repository root, never `src`, an installed-package folder or a disposable mirror.
These commands retrieve source and handoff only; they do not launch CSPM.

```powershell
New-Item -ItemType Directory -Path Y:\Projects -Force | Out-Null
Set-Location Y:\Projects
git clone --branch docs/new-computer-closeout-20261009 https://github.com/Icarus3000/CSPM.git __CSPM
Set-Location Y:\Projects\__CSPM
git fetch origin
Get-Content docs/CSPM_NEW_COMPUTER_CONTINUATION_2026-10-09.md
git switch --create experiment/clean-room-fluid-maximize-restore --track origin/experiment/clean-room-fluid-maximize-restore
git rev-parse HEAD
git ls-remote --heads origin experiment/clean-room-fluid-maximize-restore
git merge-base --is-ancestor d4289aa5cc37d3f4b4ea5086c9a8380d08e5a1b5 HEAD
git status --short --branch
```

If the branch exists already, use `git switch` without `--create`. If origin has
advanced, inspect that descendant; do not reset, merge or overwrite local work.
Read required startup files in this order: `implementation_plan.md`, `task.md`,
`implementation.md`, `docs/CSPM_Option_3_Interface_Rebuild_Brief.md`; then
`docs/VISUAL_FX_AUDIT_AND_HANDOFF_2026-08-20.md` and the current learning/moving
reports. The archival document remains readable with:

```powershell
git show origin/docs/new-computer-closeout-20261009:docs/CSPM_NEW_COMPUTER_CONTINUATION_2026-10-09.md
```

For a separate primary checkout later, without merging branches:

```powershell
git worktree add --track -b fix/invoice-billing-client-correction-20260926 ..\__CSPM_primary origin/fix/invoice-billing-client-correction-20260926
```

## Ignored dependencies and private-data boundary

A clone supplies code, scripts, governed templates and sanitized evidence. It
does **not** supply the old computer's private practice data, settings, caches,
raw captures, local stashes, installed package or native DLLs. The current native
fixture reads local CSPM settings and `CSPM.xlsm`/`Dockets.xlsm` before copying
them into a disposable profile. A fresh clone alone cannot run that fixture.
Use the governed single-writer shared-data setup/check-out flow for private
data, with explicit authorization for any data provisioning; never treat Git
starter templates as the user's current production workbooks. Do not commit
private data, session state, settings, screenshot frames or runtime logs.

The measured environment was Windows, Python 3.14.2 and Qt/PySide6 6.10.3.
Repository requirements govern runtime/development dependencies; bootstrap
creates the machine-specific ignored `.venv_*` rather than copying an old venv.
Keep all caches and temporary output on the project drive. Once environment
setup is appropriate on the new computer:

```powershell
New-Item -ItemType Directory -Path .\outputs\continuation_tmp -Force | Out-Null
$env:TEMP = (Resolve-Path .\outputs\continuation_tmp).Path
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = Join-Path $PWD 'outputs\pycache\continuation'
$env:PIP_CACHE_DIR = Join-Path $PWD 'outputs\pip_cache'
$CspmPython = & .\scripts\bootstrap_dev_env.ps1 -PassThruPython
```

Bootstrap uses `ensure_venv.ps1`, runtime/dev requirements, the qmllint popup
patch and governed wrapper. Keep VS Code's qmllint no-op configuration. Never
call `qmllint.exe` directly. Use `scripts/qmllint.ps1` or the root wrapper.

Later native rebuilding requires MSVC x64 and Windows SDK already available;
`scripts/build_cleanroom_native.ps1` does not install a toolchain. DLLs are
regenerated under ignored `outputs/native_cleanroom`. Old measured DLL SHA-256
is `35c914560112a009ec8fdce1459e5f77dd10b41acb1ec2b0ae41124ba4d9f709`;
current measured native source SHA-256 is
`f28f62e4e511895e3c1fbde3757d7714cc7997c51b3a060ba9caf03477d532c4`.
A rebuilt DLL may differ and needs new bracketed provenance.

Physical observers additionally used ignored `outputs/pixel_dependencies`:
dxcam 0.3.0, numpy 2.5.3 and comtypes 1.4.17, selected through
`CSPM_PIXEL_DEPENDENCIES`. They can be recreated later; collector-free diagnosis
does not justify running the physical collector. QML `.qsb` assets are tracked;
do not rebuild them merely to clone or read evidence. Use a project-local
`--basetemp` for later tests; the old system temporary drive ran out of space.

Future reproduction, **not executed during closeout**, after private-data and
native-toolchain prerequisites are satisfied:

```powershell
& .\scripts\build_cleanroom_native.ps1 -OutputName cspm_cleanroom_continuation.dll
& $CspmPython scripts/diagnostics/native_gpu_transition_spike.py `
  --audit-label collector_free_productivity_restore_newpc_run1 `
  --bridge-dll cspm_cleanroom_continuation.dll `
  --cycles 5 --duration-ms 350 --blend-start-ms 240 `
  --gui-delay-ms 0 --endpoint-hold-ms 0 `
  --workspace productivity --first-direction restore --restored-size 1100 760 `
  --layout-repair --activation-repair --single-owner-source `
  --native-created-source-band --intrinsic-only --render-target-import `
  --input-witness --input-trace
```

Zero GUI delay must be explicit: the runner defaults to 80 ms. No prepared
target, physical observer, native-call trace or source-transfer trace is enabled
by this command. Use a fresh label every time and preserve failures. Run real
desktop/Qt/WebEngine checks outside a restrictive sandbox; static compilation,
JSON/hash/privacy and no-window tests are separate checks.

## Evidence inventory and preservation classification

The per-file inventory identifies every enumerated ignored/local-only path and
its preservation class in private manifests retained on the old computer under
ignored `outputs/closeout_audit_20261009/`. The original completed primary census
is reused; the experimental census is repeated with `core.longpaths=true` to
include overlong generated test/cache paths. No enumeration rejection is recorded
in the completed final census. Counts are snapshots: this audit adds its own
ignored reports, but no new application/run evidence.
`docs/CSPM_CLOSEOUT_INVENTORY_2026-10-09.json` records these sanitized counts
and SHA-256 hashes of the private local manifests without publishing their paths.

| Checkout | Ignored files | A: private/raw | B: reproducible | C: recorded conclusions/scope | D: source preserved elsewhere |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary | 874,819 | 50,433 | 824,382 | 4 | 0 |
| Detached repair | 4,415 | 6 | 4,409 | 0 | 0 |
| Experimental | 39,454 | 19,277 | 20,098 | 72 | 7 |
| New archival handoff | 0 | 0 | 0 | 0 | 0 |

The seven category-D ignored originals each have a reviewed governed copy and
source/copy hash pair in `scripts/diagnostics/evidence_builders/SOURCE_PROVENANCE.json`.
Category C includes historical fixture/report helpers and this audit's own
review scripts. The primary's old independent motion prototypes are historical;
the accepted current application source is tracked. Historical finance scratch
scripts/reconciliation reports contain private data or paths and remain category
A; their dated outputs do not replace current governed backend services or data.
IDE/cache material is reproducible or conservative local-only metadata. No
additional important untracked source remains after preservation.

- **A — private/raw, intentionally local only:** logs, raw results/captures,
  disposable workbook/settings/profile copies, runtime state, protected-path
  manifests, workbook backups, exports and private stash recovery metadata.
  All originals remain on the old computer. They are not uploaded to Git and
  cannot be recovered by cloning. Source workbooks must be recovered through the
  authorized shared-data/recovery process rather than this code backup.
- **B — reproducible:** virtual environments, downloaded packages, build/dist
  outputs, native DLLs/objects, pytest/bytecode/IDE caches, generated mirrors,
  Qt instrumentation copies and retired package directories. These remain
  local; regenerate only when the next assignment requires them.
- **C — sanitized conclusions:** current learning record and October 3–8
  reports/JSON preserve source/DLL/raw-result hashes, timing reference scope,
  mismatch counts/regions, failure classifications and predecessors. The ten
  latest public and ten raw-result hashes independently match their committed
  links; aggregate counts conserve exactly. This handoff adds portable setup
  and reproduction instructions and stash-only historical knowledge.
- **D — portable first-party source:** reviewed evidence constructors are
  preserved in `scripts/diagnostics/evidence_builders/` with their README and
  original-source hashes. The ignored originals remain untouched. They are
  evidence-building tools; preservation does not qualify the motion engine.

The committed learning record is
`docs/MAXIMIZE_RESTORE_CLEAN_ROOM_LEARNING_2026-10-03.md`; current moving report
is `docs/CLEANROOM_CREATED_BAND_MOVING_2026-10-08.md` with aggregate/per-run JSON
and the existing-QML safety aggregate. Historical October 4 physical report and
all later ownership/probe/source-band/wait controls remain retained. Source and
target equality, native deadline, API/queued CPU observation, input witness,
physical continuity and owner acceptance remain separate gates.

## Worktrees, branches and cloud reachability

| Registered path | Branch / HEAD at preservation | Upstream and state |
| --- | --- | --- |
| `Y:/Projects/__CSPM` | `fix/invoice-billing-client-correction-20260926` / `f96880be888032ac10cd94696b5287335a817159` | Same-named `origin` branch; 0 ahead/0 behind; index/tracked/untracked clean. |
| `Y:/Projects/__CSPM_cleanroom_fluid_transition_20261003` | `experiment/clean-room-fluid-maximize-restore` / `d4289aa5cc37d3f4b4ea5086c9a8380d08e5a1b5` | Same-named `origin` branch; 0 ahead/0 behind; index/tracked/untracked clean. |
| `Y:/Projects/__CSPM-repair-restored` | Detached / `38b4da9c92ca3fd111ad36259adb72aa28cd8159` | No upstream; clean; exact HEAD is live `wip/billing-workbench-disbursement-flat-fee-20260924`. |
| `%TEMP%/cspm_push_handoff_eca9faf_20260820` | Detached / `0026272c7a95454222f7a43d0c63009b30a67b7d` | Already missing at startup; Git marks registration prunable. Files/index cannot be audited; HEAD is remote-reachable. Registration retained. |
| `Y:/Projects/__CSPM_closeout_handoff_20261009` | Archival `docs/new-computer-closeout-20261009`, based on `d4289aa5cc37d3f4b4ea5086c9a8380d08e5a1b5` | Added solely to publish this handoff; final own HEAD/upstream are obtained from the live ref and final response. Clean after its documentation commit. |

All worktrees share the same four repository stashes listed below; stashes are
not independent per-worktree copies. Main and historical WIP are local branches
without checked-out worktrees, each equal to its same-named live remote at the
SHA in the checkpoint table. No tags are registered.

All ordinary local development branch commits are reachable from fetched
remote branches after closeout. There are no intentionally unpublished normal
branch tips. Detached recovery checkpoints are already remotely reachable.
The missing temporary worktree registration remains unchanged; no pruning or
deletion was performed. Every extant original checkout has an empty index,
no tracked modification and no important untracked file after preservation.

Other existing live remote branches at audit time:

| Branch | Full SHA |
| --- | --- |
| `feature/client-ledger-dockets-layout` | `b6c63d1903a99d871bdcedb79c39c604c85d445f` |
| `gh-pages` | `53af412f62b84416497aa2e5bdff50fc02ee2f75` |
| `hotfix/ar-report-net-tax-layout` | `37dac017c739d34125cec6326f647531b189c0a3` |
| `mobile-web-deploy` | `f50025b04b233b94ee7ca9cd5af9e92e9533e17b` |
| `wip/ap-defect-validation` | `7ad4a85ee18e20383cb26391d747d9db5e46b0bf` |
| `wip/billing-workbench-disbursement-flat-fee-20260924` | `38b4da9c92ca3fd111ad36259adb72aa28cd8159` |

## Stashes are local only and were not modified

| Ref / full stash SHA | Date (America/Toronto) | Origin and assessment |
| --- | --- | --- |
| `stash@{0}` / `3a00d1ef7710e8ad5fe1b69452525e2fa1f9d658` | 2026-09-26 13:33 | WIP visual-handoff branch; pre-rebuild invoice correction. Published UI/test blobs and later invoice correction supersede the workflow; retain historical snapshots. |
| `stash@{1}` / `3d5357836321dbc29f0b9c6782b26d9eee7d52eb` | 2026-09-07 13:28 | Main at historical `eca9faf`; experimental visual/startup/lease snapshots, some potentially valuable historically, plus 15 private abandoned-checkout records. Never publish raw stash. |
| `stash@{2}` / `0665ad2e890f6bbd74ebb869798b3656df42e5ed` | 2026-08-12 21:03 | Autostash, planning documents; exact worktree origin not retained. One-writer/hash-based checkout and quality-gate knowledge is superseded by current roadmap. |
| `stash@{3}` / `11d37a04adb412bf1c4456d7cd8e70e40e3399b9` | 2026-08-11 21:38 | Autostash, planning documents; exact worktree origin not retained. Same published checkout and 10/10-gate direction. |

Four stashes reach eleven local-only commit objects in total: ten
stash/index/untracked wrapper commits plus historical unpublished ancestor
`eca9faff57cfee2cd6378ec5ecba7906addc7d44`. This differs from published
`0026272c7a95454222f7a43d0c63009b30a67b7d`. These intentional local objects are
excluded from the ordinary-branch unpushed count; a clone does not restore them.
No stash was applied, popped, deleted, rewritten or pushed.

The expanded reflog/object audit finds sixteen local-only commit objects in all:
those eleven stash-reachable objects, three historical commits whose exact
stable patch IDs are already remote, and two unreachable earlier stash-wrapper
objects whose trees exactly equal the retained September 7 stash/index trees.
No additional current development behavior is missing. The historical mappings
are `674ffacc4902cbc75463f6d96b47ab442c321fa4` →
`9d1910d4387f3ef433233b3f79e891682b72ba11` (report logo),
`43cd11554ce52469b410100c3c4a9194a0b94eba` →
`146b649fb21220b67fba109ab4ed214c3e95b4b4` (splash syntax), and
`cd40cfbd4e05fd4b055bc4b31eccd51adc07a888` →
`6e300886352d2a3a539c4fa9438c7a57d359bddc` (invoice root folder).
The earlier duplicate wrappers are
`cee979cfabfcdf14134591e4a2d0f2d30f47ea65` and
`060a23dc434fbc16e86fc65d48ac075e2469fdc0`; no salvage branch or upload is
needed for their private/historical snapshots. Object storage and reflogs were
not pruned or altered.

Preserved non-private stash knowledge: enforce explicit bootstrap identity and
quit guards; bound briefing startup/fallback; complete hidden-first splash
handoff before showing the main window; avoid invisible `grabToImage` stalls;
require verified frozen/live endpoint transitions; preserve same-PC lease
identity/recovery. Current remote code uses later asynchronous-worker/native
fixes. Do not restore old synchronous/fallback snapshots as a fix. The
single-writer SHA-256 cloud-package and 10/10 financial/quality gates remain
the current durable plan. No essential current non-private workflow is known
to exist solely in a stash after this summary.

`HANDOFF_INDEX.md` also has fifteen unresolved `_cspm_workspace` references.
That old directory and the referenced current-status/plan/architecture records
are absent from the primary checkout, and no relocated copies were found in
the bounded search. Do not assume those links supply the current handoff.
Adjacent ignored October 1 engineering handoffs are historical; their native
transition rejection, WebEngine/geometry scope and unresolved acceptance gates
are represented in later committed records. The new document and mandatory
startup/current clean-room records are the continuation authority.

## Safety and validation boundary

Twelve protected files were hashed before closeout and rechecked afterward:
repository starter/source workbook copies in the three original extant
checkouts, authoritative local settings/workbooks, configured shared workbooks,
and the installed main executable. All twelve hashes remain unchanged. The
October 8 protected local-data/settings and installed-main baseline also matches.
Private absolute-path manifests are retained only under ignored
`outputs/closeout_audit_20261009/`; they are not published here. Installed main
SHA-256 remains
`8D461B679B4D578CFB6BE6DE259AB2E183E62A6D9F1EB944A69527BEFC8C0FA3`.
The historical earlier settings-baseline variation remains recorded and is not
relabelled as whole-history equality. No runtime/package/install command was
executed during closeout, and no CSPM/QtWebEngine process was observed in the
closeout process check.

Every commit used an explicit allowlist, complete change/content review, staged
file/diff review, the existing read-only staged privacy/credential scanner and
whitespace checks. Preserved Python tools pass AST/compilation without execution;
public JSON parses and evidence-link hashes/counts match. No private workbook,
settings, log, screenshot/frame, application state or credential is staged.

Closeout checks are **sandbox-safe file/Git/AST/JSON/hash/privacy checks only**.
No new WebEngine or desktop runtime validation is performed during closeout.
The existing-preview Chromium HTML evidence belongs to the earlier recorded
outside-sandbox October 8 run; new PDF/installed WebEngine qualification remains
open. No source file or evidence is deleted, no stash altered and no force push
performed. No feature development follows this closeout.
