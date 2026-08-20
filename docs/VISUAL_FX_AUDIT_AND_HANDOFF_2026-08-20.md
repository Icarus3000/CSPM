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

src/qml/DetachedShellWindow.qml now uses a frozen-surface handoff for Professional maximize and restore:

1. maximizeWindowToVisibleRect() or restoreFromMaximized() records exact source/target rectangles and routes Professional through beginProfessionalMaximizeSnapshotCapture().
2. contentLayer.grabToImage() captures the completed source surface while its host still has the old geometry.
3. The image becomes the only visible surface. The native host can adopt the target geometry and the live responsive hierarchy can reflow behind it without becoming visible.
4. professionalMaximizeSnapshotProgress interpolates the frozen image x, y, width, and height directly from source rectangle to target rectangle.
5. Only on the final matching rectangle does the frozen image disappear and the live hierarchy become visible.

Professional timing is 260 ms for maximize and 230 ms for restore, both Easing.OutCubic, with no rotation or overshoot. Capture is bounded at 180 ms. The existing direct live transform remains only as a compatibility fallback if GPU readback is unavailable; it is not the preferred visual path because it cannot protect against internal reflow.

### Current validation state

- Sandbox-safe source regression: python -m pytest tests/test_maximized_restore_and_close_choreography.py — 4 passed.
- scripts/qmllint.ps1 -Targets @('src/qml/DetachedShellWindow.qml') emitted no diagnostics but exceeded the current execution harness timeout. QML lint is inconclusive, not passed.
- An outside-sandbox source launch reached the settled Professional Qt/WebEngine shell without a QML/runtime failure. The log did not demonstrate the new frozen-surface maximize marker, so actual visual motion remains manual acceptance pending.

### Manual acceptance gate — do this first

Launch with ./launch.ps1 in Professional style and begin from a visibly smaller normal window.

| Action | Must be observed | Must not be observed |
| --- | --- | --- |
| Click Maximize | One continuous 260 ms growth from the exact resting rectangle | Pre-jump, internal-panel reflow, flash, duplicate motion, delayed start |
| Click Restore | One continuous 230 ms contraction to the saved normal rectangle | Mask/corner pop, position shift, blank frame, layout snap |
| Maximize, Win+Shift+Arrow, then Restore | Restore on the monitor that currently owns the maximized native window | Return to a stale monitor or stale desktop coordinates |
| Repeat ten times | Consistent timing and clean handoff | Capture timeout, accumulating lag, stale image resurrection |

If a defect remains, preserve logs/cspm.log from the failing run and inspect MAXIMIZE / RESTORE-MAX messages before changing code. Do not replace the frozen-surface approach with multi-stage bounce, rotation, or a geometry Behavior on the native Window.

## Animation Inventory — Current Source Audit

| Surface / sequence | Primary owner | Current approach | Risk / next action |
| --- | --- | --- | --- |
| Native splash and QML reveal | src/python/main.py; DetachedShellWindow.qml | Native splash hands into QML opening/bloom | Keep native splash authoritative until QML has a real ready frame; test on a real GPU after handoff changes |
| Startup background work | DetachedShellWindow.qml; backend controllers | Deferred queue and quiet-time guard | Keep data/theme/dashboard work outside reveal and first-input budget; use timing evidence |
| Maximize / restore | DetachedShellWindow.qml | Frozen Professional source; live transform fallback | Finish manual acceptance gate before altering another motion path |
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

Use monotonic easing for Professional window transitions. OutCubic is the current baseline. Do not use OutBack, bounce, or rotation unless real-GPU review specifically approves it.

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

- 2026-08-20: Created after the Professional frozen-surface maximize/restore repair. Manual visual acceptance remains pending.

