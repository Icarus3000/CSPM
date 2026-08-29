# CSPM Task And Validation Ledger

## Accepted Payment Filter and Launcher Release Checkpoint (2026-08-29)

- [x] Cory accepted the governed `launch.ps1` path in the real application and manually confirmed the Make Payment unpaid-invoice filtering behavior.
- [x] Committed only the accepted scope as `5f7e3c49531b8eae8947ea03f60a24f16e9dab79` (`Improve payment invoice filtering and harden launcher venv resolution`): `launch.ps1`, `scripts/ensure_venv.ps1`, `src/python/repositories/excel_repo.py`, `src/qml/views/PaymentEntryView.qml`, and `tests/test_payment_invoice_filtering.py`.
- [x] Release validation: focused payment/invoice regressions (**41 passed in 11.63s**), Python compilation, PowerShell launcher/parser/setup validation, and governed QML lint (warning-only; no syntax errors). The source launch has real user acceptance; no sandbox WebEngine result was used as a pass signal.
- [x] Built version **2.4.0 / Phase 9 / build 1** from a clean detached worktree at that exact commit with `scripts/build_release.py`. Both executables, governed templates, and splash assets were produced; the build's confidential-workbook check passed (neither bundle template matches the live workbook).
- [x] Windows denied the builder's final directory rename, so `scripts/promote_verified_release_package.py` performed the documented hash-verified promotion. `dist` matches the source package: **4,358 files**, **678,587,001 bytes**, tree SHA-256 `9C8F6141B43032C5A13CC368BB7349DEC27E26E80EE0AF904A61615556274717`. `dist\\CSPM\\CSPM.exe` SHA-256: `876C7C62BD57B53BEDC940C64748C9685093551D6D590F0D14E5E4D9BC8C89AE`; recovery EXE SHA-256: `9A4F348ADC0AC17CC05DED34A348254BF091105EFB11BE9D958E80B7070DCCA4`. The prior package is recoverable at `to_delete\\dist__manual_replaced_release_20260829_174402`; the promotion audit is `to_delete\\release_promotion_20260829_174402.json`.
- [x] Packaged interactive WebEngine smoke was not run in the strict sandbox. It is not required to re-prove the already accepted source launch; the promoted executable was structurally and hash verified.

## Smooth GPU-Accelerated Maximize & Restore Animation (2026-08-19)

- [x] Diagnose the maximize window jumping and flickering. Asynchronous `grabToImage`
  readbacks, host envelope DWM resizing races with `mainWin.x/y` subtraction, and
  temporary snapshot Image swapping caused multi-frame visual hops across the screen.
- [x] Replaced snapshot image capture with a direct, hardware-accelerated GPU texture
  pipeline: `layer.enabled: true` on `contentLayer` during maximize and restore motion.
- [x] Implement pure host-relative geometric scale and translation transforms with
  zero-latency start (0ms), smooth `Easing.OutCubic` 220ms interpolation, and pixel-perfect
  alignment at frame 0 and frame 1.
- [x] Invariant preservation: Multi-monitor destination tracking via
  `restoreGlyphDestinationScreen()` and `monitorOwningWindowControl()` is fully retained.
- [x] Update choreography tests in `tests/test_maximized_restore_and_close_choreography.py`
  and verify with sandbox-safe `pytest` and `scripts/qmllint.ps1`.
- [ ] Manual source verification: Launch with `launch.ps1`, click Maximize and Restore
  in both Dark and Light themes across monitors; confirm buttery smooth 60/120fps GPU
  transition with zero jumping, zero lag, and zero coordinate hop.

## Exact Main-Window Layout Persistence (2026-08-19)

- [x] Persist the main window's final desktop `x`, `y`, `width`, and `height`
  at close in the authoritative app settings (`mainWindowLayout`), alongside
  the originating usable work area and the prior proportional fallback.
- [x] Restore that exact rectangle as the destination of the usual launch
  animation when the saved work area still matches. If a monitor was removed,
  rearranged, or resized, preserve the existing safe proportional fallback
  rather than allowing an off-screen window.
- [x] Make the layout save result observable in the close-phase log and return
  the atomic settings-write result from `saveMainWindowLayout`.
- [x] Add backend/QML regression coverage for exact layout persistence,
  negative desktop coordinates, invalid-record fallback, and matching-work-area
  restoration.
- [ ] Manual source verification: resize and move the app, close it, then run
  `launch.ps1`; confirm the standard opening animation settles at exactly that
  same size and position.

## Native Splash Main-Host Flash Hardening (2026-08-19)

- [x] Re-check the fresh runtime evidence. The reported run was `launch.ps1`
  using `.venv_CORY_CorySchneider\Scripts\python.exe`; its 06:54 session
  confirms the old pre-stage path still called `mainWin.show()` while the
  native CS splash was active. An earlier `dist\CSPM\CSPM.exe` session was
  separate and must not be used to characterize this reproduction.
- [x] Remove the more fundamental risk from the source startup sequence: the
  fully hydrated main QML object now remains `visible: false` throughout the
  CS progress, vortex, and plasma acts. The native handoff opens it only after
  `CustomSplash.hide()`; its bloom scale is set to 0.2% before that first
  native `show()` call.
- [x] Add `tests/test_splash_host_visibility_contract.py` to reject a future
  `phase2-native-prestage` launch gate and require the pinpoint state to be
  configured before `mainWin.show()`.
- [x] Separate the final native hide from the QML reveal by one compositor
  frame (32 ms), then explicitly raise and activate the main window at its
  first 0.2%-bloom frame. CSPM remains an ordinary, non-topmost app after
  that initial foreground presentation.
- [ ] Rebuild and hash-verify `dist\CSPM\CSPM.exe` with this source change.
- [ ] Manual source foreground verification: run `launch.ps1` and confirm no
  portion of the main app window appears at any point while the CS progress,
  vortex, or plasma animation is running. The first main-window pixels must
  be the 0.2%-to-full bloom after the native splash has disappeared, and that
  first frame must be in front of other applications.

## Absolute Desktop Screen Mapping & Startup Splash Monitor Invariant (2026-08-18)

- [x] Lock main app opening monitor to the native CS splash monitor:
  - *Diagnosis*: `resolveTargetScreen()` and `currentCursorScreenIndex()` queried `appRef.getCursorScreenIndex()`, so if the user moved their mouse to another monitor during startup, the main window would bloom and settle on that other monitor instead of the splash monitor.
  - *Fix*: Updated `resolveTargetScreen()` and `currentCursorScreenIndex()` to strictly lock to `startupLaunchScreenIndexSafe(0)` throughout the startup sequence (`!mainWin.isSettled`), guaranteeing that the main window always opens on the exact monitor where the CS logo splash started animating.
- [x] Eliminate Maximize Jump and Restore Flicker:
  - *Diagnosis*: Local coordinate offsets calculated against `hostX/Y` assumed the native OS window moved synchronously. Because Windows DWM moves native windows asynchronously, local offsets produced a 1-2 frame jump on maximize and flicker on restore before native `SetWindowPos` processed.
  - *Fix*:
    1. Snapshot backdrop and image properties (`professionalMaximizeSnapshotRenderX/Y`, `professionalMaximizeSnapshotImageX/Y`) now store absolute desktop screen coordinates and bind to `(screenCoord - mainWin.x)` / `(screenCoord - mainWin.y)`. Because `mainWin.x + (screenCoord - mainWin.x) = screenCoord`, the snapshot mathematically renders at the exact physical desktop pixel location regardless of OS message queue latency.
    2. Added `professionalRestoreSettleTimer` (60ms) to keep the snapshot active while the native OS window settles its restored geometry on restore.
- [x] Verified pytest choreography regression suite (**7 passed**), `py_compile` clean pass, governed `qmllint.ps1` clean pass, and rebuilding release package `dist\CSPM\CSPM.exe`.
- [ ] Manual foreground test `dist\CSPM\CSPM.exe`: verify CS splash and main window always open on the same monitor, and verify Maximize/Restore operate as a single smooth cinematic motion with zero jumping or flickering.

## Stable Professional Maximize Origin and Startup Splash Hardening (2026-08-18)

- [x] Diagnose the reported maximize jump from the persistent application log
  and the Professional animation path. The frozen frame was positioned using
  `mainWin.x/y` immediately after changing its host screen; Windows publishes
  those native coordinates asynchronously, so one or more frames could be
  calculated against a stale monitor origin.
- [x] Anchor every frozen-frame source and target coordinate to the synchronous
  `hostX/hostY` model origin instead. One durable `[MAXIMIZE]` or
  `[RESTORE-MAX]` diagnostic line now records that origin and both local
  rectangles for any foreground retry.
- [x] Prevent transparent corners of the native CS splash artwork from being
  compositor-flattened to black by applying the artwork's rounded alpha mask
  as a native top-level window mask.
- [x] Start compiling the hidden QML shell while the separate GUI-free
  Practice Briefing worker reads the snapshot; it remains uncreated and
  invisible until the complete snapshot has arrived. This removes the known
  serial wait without weakening the no-stale-data launch gate.
- [x] Run sandbox-safe Python compilation, focused maximize/startup tests
  (**15 passed**), governed QML lint (existing warning-level diagnostics only),
  and `git diff --check`.
- [x] Rebuild and promote the local CSPM EXE with the host-origin and splash
  corrections. The installed prior package SHA-256 is
  `69002B7E26BC3B9D770E782B9581CC204D3DEB2B5B8619B8F07AFA759CF5FB00`.
- [x] Diagnose the remaining visible hop from its foreground runtime log. Both
  paths logged `Unable to assign [undefined] to double` for the frozen image
  X/Y animation target. The outer backdrop moved while that image did not,
  followed by a live-layout handoff at a third position.
- [x] Replace the dynamic JavaScript context X/Y targets with persistent
  numeric QML properties and add a regression assertion that the undefined
  target fields cannot return.
- [x] Rebuild and promote the local CSPM EXE with the frozen-image target
  correction. `dist\\CSPM\\CSPM.exe` SHA-256 is
  `4FB1272BA03EABB9F3B4B2051A4C8982B7D3D20C5261A71A9EDD9540D27F2B97` and
  its bundled `DetachedShellWindow.qml` exactly matches source. The preceding
  package is recoverable at `to_delete\\dist__replaced_release_20260818_155521`.
- [ ] Manual foreground test `dist\\CSPM\\CSPM.exe`: maximize repeatedly on
  every monitor. The app surface must originate in-place and smoothly scale to
  the active monitor without an intermediate jump. Also confirm the splash has
  no rectangular black corners and reaches its progress gate promptly.

## Symmetric Professional Maximize/Restore Surface Morph (2026-08-18)

- [x] Replace the Professional frozen-frame rectangle stretch with one
  centre-preserving GPU scale for both axes.  Internal panels, text, charts,
  and chrome retain their proportions throughout maximize and restore rather
  than being cropped or independently stretched.
- [x] Use an independently morphing outer backdrop for differing normal and
  maximized aspect ratios; render the frozen image at the larger endpoint
  size; then softly hand off to the final hidden reflow only at the exact
  destination rectangle.
- [x] Run sandbox-safe maximize/restore and readiness regression tests
  (**11 passed**), governed QML lint (existing warning-level diagnostics only),
  and `git diff --check`.
- [x] Rebuild and promote the local CSPM and Recovery package. The installed
  `dist\CSPM\CSPM.exe` SHA-256 is
  `03157E36EF371A8DE6AEDE95856538916C5B5B679E44B7472910812FA918D68D` and its
  bundled `DetachedShellWindow.qml` exactly matches source. The prior release
  remains recoverable at `to_delete\dist__replaced_release_20260818_140332`.
- [ ] Manual foreground-test `dist\CSPM\CSPM.exe`: maximize and restore from
  several normal sizes on each monitor. Confirm the internal UI always scales
  uniformly from the centre without clipping, the final handoff has no visible
  jump, and the existing Win+Shift+Arrow restore-on-current-monitor rule
  remains intact.

## Isolated Startup Briefing Read and Splash-Critical Deferral (2026-08-18)

- [x] Diagnose the latest packaged crash from the durable local log and fault
  capture.  The visible process reached `briefing-snapshot-loading`, then a
  pooled worker hit a native access violation while `openpyxl` parsed the
  Practice Briefing workbook; the native splash paint thread was healthy.
- [x] Move the initial Practice Briefing read into a short-lived, GUI-free
  helper process operating on a private copy of the workbook data.  Its JSON
  result is accepted only when complete and valid; a worker exception, native
  exit, or 120-second timeout now fails the readiness gate safely instead of
  taking down CSPM.
- [x] Preserve useful diagnostics for that isolated path: the parent records
  the worker PID, exit code, response failure detail, and any Python traceback
  in the durable application log.
- [x] Keep `TrayRoot.qml` and its auxiliary QML windows off the splash-critical
  path.  The native tray remains available, while TrayRoot is loaded only after
  the cinematic handoff (or on an explicit tray click), preventing its hidden
  windows from producing a background flash during splash loading.
- [x] Rebuild and validate the repaired local EXE.  Standard promotion
  succeeded; `dist\\CSPM\\CSPM.exe` SHA-256 is
  `8FA6B2CD0E4B66FB420185045EC61C45328953E8EFF58D6E034FD895651C82AE`.
  The full 4,357-file / 678,563,551-byte installed tree manifest is
  `3CC470576E16A62F68866EE4547A1A8FF29F94D4CA973B06771B6A5ABAD578B4`,
  and both splash-critical packaged QML files exactly match source.  The prior
  package is recoverable at
  `to_delete\\dist__replaced_release_20260818_120539`.
- [x] Diagnose and eliminate the remaining pre-bloom full-window flicker from
  fresh packaged logs.  At `ready-to-reveal`, the staged full-size QML host was
  shown with `opacity: 0.001` before its frozen pinpoint snapshot existed;
  Windows can quantize that value into one visible live-content compositor
  frame.  The host now stays at exactly zero opacity through prestage, and it
  becomes compositable only at the native plasma handoff after the 0.2%
  snapshot/fallback is already in place.  First-pixel accounting also moves to
  that real release point.
- [x] Rebuild and hash-verified copy-promote the anti-flicker EXE after Windows
  denied the normal final directory rename.  `dist\\CSPM\\CSPM.exe` SHA-256 is
  `C2CBF78B7403D1F272753CCCD3B3F9AF33C2F0F6CA58E3C0105F99857A58D305`; its
  full 4,357-file / 678,564,228-byte manifest is
  `FCBC237B654ECE74F3AD01D162AA000FE707E9B3E48CD9195E025D7AEF111E58`.
  The prior package remains recoverable at
  `to_delete\\dist__manual_replaced_release_20260818_125930`.
