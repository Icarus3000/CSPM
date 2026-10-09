# Professional maximize/restore speed and smoothness — 2026-10-03

The user accepts the smooth expansion from a smaller window, but requests at
least three times the speed. Their clarification makes KDE/Fedora-style
continuous motion and natural deceleration an explicit acceptance requirement.
Their further clarification requires **one uninterrupted smooth movement from
start to finish**: no perceptible pause, restart, jump, jerk, or separate final
settling movement. Speed improvement only qualifies if it preserves that
complete visual continuity, including the captured-image/live-window handoff.
The latest clarification requires a fluid feel, **flowing like plasma or
water**, with smoothly blended speed changes and arrival, without a jarring
moment anywhere in the movement.
The user identifies the existing app opening and closing animations as
perfectly smooth and flowing; use their accepted quality as the visual
benchmark for maximize and restore, and preserve those transitions.
The accepted production transition is unchanged. No faster candidate has met
both requirements, and none was deployed or published.

## Measured result

Review the repository runtime log and the latest installed session in
LocalAppData before diagnosis. The repository log is historical; current
packaged logging appends sessions under LocalAppData. Use the portable full-app
probe with disposable workbook/settings copies and a retained Productivity
workspace. Timings start at the invoked QML button handler and record GUI
handling of submitted-frame signals; they are not physical input-to-scanout or
frame-pacing measurements.

A same-process comparison completes 20 primary toggles, five samples per
direction/configuration, plus the three taskbar/close lifecycle transitions.
All functional assertions pass and no surface watchdog timeout occurs.

| Configuration | Maximize median | Restore median |
| --- | ---: | ---: |
| Accepted 800 ms preparation / 220 ms settlement | 1,122 ms | 1,269 ms |
| Experimental 240 ms preparation / 65 ms settlement | 924 ms | 877 ms |
| Actual total speed ratio | 1.21× | 1.45× |

The preparation and settlement timelines overlap when the target becomes
ready. An 800 ms preparation duration is not an unconditional 800 ms wait.
Shortening both animators by over 3× does **not** shorten the whole transaction
by 3×.

In the separate six-toggle baseline, target geometry/layout commit takes a
median 265.5 ms, and target frame readiness plus capture another 286.5 ms.
The shorter-timing run still spends 276 / 244.5 ms at these boundaries. The
experimental preparation animation can reach its 85% cap before target
readiness, leaving a timing gap before settlement. This is a continuity risk
inferred from the timings and state machine; subjective smoothness or a
compositor-visible pause was not independently measured. Functional success
does not establish the user's visual requirement.

## Rejected experiments

Each full-app experiment uses a disposable QML tree and six primary toggles
plus lifecycle checks. Their functional assertions pass, but the measured
costs do not justify adoption. Independent runs are exploratory comparisons,
not controlled causal estimates.

| Trial, using short motion timings | Total median | Geometry/layout commit | Target readiness + capture |
| --- | ---: | ---: | ---: |
| Short motion only | 904 ms | 276 ms | 244.5 ms |
| Separate QObject metric fields | 1,047 ms | 321 ms | 280 ms |
| Immediate synchronous target capture | 2,004.5 ms | 312 ms | 1,264.5 ms |
| Lazy close/recovery/redock prompts | 899 ms | 291 ms | 249 ms |
| One metrics publication per dimension commit | 950.5 ms | 295.5 ms | 255 ms |

An additional minimal QML experiment confirms that Qt's property update group
does not coalesce these ordinary QML bindings: the metrics expression evaluates
once initially and twice more during the grouped width/height changes.
Do not introduce that API as an unproven batching fix.

