# Clean-room maximize/restore learning record

This experiment belongs to `experiment/clean-room-fluid-maximize-restore`,
based on `ad72d59160eb510dc842d0c6978967cb793fba49`. Production remains the
default and is preserved in the original checkout and installed package.
Fedora KDE Plasma is the governing external perceptual benchmark; CSPM's
accepted opening and closing are the protected internal benchmark. Cory's
populated installed-app judgment remains the final authority.

## Checkpoint 1 — initial model, before implementation-level inspection

- **PROVEN BY MEASUREMENT (historical):** shortening production's timelines
  improved complete transactions only 1.21x/1.45x. Measured target commitment
  and render/capture boundaries total approximately 552 ms. These boundaries
  do not identify individual component causes.
- **SUPPORTED BY OBSERVATION:** previously accepted corrections preserve
  title/glyph dimensions, control appearance and physical framebuffer endpoint
  alignment. Retain their contracts and pixel tests, not their state machine.
- **SUPPORTED BY OBSERVATION:** the internal opening/closing benchmark keeps
  one coherent composed surface through its visual evolution. Existing open
  PERF logging ends before the visible bloom; it cannot measure that bloom.
  A disposable benchmark is collecting submitted frames without changing
  either implementation. Physical scanout remains unmeasured.
- **WORKING HYPOTHESIS:** KWin's decisive advantage is ownership of continuous
  window textures in its compositor, rather than exchanging a captured image
  for an independently resized native host. Authoritative revision/path/SPDX
  research is in progress and will replace assumptions with source findings.

### Primary architecture selected

Test a native GPU framebuffer bridge feeding a fixed presentation window.
Copy the actual D3D11 render target to a shared, immutable GPU texture and
import it on the presentation window's device, retaining physical client
origins and sizes. Prepare the same existing live workspace beneath that
surface. Do not instantiate another workspace. Source/target textures are
composed on a single render-thread 350 ms motion clock. A predetermined smooth
content-transfer curve and fixed-size header mapping share that clock;
target readiness must never pause, cap, restart or change geometry progress.
Submitted target/live pixels, exact geometry and input restoration still need
explicit ownership. Reduced motion selects immediate guarded state adoption.
Failure is logged, releases textures and restores safe production ownership;
no watchdog extension or saved-normal-geometry mutation is permitted.

This differs from native-state/Gemini attempts because the visible native
surface stays fixed and owns immutable pixels. It differs from production
because GPU copy/import replaces CPU framebuffer readback/reupload and one
clock replaces preparation plus settlement. Native GPU APIs are a feasibility
question, not an established improvement. No KWin source is reused.

### Decision-changing experiments

| Question | Prediction | Objective gate | Next decision |
| --- | --- | --- | --- |
| Can public Qt/PySide plus a narrow D3D11 bridge preserve exact native framebuffer pixels across windows without readback? | Shared GPU textures retain physical dimensions and alpha with materially cheaper transfer. | Exact source/target pixel equality; repeated resource release; no runtime/device error. | Integrate if passed; reject GPU bridge if unavailable or unsafe. |
| Does removal of readback/upload leave enough time for target layout on a fixed clock? | Target render reaches a predetermined transfer deadline. | No readiness-driven curve change, plateau or content step; complete transaction materially faster, goal >=3x. | Keep primary only if full-app evidence passes. |
| If primary fails, can exact idle endpoint preparation be bounded and invalidated safely? | Possibly on quiescent screens; continuously changing views may invalidate it. | Same workspace, exact revision/geometry/DPI key, no moved visible delay or long idle input stall, cold-cache/load checks. | At most one materially different fallback; reject stale or disruptive caching. |

## Evidence boundaries and protected state

Only root `AGENTS.md` applies. `_cspm_workspace/CURRENT_STATUS.md` and
`WORKSPACE_PLAN.md` referenced by the old index are absent; `task.md` and
`implementation.md` are the durable current equivalents. Original dirty
diagnostics/docs and all stashes/worktrees are preserved. Installed main hash:
`8D461B679B4D578CFB6BE6DE259AB2E183E62A6D9F1EB944A69527BEFC8C0FA3`.
Repository runtime log is historical August 20; latest installed session is
October 3 09:20–09:24. Neither supplies complete physical motion evidence.

No packaging or installation is allowed before the user's qualification
gates. The experimental selector must remain explicit and default production.
Raw logs, frames, profiles and copied workbooks remain ignored local evidence.

## Next checkpoints

