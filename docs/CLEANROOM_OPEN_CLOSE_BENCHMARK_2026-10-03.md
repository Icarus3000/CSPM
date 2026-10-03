# Accepted opening/closing perceptual benchmark

The user accepts the existing opening and closing as perfectly flowing. Their
code is preserved and is a perceptual reference, not the competing engine's
architecture. No maximize/restore implementation source was studied for this
benchmark.

## Measurement

`scripts/diagnostics/open_close_benchmark.py` loads the unchanged primary source
on independently copied workbook/settings/master data, isolated machine identity,
and isolated logs. It invokes normal close after opening settles. It makes no
financial command, maximize/restore command, source edit, or persistent image.

The completed outside-sandbox Windows/Qt GPU run records 209 GUI-delivered
`frameSwapped` callbacks. Sampling is deliberately queued to the GUI thread;
these timestamps and current QML values are notification/property observations,
not render-thread sampling, compositor scanout, or physical mouse-to-photon.
Queued callbacks can bunch up after GUI blocking, so derivatives of these samples
cannot certify velocity, acceleration or jerk.

| Observation | Opening | Closing |
| --- | ---: | ---: |
| Release/command to first changed sample | 489.77 ms | 78.55 ms |
| Release/command to completion signal | 851.63 ms | 1215.92 ms |
| First changed sample to completion | 361.86 ms | 1137.37 ms |
| Motion-range sampled frame deliveries | 25 | 70 |
| Median delivery interval | 16.40 ms | 16.62 ms |
| Largest delivery interval | 28.00 ms | 38.92 ms |
| Intervals over 40 ms | 0 | 0 |

The opening release callback precedes its first sampled frame by about 476 ms;
this startup delay must not be interpreted as a 400 ms animation that actually
completed in 400 ms from command. Its first changed sampled scale is 0.123914,
then rises toward 1.0 over approximately 362 ms. The old `window.transition.open`
PERF marker ends before this bloom and is not complete visible timing. The
`post-settle-ready` phase arrives about 806.58 ms after release, about 45.05 ms
before bloom completion; this is a phase flag, not a tested physical input gate.

Closing contracts the existing surface about its centre. Its sampled scale
reaches 0.001 around 559 ms after command, then stays there while the remaining
accepted particle/burst presentation finishes. The native host rectangle stays
fixed throughout both sequences. The opening `startupCinematicSnapshotActive`
flag remains false in this standard startup route; the documented frozen-canvas
prestage is not assumed to have run.

## Perceptual lessons for the competing design

- Treat the composition as one surface. The accepted experience does not expose
  independent control/layout motion while its outer shape changes.
- Let speed diminish continuously into a matching endpoint. Opening's authored
  400 ms OutCubic bloom approaches identity without a separate settling motion.
- Keep expensive setup out of visible movement whenever evidence permits. Opening
  prepares geometry and startup content while the splash owns presentation. Its
  remaining measured startup blockage shows that authored timing alone is weak
  evidence of prompt response.
- Preserve continuity of the presented composition through handoff. Removing a
  transform at identity is a stronger perceptual premise than introducing a new
  movement at target readiness.
- Do not copy opening's title scaling or closing's decorative stages. Maximize/
  restore must keep title/glyph dimensions stable and complete much faster.
- Use the user's accepted perception as the reference, while measuring complete
  command-to-interactivity separately. Frame regularity and correct endpoints
  do not establish subjective smoothness.

These are lessons and observations, not a new manual visual acceptance claim.
No physical pixel, brightness, sharpness or glyph-bound comparison was done in
this narrow benchmark. No dedicated WebEngine HTML/PDF e2e was run.

## Reproduction and safety

```powershell
& 'Y:\Projects\__CSPM\.venv_OFFICENEW_Cory\Scripts\python.exe' `
  scripts/diagnostics/open_close_benchmark.py `
  --source-root 'Y:\Projects\__CSPM' `
  --audit-label open_close_benchmark_unique_label
```

Run from the experimental worktree, outside a WebEngine-restricting sandbox,
with the desktop slot reserved for this fixture. Do not launch concurrently with
other desktop measurement harnesses.

Evidence: ignored `logs/open_close_benchmark_20261003_run4/benchmark.json`,
`summary.json`, `protected_hashes.json`, and isolated runtime log. Local practice
workbook and authoritative settings hashes match before/after. The completed
run has no fixture failure and closes normally. Its first two starts were
harness failures from accidentally shadowing `QApplication.event`; only exact
diagnostic processes were stopped and their logs are retained. A corrected
third run completed but did not persist frame samples because normal application
quit preceded the diagnostic finish timer. A post-shutdown writer fixed that
diagnostic issue for run four. These earlier attempts are excluded from timing.

Sandbox-safe checks: diagnostic Python compilation. Outside sandbox: one retained
full-source desktop opening/closing observation run. Production source, installed
runtime, opening and closing are unchanged.