- [ ] Manual foreground verification: launch `dist\\CSPM\\CSPM.exe`. Confirm
  progress leaves 0% promptly, no black auxiliary window flashes behind the CS
  logo, the worker reaches a hydrated briefing snapshot, and the full cinematic
  sequence completes.  If it fails, review `%LOCALAPPDATA%\\CSPM\\logs\\cspm.log`
  for the isolated-worker result rather than expecting the main process to
  crash.

## Native CS Splash 0% Startup Stall and Source Crash (2026-08-18)

- [x] Make the application diagnostic log durable: development runs append to
  `logs/cspm.log`; packaged runs append to the release-independent
  `%LOCALAPPDATA%\CSPM\logs\cspm.log`. Each launch records an ISO-timestamped
  application-start boundary, with no automatic rotation or retention
  deletion. `faults.log` likewise records a timestamped fault-capture session
  boundary.
- [x] Rebuild and promote the pulled source to `dist\CSPM\CSPM.exe`. The
  promoted 4,357-file package manifest is
  `61E84C0FA3D2BC082FF598DB19C1FFA14B6497E5040612160B7C9C7E761DD2A9`
  and the EXE SHA-256 is
  `B47230E863B32B535464771433257E6C01F13AA57DE8480FD6D23402820DE686`.
- [ ] Manual foreground verification after the rebuilt package is promoted:
  launch `dist\CSPM\CSPM.exe`, confirm the full cinematic readiness sequence,
  then confirm `%LOCALAPPDATA%\CSPM\logs\cspm.log` contains both the prior
  launch and the new timestamped session rather than replacing either.

- [x] Diagnose the latest packaged launch from `dist\logs\cspm.log`: the
  process was alive and responsive, with no Windows crash event, but never
  loaded `Main.qml`, entered Bootstrap, or began Practice Briefing readiness.
  The native logo was first painted at 3.66 s and remained at 0% indefinitely.
- [x] Close the verified stuck local `dist\CSPM\CSPM.exe` process (PID 75108).
- [x] Restore a reliable startup trigger: `show_first_frame()` intentionally
  stops the legacy fade animation after its painted frame, so waiting for that
  animation's `finished` signal left Main.qml permanently unrequested.
- [x] Diagnose and repair the subsequent source launch crash. The fresh root
  runtime log reached `briefing-snapshot-loading` then exited with
  `0xC0000005`; the shared-data checkout message merely put the session in its
  intended safe read-only mode. Loading Main.qml synchronously while Qt was
  still completing pre-event-loop setup was unsafe. It is now queued for the
  first event-loop turn (`QTimer.singleShot(0, ...)`): no timed delay is added,
  and the existing `objectCreated` hook binds Bootstrap even though TrayRoot
  has already been created.
- [x] Add a regression guard that prohibits the stopped animation being used as
  the Main.qml trigger. Python compilation and focused startup/window tests
  passed (**11 passed**).
- [x] Rebuild and copy-promote the complete local package. `dist\CSPM\CSPM.exe`
  SHA-256 is `F9637A540573C1EE6A555CFD1AF4FC59F781F107721D8B535A456810FFA0F819`;
  the post-promotion 4,272-file package tree matches candidate SHA-256
  `36C584F3540560CCA5B14B491C07029113C6693CB9B2DEB6E9E5A621EFD8933E`.
  The prior package is retained at
  `to_delete\dist__manual_replaced_release_20260818_081028`.
- [ ] Manual foreground check: launch the new `dist\CSPM\CSPM.exe`. Confirm
  that the CS splash begins QML/bootstrap work immediately after its first
  painted frame, progress leaves 0%, and the Practice Briefing appears without
  an indefinite splash hold.

## Practice Briefing-First Idle Loading (2026-08-18)

- [x] Audit the normal startup path: `MainContent` was starting a timer that
  eagerly loaded all four unopened workspace stacks after the landing screen
  appeared, because the existing deferred queue was disabled by default.
- [x] Make the Practice Briefing snapshot and its landing consumer the only
  required opening data path. Unopened module stacks are no longer prewarmed;
  they load only when the user opens their module/tab.
- [x] Enable the existing post-settle queue for optional current-screen work
  and require a 900 ms quiet window before it may execute. Every click,
  keypress, touch, or wheel input refreshes the quiet window, so pending work
  cannot compete with active use. `CSPM_STARTUP_BACKGROUND_IDLE_MS` remains an
  explicit 250–10,000 ms tuning override.
- [x] Add controller/source regression coverage for repeated activity updates,
  the idle queue policy, and the disabled unopened-workspace prewarm.
- [x] Rebuild and hash-verify the local package at `dist\CSPM\CSPM.exe`
  (SHA-256 `458AB6B6808EB26AA127023A56E292224C905BCE008049F5048F27D85C0ACD78`).
  The normal builder completed both bundles and validation; Windows denied its
  final rename, so its complete candidate was copy-promoted only after a
  matching 4,272-file / 674,098,975-byte tree hash check
  (`189FB91A4DC58E1E55415CA3C156B77251D4352E51DE9C946B8EBA3D354C4B55`).
  The replaced release is retained at
  `to_delete\dist__manual_replaced_release_20260818_000744`.
- [ ] Manual foreground check: launch with `./launch.ps1`, confirm the Practice
  Briefing is responsive immediately, then open a module while clicking or
  typing. No background task should run until roughly one quiet second after
  the final interaction; newly opened modules must load only their own data.

## Native Splash / QML Prestage Flash (2026-08-17)

- [x] Diagnose the full-screen flash immediately before the native splash
  reaches 100% from the fresh packaged runtime log. The 0.2% QML pre-stage
  emitted its usual first-pixel signal, whose generic handler requested QML
  foreground focus above the still-visible native splash.
- [x] Keep the native splash foreground through the pre-rendered QML centre
  pinpoint. Its first-pixel signal is now a staging acknowledgement only;
  it never requests focus or releases a normal splash. The native plasma
  handoff releases that pre-rendered canvas directly, avoiding both the flash
  and the post-implosion QML host-creation delay.
- [x] Preserve the native CS spin/shrink/plasma animation: ignore mouse/key
  input received during loading instead of remembering it as a future skip.
  Input can still skip a cinematic act only after that act has visibly begun.
- [x] Add regression coverage that requires the hidden prestage acknowledgement
  and its focus-holding `phase2-native-prestage` launch gate.
- [ ] Rebuild and hash-verify the repaired local package at
  `dist\CSPM\CSPM.exe`.
- [ ] Manually launch the repaired package and confirm there is no whole-screen
  flash before 100%, the CS spin/shrink/plasma burst is visible, and the
  native implosion hands directly to the QML centre-out bloom. Do not advance
  the UI audit until this exact visual check is confirmed.

## Packaged Professional Startup Crash Guard (2026-08-17)

- [x] Diagnose the local packaged startup crash: Windows Error Reporting
  recorded `CSPM.exe` access violation `0xC0000005` in bundled
  `python314.dll` immediately after the Professional hidden-shell preload
  began. The governed workbook checkout and backend boot completed normally;
  this was not a live-data failure.
- [x] Serialize Phase 1 startup so the authoritative Practice Briefing worker
  completes and returns to the main event loop before the heavyweight hidden
  `DetachedShellWindow` begins compiling/creating. This removes the observed
  native worker/shell-preload overlap while retaining the no-empty-dashboard
  readiness gate.
- [x] Rebuild and hash-verify the guarded package at
  `dist\CSPM\CSPM.exe` (SHA-256
  `3BF375C7D336684421F0E76484AD466C6F76D462EBB2FDDB524DF1C0A3E7C34E`).
  The 4,272-file installed tree matches its candidate exactly; the prior
  package remains recoverable at
  `to_delete\dist__manual_replaced_release_20260817_212137`.
- [ ] Manually launch `dist\CSPM\CSPM.exe`; confirm it reaches the hydrated
  Professional landing screen without an access violation. Do not continue the
  UI audit until this exact startup check is confirmed.

## Cinematic Opening Sequence — Phase 1 Readiness Gate (2026-08-17)

- [x] Establish a data-backed, hidden **ready-to-reveal** gate for the first
  Professional workspace. The main window is created with `visible: false`;
  persisted briefing rules, workbook schema, and one complete Practice
  Briefing snapshot now finish before the normal launch gate can reveal CSPM.
- [x] Hydrate both consumers of that snapshot before reveal: the actual
  Professional landing surface (`DailyOperationsHome`, including **WIP to
  review**) and the named Practice Briefing view. Neither may schedule its
  initial direct workbook read while startup preparation is pending.
- [x] Hold the native splash safely on preload failure instead of revealing an
  empty dashboard. The eventual retry/recovery controls and cinematic progress
  presentation remain Phase 2 work.
- [x] Add focused regression coverage for valid-snapshot acknowledgement,
  failed-snapshot withholding, and the Professional landing-home handoff
  (`tests/test_startup_briefing_readiness.py`).
- [x] Serialize the optional startup metadata warm-up behind the hidden
  snapshot handoff. It no longer competes with the opening snapshot for the
  Excel repository/cache; a source launch that ended with native access-
  violation code `0xC0000005` exposed the unsafe overlap, although no Python or
  QML exception was emitted before the process stopped.
- [x] Manual foreground validation: the first `./launch.ps1` run correctly
  exposed that `DailyOperationsHome` still used its independent zero fallback
  (`WIP to review`: `$0` then `$10.1K`). Its handoff and metadata-warm race were
  repaired in source; the follow-up source launch confirmed that the landing
  home opens pre-hydrated with the real value. The current splash/window
  handoff visual is deliberately unchanged until Phase 2.
- [x] Phase 2 implementation: the native splash bar now follows only the real
  readiness milestones and reaches 100% only after `ready-to-reveal`. It then
  runs the approved 550 ms accelerating 0°→1080° logo vortex, 150 ms plasma
  flash, 80 ms hold, and 220 ms cubic implosion before it hides. Only then does
  the fully hydrated QML shell run its 400 ms centre-point bloom. Space, Enter,
  Escape, or a click skips the active act without opening a non-ready shell.
- [x] Shutdown hardening: `MainContent` cancels pending asynchronous lazy-page
  loaders before close and binds each loader's `active` state to that shutdown
  flag. The benign tray-resident `lastWindowClosed` lifecycle event is now an
  info diagnostic rather than a warning.
- [x] Phase 2 handoff tightening: the final shell geometry is now calculated
  while the native vortex/plasma sequence remains on-screen. The final plasma
  frame hides and emits its handoff in the same event turn, and Act III starts
  its deliberate 400 ms centre-point bloom without an extra queued callback.
- [x] Phase 2 flash-free joining: the QML shell is fully hydrated and rendered
  at a 0.2% frozen centre pinpoint during the native acts, but its first-pixel
  staging signal never takes focus. The native splash remains above it through
  the final progress fill, vortex, and plasma sequence, then releases the
  prepared 400 ms centre-out bloom in the same handoff turn.
- [x] Remove the pre-logo native flash: replace the empty-pixmap
  `QSplashScreen` base with a transparent `QWidget`, and begin the logo
  dissolve only after its custom logo frame has been painted while invisible.
- [x] Build and copy-promote the complete cinematic-opening release at
  `dist\CSPM\CSPM.exe`. The normal builder completed both executables and
  templates, validated the package, and safely quarantined the replaced
  release before promoting the new directory.
  The executable SHA-256 is
  `711D29CBCC7A89006A51C277C96DED2B80063789F223409D05C6660CF6D40E24`;
  the prior local release is recoverable at
  `to_delete\dist__replaced_release_20260817_200142`.
- [x] Keep restore-from-maximized on the monitor that currently owns the
  maximized window. The restore glyph resolves the raw native `Window`
  x/y/width/height at click time (never internal canvas/content offsets), so a
  Windows `Win+Shift+Arrow` monitor move is honored even if it bypasses QML's
  cached maximize state. The cached maximize owner is recovery-only. The saved
  normal rectangle is proportionally mapped/clamped within the live monitor;
  cursor-anchored restore-on-drag remains unchanged.
- [x] Remove the Fusion `ModernComboBox` implicit-height binding loop by keeping
  unlabelled combo padding independent of `control.height`.
- [x] Restore the readable close choreography: the live app remains fully
  visible while it shrinks into its centre pinpoint for 493 ms of a 1,120 ms
  sequence; only then do the 146 ms plasma burst, 146 ms hold, and 336 ms
  inward implosion render. The close path also freezes the actual source-monitor
  geometry before the first animation frame.
- [x] Add focused static regression coverage for same-monitor maximize restore
  and the close-act boundaries
  (`tests/test_maximized_restore_and_close_choreography.py`).
- [x] GPU Maximize/Restore Phase 1A source implementation: Professional now
  captures the fully composed pre-transition content frame and uses that single
  GPU image as the only visible surface during a 205 ms (120 ms
  low-performance) `OutCubic` rectangle tween. The live responsive hierarchy
  reflows invisibly underneath and is revealed only at the matching final
  frame; the reverse path temporarily retains its transparent monitor-sized
  host until its snapshot has visibly contracted. This preserves the
  live-native-monitor rule for a `Win+Shift+Arrow` transfer without stepped
  resizing or intermediate content reflow.
- [ ] Manual GPU Maximize/Restore Phase 1A verification: launch from source
  with `./launch.ps1`; on each monitor, maximize and restore CSPM and confirm
  a single 205 ms centre-out/centre-in visual morph with no flash, duplicate
  motion, or monitor jump. While maximized, transfer it with
  `Win+Shift+Arrow`, then click restore and confirm it remains on that current
  monitor. The local EXE contains this transition; the foreground check is
  still required because it cannot be validated inside this environment.
- [ ] Manual Phase 2 foreground verification: launch via `./launch.ps1`; verify
  that no app pixels precede the splash's plasma implosion, that the bar holds
  below 100% until data readiness, that the landing values never change after
  reveal, that the app begins blooming immediately from the implosion point,
  that each skip input snaps safely to the hydrated UI, that maximizing on one
  monitor then clicking the restore glyph keeps CSPM on that monitor, that a
  normal close visibly contracts the entire window before its burst, and that
  no close logs the in-progress-QML-item warning.

## Strategic Roadmap Rebaseline (2026-08-16)

Status: long-term direction recorded; no code, workbook, database, or release
artifact changed by this planning update.

