# Intermittent restore shift investigation — 2026-10-02

The user reports a very slight, intermittent position shift on maximized-to-restored transitions. This investigation reproduces a matching one-pixel change at the captured-image/live-window handoff on the 225% display. The native window rectangle remains unchanged during the compared samples. The 100% display does not reproduce that edge change in the completed comparison. This is a diagnosis, not a completed application fix or user acceptance.

## What was measured

Read the complete repository and per-user runtime logs before diagnosis. Their latest entries predate the early-motion release, so neither records this particular occurrence. Verify that installed/source shell QML and both QSB shaders match. Keep production code and the installed executable unchanged; use disposable QML, workbook and settings copies for each desktop fixture. No screenshots or videos are persisted.

Extend `scripts/diagnostics/window_responsiveness_probe.py` with optional geometry tracing, cycle count, screen selection and diagnostic-only native topmost placement. Trace content-to-global coordinates at source/target preparation, animation completion, live reveal, overlay release and finish. Timestamp capture uses QML arrays collected once, without per-frame Python render-thread callbacks. Native topmost placement keeps the disposable app unoccluded and disappears when its process exits. Label other motion so later minimize/close frames cannot be confused with the preceding restore.

Extend `desktop_pixel_tracker.py` with optional DXGI output selection, cropped single-pixel sampling and a requested sampling interval. Crop coordinates remain relative to that DXGI output; native window rectangles remain desktop coordinates. The existing full-output two-pixel sampling defaults are preserved. Cropped readings retain integer-pixel precision and reduce capture analysis cost. The built-in output starts at native desktop x=3840. Marker edges represent the rasterized image, including sampling/antialiasing; they are not proof that every point in the entire window translated by one pixel.

| Run | Result |
| --- | --- |
| 100% geometry, 24 primary toggles plus lifecycle | Pass; native/content coordinates are stable at the restore handoff. |
| 225% geometry, 10 primary toggles plus lifecycle | Pass; actual mapped content origins differ fractionally from nominal rounded targets but stay stable through handoff. |
| 100% unoccluded cropped pixels, 10 primary toggles plus lifecycle | Pass, zero watchdog timeouts; five completed primary restores have identical marker edges before/after handoff. 586 desktop samples, median read 6.613 ms. |
| 225% unoccluded cropped pixels | Overall strict fixture fails four watchdog timeouts. Three normally completed primary restores supply repeated, stable before/after observations of a one-pixel marker edge change. These observations establish the mismatch, not a passing high-DPI lifecycle or performance gate. 659 desktop samples, median read 35.495 ms. |
| Disposable target-position alignment experiment | Rejected. Overall strict fixture fails two watchdog timeouts. Correcting target bounds from actual `mapToGlobal()` fixes the horizontal component at the second position, but the one-pixel vertical edge change persists across four normally completed restores. No production change is retained. |

An initial 100% pixel attempt is also failed: no source marker was detected before the first command because the live window was occluded. It additionally hit two watchdog timeouts. Adding diagnostic topmost placement and limiting collection to 20 requested samples/second resolves the source-visibility problem in subsequent runs. Sampling still adds load, especially at 225%; do not quote these pixel runs as normal app responsiveness measurements. A diagnostic assertion logged as CRITICAL is the fixture rejecting its results, not evidence of a production backend crash.

## Reproduced small change

At the first high-DPI restored position, the marker's stable edge changes from output pixel `(261,208)` to `(261,207)` at release. Two normally completed restores reproduce this. Their native window rectangle remains `(4040,146,2338,1424)` in every compared sample. At another position the marker changes from `(362,253)` to `(363,252)`, while the native window rectangle remains `(4142,191,2338,1424)`. These are `GetWindowRect()` measurements expressed as x, y, width, height. The horizontal component therefore depends on the restored placement. Several stable samples occur on each side of the handoff, separating this from the ordinary final approach of the animation.

