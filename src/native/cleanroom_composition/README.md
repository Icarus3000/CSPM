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
Only an 80-byte geometry/clock constant buffer is updated from CPU per frame.
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
