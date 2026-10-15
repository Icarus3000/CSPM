# Workspace usage control

This workspace has a model-free allowance reader, a conservative work guard,
private durable checkpoints, and an optional external systemd user timer.
The current IDE client does **not** have a verified supported external resume
and idle-ownership interface. Automatic assistant resumption and automatic
interruption are unavailable. The agent follows the persistent pause rules in
`AGENTS.md`; the monitor cannot force the running assistant to obey them.

## Verified capabilities

The installed client identifies as `codex_vscode`; local CLI version is
`codex-cli 0.155.1`. The documented stdio app-server exchange
`initialize`, `initialized`, `account/rateLimits/read` successfully returns
both 300-minute and 10,080-minute account windows outside the sandbox. No model
turn is needed. The reader starts a temporary **account-only** process; it
never loads a thread, starts a turn, consumes reset credits, or reads auth files.

The sandbox blocks the reader's required access/networking. A failed read
returns unavailable and refuses expensive work. Outside-sandbox execution is
governed by the normal approval mechanism. Nothing bypasses authentication,
billing, rate limits, approvals or sandbox policy.

Official interfaces and their limits were checked on October 14, 2026 EDT:

- [App-server account and thread interfaces](https://learn.chatgpt.com/docs/app-server)
  document allowance reads and thread resume. Thread resume requires ownership
  by the controlling application; it is not proof that this IDE's private
  conversation can safely be driven externally.
- [Developer commands](https://learn.chatgpt.com/docs/developer-commands)
  document `codex queue` and `codex resume`. CLI help confirms they are installed.
  `codex app-server daemon version` reports the shared control socket absent.
  No supported endpoint to submit to or authoritatively inspect ownership of
  this private IDE conversation has been established. Neither command is used.
- [Scheduled tasks](https://learn.chatgpt.com/docs/automations?surface=app)
  describe app/web scheduling. This tool session exposes no scheduler interface
  that can safely resume this local IDE conversation after checking allowances.
- [Persistent instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
  establish root `AGENTS.md` as the supported workspace instruction mechanism.

The local user systemd manager is running. Its timer can read allowance while
the assistant is inactive without model turns. It does not become an IDE
resumer just because a reset time is known. No private socket probing, second
thread owner, synthetic input, UI clicking, repeated inference, or assistant
sleep loop is used.

## Inspect and operate

From the repository root:

```bash
python3 scripts/workspace_usage.py check
python3 scripts/workspace_usage.py status
python3 scripts/workspace_usage.py checkpoint --notes /path/to/private-task-notes.json
python3 scripts/workspace_usage.py checkpoint --pause
python3 scripts/workspace_usage.py watch-once
```

`check` always requests a fresh read. Exit 0 permits work under the policy;
exit 75 means stop/checkpoint. It stops at 15% in **either** account window,
on unavailable/stale/malformed data, or if an estimated batch would touch the
reserve. Without a defensible estimate it pauses early below 25%. Use
`--batch-budget-percent N` only for a defensible approximate forecast, never as
an exact token count. `--context-remaining-percent N` accepts an actually
reported context value separately; no context value is inferred from account
allowance. The client exposes no reliable context-capacity read to this script.
Agents must checkpoint proactively before context compaction or pressure.

`status` is explicitly saved data and reports its age. A failed live read keeps
the last successful observation with its original timestamp and a cached-only
warning; that snapshot never authorizes work or resumption. The reader rejects
unexpected provider window durations rather than calling them five-hour/week.
It does not estimate reset times from durations or invent an exact token count.

Private notes require these JSON fields (strings or lists as appropriate):

```json
{
  "objective": "Original objective and accepted additions",
  "constraints": ["All user constraints and authorizations"],
  "completed": ["Changes, branches and commits"],
  "validation": ["Checks and outcomes, including environment limits"],
  "unresolved": ["Problems and evidence still needed"],
  "active_tools": ["Exact processes/session IDs; safe settlement steps"],
  "child_agents": ["Agent task, state and handoff"],
  "next_steps": ["Exact next commands"]
}
```

Keep these notes current during unattended work. Credentials, private tokens,
authentication responses, environment dumps and raw provider errors must never
be supplied. The guard allowlists numerical allowance fields and generic
diagnostic codes. Checkpoints inventory branch/commit/upstream/worktree identity,
changed/untracked paths and file hashes without copying diffs or auth contents.
The original uncommitted files remain in place; the checkpoint manifest is not
a file backup. It performs no reset, stash, clean, checkout or commit.

All runtime files are ignored by Git under `.workspace-usage/`:

- `task-notes.json`: maintained objectives, constraints and next steps.
- `latest-checkpoint.json`, `checkpoints/*.json`: full recovery snapshots.
- `observation.json`, `last-successful-observation.json`, `decision.json`:
  current/cached allowance, observation timestamps, policy decisions.
- `pause-request.json`: advisory request to settle and checkpoint.
- `schedule.json`, `control.lock`: bounded retry state and kernel file lock.

Checkpoints store UTC plus America/Toronto timestamps and the actual reported
five-hour and weekly resets. A pause captures the **pause-time** five-hour
reset +120 seconds as the earliest resume gate; a subsequent new-cycle reset
never moves that stored gate. Missing reset data stays null. A monitor-created
recovery checkpoint is labelled as requiring live agent/tool settlement; the
monitor cannot discover or terminate the agent's private tool sessions.

## External monitor and removal

```bash
python3 scripts/workspace_usage.py install-monitor
systemctl --user status cspm-usage-monitor.timer
systemctl --user cat cspm-usage-monitor.service cspm-usage-monitor.timer
journalctl --user -u cspm-usage-monitor.service --since today
python3 scripts/workspace_usage.py disable-monitor
python3 scripts/workspace_usage.py remove-monitor
```

Installation writes two clearly named user units under
`~/.config/systemd/user/`. It requires governed outside-sandbox access. It is
idempotent and preserves differing existing units. Every five minutes the timer
runs one bounded process, with no model turn. It survives assistant inactivity
and user-manager restarts. The user manager must remain running; logout without
lingering and machine shutdown stop monitoring. Login starts checks again.
No system service or lingering is silently enabled.

For a paused checkpoint, checks run no earlier than its stored UTC gate, with
bounded exponential backoff (60 seconds to one hour, at most 12 checks). Actual
systemd polling can make checks later than the requested time. Weekly exhaustion
also defers to the reported weekly reset +120 seconds when available. Retries
and next-check timestamps persist across restarts. Duplicate ticks serialize
on a kernel lock. Full fresh primary allowance, weekly reserve, pause-time gate,
and verified idle ownership are tested independently. Ownership stays unknown
for this client, so the timer never resumes it. Retries stop visibly at
`retry_exhausted`; a new agent checkpoint explicitly re-arms them.

Set `enabled` to false in `usage-control.json` to stop reads as well. Disabling
or removing units preserves all checkpoints. Remove generated state separately
only after reviewing/backing it up; deleting source/config is not necessary to
disable automation. Capability flags cannot enable automatic resume: the CLI
rejects them and no resume executor exists.

## Supported manual resumption

1. Reopen **this workspace and this conversation in the IDE**. Do not start a
   second CLI against it. Read `.workspace-usage/latest-checkpoint.json`.
2. Check its actual `earliest_resume_toronto` / `earliest_resume_utc`. If unknown,
   obtain a fresh supported report; never guess a reset. For usage pauses, wait
   through the recorded gate.
3. Run `python3 scripts/workspace_usage.py check` outside the sandbox as normally
   governed. For resumption after a usage pause require the reported five-hour
   remaining allowance to be 100% and weekly above 15%, with fresh timestamps.
4. Verify no competing agent owns the workspace, review preserved files/tool
   state, and send: “Read the latest usage checkpoint, verify live allowance and
   continue its original objective and constraints.” The IDE remains sole owner.
5. Refresh task notes and write an ordinary checkpoint before the next batch.

## Verification

```bash
python3 -m unittest tests.test_usage_allowance tests.test_usage_workspace -v
python3 -m py_compile scripts/workspace_usage.py scripts/usage_control/*.py
git diff --check
```

The synthetic suite uses a controllable clock and fake account servers; it
does not exhaust account allowance. It covers reserve/projected reserve,
unknown batch size, stale/unavailable/malformed data, separate context capacity,
weekly exhaustion, full primary restoration, exact reset +120 seconds,
duplicate locks/triggers, active/unknown ownership, retry limits, crash/restart
state recovery, atomic checkpoints and preserving dirty work. Live verification
reads only the account endpoint. No WebEngine is required for this subsystem.
