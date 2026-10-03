# Professional maximize/restore: complete user-intent and engineering handoff

Status as known on 2026-10-03. Repository: `Y:/Projects/__CSPM`.
Current diagnostic environment: Windows, Python 3.14.2 and PySide6/Qt 6.10.3.

## The experience we want

The user's words are **silky, smooth, flowing, gliding, elite, premium**. They
reference the feel of KDE transition animations in Fedora. Treat this as a
quality reference, not a requirement to copy a specific KDE implementation or
an assumed numerical animation duration.

The user's latest clarification is that it must **flow like plasma or water**
and cannot be jarring. The window should feel as though it flows continuously
into its new shape. Changes in speed and the final arrival must blend smoothly,
including when the target becomes ready and the captured surface hands over to
the live window. This refines the desired feel; no new implementation or visual
acceptance is established by recording it.

The user also identifies CSPM's existing **opening and closing transitions as
perfectly smooth and flowing**. Those accepted animations are a concrete visual
benchmark inside the same application. Maximize and restore must match their
uninterrupted flow through the complete movement and final arrival, while
meeting the faster-speed objective. Preserve those approved transitions.

The smaller window must expand into its maximized rectangle as one coherent
surface. The reverse transition must glide back to its exact saved normal
rectangle with the same quality. Both must feel responsive and deliberate.
The user wants the current slow maximize to become **at least three times
faster**, while preserving smoothness. We have not established a separately
agreed fixed duration; the engineering ledger currently measures complete
transactions as well as their individual stages.

Their most explicit requirement is: **one smooth movement from start to
finish**. There must be no perceptible pause, restart, jump, jerk, separate
finishing movement or sudden correction when the moving surface becomes the
live window. Natural deceleration should lead directly into the resting size
and position. Professional motion should remain restrained: no bounce, wobble
or arbitrary rotation.

The visible requirements include all of the following:

- Movement begins promptly after the command; a long stationary preparation
  delay is part of the problem.
- Window position and size change coherently. Panels and controls must not
  visibly jump through an unrelated responsive layout during preparation.
- The custom title, glyphs and header controls keep their established pixel
  size and proportions. They must not stretch, appear to change font, or dim
  and brighten because input is temporarily locked.
- The final responsive layout arrives seamlessly during movement. There is no
  terminal layout snap, blank frame, flash, duplicate surface, native caption
  appearing behind CSPM's custom header, or corner/mask pop.
- Restore returns to the exact saved position and size, including physical
  pixel alignment. A one-pixel nudge at the handoff fails this requirement.
- The same workspace, report, state and data remain alive throughout. Do not
  recreate another workspace to animate it.
- Maximize respects the owning monitor's work area and taskbar. Restored
  movement must remain available across monitors, differing DPI/resolution,
  negative desktop origins and monitor boundaries.
- Preserve the previously approved opening, closing, minimizing and taskbar
  return behavior. Preserve movement, resizing, command guards and persistence.
  Scope this work to maximize/restore until the user accepts it in the real app.

## Current result and production mechanism

**The requested faster, equally smooth result is not complete.** The user has
accepted the smoother movement/title rendering/final settlement from earlier
corrections, and most recently calls expansion from a smaller window very
smooth but too slow. There is no accepted threefold-speed candidate.

The current enabled Professional path uses a fixed transparent transition
window and captured pixels from the existing workspace. Ordinary native
Windows-owned maximize and the earlier in-window implementation remain
historical/dormant paths; they are not the current accepted motion mechanism.

The temporary window covers the union of the source/target bounds plus needed
padding. Its native host stays fixed throughout. It is input-transparent and
nonactivating. A render-thread `UniformAnimator` drives shader motion rather
than repeatedly resizing that visible native host.

The production sequence is:

1. Capture the actual live native framebuffer into a transient in-memory image
   provider. Present the exact source appearance in the fixed transition host.
   Three submitted source frames gate hiding the original host.
2. Begin source-image movement promptly. Its first submitted moving frame gates
   committing the original workspace's final geometry/layout underneath.
3. Wait for two submitted original target frames, capture that native target
   framebuffer, then wait for two submitted captured-target frames.
4. Blend toward the target layout during the remaining movement. Fixed-size
   header mapping preserves title/glyph proportions. Direct shader endpoints
   reproduce source/target pixels without another resampling transformation.