- [x] Consolidate the approved long-term SQL, Ontario trust-accounting,
  GST/HST, income-tax, professional-corporation, household, and family goals in
  `docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md` and align the primary roadmap
  documents to it.
- [ ] Complete the active 10/10 financial-correctness, data-protection,
  packaged-app, and Professional-first manual-audit gate before beginning a
  broad SQL migration, live trust module, tax-preparation workflow, or direct
  filing integration.
- [ ] Continue the manual audit one problem at a time. The current required
  starting point remains New Matter Client dropdown / New Client handoff in
  Professional, Console, and then the detached-window path after the user
  confirms each preceding result in the real app.
- [ ] After explicit post-10/10 authorization, specify the financial-context
  model and versioned regulatory rule matrices before building any regulated
  write path. Contexts: Client Trust, Sole Proprietor Practice, future
  Professional Corporation, and Household.
- [ ] After the financial-context specification, perform the governed local
  SQLite migration with reconciliation, backup/restore, report-parity, and
  OneDrive-snapshot gates. Excel must not remain a parallel editable source of
  truth after a controlled cutover.
- [ ] After SQL cutover proof, deliver the dependent regulated workstreams in
  the documented order: Ontario trust accounting and Form 9A support;
  per-registrant GST/HST workpapers and calendar tasks; personal/
  sole-proprietor and future-PC tax workpapers; then household/family finance
  and attributed tax-preparation workflows.

The detailed acceptance criteria, official-source references, deadline behavior,
and explicit deferrals are in
`docs/CSPM_REGULATORY_TAX_AND_TRUST_ROADMAP.md`. Do not reorder these
dependencies merely because an individual report or screen already exists.

## Controlled Cross-PC Workbook Merge Gate (2026-08-12)

- [x] Read this PC's configured local and shared paths from `%LOCALAPPDATA%\CSPM\user_settings.json`; local is `C:\Users\CorySchneider\AppData\Local\CSPM\Data`, shared is `C:\Users\CorySchneider\OneDrive - LPN\CSPM_Shared_Data`.
- [x] With CSPM and Excel closed, create protected local and OneDrive-exchange recovery packages for CSPM.xlsm and Dockets.xlsm. The snapshot label is `Recovery_THIS_PC_20260812T102018`; no active `.bak` files existed.
- [x] Verify the other-PC exchange package `CSPM_Merge_Exchange\From_THIS_PC_20260812_000148` is locally hydrated, validate its hashes, and fast-forward source safely to `d210ce0` without touching unrelated untracked build folders.
- [x] Create and repair the isolated candidate `CSPM_MergeCandidate_20260812T105809` from recovery copies only. It preserves invoices `26-0092` and `26-0095`, keeps Dockets byte-identical, adopts Suffolk payment `TXN_59133aca6a` / `LED_dbc8eeeb2b`, retains CIPO vendor expenses without CIPO billing artifacts, repairs all documented legacy reconciliation failures, and restores the `Legal Practice` lookup required by the incoming payment.
- [x] Verify the repaired candidate with the workbook integrity gate using `--warn-as-error` (0 errors, 0 warnings), package ZIP/openpyxl checks, duplicate-ID check, invoice/receivable/payment/ledger reconciliation, intended invoice states, Suffolk evidence, and CIPO assertions. `merge_validation.json` reports `ok: true` and candidate CSPM SHA-256 `6AC5FBDCDECF023C019F46B92EB73DC371FC9A88FCBD708DC742D8BFE7FA2626`.
- [x] Verify the separate open SharePoint workbook is not a live promotion target, then transactionally promote the candidate to this computer's active local folder and the canonical OneDrive shared folder. Full paired recovery archives and a pre-promotion manifest are at `merge_promotions\Promotion_20260812T112927` and `CSPM_Merge_Exchange\Promotion_20260812T112927`; local/shared post-promotion package hashes match the candidate exactly.
- [x] Build and promote the runnable C-drive release at `C:\Projects\__CSPM\dist\CSPM\CSPM.exe` (SHA-256 `FF32E1F711142E7468587171545585A36387D2048E202A8B9FD2BE0C9F1248C0`). The verified 4,344-file package tree was copy-promoted after the release builder's final directory rename was denied by Windows; the replaced package and promotion manifest remain at `to_delete\dist__manual_replaced_release_20260812_121639` and `to_delete\release_promotion_20260812_121639.json`.
- [x] Recheck settings and launch only that newly built EXE. Settings remain unmodified and point to this PC's AppData data folder and canonical OneDrive shared folder. The responsive `CSPM - Main Menu` process (PID 9084) holds the matching `.cspm_checkout.json` lease, which validates the guarded writable checkout without entering a test financial transaction.
- [x] Repair Statement of Account header branding and add the firm address, phone, and email to the active `Concept_A2` invoice header. The Statement renderer now uses a Qt-trimmed logo raster to remove SVG padding, then draws the visible mark at a fixed `0.90 in x 0.57 in` alongside the firm block; the rendered header is aligned and non-overlapping. The verified C-drive release is promoted at `dist\CSPM\CSPM.exe` (SHA-256 `87F88FB5ADD01B89016C7EC031C5492F8CB74E737BB3FD885BA104FAC9BC71C2`) and passed an 80-second real startup/checkout check.
- [x] Add universal joint-retainer intake. Matters can now contain an unlimited set of independent existing or newly created directory clients, with one compatibility file anchor, explicit party roles, a joint-information acknowledgement, joint-instruction setting, engagement-document reference, and per-party billing-recipient flags. Client profiles remain separate; the linkage lives on the matter and in deliberately written notes only. Draft billing asks for a recipient only where a joint matter exposes more than one eligible billing recipient; ordinary single-client invoices retain the direct draft workflow.
- [x] Create the verified Britton joint-retainer records from the signed engagement letter in an isolated workbook candidate, then promote only after integrity, cross-PC invoice, reconciliation, ID, Dockets, CIPO, and local/cloud hash checks passed. The live matter is `BRIT-CRP-26-0195`, with Susan Mary Britton and Gary Edward Britton as independent joint clients and the two represented corporations as non-billing parties; outstanding KYC/conflict/file-opening checks are recorded on the matter rather than inferred as complete.
- [x] Synchronize the subsequently provided Britton contact details into the joint-retainer client profiles, then add the two independent client records and the same durable matter number to the separate legacy OneDrive Dockets workbook. The legacy operation populated only its reserved blank Clients/Matters rows; package validation confirmed the VBA project, table ranges, existing records, and all non-target workbook parts were unchanged.
- [x] Build and promote the joint-retainer C-drive release from source. The full 4,344-file package was hash-verified before and after promotion; the prior release is retained at `to_delete\dist__manual_replaced_release_20260812_170937`. The single real startup check passed: `dist\CSPM\CSPM.exe` (SHA-256 `10F3BC13B00B9AD6FACA712C8E044AA821A94FF5B7ECC05C030CDACEF05A9EB0`) is responsive as `CSPM - Main Menu` and holds this computer's matching writable cloud checkout.
- [/] Repair Matter Profile 360's stale details model: the repository returns the Britton matter's `Joint Retainer` payload and all four parties, but the visible card grid can retain the earlier directory-row snapshot. The UI now receives an explicit refreshed row model. Sandbox-safe QML parsing, Python compilation, and focused joint-retainer/matter-merge tests passed; the hash-verified C-drive release was promoted at `dist\CSPM\CSPM.exe`. Real-app confirmation is still required before moving to the requested Matter/Client Zen and PDF-report commands.

## Native Productivity Report (2026-08-13)

- [x] Replace the `D10` **Productivity & Utilization** generic placeholder with a native CSPM Productivity Report: start/end dates, editable annual target, the seven legacy quick presets **plus Today**, realized-production KPIs, annual forecast, top clients, and four-month/seven-day trends.
- [x] Preserve the legacy calculation contract: docket value is adjusted to booked invoice billings where an invoice was written down; forecast defaults to the legacy 336-day planning basis but now uses the user-editable **Settings → Productivity Forecast** value; trend windows are anchored to the selected end date. The report is read-only against the active workbook package.
- [x] Add a branded, one-page native PDF export from the exact displayed report payload, plus focused realization/date-range/PDF regression coverage.
- [x] With CSPM closed, build and verify the complete runnable package at `dist\CSPM\CSPM.exe` without touching active cloud data. The final 4,312-file release tree was hash-verified before and after copy-promotion (tree SHA-256 `81C6FB0A03C2EBF3AADD4BC711512DE046EA6C4B9B4D2FF473856406222C9C06`); `CSPM.exe` SHA-256 is `A287DDF24934034F8AA9D4825EB710D530E6883AC5D609E5E3BED5D8613836A6`. The replaced package is recoverable at `to_delete\dist__manual_replaced_release_20260812_220219`, with the promotion audit at `to_delete\release_promotion_20260812_220219.json`.
- [x] Correct the first runtime D10 failure: the packaged report loader rejected fractional `font.pixelSize` values (`int expected`) and the generic form remained visible beneath it. Font sizes are now valid integers and D10 is explicitly excluded from the generic fallback form. The corrected 4,312-file package at `dist\CSPM\CSPM.exe` was hash-verified with tree SHA-256 `C8E482910AB409B258D0B83C87E36C996497CF07A3CB26AEEA74862E7F2CD5C4`; `CSPM.exe` SHA-256 is `851536B9B9A7562F1693519F49E3E1DF20E563812F453FCECD781D86122BED4A`. The preceding package is recoverable at `to_delete\dist__manual_replaced_release_20260813_064704`, with audit `to_delete\release_promotion_20260813_064704.json`.
- [x] Make the full **My productivity** card on the no-tabs Daily Operations home an explicit click target for D10. It now has an all-card `MouseArea`, pointer cursor, and hover treatment; clicking anywhere opens the single-instance **Productivity & Utilization** workspace tab. Source-level interaction coverage passes; packaging is deferred until CSPM is closed.
- [x] Redesign native D10 around a fixed no-scroll report canvas: a narrow left **Report Parameters** rail contains dates, annual target, a full-width **Generate Report** action, and quick ranges; the wider right canvas contains the executive report, KPIs, forecast, clients, and charts. Add a **Zen View** action that reparents the same live panel into a maximized report window, and make the informational **Live Data · Read Only** status explain its no-write guarantee on hover. With CSPM closed, the complete 4,312-file package was hash-verified before and after promotion at `dist\CSPM\CSPM.exe` (tree SHA-256 `90C30953A4D2E18C086789E080A2A0F5D91FA5B24E74AF9D709BCAFA6DF93D15`; EXE SHA-256 `01397905B0CF4B9EB0FEC5C5B72D5DC7B5473F7535F80869C3BE0B3EB94CA531`). Packaged QML parses and instantiates; the preceding release is recoverable at `to_delete\dist__manual_replaced_release_20260813_070957`, with audit `to_delete\release_promotion_20260813_070957.json`.
- [x] Increase D10’s Start Date, End Date, and Annual Target entry fields from 46px to 56px so their stacked labels and values do not clip in the narrow parameter rail. With CSPM closed, the complete 4,312-file package was hash-verified before and after promotion at `dist\CSPM\CSPM.exe` (tree SHA-256 `62090FD081AD575ED3D0CE7FF8280C3600BBF0359108E908BDAC8F876719791A`; EXE SHA-256 `B1F449854BD6D807AC327FECCB41D79B034CDE8851FAB85585ED6CCF7AE1B786`). Packaged QML parses and instantiates; the preceding release is recoverable at `to_delete\dist__manual_replaced_release_20260813_072500`, with audit `to_delete\release_promotion_20260813_072500.json`.
- [x] Expand **Settings → Productivity Forecast** from one opaque annual-basis input into a schedule model: scheduled workdays per week; vacation, public holidays, and other unavailable time expressed only as scheduled workdays; calculated 52-week basis; and an explicit manual override. Existing 336-day forecasts remain unchanged until the calculated basis is deliberately enabled.
- [x] Remove the illegal Zen View cross-window reparenting that generated render-thread warnings; Zen now opens a separate read-only presentation from the same displayed report snapshot.
- [x] Improve Professional title-bar responsiveness without removing transition graphics: make minimize/maximize/close hover and press states explicit; begin the existing close motion immediately rather than waiting for a full-frame capture; and use a live, read-only minimize overlay to avoid that capture delay.
- [x] With CSPM closed, build and hash-verify the complete Productivity/settings/window-motion release at `dist\CSPM\CSPM.exe`. The 4,313-file promoted tree matches the isolated build candidate byte-for-byte; EXE SHA-256 `FC000EC08EEAFE3E3875EB0C8DC1E5C9D10FDC57E679499614EB7A65A2231A5C`. The preceding release is recoverable at `to_delete\dist__manual_replaced_release_20260813_080600`.
- [ ] Manual foreground verification: open `D10`, test every preset and an edited annual target, compare a selected period to the legacy report, then export and review the PDF in both light and dark themes.
- [x] Remove the redundant D10 **Generate Report** button. The report now regenerates on a committed Start Date, End Date, or Annual Target edit, as well as after calendar selection and every quick range. Source changed only; packaging is deliberately deferred while CSPM is open.
- [x] Repair the Legacy Dockets Import review’s safe selection: it now compares docket commercial fields with occurrence-aware matching so migrated client/matter labels do not cause historical entries to be selected again. After the explicit safe-selection click, show a visible summary card with dockets, hours, WIP, and required client/matter setup. With CSPM closed, the full 4,315-file package was hash-verified and copy-promoted to `dist\CSPM\CSPM.exe` (tree SHA-256 `257B9DCD03802DBB874E9C5A1C031A18A7CE4C8ECB892C0933EFF85284FE2967`; EXE SHA-256 `1F173F0C0827B7EE35318F68337D680643E709A8DA542FF2E5F0867F191A3C0A`). The prior release is recoverable at `to_delete\dist__manual_replaced_release_20260813_180636`.

## Matter WIP Reconciliation and Archived-File Safeguards (2026-08-13)

