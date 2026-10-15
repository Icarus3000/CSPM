"""Read account quotas without starting a model turn, and evaluate a reserve.

The stable Codex app-server stdio protocol is documented at
https://learn.chatgpt.com/docs/app-server (Initialization; Rate limits).
Only initialize, initialized and account/rateLimits/read are sent. This process
does not attach to an IDE server or load/resume/start a conversation. No auth,
server messages, stderr, credits, plan names or account identifiers are retained.

``resume_allowed`` is a quota prerequisite, not permission to start an agent.
The caller must additionally enforce the *checkpoint's* recorded reset + 120s,
supported client ownership and an idempotent scheduler lock. A new observation's
next reset must never replace that recorded pause-time reset.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
import select
import subprocess
import time
from typing import Any
from zoneinfo import ZoneInfo


UTC = timezone.utc
TORONTO = ZoneInfo("America/Toronto")
SOURCE = "codex-account/rateLimits/read"
DEFAULT_COMMAND = ["/usr/local/bin/codex", "app-server"]
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("An aware datetime is required")
    return value.astimezone(UTC)


def _times(value: datetime) -> tuple[str, str]:
    value = _utc(value)
    return value.isoformat().replace("+00:00", "Z"), value.astimezone(TORONTO).isoformat()


def _number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _percent(value: Any) -> bool:
    return _number(value) and 0 <= value <= 100


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, TypeError, OverflowError):
        return None


def _base(now: datetime) -> dict:
    utc, toronto = _times(now)
    return {
        "schema_version": 1,
        "status": "ok",
        "source": SOURCE,
        "observed_at_utc": utc,
        "observed_at_toronto": toronto,
        "account_allowance": True,
        "context_capacity": False,
        "windows": {},
    }


def unavailable(now: datetime, code: str) -> dict:
    """Return a credential-free failure; callers must not add raw exceptions."""
    result = _base(now)
    result.update(status="unavailable", diagnostic_code=code)
    return result


def normalize_response(response: dict, now: datetime) -> dict:
    """Allowlist the current account bucket's two known quota windows.

    ``response`` is an account/rateLimits/read *result* (not the RPC envelope).
    An unfamiliar provider window is unavailable, never relabeled five-hour or
    weekly. Missing resets remain unknown; they are not inferred from duration.
    """
    if not isinstance(response, dict):
        return unavailable(now, "invalid_rate_limits_response")
    by_id = response.get("rateLimitsByLimitId")
    if isinstance(by_id, dict) and "codex" in by_id:
        bucket = by_id["codex"]
    else:
        bucket = response.get("rateLimits")
    if not isinstance(bucket, dict) or bucket.get("limitId") not in (None, "codex"):
        return unavailable(now, "missing_codex_allowance")

    windows: dict[str, dict] = {}
    for name in ("primary", "secondary"):
        window = bucket.get(name)
        if not isinstance(window, dict):
            return unavailable(now, "missing_quota_window")
        minutes, used = window.get("windowDurationMins"), window.get("usedPercent")
        if not _number(minutes) or minutes not in (300, 10080):
            return unavailable(now, "unsupported_quota_windows")
        key = "five_hour" if minutes == 300 else "weekly"
        if key in windows:
            return unavailable(now, "duplicate_quota_window")
        if not _percent(used):
            return unavailable(now, "invalid_usage_percentage")
        reset = window.get("resetsAt")
        reset_utc = reset_toronto = None
        if reset is not None:
            if not _number(reset) or reset <= 0:
                return unavailable(now, "invalid_reset_timestamp")
            try:
                reset_utc, reset_toronto = _times(datetime.fromtimestamp(reset, UTC))
            except (ValueError, OverflowError, OSError):
                return unavailable(now, "invalid_reset_timestamp")
        windows[key] = {
            "window_minutes": int(minutes),
            "used_percent": used,
            "remaining_percent": 100 - used,
            "reset_at_utc": reset_utc,
            "reset_at_toronto": reset_toronto,
        }
    if set(windows) != {"five_hour", "weekly"}:
        return unavailable(now, "missing_quota_window")
    result = _base(now)
    result["windows"] = windows
    # A reached-limit response cannot be overridden by apparently ample quotas.
    result["rate_limit_reached"] = bucket.get("rateLimitReachedType") is not None
    return result


class _ReadFailure(Exception):
    pass


def read_live(command: list[str], now: datetime, timeout: float = 25) -> dict:
    """Read fresh account quotas in an isolated, account-only stdio subprocess.

    No raw provider errors are returned. Binary os.read avoids TextIO buffering
    hiding a second complete JSON line while select reports no unread bytes.
    Timeouts cover the entire exchange and cleanup always settles this process.
    ``now`` is injected for deterministic testing and records observation start.
    """
    _utc(now)
    if not isinstance(command, list) or not command or not all(isinstance(arg, str) and arg for arg in command):
        return unavailable(now, "invalid_reader_command")
    if not _number(timeout) or timeout <= 0:
        return unavailable(now, "invalid_reader_timeout")
    process = None
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        assert process.stdin is not None and process.stdout is not None
        deadline = time.monotonic() + timeout
        buffer = bytearray()
        received = 0

        def send(message: dict) -> None:
            process.stdin.write((json.dumps(message, separators=(",", ":")) + "\n").encode())
            process.stdin.flush()

        def reply(request_id: int) -> dict:
            nonlocal received
            while True:
                while b"\n" in buffer:
                    line, _, remainder = buffer.partition(b"\n")
                    buffer[:] = remainder
                    if not line.strip():
                        continue
                    try:
                        message = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        raise _ReadFailure("invalid_rpc_response") from None
                    if not isinstance(message, dict):
                        raise _ReadFailure("invalid_rpc_response")
                    if message.get("id") != request_id:
                        # Notifications may precede responses; never persist them.
                        continue
                    if "error" in message:
                        raise _ReadFailure("account_rpc_unavailable")
                    if not isinstance(message.get("result"), dict):
                        raise _ReadFailure("invalid_rpc_response")
                    return message["result"]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _ReadFailure("account_read_timeout")
                ready, _, _ = select.select([process.stdout], [], [], remaining)
                if not ready:
                    raise _ReadFailure("account_read_timeout")
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    raise _ReadFailure("account_reader_closed")
                received += len(chunk)
                if received > _MAX_RESPONSE_BYTES:
                    raise _ReadFailure("account_response_too_large")
                buffer.extend(chunk)

        send({
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "cspm_usage_guard", "title": "CSPM Account Allowance Reader", "version": "1.0.0"}},
        })
        reply(1)
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "account/rateLimits/read"})
        return normalize_response(reply(2), now)
    except _ReadFailure as failure:
        return unavailable(now, str(failure))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return unavailable(now, "account_reader_unavailable")
    finally:
        if process is not None:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            if process.stdout is not None:
                process.stdout.close()


def evaluate(
    observation: dict,
    now: datetime,
    reserve_percent: float = 15,
    max_age_seconds: int = 120,
    batch_budget_percent: float | None = None,
    context_remaining_percent: float | None = None,
    context_reserve_percent: float = 15,
) -> dict:
    """Fail closed on unavailable/stale account data and protect both quotas.

    A batch budget is an approximate percentage estimate applied conservatively
    to both windows, not an exact token forecast. Unknown estimates stop new
    batches within ten percentage points of the reserve. Conversation context
    is independent; when actually reported low it requires a checkpoint too.
    """
    now = _utc(now)
    work_reasons: list[str] = []
    resume_reasons: list[str] = []
    age = None
    fresh = False
    gate_utc = gate_toronto = None
    settings_valid = (
        _percent(reserve_percent) and reserve_percent < 100
        and _number(max_age_seconds) and max_age_seconds >= 0
        and _percent(context_reserve_percent) and context_reserve_percent < 100
    )
    if not settings_valid:
        work_reasons.append("invalid_policy_configuration")

    if not isinstance(observation, dict) or observation.get("status") != "ok":
        work_reasons.append("account_allowance_unavailable")
    else:
        observed = _parse_time(observation.get("observed_at_utc"))
        if observed is None:
            work_reasons.append("observation_time_unknown")
        else:
            age = (now - observed).total_seconds()
            fresh = settings_valid and 0 <= age <= max_age_seconds
            if age < 0:
                work_reasons.append("observation_from_future")
            elif not fresh:
                work_reasons.append("account_allowance_stale")
        if observation.get("account_allowance") is not True or observation.get("context_capacity") is not False:
            work_reasons.append("invalid_allowance_kind")
        if observation.get("rate_limit_reached") is True:
            work_reasons.append("provider_rate_limit_reached")
        windows = observation.get("windows")
        if not isinstance(windows, dict):
            windows = {}
        for key, minutes in (("five_hour", 300), ("weekly", 10080)):
            window = windows.get(key)
            if not isinstance(window, dict):
                work_reasons.append(key + "_allowance_unknown")
                continue
            used, remaining = window.get("used_percent"), window.get("remaining_percent")
            if window.get("window_minutes") != minutes or not _percent(used) or not _percent(remaining) or not math.isclose(used + remaining, 100, abs_tol=1e-9):
                work_reasons.append(key + "_allowance_invalid")
                continue
            if settings_valid and remaining <= reserve_percent:
                work_reasons.append(key + "_reserve_reached")
            if batch_budget_percent is None:
                if settings_valid and remaining < min(100, reserve_percent + 10):
                    work_reasons.append(key + "_batch_budget_unknown_near_reserve")
            elif not _percent(batch_budget_percent):
                work_reasons.append("invalid_batch_budget")
            elif settings_valid and remaining - batch_budget_percent <= reserve_percent:
                work_reasons.append(key + "_batch_would_use_reserve")
            reset = _parse_time(window.get("reset_at_utc"))
            if reset is None:
                resume_reasons.append(key + "_reset_unknown")
            elif key == "five_hour":
                try:
                    gate_utc, gate_toronto = _times(reset + timedelta(seconds=120))
                except OverflowError:
                    resume_reasons.append("five_hour_reset_invalid")
            if key == "five_hour" and used != 0:
                resume_reasons.append("five_hour_not_fully_restored")

    if context_remaining_percent is not None:
        if not _percent(context_remaining_percent):
            work_reasons.append("context_capacity_invalid")
        elif settings_valid and context_remaining_percent <= context_reserve_percent:
            work_reasons.append("context_checkpoint_required")
    work_reasons = list(dict.fromkeys(work_reasons))
    resume_reasons = list(dict.fromkeys(work_reasons + resume_reasons))
    return {
        "work_allowed": not work_reasons,
        "resume_allowed": not resume_reasons,
        "resume_requires_recorded_gate": True,
        "checkpoint_required": bool(work_reasons),
        "fresh": fresh,
        "age_seconds": age,
        "work_reasons": work_reasons,
        "resume_reasons": resume_reasons,
        "reasons": resume_reasons,
        "resume_not_before_utc": gate_utc,
        "resume_not_before_toronto": gate_toronto,
    }
