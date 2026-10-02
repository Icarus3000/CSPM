# Maximize/restore responsiveness candidate — 2026-10-02

The user accepted the title/glyph rendering and smooth final settlement, then reported the delay before movement. The subsequent request authorizes implementation, executable recompilation and Git publication. The preceding dependency analysis remains historical evidence: [responsiveness analysis](MAXIMIZE_RESTORE_RESPONSIVENESS_ANALYSIS_2026-10-02.md).

## Result and mechanism

Begin moving the accurately captured source image before preparing the resized target. In the completed same-process comparison, the median button-handler-to-first-submitted-moving-frame interval falls from 636/666 ms to 160/163 ms for maximize/restore. The total transaction still takes approximately one second; this change moves costly work out of the initial stationary wait rather than eliminating that work.

`DetachedShellWindow.qml` passes `professionalEarlyWindowMotionEnabled` to the fixed transition window. After its unchanged three source submitted frames, hide the original host and start a render-thread `UniformAnimator`. Its first submitted frame gates the original host's final geometry/layout assignment. Prepare and capture the target from the same existing workspace while the source image moves. Original target frames, captured-target frames, final image, live-host frames and release frames retain their readiness gates. The 3500 ms handoff watchdog is unchanged.

`WindowTransitionSurface.qml` separates preparation movement from final settlement. Preparation advances toward 85% over 800 ms; when the final captured texture has passed its readiness gate, a 220 ms settlement factor combines the current preparation position with the exact endpoint. It starts with zero derivative and continues preparation movement, preserving position and velocity at target readiness. At settlement factor one, the shader owns the exact target geometry/pixels. Stop both animators on cancellation and release.

Both shader uniform blocks and baked QSB files include the new factors. The fragment shader samples source pixels alone until settlement begins; it then completes the target-layout blend before the end. The existing fixed-size header mapping is retained throughout. Body content can be transformed during motion, as in the preceding release; subjective appearance still requires real-app acceptance. The diagnostic switch retains the earlier ordering for comparison; production defaults to early movement. The title stamp reads `EARLY MOTION CANDIDATE`.

No second workspace is created. Target captures, report instances, native ownership, monitor geometry, interaction guards and saved layout behavior retain their existing contracts. No stable-metrics cache, lazy prompt rewrite, mask removal, native geometry deferral, transition-window pool or capture-readiness shortcut is promoted. Those local experiments did not establish a reliable benefit or failed lifecycle checks.

## Measurements and limits

Outside-sandbox desktop fixture `responsiveness_watchdog_trace_20261002` alternates the preceding and new ordering in pairs in the same app, on the same populated Productivity report. It completes 20 primary toggles plus three additional transitions, restored movement, taskbar returns in both states and maximized close. Functional failures and watchdog timeouts are zero. The display is 100% DPI, with 1414x832 restored content and 1920x1032 maximized content. It is different from the earlier 225% analysis; compare the paired rows below, not the absolute numbers across display configurations.

| Ordering | Direction | Samples | Median start notification | Median completed handoff | Median geometry commit |
| --- | --- | ---: | ---: | ---: | ---: |
| Earlier | Maximize | 5 | 636 ms | 1035 ms | 252 ms |
| Early movement | Maximize | 5 | 160 ms | 1150 ms | 255 ms |
| Earlier | Restore | 5 | 666 ms | 1046 ms | 173 ms |
| Early movement | Restore | 5 | 163 ms | 1021 ms | 145 ms |

The separate completed ten-toggle candidate run (`responsiveness_final_source_20261002`) has start-notification medians 209/257 ms and completed-transaction medians 1329/1391 ms. Scheduling and load vary. These tests invoke the actual QML button handler through its `clicked` signal and timestamp GUI handling of submitted frames. They do not time physical mouse input, compositor presentation or monitor scanout. The proposed 100 ms warm/150 ms first-use goal is still unachieved.

Retained nonsensitive paired timing evidence: [comparison timings](MAXIMIZE_RESTORE_RESPONSIVENESS_FIX_TIMINGS_2026-10-02.json). The portable fixture is `scripts/diagnostics/window_responsiveness_probe.py`; it instruments a disposable copy of QML and uses disposable workbook/settings copies. Per-frame Python render-thread observers and 5 ms polling are disabled. Optional desktop coordinate collection remains a separate process and saves no screenshots.

