# Professional maximize/restore candidate and continuation handoff — 2026-10-02

## Status and user instructions

This is a **candidate awaiting the user's visual acceptance**, not a declaration that silky motion is achieved. The user requested continued implementation, an EXE rebuild at the next manual-check boundary, and commit/push with enough history for another Codex instance on another computer. That explicitly authorizes packaging this candidate before visual acceptance. Do not move to another visual state machine until this P0 gate is accepted.

Read AGENTS.md's four startup documents in order, then the visual FX handoff and the actual current `logs/cspm.log`. This document supersedes the implementation/status descriptions in older motion handoffs; those documents remain evidence of rejected attempts. Preserve the Option 3 shell direction and future migration roadmap.

Keep the user's custom title bar/glyphs and approved opening, closing, minimizing, and taskbar-return effects. Preserve workspace and unrestricted restored movement across **all monitors, DPI values, resolutions, and negative desktop origins**. Diagnostic placement on the primary monitor must never become an application restriction. The user wants substantive progress updates every 30–45 seconds, with no long silent periods.

## Implemented candidate

- `DetachedShellWindow.qml` now routes the enabled Professional custom transition to `captureProfessionalTransitionSurface()`. Existing monitor selection/restored movement code and native bridge are retained. The native path remains disabled, as in Gemini's preceding release.
- `WindowTransitionSurface.qml` holds **one captured image of the existing contentLayer**, retaining its grab result for image lifetime. It does not instantiate `MainContent`, another report, or another workspace.
- The temporary transparent, input-transparent, nonactivating frameless window covers the union of source and target rectangles and stays at that exact rectangle for the entire transaction. No visible HWND resize occurs during its motion or handoffs.
- Three actual submitted source frames and image readiness gate hiding the original window. Render-thread `UniformAnimator` interpolates one shader quad over 220 ms with OutCubic easing. Target host/layout preparation occurs hidden underneath after the first motion frame.
- Two submitted frames from the original target scene gate readiness. After motion completion, two more surface frames gate revealing the original. A 90 ms opacity blend changes from the scaled source image to the actual responsive target layout; three final surface frames gate removal.
- The shader sources and baked Qt 6 QSB files are checked in under `src/qml/shaders`. Runtime shader baking is unnecessary. Rebuild both files with the current venv's PySide6 `qsb.exe --qt6 -o OUTPUT SOURCE` after changing their sources. Qt 6.10.3 was used here.
- Sequence checks reject stale capture callbacks; shared stop/finish cleanup destroys the surface and restores original opacity. A 3500 ms watchdog aborts an incomplete transaction. Input is gated while the transaction is active.
- Header identifies **BUILD 2026-10-02 WINDOW HANDOFF CANDIDATE**.

The earlier Gemini `professionalInWindowTransitionAnimation`, start/finish functions, and duplicate-content `MaximizeOverlay` fallback remain in the shell but are **not called by the enabled candidate path**. Do not confuse their timer or GUI-thread animation with the new frame-gated path. Their cleanup references remain in shared cancellation. Removing dormant code is deferred to avoid broad unrelated choreography changes before acceptance.

## What the latest measurements establish

Full-source testing ran outside sandbox, on the real Windows desktop, using disposable copies of local workbooks/settings. Eight colored corner/midpoint markers were injected into the actual contentLayer. A separate DXGI process sampled composited pixels in RAM and wrote coordinates only; no screenshots/video were saved.

The complete run made **10 toggles (five maximize/restore pairs)**, synthetic restored movement after pairs two and four, normal and maximized taskbar-return sequences, and maximized close. Functional failures: `[]`. Restored content remained exactly 1100x760; final restored origin was (410,180), reflecting the two synthetic moves. The same Productivity workspace remained open. Main native flags/style stayed frameless (`0x40004801`, `0x960a0000`), with zero native margins and a 12-pixel restored radius.

Unlike the preceding release, the measured paths no longer show old-size content jumping to (30,30) and back, or restored content displaced to (640,284) before correcting. The first maximize sensor moves from (338,158) toward (32,26), then the settled live target is (18,18). The first restore moves from (18,18) toward (332,154), then the settled live source is (338,158). The small end difference reflects source-image scaling versus real target layout and is blended; visual quality of that blend is still a user check.

**Remaining latency:** source readiness was approximately 100–168 ms after command; live target handoff approximately 665–823 ms; the entire transaction approximately 0.9–1.0 seconds. Motion itself is 220 ms. Whole-transaction surface swap gaps still reach 293–365 ms around hidden layout work after the moving image reaches its endpoint. Median surface swap intervals around 16.6–17.6 ms must **not** be reported as continuous 60 FPS or complete responsiveness. This candidate removes measured large presentation jumps but has not established the user's requested fast cinematic result.

