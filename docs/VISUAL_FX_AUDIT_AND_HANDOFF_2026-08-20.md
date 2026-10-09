# Visual FX Audit and Continuation Handoff

Status: Active user-directed priority as of 2026-08-20.

## Latest continuation point — 2026-10-03

Complete user-requested handoff: `docs/MAXIMIZE_RESTORE_COMPLETE_HANDOFF_2026-10-03.md`. It consolidates the silky, smooth, flowing, gliding, elite, premium objectives, documented attempts and current status. This handoff does not introduce a new animation fix or validation result.

**Hard user acceptance requirement:** maximize/restore must be one uninterrupted smooth movement from start to finish, including the captured-image/live handoff. No perceptible pause, restart, jump, jerk or separate final settling movement. Faster timing only qualifies when this complete continuity is preserved.

Latest feel clarification: it must **flow like plasma or water** and cannot be jarring. Smooth changes in speed and arrival must preserve that fluid feeling through target readiness and live handoff. This is a requirements update only; the faster implementation remains unresolved.

The user explicitly identifies CSPM's existing opening and closing animations as **perfectly smooth and flowing**. Preserve them and use their accepted uninterrupted movement and final arrival as the in-app visual benchmark for maximize/restore. Recording this benchmark does not establish a new implementation or validation result.

Follow-up component profiling is attempted but remains inconclusive: source-frame watchdog/state/overall-timeout failures and stalled control/native-render fixtures do not produce a usable target-layout profile. Preserve failed/incomplete evidence, exclude it from prior passing aggregates, and do not adopt the diagnostic elapsed-time animation driver. No production/dist/installed change or new smoothness/WebEngine acceptance is obtained. Restore reliable desktop profiling before attributing the measured target-layout cost to a specific component.

The user accepts smooth maximize from a smaller window, requests at least 3× speed and explicitly requires KDE/Fedora-style continuous motion with natural deceleration. A matched 20-toggle comparison shows that shortening 800/220 ms timings to 240/65 ms improves complete maximize/restore by only 1.21×/1.45×. Target layout/rendering still dominates, and shortened preparation can end before target readiness. Reject the timing-only candidate and restore accepted production QML; installed/dist runtime is unchanged. Granular metrics, immediate capture, lazy prompts and metrics coalescing do not establish a useful gain. Retain only disposable comparison diagnostics and nonsensitive evidence. Read `docs/MAXIMIZE_RESTORE_SPEED_AND_SMOOTHNESS_ANALYSIS_2026-10-03.md` and the latest task/implementation entries. Threefold speed and continuous smoothness remain unmet; profile the measured layout/first-render boundaries before another correction. Stay on P0 until real-app user acceptance.

## Latest continuation point — 2026-10-02

**Latest authorized correction:** the user permits fixing the intermittent restore nudge and previously requests release publication/recompilation. Native framebuffer capture and actual Windows client geometry preserve the physical pixel grid through direct shader endpoints, while accepted header mapping/early movement and all gates/watchdog remain. Both GPU regressions pass, including 18 exact handoffs across three screens and monitor boundaries; forty safe tests pass. Final populated-app comparisons pass at both DPIs. Both executables are rebuilt and the complete package is installed at `C:/Programs/CSPM`. Candidate/installed startup, four title-bar toggles each and actual packaged WebEngine rendering pass; all 4,377 runtime files and 168 source/bundled QML files match, with workbook/settings hashes unchanged. Fix/release `6c72200` is pushed and the full remote SHA independently verified; this documentation follow-up records publication. Read `docs/RESTORE_PIXEL_ALIGNMENT_FIX_2026-10-02.md` and the latest ledger. Do not advance from P0; real-user installed acceptance remains open.

**Latest reported defect:** a slight intermittent restore-position shift. Investigation reproduces a matching one-pixel change at the captured-image/live handoff on 225% DPI while native window coordinates remain stable. The completed 100% pixel comparison shows no such change. High-DPI pixel runs hit timeouts and remain overall failed evidence; completed transitions still establish the mismatch. A disposable actual-position correction removes a horizontal difference but leaves the vertical one, so no application fix is promoted. Read `docs/RESTORE_INTERMITTENT_SHIFT_INVESTIGATION_2026-10-02.md` before the next scoped correction. Match physical capture/replay/live rasterization grids and validate both DPIs and several placements; preserve the accepted title/glyph rendering and early motion. Installed application is unchanged by this diagnosis. P0 stays open for this defect and real-user acceptance.

