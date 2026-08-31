# Visual FX Audit and Continuation Handoff

Status: Active user-directed priority as of 2026-08-20.

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

As of 2026-08-31, Professional maximize/restore follows Source's native-window
ownership model:

1. `src/python/platform/native_window_style.py` keeps Qt's client-drawn
   frameless chrome but restores the HWND caption/thick-frame/system/min/max
   style contract that Windows uses for its DWM state animation.
2. The title-bar command calls one native `SW_MAXIMIZE` or `SW_RESTORE`
   operation through `AppController.requestProfessionalNativeWindowState()`.
3. `DetachedShellWindow.qml` does not set `maximizeAnimInProgress`, stage a
   monitor-sized host, enable the maximize texture layer, or run a per-frame
   QML geometry/texture timeline on the ordinary Professional path.
4. `Window.Maximized` / `Window.Windowed` is authoritative. QML follows that
   event to synchronize the glyph, final/canvas model, normal bounds, monitor,
   and persistence.
5. `Win+Shift+Arrow` passes through to Windows for this ready native path, so
   the maximized HWND and Windows-owned normal placement transfer together.

The prior 240 ms one-owner texture implementation remains only as a
bridge-unavailable compatibility fallback. It is not the accepted Windows
Professional path.

### Current validation state

- Sandbox-safe: changed Python modules compile; focused maximize/native-style/
  layout suites report **9 passed**; governed QML lint exits 0 with no syntax
  error and existing warning-level diagnostics only; scoped `git diff --check`
  exits 0.
- Outside-sandbox source runtime: `launch.ps1` reached a responsive real
  Qt/WebEngine shell. The custom chrome remained intact; the live HWND carried
  style `0x16CF0000` / exstyle `0x00080100`; CSPM's own maximize glyph entered
  true `IsZoomed` / `0x17CF0000` state; restore returned to the exact prior
  normal HWND rectangle and style.
- The source app is left open in normal state. Automated checks establish the
  native ownership/state contract, not subjective frame pacing. Cory's manual
  visual acceptance remains pending and blocking. No package was built.

### 2026-08-31 P0 native-window correction in progress

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
| Maximize / restore | native_window_style.py; AppController; DetachedShellWindow.qml | Native HWND state; QML follows Windows events | Finish manual acceptance gate before altering another motion path |
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

- 2026-08-31: Replaced the rejected Professional texture/host choreography
  with Source-like native HWND maximize/restore ownership; manual visual
  acceptance remains pending.
- 2026-08-20: Created after the Professional frozen-surface maximize/restore repair. Manual visual acceptance remains pending.