2. First complete prototype: expected/actual timing, content continuity,
   remaining readiness dependency and next decision.
3. Objective rejection/promotion: full transaction, pacing, derivatives,
   pixel/luminance/sharpness evidence and KDE perceptual evidence limits.
4. Integrated candidate: retained discoveries, discarded assumptions,
   geometry/content/live ownership, benchmark comparison and acceptance gaps.
5. Final handoff: useful findings, real candidate/rejection status, safe
   fallback and Cory's single next action.

## Decisive native GPU capability gate — defined before execution

The user's latest steering makes a small native C++ composition bridge the
next priority. The separate QML single-clock implementation is a comparison
fallback only; no native full-engine promotion precedes this spike.

**Question:** can a populated Qt Quick framebuffer reach a fixed Windows
DirectComposition host through GPU-only copy/sharing, with compositor motion
independent of the Qt GUI/layout thread? **Prediction (WORKING HYPOTHESIS):**
typed D3D11 capture of Qt's current render target, immutable shared texture,
keyed-mutex synchronization and same-adapter DirectComposition copy can supply
the missing ownership boundary. Python passes only an opaque public Qt native
context pointer to C++; no Python virtual-table/ABI/native-binding emulation.
MSVC and the installed Windows SDK are available. No toolchain is installed.

**PASS requires all of:** representative populated source and differently
sized target GPU frames; no CPU full-frame path feeding presentation; sampled
physical motion through an intentional GUI stall; fixed-schedule transfer that
never changes trajectory; translation-only header dimensions; exact physical
source/target and matching first live endpoint; stable repeated directions;
bounded, reported failure when a target misses its deadline. A colored minimal
window, successful compile or compositor-independent timer is insufficient.

**FAIL is classified as:** Qt redirection/native texture access, device
compatibility, synchronization, DirectComposition presentation, physical pixel
mapping, readiness deadline, live-HWND handoff, packaging or lifecycle. Missing
physical evidence is unvalidated, not a pass. Raw images stay in RAM.

If this gate passes, integrate this native foundation with the same CSPM
workspace and compare whole transactions against production. If it fails,
test at most one independent QML fixed-clock fallback; do not resume minor
production duration changes. No installed production file/data is touched.

### Lessons confirmed by authoritative KWin source

**SUPPORTED BY OBSERVATION (source):** canonical KWin revision
`ee272a4d33c4d7966ee342e051313f2cb5813ee0` uses default Stretch, nominal
250 ms OutCubic, an old GPU appearance over current live target pixels and
compositor-owned scheduling. Its actual clock accumulates capped predicted
presentation deltas; the earlier uncapped absolute-clock assumption is
**DISPROVEN**. It still needs committed target client content and can scale
decorations. CSPM independently needs protected header treatment, cold-command
latency and exact physical live handoff. See the per-file SPDX, source paths,
release distinction and Windows capability mapping in
`KWIN_MAXIMIZE_REFERENCE_2026-10-03.md`. No KWin source is copied or adapted.

**PROVEN BY MEASUREMENT (GUI-delivered observations only):** the protected
opening/closing run retains 209 submitted-frame deliveries, with changing
opening span 361.86 ms and complete close 1215.92 ms. Largest sampled motion
gaps are 28.00/38.92 ms. Physical scanout, jerk and subjective acceptance are
**STILL UNKNOWN** for this measurement. The internal benchmark's lesson is
cohesive presentation through arrival, not a prescription to copy its code.

### Native access result: first populated GPU capture

**PROVEN BY MEASUREMENT — texture access only:** the isolated real CSPM
Productivity workspace renders through Direct3D11. The public
`QSGRendererInterface::DeviceContextResource` queried in a one-shot render
callback supplied the typed SDK bridge with the current 1122x782 client render
target. Native immutable GPU copy returned successfully; request-to-GUI result
was 88.66 ms, with 44.93 ms inside the callback/copy boundary. Frame dimensions
equal actual Windows client dimensions. Source presentation requires zero CPU
frame readbacks/uploads by construction; no image supplies the native host.
The fixture released its frame and closed the app normally. Protected original
workbook/settings hashes match. Evidence: ignored
`logs/native_gpu_access_20261003_run1/native_gpu_spike.json`.

