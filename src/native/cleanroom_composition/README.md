# Experimental native GPU composition bridge

## Current decision — 2026-10-03 continuation

The cold complete candidate is rejected for integration. The rebuilt preserved
bridge again misses its fixed content deadline: target delivery is about 855 ms
after native start, with an observed source endpoint hold of at least 428 ms.
The optional disposable profile associates 353 ms with the two final-size
assignments before native host resizing, then observes substantial first-frame
and GUI-delivery delay. GPU export itself takes about 6 ms in that profile.
No source/target transport or pacing change demonstrated removal of this cold
Qt dependency. Individual expensive bindings remain unidentified.

The sole fixed-clock QML comparison also misses every primary target deadline.
There is no qualifying complete engine to package, install or make the default.
Native texture access, independent presentation and prepared pixel identity
remain useful capability results. All failed runs are retained locally, and
privacy-safe aggregate results are preserved on the experimental Git branch.
See the clean-room learning record for classifications and measurement limits.

This is a capability spike, disabled in production. It builds against the
existing Microsoft Windows SDK and MSVC without Qt C++ headers or Qt ABI
emulation. Python passes only the borrowed `ID3D11DeviceContext*` returned by
the public Qt renderer interface; native calls use SDK-typed COM interfaces.

Build from this experimental worktree:

```powershell
.\scripts\build_cleanroom_native.ps1 -OutputName cspm_cleanroom_composition_paced.dll
```

The output is ignored `outputs/native_cleanroom/cspm_cleanroom_composition_paced.dll`.
The build accepts a plain DLL output filename so an active desktop fixture's
binary need not be replaced. Build logs are retained beside the DLL. Use
`ctypes.CDLL`: exports use the Windows x64 C ABI. ABI version remains 1.
This output must be explicitly included by a governed experimental package;
the current release builder does not automatically bundle it.
Load one bridge version per fixture process. The preserved shader and paced
binaries reuse a window-class name and must not both create hosts in the same
process. System imports include D3D11, DirectComposition and D3DCOMPILER_47;
MSVCP140/VCRUNTIME140/VCRUNTIME140_1 and the universal CRT must be provided by
the existing governed runtime environment. No global installation is performed.

## Capture contract

Connect a one-shot callback directly to `QQuickWindow.afterRenderPassRecording`.
Call `window.beginExternalCommands()` before querying
`QSGRendererInterface.DeviceContextResource`, pass its opaque value to
`cspm_gpu_capture`, and call `window.endExternalCommands()` in `finally`.

Capture retrieves the current RTV, queries its typed Texture2D, copies into an
immutable shared keyed-mutex GPU texture, submits with Flush and releases key
1. There is no texture Map, framebuffer CPU readback or image upload. The
destination device uses the same GPU adapter, opens the shared texture,
acquires key 1 with a 40 ms bound, and copies into a native-owned shader texture.
The keyed mutex governs cross-device rendering access. Flush submits commands;
it does not prove CPU-observable GPU completion or physical presentation.
The native immediate context orders its copy before sampling and presenting.
Only a 112-byte geometry/clock/witness constant buffer is updated from CPU per frame.
The source/target pixel data remains on GPU throughout the bridge.
Both RGBA8 and BGRA8 are accepted; MSAA/array/mipmap/other formats are explicit
capability failures. CPU call duration measures submission, not scanout.

## C exports

```c
unsigned cspm_comp_abi_version(void);
void *cspm_gpu_capture(void *context, unsigned *width, unsigned *height);
void cspm_gpu_release(void *frame);
void *cspm_comp_create_from_frame(void *frame, int hostLeft, int hostTop,
                                int hostWidth, int hostHeight);
int cspm_comp_set_source_frame(void *host, void *frame, float x, float y,
                              float width, float height, float headerPx,
                              float rightFixedWidth);
int cspm_comp_start(void *host, float targetX, float targetY, float targetWidth,
                    float targetHeight, unsigned durationMs,
                    unsigned blendStartMs);
int cspm_comp_set_target_frame(void *host, void *frame);
unsigned cspm_comp_status(void *host);
int cspm_comp_presentation(void *host, unsigned *submittedCount,
                           unsigned *displayedCount, unsigned *statisticsHRESULT);
double cspm_comp_elapsed_ms(void *host);
uintptr_t cspm_comp_hwnd(void *host);
int cspm_comp_finish(void *host);
void cspm_comp_destroy(void *host);
unsigned cspm_comp_error(void *host, char *buffer, unsigned capacity);
```

