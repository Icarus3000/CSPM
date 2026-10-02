# Gemini maximize/restore release review — 2026-10-02

## Result

The user rejects release commit `3ea0d7d` as still not working as desired. Fresh outside-sandbox source testing reproduces both a maximize preparation jump and a restore settlement jump. The smoothness acceptance gate remains failed. The repository ledgers' preceding claims that motion was fully verified are superseded by this review.

## Release and evidence verification

- Source, dist, and installed `DetachedShellWindow.qml` SHA-256 all equal `70CEBF98F6984CBA2D14030A7040947167ADADACF4346E42C0EF604CB41042E4`. The installed QML contains Gemini's implementation; this is not a stale-QML mismatch.
- Gemini's preserved `pixel8_external_collector.csv` contains its header only. Its collector log reports DXGI `DuplicateOutput` failing with `Access is denied`. Thus that run supplies no pixel-position evidence for the claimed elimination of jumps/clipping.
- `REGRESSION FAILURES []` checks final state, geometry, workspace, and transition completion. It does not assert continuous marker movement. The diagnostic checks native maximized state only when native ownership is active, accommodating the new in-window path.
- Frame-swap averages within selected animation intervals do not establish preparation or settlement quality. A regular sequence of swapped frames can still include wrong pixel positions or a later layout replacement.

## Fresh outside-sandbox reproduction

Ignored local driver: `logs/native_maximize_fix_20261001/review_ready_probe_20261002.py`. It uses disposable workbook/settings copies, pins diagnostic placement to the primary monitor, retains the Productivity workspace, attaches eight valid parent-relative markers to the actual content layer, and waits seven seconds for the separate DXGI collector to initialize. No screenshots or video are saved.

Artifacts: `review_ready_pixel8_20261002.csv` (629 samples, 453 with the top-left marker found), `.commands.csv`, `review_ready_frame_trace_20261002.json`, and `review_ready_run_20261002.txt`. Coordinates refer to this fixture's 1100x760 restored content at (320,140), with a 1920x1040 maximized target. Collector sampling is not a full 60-FPS guarantee; sensor disappearance alone does not establish the exact clipping boundary.

Maximize relative to command:

| Time | Top-left marker | Top-right marker x | Observation |
| --- | --- | --- | --- |
| Before / 15 ms | (338,158) | 1384 | Correct restored appearance |
| 60–97 ms | (30,30) | 1076 | Old-size content near upper-left after host changes |
| 123–143 ms | (338,158) | 1384 | Returns to original source rectangle |
| 162–359 ms | (272,130) → (32,26) | 1486 → 1858 | In-window expansion |
| 904 ms | (18,18) | 1884 | Final maximized layout |

Qt frame swaps have a gap from approximately 314 ms to 852 ms. During settlement finalX/finalY change at 315 ms, finalW at 407 ms, and finalH at 629 ms. This supports an exposed settlement delay; it does not assign every millisecond to a particular Qt internal operation.

Restore relative to command:

| Time | Top-left marker | Right/bottom markers | Observation |
| --- | --- | --- | --- |
| Before / 74 ms | (18,18) | Present | Maximized appearance |
| 104–324 ms | (86,48) → (332,154) | Present | Shrinking in-window motion |
| 505 ms | (640,284) | Not found | Host has contracted; stale content is displaced |
| 674 ms | (338,158) | Present | Correct final restored layout |

Qt frame swaps have a gap from approximately 266 ms to 645 ms. The host's x/y/width change around 506–507 ms and its height around 651 ms. Functional taskbar/close and workspace checks still finish with no recorded failures; physical maximize/restore motion fails independently.

## Code-level boundary problems

`startProfessionalInWindowTransition()` changes the native host envelope before a correctly compensated source frame is known to be displayed. The measured upper-left appearance followed by return to the source rectangle confirms this handoff is exposed.

`finishProfessionalInWindowTransition()` changes final dimensions, clears `maximizeAnimInProgress`, changes the content from its frozen source dimensions to the target dimensions, drops its transform/layer, and contracts the restored host. These operations occur without a confirmed presented target frame. The measured restore displacement confirms that correct transform interpolation alone is insufficient.

The next correction must handle these presentation boundaries and the layout replacement. Increasing animation duration or reporting an average FPS does not address them. Any revised design must explain how source pixels remain at their exact desktop position during host preparation and how complete target pixels arrive before removing compensation or contracting the host. Rejected native and duplicate-content overlay experiments remain relevant constraints; no new architecture is declared validated by this review.

## Scope and validation limits

No application code, executable, live workbook, or dependency requirements were changed. No unit/lint suite was rerun; repository diff whitespace verification is a static check. The reproduction ran outside sandbox with the full source application and disposable data; no new dedicated WebEngine page/PDF render check was performed. Native-title-bar leakage and physical all-monitor/mixed-DPI movement were not independently verified in this review. The previously stopped keep-awake helper remains stopped; the pixel collector clears its own temporary wakefulness request on completion.