Checked-in aggregate measurements: `MAXIMIZE_RESTORE_SENSOR_RESULTS_2026-10-02.json`. Missing exact-color markers during blending are recorded as missing, not counted as detections and not automatically interpreted as the entire window disappearing. Collector resolution is approximately two pixels and sampling approximately 30–45 Hz. Native style checks do not prove every possible activation/caption stress condition; synthetic movement does not prove physical mixed-DPI dragging.

## Attempt history: do not repeat failed work blindly

| Attempt | Outcome / distinction |
| --- | --- |
| Earlier duplicated MainContent overlay and fixed 16 ms readiness timer | Rejected. Recreated workspace/layout and exposed host preparation/settlement. The new surface captures existing pixels, uses no duplicate workspace, and gates on submitted frames. |
| Native Windows-owned maximize/restore bridge (`5cf73ea` release) | Functional geometry/lifecycle tests passed, but user and pixel measurements rejected motion. Native-frame/titlebar leakage was also reported. Opening success never validated maximize. |
| Native frame refresh/NC suppression, margins, copy-bits protection, normal placement | Preserved bridge experiments did not remove measured pre-jump. See `MAXIMIZE_RESTORE_DIAGNOSTIC_HANDOFF_2026-10-01.md`. |
| Opaque surface, Qt repaint/expose/redraw variants, OpenGL, D3D12, single-thread render loop, system commands/deferred calls, isolated Qt 6.11.2 | Rejected in full-app testing; historical functional pass was insufficient. See the visual FX audit and task ledger. Do not promote ignored prototypes. |
| DWM thumbnail / independent GDI host | Thumbnail clipped; GDI had delay/handoff artifacts. Neither accepted. |
| Cached/batched metrics, stable QtObject proxy, disabled redirection surface | Did not remove pre-jump; reverted/kept diagnostic only. |
| Gemini `3ea0d7d` in-window transform | User rejected. Fresh 629-sample run reproduced preparation jump and restore displacement. Gemini's own CSV was header-only after DXGI AccessDenied, so its motion-success/60-FPS claims are superseded. Detailed review: `MAXIMIZE_RESTORE_GEMINI_REVIEW_2026-10-02.md`. |
| Current surface with second target capture | First local version completed too slowly (~1.3 s), rejected a subsequent toggle, and incurred unnecessary capture latency. Replaced by readiness from the actual original target window. |
| Current surface with direct frame update requests | Later restore stalled. Queuing requests through Qt.callLater avoids coalescing into the frame still ending, but alone did not solve the repeat-use gate. |
| Current surface requiring ShaderEffect.Compiled | First maximize worked; repeated cached shader rendered with status Uncompiled, so restore timed out. Gate now checks image readiness, actual submitted frames, and absence of ShaderEffect.Error. Temporary console diagnostics removed. |
| Current final frame-gated surface | Ten toggles plus lifecycle passed; eight-sensor data removes the previously measured large jumps. Full speed/smoothness and all-monitor physical acceptance remain pending. |

Local ignored artifacts are under `logs/native_maximize_fix_20261001/`: `review_ready_*`, `surface_*probe*`, `surface_*pixel8*`, `surface_complete_*`, final lint/build logs, and keep-awake state. These are **not in Git**. The aggregate results, review, this history, and the portable diagnostic are in Git so another machine has the essential evidence without private workbook copies or diagnostic dependencies.

## Reproduce on another Windows computer

Use this branch and its latest pushed commit, the repository venv, and matching PySide6.10 runtime. Governed release package includes both new QSB shaders because the builder bundles the entire QML tree.

`scripts/diagnostics/window_transition_probe.py` is the portable full-source runner; `pixel_tracker_process.py` launches `desktop_pixel_tracker.py` separately. Install **diagnostic-only** `dxcam`, `numpy`, and `comtypes` into an isolated directory, then point `CSPM_PIXEL_DEPENDENCIES` at it. They are not production requirements.