All rectangles/header metrics are physical pixels relative to the fixed native
host; framebuffer width/height must agree with the source/target physical
rectangles. Include actual framebuffer padding in header/control metrics.
Set-source/target synchronously copy GPU pixels; the caller may release the
frame when the call returns. A queued operation retains COM ownership even if
its completion bound fails. Status bits: source commit processed 1, clock
started 2, endpoint frame submitted with target pixels 4, target uploaded 8,
failed 16, DXGI statistics observed endpoint present ID 32. Source commit
processing, endpoint submission and DXGI statistics are not independent physical
presentation proof. Status is read from atomic flags rather than deriving
endpoint success from elapsed time.

Each transaction uses its own host. Source and target may be set only once.
The host has its own UI thread, input-transparent/nonactivating fixed HWND,
and a GPU composition swapchain. Its independent native UI thread renders and
presents using one absolute QPC begin time; this is native-thread animation,
not compositor-owned animation. Geometry and content use the monotonic C3
polynomial `35p^4 - 84p^5 + 70p^6 - 20p^7`, with zero first, second and third
derivatives at both ends. The content clock starts at the authored blend time.
The premultiplied shader computes `old * (1-a) + target * a` for all four
channels in one pass. Integer `Texture2D.Load` endpoint branches avoid filtering
and remove the old source contribution at target alpha corners.

The paced swapchain uses `FRAME_LATENCY_WAITABLE_OBJECT` and a queue limit of
one. Before every render, including the source frame, the native thread waits
at most 100 ms for its presentation slot and then samples QPC. A delayed slot
skips stale trajectory samples rather than changing or restarting the clock.
The wait handle is closed during native-thread resource cleanup. Optional
atomic presentation telemetry reports the last submitted ID, last ID reported
by `GetFrameStatistics`, and the statistics HRESULT. The first statistics query
may report disjoint, and Microsoft documents limits in multiple-monitor cases.
The native thread polls endpoint statistics for at most 250 ms after authored
duration; it never uses an observed ID alone to prove physical acceptance.

Target upload accepts a diagnostic prepared frame before start. That mode
isolates GPU presentation capability and must record its stationary preparation
wait; it cannot qualify cold command-to-presentation responsiveness. After
start, target upload fails after the fixed blend deadline. A missed target
does not cap, pause or restart geometry. Host rectangles must be integral
physical pixels, lie fully inside the fixed host and match GPU frame dimensions.
Copies use matching full resource extents rather than unchecked atlas offsets.
The original workspace is owned by the Qt application throughout.

## Gate before desktop launch

Qualification requires a populated CSPM GPU source, a differently sized GPU
target, independent physical movement during an intentional Qt GUI stall,
the same content transfer schedule, fixed header proportions, physical endpoint
pixel equality, live Qt handoff, repeated maximize/restore, and bounded late
target failure. An elapsed status flag, compile success, source-only pattern or
final rectangle cannot pass that gate.

The initial visual-tree control kept source opacity at one beneath the target;
that retained source contributions at translucent target corners. Its binary
is preserved as `cspm_cleanroom_composition_visual_control.dll`. The shader
corrects that equation, but pixel equality and header stability still require
the real desktop gate. Finishing hides the host only after the
caller proves a matching submitted live Qt frame. Source coverage processing
does not prove scanout; the collector must check real desktop pixels.

The first populated cold-target fixture proved GPU source/target capture and
independent source movement during intentional Qt delays. Its target became
available about 705 ms into the transaction and missed the fixed 240 ms
transfer deadline. Cold-target readiness remains a qualification failure;
prepared-target success cannot remove that failure.

Caller waits are bounded: commands 2000 ms, initialization/destruction 3000 ms,
and shared-resource acquisition 40 ms. Windows/driver calls may still outlive
those caller bounds; a timed-out live host is retained rather than freed or
forcibly terminated. Queued frames retain COM ownership after a caller timeout.
This intentional retention is a capability-spike limitation, not a production
lifecycle claim. Per-transaction HWNDs/resources are normally released on
their native owner thread. There is no engine promotion or production default
change in these files.

## Primary sources

