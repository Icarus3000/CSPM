# Physical qualification continuation — 2026-10-04

The observer now distinguishes fresh DXGI desktop raster deliveries from cached results and pointer-only updates. Exact same-swapchain revision witnesses additionally test the intended native representation. The complete cold candidate remains **unqualified**; every failed predecessor is retained.

Full counts, mismatch histograms, named regions, alignment/color diagnostics, geometry, source/DLL provenance and relative timing chains are in `CLEANROOM_PHYSICAL_QUALIFICATION_RESULTS_2026-10-04.json`. Raw captures, profiles and logs remain ignored locally; no private screenshot is published.

| Run | Status | Internal directions | Fresh gates pass/fail | Required source / target comparisons |
| --- | --- | ---: | --- | --- |
| `native_gpu_fresh_cold_directory_20261004_run1` | FAIL | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_directory_20261004_run2` | FAIL | 1 | 8 / 0 | source [84, 0]; target [0] |
| `native_gpu_fresh_cold_home_20261004_run1` | FAIL | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_home_20261004_run2` | FAIL | 2 | 10 / 0 | source [0, 0]; target [0, 0] |
| `native_gpu_fresh_cold_invoice_20261004_run1` | FAIL | 0 | 1 / 0 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_invoice_20261004_run2` | FAIL | 0 | 0 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_invoice_20261004_run3` | FAIL | 0 | 0 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_productivity_20261004_run1` | FAIL | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_productivity_20261004_run2` | FAIL | 0 | 3 / 0 | source [0]; target unmeasured |
| `native_gpu_fresh_cold_productivity_quiet_20261004_run1` | FAIL | 0 | 0 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_productivity_quiet_20261004_run2` | FAIL | 0 | 1 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_productivity_quiet_restore_20261004_run1` | FAIL | 0 | 0 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_productivity_quiet_restore_20261004_run2` | FAIL | 0 | 1 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_productivity_restore_20261004_run1` | FAIL | 0 | 3 / 0 | source [0]; target unmeasured |
| `native_gpu_fresh_cold_time_20261004_run1` | FAIL | 4 | 20 / 0 | source [0, 0]; target [0] |
| `native_gpu_fresh_cold_time_20261004_run2` | FAIL | 0 | 1 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_time_20261004_run3` | FAIL | 0 | 1 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_cold_time_20261004_run4` | FAIL | 4 | 20 / 0 | source [0, 0, 0, 0]; target [0, 0, 0, 0] |
| `native_gpu_fresh_source_directory_20261004_run1` | FAIL | 1 | 4 / 0 | source [0]; target unmeasured |
| `native_gpu_fresh_source_invoice_20261004_run1` | FAILED BEFORE NORMAL RESULT | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_fresh_source_invoice_20261004_run2` | FAILED BEFORE NORMAL RESULT | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_fresh_source_invoice_20261004_run3` | FAIL | 1 | 4 / 0 | source [64]; target unmeasured |
| `native_gpu_fresh_source_invoice_20261004_run4` | FAIL | 1 | 4 / 0 | source [54]; target unmeasured |
| `native_gpu_fresh_source_time_20261004_run1` | FAIL | 0 | 1 / 1 | source unmeasured; target unmeasured |
| `native_gpu_fresh_source_time_20261004_run2` | FAIL | 1 | 4 / 0 | source [0]; target unmeasured |
| `native_gpu_restore_publication_costs_20261004_run1` | LAYOUT CONTROL; NOT CANDIDATE | 2 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_source_diagnosis_time_20261004_run1` | FAILED BEFORE NORMAL RESULT | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_source_diagnosis_time_20261004_run2` | FAILED BEFORE NORMAL RESULT | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_source_diagnosis_time_20261004_run3` | FAILED BEFORE NORMAL RESULT | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_source_diagnosis_time_20261004_run4` | FAILED BEFORE NORMAL RESULT | 0 | 0 / 0 | source unmeasured; target unmeasured |
| `native_gpu_source_diagnosis_time_20261004_run5` | FAIL | 1 | 0 / 0 | source [0]; target unmeasured |
| `native_gpu_source_markers_time_20261004_run1` | FAIL | 1 | 0 / 0 | source [0]; target unmeasured |
| `native_gpu_source_unlocked_time_20261004_run1` | FAIL | 1 | 0 / 0 | source [0]; target unmeasured |