**Current continuation:** the user accepts title/glyph rendering and smooth final settlement, and requests removing the initial lag followed by recompilation and Git publication. The candidate starts source-image motion before the expensive target-layout preparation. A same-process 20-toggle comparison passes: old/new start-notification medians are 636/160 ms for maximize and 666/163 ms for restore at 100% DPI; total handoff remains about a second. The 18-sample GPU regression preserves header size and exact endpoints. Earlier stress comparison/pixel runs hit timeouts and remain failed evidence; the later comparison passes with unchanged watchdog/readiness gates. Full main/recovery rebuild and deployment to `C:/Programs/CSPM` are complete. Outside-sandbox candidate/installed startup and actual installed WebEngine rendering pass; full manifest/source QML match and workbook/settings hashes are unchanged. Fix/release commit `39c873d` is pushed and independently verified on `origin/fix/invoice-billing-client-correction-20260926`; this documentation follow-up records publication. Read `docs/MAXIMIZE_RESTORE_RESPONSIVENESS_FIX_2026-10-02.md` and the current ledger for actual release results. P0 remains open for installed responsiveness/title/settlement acceptance, caption stress and physical mixed-DPI/all-monitor checks. Do not advance to another visual state machine.

**Preceding analysis:** two outside-sandbox full-source timing runs at 225% DPI locate roughly 1.1–1.3 seconds of preparation, dominated by final-size binding/layout work and the first resized render. The newer 100% comparison is not a direct before/after against those historical absolute timings. `docs/MAXIMIZE_RESTORE_RESPONSIVENESS_ANALYSIS_2026-10-02.md` records that analysis-only stage.

The user subsequently requested full recompilation and Git publication. Both executables have been rebuilt with approved templates, the complete package is installed at `C:/Programs/CSPM`, candidate/installed startup and actual WebEngine rendering pass, and source/dist/installed QML plus the full runtime manifest match. Workbooks/settings are unchanged. Read the full rebuild continuation in `docs/MAXIMIZE_RESTORE_SETTLEMENT_FIX_2026-10-02.md` and the latest task/implementation ledger. User visual acceptance remains open.

Fix/release commit `c0d16ec` is pushed and its remote SHA verified on `origin/fix/invoice-billing-client-correction-20260926`; the publication ledger follows in a documentation-only commit.

**Latest follow-up:** the user finds the cloud candidate smoother but reports title/glyph distortion and a jarring endpoint. The installed asset patch now captures both endpoint layouts from the same workspace, keeps header text/controls at native size, and completes the layout blend during movement. Eight real GPU samples verify fixed header dimensions and exact endpoint pixels; ten full-app toggles plus taskbar/close checks pass without watchdog timeout. User visual acceptance remains open. Target capture adds preparation time: subsequent full transactions measured 1.129–1.489 seconds, with the first at 2.125 seconds. Read `docs/MAXIMIZE_RESTORE_SETTLEMENT_FIX_2026-10-02.md` for this latest implementation and evidence. The single-image/terminal-fade description in the preceding handoff below is historical.

The older native-path implementation description below is historical. Gemini's subsequent in-window release was also rejected; its header-only pixel capture did not validate motion. The latest candidate uses one captured image of the existing shell in a fixed frameless surface, with render-thread shader motion and submitted-frame handoff gates. Ten real desktop toggles pass functional checks; eight pixel sensors no longer reproduce the previous large jumps. Full handoff still takes approximately 0.9–1.0 seconds, and user speed/smoothness, caption stress and physical mixed-DPI acceptance remain pending. The user explicitly requested rebuilding and committing/pushing at the manual-review boundary. Read `docs/MAXIMIZE_RESTORE_HANDOFF_2026-10-02.md` for complete implementation, rejected attempts, measurements, reproduction and release continuation; older success claims are not manual acceptance.

This is the durable continuation point for all visual, motion, and animation work. It does not replace docs/ANIMATION_SPECS.md; that older Project Jelly document is a read-only historical reference and contains superseded direction.

## Product Standard

CSPM should feel deliberate, quiet, responsive, and cinematic only where motion serves a clear purpose. A transition must communicate a state change, never expose implementation details.