**STILL UNKNOWN:** visible composition, exact pixels, independent motion under
GUI delay, target deadline, header mapping and live handoff. The result answers
the missing-native-binding question without unsafe Python pointer emulation;
it does not qualify the engine. Next decision-changing run uses the same
populated workspace, 350 ms absolute composition clock, fixed 240 ms target
transfer deadline and an intentional 80 ms GUI delay. No readiness-driven
clock changes are permitted. That run will distinguish native presentation
capability from target-layout latency.

## Checkpoint 2 — cold populated native motion fails the readiness gate

**PROVEN BY MEASUREMENT:** outside-sandbox
`native_gpu_composition_20261003_run1` obtains both actual source (1122x782)
and resized target (1920x1040) as native GPU frames. Source capture is 0.88 ms
inside the render callback in this warm trial. The native motion clock runs
350 ms and its transfer deadline stays 240 ms. The intentional GUI delay is
80.59 ms; committing the populated target then takes 323.23 ms. The target
reaches the bridge about 705 ms after motion starts. It is rejected as late;
zero repeated transitions complete. The deadline and movement are not extended.
Protected original workbook/settings hashes match after normal cleanup.

**SUPPORTED BY OBSERVATION:** the independent desktop coordinate collector
shows source markers moving while the GUI is delayed and while Qt commits the
layout. Geometry reaches the endpoint before target readiness, leaving a
source-only hold. This is a failed complete experience, even though native
ownership removes GUI-driven movement stalls. Exact glyph appearance, endpoint
pixels, repeated handoff and mixed-DPI correctness remain **STILL UNKNOWN**.

**DISPROVEN:** obtaining a GPU target by itself removes populated Qt target
latency from the critical path. GPU transport succeeds; cold layout/render
readiness still controls whether the fixed appearance schedule can be met.
The native foundation is therefore not qualified for integration or packaging.

**Next decision-changing isolation:** prepare the same workspace's target
before the native clock starts, then measure GPU endpoint presentation and
live-HWND handoff through repeated directions. That stationary preparation is
included in complete timing and cannot qualify as a fast candidate. A single
premultiplied GPU shader replaces stacked source/target visuals to test exact
alpha and endpoint mapping; this corrects presentation inside the same primary
architecture, rather than changing clocks or attempting another fallback.
If this isolated capability works but cold readiness still fails, reject the
primary full contract and test the one independent QML fixed-clock fallback.

**Engineering value:** the experiment now distinguishes GPU access and native
motion ownership from target-layout readiness. A complete solution must change
the latter dependency; hiding a pre-render wait or stretching the clock is not
an acceptable discovery.

## Checkpoint 3 — submission is not the displayed endpoint

**PROVEN BY MEASUREMENT:** the first premultiplied GPU shader isolation
finishes four repeated directions. All four stable source/live desktop pixel
comparisons are exact. All four target/live comparisons fail (about 57–63% of
pixels differ). Stationary preparation is counted: command-to-handoff spans
approximately 1.73–1.98 seconds, not 350 ms. GPU source and target imports use
the same adapter and no CPU framebuffer presentation path.

**SUPPORTED BY OBSERVATION:** the independent desktop collector still sees
intermediate geometry after the native endpoint submission flag. The flag
therefore does not establish the displayed endpoint; assigning the differences
to a shader or Qt layout defect would be premature. Source GPU presentation
is established, while target/live equality and physical pacing are unresolved.
The nominal movement's collector medians are about 31–33 ms; this is also
insufficient evidence for the required silky experience.

**DISPROVEN:** a successful `Present` and an elapsed endpoint flag can safely
release the live HWND by themselves. Queue ownership and displayed-frame
readiness are part of the architecture, not optional measurement details.

**Next decision:** use a separately named native build with DXGI frame latency
limited to one and a bounded wait before each render. QPC is sampled after
the wait; readiness still cannot alter motion. This remains the primary GPU
architecture, with independent native-thread presentation rather than KWin's
compositor-owned animation. A labelled 120 ms diagnostic endpoint hold will
separate settled pixel equality from scanout timing and remains included in
complete timing. It cannot justify a fast-candidate or seamless-handoff claim.
Then test the sole QML fixed-clock fallback against the unchanged production
control, without revisiting production duration constants.

## Continuity checkpoint — exact preserved boundary, 2026-10-03

The prior session had already completed both the corrected prepared-endpoint
isolation and a corrected **cold** rerun. The user's continuation handoff says
the cold rerun was about to begin; ignored raw evidence shows it finished at
12:00:39 Eastern. Do not repeat it merely because the learning record stopped
at Checkpoint 3. This checkpoint reconstructs existing evidence; it is not a
new desktop test. All failed runs remain preserved, and the aggregate JSON's
original top-level gates and `gateScope` still describe the first cold trial.
The appended run and `continuityReconstruction` describe this later boundary.