Cold target readiness and later observation remain separate measured boundaries:

| Cold run / cycle | Direction | Geometry commit ms | Render-callback target import after native start ms | Fresh endpoint / live desktop observation after native start ms | Input-restored GUI observation after command ms |
| --- | --- | ---: | ---: | --- | ---: |
| `native_gpu_fresh_cold_directory_20261004_run2` / 0 | maximize | 119.245 | 237.913 | 459.816 / 524.581 | 1313.363 |
| `native_gpu_fresh_cold_home_20261004_run2` / 0 | maximize | 68.975 | 161.702 | 463.619 / 532.341 | 900.756 |
| `native_gpu_fresh_cold_home_20261004_run2` / 1 | restore | 60.587 | 139.61 | 444.734 / 533.131 | 893.972 |
| `native_gpu_fresh_cold_time_20261004_run1` / 0 | maximize | 84.288 | 191.0 | 458.245 / 536.057 | 955.359 |
| `native_gpu_fresh_cold_time_20261004_run1` / 1 | restore | 83.996 | 157.974 | 421.011 / 473.65 | 787.879 |
| `native_gpu_fresh_cold_time_20261004_run1` / 2 | maximize | 81.857 | 129.017 | 428.719 / 488.574 | 718.592 |
| `native_gpu_fresh_cold_time_20261004_run1` / 3 | restore | 65.041 | 127.678 | 435.982 / 490.253 | 797.032 |
| `native_gpu_fresh_cold_time_20261004_run4` / 0 | maximize | 88.553 | 182.755 | 457.352 / 529.489 | 937.906 |
| `native_gpu_fresh_cold_time_20261004_run4` / 1 | restore | 55.338 | 124.376 | 416.758 / 503.083 | 802.66 |
| `native_gpu_fresh_cold_time_20261004_run4` / 2 | maximize | 61.584 | 148.15 | 446.435 / 502.096 | 751.007 |
| `native_gpu_fresh_cold_time_20261004_run4` / 3 | restore | 72.672 | 148.982 | 436.411 / 475.851 | 761.515 |

Source overlap comparisons retain every mismatching pixel. The recurring sixteen differences fall at the four rounded content corners: rows `8, 10, 11, 15, 540, 544, 545, 547` and columns `8, 10, 11, 15, 760, 764, 765, 767`, two differences at each listed row/column in the small Time Entry control. Stacking partially transparent source corners is a working explanation. Exact hidden-source equality and a deliberate native-removal difference are separate controls; they do not authorize ignoring those corner pixels. **Cory remains the authority for every nonzero visual difference.**

The first fresh source run fails its witness despite newly delivered raster frames: its marker occupied the taskbar band while the native host was below the live host in observed Z-order. The source-only control chooses an observable margin outside its actual source; cold qualification must keep the witness outside both true endpoints. A native `HWND_TOP` ordering trial has passing samples, but later witness failures remain failures and do not certify universal visibility.

Later fixture startup explicitly requests activation. The final sampler brackets the observed foreground HWND, visibility, client rectangle and state; the app can remain observable above another foreground window. It never treats activation API success as visible-frame proof. Earlier Home, Directory and Productivity acquisition crops exceeded the selected output; the first invoice fixture also produced inconsistent content/client geometry. These preserved setup failures do not measure the engine's source fidelity or restore readiness. The foreground Client Directory source control subsequently supplies a fresh source witness and exact hidden-source pixels, while its nonzero overlap remains a recorded failure.

The first cold Time Entry run completed four internal directions and twenty passing fresh observations, then failed deferred spatial analysis because source regions were reused for a differently sized target. Its incomplete analysis and cleanup timeout remain failed evidence. Root retained the raw result and normally closed only its owned fixture. Per-cycle target regions and bounded exception cleanup were corrected before follow-up runs.

The restored target now adopts normal visibility padding before host-envelope and canvas geometry, then publishes its complete target metrics. The earlier instrumented layout-only restore/maximize control observes normal restored client extent `1122×782` for `1100×760` content. Restore width/height propagation is `12/10 ms`, padding `1 ms`, metrics publication `74 ms`; maximize is `11/11 ms`, padding `2 ms`, publication `62 ms`. These perturbed CPU observations do not establish cold native readiness or a causal speed ratio.