5. Two submitted final-surface frames gate revealing the live host. Two live
   host frames and three release frames gate removing the transition host.

Early preparation advances toward 85% over **800 ms, OutCubic**. Once the target
is ready, a **220 ms, InOutCubic** settlement factor combines the current
preparation position with the exact endpoint. Those timelines overlap: this
does not mean an unconditional 800 + 220 ms wait. A non-early comparison path
also exists with a 220 ms OutCubic animator. Sequence checks, input guards,
capture cleanup and the **3500 ms watchdog** remain.

This is internally a preparation/settlement pipeline. The user's requirement
concerns what they see: any two-stage appearance or pause fails, regardless of
how correct the internal state machine or final rectangle is.

## Approaches already tried

These are the distinct documented approach families, including failed trials.
Historical pass results do not supersede later user rejection or fresh pixel
evidence. Read the linked detailed records before repeating an experiment.

| Approach | Result and lesson |
| --- | --- |
| Duplicate `MainContent` overlay and fixed 16 ms readiness wait | Rejected. It recreated workspace/layout and exposed preparation/settlement. The current surface captures the existing workspace instead. |
| Native Windows/DWM-owned maximize/restore | Correct final geometry and lifecycle did not give acceptable motion. The full app showed old-size content moving toward the upper-left before the resized image arrived; jerky restore and native-caption leakage were reported. |
| Native protocol refinements | Tried Qt/native frame agreement, suspended geometry bindings, margins, nonclient activation/painting/caption suppression, idempotent frame setup, copy-bits protection, normal placement and release ordering. Some corrected functional contracts/corners, but did not remove the measured presentation failure. |
| Opaque surfaces and swapchain/alpha variants | Minimal probes looked promising; the full application still failed. Transparency alone is not an established root cause. |
| Repaint/expose/redraw variants, size-event paint dispatch and compositor flushes | Did not establish a clean full-app transition. |
| OpenGL, D3D12, basic/single-thread render loop, system commands/deferred calls and isolated Qt 6.11.2 | Rejected as full-app solutions; symptom changes or functional success were insufficient. No global renderer/runtime switch was retained. |
| DWM thumbnails, independent GDI presentation and live native-container experiments | Thumbnails clipped; other variants added latency or handoff artifacts. No accepted production solution. A freeze-representation API attempt returned an invalid-argument error. |
| Cached/batched metrics, stable QtObject proxy and disabled redirection surface in the native investigation | Did not remove the old-size pre-jump; reverted or retained only as ignored diagnostics. |
| Gemini's in-window transform release (`3ea0d7d`) | User rejected it. Fresh compositor measurements reproduced a preparation jump and restore displacement. Its earlier pixel CSV was header-only after access denial, so the associated visual-success/60-FPS claims were unsupported. |
| First fixed-surface, single-source capture | Removed the earlier large measured jumps in a completed ten-toggle run, but scaled title/glyphs and a terminal fade exposed layout differences. Total transition remained approximately a second. Superseded by two endpoints/header mapping. |
| Early surface target-capture/update/readiness variants | One second-capture version was slow and rejected a subsequent toggle. Direct frame requests could stall. A `ShaderEffect.Compiled` gate failed repeated use when a cached shader rendered with `Uncompiled` status. Queued requests plus actual submitted frames, image readiness and absence of shader errors became the gate. Later stress failures still exist. |
| Two endpoint captures, fixed-size header mapping and layout blend during movement | Retained. Addressed title/glyph distortion, control dimming and the jarring terminal layout replacement. The user accepted those visuals. Target preparation initially added a substantial stationary delay. |
| Begin source movement before target preparation | Retained and released (`39c873d`). Matched start-notification medians improved from 636/666 ms to 160/163 ms for maximize/restore. This moved work behind early movement; it did not eliminate the layout/render cost. |
| Restore target-position correction alone | Rejected. It removed a horizontal high-DPI difference but left the vertical one-pixel mismatch. |
| Whole-root capture and predictive physical-coordinate rounding | Rejected as incomplete. Antialiased pixels still differed, including at monitor boundaries. |
| Native framebuffer capture, actual Windows client origins/sizes and direct shader endpoints | Retained and released (`6c72200`). Exact endpoint tests and completed populated-app comparisons addressed the tested fractional-DPI handoff mismatch. Manual acceptance remains required. |
| Shorten preparation/settlement to 240/65 ms | Rejected. The complete transition improved only 1.21x/1.45x in a matched comparison, and preparation could hit its 85% cap before the target was ready. That creates a continuity risk; a visible pause was not independently certified. |
| Separate QML QtObject metric fields | No useful gain in the speed investigation; exploratory total median 1047 ms. Not promoted. |
| Immediate synchronous target capture instead of waiting for target frames | Regressed to an exploratory total median of 2004.5 ms. Not promoted. Capture is not a free read of already-ready pixels. |
| Lazy close/recovery/redock prompts | Exploratory median 899 ms versus 904 ms for short motion alone; no established useful improvement. An initial mirror rewrite failed before launch. Not promoted. |
| Coalesced metrics publication across a size commit | Exploratory median 950.5 ms; no useful improvement. Not promoted. |
| Qt property update group | Minimal QML experiment still evaluated ordinary bindings for both dimension changes. Not a demonstrated batching solution. |
| Later Python/component/native render profiling and elapsed-time animation driver | Inconclusive. The corrected Python run timed out at source readiness before target geometry and failed its state/overall gates. Control/native timing attempts stalled or were incomplete. The elapsed-time driver was diagnostic only and not adopted. No target-layout cause or smoothness improvement was established. |