**PROVEN BY MEASUREMENT — constrained endpoint capability:**
`native_gpu_paced_prepared_20261003_run1` completes four alternating directions
with zero differing pixels in all four source and all four target/live
full-frame comparisons. The paced DLL hash is
`68391F186018C1AF4D4F6526D8F28A299DBA0F10929886D98C9B882CE6AA03A7`.
This proves exact transfer is feasible on the tested device when the target
is prepared before the native clock and a labelled 120 ms endpoint hold is
used. Complete command-to-live times are 1451–1717 ms. It does not prove prompt
cold use, a no-hold handoff, smooth protected glyphs, mixed DPI, lifecycle
regressions or the required threefold improvement. The earlier four failing
target comparisons remain failed evidence. Corrected queue/sampling behavior
supports a presentation-boundary explanation; changing both queue pacing and
the endpoint sampling wait does not isolate which change accounts for every
pixel difference.

**PROVEN BY MEASUREMENT — corrected cold gate still fails:**
`native_gpu_paced_cold_20261003_run1` uses that same paced DLL, with
`prepared_target=false` and `endpoint_hold_ms=0`. Two directions are requested;
the first maximize fails and zero complete. Its source full-frame comparison
has zero differences. The differently sized 1920x1040 target arrives **884.16
ms after the logged native start**, missing the immutable 240 ms appearance
deadline by 644.16 ms. The authored movement remains 350 ms. No target upload,
target presentation or successful target/live comparison is exercised.

The measured cold boundary decomposition is:

| Boundary | Measured duration |
| --- | ---: |
| Intentional GUI delay | 80.23 ms |
| Blocking target geometry/layout call | 439.51 ms |
| Target capture request to render callback | 239.53 ms |
| Native capture submission boundary | 13.90 ms |
| Capture finish to queued GUI result delivery | 110.74 ms |

These are causal ordering boundaries, not individual binding, polish, scene
graph, WebEngine, GPU fence or component costs. GPU copy submission occupies
only part of the observed target delay. **STILL UNKNOWN:** what creates each
underlying layout/render/delivery cost and which change could remove it while
preserving the same workspace and exact pixels. The original 704.52 ms cold
run used the earlier visual-control DLL and omitted the whole-frame source
pixel instrumentation; the later 884.16 ms result is not a matched causal
comparison or proof that pacing made readiness slower.

**PROVEN BY MEASUREMENT — unconfigured visible plateau:** the independent
desktop collector observes the first changed marker coordinates 74.81 ms
after logged native start, or 412.63 ms after command. A complete source-only
endpoint coordinate signature is then stationary for **at least 440.68 ms**
(440.66–881.34 ms after start), before cleanup changes the scene. One changed
sample occurs within GUI sleep and eleven during the blocking layout call.
The nominal 350 ms motion contains twelve collected samples, with 30.59 ms
median / 44.85 ms maximum intervals. These observer timestamps precede frame
grab/processing and are not exact scanout or compositor frame-pacing data.
They establish independent motion and an unacceptable complete-experience
pause, not a silky candidate. No diagnostic hold was configured in this run.

**SUPPORTED BY OBSERVATION — failure ownership remains incomplete:** current
native rendering marks absent target content failed at the authored blend
deadline and continues its geometry clock unchanged. The Qt fixture is blocked
in layout/render readiness and only observes failure when the late capture
returns, at 884.52 ms after start; cleanup finishes at 906.74 ms. The later
`set_target_frame` guard replaces the original deadline error with its generic
already-failed transaction message. The raw cold log therefore does not retain
or timestamp the earlier native rejection. Precommit safe fallback and
never-arriving-target recovery remain **STILL UNKNOWN**. Original production
workbook/settings hashes match in all five preserved native runs.

**SUPPORTED BY OBSERVATION — preserved source provenance has limits:** current
native source timestamp (11:54:37) precedes the paced build (11:54:48), and its
exports/logic agree with the measured DLL. There is no contemporaneous saved
source hash/build manifest proving an exact source-to-binary mapping. Current
spike script timestamp (11:58:58) follows the passing prepared run (11:57:38)
and precedes the failed cold run. The current script includes optional native
presentation telemetry and `presentation` fields on endpoint events; preserved
prepared rows have neither field, and the cold run fails before that polling
branch. That added telemetry is therefore unvalidated by preserved desktop
evidence. Source hashes observed during this continuation are recorded in the
aggregate as audit snapshots, not original run provenance. No malformed edit
is established by these evidence gaps; current compilation and focused checks
belong to the continuing implementation task.

