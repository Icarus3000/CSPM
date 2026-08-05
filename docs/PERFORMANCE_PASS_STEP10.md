# Step 10 Performance Pass

This document records the measured startup and interaction hotspots after structural cleanup.

## Scope

- Startup splash and falling-window handoff.
- Sidebar navigation transitions.
- Master calendar loading and selection interactions.
- Detached-window open/close transitions.

## Instrumentation Added

- `src/qml/DetachedShellWindow.qml`
  - `window.transition.open`: starts in `startOpeningLaunchNow()`, ends in `transitionToSettled()`.
  - `window.transition.close`: starts in `transitionToClosing()`, ends in `finalizeCloseSequence()`.
- `src/qml/views/MainContent.qml`
  - `sidebar.nav.open` and `sidebar.nav.back`.
- `src/qml/views/TimeDocketView.qml`
  - `master.calendar.loadDeadlines`
  - `master.calendar.refreshEntries`
  - `master.calendar.selectDate`
- Shared helper:
  - `src/qml/standards/PerfTrace.js`

All markers log through existing startup logging as `[PERF] ... elapsedMs=...`.

## Baseline Hotspots (Measured)

From the user startup run on March 9, 2026:

1. Main component load before gate:
   - `_onMainComponentStatusChanged component Ready loadElapsedMs=2519`
2. Splash-visible to splash-complete timeline:
   - splash start around `3.213s`
   - splash fully gone around `15.144s`
3. First-pixel handoff is already fast:
   - `splash->first-pixel lag window: 0.185s`
4. Input readiness lag after first pixel:
   - `first-pixel->first-input latency: 4.400s`
5. Deferred backend boot:
   - `boot_backend complete [1.716s]`

Primary bottlenecks are component-loading + intentional splash/queue gating, not the splash-to-first-pixel handoff.

## Profiling Runbook

1. Run with startup tracing enabled:
   - PowerShell:
   - ``$env:CSPM_DOCKET_TRACE='1'; & .\.venv_OFFICENEW_Cory\Scripts\python.exe .\src\python\main.py``
2. Capture `[PERF]` lines and startup timing lines from console logs.
3. Exercise:
   - app startup,
   - one sidebar open/back cycle,
   - one master calendar load/select cycle,
   - one detached-window open/close cycle.
4. Compare elapsed metrics across 3 runs; optimize only metrics that are consistently slow.

## Optimization Rule

Do not change animation behavior unless profiling shows repeatable bottlenecks in measured markers. Avoid speculative changes without a metric delta.