- [x] Add an audited **Reconcile Selected** action to the WIP workbench. It records an entered destination invoice/reconciliation reference and reason, changes only the selected residual time/fee entries to read-only `Reconciled`, and never creates, alters, reverses, or pays an invoice.
- [x] Keep reconciled entries out of WIP permanently, preserve their audit trail on subsequent table writes, and prevent future time entries from merging into reconciled historical entries.
- [x] Treat an associated real Draft Invoice as a financial blocker: the user must use Invoice Builder’s existing **Delete Draft** (or finalize it) before reconciliation or archiving. Matter status validation now reports the linked draft number(s) rather than silently archiving the file.
- [x] Ensure archived/closed matters never appear in WIP. Add an authoritative repository guard for new time, direct-fee, and client-disbursement entries; stale UI state or direct calls cannot bypass it.
- [x] For an Archived matter only, require the three-stage protected re-open flow: archived warning → exact typed `REOPEN <Matter Number>` → distinct final **Confirm and save** of the actual time/fee/client-disbursement entry. The re-open is recorded in Matter Notes; it does not itself create a financial entry.
- [x] Diagnose the Borkowsky WIP discrepancy without changing financial data: fourteen historical Borkowsky/Suffolk rows total `$7,362.50` and the transfer row is `-$7,362.50`; the separate `$148.75` row is a PLC Group Inc. docket misfiled against Borkowsky and must be moved to its proper PLC matter rather than reconciled to Suffolk.
- [x] Preserve selection through WIP tab-state restores, filtering, sorting, and ordinary list refreshes. A reusable blocking **Selection changed** dialog now explains any removal caused by a docket actually leaving the worklist; the Bulk Docket Move screen follows the same contract when its query changes or candidates become ineligible.
- [x] Make non-zero WIP reconciliation deliberate: the dialog displays the selected total, requires a second explicit acknowledgement when it is not `$0.00`, and the repository independently rejects a non-zero reconciliation unless that confirmation is passed.
- [x] Repair the B05 matter selectors' vertical text layout, add double-click Jelly Calendar access for both date fields, and lock its placement to the exact centre of the monitor containing the initiating date field. The destination selector uses the same corrected field geometry.
- [x] Add a blocking, prominent **Dockets moved successfully** confirmation after a completed B05 move; use **OK** (not Cancel) for the non-reversible Selection changed acknowledgement.
- [x] Reduce the Matter Profile 360 top action-strip footprint, enlarge its Statement of Account action, make the Joint Retainer selector visible in light and dark themes, and add a confirmed **Archive Matter** action to the editor. Archiving retains all records and invokes the existing financial-blocker and protected re-open safeguards.
- [x] Build and hash-verify the complete runnable release at `dist\CSPM\CSPM.exe` without opening or changing live CSPM data. The 4,314-file package manifest is `BCB21CB79FE1B2D18745824E03BF13B0D5D6E5F402E57254DE56C47EADEC529F`; EXE SHA-256 is `29282AD0BAC6DE1598975F513C69580A37477619F30BE984F9640D07FDFA747A`. The replaced package is recoverable at `to_delete\dist__manual_replaced_release_20260813_105635`, with promotion audit `to_delete\release_promotion_20260813_105635.json`.
- [x] With CSPM closed, build and hash-verify the selection-retention/non-zero-reconciliation release at `dist\CSPM\CSPM.exe` without changing live data. The 4,315-file promoted tree matches the candidate (manifest SHA-256 `344E11B5ACB8A9815932ED833C10BCD15922BEDA4357472E052B1053C8B71F73`); EXE SHA-256 is `A78BBEB09CC5F0A93393371C0773CE100B19FF6B381B521F709B89D562C17F2B`. The immediately preceding release is recoverable at `to_delete\dist__manual_replaced_release_20260813_112156`, with promotion audit `to_delete\release_promotion_20260813_112156.json`.
- [x] With CSPM closed, build and hash-verify the B05/Matter Profile visual-workflow release at `dist\CSPM\CSPM.exe` without changing live data. The 4,315-file promoted tree matches the verified candidate (manifest SHA-256 `73A01E6DCE1DC2B25CA0CAB33E8AF5CA9B5C1BF19A641A85F7FEF34426C342EF`); EXE SHA-256 is `2C29636E917227DF3B1C52194FEBA13731518FCBA34BF38A581E73374C9E9543`. The prior release is recoverable at `to_delete\dist__manual_replaced_release_20260813_121312`, with promotion audit `to_delete\release_promotion_20260813_121312.json`.
- [ ] Manual foreground verification: double-click each B05 date field on every monitor and confirm the Jelly Calendar's centre exactly matches that monitor's centre; type/filter a matter in both B05 selectors with no clipping; complete a test move and confirm the prominent success dialog; confirm reconciliation's non-reversible acknowledgement uses **OK**. Confirm the visible Joint Retainer control and Archive Matter confirmation in Edit Matter Profile. Then move the misfiled PLC `$148.75` docket using **B05 Move Dockets Between Matters**; select the remaining Borkowsky rows, confirm they total `$0.00`, reconcile them to Suffolk `26-0080`, then archive Borkowsky and test the protected re-open flow. Also confirm WIP selections survive tab-state restore, filtering, sorting, and Refresh; confirm the explanatory dialog appears only when selected records genuinely leave the list.

## In-App Legacy WIP Catch-Up (2026-08-13)

- [x] Add **Select Safe Docket Update** to Legacy Dockets Import's analysis-review grid. It selects only newly identified dockets plus any newly required client/matter rows; it explicitly leaves ledger, A/R, invoices, disbursements, and unrelated legacy setup records unselected.
- [x] Manual foreground workflow completed through **Legacy Dockets Import**: **Select Safe Docket Update** selected 18 true source-only dockets plus the required H. Kassinger client and Tax Audit matter—no finance rows. **Import Selected Data** added 20 records. WIP now has 51 Draft entries totalling `$27,101.65`; the 14 Borkowsky historical entries remain Reconciled and excluded.

## WIP Zen Selected-Row Theme Repair (2026-08-13)

- [x] Define the missing shared `SemanticTheme.tableSelectedBackground()` token as an opaque, contrast-safe blend for both light and dark themes. This eliminates the Zen workbench's repeated QML TypeError and its white-on-white selected rows.
- [x] Build, validate, and copy-promote the complete release at `dist\CSPM\CSPM.exe` (tree SHA-256 `6417E40B1ABCE09258923976C6251A078740FC4DBB72F56CFF3923F174DD8B6E`; EXE SHA-256 `C699444A2B3A68340503213E51F0D0372D255E6B599DE2C485C34A203DDDBA60`). The replaced release is recoverable at `to_delete\dist__manual_replaced_release_20260813_183840`.
- [ ] Manual foreground verification: in both Light and Dark mode, open WIP-to-Bill, select several rows, then open Zen Mode. Selected rows must remain visibly distinct with readable text; the runtime log must have no `tableSelectedBackground is not a function` warning.

## Closing Transition Monitor Affinity (2026-08-13)

- [x] Freeze the close animation's content geometry and source monitor from the native window position at the instant the user initiates Close.
- [x] Keep the Console closing overlay hidden until that source monitor and its frozen global geometry have been explicitly applied.
- [ ] Manual foreground verification: place CSPM on each monitor in turn, press Close from that monitor, and confirm the entire animated closing transition remains on that same monitor in both Console and Professional styles.

## Cloud-Canonical Checkout / Publish (2026-08-11)

- [x] Replace the unsafe timestamp-based local/master copy logic with package SHA-256 comparisons and a recorded common ancestor for `CSPM.xlsm` plus `Dockets.xlsm`.
- [x] Make the configured OneDrive shared folder canonical and require an exclusive `.cspm_checkout.json` writer checkout before CSPM enables any Excel-repository save.
- [x] On normal exit, publish only a checked-out local change after creating a verified, immutable full-package release under the shared folder's `.cspm_releases/`; then release the checkout.
- [x] Refuse unknown or divergent local/cloud copies without overwriting either; preserve local files and fail safe as read-only.
- [x] Replace the setup wizard's unconditional baseline copies with safe empty-cloud seeding and conflict detection.
- [x] Add isolated tests for fresh-machine checkout, second-PC blocking, release publish, publish-time cloud conflict, blank seed handling, and existing-cloud setup protection.
- [ ] Manually recover and merge the other PC's `26-0092` / `26-0095` correction before allowing this PC's existing divergent local package to become the cloud baseline.
- [ ] Manual two-PC verification after recovery: open CSPM on PC A, confirm PC B is read-only while A holds checkout; save/close A; open B and confirm it pulls A's release before edits.

## Statement Matter-Link Dark Contrast (2026-08-11)

- [x] Override Qt RichText's default dark link colour for clickable matters in Statement of Account with high-contrast `#93C5FD` only when the app is in dark mode.
- [x] Preserve the existing light-mode matter-link treatment and ordinary Client & Matter text.
- [x] Add focused regression coverage for the dark-only inline link-colour markup.
- [x] Rebuild and copy-promote the complete cloud-checkout release at `dist/cspm.exe` / `dist/CSPM.exe` (SHA-256 `C46F71CF1FA968FBC7FC595AB0EB16D788A19B9AC0359FB50C5AC91C423B230F`); the replaced package is recoverable at `to_delete/dist__manual_replaced_release_20260811_233744/`.
- [ ] Manual foreground verification: in dark mode, reopen Leviathan's Statement of Account and confirm each clickable matter label is readily legible, clearly identifiable as a link, and remains readable on alternating rows; confirm light mode remains unchanged.

## CIPO Rogue Vendor A/R Repair (2026-08-11)

- [x] Trace the Statement of Account CIPO choice to five imported CIPO expense rows that were incorrectly represented in Receivables and Invoice Log as open client invoices.
- [x] Add an idempotent, guarded repair that selects a candidate only when its vendor-named receivable reference is also backed by a same-vendor **Expense** transaction; preserve the expense, disbursement, and ordinary vendor-ledger history.
- [x] Create protected snapshot `Backup_20260811_225403_A11A358A` and atomically remove the five CIPO Receivables rows, five CIPO Invoice Log rows, and one stale rogue-vendor cleanup ledger row from the live LocalAppData workbook.
- [x] Verify afterward that CIPO has zero receivables/Invoice Log artifacts and is no longer selectable for Statement of Account; all five CIPO expense transactions and Tremendis Group's `25-0062` disbursement remain.
- [ ] Manual foreground verification: reopen Statement of Account and confirm CIPO is absent from **Billing Client** while genuine open billing clients and invoices remain available.

## Professional Module Rail Tooltip Dismissal (2026-08-11)

- [x] Suppress a rail icon's hover tooltip immediately on left-button press and while that module's flyout is active, so the popup cannot cover the flyout menu.
- [x] Add focused regression coverage for the press suppression, pointer-exit reset, and active-flyout guard.
- [x] Rebuild and copy-promote the complete runnable package at `dist/cspm.exe` (SHA-256 `DB5DA08E0C54C00E5C4E7A585CDC843F68CB8C78EF4296DBB1318500BFA11142`); the immediately replaced package is recoverably retained under `to_delete/dist__manual_replaced_release_20260811_222200/`.
- [ ] Manual foreground verification: hover **Billing & Invoicing** until its label appears, then click it. Confirm the label disappears immediately and never covers the menu; repeat with another module flyout.

## Payment Entry Routed Defaults and Deposit Account (2026-08-11)

- [x] When Invoice Directory opens a new Payment Entry tab for an invoice, wait for that invoice's live receivable row and prefill the editable payment amount with its full remaining balance exactly once.
- [x] Add a workbook-backed **Deposit account** selector to Payment Entry; retain the payment method separately and post the selected account as the transaction's receiving account.
- [x] Preserve the selected deposit account when amending an existing payment.
- [x] Rebuild and promote the complete runnable package at `dist/cspm.exe` (SHA-256 `B7F0E0961EA4B493961F95E5A07198F4D1244FD4BC9A9AD4CD415784C078D0E1`); the immediately replaced package is recoverably retained under `to_delete/dist__manual_replaced_release_20260811_220900/`.
- [ ] Manual foreground verification: from Invoice Directory, select an unpaid invoice and choose its **Unpaid** payment shortcut. Confirm Payment Entry pre-fills the exact balance due, allows editing it for a partial payment, and lists/selects the intended receiving account before posting.

## Payment Entry Selection Stability and Form Fit (2026-08-11)

- [x] Preserve the selected invoice as a scalar invoice key across payment-list refreshes, rather than relying on a replaceable table-row object.
- [x] Prevent automatic payment-list refreshes from clearing the active invoice, history, or in-progress partial-payment amount.
- [x] Include the complete Payment Entry state in the parent work-tab checkpoint/restore contract, including selection, payment amount, adjustment amount, and adjustment reason.
- [x] Compact the right-side form slightly so its evidence/status wording remains visible in the normal Professional window without making the fields cramped.
- [x] Commit a payment or payment amendment as one atomic macro-workbook replacement, rather than separately rewriting Transactions, Ledger, Receivables, Time, and Disbursements.
- [x] Use an isolated, unique temporary workbook and bounded retry schedule for a transient Windows file lock; a final lock error now confirms that the attempted change was not saved.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `38CBA00E2D1F7E48517BA0D16D20BF2FB8837B41A730A29C82F8B82A048DE087`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_204651/`. The promoted executable has no `Zone.Identifier` downloaded-file marker.
- [ ] Manually choose an invoice, enter a partial payment, wait through any background refresh, and confirm the selection and entered values remain intact. Confirm the lower status/evidence wording is visible without vertical scrolling at the normal window size. Post a test payment with Excel closed and confirm the worker completes promptly; if an external lock is deliberately held, confirm the retry ends with the clear no-save error and no duplicate payment.

## Invoice Finalization Throughput and UI Responsiveness (2026-08-11)

- [x] Eliminate the serial full-workbook save chain during invoice finalization: calculate the final totals in memory and commit Time, Disbursements, Receivables, Invoice Log, Ledger, and Drafts as one atomic macro-workbook replacement.
- [x] Apply the same one-commit rule when reclaiming a voided invoice number for a correction/reissue, so the internal supersession records cannot cause another multi-save pause.
- [x] Keep Chromium's required PDF render on its GUI thread, but move page-number/header post-processing to the worker pool and give every export its own temporary PDF path.
- [x] Keep CSPM in the foreground during finalization; the success view has its own **Open Final PDF** action, so finalization no longer auto-launches an external reader mid-handoff.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `32A907A81614326AF36F256CF95458D75F5D4362293C9A5C7881A5E2BAAB4B3D`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_202431/`. The promoted executable has no `Zone.Identifier` downloaded-file marker.
- [ ] Manually finalize one ordinary invoice and one correction/reissue invoice from the real package. Confirm the active stage remains visible, Windows never reports CSPM as not responding, the success/check view appears promptly, and **Return to WIP** works after each.

## Matter Financial Safeguards and Visibility (2026-08-11)

