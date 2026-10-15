# CSPM Agent Run Rules

These instructions are mandatory for AI agents working in this repository.

## Persistent workspace usage control

- Before expensive batches and about every five minutes during sustained work,
  run `python3 scripts/workspace_usage.py check` for fresh account allowances.
  The reader uses documented, read-only account RPCs; it never starts a model
  turn or attaches to the IDE conversation. If sandbox networking blocks it,
  use governed outside-sandbox execution. Keep approvals/authentication intact.
- Treat account allowance and conversation context as separate quantities.
  Never invent percentages, token counts, reset times or context headroom.
  Saved observations are historical: inspect their timestamp and age.
- At approximately 15% remaining in either five-hour or weekly allowance,
  stop launching work. Stop earlier when a batch might use the reserve; an
  unknown batch estimate stops work within ten percentage points of it.
  Exit 75 means stop and checkpoint; unavailable/stale data fails closed.
- Maintain private `.workspace-usage/task-notes.json` with the original
  objectives, all constraints, completed changes, validation, unresolved
  problems, tools/child agents, and exact next commands. Never record secrets.
  Before yielding for usage or low context, settle tools and child agents,
  update those notes, then run `python3 scripts/workspace_usage.py checkpoint
  --pause`. Ordinary recovery checkpoints omit `--pause`.
- Resume no earlier than the ACTUALLY REPORTED pause-time five-hour reset plus
  120 seconds, with a fresh fully restored five-hour allowance, weekly
  allowance above reserve, and verified idle ownership. UTC is for scheduling;
  America/Toronto is for readable times. Unknown reset/ownership blocks resume.
- This IDE currently has no established supported external resume/idle-owner
  interface. The systemd timer monitors only; it cannot interrupt or restart
  this assistant. Do not start another CLI owner, probe private IDE sockets,
  use repeated model calls, or sleep-loop as a scheduler. Resume manually in
  this same IDE conversation from `.workspace-usage/latest-checkpoint.json`.
  Do not claim automatic restart works. See `docs/WORKSPACE_USAGE_CONTROL.md`.

## Required Startup Reading

Before planning, diagnosing, editing, testing, or responding to an open-ended request
such as "proceed with next task", every AI agent must read these files in order:

1. `implementation_plan.md` — durable Professional/Console roadmap, Option 3 shell direction, and future Flutter/React Native migration intent.
2. `task.md` — current execution checklist and next available tasks.
3. `implementation.md` — latest implementation snapshot, completed work, validation notes, and manual checks still needed.
4. `docs/CSPM_Option_3_Interface_Rebuild_Brief.md` — canonical Option 3 interface rebuild brief.

## Current User-Directed Visual FX Priority (2026-08-20)

After the required startup reading, read
`docs/VISUAL_FX_AUDIT_AND_HANDOFF_2026-08-20.md` before beginning visual,
motion, or animation work. This is the user's current next-priority workstream.

- Begin with its P0 Professional maximize/restore manual acceptance gate.
- Do not move to another visual state machine until the user confirms the
  current maximize/restore path is clean in the real application.
- This user-directed priority supersedes the default manual-audit starting
  point below until that acceptance gate is complete.

Current manual audit priority:

- Open `docs/MANUAL_SCREEN_REPORT_AUDIT.md` after the startup reading above.
- Continue the screen-by-screen, window-by-window, report-by-report audit one
  problem at a time.
- Start with the New Matter Client dropdown / New Client handoff unless the user
  reports a more urgent defect.
- Do not move to the next problem until the user confirms the current problem is
  fixed in the real app.

If the user says "proceed with next task" or similar, continue from the next relevant
unchecked item in `task.md`, guided by `implementation_plan.md` and the Option 3 brief.
Do not infer a different long-term UI direction unless the user explicitly changes it.

## Planning Document Updates

After meaningful implementation work, update the durable planning files as needed:

- `task.md` for task status and newly discovered work.
- `implementation.md` for completed work, important files, validation, and manual checks.
- `implementation_plan.md` when the roadmap or architecture direction changes.
- `docs/CSPM_Option_3_Interface_Rebuild_Brief.md` only when the user explicitly revises the canonical brief.

## WebEngine Sandbox Policy

- Qt WebEngine runtime launch is known to fail in strict sandboxed shells with:
  - `FATAL: channel-pipe ... Access is denied (0x5)`
- Treat this as an environment restriction, not an app-logic failure.

## Required Test Split

- Inside sandbox:
  - run static/safe checks only (examples: `python -m py_compile`, QML parse checks, unit tests that do not open WebEngine).
  - do not use sandbox WebEngine launch outcomes as pass/fail signal for app behavior.
- Outside sandbox (or with explicit elevated permission):
  - run end-to-end startup validation that includes splash/WebEngine rendering.
  - run any smoke test that must instantiate `QtWebEngine` process runtime.

## Reporting Requirement

- When giving results, explicitly state:
  - which checks were sandbox-safe only,
  - which checks were executed outside sandbox for real WebEngine validation.

## Fallback Behavior for Debug Sessions

- If an agent cannot obtain outside-sandbox execution permission, it must:
  - continue with sandbox-safe validation,
  - clearly flag WebEngine e2e as "not validated in this environment",
  - provide the exact command the user can run outside sandbox.

## QMLLint Popup Policy

- Never call `qmllint.exe` directly from tools/automation.
- Keep VS Code qmllint path hard-disabled:
  - `.vscode/qmllint-noop.bat` (setting: `qtForPython.qmllint.path`)
  - and leave `.vscode/qmllint-wrapper.bat` as no-op for cached callers.
- For intentional lint runs, use:
  - `scripts/qmllint.ps1` (or repo root `qmllint.ps1`) only.
- After creating or repairing a venv, run:
  - `scripts/patch_qmllint_popup.ps1`
  to patch PySide `pyside_tool.py` so wrapper subprocess calls are console-bound and do not trigger popup-based version probes.

## Git Clean Policy

- NEVER run `git clean -fdx` without explicitly excluding ALL virtual environment directories using `-e ".venv*"`.
- A generic `git clean -fdx` is DANGEROUS and will aggressively delete the dynamic local virtual environment (e.g. `.venv_MACHINE_USER`) because it ignores `.gitignore` rules.
- If you need to clean untracked files, either use `git clean -fd` (which safely respects `.gitignore`) or ALWAYS use `git clean -fdx -e ".venv*"`.

## Diagnostic Log Review Policy

- The app is configured to write a fresh runtime log to logs/cspm.log on every launch (using mode='w').
- When a user reports a bug, crash, or unexpected behavior in the Python/QML layers, agents MUST invisibly read the contents of logs/cspm.log (using the iew_file or un_command tool) BEFORE proposing any solutions.
- Reviewing the runtime log first is mandatory to avoid guessing the source of backend/serialization/QML errors.
