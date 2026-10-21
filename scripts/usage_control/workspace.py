"""Durable workspace state. No function here starts or resumes a model turn."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
try:
    import fcntl
except ImportError:  # Windows has byte-range locks instead of flock.
    fcntl = None
    import msvcrt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zoneinfo import ZoneInfo

UTC = timezone.utc
TORONTO = ZoneInfo("America/Toronto")


def stamp(now: datetime) -> dict:
    return {"utc": now.astimezone(UTC).isoformat(),
            "toronto": now.astimezone(TORONTO).isoformat()}


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    return result.astimezone(UTC)


def atomic_json(path: Path, data: dict) -> None:
    """Replace complete state atomically, including across process crashes."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


@contextmanager
def state_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(directory / "control.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("another_monitor_owns_state") from None
        yield
    finally:
        os.close(fd)


def _git(root: Path, *args: str) -> str:
    process = subprocess.run(["git", "-C", str(root), *args],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, errors="surrogateescape", timeout=20, check=False)
    if process.returncode:
        return "unavailable"
    return process.stdout.rstrip("\n")


def git_inventory(root: Path) -> dict:
    """Record identity and changed file hashes, never diffs or auth contents."""
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status == "unavailable":
        return {"status": "unavailable", "changes": None,
                "preservation": "Git inventory failed; existing work was not modified."}
    changes = []
    entries = status.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        mode, name = entry[:2], entry[3:]
        item = {"status": mode, "path": name}
        if "R" in mode or "C" in mode:
            if index < len(entries):
                item["previous_path"] = entries[index]
                index += 1
        path = root / name
        # Do not open credential files, even for hashing. Git status names only.
        sensitive = any(part.lower() in {".aws", ".ssh", ".codex", ".env"}
                        for part in Path(name).parts)
        sensitive = sensitive or path.name.lower().startswith(".env.")
        sensitive = sensitive or any(word in path.name.lower() for word in
                                      ("credential", "auth.json", "secret", ".pem", ".key"))
        if not sensitive and path.is_file() and not path.is_symlink():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            item["sha256"] = digest.hexdigest()
            item["bytes"] = path.stat().st_size
        else:
            item["content_recorded"] = False
        changes.append(item)
    return {"branch": _git(root, "branch", "--show-current"),
            "head": _git(root, "rev-parse", "HEAD"),
            "upstream": _git(root, "rev-parse", "--abbrev-ref", "@{upstream}"),
            "upstream_head": _git(root, "rev-parse", "@{upstream}"),
            "worktrees": _git(root, "worktree", "list", "--porcelain"),
            "changes": changes,
            "preservation": "Existing files remain in place; no reset, stash, clean, commit or checkout is performed. This manifest is not a backup of file contents."}


def resume_gate(checkpoint: dict, observation: dict, policy: dict,
                now: datetime, ownership: str, config: dict) -> dict:
    """Inspect future eligibility only. IDE fallback never executes a resume."""
    reasons = list(policy.get("resume_reasons", []))
    gate = checkpoint.get("earliest_resume_utc")
    if gate is None:
        reasons.append("pause_reset_unknown")
    else:
        try:
            if now < parse_time(gate):
                reasons.append("before_recorded_reset_plus_buffer")
        except (TypeError, ValueError):
            reasons.append("invalid_recorded_reset")
    if not policy.get("resume_allowed", False):
        reasons.append("fresh_allowance_not_resume_ready")
    if ownership != "verified_idle":
        reasons.append("active_owner" if ownership == "active" else "ownership_unverified")
    prerequisites_met = not reasons
    supported = config.get("automatic_resume_supported") is True
    enabled = config.get("automatic_resume_enabled") is True
    # This implementation has no resume executor. Even editing the capability
    # flags cannot cause a CLI owner to be launched against the IDE.
    if not supported:
        reasons.append("ide_resume_unsupported")
    if not enabled:
        reasons.append("automatic_resume_disabled")
    return {"prerequisites_met": prerequisites_met,
            "action": "manual_resume_ready" if prerequisites_met else "defer",
            "automatic_resume_executed": False,
            "reasons": list(dict.fromkeys(reasons))}


def next_check(state: dict, checkpoint: dict, observation: dict, policy: dict,
               now: datetime, config: dict, ownership: str = "unknown") -> dict:
    """One idempotent scheduler tick, with durable bounded retry/backoff."""
    state = dict(state)
    key = checkpoint["checkpoint_id"]
    if state.get("checkpoint_id") != key:
        state = {"checkpoint_id": key, "attempts": 0, "phase": "waiting"}
    if state.get("phase") == "retry_exhausted":
        return state
    due = state.get("next_check_utc")
    if due and now < parse_time(due):
        return state
    gate = checkpoint.get("earliest_resume_utc")
    if gate and now < parse_time(gate):
        state.update(phase="waiting_for_reset", next_check_utc=gate)
        return state
    result = resume_gate(checkpoint, observation, policy, now, ownership, config)
    attempts = state.get("attempts", 0) + 1
    state.update(attempts=attempts, last_check=stamp(now), eligibility=result)
    if attempts >= config["max_resume_checks"]:
        state.update(phase="retry_exhausted", next_check_utc=None)
    else:
        delay = min(config["retry_max_seconds"],
                    config["retry_initial_seconds"] * 2 ** min(attempts - 1, 20))
        weekly = observation.get("windows", {}).get("weekly", {})
        if "weekly_reserve_reached" in policy.get("resume_reasons", []):
            reset = weekly.get("reset_at_utc")
            if reset:
                delay = max(delay, (parse_time(reset) - now).total_seconds() + 120)
        state.update(phase="manual_ready" if result["prerequisites_met"] else "deferred",
                     next_check_utc=stamp(now + timedelta(seconds=delay))["utc"])
    return state


def make_checkpoint(root: Path, directory: Path, notes: dict, observation: dict,
                    policy: dict, now: datetime, config: dict, pause: bool = True) -> dict:
    required = ("objective", "constraints", "completed", "validation", "unresolved",
                "active_tools", "child_agents", "next_steps")
    if any(key not in notes for key in required):
        raise ValueError("Checkpoint notes must include: " + ", ".join(required))
    if set(notes) - set(required) - {"checkpoint_kind"}:
        raise ValueError("Checkpoint notes contain unsupported fields")
    created = stamp(now)
    checkpoint_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    gate = policy.get("resume_not_before_utc")
    # Gate is captured from actual reported pause-time reset, never recalculated
    # from a later allowance window. Unknown resets stay unknown.
    checkpoint = {"schema_version": 1, "checkpoint_id": checkpoint_id,
                  "workspace": str(root.resolve()),
                  "conversation_id": os.environ.get("CODEX_THREAD_ID"),
                  "client": config["client"], "created": created, **notes,
                  "git": git_inventory(root), "allowance": observation,
                  "policy": policy, "earliest_resume_utc": gate,
                  "earliest_resume_toronto": (stamp(parse_time(gate))["toronto"] if gate else None),
                  "ownership": "IDE client retains ownership; external idle state unverified",
                  "automatic_resume_supported": False,
                  "resume_required": pause,
                  "manual_resume": "Open this workspace and this conversation in the IDE. Read the latest checkpoint, run the live guard, and continue only after fresh allowances and the recorded time gate permit it."}
    atomic_json(directory / "checkpoints" / (checkpoint_id + ".json"), checkpoint)
    atomic_json(directory / "latest-checkpoint.json", checkpoint)
    atomic_json(directory / "schedule.json", {"checkpoint_id": checkpoint_id,
                "phase": "waiting" if pause else "monitoring", "attempts": 0,
                "next_check_utc": gate if pause else None})
    return checkpoint
