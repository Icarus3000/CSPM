# Submitted-surface probe qualification — 2026-10-08

**FINAL PIXEL AND LIFECYCLE BLOCKERS MATERIALLY REDUCED — CANDIDATE NOT YET QUALIFIED.** The former submitted probe is proved unreliable by synthetic markers. The corrected revision-keyed probe now matches target/live samples on the completed Directory control. Setup, cold-readiness and source-band failures remain retained; uninterrupted motion and a complete candidate are not qualified.

## Probe coordinate and immutable identity proof

**PROVEN BY MEASUREMENT:** the original flip-model submitted-buffer reader differs on 99 of 135 stopped source markers and 39 of 45 endpoints. The corrected retained snapshot differs on zero of each. The independently CPU-authored two-format control compares all 270 source and 90 endpoint markers exactly in BGRA8/RGBA8, including corners, four edges, centre and the narrow mismatch band. One-texel row pitches are 64 bytes in both formats. Snapshot survives host hide, resource/revision identity is distinct, and intermediate motion makes zero diagnostic snapshot copies. Real D3D11/Present evidence is separate from scanout.

The native diagnostic enables an immutable BGRA snapshot before source preparation. It copies before the recorded stopped source/endpoint Present, associates host generation, snapshot revision, source/target frame revisions, ordinal GPU-resource identities, submitted Present ID, witness revision and phase, and verifies the same identity before/after sampling. The old rotating swapchain backbuffer is no longer treated as the last submitted immutable pixels. ABI stays 1 with additive identity exports; safe DLL load/null checks pass.

Every requested client-local physical texel maps to desktop, output-relative, frame, Qt logical pixel centre, framebuffer, source/target/later-live texture and native-host snapshot coordinates. It uses measured complete-client/host extents and DPR/padding; top-left origin, no vertical inversion, half-open bounds, subresource 0 and native Map.RowPitch are explicit. No coordinate is cropped, rounded back from Qt or converted through gamma/alpha. The companion JSON records all actual conversion rows and separate identity evidence.

## New Directory controls and failures

All new controls retain 350 ms motion, 240 ms target transfer, no prepared target, zero configured hold/delay, general layout/icon repairs, fresh observer gates and full client comparisons. They enable endpoint identity probing, passive input trace, F24 witness, after-input pixels and explicit activation profiling. Diagnostic readback/observer work extends endpoint residence and is excluded from a claim of uninterrupted motion.

| Run | Classification | Directions | Fresh PASS / FAIL | Pixel comparisons | Input PASS / FAIL | Raw result SHA-256 |
| --- | --- | ---: | --- | ---: | --- | --- |
| directory run1 | Argument failure before launch | 0 | 0 / 0 | 0 | 0 / 0 | No normal result |
| native_gpu_probe_contract_directory_20261008_run2 | FAIL | 0 | 4 / 0 | 4 | 0 / 0 | `65ab8d9360081f6044d6b8140464b2a66a41263fb52a8a6a21bd4b0ce8b8c682` |
| native_gpu_probe_contract_directory_20261008_run3 | ENDPOINT RUN COMPLETE; CANDIDATE UNQUALIFIED | 2 | 14 / 0 | 12 | 2 / 0 | `2f14cdb7b85779bb95f0c48172daf0c0f675618a0a22422d257de1dfb8a2405c` |
| native_gpu_probe_contract_directory_20261008_run4 | FAIL | 0 | 1 / 0 | 0 | 0 / 0 | `2dd0a901f11f5597550b6c5fd293c06c0d5097c013c0e98909d879c86477fbdc` |
| native_gpu_probe_contract_directory_20261008_run5 | FAIL | 0 | 1 / 0 | 0 | 0 / 0 | `fc3ca3e5cdd948d6225fda7bf28ecfb408ea6224694d6138a82992141a7bdd92` |

Each failed raw result and prelaunch log is retained by hash. Run2 rejects the unchanged target deadline after four exact source comparisons. Runs4/5 reject the owned source-band visibility check before motion. The expected band is sampled inside that API after input lock; preceding state logs are before lock. Recorded pre-lock foreground false is correlation only. Without contemporaneous expected-entry/actual-exit band values or post-batch band proof, these rejections do not establish an underlying band cause. They provide no readiness, target/live or input result. Marker-format output finalized within run2's application lifecycle, but precise execution/readiness overlap and causal contention are unproved. The only completed directions, sample counts and equality claims are the explicit measured rows below.