Non-negotiable visual bar:

- no one-frame teleport, duplicate movement, native-window resize strobe, or mask pop;
- no empty frame, full-window flash, or unowned frame during a handoff;
- no visible responsive-layout reflow inside a surface that is meant to move as one object;
- input is locked only for the actual duration of a transition;
- Professional is restrained and premium: no bounce, wobble, arbitrary rotation, or constantly distracting ornament.

## Immediate Priority — Professional Maximize / Restore

### Reported failure

Maximizing a smaller Professional window looked as though it jumped around the screen. Even where the outer rectangle was approximately correct, its responsive layout could already have reflowed to the full-screen arrangement and then been scaled down. Panels, text, and controls therefore appeared to move independently instead of as a single premium window surface.

### Current implementation

As of the 2026-10-01 source correction, Windows Professional maximize/restore
uses native ownership. The rebuilt 2026-10-01 release now deploys this path.
The preceding installed package used an overlay; the earlier 2026-08-31 source
description was not present in the pulled implementation.

1. `src/python/platform/native_window_state.py` establishes compatible Qt/native
   frame flags, suppresses native non-client painting, and confines the
   maximized client to the monitor work area. CSPM still draws its own title
   bar and glyphs. Settled native ownership clears layered styling and the
   custom window mask.
2. The title-bar command calls one native `SW_MAXIMIZE` or `SW_RESTORE`
   operation through `AppController.requestProfessionalNativeWindowState()`.
3. `DetachedShellWindow.qml` does not set `maximizeAnimInProgress`, stage a
   monitor-sized host, enable the maximize texture layer, or run a per-frame
   QML geometry/texture timeline on the ordinary Professional path.
4. Conditional QML host bindings are suspended while Windows owns geometry.
   Native visibility/client geometry synchronizes the glyph, final/canvas
   model, normal bounds, and monitor. Persistence is deferred beyond motion.
5. `Win+Shift+Arrow` passes through to Windows only while natively maximized,
   so the maximized HWND and Windows-owned normal placement transfer together.
   Restored windows keep CSPM's original monitor/DPI movement pipeline.
6. Before existing close/minimize/taskbar and cursor-anchored drag-restore
   sequences, the bridge returns the original flags/styles, mask handling,
   and QML geometry ownership without animating its internal state adoption.

The prior 240 ms one-owner texture implementation remains only as a
bridge-unavailable compatibility fallback. It is not the accepted Windows
Professional path.

### Current validation state

Latest 2026-10-01 user report: the separate upper-left appearance is resolved in their run, but transitions feel slow and the restored shell has huge clipped corners until moved. The user authorized the scoped geometry correction and executable release, alongside an urgent invoice reversal repair. Restored Professional corners now use final settled padding instead of a transient monitor-sized canvas; native geometry synchronization gates the rounded mask and mask changes explicitly invalidate it. Native frame preparation is idempotent and frame refresh discards copied client pixels. The approved custom title bar and other transition handlers remain.

69 focused safe tests, compilation, and governed QML lint pass (existing lint warnings remain). Outside-sandbox full-source functional regression completed 20 toggles with one workspace, exact restored bounds, a 12-pixel restored radius, taskbar return in both states, and custom close. Actual WebEngine PDF rendering passed. These are functional checks, not a claim of silky motion or physical mixed-DPI acceptance. Earlier rejected presentation experiments below are historical evidence, not production code. Final executable build/deployment results are recorded in implementation.md.

Restored-window movement across every connected monitor, including differing
DPI/resolution and negative desktop origins, is a required regression constraint.
Diagnostic single-monitor placement must never constrain the application. The
native bridge now releases ownership before restored drag/resize/classic and
adjacent-monitor movement; restored Win+Shift+Arrow retains the original CSPM
pipeline. Twenty focused safe tests and scoped governed lint pass. The full-app
surface experiments still show the upper-left jump and remain diagnostic only;
do not promote them or claim animation acceptance.

- Sandbox-safe: changed Python modules compile; focused native-state/
  choreography/layout/feedback suites report **17 passed**; governed QML lint exits 0 with no syntax
  error and existing warning-level diagnostics only; scoped `git diff --check`
  exits 0.