Other earlier early-motion prototypes involving mask removal, native geometry
deferral, window pooling or capture shortcuts were not promoted: they did not
show a reliable benefit or failed lifecycle checks. Do not erase failed runs
from the record or repeat these families without new evidence about what is
different.

## Current speed evidence and its limits

The strongest recent comparison ran both timing configurations in the same
populated app: 20 primary toggles, five samples for each direction/configuration,
plus three lifecycle transitions. Functional assertions passed without a
watchdog timeout.

| Configuration | Maximize median | Restore median |
| --- | ---: | ---: |
| Production 800/220 ms timelines | 1122 ms | 1269 ms |
| Rejected 240/65 ms timelines | 924 ms | 877 ms |
| Complete-transaction speed ratio | 1.21x | 1.45x |

A separate six-toggle baseline measured median target geometry/layout commit
at **265.5 ms** and target readiness/capture at **286.5 ms**. Much of the total
cost survives shorter animators. These locate expensive boundaries; they do
not establish which individual binding, layout, effect, render synchronization
or capture operation accounts for every millisecond.

The successful initial speed investigation contains **60 primary toggles / 84
total transitions** across completed fixtures. Later failed/incomplete profiling
runs are excluded. Tests use disposable source/data/settings and primarily the
100% display for this latest speed investigation. Earlier 225% and pixel runs
have different load/configuration and must not be used as a causal before/after.

Timestamps run from the programmatically invoked QML button handler to GUI
handling of submitted-frame signals. They are not physical mouse-to-photon,
compositor scanout or complete frame-pacing measurements. Regular frame swaps,
average FPS, correct final geometry and passing unit tests do not prove one
continuous premium movement.

## Release, validation and manual status

The endpoint/header/early-motion corrections were previously rebuilt,
installed and published. The last recorded package refresh on 2026-10-03 pulled
through `ad72d59` and rebuilt main/recovery into `C:/Programs/CSPM`. That refresh
did not add a new speed fix. The recent speed experiments were not rebuilt,
installed, committed or pushed; accepted production animation files remain
unchanged. The retained diagnostic comparison and investigation documents are
currently local worktree changes. Preserve the pre-existing task/implementation
release notes when editing them.

Sandbox-safe checks in the initial speed investigation: **28 focused tests**,
diagnostic compilation, governed QML lint with existing warnings and whitespace
checks passed. Later profiling follow-up passed compilation/whitespace only.

Outside sandbox, prior real Qt GPU tests verified header dimensions/direct
endpoints and 18 exact two-window handoffs across three screens including 225%
DPI and monitor boundaries. Completed populated-app pixel comparisons at 100%
and 225% found equal tested frozen/live restore marker bounds. Their 250 ms
endpoint hold was diagnostic only and cannot support production speed claims.
Some earlier/load-related stress runs timed out and remain failures.

Previous packaged startup/control smoke checks and actual WebEngine HTML/PDF
rendering passed. No new dedicated WebEngine e2e was run for the speed
investigation or failed profiling follow-up. Current desktop profiling cannot
be reported as a new passing motion check.

