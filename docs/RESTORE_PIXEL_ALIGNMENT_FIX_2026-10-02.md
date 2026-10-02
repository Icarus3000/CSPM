# Restore endpoint pixel alignment correction — 2026-10-02

The user authorizes fixing the intermittent restore nudge and previously requests Git publication and executable recompilation. Both executables are rebuilt and the complete package is installed at `C:/Programs/CSPM`. Real-app visual acceptance is still required before leaving P0.

## Resulting implementation

The earlier investigation reproduced a one-pixel marker-edge change at 225% DPI when the captured endpoint disappeared and the live window took over. Native window coordinates stayed fixed. A target-position-only experiment left the vertical mismatch; a whole-root item capture still differed from native rendering around a small number of antialiased edge pixels. Both incomplete attempts are rejected.

`backend/window_frame_capture.py` reads `QQuickWindow.grabWindow()` only at the source and target capture gates on the GUI thread. It publishes each QImage through a short-lived in-memory Qt image provider. Images retain their exact physical dimensions and are never resized by the provider or written to disk. Release/cancellation clears provider entries; QML image caching is disabled for these unique transient URLs. The engine exposes this service before loading the application QML. A failed capture returns to the existing completion fallback.

`DetachedShellWindow.qml` retains the same workspace, captures its entire native rendered frame including transparent padding, and records the content's normalized location inside that frame. The fixed transition surface maps captured physical frame dimensions and native desktop origins to its own actual framebuffer dimensions. On Windows, read actual client origins and sizes through `ClientToScreen()`/`GetClientRect()` after creating the hidden native surface, before showing any transition pixels. This replaces an insufficient predictive rounding formula at monitor boundaries. Reactive bindings use the resulting fixed native geometry. This does not change saved restore coordinates or constrain monitor selection.

Both shader uniform blocks and baked QSBs carry source/target content UV rectangles. Moving frames retain the established fixed-size header mapping. At exactly progress zero or one, sample the corresponding native frame directly; borders, padding and antialiased text do not pass through intermediate header/body remapping. The temporary host stays fixed. Early movement and all production submitted-frame gates, animation durations and the 3500 ms watchdog are unchanged. The old content capture remains a diagnostic comparison switch; production defaults to native frames. The title stamp is `PIXEL ALIGNED HANDOFF`.