**DISPROVEN:** corrected queue pacing by itself qualifies the cold populated
transition. **SUPPORTED BY OBSERVATION:** the GPU capture/presentation boundary
and constrained exact endpoint transfer remain useful engineering discoveries.
They do not remove cold responsive-layout readiness from this experiment's
critical path. **STILL UNKNOWN:** a qualifying native design, the authorized
QML fixed-clock fallback's complete A/B result, and Cory's installed KDE-quality
acceptance. No package or installed production change is permitted at this
boundary.

**Next decision-changing work:** preserve and check the exact current source;
instrument only deeper geometry/layout/render/delivery boundaries that can
change the cold architecture decision. Any new cold run must identify its
source/binary and instrumentation changes and retain failures. If the primary
cannot meet a fixed cold appearance schedule without an endpoint hold/content
replacement, reject its full-candidate qualification and measure the sole
independent QML fixed-clock fallback against unchanged production. Do not
reinterpret prepared identity as a speed fix or repeat duration tuning.

Evidence: `docs/CLEANROOM_NATIVE_SPIKE_RESULTS_2026-10-03.json` and ignored
`logs/native_gpu_paced_cold_20261003_run1/` / its console log. Raw desktop pixels
remain in RAM; the durable record contains only nonsensitive aggregate metrics.
This reconstruction uses safe filesystem/JSON/CSV inspection only. Prior raw
desktop trials were outside sandbox; this checkpoint performs no new Qt GUI
launch, WebEngine e2e, packaging or user acceptance.

### Continuation current-source cold recheck

The root continuation rebuilds the current preserved native source into a
separate `cspm_cleanroom_continuity.dll`, preserving all prior binaries. Build
log: `outputs/native_cleanroom/build_20261003_145746_59056.log`. New DLL SHA256:
`42F63DEC5E329AF22E622460B51AAC52DDB5AF64F369D6F6819FB4842834815A`.
The current C++ source hash observed during the audit is recorded separately
in the aggregate; it does not retroactively establish the prior runs' exact
source provenance.

`native_gpu_continuity_cold_20261003_run1` fails before any transition command
because the optional desktop measurement dependency `dxcam` is unavailable.
This is a preserved fixture failure, with unchanged protected hashes, rather
than architecture motion evidence. The root provides the dependency through
ignored isolated `outputs/pixel_dependencies` and retains the failed run.

**PROVEN BY MEASUREMENT:** subsequent
`native_gpu_continuity_cold_20261003_run2` reproduces the cold readiness failure
with that rebuilt DLL, cold target and zero configured endpoint hold. Four
directions are requested, but the first maximize fails and zero complete.
Source full-frame comparison remains exact. Target delivery is **854.95 ms
after logged native start**, missing the fixed 240 ms deadline by 614.95 ms.
The measured boundaries are 80.92 ms intentional GUI sleep, 453.25 ms blocking
geometry/layout call, 219.48 ms request-to-render callback, 11.55 ms capture
submission and 89.53 ms queued GUI delivery. Full command-to-fixture-finish is
1300.37 ms; this is failed diagnostic cleanup time, not a successful handoff.

The independent collector first observes changing coordinates 63.77 ms after
logged native start (489.66 ms after command). The source-only endpoint marker
signature stays stationary for **at least 428.12 ms**, from 435.52 to 863.64 ms
after start. One changed sample is within intentional sleep and eleven during
the blocking layout call. The nominal motion has twelve samples, with median
30.50 ms / maximum 39.82 ms intervals. These remain sparse observer timings,
not exact scanout/pacing or subjective smoothness. No target/live successful
handoff is exercised. Original protected hashes match.

The recheck verifies that coherent compilation of the preserved source does
not remove the cold defect. It does not identify individual layout costs,
qualify the current unexercised endpoint telemetry, or justify installation.
The next decision boundary remains deeper scoped profiling and, if the primary
cannot qualify, the sole independent QML fixed-clock production comparison.
This new full-app desktop run was executed by the root outside sandbox; the
evidence audit itself uses only safe file/JSON/CSV inspection. No new dedicated
WebEngine HTML/PDF rendering or installed acceptance is established here.