The 100% comparison observes `(271,118)`, `(316,138)` and `(361,158)` remaining identical across the handoff, in five primary restores. The observed scale/placement dependence plausibly explains an intermittent perceived shift. It does not prove which monitor or exact occurrence the user reported; optional timing/display clarification and real-app acceptance remain open.

Nonsensitive coordinate/count evidence: [RESTORE_INTERMITTENT_SHIFT_RESULTS_2026-10-02.json](RESTORE_INTERMITTENT_SHIFT_RESULTS_2026-10-02.json). Full local traces remain in the matching ignored `logs/restore_shift_*` folders.

## Diagnosis and next correction

The evidence locates the mismatch at replacing the endpoint image with the live scene. `DetachedShellWindow.qml` currently captures `contentLayer` locally and places that texture using rounded logical target coordinates. At 225%, `mapToGlobal()` reports actual content origins such as `(3937.8889,73.8889)` for nominal `(3938,74)`, or `(3983.2222,93.8889)` for nominal `(3983,94)`. These are fractional physical-pixel differences. The offscreen image, the fixed transition window and the padded live window also have separately rounded framebuffer dimensions; the shader samples the capture through normalized UVs and smooth/mipmap filtering.

The leading explanation is a difference in rasterization/sampling grids between capture/replay and the native live scene. Position correction alone is demonstrably insufficient: the disposable experiment removes the horizontal difference but leaves the vertical one. Do not promote a blanket rounding tweak, longer timer or additional arbitrary frame count as a fix. The existing readiness gates already submit the final image and live window; those gates do not establish their pixel equality on fractional-DPI displays. Qt describes frameSwapped as queued presentation, not physical scanout. [Qt QQuickWindow frameSwapped documentation](https://doc.qt.io/qt-6.10/qquickwindow.html#frameSwapped)

Next scoped work: make the endpoint capture/replay use the same physical origin, framebuffer dimensions and sampling grid as the live target, then add a real high-DPI two-window handoff regression. Evaluate a capture that preserves the live host's rasterization phase, rather than a local content capture that is resampled again. Preserve the accepted fixed-size title/glyphs, early start, existing workspace, readiness gates, monitor movement and watchdog. Require identical final pixels on both 100% and 225% displays at several restored placements, plus a clean unoccluded repeated lifecycle run, before installing a correction. No application implementation of this proposal is made here.

## Reproduction and validation scope

Run with the project venv, outside a WebEngine-restricting sandbox. The collector requires `dxcam`/NumPy; on this machine they are isolated under ignored `logs/responsiveness_pixel_dependencies` rather than added to production dependencies. Confirm Qt screen and DXGI output indices before using a different computer.

```powershell
$env:CSPM_PIXEL_DEPENDENCIES = (Resolve-Path logs/responsiveness_pixel_dependencies).Path
$env:CSPM_PIXEL_REGION = '0,0,800,500'
$env:CSPM_PIXEL_INTERVAL_MS = '50'
$env:CSPM_PIXEL_OUTPUT = '1'
python scripts/diagnostics/window_responsiveness_probe.py --geometry --pixels --keep-visible --screen-index 1
```

For the 100% primary comparison, select output/screen 0 and crop `0,0,700,400`. `--cycles 24` extends repeated toggles; the strict fixture rejects watchdog timeouts, source occlusion, missing cycles and functional failures. Preserve failed runs as failed evidence.

Sandbox-safe checks: both changed diagnostic scripts compile and whitespace checks pass. Outside-sandbox runtime checks: the source desktop/geometry/cropped-pixel runs above; failures are explicitly retained. No new dedicated WebEngine HTML/PDF rendering probe or packaged startup test is run because application code/runtime is unchanged. The preceding release's WebEngine results are historical. Protected workbooks and authoritative settings remain unchanged. No application fix, deployment or recompilation is performed. P0 remains open for this same restore defect; do not advance to another visual state machine.