PowerShell example (replace the venv path with the local machine's):

```powershell
$python = '.venv_OFFICENEW_Cory/Scripts/python.exe'
& $python -m pip install --target logs/pixel_dependencies dxcam numpy comtypes
$env:CSPM_PIXEL_DEPENDENCIES = (Resolve-Path logs/pixel_dependencies).Path
& $python scripts/diagnostics/window_transition_probe.py
```

Run unlocked on an interactive desktop **outside sandbox**. The fixture reads `%LOCALAPPDATA%/CSPM/data/{CSPM,Dockets}.xlsm` and user settings, copies them into ignored `logs/window_transition_diagnostic/disposable_profile`, and points local/master/runtime directories at those copies. It uses a **1920x1040 primary work-area fixture with restored bounds (320,140,1100,760)**; adapt fixture settings/DXGI output mapping for a different monitor arrangement. It deliberately pins only the fixture's launch context; production movement has no such restriction. Do not use it against live checkout/edit operations.

The runner exits nonzero for functional failures or insufficient actual pixel samples, including a header-only CSV or no detected source marker before the first command. It waits seven seconds for collector startup; increase only if the collector baseline proves initialization missed the first transition. Outputs: coordinate/command CSVs, frame trace, functional results JSON, and collector log. Inspect coordinates over the **whole** transaction, not just final state or a selected frame average. The pass result alone still does not assert motion continuity.

## Manual acceptance and next work

1. Run the rebuilt installed candidate and confirm the header. Repeat maximize/restore with a populated workspace; check initial position, speed, smoothness, final blend, rounded corners without moving, and absence of a native caption after many cycles.
2. Drag the restored window physically to every connected monitor, especially differing DPI/resolution and negative origins; maximize and restore on each. Check size, glyphs, workspace, and no position jump. Current automated fixture has **not** accepted these cases.
3. Check the approved opening, closing, minimize, and normal/maximized taskbar-return effects remain satisfactory. Calendar fix remains in source; the focused date-selection/filter tests pass.
4. If the candidate still feels slow, inspect hidden target layout/reflow costs and endpoint hold before changing duration. Do not make the movement slower to conceal stalls, move/resize the visible surface, or reuse the old duplicate-content solution without explaining the difference and measuring it.

Invoice 26-0092 was already reconciled/published before this work, with active-directory exclusion and reversal evidence. Do not reverse it again. No live invoice or seed workbook changes belong to this motion release.

## Validation, build, deployment, and Git

Static/sandbox-safe: 44 focused tests passed; diagnostic Python compilation passed; governed QML lint passed with warnings; shader baking passed. Outside-sandbox: real full-source desktop transitions and actual pixel sampling. The first standalone WebEngine PDF probe timed out while packaging; a repeat after packaging loaded HTML and rendered a valid 17,199-byte PDF. The portable full-source diagnostic also completed successfully with actual coordinate data.

Packaged executable startup reaches a visible ready main window with disposable data. Attempts to exercise its controls using posted messages and OS mouse input did **not** reach the maximize handler. Direct inspection showed the source control interactive and correctly positioned; the instrumented OS attempt showed SetCursorPos returning 0 with the cursor remaining (960,540). The input attempts are not application transition failures and are not packaged motion passes. `scripts/diagnostics/packaged_window_smoke.py` therefore defaults to startup validation; `--transitions` additionally exercises buttons on a desktop allowing cursor movement, and rejects denied cursor positioning explicitly. The fixture assumes this primary 1920x1040 arrangement. Source/dist QML and both QSB hashes match. Final deployment/hash results are recorded in `implementation.md`. Do not conflate startup success, native style, or functional bounds with motion acceptance.

Release command: `python scripts/build_release.py --validate --no-deploy`. Main/recovery builds and template checks completed; the builder's fallback move succeeded after Windows denied the initial staging rename. Packaged startup passed in 9.18 seconds. Deployed with the normal builder helper to `C:/Programs/CSPM`, preserving existing data/backups/logs. Installed/dist main and recovery EXE hashes, and source/dist/installed changed QML and both QSB hashes, match. Provenance: `MAXIMIZE_RESTORE_RELEASE_2026-10-02.json`. These are this build's byte hashes, not a promise of identical EXEs/line endings on another computer. Code, tests, diagnostic, measurements and handoff were committed together as `90a7725` and pushed successfully to `origin/fix/invoice-billing-client-correction-20260926`. This follow-up ledger records confirmed publication. The user visual acceptance gate is still open.

Temporary keep-awake helper requested system/display wakefulness and disabled the screensaver, without changing persistent power plans. It is now stopped; `keep_awake_tests.json` reports `active:false` and restoration of the originally enabled screensaver. If using it again, create `logs/native_maximize_fix_20261001/keep_awake_tests.stop` at testing completion and verify restoration. It also has an eight-hour failsafe. Check actual current state on each computer rather than assuming any old helper is still running.