Reproduce from the repository root with the project venv activated, outside a WebEngine-restricting sandbox:

```powershell
python scripts/diagnostics/window_responsiveness_probe.py --compare
python -m pytest tests/test_window_settlement_render.py
python scripts/diagnostics/packaged_window_smoke.py --exe C:/Programs/CSPM/CSPM.exe --startup-timeout 120
```

The timing fixture rejects functional failures, any handoff watchdog timeout, missing transitions or an incomplete cycle count. It records cancelled-transition stages if the watchdog fires. The optional `--pixels` collector requires desktop-duplication dependencies and access; its failed loaded run supplies no performance guarantee.

Earlier runs are retained as failures: the first final comparison and the optional desktop-pixel run each hit two 3500 ms watchdog timeouts. Their final states passed, but their timing runs fail strict acceptance and supply no release performance claim. The optional collector also added substantial sampling overhead. The cause of those intermittent stalls is not established; the subsequent comparison passes without changing the watchdog or readiness gates. Do not describe the candidate as immune to slow-machine/load-related timeouts. A GPU probe first exceeded its 45-second fixture deadline during expensive Python pixel comparisons; replacing millions of temporary QColor allocations with an equivalent full-RGBA comparison makes the complete rerun pass.

## Validation

Sandbox-safe checks: 38 focused tests covering window ownership, maximize/restore/close choreography, restored corners and layout persistence pass; governed `scripts/qmllint.ps1` returns zero with existing warnings; diagnostic compilation, shader baking and whitespace checks pass. Do not launch `qmllint.exe` directly.

Outside sandbox: the GPU shader regression passes 18 samples covering both orderings, both directions, source-only preparation, target blending and exact endpoints. Each title marker remains 12x13 pixels, and every endpoint channel matches exactly (maximum difference zero). The two completed full-source desktop runs above pass functional lifecycle checks with no watchdog timeout. These checks preserve the accepted endpoint contract but do not replace subjective movement or physical mixed-DPI acceptance.

Full main/recovery recompilation passes with `scripts/build_release.py --validate --no-deploy`, including approved-template and confidentiality gates. Main EXE: 9,186,663 bytes, compiled at 2026-10-02 14:13:29 Eastern. Recovery: 2,170,513 bytes, compiled at 14:14:55. Previous dist is retained at `to_delete/dist__replaced_release_20261002_141455`. Candidate outside-sandbox startup passes at 31.82 seconds to input-ready on disposable data. The full package is deployed through `deploy_to_programs()` to `C:/Programs/CSPM`; the previous installed runtime is retained at `to_delete/installed__before_responsiveness_release_20261002`.

Installed outside-sandbox startup passes at 55.09 seconds on disposable data. The harness closes its main window, then stops its remaining tray fixture; this is a startup/readiness/window-close check, not a clean event-loop exit assertion. Actual installed WebEngine loads HTML and produces a valid 41,201-byte PDF using the packaged Chromium helper/resources/locales. Chromium emits a display-layout diagnostic; rendering still passes. No new installed-binary animation timing or physical cursor automation is claimed.

Full manifest verification matches 4,372 runtime files / 678,992,015 bytes between dist and installed runtime, excluding preserved data/logs/backups. All 168 QML-tree files match source. Protected workbook and authoritative settings hashes remain unchanged. Main EXE SHA-256: `0E08CA4446F196875128EAB6E3329A06C7E1B43B6496B5572C55CB47097D96A9`. Recovery SHA-256: `8D92D2A46429143E3305031749EB2E532DAA580D8E25D9AC0F25D95C0EE5252B`.

Local release evidence: `logs/responsiveness_release_20261002_build.log`, candidate/installed smoke logs and result JSON, backup/deployment logs, WebEngine result/PDF and `responsiveness_release_20261002_verification.json`. These remain separate from the source timing runs. Git publication targets `origin/fix/invoice-billing-client-correction-20260926`; the actual pushed commit will be recorded after remote verification.

## Next manual gate

Run the rebuilt installed application and compare the delay before movement in both directions. Confirm that the accepted title/glyph size and smooth final settlement remain clean, including the populated report. P0 stays open for that feedback, caption stress and physical mixed-DPI/all-monitor movement. If responsiveness is still insufficient, the remaining work is the synchronous resized layout and first-frame cost, followed by a proven GPU texture architecture. Do not advance to another visual state machine until the current path is accepted.
