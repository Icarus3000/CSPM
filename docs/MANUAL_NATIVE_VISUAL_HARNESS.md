# Disposable manual native motion fixture

This development-only diagnostic mode reuses the current native GPU transaction
in `scripts/diagnostics/native_gpu_transition_spike.py`. It does not integrate
the DLL into ordinary CSPM or change its selector. The recovered experimental
checkpoint is `d4289aa5cc37d3f4b4ea5086c9a8380d08e5a1b5`; preserve that branch
and keep this harness on a separate local setup branch. Do not push or install it.

Build using the existing governed command:

```powershell
.\scripts\build_cleanroom_native.ps1 -OutputName cspm_cleanroom_manual_visual.dll
```

Launch from this worktree's isolated Python environment, using a fresh audit
label every time:

```powershell
.\.venv\Scripts\python.exe scripts/diagnostics/native_gpu_transition_spike.py `
  --manual --audit-label manual_native_visual_unique `
  --bridge-dll cspm_cleanroom_manual_visual.dll --workspace time-entry `
  --restored-size 960 650 --gui-delay-ms 0 --duration-ms 350 --blend-start-ms 240 `
  --intrinsic-only --single-owner-source --native-created-source-band `
  --render-target-import --layout-repair --activation-repair
```

The command refuses collectors, profiling, prepared targets, changed timings,
reduced-motion requests and missing/out-of-scope DLLs. It copies only repository
templates and seeds three explicitly synthetic clients, matters and time entries.
All settings, data, cache, exports and machine identity are redirected below the
unique audit folder. No master/cloud directory is configured. A process-local
Python I/O guard refuses outside writes, outside user-profile reads, registry
mutations, external actions and sockets. The only permitted Python child command
is the existing crash-isolated briefing worker, with verified synthetic request,
data and result paths inside the audit directory; its discard output device is
also permitted. Qt WebEngine storage is explicitly
redirected and uses memory cache/no persistent cookies. This is a scoped
development fixture, not an operating-system security sandbox or production app.

Only an ignored disposable QML copy intercepts the ordinary maximize/restore
control, after its existing command guards. Other Professional transition entry
paths reject in this copy. The native C++ implementation, production QML files,
350 ms duration, 240 ms target deadline, 100 ms slot gate, source-band ownership,
capture, input locks and bounded cleanup remain unchanged. There is no production
fallback and no A/B control. Successful native transitions return to manual-ready
state; no automatic cycles or unattended assessment deadline are scheduled.

The window is labelled **CSPM NATIVE MOTION VISUAL TEST — DISPOSABLE**. A separate
small status panel shows the requested/used engine, source and DLL hashes,
direction, source preparation, target import, rejection and input restoration.
Presentation-slot returns are not traced: the unchanged native gate is enforced,
but passing compile/load or a returned status is not independently observed
presentation proof. This limitation is explicitly displayed. GUI status updates
and the synthetic label add diagnostic overhead; this run cannot qualify timing.

A native rejection performs the existing bounded cleanup and becomes terminal:
the enabled live fixture and its rejection status remain visible; no retry or
production animation follows. Close using the custom window X or **Close
disposable fixture** in the status panel. Processes/resources are owned by this
fixture. Logs, synthetic workbooks and hashes are retained in the ignored audit
directory for review; no broad deletion or termination of other CSPM processes.

Before a real launch run focused manual-selector/native contracts, Python
compilation, governed bridge build/load, complete-diff review and the repository
privacy scanner on only the harness source/docs/tests. `manual_launch.json`
records actual arguments, redirected paths, Git/source hashes and DLL provenance;
`manual_status.json` records the compact status; native events retain failures.

Cory should maximize/restore five times and judge prompt onset, continuous flow,
restore quality, pause/restart/change of gear, visible content replacement,
title/glyph/control stability, final pixel correction, consistency, and similarity
to Fedora KDE Plasma and the accepted CSPM opening/closing. Manual visual judgment
does not close the existing collector-free readiness, Home pixel, physical input,
continuous handoff, lifecycle/WebEngine or mixed-DPI qualification gaps.