| Run / cycle | Complete client target/live differences before / after input | Probe samples | Target ↔ submitted / target ↔ live / desktop different samples | Revision source / target / live |
| --- | --- | ---: | --- | --- |
| native_gpu_probe_contract_directory_20261008_run3 / 0 | 0 / 0 | 16 | 0 / 0 / 0 | 1 / 2 / 3 |
| native_gpu_probe_contract_directory_20261008_run3 / 1 | 0 / 0 | 40 | 0 / 0 / 0 | 4 / 5 / 6 |

The former 63-pixel result remains a measured historical failure. Exact current observations do not retrospectively validate its submitted samples or prove a universal margin cure. Bounded source/submitted/target/live RGBA and desktop values stay in ignored per-cycle files; public records include only their hashes, sample counts, ordinal identities, coordinates and equality statistics. A margin that still differs with matching transparent source/target/submitted/live requires fresh controlled-backdrop evidence before assigning a cause.

## Focus, activation, input and timing

The companion JSON separates command receipt, guard release, native foreground/focus/active ownership, Qt application/window active snapshots, F24 posting/native/Qt/QML acceptance/release, focus disposal and witness cleanup for each accepted direction. It retains native readiness/API boundaries separately for rejected directions. These are disposable posted-key/GUI/QPC observations, including Python profiling and collector work, not human input or physical scanout.

| Run / cycle / direction | Guard → post ms | Post → native ms | Native → Qt ms | Qt → QML ms | Guard → QML ms | Witness |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| native_gpu_probe_contract_directory_20261008_run3 / 0 / maximize | 147.977 | 193.859 | 76.371 | 0.320 | 418.527 | PASS |
| native_gpu_probe_contract_directory_20261008_run3 / 1 / restore | 9.600 | 217.107 | 14.310 | 0.114 | 241.130 | PASS |

Terminal PASS follows consumed press/release and error-free owned focus disposal with deleteLater scheduling; it does not directly witness deferred QObject destruction. Passive trace cleanup records are preserved. Exact native focus alone is not accepted as proof of actual QML delivery or populated repeated reliability.

## Provenance, validation and release boundary

Initial corrected DLL is `1e185a8b7f35aeb62748425830e4a8775d0441d9e6228015d41b2bd61cd5e1da`. The later independently rebuilt verified DLL is `87cd33015bb44818a6a9ff4f73b2b8289ee2cf14dc841021002782c6c8bc24d6`; its successful `/W4` native-source/build-script hashes match before/after and its corresponding run startup hashes. This proves the named native source/DLL compile provenance, not a clean complete application build. Run-startup source equality across this set is `True`; each manifest is retained. Recovery checkpoint `5e625cc2fa854f056b2b846a75bc0679319acc8d` and all earlier report/result bytes remain unchanged.

Safe aggregate validation covers 16 complete-client comparisons, 20 accepted fresh gates, 16 complete region totals and 28 provenance checks. Privacy scanning excludes user paths, native handles and private sampled colors; ordinal resource/revision IDs are deliberately public identity evidence. All observed protected-original hashes remain unchanged; installed fallback executable hash is `8d461b679b4d578cfb6be6de259ab2e183e62a6d9f1eb944a69527befc8c0fa3`.

The focused safe suite passes 523 tests with one explicit deselection in 24.39 seconds, zero failure/error and no source/test hash drift. Modified Python diagnostics compile; the independently verified DLL preserves ABI 1 and passes five typed null rejection calls without HWND/device/WebEngine. The synthetic marker/runtime checks remain separate from these sandbox-safe checks.

Real native marker and disposable Qt desktop measurements were executed outside sandbox. Safe file/hash/contract/conservation checks are separate. No new installed WebEngine/PDF, physical mixed-DPI, complete native lifecycle, reduced motion, continuous-motion or packaging claim is made. Productivity cold restore and repeated populated input remain open until their separately recorded current-code controls. All new temporary/build/log/report output remains on Y:. No production package/data, deadline/duration, fallback, worktree or stash mutation. **Not yet accepted by Cory.**