All motion/delivery settings remain fixed at 350 ms native motion / 240 ms target-transfer deadline; qualifying cold configurations have zero prepared target, zero configured endpoint hold and zero intentional GUI delay. A fresh-observer wait is measurement overhead and can leave a static endpoint visible while qualification proceeds. No passing endpoint comparison here proves uninterrupted handoff or the requested threefold speed gain.

Validation split: this report's collector performs **sandbox-safe JSON, hash and privacy checks only**. Root's actual desktop/Qt runs occur **outside sandbox** with disposable settings/workbooks and protected-original manifests. WebEngine evidence is the existing-preview HTML load event only where recorded. New PDF, installed-package, physical mixed-DPI, complete lifecycle and owner acceptance gates remain open. Production and the installed package are unchanged.

Final scoped findings: the two fresh Time Entry source/live-hidden controls and the foreground Directory source control expose the earlier large absent-host difference pattern. New Time Entry/Home cold endpoint comparisons are exact, but every sixteen-pixel overlap remains failed. The cold Directory's additional eighty-four source differences lie only in client margin `[1111,644,1122,654]`. Existing-preview Chromium HTML load succeeds; fresh invoice source controls have sixty-four/fifty-four margin differences at `[1111,548,1122,557]` / `[1111,550,1122,557]`, with exact header/body pixels and sixteen additional overlap corners. Full-client equality still fails. In the last invoice control, the cursor stays at `[2909,473]` on another monitor across baseline and hidden-source observation; it is not inside the recorded mismatch. Backdrop/alpha causality remains unknown, and no margin is removed from comparison.

Matched instrumented Productivity uses the same populated workspace with no prepared target, intentional GUI delay or endpoint hold. Maximize/restore width propagation is 15/13 ms, height 12/5 ms, complete commit 119.28/157.12 ms, metrics publication 63/119 ms. First-target Qt stages report polish 26/40 ms, composite sync 28/26 ms, render 66/74 ms (export/import included). Native export occupies 10.44/15.64 ms and finishes 237.16/280.23 ms after the GUI native-start notification; rejected imports return at 246.60/303.92 ms after that notification. API/queued CPU observations do not establish GPU completion or scanout, and these are not a matched causal comparison against the older 389.45 ms restore. Correct restored padding does not resolve both-direction readiness. The later quiet attempts fail the observable witness and cannot supply readiness measurements.

All 33 retained October 4 runs are classified: 26 failures, six pre-result fixture failures and one layout-only control. There are 86 successful fresh-frame observations and nine bounded rejected observation gates. Six pre-result failures include the preserved argument-splat and duplicate-launch/single-instance controls. The public aggregate preserves raw classifications and counts while independently retaining every nonzero overlap/endpoint difference as a failed qualification. No run is a complete qualified candidate.

Final sandbox-safe verification: 268 focused tests, diagnostic Python compilation, governed QML lint with existing warnings, MSVC `/W4` native/shader compilation, ABI/null rejection, aggregate conservation/privacy and whitespace checks. Actual Qt desktop and existing-preview Chromium HTML checks ran outside sandbox. Installed executable SHA256 remains `8D461B679B4D578CFB6BE6DE259AB2E183E62A6D9F1EB944A69527BEFC8C0FA3`; protected source workbooks/settings match their original hashes. No process from these fixtures remains active. P0/Cory acceptance, PDF/installed WebEngine, mixed-DPI desktop, motion continuity and input-to-photon timing remain unvalidated.

Decision: the requested observer/padding correction and remaining-difference localization are complete for this continuation. The conditional complete cold qualification is not entered because overlap, margin and populated restore gates fail. Production remains the safe default; no commit, installation or other visual-state work follows.

A final repeat encountered `OSError: [Errno 28] No space left on device` while writing fixtures to the Windows system temporary drive: 254 tests passed and 14 fixture setups errored. That raw log is retained. The identical 268-test selection passed in 16.44 seconds with a new ignored worktree-local `--basetemp`, without deleting any files or changing test/application behavior.