- [Exact Qt 6.10.3 render callback/API source](https://github.com/qt/qtdeclarative/blob/v6.10.3/src/quick/items/qquickwindow.cpp)
- [Qt renderer resource contract](https://doc.qt.io/qt-6/qsgrendererinterface.html)
- [Microsoft shared-resource contract](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11device-opensharedresource)
- [Microsoft keyed synchronization](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgikeyedmutex-acquiresync)
- [Release shared rendering access](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgikeyedmutex-releasesync)
- [GPU swapchain into DirectComposition](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/nf-dxgi1_2-idxgifactory2-createswapchainforcomposition)
- [Present contract](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgiswapchain-present)

Compile history on 2026-10-03: initial build passed; adding animated container
clips exposed overload ambiguity for integer zero in SetLeft/SetTop and failed
once; explicit float arguments corrected it. Subsequent builds passed with
MSVC `/W4`, including lifetime/race/deadline guards. The failed compile is not
runtime evidence and is not omitted from this record.

Shader build passed `/W4` on 2026-10-03; SHA256
`8C1DEC039523243956541BA13D8332FC91FE914014A32DCE826563A361698F77`.
Its four-cycle prepared fixture proved all four source endpoints exactly;
target measurements failed and physical collection showed motion remaining
after the submission flag. Those failures motivated bounded queue pacing;
they are not discarded or replaced by later prepared results.
Paced build passed `/W4`; SHA256
`68391F186018C1AF4D4F6526D8F28A299DBA0F10929886D98C9B882CE6AA03A7`.
The root-run `logs/native_gpu_paced_prepared_20261003_run1` fixture completed
four alternating maximize/restore cycles. All eight physical source/target
endpoint comparisons had zero differing pixels, and protected production-file
hashes remained unchanged. This diagnostic prepared targets after three Qt
submissions and held the submitted native endpoint for 120 ms before sampling.
Its full command-to-live handoffs took roughly 1451–1717 ms. It explicitly
reports `NOT QUALIFYING`: the stationary preparation and diagnostic settling
remain in full transaction time, and the earlier cold deadline failure stands.
Static DLL load/ABI/null-argument rejection passed; these are sandbox-safe
checks, with no Qt/WebEngine or desktop launch by this native subtask.
Root owns the outside-sandbox populated Qt/WebEngine desktop gate and reports
its separate physical endpoint/repeat evidence.

The preceding description recorded three Qt submissions before prepared
capture. Current diagnostic source instead requests the next after-pass capture;
no saved source manifest establishes that older gate exactly. The historical
pixel pass belongs to its preserved run and is not a fresh pass of every later
script edit. New runs save source/DLL hashes at startup. Use
`--profile-boundaries` to create an instrumented disposable QML mirror and record
only commit statements and one-shot render/adoption callbacks. Profiling buffers
event output; its render callbacks still need Python's GIL. Millisecond QML
wall-clock observations are calibrated per transaction. These are neither pure
Qt stage durations nor physical scanout timestamps. No CPU framebuffer image
feeds the native host in either mode.

## Target-readiness continuation, 2026-10-03

The opt-in shared-control/disabled-effect, HomeGrid and batched shell metrics
repair is checkpointed at `485ff58`. It retains ordinary production behavior
when the process-local repair flag is absent. The current separately named
`cspm_cleanroom_stage_resume.dll` build passes MSVC `/W4`, shader compilation and
ABI/null checks; SHA256
`69556EA8A21F483281DE2234646CC01355A595EB9FF1D3CE860FF04D021F80BE`.
No installed Qt module is patched by these source changes.

The diagnostic `--render-target-import` caller validates the predetermined
physical endpoint and calls the unchanged target setter from the render
callback after export. The native owner thread still acquires/copies the shared
resource, publishes its own SRV, and enforces the same 240 ms transfer deadline
before and after copying. No direct render-thread access to native-owned
resources or weaker readiness gate is introduced. Captured frame lifetime and
terminal cleanup cover active imports and undelivered queued notifications.

One populated cold Productivity maximize publishes its native target at
205.66 ms; queued GUI receipt arrives at 244.19 ms. Following restore misses at
280.00 ms, and a separate cold restore misses at 389.58 ms, including 169 ms
metrics publication. Other workspace/size fixtures achieve internal readiness
in both directions, but table and foreground Time Entry pixel checks fail.
Chromium HTML load success in the existing preview is separately established;
visible preview/PDF fidelity is untested. Native API returns and DXGI counters
do not prove desktop scanout, endpoint equality or input restoration. The
command-to-live fixture still includes source preparation and explicit
endpoint/live observation waits. Zero configured endpoint hold is not a
physical no-plateau certification.

All failed raw runs remain ignored locally. Sanitized stage/thread intervals,
overlap limits and source hashes are recorded in
`docs/CLEANROOM_TARGET_READINESS_DECOMPOSITION_2026-10-03.json`; interpretation
and remaining restore/layout costs are in the clean-room learning record.
**Candidate not qualified; no package/install/default change or user acceptance.**

## Submitted-surface identity continuation, 2026-10-08

The preceding retained `GetBuffer(0)` COM pointer was not an immutable submitted
allocation. Microsoft documents that Direct3D 10/11 changes backbuffer identities
after flip-model Present. A persistent interface can therefore address different
storage after submission. This accounts for diagnostic submitted samples that
disagreed even when independently observed desktop endpoints were exact.
See the [Microsoft DXGI backbuffer identity contract](https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/d3d10-graphics-programming-guide-dxgi#care-and-feeding-of-the-swap-chain).
This establishes a probe error, not the cause of the retained Directory desktop
margin discrepancy; the latter still requires fresh complete-client measurement.

The additive diagnostic APIs below retain ABI version 1. Call
`cspm_comp_enable_probe_snapshot` exactly once before source preparation when
requesting source/endpoint probes. Ordinary runs allocate no diagnostic snapshot.
An enabled host copies its exact drawn swapchain buffer into an owned GPU
allocation **before Present**, only for stopped source and complete endpoint
frames. Intermediate moving frames perform no diagnostic copy. No CPU readback
is added to the motion clock. A stopped bounded probe maps at most 64 one-texel
staging resources; it never feeds presentation. Finish/hide preserves the owned
endpoint snapshot until native resource cleanup.

```c
int cspm_comp_enable_probe_snapshot(void *host);
int cspm_gpu_frame_identity(void *frame, void *output, unsigned capacity);
int cspm_comp_probe_identity(void *host, void *output, unsigned capacity);
int cspm_comp_probe_pixels(void *host, const int *xy, unsigned count,
                           unsigned char *sourceBGRA, unsigned char *submittedBGRA);
int cspm_comp_probe_endpoint_pixels(void *host, const int *xy, unsigned count,
                                    unsigned char *targetBGRA, unsigned char *submittedBGRA);
int cspm_comp_probe_frame_pixels(void *host, void *frame, const int *xy,
                                 unsigned count, unsigned char *frameBGRA);
```

Initialize identity output `version=1` and `byteSize` before each call. On the
Windows x64 ABI, `FrameIdentity` is 48 bytes, in this order: `uint32_t version,
byteSize`; `uint64_t revision`; `uint32_t width,height,format,mipLevels,arraySize,
sampleCount,subresource,orientation`. Frame revision survives queued COM retention.

`ProbeIdentity` is 200 bytes, in this order: `uint32_t version,byteSize`;
`uint64_t hostGeneration,snapshotRevision,sourceFrameRevision,targetFrameRevision`;
`uint32_t submittedPresentId,phase,witnessRevision,subresource`;
`double snapshotQueuedSeconds,presentBeginSeconds,presentReturnSeconds,motion,content`;
`int32_t hostLeft,hostTop,hostWidth,hostHeight,sourceLeft,sourceTop,sourceWidth,
sourceHeight,targetLeft,targetTop,targetWidth,targetHeight`;
`uint32_t sourceFormat,targetFormat,snapshotFormat,snapshotWidth,snapshotHeight,
snapshotEnabled,orientation,premultiplied`;
`uint64_t sourceResourceIdentity,targetResourceIdentity,snapshotResourceIdentity`.
The resource identities are monotonic opaque IDs, not addresses. Phase 1 is source,
phase 3 is complete target; the witness revision is the same value drawn in the
presentation swapchain. Identity matches the last successful Present ID/QPC
boundary and submitted motion/content sample. A source snapshot remains unchanged
through motion but cannot be sampled as the current source once the clock starts.
A completed target requires the exact `motion=content=1` endpoint.

Probe coordinates are nonnegative, integral physical framebuffer/client pixels.
Right/bottom are exclusive. Source/target texture coordinates use no offset;
submitted coordinates add the corresponding integral source/target host-relative
origin. Subresource is mip/array slice 0 and orientation 1 is top-left. D3D rows
are not inverted. The one-texel staging read consumes its first four bytes,
so padded RowPitch does not imply a coordinate adjustment. RGBA8 input is reordered
to BGRA output; UNORM premultiplied channel values are returned without compositing
or unpremultiplication. The independent original-source/later-live exported frame
probe validates against that immutable frame's own extent. Its caller separately
requires later-live dimensions to equal the complete target extent.

`tests/native_cleanroom_submission_marker.cpp` is a real D3D11/DirectComposition
synthetic GPU control, separate from safe no-window checks. It authors coordinate
and revision markers at all four corners, four edge midpoints, centre and 36 points
in the Directory band (`x=1111..1122`, `y=646,650,655`), using source offset `(12,14)`
and target offset `(40,50)`. Returned source and submitted texels are independently
checked against the CPU-authored formula. It checks BGRA8 and RGBA8, alpha values
0/85/170/255, revision/Present/phase metadata, no intermediate snapshot rewrite,
stale identity rejection and retention after hide. This is a shader/probe identity
test, not a desktop scanout or real-app qualification.

The preserved pre-repair BGRA-only control differs at 99/135 source and 39/45
endpoint samples. The initial repaired BGRA control is exact at 135/135 and 45/45;
the strengthened CPU-formula/two-format control is exact at 270/270 source and
90/90 endpoint samples. Both actual one-texel staging row pitches are 64 bytes.
All synthetic artifacts remain ignored under
`outputs/cleanroom_resume_20261004/probe_identity_20261008`. SHA-256 provenance:

| Artifact | SHA-256 |
| --- | --- |
| Probe-contract native source at measurement | `3630819DC29DBDC440C850A4547669A7FEB1A5BFF0F47D353FB9E8D101678C6E` |
| Initial probe-contract DLL (`cspm_cleanroom_probe_identity_20261008.dll`) | `1E185A8B7F35AEB62748425830E4A8775D0441D9E6228015D41B2BD61CD5E1DA` |
| Baseline marker result | `51C7857D8E5B62EAFA7ACEC0395279B4A413681DFBFF77BC22E32CEF1E62C0E0` |
| Initial repaired marker result | `DECCE9E021E58F5C8DC800509248D2CF8F9A9BB64BFCBB2B6567ACD11B8BA0B1` |
| Two-format CPU-formula marker result | `A58F14D99B6917F052AB8E196FF0B49D6297CE501DB250A80513B8C1C0A31BC0` |

MSVC `/W4` native/shader build, the no-window native contract executable, additive
ABI/null-export rejection and whitespace checks pass. These are sandbox-safe
checks without Qt/WebEngine. The synthetic marker GPU executable ran outside
sandbox with a hidden nonactivating test HWND and no private content. Root owns
fresh Directory/Qt/desktop evidence; this subtask adds no WebEngine startup/PDF,
installed-package, complete cold qualification or Cory acceptance claim.

## Passive source-band transfer telemetry, 2026-10-08

Later Directory and Productivity controls reject source-band verification after
successful hide-live/show-native batching, before motion. Earlier observations
show a topmost live source and a hidden non-topmost native host; the failed API
boundary previously retained no expected/actual styles. Foreground and native
owner-thread correlations do not establish the cause. The following telemetry
fills that gap without changing batch flags, ordering, failure gates, activation,
shaders, geometry, padding or authored motion/readiness deadlines.

```c
int cspm_comp_enable_source_transfer_trace(void *host);
int cspm_comp_source_transfer_observation(void *host, void *output, unsigned capacity);
int cspm_comp_source_windowpos_trace(void *host, void *output, unsigned capacity);
```

Enable explicitly once before source preparation. Previous/ordinary runs remain
uninstrumented. The actual transfer call starts the trace, omitting initialization
noise, and captures input-lock-complete API-entry styles, expected source band,
process/thread relationships, owner relationships, foreground ownership and
visibility. It records Begin/Defer/End accepted results, QPC boundaries and exact
exit styles before preserving the unchanged rejection reason. Data remains
readable after failure bit 16. No readback, input injection, retry, activation or
additional presentation operation occurs.

`SourceTransferObservation` has version 1 and byte size 192. Field order:
`uint32_t version,byteSize`; `uint64_t hostGeneration,sequence`;
`uint32_t stage,accepted,win32Error,expectedTopmost,currentThreadId,currentProcessId,
liveThreadId,liveProcessId,nativeThreadId,nativeProcessId,sameParent,sameProcess,
liveThreadOwned,nativeThreadOwned,liveForegroundEntry,liveForegroundExit,
liveOwnerRelation,nativeOwnerRelation,liveStyleEntry,nativeStyleEntry,liveStyleExit,
nativeStyleExit,liveVisibleEntry,nativeVisibleEntry,liveVisibleExit,nativeVisibleExit,
beginAccepted,liveDeferAccepted,nativeDeferAccepted,endAccepted`;
`double entrySeconds,beginBatchSeconds,endBatchBeginSeconds,endBatchReturnSeconds,
exitSeconds`; `uint32_t traceEnabled,policySampled`. Thread-owned fields compare
against the calling thread. Same-process means both windows belong to the current
process. Owner relations are 0 none, 1 original live, 2 native host, 3 another owned
process window, 4 another process, 5 unknown. No HWND or pointer is returned.

Stage 0 means no transfer entry. Stage 1 means entered; stages 2–8 respectively
identify validation, Begin, live Defer, native Defer, End, visibility and band
rejection; stage 9 means accepted. Stage 10 identifies native-worker hidden band
preparation (terminal rejection if that operation fails); stage 11 rejects a live
band change between native preparation and batching. `policySampled=1` establishes the actual band
read used by batching. Successful Win32 calls alone cannot establish transfer
acceptance or observed desktop pixels. For failed batch positioning APIs,
`win32Error` is captured immediately; state-gate rejection has no fabricated
Win32 error. Hidden worker rejection preserves its native error string, and
does not currently publish a separate worker SetWindowPos return/error field.

`SourceWindowPosTrace` is version 1, byte size 1048, row byte size 64, with header
`uint32_t version,byteSize,rowByteSize,count`; `uint64_t totalRows`; then 16 rows.
Each row contains `uint64_t sequence`; `double timeSeconds`;
`uint32_t message,phase,insertAfterBandBefore,insertAfterBandAfter,flagsBefore,
flagsAfter,styleBefore,styleAfter,currentThreadId,expectedTopmost,visibleAfter,
reserved`. Phase is the transfer stage at observation, and reserved is zero.
Only the owned host's stopped `WM_WINDOWPOSCHANGING/CHANGED` messages are observed;
the original `DefWindowProc` executes once, unchanged. First sixteen rows are
retained, so later cleanup cannot overwrite transfer evidence; `totalRows` exposes
truncation. Rows after API return remain observable until motion/cleanup and have
their own QPC and terminal stage, allowing delayed ordering to be distinguished
from immediate returned state. Insert-after bands are 0 TOP/null, 1 TOPMOST,
2 NOTOPMOST, 3 BOTTOM, 4 original live, 5 another current-process window, 6 another
process, 7 unknown. Pointer addresses and unrelated window identities are omitted.

Telemetry native-source SHA-256 is
`4017831FE05FBCDB651E7B619BC4BFE62F9AB51387A6AF36718B2E0D622C15F0`;
new `cspm_cleanroom_source_transfer_trace_20261008.dll` SHA-256 is
`B5B6D0313AAAD930910AD15EA97364C353D5FEAC2A0F606FF5355078AFB15968`.
Source/build-script/contract hashes match before and after compilation in ignored
`outputs/cleanroom_resume_20261004/source_transfer_trace_20261008` manifests.
MSVC `/W4` native/shader build, the no-window native contract, ABI 1/additive export
null rejection and whitespace checks pass. Safe contract checks use synthetic
message data and null HWNDs; they send no Windows messages and construct no window
or device. Root owns real transfer measurements. The band cause and complete cold
qualification remain open; no new desktop GPU or WebEngine claim belongs to these
safe checks.

## Owned hidden-band preparation, 2026-10-08

The actual passive Productivity transfer trace proves failed native promotion:
expected band is topmost, live entry/exit style remains `0x80008`, native
entry/exit remains `0x082000a0`, and source foreground remains false. Both Defer
calls and End return success. The host belongs to the native worker, the live
source to the GUI thread, and both are in the same process with the same parent.
Native `WM_WINDOWPOSCHANGING` receives foreign-window insertion band 6 with flags
`0x53`; `WM_WINDOWPOSCHANGED` receives band 6 with flags `0x1857`. This establishes
the failed cross-thread request's observed result. It does not separately prove
whether foreground permission or another Windows policy caused that rewrite.
Raw retained evidence is
`logs/native_gpu_source_transfer_productivity_20261008_run1/native_gpu_spike.json`;
the prior failure and original native error remain unchanged.

The general diagnostic correction samples the owned live band and applies it
once on the native HWND's verified owner thread while the host remains hidden
and stopped. That operation uses `SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE` and strictly
verifies the resulting band and unchanged hidden visibility. The GUI thread
then verifies that the live band has not changed and uses `SWP_NOZORDER` in its
existing hide-live/show-native batch, preserving the already established band.
The existing visible worker ordering operation reuses the same owned-thread
helper. This adds no activation, retry, geometry motion, shader/alpha alteration
or weaker band/visibility/pixel/witness gate. Production remains unchanged.

The unchanged 192/64/1048-byte telemetry tags native hidden preparation with
WINDOWPOS phase 10, then returns to phase 1 for the GUI batch. The actual style
change can be bracketed by native changing/changed rows before the recorded GUI
batch QPC boundaries. Those are observed operation boundaries, not a pure CPU or
GPU execution duration. Source foreground entry/exit remains independently
reported. The helper rejects unknown policy, wrong worker ownership, unexpected
visibility, absent source preparation, running clocks and failed transactions.

Corrected native-source SHA-256:
`C49FCBC8FDCBC761380EA42F47788D5E048BFC7765597137673C3CBB7E3A19DB`.
Unique `cspm_cleanroom_source_band_worker_20261008.dll` SHA-256:
`03C9805C87AA82554F80E7C547FA36FF98B3154D8BD49D117C37EE740D238697`.
Bracketing source/build-script/contract hashes match in ignored
`outputs/cleanroom_resume_20261004/source_band_worker_20261008` manifests.
MSVC `/W4` native/shader build, safe native contract, ABI 1/seven null-export
checks and whitespace review pass. This native subtask ran no new GPU/window or
WebEngine fixture. Root owns the matched cold restore, worker-band and fresh
desktop evidence; readiness/input/continuous-motion/lifecycle and user acceptance
remain required before qualification.

The later SDK-only `tests/native_cleanroom_source_band_control.cpp` loads one
diagnostic DLL per process, creates a task-owned visible `WS_EX_NOACTIVATE`
source on the caller thread, and supplies CPU-authored synthetic GPU markers.
Both non-topmost and topmost policies use the actual transfer API and native
worker host. Baseline telemetry DLL `B5B6D031...` and corrected worker DLL
`03C9805C...` both pass with measured source foreground entry/exit false, unchanged
original foreground through cleanup, hidden live/visible native windows, correct
bands and eighteen exact source/submitted coordinate pairs per DLL. The corrected
trace shows hidden worker phase 10 followed by GUI phase 1 with `SWP_NOZORDER`.
These outside-sandbox synthetic controls contain no private content, Qt or
WebEngine and do not observe complete desktop pixels.

The baseline also passes: its actual insertion uses another current-process
window (band 5), whereas the retained full-app failure uses a foreign-process
window (band 6). Foreground false alone therefore does not explain the failure.
The synthetic source has no Qt/input guard, so the previously failing background
full-app condition remains a separate qualification requirement. Results are
retained in ignored
`outputs/cleanroom_resume_20261004/foregroundfalse_band_control_20261008`:
baseline JSON SHA-256
`55EE53CA7C4186072BA52A809A4256E21A67AC04094555F92291AC8EE0527E4F`;
corrected JSON SHA-256
`7D7E285DA065395142B68FCD0831307D89377EB98C4002CCC779ED8129C69F13`.
Both processes exit normally; their twenty-second outer watchdog is not reached.
The native source and diagnostic DLLs remain unchanged by this control.

The later real Productivity cold restore-first run 3 rejects the hidden worker
preparation itself, with zero completed cycles. The same frozen source and DLL
above are retained; raw JSON SHA-256 is
`54DD99FB541F1078F283C4638B6A1D948B43EB83B899B86F4CB235862FF91CC6` at
`logs/native_gpu_source_transfer_productivity_20261008_run3/native_gpu_spike.json`.
Expected topmost is 1; source foreground entry/exit is 0. Live entry/exit style
remains `0x80008`, visible; native entry/exit remains `0x082000a0`, hidden. Both
windows have no owner, share the process and parent, and the changing message
executes on the recorded native owner thread. The single phase-10
`WM_WINDOWPOSCHANGING` row has foreign insertion band 6 and flags `0x13`, unchanged
across the original `DefWindowProc`. No `WM_WINDOWPOSCHANGED` row is retained.
`SetWindowPos` returns success, but the strict style/visibility verification fails
with the original error, "Stopped source band operation did not preserve the
owned live window band and visibility". The GUI visibility batch never starts:
all Begin/Defer/End accepted fields and batch timestamps remain zero. The worker
request is bounded by transfer entry/exit, 2.583 ms apart; that interval includes
dispatch and checking, rather than pure Win32 execution time. Live input is
subsequently restored by the existing failure cleanup.

Run 2's earlier accepted transfers therefore do not establish a universal repair:
both had foreground entry/exit true. Its restore completes with exact pixels and
input, while the next maximize accepts its target at 165.356 ms but fails the
unchanged 100 ms presentation-slot gate before a complete endpoint. That gate
does not record the actual wait result or a failure-time native window state, so
neither a specific wait-result code nor a source-band cause can be assigned to
that separate failure.

Microsoft's [SetWindowPos contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos)
requires foreground permission to bring a window to the top, while separately
defining `SWP_NOACTIVATE`. This supports investigating foreground permission but
does not prove it caused the failed request. The successful background SDK
controls use insertion band 5; the failed application uses band 6. The current
sanitized enum records the predecessor's process relationship, not its topmost
style or whether it is the foreground window. A useful next bounded measurement
is passive predecessor-band/foreground relationship evidence, followed by a
same-DLL SDK comparison with an owned layered source and the input guard. No
activation, retry, gate relaxation, native source edit or further desktop run
belongs to this read-only diagnosis. The background full-app source-band
condition, repeated populated readiness and complete qualification remain open.

## Explicit source-band creation control, 2026-10-08

`cspm_comp_create_from_frame_with_source_band` is a diagnostic opt-in. It
validates the visible current-process GUI source and immutable frame extent,
then creates its hidden worker HWND with the sampled `WS_EX_TOPMOST` policy.
The ordinary `cspm_comp_create_from_frame` export retains its default behavior.
Both windows remain independent unowned top-level windows; this does not add
a `GW_OWNER` relationship or request foreground permission.

`cspm_comp_create_from_frame_observed` accepts that same frame/live HWND and
geometry, a strategy flag (0 historical, 1 direct creation), and caller-sized
creation/native-trace outputs. It enables telemetry before initialization for
both strategies. Creation rows are 392 bytes; the bounded twelve-row observation
is 4816 bytes. Existing version-1 call/state/trace layouts are unchanged.
`cspm_comp_source_creation_observation` only reads the retained observation.
On null creation, capture `cspm_comp_error(nullptr)` before any later native
call. Rejected initialization preserves outputs and safe lifetime retention.
On accepted creation with invalid evidence, retain the host for one cleanup.

The created hidden band/style/visibility/authority is checked immediately,
after source attachment, after commit return and after commit processing.
Hidden positioning preserves Z-order. Once visible, one nonactivating
`HWND_TOP` placement raises within the verified group, followed by another
observed band/visibility check. No repeated promotion is attempted.

`tests/native_cleanroom_win32_band_control.cpp` provides pure Win32 GUI/worker
A/B metadata; the D3D11 source control supports `--created-live-band`,
`--created-native-band` and `--guard`. The populated spike requires
`--single-owner-source` for `--native-created-source-band`. Current matched
results, exact physical source controls, rejected attempts and binary hashes
are in `docs/CLEANROOM_CREATED_SOURCE_BAND_2026-10-08.md` and JSON. These
stopped controls do not qualify moving presentation-slot, target deadline,
continuous motion, WebEngine or installed acceptance. All 350/240/100 ms gates
remain unchanged and production remains the default.
