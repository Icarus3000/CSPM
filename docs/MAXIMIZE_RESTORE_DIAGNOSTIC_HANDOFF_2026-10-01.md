# Maximize/restore diagnostic handoff — 2026-10-01

## Current result

The maximize/restore motion defect remains unresolved. Do not represent the current native-frame candidate, passing functional tests, or installed executable as a visually accepted fix. The user reports upper-left movement before maximize, jerky restore, and a native title bar behind the custom shell after repeated cycles. The opening animation is already smooth; its visible presentation is a useful comparison, not evidence that maximize must remain jerky.

Startup reading and priority remain defined by AGENTS.md. Read the current runtime log before proposing fixes. Preserve custom chrome, approved opening/closing/minimize/taskbar animations, the existing workspace, and restored movement across every monitor/DPI/resolution/desktop origin. Primary-monitor-only placement is diagnostic only. User authorized implementation, executable rebuild, commit, and push; visual acceptance is still pending.

## Current uncommitted changes

- `src/python/platform/native_window_state.py`: native caption/activation handling, frame-refresh copy-bits protection, release ordering with geometry ownership held through frame changes, authoritative normal placement on restore, and DPR-aware minimum track size. These are candidates; they have NOT eliminated the measured pre-jump. Native title-bar leak has not yet been physically confirmed fixed.
- `tests/test_professional_native_window_state.py`: focused tests for the above native contracts (17 passing). These do not establish smooth presentation.
- `src/qml/views/WIPBillingWizardView.qml`: confirmed calendar lifetime fix. JellyCalendar hides itself before emitting datePicked; synchronous Loader unloading destroyed it before the selection reached the workbench. Unloading now waits until Qt.callLater.
- `tests/wip_calendar_probe.py` and `tests/test_wip_calendar_selection.py`: actual offscreen QML date selection verifies both displayed fields, inclusive table filtering, reopening, cancellation, and no orphan calendar. Failed before the fix, passes afterward. No live practice data writes.
- `task.md`: captures the three reported release regressions.
- `DetachedShellWindow.qml` metrics batching/stable-object experiments were rejected and reverted; a Git status entry can reflect line-ending normalization without a substantive diff. Inspect before editing.

## Strongest new measurements

Ignored local artifacts: `logs/native_maximize_fix_20261001/`.

Use `source_external_pixel_probe.py`, `pixel_tracker_process.py`, and `desktop_pixel_tracker.py`. Eight colored edge/midpoint markers are injected only in the disposable source fixture. A SEPARATE process reads composited primary-monitor pixels via DXGI Desktop Duplication and writes coordinates only. No screenshots or video are saved. The app uses disposable workbook/settings copies and keeps an open Productivity report. Collector dependencies are isolated under `pixel_dependencies`, not production requirements.

Latest output: `pixel8_external_collector.csv`, `pixel8_external_collector.commands.csv`, `pixel8_external_collector_run.txt`, `qt_frame_trace.json`, `state_profile_0.txt`, and `state_profile_1.txt`. Collector is approximately 30–45 Hz; exact-color tracking has about two-pixel resolution and missing markers are not proof that an entire surface vanished. This does not establish full 60-FPS quality.

Latest maximize (relative to command):

- Before: top-left marker (338,158), top-right (1384,158), bottom-right (1384,864).
- 16 ms: native outer rectangle already (-8,-8,1936,1056), while displayed markers retain old coordinates.
- 31 ms: top-left (82,60), top-right (1092,60), bottom-right (1092,742): old-size content near the upper-left.
- 198 ms: top-left (30,30), top-right (1076,30), bottom-right (1076,736).
- Qt finalWChanged at 85 ms, finalHChanged at 282 ms; first subsequent frame begins at 406 ms and swaps at 452 ms.

Restore: top-left moves toward restored coordinates, right/bottom markers are not found during the intermediate clipped presentation, and the first resized frame swaps around 409 ms. Full restored marker positions are detected at 450 ms.

Separate-process cProfile: 283 ms overall toggle, including approximately 273 ms inside QWindow.showMaximized. This identifies the call boundary containing the delay, NOT whether the time is Windows animation, synchronous QML callbacks, layout, or Qt internals. Do not assert a fully established root cause from cProfile alone. Earlier in-process collector timing was contaminated by observer/GIL overhead; use the separate-process data.

Functional source fixture completes normal/maximized taskbar cycles and maximized close with no recorded contract failures, but the pixel trace still fails motion acceptance. Existing movement tests use synthetic model movement, not complete physical header-drag/mixed-DPI validation.

## Rejected experiments

Read the complete historical list in `docs/VISUAL_FX_AUDIT_AND_HANDOFF_2026-08-20.md` before repeating anything. This session additionally rejected cached/batched uiMetrics, a stable QtObject metrics proxy, and QT_QPA_DISABLE_REDIRECTION_SURFACE=1: none removed the measured upper-left presentation. Do not promote these experiments or blindly reinstall duplicate MainContent overlays. A new approach must explain specifically what differs from a failed attempt and provide measurable evidence.

## Checks and release status

46 focused sandbox-safe tests passed, including the native contracts, close/taskbar choreography, restored corners, invoice lifecycle, real offscreen calendar selection, and date filtering. Governed WIP QML lint returned 0 with existing warnings. These checks do not validate physical motion or WebEngine rendering.

Outside-sandbox full-source fixture runs initialize the real application and perform native transitions with disposable data. Their final geometry/workspace checks pass while physical pixel movement fails. No new dedicated PDF/WebEngine rendering check, executable rebuild, deployment, or commit/push has occurred in this diagnostic session. The previous release and invoice 26-0092 repair remain completed; do not reverse or edit the live invoice again.

## Temporary keep-awake helper

At handoff, `keep_awake_tests.py` is active. It temporarily suppresses the screensaver and requests display/system wakefulness; it does not edit persistent power plans. State is recorded in `keep_awake_tests.json`, including the original screensaver setting. It has an eight-hour failsafe. At testing completion create `logs/native_maximize_fix_20261001/keep_awake_tests.stop`, then verify the JSON shows active=false and the original screensaver setting is restored. Check actual current state before assuming the helper remains active.

Provide substantive user updates every 30–45 seconds. State observations separately from hypotheses. Never equate correct final bounds, app startup, or passing unit tests with silky motion.