- Outside-sandbox source runtime with disposable workbook/settings copies:
  ten cycles used true `IsZoomed`, preserved the same Productivity report,
  created no overlay, and restored exact normal bounds. A native contract
  probe verified client/work-area alignment and restored flags. Normal and
  maximized taskbar cycles plus maximized close completed without functional
  failures. Separate real WebEngine rendering produced a 38,902-byte PDF.
- The user rejected the first native attempt because maximize still jumped
  toward the upper left. Unlocked-desktop recordings confirm the revised
  native geometry contract still fails visually: the old-size transparent
  Qt Quick surface moves first, then the full-size surface arrives. Minimal
  probes suggested the premultiplied-alpha swapchain, but a full-source run
  with an initially opaque surface also reproduces the jump. Alpha alone is
  therefore not an established cause. Native style/geometry checks do not
  prove this rendering boundary is clean.
- An ignored per-window swapchain prototype uses an opaque surface only for
  the native state operation and restores alpha afterward. Minimal-window
  evidence did not establish full-app quality: subsequent full CSPM captures
  using the exact QML toggle still show the old-size surface at the upper left
  before the full-size surface arrives. The prototype failed and remains
  diagnostic only. Earlier locked/occluded captures are invalid evidence.
  Restore temporary desktop settings at test completion. User visual
  acceptance remains blocking; no corrected package was built.

### Proposed next correction — not implemented or accepted

The user requested a concrete solution without further screenshots. Use one stable
native custom-frame controller on the existing QQuickWindow and retain the existing
MainContent. Compare the complete native event contract against QWindowKit's Win32
implementation before changing code. Stable/idempotent flags alone already failed;
this proposal adds specific native-protocol corrections, not a repetition of that
experiment:

- Current bridge refreshes the frame with SetWindowPos flags 0x37. QWindowKit's
  WM_WINDOWPOSCHANGING handler documents a client-content shift for exactly this
  combination and adds SWP_NOCOPYBITS. Treat this as a relevant, testable defect,
  not proof of the complete maximize failure's cause.
- Current bridge unconditionally swallows WM_NCPAINT and returns a constant for
  WM_NCACTIVATE. Reference handling permits compositor NC painting and forwards
  activation to DefWindowProc with lParam=-1 to suppress border repaint while
  preserving activation state. Suppress visible native caption through client-area
  calculation, not indiscriminate suppression of compositor messages.
- Initialize Qt/custom client margins and the native frame coherently; avoid
  repeated Qt flag/style changes inside each maximize/restore command. Correct
  geometry ownership and retain original normal-window monitor/DPI algorithms.
- Preserve existing opening/closing/minimize/taskbar choreography. A stable-frame
  implementation must explicitly suppress Windows state animations during those
  custom transactions and verify their existing geometry/mask/opacity behavior.
  This is a regression obligation, not an established no-impact guarantee.

Reference: https://github.com/stdware/qwindowkit/blob/main/src/core/contexts/win32windowcontext.cpp
Framework setup/lifecycle notes: https://github.com/stdware/qwindowkit/blob/main/README.md
Microsoft SWP_NOCOPYBITS contract: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos

No library dependency, native plugin, source fix, or package change was made for
this proposal. A compiled Qt-matched adapter may be appropriate if adopting the
framework's full Qt/native integration. User observations, event ordering, real
startup/WebEngine validation and protected-animation/mixed-DPI regression checks
must establish whether this approach actually succeeds; no more screenshot
collection is required.

### Historical 2026-08-31 P0 notes — superseded by the source status above

The earlier telemetry conclusion is superseded. `phaseLog()` is disabled
unless verbose logging is enabled, and Qt debug/info messages are normally
dropped by `main.py`. The warning-level native-envelope staging line was not
evidence that the 240 ms timeline failed to start; staging-to-settings-save
timing was consistent with the animation completing.

The user's visual report instead exposed an ownership mismatch. Source leaves
one HWND and the full maximize/restore transaction with Windows/DWM. CSPM was
resizing a layered native host around a QML texture transition, so native
surface/swapchain reconfiguration could remain visible regardless of easing.

The current source build now restores Source-like native style bits and calls
the real HWND maximize/restore command. A disposable local Qt compositor probe
confirmed that the corrected layered HWND receives DWM-owned intermediate
frames, so CSPM's transparent surface and separate close/minimize visuals did
not need to be redesigned for this P0. The real source app has passed native
state/geometry wiring checks and is open for the manual gate below. Do not
build/promote a package or advance to another visual state machine until Cory
accepts this source motion.

