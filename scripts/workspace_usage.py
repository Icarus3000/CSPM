#!/usr/bin/env python3
"""Model-free allowance checks and private checkpoints for this workspace."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from usage_control.allowance import evaluate, read_live
from usage_control.workspace import (atomic_json, make_checkpoint, next_check,
                                     parse_time, read_json, stamp, state_lock)

ROOT = Path(__file__).resolve().parents[1]


def load_config(root: Path) -> tuple[dict, Path]:
    config = read_json(root / "usage-control.json")
    if config.get("automatic_resume_enabled") or config.get("automatic_resume_supported"):
        raise ValueError("This IDE adapter supports monitoring and manual resume only")
    if config.get("reset_buffer_seconds") != 120:
        raise ValueError("The required reset buffer is 120 seconds")
    state = (root / config["state_directory"]).resolve()
    if not state.is_relative_to(root.resolve()) or state == root.resolve():
        raise ValueError("State must be a private subdirectory of the workspace")
    return config, state


def get_observation(config: dict, now: datetime) -> dict:
    return read_live(config["account_command"], now,
                     timeout=config["account_timeout_seconds"])


def policy_for(observation: dict, now: datetime, config: dict, args) -> dict:
    return evaluate(observation, now,
                    reserve_percent=config["reserve_percent"],
                    max_age_seconds=config["max_observation_age_seconds"],
                    batch_budget_percent=getattr(args, "batch_budget_percent", None),
                    context_remaining_percent=getattr(args, "context_remaining_percent", None),
                    context_reserve_percent=config["context_reserve_percent"])


def save_observation(directory: Path, observation: dict, policy: dict, now: datetime):
    # Keep last successful observation explicitly cached; never present it as live.
    if observation.get("status") == "ok":
        atomic_json(directory / "last-successful-observation.json", observation)
    atomic_json(directory / "observation.json", observation)
    atomic_json(directory / "decision.json", {"checked": stamp(now), **policy})
    cached = directory / "last-successful-observation.json"
    if observation.get("status") != "ok" and cached.exists():
        previous = read_json(cached)
        age = (now - parse_time(previous["observed_at_utc"])).total_seconds()
        return {"cached_observation": previous, "cached_age_seconds": age,
                "cached_warning": "Historical only; cannot authorize work or resumption"}
    return {}


def checkpoint_notes(directory: Path, args) -> dict:
    supplied = getattr(args, "notes", None)
    if supplied:
        notes = read_json(Path(supplied))
        atomic_json(directory / "task-notes.json", notes)
        return notes
    return read_json(directory / "task-notes.json")


def run_once(args) -> int:
    root = args.root.resolve()
    config, directory = load_config(root)
    now = datetime.now(timezone.utc)
    if not config["enabled"]:
        print(json.dumps({"enabled": False, "automatic_resume_executed": False}))
        return 0
    with state_lock(directory):
        if args.command == "status":
            result = {"enabled": True, "automatic_resume_supported": False,
                      "limitation": config["limitation"]}
            for name in ("observation", "decision", "schedule"):
                path = directory / (name + ".json")
                if path.exists():
                    result[name] = read_json(path)
            saved = result.get("observation", {}).get("observed_at_utc")
            result["saved_data_only"] = True
            result["observation_age_seconds"] = ((now - parse_time(saved)).total_seconds()
                                                   if saved else None)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "watch-once":
            schedule = directory / "schedule.json"
            latest = directory / "latest-checkpoint.json"
            if latest.exists():
                checkpoint = read_json(latest)
                old_state = read_json(schedule) if schedule.exists() else {}
                if old_state.get("checkpoint_id") != checkpoint["checkpoint_id"]:
                    # Recover a crash after latest-checkpoint was promoted but
                    # before the separate scheduler state was replaced.
                    paused = checkpoint.get("resume_required", True)
                    atomic_json(schedule, {"checkpoint_id": checkpoint["checkpoint_id"],
                        "phase": "waiting" if paused else "monitoring", "attempts": 0,
                        "next_check_utc": checkpoint.get("earliest_resume_utc") if paused else None})
            if schedule.exists():
                state = read_json(schedule)
                if state.get("phase") == "retry_exhausted":
                    print(json.dumps({"action": "retry_exhausted", "automatic_resume_executed": False}))
                    return 0
                due = state.get("next_check_utc")
                if due and now < parse_time(due):
                    print(json.dumps({"action": "waiting", "next_check_utc": due}))
                    return 0
        observation = get_observation(config, now)
        policy = policy_for(observation, now, config, args)
        result = {"observation": observation, "policy": policy,
                  **save_observation(directory, observation, policy, now)}
        if args.command == "checkpoint":
            notes = checkpoint_notes(directory, args)
            checkpoint = make_checkpoint(root, directory, notes, observation, policy, now, config,
                                         pause=args.pause or policy["checkpoint_required"])
            result["checkpoint"] = str(directory / "latest-checkpoint.json")
            result["earliest_resume_utc"] = checkpoint["earliest_resume_utc"]
        elif args.command == "watch-once":
            latest = directory / "latest-checkpoint.json"
            schedule = directory / "schedule.json"
            if policy["checkpoint_required"]:
                atomic_json(directory / "pause-request.json", {
                    "requested": stamp(now), "reasons": policy["reasons"],
                    "instruction": "Stop new batches, settle tools and child agents, update task notes and checkpoint before yielding.",
                    "automatic_interrupt_supported": False})
                # Reuse the latest maintained task notes. A monitor cannot know
                # live tool/agent state; label this as a recovery checkpoint.
                if (not latest.exists() or not schedule.exists()
                        or not read_json(latest).get("resume_required")):
                    try:
                        notes = checkpoint_notes(directory, args)
                        notes["checkpoint_kind"] = "monitor_recovery_requires_agent_settlement"
                        make_checkpoint(root, directory, notes, observation, policy, now, config)
                    except FileNotFoundError:
                        result["checkpoint_notes_missing"] = True
            if (latest.exists() and schedule.exists()
                    and read_json(latest).get("resume_required")):
                checkpoint = read_json(latest)
                state = read_json(schedule)
                # No supported authoritative ownership query for the private IDE.
                state = next_check(state, checkpoint, observation, policy, now, config,
                                   ownership="unknown")
                atomic_json(schedule, state)
                result["schedule"] = state
        print(json.dumps(result, indent=2))
        return 0 if args.command in ("watch-once", "checkpoint") else (0 if policy["work_allowed"] else 75)


def unit_paths() -> tuple[Path, Path]:
    base = Path.home() / ".config/systemd/user"
    return base / "cspm-usage-monitor.service", base / "cspm-usage-monitor.timer"


def install_monitor(root: Path) -> int:
    config, _ = load_config(root)
    service, timer = unit_paths()
    service.parent.mkdir(parents=True, exist_ok=True)
    # systemd interprets percent specifiers and quoted strings itself.
    def quote(value: str) -> str:
        return '"' + value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"') + '"'
    if any(char in str(root) for char in "\n\r\0"):
        raise ValueError("Unsupported control character in workspace path")
    working_directory = str(root).replace("%", "%%")
    service_text = "\n".join([
        "[Unit]", "Description=CSPM read-only account allowance monitor (no model turns)",
        "[Service]", "Type=oneshot", "UMask=0077", "TimeoutStartSec=50",
        "WorkingDirectory=" + working_directory,
        "ExecStart=" + quote(sys.executable) + " " + quote(str(root / "scripts/workspace_usage.py"))
        + " --root " + quote(str(root)) + " watch-once", ""])
    timer_text = "\n".join([
        "[Unit]", "Description=Check CSPM allowance without starting an assistant",
        "[Timer]", "OnBootSec=2min", f"OnUnitInactiveSec={config['poll_seconds']}s",
        "AccuracySec=10s", "Unit=cspm-usage-monitor.service", "[Install]",
        "WantedBy=timers.target", ""])
    for path, content in ((service, service_text), (timer, timer_text)):
        if path.exists() and path.read_text() != content:
            legacy = service_text.replace("WorkingDirectory=" + working_directory,
                                          "WorkingDirectory=" + quote(str(root)))
            if path != service or path.read_text() != legacy:
                raise ValueError("Existing differing unit preserved: " + str(path))
    for path, content in ((service, service_text), (timer, timer_text)):
        path.write_text(content)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", timer.name], check=True)
    print(json.dumps({"installed": True, "service": str(service), "timer": str(timer),
                      "automatic_resume_supported": False,
                      "note": "Monitor only. No model calls, conversation attachment, or automatic interrupt. User systemd manager must be running."}, indent=2))
    return 0


def remove_monitor(remove: bool) -> int:
    service, timer = unit_paths()
    subprocess.run(["systemctl", "--user", "disable", "--now", timer.name], check=True)
    if remove:
        subprocess.run(["systemctl", "--user", "stop", service.name], check=True)
        for path in (service, timer):
            if path.exists():
                content = path.read_text()
                if "CSPM" not in content or "usage" not in content:
                    raise ValueError("Unrecognized unit preserved: " + str(path))
                path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print(json.dumps({"monitor_enabled": False, "units_removed": remove,
                      "checkpoints_preserved": True}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Live guard; exit 75 means stop/checkpoint")
    check.add_argument("--batch-budget-percent", type=float)
    check.add_argument("--context-remaining-percent", type=float)
    checkpoint = sub.add_parser("checkpoint", help="Refresh private durable checkpoint")
    checkpoint.add_argument("--notes", type=Path, help="Private structured task notes JSON")
    checkpoint.add_argument("--context-remaining-percent", type=float)
    checkpoint.add_argument("--pause", action="store_true", help="Capture pause-time reset and arm bounded eligibility checks")
    sub.add_parser("status", help="Read saved state only; timestamps may be stale")
    sub.add_parser("watch-once", help="One model-free monitor tick, bounded retry state")
    sub.add_parser("install-monitor", help="Install idempotent systemd USER monitor timer")
    sub.add_parser("disable-monitor", help="Stop periodic checks and keep checkpoints")
    sub.add_parser("remove-monitor", help="Remove user timer/service and keep checkpoints")
    args = parser.parse_args()
    try:
        if args.command == "install-monitor":
            return install_monitor(args.root.resolve())
        if args.command in ("disable-monitor", "remove-monitor"):
            return remove_monitor(args.command == "remove-monitor")
        return run_once(args)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        # Do not log subprocess output, private config, or exception strings.
        print(json.dumps({"status": "unavailable", "work_allowed": False,
                          "diagnostic": "Usage control failed; inspect configuration and state. No model turn was started."}))
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