**Still open:** at least threefold useful speed improvement while retaining
one uninterrupted silky glide, reliable behavior under load, and real-user
acceptance of the installed result. Physical all-monitor/mixed-DPI dragging,
caption/activation stress and repeat-use acceptance remain manual obligations.
No faster version has satisfied those requirements.

## How the next agent should continue

1. Read the repository's required startup documents in order, followed by the
   visual handoff. Read runtime logs before proposing a fix. The repository log
   is historical; also inspect the latest installed session under
   `%LOCALAPPDATA%/CSPM/logs/cspm.log`. Current runtime logs append sessions despite
   the older fresh-log description, so scope conclusions to the right session.
2. Confirm the running package and current enabled transition path. Restore
   reliable desktop profiling and identify the source-frame stalls separately
   before trusting another target-layout profile. Do not assign their cause
   without evidence or increase the watchdog to conceal them.
3. Profile beneath the established target geometry/layout and first resized
   render boundaries. Reduce demonstrated work while preserving the same
   workspace, endpoint pixels, custom header and readiness contracts.
4. Evaluate the whole transition in both directions: prompt start, continuity,
   deceleration, target-layout arrival, live handoff and input release. A faster
   duration setting alone is not a qualifying fix. Do not slow motion to hide
   preparation delays or remove gates without an equally strong demonstrated
   presentation guarantee.
5. Validate on the real desktop with a populated workspace, several restored
   sizes/positions, repeated toggles, all monitor scales/boundaries and lifecycle
   regression checks. Keep static checks, GPU pixel checks, source timing,
   packaged checks and subjective acceptance distinct.
6. Deliver a concrete candidate and obtain the user's acceptance in the real
   application before moving to another visual state machine. Keep task.md,
   implementation.md and the visual handoff current. Preserve the canonical
   Option 3 direction and unrelated work/data.

## Essential files and evidence

Runtime:

- `src/qml/DetachedShellWindow.qml`
- `src/qml/WindowTransitionSurface.qml`
- `src/qml/shaders/window_transition.vert` / `.frag` and their baked `.qsb` files
- `src/python/backend/window_frame_capture.py`
- `src/qml/views/MainContent.qml`
- `src/qml/components/ProfessionalAppShell.qml` / `ProfessionalTopHeader.qml`

Portable diagnostics/tests:

- `scripts/diagnostics/window_responsiveness_probe.py` (`--compare-short-motion`
  changes only its disposable mirror; it is not a smoothness certification)
- `scripts/diagnostics/window_transition_probe.py`
- `scripts/diagnostics/check_window_handoff_pixels.py`
- `tests/test_window_settlement_render.py`
- `tests/test_maximized_restore_and_close_choreography.py`

Detailed records, in historical order:

- `docs/MAXIMIZE_RESTORE_DIAGNOSTIC_HANDOFF_2026-10-01.md`
- `docs/MAXIMIZE_RESTORE_GEMINI_REVIEW_2026-10-02.md`
- `docs/MAXIMIZE_RESTORE_HANDOFF_2026-10-02.md` (its single-image/terminal-fade
  mechanism is historical)
- `docs/MAXIMIZE_RESTORE_SETTLEMENT_FIX_2026-10-02.md`
- `docs/MAXIMIZE_RESTORE_RESPONSIVENESS_ANALYSIS_2026-10-02.md`
- `docs/MAXIMIZE_RESTORE_RESPONSIVENESS_FIX_2026-10-02.md`
- `docs/RESTORE_INTERMITTENT_SHIFT_INVESTIGATION_2026-10-02.md`
- `docs/RESTORE_PIXEL_ALIGNMENT_FIX_2026-10-02.md`
- `docs/MAXIMIZE_RESTORE_SPEED_AND_SMOOTHNESS_ANALYSIS_2026-10-03.md` and its
  nonsensitive `...RESULTS_2026-10-03.json`
- `docs/VISUAL_FX_AUDIT_AND_HANDOFF_2026-08-20.md` (read newest continuation first;
  its older native-path descriptions remain historical)

Most raw workbook-copy/desktop traces are ignored local logs, not portable Git
artifacts. The checked-in historical records and local nonsensitive aggregate
capture the distinctions another agent needs. No live financial or workbook
change belongs to this animation task.