### Manual acceptance gate — do this first

Launch with ./launch.ps1 in Professional style and begin from a visibly smaller normal window.

| Action | Must be observed | Must not be observed |
| --- | --- | --- |
| Click Maximize | One continuous native Windows/DWM transition from the exact resting rectangle, visually matching Source | Pre-jump, internal-panel reflow, flash, duplicate motion, delayed start |
| Click Restore | One continuous native Windows/DWM transition to the Windows-owned normal rectangle | Mask/corner pop, position shift, blank frame, layout snap |
| Maximize, Win+Shift+Arrow, then Restore | Restore on the monitor that currently owns the maximized native window | Return to a stale monitor or stale desktop coordinates |
| Repeat ten times | Consistent timing and clean handoff | Accumulating lag, stale layer, native resize sweep |

If a defect remains, preserve logs/cspm.log from the failing run and inspect MAXIMIZE / RESTORE-MAX messages before changing code. Do not add multi-stage bounce, rotation, a native-Window geometry Behavior, or image readback to this path.

## Animation Inventory — Current Source Audit

| Surface / sequence | Primary owner | Current approach | Risk / next action |
| --- | --- | --- | --- |
| Native splash and QML reveal | src/python/main.py; DetachedShellWindow.qml | Native splash hands into QML opening/bloom | Keep native splash authoritative until QML has a real ready frame; test on a real GPU after handoff changes |
| Startup background work | DetachedShellWindow.qml; backend controllers | Deferred queue and quiet-time guard | Keep data/theme/dashboard work outside reveal and first-input budget; use timing evidence |
| Maximize / restore | native_window_state.py; AppController; DetachedShellWindow.qml | Native HWND state; QML follows Windows events | Finish manual acceptance gate before altering another motion path |
| Restore by title-bar drag | DetachedShellWindow.qml | Separate cursor-anchored geometry path | Test separately; preserve pointer anchoring and do not add cinematic delay |
| Dragging | DetachedShellWindow.qml | Native drag when available; 8 ms fallback cursor polling | Measure QML geometry cost; prefer native/event-driven motion over more polling |
| Resizing | DetachedShellWindow.qml | Live resize with a 4 ms timer and effect reduction | Profile a dense view; coalesce to display cadence and avoid FBO/mask reallocation per tick |
| Minimize / taskbar / tray | JellyController.qml; DetachedShellWindow.qml | In-place scale/translation/opacity choreography | Audit each entry path independently; Professional needs restrained effects |
| Close / shutdown | JellyController.qml; DetachedShellWindow.qml | In-place collapse plus particle/plasma stages | Ensure one visual owner each frame and prevent async work from blocking the first collapse frame |
| Chrome glow / flair | ChromeSurface.qml; VisualRules.qml | Glow, masks, continuous flair/plasma | Make Professional explicitly own its effect budget rather than relying on lowPerformanceMode |
| Panels, dialogs, controls | MainContent.qml; component QML; VisualRules.qml | Individual microinteraction behaviors | Standardize semantic durations/easings by component class |

## Cross-Cutting Performance Risks

1. Per-frame timers: the 4 ms resize timer and 8 ms fallback drag poll can perform more work than the display can show. Faster timers do not create smoother presentation if they starve the GUI or scene-graph render.
2. Large effects and masks: MultiEffect, rounded masks, glow layers, blur-like effects, and offscreen captures can pressure textures/FBO allocation during size changes.
3. Responsive layout during motion: changing finalW/finalH changes layout. Animate one composed surface whenever that layout must appear coherent.
4. GUI-thread contention: workbook/data refresh, settings/theme activity, queued startup tasks, logging, and QML object creation can interrupt an otherwise correct easing curve. Correlate with logs/frame-time evidence; do not guess.
5. Multiple state owners: native Window geometry, host envelope, canvas geometry, content-local geometry, and transforms interact. A transition needs one explicit visual owner and one final geometry source of truth.

## Improvement Roadmap

### P0 — Complete maximize acceptance

Do not begin a broad visual rewrite until the user confirms the manual maximize/restore gate. If it fails, fix that path only, add a regression guard, validate, and ask again.

### P1 — Establish a Professional effect budget

