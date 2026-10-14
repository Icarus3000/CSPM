"""Nonblocking, profile-local calendar bridge; independent of workbook startup."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import threading
from typing import Callable
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Property, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from shiboken6 import isValid

from backend.workers import Worker
from services.calendar_agenda_service import (
    CalendarAgendaService, empty_snapshot, sanitize_calendar_config,
)
from services.holiday_calendar_service import HolidayCalendarService
from services.calendar_auth import safe_microsoft_device_signin_url


def safe_calendar_link(value: str) -> bool:
    """Only user-invoked links to known calendar/authentication publishers."""
    try:
        parsed = urlsplit(str(value))
        if parsed.scheme != "https" or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443):
            return False
        host = (parsed.hostname or "").lower()
        if host == "login.microsoft.com":
            return safe_microsoft_device_signin_url(value)
        return host in {
            "outlook.office.com", "outlook.office365.com", "outlook.live.com",
            "teams.microsoft.com", "teams.live.com", "login.microsoftonline.com",
            "microsoft.com", "www.microsoft.com", "entra.microsoft.com",
            "learn.microsoft.com", "hebcal.com", "www.hebcal.com",
            "holidays.readthedocs.io",
        }
    except (TypeError, ValueError):
        return False


class CalendarAgendaController(QObject):
    snapshotChanged = Signal()
    configurationChanged = Signal()
    busyChanged = Signal()
    _challengeReady = Signal(int, object)

    def __init__(self, profile_dir: Path, configuration=None, *,
                 save_callback: Callable | None = None, service=None, parent=None):
        super().__init__(parent)
        self._configuration = sanitize_calendar_config(configuration or {})
        self._snapshot = empty_snapshot(self._configuration)
        self._save_callback = save_callback
        self._service = service or CalendarAgendaService(
            Path(profile_dir) / "calendar", holiday_provider=HolidayCalendarService(),
        )
        self._busy = False
        self._revision = 0
        self._cancel = threading.Event()
        self._closed = False
        self._disconnect_requested = threading.Event()
        self._workers = {}
        # Calendar I/O cannot queue ahead of workbook readiness or accepted saves.
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._pool.setExpiryTimeout(30000)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5 * 60 * 1000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._challengeReady.connect(self._accept_challenge)

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self):
        return deepcopy(self._snapshot)

    @Property("QVariantMap", notify=configurationChanged)
    def configuration(self):
        return deepcopy(self._configuration)

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    def _set_busy(self, value):
        if self._busy != bool(value):
            self._busy = bool(value)
            self.busyChanged.emit()

    def _publish(self, snapshot):
        self._snapshot = deepcopy(snapshot)
        self.snapshotChanged.emit()

    def _invalidate(self):
        self._cancel.set()
        self._revision += 1
        self._pool.clear()
        self._workers = {key: worker for key, worker in self._workers.items() if isValid(worker)}
        self._set_busy(False)

    def apply_configuration(self, configuration):
        """Settings reload is local only, and never starts a network request."""
        clean = sanitize_calendar_config(configuration or {})
        if clean == self._configuration:
            return
        self._invalidate()
        self._configuration = clean
        self.configurationChanged.emit()
        self._publish(empty_snapshot(clean))

    @Slot("QVariantMap", result=bool)
    def saveConfiguration(self, configuration):
        if self._closed:
            return False
        if hasattr(configuration, "toVariant"):
            configuration = configuration.toVariant()
        clean = sanitize_calendar_config(configuration)
        raw = configuration if isinstance(configuration, dict) else {}
        invalid_field = None
        if str(raw.get("clientId") or "").strip() and not clean["clientId"]:
            invalid_field = "Enter a valid Application (client) ID from Microsoft Entra."
        elif str(raw.get("accountEmail") or "").strip() and not clean["accountEmail"]:
            invalid_field = "Enter a valid calendar account email address."
        elif str(raw.get("tenantId") or "").strip() not in ("", "organizations") and clean["tenantId"] == "organizations":
            invalid_field = "Enter a valid Directory (tenant) ID or Microsoft tenant domain."
        if invalid_field:
            self._publish({**self._snapshot, "message": invalid_field})
            return False
        try:
            if self._save_callback is not None and not self._save_callback(clean):
                self._publish({**self._snapshot, "message": "Calendar settings could not be saved."})
                return False
        except Exception:
            self._publish({**self._snapshot, "message": "Calendar settings could not be saved."})
            return False
        self.apply_configuration(clean)
        return True

    @Slot(str, bool)
    def setCalendarEnabled(self, calendar_id, enabled):
        config = self.configuration
        if str(calendar_id).startswith("holidays:"):
            source = str(calendar_id).split(":", 1)[1]
            if source not in ("CA", "US", "JEWISH"):
                return
            config["holidaySources"][source] = bool(enabled)
            config["disabledCalendarIds"] = [value for value in config["disabledCalendarIds"] if value != calendar_id]
        else:
            # Only a known discovered calendar can be toggled through the UI.
            if not any(row.get("id") == calendar_id for row in self._snapshot.get("calendars", [])):
                return
            disabled = set(config["disabledCalendarIds"])
            if enabled:
                disabled.discard(calendar_id)
            else:
                disabled.add(calendar_id)
            config["disabledCalendarIds"] = sorted(disabled)
        if self.saveConfiguration(config):
            self.refresh()

    @Slot()
    def refresh(self):
        if self._closed or self._busy:
            return
        self._refresh_timer.start()
        self._start_operation("fetch")

    @Slot()
    def connectAccount(self):
        if self._closed or self._busy:
            return
        self._refresh_timer.start()
        self._start_operation("connect")

    @Slot()
    def disconnectAccount(self):
        if self._closed:
            return
        self._disconnect_requested.set()
        self._invalidate()
        self._refresh_timer.stop()
        self._publish(empty_snapshot(self._configuration))
        self._start_operation("disconnect")

    def _start_operation(self, operation):
        self._revision += 1
        revision = self._revision
        config = self.configuration
        cancellation = threading.Event()
        self._cancel = cancellation
        self._set_busy(True)
        # Cached rows are never presented as a successful current refresh.
        self._publish({**self._snapshot, "state": "loading", "stale": bool(
            self._snapshot.get("today") or self._snapshot.get("next7Days")),
            "message": "Disconnecting…" if operation == "disconnect" else "Refreshing calendar…",
            "signInCode": "", "signInUrl": ""})

        def run():
            try:
                if cancellation.is_set():
                    return (revision, None)
                # A cancelled queued Disconnect must still be fulfilled before
                # another connection is used, or during shutdown after drain.
                if self._disconnect_requested.is_set():
                    self._service.disconnect()
                    self._disconnect_requested.clear()
                if operation == "connect":
                    snapshot = self._service.connect(
                        config, lambda challenge: self._challengeReady.emit(revision, challenge),
                        cancellation,
                    )
                elif operation == "disconnect":
                    snapshot = empty_snapshot(config)
                    snapshot.update(state="disconnected", message="Microsoft 365 disconnected.")
                else:
                    snapshot = self._service.fetch(config, cancellation)
                return (revision, snapshot)
            except Exception:
                # Auth errors must not expose provider responses, codes or tokens
                # through Worker logging or normal error/toast instrumentation.
                message = ("The saved calendar sign-in could not be removed. Try Disconnect again."
                    if self._disconnect_requested.is_set() else
                    "The calendar could not be refreshed. Check the connection and try again.")
                return (revision, {**empty_snapshot(config), "state": "error",
                    "message": message, "errors": [message]})

        worker = Worker(run, name="calendar-agenda")
        self._workers[revision] = worker
        worker.signals.result.connect(self._accept_result)
        # A retained reference prevents frozen Python wrappers being collected.
        self._pool.start(worker)

    @Slot(object)
    def _accept_result(self, result):
        revision, snapshot = result
        self._workers.pop(revision, None)
        if self._closed or revision != self._revision or snapshot is None:
            return
        self._set_busy(False)
        if snapshot.get("state") == "error" and (
            self._snapshot.get("today") or self._snapshot.get("next7Days")
        ):
            snapshot = {**snapshot,
                "today": self._snapshot.get("today", []),
                "next7Days": self._snapshot.get("next7Days", []),
                "calendars": self._snapshot.get("calendars", []), "stale": True,
                "asOf": self._snapshot.get("asOf", "")}
        self._publish(snapshot)

    @Slot(int, object)
    def _accept_challenge(self, revision, challenge):
        if self._closed or revision != self._revision:
            return
        code = str(challenge.get("user_code") or challenge.get("signInCode") or "")
        url = str(challenge.get("verification_uri") or challenge.get("signInUrl") or "")
        self._publish({**self._snapshot, "state": "signing-in",
            "message": "Open Microsoft sign-in, enter this code, and use your configured account.",
            "signInCode": code, "signInUrl": url if safe_calendar_link(url) else ""})

    @Slot(str, result=bool)
    def openEventLink(self, value):
        if self._closed or not safe_calendar_link(value):
            return False
        return bool(QDesktopServices.openUrl(QUrl(value)))

    @Slot()
    def cancelConnection(self):
        self._invalidate()
        self._refresh_timer.stop()
        self._publish(empty_snapshot(self._configuration))

    def shutdown(self):
        """Cancel only calendar jobs; accepted financial saves keep their pool."""
        self._closed = True
        self._refresh_timer.stop()
        self._invalidate()
        self._pool.waitForDone()
        self._workers.clear()
        if self._disconnect_requested.is_set():
            try:
                self._service.disconnect()
                self._disconnect_requested.clear()
            except Exception:
                self._publish({**empty_snapshot(self._configuration), "state": "error",
                    "message": "The saved calendar sign-in could not be removed. Try Disconnect again."})