- [x] Prevent an existing matter from being moved to **On Hold**, **Closed**, or **Archived** while it has unbilled WIP or unpaid invoices; enforce the rule in the Excel repository, not only in the screen.
- [x] Make permanent deletion a true last resort: block it server-side whenever the matter has linked records, with a specific financial explanation where WIP or unpaid invoices are present.
- [x] Correct the Matter delete-confirmation buttons so both retain usable fixed dimensions, and keep the dialog open with an inline reason when deletion is refused.
- [x] Add a live **WIP & unpaid invoices** panel to both Matter Profile 360 and the editable Matter screen, including a matter-filtered **Open WIP Ledger** tab and direct invoice links that open each invoice in a new Invoice Directory tab.
- [x] Add regression coverage proving that the financial summary follows the work matter rather than the billing client, and that deletion is blocked by active WIP/A/R.
- [x] Treat legacy Dockets matter rows as fallback-only in Statements of Account: when a current time/disbursement row already resolves an invoice's matter, do not append a stale reversed/pre-reissue legacy association.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `CC1BC203D975F0E3A0B0688BFA5E0D44C4CB473B75E319514FF988DC9FA0B149`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_155245/`.
- [ ] Manual foreground verification: open a matter with WIP and unpaid invoices; confirm the card amounts/list, the WIP and invoice links, rejection of On Hold/Closed/Archived, and the corrected delete-dialog button sizing. Then resolve all work and confirm the status/deletion rules permit the appropriate next step.

## Matter Rename Save Verification (2026-08-11)

- [x] Prevent a dirty **Edit Matter** form from returning to Matter Profile 360 through **Cancel** without an explicit discard decision.
- [x] Rename the edit action to **Save Matter & Return** and, before returning, re-read the saved matter by ID and verify its Matter Name and Display Name exactly match the submitted values.
- [x] Keep the editor open with a clear error if the post-save verification cannot establish the saved name pair.
- [x] Add regression coverage for the protected cancel and verified save/return contract.
- [ ] Manual foreground verification: edit a test matter's Matter Name and Display Name, select **Save Matter & Return**, and confirm the profile heading, selector, and field values show the new names. Then make another edit, select **Cancel**, and confirm the discard confirmation offers **Keep Editing** and **Discard Changes**.

## Tab Transition Performance Audit (2026-08-11)

- [x] Measure the live Leviathan Statement path and identify the material cold-read costs: schema validation, CSPM workbook parsing, and an unnecessary legacy-Dockets fallback.
- [x] Read Statement-related workbook tables in one opening, cache a verified schema for the unchanged workbook, and skip the legacy Dockets workbook when current records already resolve every requested invoice's matter.
- [x] Move Statement client-list, open-invoice, and preview requests to existing QThreadPool workers; load the Statement component only when its D17 route is active; and remove redundant Option 3 state reapplications during routed workspace opens.
- [x] Add runtime timing for all Option 3 workspace opens and Statement background requests, so the next manual run produces concrete route evidence in `logs/cspm.log`.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the performance repair (SHA-256 `9F90122E5B0E1EBDF420B22FF7F900B8804C2CFB2B56A80A636A8BDB6CC70391`); the preceding release is recoverable at `to_delete/dist__replaced_release_20260811_151733/`.
- [ ] Manual foreground verification: open **Finance & Ledger → Statement of Account** from a cold launch. The tab shell must appear immediately with a loading state, remain responsive while choices/invoices load, and still generate the same 21 Leviathan open invoices. Then open several other modules and inspect new `[PERF] MainContent workspace-open-*` entries in `logs/cspm.log` before choosing the next screen-specific optimization.
- [ ] Complete the application-wide transition audit one route at a time using those timings; prioritize the remaining large eager QML views and synchronous workbook calls. Do not migrate the production datastore until those UI and query baselines are recorded.

## Invoice Builder Preview Responsiveness (2026-08-11)

- [x] Profile the live draft-preview path and identify the actual cold-read cost: synchronous draft selection and repeated macro-workbook parsing, rather than HTML rendering.
- [x] Add a signature-validated streaming read path for cached workbook table layouts; warm the seven tables required by Invoice Builder from one immutable snapshot.
- [x] Move Invoice Builder draft selection to one background workspace request that returns the draft, its line items, and rendered preview together.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the preview responsiveness repair (SHA-256 `35030BD17EB952C7AE95089BE83B4A397483596AAEB1AD1BB6D60E13B4A93D34`); the preceding release is recoverable at `to_delete/dist__replaced_release_20260811_195859/`.
- [ ] Manual foreground verification: from a cold launch, open WIP-to-Bill then Invoice Builder, select a draft, and confirm the shell remains interactive while a preview is prepared; reselect the same draft and confirm it paints essentially immediately.

## Statement-to-Record Navigation (2026-08-11)

- [x] Make each Statement of Account invoice number a direct link that opens the selected invoice in its own Invoice Directory workspace, without replacing the statement tab.
- [x] Preserve each resolved Matter_ID in the statement data contract and make the individual matter name within `Client & Matter` a direct Matter Profile 360 link; unresolved historic text remains non-clickable rather than guessing a record.
- [x] Add regression coverage for the Matter_ID-bearing statement row contract and verify all 21 current Leviathan open invoices expose a resolvable matter link in a read-only live-workbook check.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `9A3181C405787F614DC3BDF45D53C8E36F73E854F95BD57EB197C7110F191484`); the preceding package is recoverable at `to_delete/CSPM__replaced_release_20260811_144319/`.
- [ ] Manual foreground verification: from Statement of Account, select an invoice number and a matter name. Confirm the original statement remains open, the invoice opens in a distinct Invoice Directory tab, and the matter opens its correct Matter Profile 360 record where **Edit Matter** allows a rename.

## Daily Operations A/R Metric Clarity (2026-08-11)

- [x] Replace the ambiguous Daily Operations headline `Overdue A/R` with the authoritative total open A/R from the same Receivables-based authority as A/R Aging & Detail.
- [x] Retain overdue exposure as the secondary line, including its dollar amount and invoice count, using the user's configured overdue grace period.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `487E3F85C38FF22EA78EA7FEFFDEEA2AB8AED6812FB4AA78AC0B6597F9659D17`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_125058/`.
- [ ] Manual foreground verification: confirm Daily Operations now reads `Total A/R` with an `Overdue: $… · … invoices` secondary line, and that selecting it still opens A/R Aging & Detail.

## WIP-to-Bill Performance and Responsiveness (2026-08-11)

- [x] Eliminate the automatic 300 ms WIP-load delay and the repeated full reload triggered by workspace state restoration.
- [x] Cache the WIP projection in memory for the current workbook signature; serve a tab re-entry from that cache and prevent concurrent duplicate loads.
- [x] Read the five WIP lookup/data tables from one macro-workbook opening rather than opening and parsing it once per table.
- [x] Keep the prior verified WIP list visible if a manual refresh fails, and show an inline `Loading` / `Ready` / cached status beside the explicit Refresh control.
- [x] Add focused regression coverage for the one-snapshot read and signature-checked cache path.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after this WIP responsiveness repair (SHA-256 `8EC1CF44EF6542351FAA0A182A5FE784E8B7CB42DE17573991C96135067F8AB8`); the prior release is recoverable at `to_delete/dist__replaced_release_20260811_121600/` and the validated build candidate remains at `to_delete/dist_staging_32820__unpromoted_build_20260811_121443/`.
- [ ] Manual foreground verification: open WIP-to-Bill Workbench twice without changing data (the second opening should be effectively immediate and say `cached`); click Refresh once and confirm the screen remains responsive while it updates.

## Invoice 26-0057 Reversal and Single-Docket Correction (2026-08-10)

- [x] Repair the Invoice Reversal service/UI signature mismatch that caused reversals to fail before changing workbook data.
- [x] Make a reversal return only its linked WIP to the canonical unbilled state, void its receivable, and retain one auditable `-V` contra record in Invoice Log, Ledger, and Transactions.
- [x] Exclude void/reversal invoice lines from Client Ledger while retaining the returned WIP docket.
- [x] With CSPM and Excel closed, create a verified candidate then promote the repair for only `T_e6d43292a1` (2026-05-05) from 965 Canada to AL ADVISOR / Tax Planning. The recoverable pre-repair backup is at `C:\Users\CorySchneider\AppData\Local\CSPM\backups\CSPM\al_advisor_may5_20260810_182534\CSPM.before-al-advisor-may5-repair.xlsm`.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the correction (SHA-256 `91291C6D0125C710E82E3DFED1B8EDBA00B9BD1CA923AF5C82F66FC93C0CF916`); the previous package is recoverable at `to_delete/CSPM__replaced_release_20260810_183823/`.
- [ ] Manual foreground verification: in AL ADVISOR's Client Ledger, confirm the May 5 time entry is WIP and there are no active invoice lines for 26-0057; confirm no other 965 Canada docket moved.
- [ ] Decide and perform the separate authoritative `Dockets.xlsm` correction before the next historic financial sync, otherwise that sync will restore the old historic 26-0057 state.

## Correct and Reissue Invoice Workflow (2026-08-10)

- [x] Add a supported **Correct & Reissue** path for an unpaid, uncredited invoice: return only its linked WIP, preserve the original/reversal as internal audit evidence, and carry the original invoice number as a suggested replacement.
- [x] Let the returned WIP be reassigned before it is redrafted; keep the original number as an editable suggestion at finalization rather than a hard lock. Removing a docket from a correction draft releases the suggestion so it can be billed independently.
- [x] Keep internal `-SUPERSEDED` and `-V` audit entries out of Client Ledger and recipient-facing statements.
- [x] Add regression coverage for reversing, suggesting, reassigning/redrafting, choosing a different valid final number, and releasing removed WIP for separate billing.
- [x] Let Finalize Invoice reclaim a previously voided, unpaid/uncredited number in-app: show clear guidance, archive the former record only at confirmed finalization, and then issue the corrected replacement under the original number.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` (SHA-256 `B29F723E80AD0EAF0B39FB681003C80090E00E09FB194F2C8E522D9CD0F0FDC4`); retain the prior package at `to_delete/dist__replaced_release_20260811_101916/`.
- [x] Redesign the Correct / Reverse modal so its instructions scroll inside a responsive card while **Cancel**, **Correct & Reissue**, and **Reverse Only** remain visible at the bottom of the window.
- [x] Make PDF handling genuinely optional: **Keep PDF** is the default, and Move/Delete require the user to select a real source PDF. Validate that selection before changing financial records; never overwrite an existing archived PDF.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` with the modal repair (SHA-256 `A6853F5CA92EC5A61511BA101141AAAAA8F8012303E22B3C8B7C9BAE342B5B00`); the prior package is recoverable at `to_delete/dist__replaced_release_20260811_181606/`.
- [x] Move Invoice Directory list/detail reads and Correct & Reissue / Reverse workbook work to background workers so the QML event loop can paint and remain interactive throughout the operation.
- [x] Make a statement-routed Invoice Directory selection refresh its detail card automatically once the invoice list arrives; show explicit loading state rather than temporary zero-dollar results.
- [x] Replace the unreliable modal radio controls with direct, mutually exclusive PDF-action rows and a visible non-blocking working state.
- [x] Move final-invoice number lookup, final HTML preparation, and post-finalization draft refreshes off the QML thread; present the active finalization phase while each background step completes.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the Invoice Directory and finalization responsiveness repairs (SHA-256 `5FF8C7112C90638F8C379A8AC453E4F38BD3DFF0F77C9DDA64DD6295AFF2C8B0`); the prior complete release is recoverable at `to_delete/dist__replaced_release_20260811_190908/`.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after making correction numbers suggestions rather than locks and releasing the split Concierge Club 26-0092 docket (SHA-256 `A3C66B3AFFD0BA0D7FF1BA4E55E1E4F30F3A44C31B06E0EEC7566A475269211C`); the preceding package is recoverable at `to_delete/dist__replaced_release_20260811_192907/`.
- [ ] Manually verify a full correction-and-reissue cycle in the real application.
- [ ] Manual foreground verification: open an invoice link from Statement of Account and confirm the directory card populates without deselecting/reselecting. In Correct & Reissue, choose each PDF option once and confirm only that option is visibly selected. Choose **Delete selected PDF permanently** with a selected test PDF, select **Correct & Reissue**, and confirm the modal reports progress while the app remains responsive.
- [ ] Manually verify a corrected draft prefills its former invoice number as a suggestion, accepts another unused number, and keeps a removed docket as ordinary WIP for a separate invoice.

## Statement of Account Internal Adjustments (2026-08-10)

- [x] Keep historic background CreditsAdj rounding/write-off entries out of the recipient-facing Paid / Credits column.
- [x] Render the client-facing invoice total net of the internal adjustment, while preserving the original receivable, payment, and adjustment audit values in the workbook.
- [x] Add a regression test for invoice 26-0055-style one-cent background adjustments.
- [x] Rebuild and promote dist/CSPM/CSPM.exe (SHA-256 3050A8578A9BC65953072F8DBD7CA0715670DB839CF089BFA5B31B1D74AD7374); retain the replaced package at to_delete/CSPM__replaced_release_20260810_174719/.
- [ ] Manually confirm invoice 26-0055 displays $2,361.70 / no payment credit / $2,361.70 and the Leviathan statement total is $53,474.49.

## LIHDC Settlement Set-off Reconstruction (2026-08-10)