Audit ChromeSurface.qml, VisualRules.qml, JellyController.qml, and window commands. Write down which effects are allowed for Professional, Console, and low-performance modes. Professional should use subtle depth, short coherent transforms, and stable lighting; continuous plasma/flair, spring/bounce, and arbitrary rotation require an explicit reason.

### P2 — Create semantic motion tokens

Consolidate by meaning, not by component:

- feedback: 100–160 ms;
- compact expand/collapse: 160–220 ms;
- window state change: 220–280 ms;
- intentional cinematic reveal only: longer, with background work isolated.

Use monotonic easing for application-owned Professional transitions. Native
maximize/restore deliberately has no QML easing token; Windows/DWM owns its
timing. Do not use OutBack, bounce, or rotation unless real-GPU review
specifically approves it.

### P3 — Instrument frame pacing before expanding effects

Add narrow diagnostics around transition start/end, snapshot capture latency, GUI-thread blocking work, and missed-frame symptoms. Do not write visible-frame logs in production. Review capture timing together with the user-reported visual result and logs/cspm.log.

### P4 — Audit one state machine at a time

Recommended order after maximize acceptance:

1. button minimize to taskbar;
2. taskbar restore;
3. tray exit and tray restore;
4. normal close;
5. title-bar drag, snap, and drag-restore;
6. resize under a dense screen;
7. dialogs, dropdowns, panels, and navigation microinteractions.

For every state machine, document source state, visual owner, native geometry change, input lock, cancellation path, duration/easing, final handoff, and manual acceptance criteria before moving to the next one.

## Rules for the Next Agent

1. Read this document immediately after the mandatory repository startup documents. The user explicitly made visual FX the next priority.
2. Start with the P0 Professional maximize/restore manual acceptance gate. If the user has not confirmed it, do not jump to another visual issue.
3. For a reported visual defect, read logs/cspm.log first. Inspect the exact current transition owner before proposing a repair.
4. Change one visual sequence at a time and preserve unrelated dirty-worktree changes.
5. Run sandbox-safe checks and label them as such. Static checks do not prove motion quality; run real Qt/WebEngine visual validation outside the sandbox when permitted.
6. Record each meaningful visual change here, in task.md, and in implementation.md. Leave the user manual check open until the user confirms it in the real app.

## Key Files

- src/qml/DetachedShellWindow.qml — host/canvas geometry and primary window-state choreography.
- src/qml/components/JellyController.qml — close, minimize, restore, and deformation sequences.
- src/qml/components/ChromeSurface.qml — chrome, glow, flair, and composed effect cost.
- src/qml/standards/VisualRules.qml — visual/motion standards and style policy.
- src/qml/views/MainContent.qml — shell content, interaction gating, navigation transitions.
- src/python/main.py — native splash and QML handoff.
- tests/test_maximized_restore_and_close_choreography.py — maximize/restore source regression guard.

## Change Log

- 2026-10-01: Diagnosed the installed overlay path and added the scoped native
  source bridge. After the user rejected an upper-left pre-jump, revised host
  binding ownership, Qt/native frame agreement, and work-area client sizing.
  Seventeen safe tests and outside-sandbox functional checks pass, but the
  revised source recording still fails motion quality. Isolated probes identify
  the transparent swapchain boundary; a scoped surface-preparation prototype
  awaits full CSPM validation and manual acceptance.
  Installed/dist packages remain unchanged by this source correction.
- 2026-09-24: Scoped Invoice Builder responsiveness repair at the user's direction. Fixed-width settings/action rows now wrap within the available monitor width, and Zen Preview reuses a focus-mode preview/settings workspace without the left draft pane. This does not alter the Professional maximize/restore state machine or close its still-pending manual acceptance gate; the Invoice Builder layout has its own foreground monitor check pending.
- 2026-09-10: Added a focused in-app quick-payment modal to Payment Entry at
  the user's direction. It uses the existing shared Popup/control styling and
  introduces no new window-state or motion sequence; the Professional
  maximize/restore manual acceptance gate remains pending and unchanged.
- 2026-08-31: Replaced the rejected Professional texture/host choreography
  with Source-like native HWND maximize/restore ownership; manual visual
  acceptance remains pending.
- 2026-08-20: Created after the Professional frozen-surface maximize/restore repair. Manual visual acceptance remains pending.

