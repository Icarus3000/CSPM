"""
Session recovery and runtime state persistence.

Extracted from app_controller.py to reduce monolith size.
Manages close-session snapshots, recovery detection, and runtime state I/O.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class SessionRecoveryManager:
    """Manages session recovery snapshots and runtime state persistence.

    Parameters:
        draft_session_path: Path to the draft session snapshot JSON file.
        runtime_session_path: Path to the runtime session state JSON file.
        report_failure: callable(user_message, *, context, exc, emit_signal)
    """

    def __init__(
        self,
        draft_session_path: Path,
        runtime_session_path: Path,
        report_failure: Callable[..., None],
    ) -> None:
        self._draft_session_path = draft_session_path
        self._runtime_session_path = runtime_session_path
        self._report_failure = report_failure

    # ── Atomic file helpers ────────────────────────────────────────────────────

    def write_json_atomic(self, target_path: Path, payload: Dict[str, Any]) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        temp_path.write_text(serialized, encoding="utf-8")
        try:
            os.replace(str(temp_path), str(target_path))
            return
        except PermissionError:
            # Some synced/workspace ACL policies block replace/rename (delete-child denied).
            # Fallback to direct overwrite so runtime state writes still succeed.
            target_path.write_text(serialized, encoding="utf-8")
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            return

    def delete_file_if_exists(self, path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            self._report_failure(
                "Could not remove file",
                context="filesystem.delete_if_exists",
                exc=exc,
                emit_signal=False,
            )

    # ── Runtime state ──────────────────────────────────────────────────────────

    def load_runtime_state(self) -> Dict[str, Any]:
        try:
            if not self._runtime_session_path.exists():
                return {}
            raw = json.loads(self._runtime_session_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
            return {}
        except Exception as exc:
            self._report_failure(
                "Could not load runtime session state",
                context="session.runtime_state.load",
                exc=exc,
                emit_signal=False,
            )
            return {}

    def save_runtime_state(self, state: Dict[str, Any]) -> None:
        self.write_json_atomic(self._runtime_session_path, dict(state or {}))

    def mark_runtime_open(self) -> None:
        state = self.load_runtime_state()
        state["version"] = 1
        state["cleanShutdown"] = False
        state["openedAtUtc"] = datetime.now(timezone.utc).isoformat()
        state["globalTimerLock"] = {}
        self.save_runtime_state(state)

    # ── Close session snapshots ────────────────────────────────────────────────

    def save_close_session_snapshot(self, payload: dict) -> bool:
        try:
            snapshot = {
                "version": 2,
                "savedAtUtc": datetime.now(timezone.utc).isoformat(),
                "payload": dict(payload or {}),
            }
            self.write_json_atomic(self._draft_session_path, snapshot)
            return True
        except Exception as exc:
            self._report_failure(
                "Could not write close-session snapshot",
                context="session.close_snapshot.write",
                exc=exc,
            )
            return False

    def load_close_session_snapshot(self) -> Optional[Dict[str, Any]]:
        try:
            if not self._draft_session_path.exists():
                return None
            raw = json.loads(self._draft_session_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            payload = raw.get("payload")
            if not isinstance(payload, dict):
                return None
            return {
                "savedAtUtc": str(raw.get("savedAtUtc", "")),
                "payload": payload,
            }
        except Exception as exc:
            self._report_failure(
                "Could not load close-session snapshot",
                context="session.close_snapshot.load",
                exc=exc,
                emit_signal=False,
            )
            return None

    # ── Recovery detection ─────────────────────────────────────────────────────

    @staticmethod
    def payload_has_close_risk(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        windows = payload.get("windows")
        if not isinstance(windows, list):
            return False
        for row in windows:
            if not isinstance(row, dict):
                continue
            if bool(row.get("hasUnsavedWork")) or bool(row.get("hasRunningTimer")):
                return True
        return False

    @staticmethod
    def build_recovery_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
        windows = payload.get("windows")
        if not isinstance(windows, list):
            windows = []
        total = 0
        detached = 0
        unsaved = 0
        running = 0
        for row in windows:
            if not isinstance(row, dict):
                continue
            total += 1
            if bool(row.get("detachedWindow")):
                detached += 1
            if bool(row.get("hasUnsavedWork")):
                unsaved += 1
            if bool(row.get("hasRunningTimer")):
                running += 1
        return {
            "windowCount": total,
            "detachedCount": detached,
            "unsavedCount": unsaved,
            "runningTimerCount": running,
        }

    def load_pending_close_recovery(self) -> Optional[Dict[str, Any]]:
        runtime = self.load_runtime_state()
        if runtime.get("cleanShutdown", True):
            return None
        snapshot = self.load_close_session_snapshot()
        if not snapshot:
            return None
        payload = snapshot.get("payload", {})
        if not self.payload_has_close_risk(payload):
            return None
        return snapshot

    def get_pending_close_recovery(self, pending: Optional[Dict[str, Any]]) -> dict:
        if not pending:
            return {"available": False}
        payload = pending.get("payload", {})
        return {
            "available": True,
            "savedAtUtc": str(pending.get("savedAtUtc", "")),
            "payload": payload,
            "summary": self.build_recovery_summary(payload),
        }

    def resolve_pending_close_recovery(self, action: str) -> bool:
        try:
            normalized = str(action or "").strip().lower()
            if normalized == "reset":
                self.delete_file_if_exists(self._draft_session_path)
            state = self.load_runtime_state()
            state["recoveryPromptHandledAtUtc"] = datetime.now(timezone.utc).isoformat()
            self.save_runtime_state(state)
            return True
        except Exception as exc:
            self._report_failure(
                "Could not resolve pending recovery",
                context="session.recovery.resolve",
                exc=exc,
            )
            return False

    def mark_expected_shutdown(self, clear_recovery_snapshot: bool = True) -> bool:
        try:
            state = self.load_runtime_state()
            state["cleanShutdown"] = True
            state["closedAtUtc"] = datetime.now(timezone.utc).isoformat()
            state["globalTimerLock"] = {}
            self.save_runtime_state(state)
            if clear_recovery_snapshot:
                self.delete_file_if_exists(self._draft_session_path)
            return True
        except Exception as exc:
            self._report_failure(
                "Could not mark expected shutdown",
                context="session.shutdown.mark_expected",
                exc=exc,
            )
            return False