- [x] Diagnose the six 2026-07-29 LIHDC settlement allocations incorrectly imported as CIBC Chequing → AMEX / Costco transfers.
- [x] With user confirmation and CSPM closed, create recoverable local-workbook backups and reconstruct the governed A/R–A/P set-off payment, ledger evidence, A/P bill state, clearing-account transaction references, and voided duplicate settlement expense.
- [x] Route Invoice Directory settlement links to a record-specific Accounts Payable set-off tab instead of Transactions Master.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` with the governed set-off detail workspace (SHA-256 `115D03EBA9800DF4B7E5B9F2C3DD4F0542909FC135C2509E610CF1680899238C`); retain the replaced package at `to_delete/CSPM__replaced_release_20260810_130505/`.
- [ ] Manual foreground verification: open invoice `26-0069`, select the $2,649.44 settlement set-off, and confirm a new tab shows the LIHDC set-off, its six allocations, no bank account, and the reversal/replacement action.

## Invoice Directory Card Density and Payment-Tab Handoff (2026-08-10)

- [x] Increase the Invoice Directory summary cards symmetrically, make the invoice-status pill more noticeable, and tighten the Payment & Ledger card's internal hierarchy. User visually confirmed the revised presentation is better.
- [/] Make payment IDs, amount/date links, and the Payment Entry action open record-specific payment work tabs without replacing the Invoice Directory tab.
- [/] Add each linked matter's plain-English description as a compact, hover-expandable third line in the Invoice Directory sidebar.
- [x] Rebuild and promote the complete runnable package at `dist/CSPM/CSPM.exe` after the Invoice Directory changes.
- [ ] Manually confirm the matter-description line is readable and that payment ID, amount/date, and Payment Entry each route to the intended payment tab while the Invoice Directory remains open.

## Native Splash Loader Refinement (2026-08-10)

- [/] Replace the native splash's narrow, exponential pseudo-progress line with a visible zero-percent hold, elapsed-time progress, and a wider plasma-style loader.
- [x] Anchor splash progress to the first post-startup paint rather than process startup, extend the zero hold, and slow the normal advance so the initial visible frame cannot be near full.
- [ ] Manually launch CSPM and confirm the splash opens at a visible 0%, advances smoothly, reaches 100% during the main-window handoff, and reads clearly against the logo in the real app.

## Data Folder Automatic Restart (2026-08-10)

- [x] Replace the broken immediate relaunch after Data Folder Setup with a delayed restart that waits for the active CSPM process and its single-instance lock to exit first.
- [x] Rebuild and promote the complete runnable package at `dist/CSPM/CSPM.exe` after the splash and auto-restart repairs.
- [ ] Manually complete the final Data Folder Setup step and confirm CSPM closes and automatically reopens using the selected Shared Data Source and Local Working folders.
## 10/10 Quality Execution Roadmap (2026-08-10)

- [ ] Follow the ordered financial-correctness, runtime-stability, manual-audit,
  operational-resilience, and certification gates in
  `docs/CSPM_10_10_EXECUTION_ROADMAP.md`.
- [ ] Do not declare a 10/10 release until its certification checklist has
  evidence for financial reconciliation, clean core-workflow logs, manual audit,
  shared-data recovery, and candidate-package verification.

## Selectable Billing-Client Statements (2026-08-10)

- [x] Add an explicit Billing Client selector that lists bill-to parties with open receivables.
- [x] Load unpaid and partially paid invoices by billing client and statement date, selecting every open invoice by default.
- [x] Let the user manually include/exclude invoices, select all/clear, and see the selected balance update before generation; the selection never changes A/R data.
- [x] Replace the generic statement PDF path with a dedicated branded Statement of Account layout, including bill-to details, selected invoices, amount-due callout, and payment-contact note.
- [x] Add focused regression coverage and promote the runnable package at `dist/cspm.exe` (SHA-256 `8B3F64D8C9072B5B94845DDAC21777D1A0B768E32788FD0B7C59CAB2452DD381`); the replaced package is recoverably retained under `to_delete/`.
- [x] Remove inherited generic placeholder controls from the live `D17` statement route, require an explicit billing-client selection, default the statement date to today, and use the Professional semantic input/button controls.
- [x] Rebuild and promote the revised package at `dist/CSPM/CSPM.exe` (SHA-256 `18BD4913E9E69F185E8AC732CD9930841E8E87F0FE3A37FE41EA41EEAA765CFD`); the prior package is retained at `to_delete/CSPM__replaced_release_20260810_135556/`.
- [x] Resolve every statement line to the actual client and plain-English matter receiving the work, including historical companion-docket evidence. Never substitute the billing client as the work recipient.
- [x] Replace the ambiguous preview `Value` heading with `Details`, and make the primary action open the completed statement preview directly; the preview itself owns Save, CSV, and Print.
- [x] Rebuild and promote the corrected full package at `dist/CSPM/CSPM.exe` (SHA-256 `35A16BAA2A48139EEDC38FAF34054B2EDAAE9C884BFB05CBDED3C0D0291F9085`); the replaced package is recoverable at `to_delete/CSPM__replaced_release_20260810_154508/`.
- [x] Make report CSV export visibly acknowledge its start and outcome, including the exact `CSV Exported. Saved here:` message followed by the destination folder as an inline Explorer link, and a prominent failure notice.
- [x] Rebuild and promote the CSV-feedback package at `dist/CSPM/CSPM.exe` (SHA-256 `5BE3DBA92D634966699417601468954BC1C5ACAF42B90BEF692A079C3A9431FA`); the replaced package is recoverable at `to_delete/CSPM__replaced_release_20260810_162444/`.
- [ ] Manual foreground verification: open **Reports → Statement of Account**, choose a billing client, confirm each `Client & Matter` is the work recipient rather than the billing client, deselect at least one unpaid invoice, select **Preview Statement**, and confirm the preview's Save/CSV/Print actions contain only the selected invoices and matching amount due.

## Governed Historic Financial Synchronization (2026-08-06)

- [x] Build a source-controlled synchronization service that treats `C:\Users\cschn\OneDrive - LPN\__Invoices (1)\Dockets.xlsm` as the historic financial authority while preserving CSPM-native records after the source snapshot cutoff.
- [x] Normalize legacy receivable footer/duplicate/credit-sign artefacts with ledger and Invoice Log cross-checks; never import vendor expense references as A/R.
- [x] Build an isolated candidate and audit report before any promotion; require source-owned A/R, ledger, and productivity totals to reconcile within $0.02 / 0.01 hours.
- [x] Gate the actual CSPM Financial Dashboard and Productivity Dashboard calculations against independent candidate values, including exclusion of A/R set-offs from cash banked totals.
- [x] Add an explicit promotion command that checks the original target hash and creates a recoverable pre-sync backup; it refuses to proceed while CSPM holds the workbook open.
- [ ] With CSPM closed and after reviewing the candidate audit, promote the approved candidate and manually inspect the dashboard, the paid LIHDC settlement, and the partial $376.13 balance on invoice `26-0069`.

## Matter Merging & Data Integrity (2026-08-09)
- [x] Identify duplicate matters (e.g. LITE - tax planning) and merge them into an authoritative record by reparenting time entries.
- [x] Identify orphaned matters in time entries (e.g. BORK - Custom Fee) and recreate them in the Matters table.
- [x] Eliminate "ghost" matters by resolving all duplicates and orphans.
- [x] Backend: Expose `mergeMatters` function via `AppController` that links to `ClientRepo` and `ExcelRepo`.
- [x] Backend: Update `_merge_duplicate_matters` to reassign disbursements alongside time and transactions.
- [x] QML: Add **Merge Matter** dialog to the matter profile view (`MatterProfilePanel.qml`).
- [ ] Manual foreground verification: Launch the application and test the UI merge of "CRA Audit" into "Legacy Matter EASY-LEVI-TAX-26-0021" for the Easy 4.0 client.
## Portable Current Data and Explicit Data Locations (2026-08-06)

- [x] Replace the repository's older `data/CSPM.xlsm` with the verified current LocalAppData workbook, including the repaired invoice `26-0080`; `Dockets.xlsm` was verified identical.
- [x] Rename the Settings controls to **Shared Data Source Folder** and **Local Save Folder** so their roles are clear on every computer.
- [x] Require a selected shared source to contain valid `CSPM.xlsm` and `Dockets.xlsm` files, and defer either location change until a clean restart so the active session cannot push into an unpulled/new location.
- [x] Rebuild and promote the revised `dist/CSPM/CSPM.exe`; the active package remains outside quarantine.
- [ ] On the second computer, manually choose the desired shared source package and local save package from Settings, restart, and confirm the current invoices, clients, and dockets appear.

## Repository Build-Artifact Quarantine (2026-08-06)
- [x] Move seven confirmed stale PyInstaller distribution/build artifacts into `to_delete/` for review rather than permanent deletion.
- [x] Update the release builder to quarantine a replaced package and any unpromoted default staging output instead of deleting it or leaving it at the repository root.
- [x] User approved permanent deletion of the reviewed `to_delete/` quarantine; remove its contents while leaving the active package, live workbooks, and source tree untouched.

## Direct-Fee Invoice Finalization Integrity Repair (2026-08-06)
- [x] Diagnose invoice `26-0080` as a direct-fee finalization defect: a valid `$5,000.00` gross fee / `$5,650.00` total had zero net/HST fields, which propagated into Invoice Log, Receivables, and Ledger.
- [x] Harden draft creation, recalculation, and finalization so direct-fee rows recover net/HST from their positive gross amount and finalization recalculates totals before posting accounting records.
- [x] Add a targeted accounting repair service for historical finalized invoices and validate both the prevention and repair paths against a disposable in-memory workbook.
- [x] With CSPM closed, create a reversible active-workbook backup and repair invoice `26-0080`; confirm the live Invoice Log, Receivables, Revenue ledger, and linked fee entry now show Fees `$5,000.00`, HST `$650.00`, and Balance `$5,650.00`.
- [x] Rebuild and promote the revised `dist/CSPM/CSPM.exe`; the previous release is retained in `to_delete/dist__manual_replaced_release_20260806_103020/`.
- [ ] Manually confirm Invoice Directory/Reverse Invoice show the repaired totals, the high-DPI compact layout, and the separate Directory-to-Reversal flow.
- [ ] Manually delete a draft and confirm the only notification is `Draft <number> deleted` (no preview error).
- [ ] Manually launch `dist/CSPM/CSPM.exe` and confirm that only the native PNG splash appears, the main shell's first visible frame appears beneath it, the PNG begins fading out in that same handoff, and CSPM is foregrounded on its target monitor after the PNG closes.

## Native PNG-Only Splash and Matter Selector Repair (2026-08-06)

- [x] Disable every QML splash creation path; retain only a native PNG centered on the target monitor. The main QML load waits for its visible eased fade-in to finish; at the main window's first painted pixel, the main frame is visible beneath it and the PNG starts its eased fade-out in the same handoff. Restore main-window foreground only after the PNG closes.
- [x] Replace the raw bulk-docket matter dropdowns with searchable, light/dark themed controls that display `Client | Matter Description | Matter Number`.
- [x] Rebuild and promote the repaired `dist/CSPM/CSPM.exe`; preserve the immediately replaced package at `to_delete/dist__replaced_release_20260806_105321/`.
- [ ] Manually verify the PNG-only startup, post-splash foreground focus, selector filtering, and selector appearance in both themes.

## Professional No-Open-Tabs Default (2026-08-06)

- [x] Replace the automatic Professional `Practice Briefing` startup tab with the native Professional no-open-tabs background and its existing quick tiles; preserve explicitly routed starts and already-open workspaces.
- [x] Keep the console-style `HomeGrid` exclusive to its existing non-Professional shell rather than overlaying the Professional home.
- [x] Replace the static no-tabs tiles with a responsive, no-scroll Daily Operations home: daily deadline/time/WIP/A/R KPIs, the four primary daily pathways, a capped priority queue, recent work, and WTD/YTD productivity. It reuses the existing Practice Briefing payload and does not open a workspace tab.
- [x] Rebuild the release and place the complete runnable package at the requested `dist/cspm.exe` path; the immediately prior package is recoverably retained at `to_delete/dist__replaced_release_20260806_124516/`.
- [x] Correct the last-tab close path: choosing **Discard** for unsaved Time Docket Entry changes now removes that tab and transitions to the native no-tabs Daily Operations home instead of recreating the same docket tab.
- [ ] Manually launch CSPM normally and confirm the Professional no-open-tabs background/tiles are the first main-app surface with no Practice Briefing tab opened.

## Tray-Only Relaunch Wake-Up (2026-08-06)

- [x] Have the primary instance listen on `CSPM_IPC_SERVER` and route a duplicate executable launch through the exact same `TrayController.open_cspm()` path as the tray's `Open CSPM` action.
- [x] Do not construct a native splash for `--tray-only`; a duplicate executable detects the existing instance before QApplication/splash startup and only wakes that instance.
- [x] Rebuild and promote the updated `dist/CSPM/CSPM.exe`; Windows denied the builder's directory rename, so the verified candidate was copied into the empty `dist/` after the prior package was moved intact to `to_delete/dist__manual_replaced_release_20260806_111120/`. The built candidate remains intact in `to_delete/` as a recovery copy.
- [x] Rebuild and promote the splash/home revision; the verified `2026-08-06 11:21` candidate was copy-promoted after Windows again denied the builder's final directory rename. The replaced release is retained at `to_delete/dist__manual_replaced_release_20260806_112200/` and the candidate remains intact in `to_delete/dist_staging_20652__unpromoted_build_20260806_112140/`.
- [x] Rebuild and promote the Professional-home correction; the verified `2026-08-06 11:27` candidate was copy-promoted after the same Windows rename denial. The replaced release is retained at `to_delete/dist__manual_replaced_release_20260806_112840/` and the candidate remains intact in `to_delete/dist_staging_18240__unpromoted_build_20260806_112751/`.
- [ ] Manually start `dist/CSPM/CSPM.exe --tray-only`, relaunch `dist/CSPM/CSPM.exe`, and confirm the existing app opens without any splash.

## Backend Canonical Account-Balance Engine
- `[/]` Implement canonical account-balance engine in `excel_repo.py`
  - `[ ]` Create `_canonical_ar_ledger(filters)` method
  - `[ ]` Support parsing parameters (client, billing client, matter, date ranges, open-items only toggle)
  - `[ ]` Correctly merge chronological AR transactions (Invoices, Payments, Credits, Write-offs)
  - `[ ]` Apply progressive balance calculations (Opening Balance + Charges - Credits = Running Balance)
- `[ ]` Refactor `get_client_ledger_report` to consume the engine for accurate UI balances.
- `[ ]` Refactor `statement_of_account_report` to consume the engine for robust external payloads.

## QML UI for Statement of Account
- `[ ]` Build `StatementOfAccountView.qml`
- `[ ]` Wire progressive disclosure options (Scope picker, Date range picker, Open items toggle)
- `[ ]` Implement robust layout matching the Professional theme (Semantic colors, standardized tables)

## Contextual Integration
- `[ ]` Wire context pathways to trigger Statement generation from:
  - `[ ]` `ClientProfilePanel`
  - `[ ]` `MatterProfilePanel`
  - `[ ]` `PracticeBriefingView` (optional/advanced)

## Testing and Verification
- `[ ]` Add UI automated tests (`test_statement_of_account_ui.py`) to verify progressive disclosure and display.
- `[ ]` Create backend unit tests (`test_canonical_ar_ledger.py`) to verify calculations for partial/multi-invoice payments.


### Phase 9 Status Update (2026-07-30)
- **Settings-Precedence Regression**: RESOLVED (authoritative path C:\Users\cschn\AppData\Local\CSPM\user_settings.json).
- **Professional-Interface Launch**: VISUALLY CONFIRMED BY CORY (approx. 18s).
- **Full Automated Suite**: PASS (393 passed, 12 skipped, 0 failed).
- **Production Build**: DEFERRED BY CORY (CSPM is in active development, not yet distributed).
- **Phase 9 A+ Status**: NOT YET CLAIMED (Cory has additional bugs to address).
- **Phase 10 Ask CSPM**: PAUSED.
- **SQL and SQLite**: PAUSED.
- **System-Tray Timekeeping**: Deferred until application is stabilized.
- **Gate B**: Evidence preserved, but production/installer readiness is deferred.


### Phase 9 Icon Repair Update (2026-07-30)
- **Stale CSPM.exe Discovered**: The previous CSPM.exe (approx. 16:28 PM) predated the settings repair and was stale.
- **Previous Executable Timestamp**: Thu Jul 30 16:28:50 2026 (SHA-256: 16edeb1b4dd75d2046b8ddc51be55ce759fe30b72c76ac5859cc69745a6c0e64)
- **Fresh Candidate Timestamp**: Thu Jul 30 18:06:48 2026 (SHA-256: 85B87AABC454A2470EBD483C51DE6FEA614763F029512C2125C6D2A6E36C9C80)
- **Icon Root Cause**: The PyInstaller build configuration (scripts/build_release.py) was completely missing the --icon argument for the main application, causing Windows to fall back to generic icons or cached stale icons.
- **Repairs**: Added --icon=src/assets/app_icon.ico to the cmd_main build command.
- **Test Results**: Focused icon identity test passed. Full suite passed (398 passed, 12 skipped, 0 failed).
- **Candidate Build Result**: A fresh, disposable candidate build was successfully generated. Packaged templates do not match live workbooks.
- **Visual Status**: Cory visual status is PENDING (needs to inspect the uniquely named executable).
- **Production Status**: Production readiness and Phase 9 A+ are NOT CLAIMED.

### Phase 9 Active Data Routing Repair (2026-07-31)
- **Startup Logic Contract**: Refactored `AppController.__init__` to load `localDataDir` synchronously and apply `override_data_dir` BEFORE repository and facade instantiation.
- **Empty-Data Safety Barrier**: Implemented strict Phase 4 checks. CSPM.exe will no longer silently seed a blank LocalAppData practice if the configured `localDataDir` is unavailable, or if a valid known project data folder exists (detects frozen/packaged context).
- **Settings Integrity**: Verified that `localDataDir` overrides are not overwritten by the deferred settings load.
- **Verification**: Wrote `test_data_routing_guards.py`. All deterministic path-resolution assertions pass.

## Client Directory Backend-Boot Repair (2026-08-05)

- [x] Prevent the deferred settings worker from starving or being dropped before the critical workbook backend boot runs.
- [x] Rebuild the packaged `dist/CSPM/CSPM.exe` after the repair; only governed blank templates are bundled, and the active LocalAppData workbook remains untouched.
- [x] Historical check: `leviathan` returned 26 rows; this exposed the now-corrected broad metadata/parent-client search defect.

## Directory Metrics & Profile Navigation Repair (2026-08-05)

- [x] Expose the live dashboard summary as a QML slot and push the live payload into the module header after backend boot.
- [x] Restrict Client Directory search to client identity and contact fields, excluding shared parent-client metadata and operational notes.
- [x] Route a Client Directory double-click directly into the populated Edit Client Profile form, with Return/Cancel leading back to the selected Client Profile 360.
- [ ] Manual foreground verification: launch `dist/CSPM/CSPM.exe`; confirm `Leviathan Private Network` returns exactly one row, the badge reads `Active Matters: 192 (Clients: 113)`, and double-clicking that row opens its populated `Edit Client Profile` form.

## Invoice Builder Restoration (2026-08-05)

- [x] Restore the Invoice Builder master-detail layout: line items at left, HTML preview at upper right, and fixed settings/actions controls at lower right.
- [x] Theme every Invoice Builder dropdown with an explicit popup and delegate that reads the application light/dark state.
- [x] Add persisted custom-fee reconciliation choices and payload rules for visible discount-line versus hidden adjustment behavior.
- [x] Correct Discount Line invoice rendering so Legal Services Rendered shows the full docketed service amount before the Courtesy Discount reduces it to the agreed flat fee.
- [x] Tie the transparent native splash fade-out to successful root-QML construction rather than a blind startup timeout.
- [ ] Manual foreground verification: launch with .\launch.ps1, confirm the Invoice Builder in both themes, exercise every dropdown popup, and verify the splash handoff with WebEngine enabled.

## Direct Fee Docket Entry & Professional Splash (2026-08-05)

- [x] Add `Fee Docket Entry` directly below `Time Docket Entry` in the Docketing & Deadlines flyout and route it to its own B02 workspace tab.
- [x] Add a matter-linked direct-fee form that saves a positive zero-hour/zero-rate WIP entry, preserving the normal WIP, draft, and invoice pipeline.
- [x] Keep fee entries separate from the time-docket daily aggregation, and verify in a temporary workbook that a fee-only matter produces a flat-fee invoice payload.
- [x] Remove the Professional splash one-shot path that hid the logo and completed immediately; keep a native logo fallback visible while the animated renderer warms up.
- [ ] Manual foreground verification: launch `dist/CSPM/CSPM.exe`, confirm `Fee Docket Entry` appears directly below `Time Docket Entry`, save a fee against a matter, and confirm the Professional splash logo visibly dissolves in and out before the main window opens.

## WIP Empty-Selection Guard & Packaged Splash Assets (2026-08-05)

- [x] Keep `Create Draft Invoice` clickable with no WIP selection and show a clear, non-blocking explanation instead of starting a build operation.
- [x] Reject empty draft requests in both the billing controller and invoice-draft service, preventing blank invoices from any call path.
- [x] Bundle the root `assets/` folder in release builds and fail the release build if required CSPM splash assets are absent.
- [x] Rebuild and promote the normal `dist/CSPM/CSPM.exe` with the required `CS.svg` and `splash_logo.svg` assets present.
- [ ] Manual foreground verification: click `Create Draft Invoice` with no selected WIP and confirm the warning leaves the builder responsive; then launch `dist/CSPM/CSPM.exe` and confirm the CSPM logo visibly fades in and out before the main window appears.

## Invoice Service Client & Matter Context (2026-08-06)

- [x] Clearly distinguish the invoice `Bill To` recipient from the client receiving legal services.
- [x] Show the actual billed-entry client and matter number/name in a persistent `Legal Services For` block on every invoice, including direct-fee / flat-fee invoices.
- [ ] Manual foreground verification: preview an ordinary invoice and a fee-only invoice; confirm `Bill To`, `Client`, and `Matter` are each visible and accurately identify the work.

## Invoice Date & Close-to-Tray Preference (2026-08-06)

- [x] Make the invoice date explicit in the Invoice Builder, supporting typed `YYYY-MM-DD` values and calendar selection.
- [x] Move the date control into the active `InvoiceBuilderWorkspace` billing-controls panel; the first implementation was in an explicitly hidden legacy fallback layout.
- [x] Validate and persist the selected draft date, invalidate the cached payload, and regenerate the HTML preview immediately.
- [x] Add a persisted Settings toggle for `Close to tray`; use it in the main-window close path instead of unconditionally quitting CSPM.
- [ ] Manual foreground verification: select a draft invoice and verify the blue `Invoice date` panel directly below the preview accepts `YYYY-MM-DD` typing and `Choose date` opens the calendar; set `Close to tray` On, close the main window, and confirm the tray remains usable and restores CSPM; then set it Off and confirm close exits CSPM.

## Invoice Line-Item Field Clarity & Fee Editing (2026-08-06)

- [x] Add light-gray contextual placeholders for blank Date, Description, Hours, and Hourly Rate inputs in the Invoice Builder line-item editor.
- [x] Identify direct fee entries in the draft-line payload and replace the time-only fields with one `Fee amount ($)` input when editing a fee.
- [x] Identify the actual service client and use the matter's plain-English Description (falling back safely to Matter Name) in its place.
- [x] Render third-party service context compactly as `Matter: <client name> | <matter description>` on one line; retain the normal two-field context for ordinary invoices.
- [ ] Manual foreground verification: preview a third-party invoice and confirm the `Legal Services For` block renders `Matter: <service-client name> | <plain-English matter description>` with no coded matter number.

## A/P Settlement Set-Off (2026-08-06)

- [x] Add a linked, non-cash A/P set-off payment method that allocates one supplier-bill settlement against one or more existing receivables, including partial invoice allocations.
- [x] Validate every allocation before saving and post A/P, A/R, ledger, time-entry payment state, expense clearing account, and audit evidence in one atomic workbook replacement.
- [x] Add a matching whole-set-off reversal that restores the A/P bill and all affected receivables together.
- [x] Rebuild and promote the runnable package at `dist/cspm.exe`; preserve its flat executable/_internal/data/recovery layout for future builds.
- [x] Allow an A/P bill total to be entered as the authoritative amount; derive subtotal/HST safely for taxable and HST-exempt bills.
- [x] Make the set-off allocation editor independently vertically scrollable so every allocation can be pasted and reviewed.
- [x] Rebuild and promote the A/P usability repair at `dist/cspm.exe` (SHA-256 `39CA22521371289F5A2E1700CFB9A1F613241C2AA2E2A16660078713B04AE763`).
- [x] Replace raw worker tracebacks in A/P with their concise validation message.
- [x] Stop automatically applying the LIHDC agency share to dockets whose `AmountToYou` is already net of that share.
- [x] Replace typed A/R set-off allocations with a searchable receivable-selection workflow that supports full or partial allocations and an in-dialog balancing total.
- [ ] With CSPM closed, create a recoverable backup and repair the pre-existing double-split balances for invoices 26-0066 and 26-0069 from the supplied July settlement schedule before posting the set-off.
- [ ] Manually verify the set-off workflow in CSPM against a copy of the production workbook before entering the July 2026 settlement.

## Startup Focus Safety Repair (2026-08-06)

- [x] Remove the main-window startup focus lock and every automatic Win32 foreground/topmost escalation.
- [x] Limit splash handoff to one regular Qt activation request and prevent delayed startup timers from reclaiming focus.
- [x] Add a regression test that rejects topmost or foreground-stealing code in the main startup path.
- [x] Limit the settled native window to the visible canvas after confirming the previous release's actual native window covered the full 2380x1500 monitor.
- [x] Restore the backend-boot trigger as a settlement lifecycle action; confirm read-only that the live workbook retains 115 clients, 194 matters, and 682 time entries.
- [x] Rebuild and promote `dist/cspm.exe` (SHA-256 `C2416E8B54FF464ACF37F44B35C615C3E66C985BCFDEAAC944BC725622330791`).
- [ ] Manually confirm that the visible dashboard loads existing data and that another app and the taskbar remain clickable on CSPM's monitor.

## Finalized Preview & UI Polish (2026-08-08)
- [x] Fix HTML Preview Loading UX: Add an animated BusyIndicator cycling circle and tie it to isPreviewLoading.
- [x] Fix Finalized Preview State: Ensure the preview updates to hide the DRAFT tag after finalization.
- [ ] Manual verification: Finalize an invoice and confirm the new success overlay appears, PDF-open buttons work, and the preview removes the DRAFT tag.

## Invoice Directory Matter & Payment Detail (2026-08-10)
- [x] Show each invoice's linked matter with its plain-English description; include time, disbursement, and transaction matter links, with a conservative single-matter historic fallback.
- [x] Show dated payment activity in the ledger card, preserve multiple partial payments, and avoid duplicate transaction/ledger evidence or invoice-creation revenue.
- [x] Refresh an open Invoice Directory immediately after a payment is saved, so the dated history, paid total, and balance update without reselection.
- [x] Enforce all three invoice cards at the 25%-taller height, with balanced flexible top/bottom space rather than an advisory preferred height that the layout may ignore.
- [x] Make the Unpaid status pill 25% more prominent and route it directly to Payment Entry for that invoice.
- [x] Present ledger payments as aligned `Payment | Amount | Date` columns, and let the amount or date open that exact editable payment record; an update adjusts the existing payment rather than creating a second payment.
- [x] Recognize explicitly recorded invoice-linked Transfer set-offs as `Settlement set-off` activity rather than claiming no payments are recorded; include the settlement note and open the editable Transaction Master record in a new tab.
- [x] Rebuild and promote `dist/CSPM/CSPM.exe` after the settlement-set-off correction (SHA-256 `0F69B493A3487812FD7F0C32297834128D9FCE5813C02871CB8D7AC823EAFF40`); retain the replaced package at `to_delete/CSPM__replaced_release_20260810_121803/`.
- [x] Rebuild and promote `dist/cspm.exe` after the update (SHA-256 `7688024CF76F5B41F1E60B9BC91EF44BD155C524260217D06C45BF368671DBA7`); retain the replaced release at `to_delete/dist__replaced_release_20260810_092700/`.
- [ ] Manual foreground verification: select invoice `26-0061` in Invoice Directory; confirm `Commercial Contracts Review`, the Jun 30, 2026 EFT payment, the aligned payment columns, and the taller balanced cards are visible. Confirm an Unpaid pill opens Payment Entry for its invoice, and that clicking a payment amount/date opens that payment for editing. For invoice `26-0069`, confirm the card says `Settlement set-off — LIHDC settlement 2026-07-29` rather than `No payments recorded`; click it and confirm a new editable Transaction Master tab opens for `TXN_e0add4a5d6` while Invoice Directory remains open. Then post two partial payments against a test invoice and confirm both payment dates/amounts remain listed and one can be amended without duplication.

## Productivity Zen Layout & Invoice Status Clarity (2026-08-13)

- [x] Remove the recursive Zen report layout constraint that expanded the forecast/client cards and crushed the chart row below the viewport.
- [x] Derive Invoice Directory labels from the financial balance: positive/no payment = `Unpaid`, partial payment = `Partially Paid`, zero balance = `Paid`; an outstanding status pill opens the prefilled Payment Entry workspace.
- [x] Build and hash-verify the complete runnable release at `dist\CSPM\CSPM.exe` without opening or changing active data. The 4,315-file installed tree matches the isolated candidate (tree SHA-256 `07A78C619B841FBC763C534D922BB76AD8E29412FD104BA92A6B6C29587087D4`); EXE SHA-256 is `341FF04BFC98FBF8C46F29F197060A7FB47E59F2CA64FA65C1ACE5EE824F4003`. The replaced package is recoverable at `to_delete\dist__manual_replaced_release_20260813_232746`, with promotion audit `to_delete\release_promotion_20260813_232746.json`.
- [ ] Manual foreground verification after the next package build: open Productivity Zen View on a maximized display and confirm all KPIs, insights, and both charts are fully visible without overlap; open invoice `26-0077` and confirm the clickable pill says `Unpaid`.

## Same-PC Abandoned Cloud Checkout Recovery (2026-08-14)

- [x] Automatically recover a shared checkout marker only when it identifies this same CSPM installation and Windows confirms its recorded process is no longer running. Preserve a local write-once audit copy before removing that marker.
- [x] Preserve the conservative cross-PC rule: never reclaim a marker from another installation, a different computer name, an unreadable marker, or any recorded PID that is still live or cannot be queried.
- [x] Add focused regression coverage for dead same-PC recovery, foreign-marker protection, and live-process protection.
- [x] With CSPM closed, build/promote the updated package. `dist\CSPM\CSPM.exe` SHA-256 is `94E1DCDDC37E785860BC248D2BD8402775B07B48E8CE20970A25393314907261`; promoted package tree SHA-256 is `98853FF31B48FBDBFE6F17D78C17D3100395F26A624B6417F9A1216B4C2677EF`.
- [ ] Manual foreground verification: launch the new package and confirm the existing OFFICENEW marker is recovered automatically at startup before posting a verified payment.

## Governed Supplier Invoice & Client Disbursement Workflow (2026-08-15)

- [x] Preserve supplier invoice totals in their original CAD/USD currency while storing the entered exchange rate and CAD reporting totals.
- [x] Add shared `Supplier_Invoices` evidence storage with an immutable content hash and portable relative path in the A/P bill record.
- [x] Record a new matter-linked supplier bill as one governed bundle: A/P payable, base-CAD expense transaction, and recoverable WIP disbursement.
- [x] Record a supplier payment as an A/P lifecycle payment plus a separate, linked bank-to-A/P clearing transfer, without double-counting it as a second expense.
- [x] Add the historical-adoption workflow: link an existing legacy expense and existing client WIP to an A/P bill/payment/document trail without adding a duplicate expense, ledger row, or WIP entry.
- [x] Repair historical supplier adoption for legacy expenses with no Matter field: permit a unique, verified ledger chain of expense transaction → supplier invoice → client invoice/work client → ungoverned client WIP, and resolve legacy matter numbers to the current MatterID before pre-filling the entry form.
- [x] Remove the false A/P save timeout: keep the operation active, show a neutral in-progress message, and refresh the A/P list automatically when the guarded write completes.
- [x] Support supplier evidence in PDF, JPG/JPEG, PNG, TIF/TIFF, DOC/DOCX, XLS/XLSX formats. Preserve the original non-PDF file and create a verified PDF evidence copy in the shared folder.
- [x] Make the client-side HST-exempt checkbox label explicitly readable in both light and dark themes and show an indeterminate circular saving indicator while evidence is copied, converted, and verified.
- [x] Build and promote the evidence conversion and A/P progress release at `dist\CSPM\CSPM.exe` (SHA-256 `71C6FE854CB1648F776B9258331BFD9378034EBA280FD92E683ABB738F4BFF5B`; package-tree SHA-256 `EDD8F9506C8FC128DA463D464520EAE098CD01617358C127271F27755222E929`).
- [x] Build and promote the verified complete package at `dist\CSPM\CSPM.exe` (SHA-256 `D6AF0A5E3191AE0DABF6FA7484C9884FEAA2E84EE345BB9C27BF0725E6CA7EC7`; 4,315-file tree SHA-256 `608AA16213872F81C6CEBA0B713B6EEAB65A404BCB4E0137BB319DFCD81B0875`).
- [ ] Manual foreground verification: create one test CAD supplier bill and one USD/HST-exempt supplier bill, attach a PDF and a non-PDF file, confirm their source/PDF evidence files appear under the shared `Supplier_Invoices` folder, invoice the recoverable WIP, and record/reverse a partial supplier payment. Then use **Adopt historical…** to reconcile the Spencer Fane Ferreira record after confirming its candidate amounts.

## Premium Ledger Report Workspace (Implemented 2026-08-15; foreground verification pending)

- [x] Evolve the existing Client Ledger Report data/query layer into one reusable ledger-report foundation; do not create a second divergent query or mutate workbook data merely to display a report.
- [x] Add a dedicated **Today's Time Ledger** route from the Daily Operations **Time today** card. It opens a new work tab prefiltered to Today, all clients/matters, time entries only, grouped and sorted by matter.
- [x] Retain the custom financial **Client Ledger** route and add the matter-time ledger alongside it on the same controller/repository payload. Both report panels are now lazy-loaded so an inactive report cannot initiate a background workbook read.
- [x] Support explicit date range/quick ranges, client, matter, billing-client, and docket-description/reference search filters in the Matter Time Ledger. The home-card route provides defaults only; the user may change every filter in the tab.
- [x] Extend the read-only report payload with matter number, client, distinct billing client, date, description, decimal hours, rate, gross fee, net fee, reference, and status. Preserve existing client-parent and joint-retainer resolution rules.
- [x] Apply a report-wide display rule: show a Billing Client value/column only when it is materially different from the service Client. Compare normalized party identity (ID when available; otherwise trimmed, whitespace-normalized, case-insensitive name). Never duplicate the same party in a row, group heading, report subtitle, or PDF.
- [x] Build matter-group headers and subtotals for the time-ledger mode, including matter number, client, optional distinct billing client, entry count, decimal hours, gross fees, and final report totals.
- [x] Add a purpose-built detached Ledger Zen Window with independent, readable layout, sensible minimum dimensions, and monitor-centering based on the window that initiated the command.
- [x] Add a dedicated branded landscape PDF renderer: firm/report header, applied filters, repeat table headers, matter groups/subtotals, final totals, and page numbering.
- [x] Add focused regression coverage for date/type defaults, matter grouping/totals, equal-versus-distinct client/biller display, home-card navigation contract, Zen-window construction, and PDF creation. Sandbox-safe tests are complete.
- [x] Correct the first live visual/export pass: labelled ledger filters are 56px high to prevent clipped labels/values; status/Zen controls use explicit semantic info tokens in both themes; a successful export now opens the newly created PDF and leaves a visible success message in the ledger.
- [x] Recompose the Matter Time Ledger PDF as a disciplined, full-width landscape report: a three-row scope block states the exact period, data scope, client, billing client, matter, and search filters; aligned KPI columns show matters, dockets, billable hours, gross fees, and net fees; every matter uses the same full-width heading/detail/subtotal grid; detail rows expose separate reference and status columns; and the final summary uses the complete printable width. This removes the former centred short tables and ambiguous, under-specified totals.
- [x] Complete the premium presentation pass: inline and Zen **Export PDF** actions now use the same semantic primary `PillButton`, Zen View and Close use the matching secondary control, and all respond consistently in Professional Light and Dark themes. The PDF now uses a quieter two-row scope card, restrained dividers instead of repeated full grids, deliberately spaced matter units, a consistent full-width grid, and a two-row final metrics bar. A representative two-matter export was visually reviewed as one balanced page.
- [x] With CSPM closed, build and hash-verify the premium ledger release at `dist\CSPM\CSPM.exe`. The release builder completed; Windows denied only its final rename. The governed promotion completed afterward with an exact candidate-to-installed manifest match: 4,321 files, 712,847,900 bytes, SHA-256 `AAFD5B313DB4F087C31211ECD576DFDD3B4C3B72DACE2FBD551115BBCAE42DCF`. EXE SHA-256: `343FB1D508586231A23E0BACC440915CB4666663FAB59F756D77296978B8FE6C`. The preceding release is recoverable at `to_delete\dist__manual_replaced_release_20260815_172816`; promotion audit: `to_delete\release_promotion_20260815_172816.json`.
- [ ] Manual foreground verification: test the Daily Operations **Time today** route, direct **Finance & Ledger → Matter Time Ledger** route, filters, both light/dark themes, Zen View on a non-primary monitor, and exported PDF. Confirm filter text is not clipped, the LIVE READ ONLY pill and Zen action are themed in both modes, each Export PDF command opens the PDF, and no duplicate Billing Client text appears when the parties are the same.
- [x] With CSPM confirmed closed, build and hash-verify the updated package at `dist\CSPM\CSPM.exe`. The guarded builder completed, Windows denied only its final directory rename, and the verified copy-promotion path installed the complete 4,321-file release. EXE SHA-256: `111853C4B42B63F6225530ECB1748E2B178B3EB683F67CE8DC603D324C4B06B2`; package-tree SHA-256: `BA7C72A6C60B5E384154AAB5614FE85A33132B2BBE534246CEEE00AC57A3B28C`. The six affected bundled QML files match source and the EXE has no `Zone.Identifier`. The prior package remains recoverable at `to_delete\dist__manual_replaced_release_20260815_155250`.
- [x] With CSPM still closed, build and promote the PDF-layout follow-up at `dist\CSPM\CSPM.exe`. PyInstaller completed both bundles; Windows denied only its final directory rename. The guarded copy-promotion command exceeded its console limit after materializing the destination, but independent source-versus-installed tree manifests match exactly: 4,321 files, 712,846,829 bytes, SHA-256 `EC1966FF2FD76A40E3509C0DB23129855991E5DE519714A91E9C88F1EFD0B962`. `CSPM.exe` SHA-256 is `B18BF5AF1B5194BACC663F3FF4EAB8A6F8741AD6A1F977AB82123736F55BC8B6`; the package has no `Zone.Identifier`, and the previous package is recoverable at `to_delete\dist__manual_replaced_release_20260815_165820`.
- [x] Replace the Matter Time Ledger's landscape export with a true portrait composition: the canonical Cory Schneider Law Office invoice/report mark beside the firm block; concise three-row scope card; portrait-native KPI strip; date, description/status, hours, rate, gross, and net ledger grid; exact-grid matter subtotals; and a compact four-metric final summary.
- [x] Add structural pagination rules rather than relying on margins: a matter heading is kept with its first docket, a large matter's final docket stays with its exact-grid subtotal, repeated detail headers continue across pages, and the Final Summary title/values are one indivisible unit.

## Singularity Exit VFX & Direct In-Place Close Engine (2026-08-16)

- [x] Full Revert to Git Cloud baseline (`origin/main` commit `c692fad`): all original window dragging, Aero Snap, minimize, restore, and header logic completely restored to their pristine state.
- [x] Direct In-Place Singularity Close Engine:
  - Eliminated fragile secondary overlay window handoff, asynchronous `grabToImage` bitmap memory reclamation issues, and DWM multi-window transparency FBO composite failures.
  - Implemented 550ms Singularity mathematical collapse ($p^{0.7} \times \pi$ tidal spaghettification, $720^\circ$ continuous vortex twist, $(1-p)^{2.2}$ scale decay, smooth fade-out) directly in `JellyController.qml` on the live window's hardware-accelerated scene graph.
  - Embedded 250-particle orbital accretion Canvas directly inside `DetachedShellWindow.qml` with dynamic radial gradient glow (`#38BDF8` $\to$ `#818CF8` $\to$ `#F472B6`).
  - Eliminated pre-animation flash/flicker by bypassing `applyClosingGeometryAtomically()` on in-place close, locking the settled host window envelope without DWM/FBO resize repaints, and maintaining seamless rounded-mask shader continuity.
  - Added Motion FX Studio launcher in `SettingsMenu.qml` and backend setting slots in `AppController`.
  - Promoted verified release package at `dist/CSPM/CSPM.exe` (SHA-256 `B7DB028380AD040253967F4C63AC2BC5457272A94D5120301082C6804AE2F693`).