The first lazy-prompt experiment fails before launching because its mirror
rewrite loses a marker. The corrected retry is the completed row above; retain
the failed diagnostic result. The direct-capture trial is especially unsuitable:
Qt's threaded capture path polishes and synchronizes before readback, so
invoking it earlier is not a free reuse of an existing framebuffer. The exact
Qt 6.10.3 implementation was inspected in [Qt's render-loop source](https://github.com/qt/qtdeclarative/blob/v6.10.3/src/quick/scenegraph/qsgthreadedrenderloop.cpp);
[the API documentation](https://doc.qt.io/qt-6.10/qquickwindow.html#grabWindow)
also identifies its performance cost. The trial measures a regression, rather
than proving which internal wait caused it.

## Retained work and reproduction

Only a diagnostic mode is retained in
`scripts/diagnostics/window_responsiveness_probe.py`. It alternates the accepted
and experimental timing pairs inside the disposable copy, preserves every
frame gate, and labels each result with `baselineMotion`. Default diagnostics
continue using production timings. Production QML, shaders, Python runtime,
dist and installed runtime are unchanged; no executable rebuild, deployment,
commit/push, or financial command occurred.

Run outside a WebEngine-restricting sandbox, using the local project venv:

```powershell
& $CspmPython scripts/diagnostics/window_responsiveness_probe.py --compare-short-motion --screen-index 0 --audit-label maximize_speed_comparison
```

Set `$CspmPython` to the project interpreter created by `scripts/bootstrap_dev_env.ps1`.
This is a performance/functional diagnostic, not a smoothness certification.
Raw local evidence is under `logs/maximize_speed_*_20261003`; nonsensitive
aggregate measurements are in
`docs/MAXIMIZE_RESTORE_SPEED_AND_SMOOTHNESS_RESULTS_2026-10-03.json`.

## Continuity clarification follow-up: profiling remains inconclusive

After the user requires one uninterrupted movement, further profiling is
attempted in disposable desktop fixtures. A first Python profiling harness
fails to compile before launch. Its corrected run reaches two primary commands,
but both time out at the source-frame gate, before committing target geometry;
the fixture also fails its state assertion and overall timeout. These Python
call statistics do not profile the target-layout bottleneck. A report refresh
appears in the waiting interval, which does not establish it as the cause of
resize cost.

An unmodified control, native Qt render-timing attempts, and a diagnostic-only
elapsed-time animation-driver trial also fail to produce a completed target
layout profile. Stalled fixtures are stopped using their exact diagnostic
command lines. The rendering trace covers initial/source frames, not a complete
resize. It cannot certify pacing or support a production optimization. The
elapsed-time driver is not adopted: [Qt 6.10's documentation](https://doc.qt.io/qt-6.10/qtquick-visualcanvas-scenegraph.html#driving-animations)
also identifies a possible smoothness tradeoff.

Preserve these failed/incomplete attempts under
`logs/maximize_speed_python_profile*20261003*` and
`logs/maximize_continuity_*20261003*`; exclude them from the earlier passing
60-primary-toggle aggregate and from speed estimates. No further production,
packaged or installed change is made. Follow-up sandbox-safe checks cover
diagnostic compilation and whitespace only; outside-sandbox desktop profiling
is unsuccessful. No new WebEngine e2e check is run.

## Validation and next gate

Sandbox-safe checks: 28 existing window choreography/control feedback/layout
persistence/native-state tests pass; the diagnostic compiles; governed QML lint
returns 0 with existing warnings during the temporary timing trial; whitespace
checks pass. The temporary production timing edit was reverted.

Outside sandbox: actual desktop/full-source Qt GPU timing and functional
workspace/geometry/taskbar/close checks described above. No new dedicated
WebEngine HTML/PDF e2e or packaged startup test was run in this investigation.
Existing packaged WebEngine release checks remain historical evidence.

P0 stays on this same maximize/restore workstream. The threefold total-speed
target and KDE-style continuity remain unmet. Next useful implementation work
needs a component-level profile beneath the measured layout and first resized
render boundaries, followed by a demonstrated reduction there. Retain exact
native endpoint pixels, fixed title/glyph size, the existing workspace, all
readiness gates and the watchdog. Do not repeat the rejected metric/capture
experiments without new evidence, or declare shortened timers a completed fix.
The user must judge the faster continuous glide in the real app before moving
to another visual state machine.