Qt documents both GUI-thread restriction and performance cost for `grabWindow()`; validate this cost rather than assuming it is free. [Qt 6.10 QQuickWindow documentation](https://doc.qt.io/qt-6.10/qquickwindow.html#grabWindow)

## Validation completed before packaging

- Sandbox-safe: changed Python/diagnostic files compile; 40 focused window-state/choreography/corner/layout/feedback tests pass; governed QML lint exits zero with warning-level diagnostics; shader baking and whitespace checks pass.
- Outside sandbox, GPU: both opt-in tests pass. The original 18 intermediate/endpoint samples preserve title marker dimensions and exact endpoints. The new two-window comparison passes 18 cases across all three attached screens (100%, 225%, 100%), two sizes and three placements including a window straddling a monitor boundary, with maximum channel error zero. The expanded run rejected predictive coordinate rounding; actual Windows client geometry removes that mismatch. Pixel images stay in RAM. The test also requires the provider pool to be empty after each release.
- Outside sandbox, full populated app at 225%: the final held-endpoint pixel run passes six primary toggles plus lifecycle without any watchdog timeout. All three primary restores have identical marker x/y/width/height before and after handoff, with two repeated stable readings on each side and unchanged native rectangles. Positions include `(261,207,39,34)` and `(363,252,38,37)` in DXGI output pixels.
- The pixel fixture inserts a **diagnostic-only 250 ms endpoint hold**, collects a 600x360 crop at a requested 80 ms interval, and keeps only its disposable HWND above other windows. The hold is absent from production and cannot supply normal performance timings. This isolates stable endpoint equality from the prior diagnostic's too-short sample interval.
- Outside sandbox, matched timing without a hold or pixel collector: a same-process 20-toggle comparison alternates content/native capture in pairs. All 23 transitions including lifecycle pass with no watchdog timeout. Maximize start-notification medians are 286/219 ms (content/native), restore 296/301 ms, each five samples. Complete transaction medians are 1675/1565 ms and 1727/1691 ms respectively. These are GUI notifications of submitted frames, not physical mouse-to-photon measurements. Observed scheduling load differs from the preceding release's absolute timings; the new comparison establishes no material restore-start regression within this run.

Earlier native-frame DXGI runs fail the strict fixture with watchdog timeouts and insufficient stable endpoint samples. Preserve them as failed stress evidence. A successful later lower-load held run does not establish immunity to load-related timeouts. The unmodified watchdog/readiness gates remain in force.

## Reproduction

Use the project venv outside a WebEngine-restricting sandbox:

```powershell
$env:CSPM_RUN_WINDOW_GPU_TESTS = '1'
python -m pytest -q tests/test_window_settlement_render.py
python scripts/diagnostics/window_responsiveness_probe.py --compare-capture --keep-visible
$env:CSPM_PIXEL_DEPENDENCIES = (Resolve-Path logs/responsiveness_pixel_dependencies).Path
$env:CSPM_PIXEL_OUTPUT = '1'
$env:CSPM_PIXEL_REGION = '0,0,600,360'
$env:CSPM_PIXEL_INTERVAL_MS = '80'
python scripts/diagnostics/window_responsiveness_probe.py --geometry --pixels --keep-visible --screen-index 1 --cycles 6 --endpoint-hold-ms 250
python scripts/diagnostics/check_window_handoff_pixels.py logs/<audit-label>
```

Confirm screen/output indices on another computer. The primary comparison selects screen/output 0. Geometry, collector interval, endpoint hold and comparison switches affect disposable copies only; no practice workbook or authoritative setting is edited.

## Release continuation

Final actual-native-geometry full-source pixel runs pass on both the 225% and 100% displays. Each completes six primary toggles plus lifecycle (nine transitions), without a watchdog timeout. All three primary restores per display have equal marker x/y/width/height in repeated frozen/live readings and unchanged native rectangles. These final runs retain the diagnostic-only 250 ms hold and are endpoint/lifecycle evidence, not performance benchmarks. Aggregate coordinates/counts and the matched timing rows are recorded in `RESTORE_PIXEL_ALIGNMENT_FIX_RESULTS_2026-10-02.json`.

The full main/recovery build passes approved-template and bundled-confidentiality gates. Main EXE: 9,190,747 bytes, built Friday October 2, 2026 at 17:11:54 Toronto time, SHA-256 `0CF9EC7923DE3F0E84ACC1B0EE9608E51868CED11B23522D511BEFE6B17F9F11`. Recovery EXE: 2,170,513 bytes, built at 17:13:40, SHA-256 `091249F152E1E184E4EB84CD40EF15A2CD5829BEA414EEACD1BAF034E1CBDFF8`. Preserve the previous installed package at `to_delete/installed__before_pixel_alignment_release_20261002`; its main EXE matches the preceding release hash. The previous dist package is quarantined at `to_delete/dist__replaced_release_20261002_171342`.

Outside sandbox, the compiled candidate passes startup in 17.93 seconds and four title-bar maximize/restore invocations through Windows UI Automation. The real transition HWND is observed appearing and retiring on every toggle; both restores return to the exact initial native rectangle and native caption style remains absent. The installed package passes the same checks, with startup in 27.92 seconds. These are functional smoke tests on the 100% display, not physical mouse-to-photon or visual acceptance measurements. No desktop cursor movement is needed.

The packaging diagnostic previously waited for a QML debug completion line that is not persisted in the windowed release's runtime log. Those attempts remain failed diagnostic runs; they do not establish an application transition failure. The corrected diagnostic observes the actual transition HWND lifecycle and restore geometry rather than relying on debug logging. Startup-only validation also leaves the desktop cursor alone.

Actual outside-sandbox WebEngine rendering passes against both candidate and installed packages using their own helper executable/resources/locales. Both load disposable HTML and produce a valid 41,201-byte PDF. Chromium emits a nonfatal display-layout message; rendering still completes successfully. Tests use disposable profiles/data, not authoritative workbooks or settings.

The complete installed/candidate comparison passes for all 4,377 runtime files / 679,044,943 bytes. All 168 source/bundled QML files match, and protected workbook/settings hashes are unchanged. Git publication is pending. Real-user P0 acceptance remains open: repeat restore at several positions on both display scales and confirm no nudge, title/font change or responsiveness regression.