## Gravitational Siphon Minimize & Restore Engine & Plasma Inward Close (2026-08-16)

- [x] Implemented direct in-place Gravitational Siphon minimize and restore engine in `JellyController.qml` and `DetachedShellWindow.qml`:
  - Configured strictly vertical downward host envelope extension (`hostX` and `hostY` do not move, `hostW` does not expand sideways, `hostH` extends from window top to taskbar), allowing the full gravitational Y descent all the way to the real Windows taskbar at the bottom of the screen (`targetDistY = screenBottomY - (finalY + finalH)`) without horizontal desktop click-blocking.
  - Siphons downward into the top of the Windows taskbar with gravitational acceleration ($\text{transY} = p^{2.2} \times \text{targetDistY}$), a $360^\circ$ continuous cosmic spiral twist ($\theta = p^{2.2} \times 360^\circ$), asymmetric tidal tapering ($scaleX \to 0.002, scaleY \to 0.002$), and terminal fade.
  - 380ms white-hole restore ejection ($1.0 \to 0.0$ reverse bloom out of the taskbar with 3% elastic settling bounce).
  - Eliminated restore frame 0 flash/flicker by binding `wasWindowMinimized` state and initializing `opacityVal = 0.0`, `transY = targetDistY`, `scale = 0.002` on restore before frame 0 paints.
  - Fixed `Math.pow(negative, 2.2)` `NaN` evaluation in `onMinimizeProgressChanged` during `Easing.OutBack` restore overshoot, completely eliminating the late-phase restore flicker.
  - Completely disabled `Behavior on x/y/w/h` on the native OS window, ensuring single-frame instantaneous maximize/restore-from-maximize without continuous swapchain resize strobing.
  - Integrated 250-particle accretion stream swirling down with `jelly.transY` to the top of the taskbar.
  - Synchronized assets to `dist/CSPM/_internal/src/qml/`.
- [x] Implemented Right-Click Minimize-to-Tray Comet Engine & Unobtrusive Toast:
  - Right-click detection on minimize title bar buttons in `ProfessionalTopHeader.qml`, `MainContent.qml`, and `TitleBarButton.qml`.
  - Dynamic System Tray / Clock coordinate calculation across multi-monitor setups (bottom taskbar tray, side/top taskbars, or bottom-right corner fallback).
  - 2D vector-aware comet trajectory along angle $\theta = \text{atan2}(\Delta Y, \Delta X)$ with backwards-trailing incandescent plasma wake and sparks.
  - Symmetrical reverse restore launched from the exact stored terminal coordinates back into center pinpoint and outward bloom.
  - Unobtrusive floating glass toast notification informing the user that CSPM is running in the system tray, auto-dissolving with a smooth premium fade-out after ~3.2s.
  - Synchronized assets to `dist/CSPM/_internal/src/qml/`.
- [x] Manual foreground verification: launch `dist/CSPM/CSPM.exe` and test right-click minimize to tray and tray restore.
