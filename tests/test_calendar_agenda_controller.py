"""Calendar worker ownership, settings, cancellation and GUI-thread contracts."""
import os
import sys
import threading
import time
from pathlib import Path

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/python"))
from backend.controllers.calendar_agenda_controller import CalendarAgendaController, safe_calendar_link
from services.calendar_agenda_service import empty_snapshot, sanitize_calendar_config

CONFIG = {
    "clientId": "11111111-1111-1111-1111-111111111111",
    "tenantId": "22222222-2222-2222-2222-222222222222",
    "accountEmail": "calendar@example.test",
    "holidaySources": {"CA": False, "US": False, "JEWISH": False},
}


class FakeService:
    def __init__(self):
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def fetch(self, config, cancel_event=None):
        self.calls.append(("fetch", config, cancel_event))
        self.started.set()
        self.release.wait(2)
        return {**empty_snapshot(config), "state": "ready", "message": "Refreshed"}

    def connect(self, config, challenge_callback, cancel_event):
        self.calls.append(("connect", config, cancel_event))
        self.started.set()
        challenge_callback({"user_code": "TESTCODE", "verification_uri": "https://microsoft.com/devicelogin"})
        cancel_event.wait(2)
        return {**empty_snapshot(config), "state": "ready", "message": "Old sign-in"}

    def disconnect(self):
        self.calls.append(("disconnect",))


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Calendar controller did not reach expected state")


@pytest.fixture
def controller(tmp_path):
    qt = QGuiApplication.instance() or QGuiApplication([])
    service = FakeService()
    saved = []
    def save(config):
        saved.append(config)
        return True
    instance = CalendarAgendaController(tmp_path, CONFIG, service=service, save_callback=save)
    yield instance, service, saved, qt
    service.release.set()
    instance.shutdown()
    QCoreApplication.processEvents()


def test_binding_controller_does_not_start_network_or_timer(controller):
    instance, service, _, _ = controller
    assert instance.snapshot["state"] == "disconnected"
    assert not service.calls
    assert not instance._refresh_timer.isActive()


def test_refresh_returns_immediately_and_publishes_on_gui_thread(controller):
    instance, service, _, _ = controller
    service.release.clear()
    observed_threads = []
    instance.snapshotChanged.connect(lambda: observed_threads.append(QThread.currentThread()))
    began = time.monotonic()
    instance.refresh()
    assert time.monotonic() - began < 0.2
    assert instance.busy
    assert instance.snapshot["state"] == "loading"
    assert service.started.wait(1)
    # Repeated UI refresh cannot submit a duplicate in-flight request.
    instance.refresh()
    service.release.set()
    wait_for(lambda: not instance.busy)
    assert len(service.calls) == 1
    assert instance.snapshot["state"] == "ready"
    assert all(thread == instance.thread() for thread in observed_threads)


def test_changed_config_rejects_previous_account_result(controller):
    instance, service, saved, _ = controller
    service.release.clear()
    instance.refresh()
    assert service.started.wait(1)
    replacement = {**CONFIG, "accountEmail": "different@example.test"}
    assert instance.saveConfiguration(replacement)
    assert instance.snapshot["accountEmail"] == replacement["accountEmail"]
    service.release.set()
    wait_for(lambda: instance._pool.activeThreadCount() == 0)
    QCoreApplication.processEvents()
    assert instance.snapshot["state"] == "disconnected"
    assert instance.configuration["accountEmail"] == replacement["accountEmail"]
    assert saved[-1]["accountEmail"] == replacement["accountEmail"]


def test_cancelled_signin_never_publishes_late_success(controller):
    instance, service, _, _ = controller
    instance.connectAccount()
    wait_for(lambda: instance.snapshot["state"] == "signing-in")
    assert instance.snapshot["signInCode"] == "TESTCODE"
    instance.cancelConnection()
    assert service.calls[0][2].is_set()
    wait_for(lambda: instance._pool.activeThreadCount() == 0)
    QCoreApplication.processEvents()
    assert not instance.busy
    assert instance.snapshot["state"] == "disconnected"
    assert not instance.snapshot.get("signInCode")


def test_failed_persistence_does_not_apply_settings(controller):
    instance, _, _, _ = controller
    old = instance.configuration
    instance._save_callback = lambda config: False
    assert not instance.saveConfiguration({**CONFIG, "accountEmail": "other@example.test"})
    assert instance.configuration == old


@pytest.mark.parametrize("field,value,message", [
    ("clientId", "wrong-app-id", "Application (client) ID"),
    ("accountEmail", "not-an-email", "email address"),
    ("tenantId", "../wrong-tenant", "Directory (tenant) ID"),
])
def test_malformed_setup_is_visible_without_persisting(controller, field, value, message):
    instance, _, saved, _ = controller
    assert not instance.saveConfiguration({**CONFIG, field: value})
    assert message in instance.snapshot["message"]
    assert not saved


def test_saved_settings_cannot_contain_tokens_or_client_secret(controller):
    instance, _, saved, _ = controller
    assert instance.saveConfiguration({**CONFIG, "access_token": "secret", "clientSecret": "secret"})
    assert saved[-1] == sanitize_calendar_config(CONFIG)
    assert "secret" not in repr(instance.configuration)


def test_calendar_toggle_requires_discovered_calendar(controller):
    instance, service, saved, _ = controller
    instance.setCalendarEnabled("unknown", False)
    assert not saved and not service.calls
    instance._publish({**instance.snapshot, "calendars": [{"id": "calendar-1"}]})
    instance.setCalendarEnabled("calendar-1", False)
    wait_for(lambda: not instance.busy)
    assert saved[-1]["disabledCalendarIds"] == ["calendar-1"]


def test_holiday_toggle_updates_source_switch(controller):
    instance, _, saved, _ = controller
    instance.setCalendarEnabled("holidays:JEWISH", True)
    wait_for(lambda: not instance.busy)
    assert saved[-1]["holidaySources"]["JEWISH"] is True


def test_reenabling_holiday_removes_legacy_disabled_id(controller):
    instance, _, saved, _ = controller
    instance.apply_configuration({**CONFIG, "disabledCalendarIds": ["holidays:JEWISH"]})
    instance.setCalendarEnabled("holidays:JEWISH", True)
    wait_for(lambda: not instance.busy)
    assert saved[-1]["disabledCalendarIds"] == []
    assert saved[-1]["holidaySources"]["JEWISH"] is True


def test_shutdown_cancels_calendar_signin(controller):
    instance, service, _, _ = controller
    instance.connectAccount()
    assert service.started.wait(1)
    began = time.monotonic()
    instance.shutdown()
    assert time.monotonic() - began < 1
    assert service.calls[0][2].is_set()
    assert not instance._refresh_timer.isActive()
    assert not instance.busy


def test_disconnect_intent_survives_immediate_shutdown_behind_reader(controller):
    instance, service, _, _ = controller
    service.release.clear()
    instance.refresh()
    assert service.started.wait(1)
    instance.disconnectAccount()
    # Queued disconnect is discarded by shutdown, but its intent must survive.
    service.release.set()
    instance.shutdown()
    assert ("disconnect",) in service.calls
    assert not instance._disconnect_requested.is_set()


def test_disconnect_failure_is_visible_and_retried_at_shutdown(controller):
    instance, service, _, _ = controller
    attempts = []
    def fail_once():
        attempts.append(True)
        if len(attempts) == 1:
            raise OSError("synthetic failure")
    service.disconnect = fail_once
    instance.disconnectAccount()
    wait_for(lambda: not instance.busy)
    assert instance.snapshot["state"] == "error"
    assert "could not be removed" in instance.snapshot["message"]
    assert instance._disconnect_requested.is_set()
    instance.shutdown()
    assert len(attempts) == 2
    assert not instance._disconnect_requested.is_set()


def test_current_microsoft_device_page_survives_challenge_and_opens_without_launching_browser(controller, monkeypatch):
    instance, _, _, _ = controller
    url = "https://login.microsoft.com/device"
    opened = []
    monkeypatch.setattr("backend.controllers.calendar_agenda_controller.QDesktopServices.openUrl", lambda value: opened.append(value.toString()) or True)
    instance._accept_challenge(instance._revision, {"user_code": "SYNTHETIC", "verification_uri": url})
    assert instance.snapshot["state"] == "signing-in"
    assert instance.snapshot["signInUrl"] == url
    assert instance.openEventLink(instance.snapshot["signInUrl"])
    assert opened == [url]
    assert not instance.openEventLink(url + "?code=unexpected")
    assert opened == [url]


def test_device_challenge_and_open_microsoft_signin_copy_user_code_to_clipboard(controller, monkeypatch):
    instance, _, _, qt = controller
    if not isinstance(qt, QGuiApplication):
        from types import SimpleNamespace
        state = {"text": ""}
        fake_clipboard = SimpleNamespace(
            setText=lambda value: state.__setitem__("text", str(value)),
            text=lambda: state["text"],
        )
        monkeypatch.setattr(QGuiApplication, "clipboard", staticmethod(lambda: fake_clipboard))
    else:
        QGuiApplication.clipboard().setText("")

    url = "https://login.microsoft.com/device"
    opened = []
    monkeypatch.setattr("backend.controllers.calendar_agenda_controller.QDesktopServices.openUrl", lambda value: opened.append(value.toString()) or True)

    instance._accept_challenge(instance._revision, {"user_code": "  F5CHSERFA  ", "verification_uri": url})
    assert instance.snapshot["signInCode"] == "F5CHSERFA"
    assert QGuiApplication.clipboard().text() == "F5CHSERFA"

    QGuiApplication.clipboard().setText("OVERWRITTEN")
    assert QGuiApplication.clipboard().text() == "OVERWRITTEN"

    assert instance.openEventLink(instance.snapshot["signInUrl"])
    assert opened == [url]
    assert QGuiApplication.clipboard().text() == "F5CHSERFA"

    assert instance.copyToClipboard("  MANUAL99  ") is True
    assert QGuiApplication.clipboard().text() == "MANUAL99"
    assert instance.copyToClipboard("   ") is False



@pytest.mark.parametrize("url", [
    "https://microsoft.com/devicelogin", "https://login.microsoft.com/device", "https://entra.microsoft.com/",
    "https://outlook.office.com/calendar/item/test", "https://teams.microsoft.com/l/meetup-join/test",
    "https://www.hebcal.com/", "https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app",
])
def test_trusted_links_are_openable(url):
    assert safe_calendar_link(url)


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "file:///C:/secret", "http://outlook.office.com/test",
    "https://outlook.office.com.evil.test/", "https://evil.test/",
    "https://outlook.office.com:8080/test", "https://name:secret@outlook.office.com/",
    "https://login.microsoft.com/other", "https://login.microsoft.com/device?code=unexpected",
    "https://login.microsoft.com/device#unexpected", "https://login.microsoft.com.evil.test/device",
])
def test_unsafe_links_are_rejected(url):
    assert not safe_calendar_link(url)


def test_shutdown_cancels_actual_msal_polling_without_network_or_persistence(tmp_path):
    """Exercise MSAL's real polling loop, rather than a cooperative fake loop."""
    from datetime import datetime, timezone
    import runpy
    from types import SimpleNamespace

    from msal.oauth2cli.oauth2 import Client
    from services.calendar_agenda_service import CalendarAgendaService

    helpers = runpy.run_path(str(Path(__file__).with_name("test_calendar_auth.py")))
    auth, app, cache, store, _ = helpers["fixture_auth"](tmp_path)
    original_cache = cache.serialize()
    polled = threading.Event()

    def synthetic_pending_response(flow, **kwargs):
        polled.set()
        return {"error": "authorization_pending"}

    # Actual MSAL polling uses an injected no-I/O token-response function.
    # A sixty-second interval must still stop promptly on controller shutdown.
    client = SimpleNamespace(
        DEVICE_FLOW_RETRIABLE_ERRORS=Client.DEVICE_FLOW_RETRIABLE_ERRORS,
        _obtain_token_by_device_flow=synthetic_pending_response,
    )
    app.flow["interval"] = 60
    app.acquire_token_by_device_flow = lambda flow: Client.obtain_token_by_device_flow(client, flow)
    configuration = {
        **helpers["CONFIG"], "holidaySources": {"CA": False, "US": False, "JEWISH": False},
    }
    service = CalendarAgendaService(
        tmp_path, auth=auth, now=lambda: datetime.now(timezone.utc),
    )
    qt = QCoreApplication.instance() or QCoreApplication([])
    instance = CalendarAgendaController(tmp_path, configuration, service=service)
    try:
        instance.connectAccount()
        assert polled.wait(1), "Actual MSAL device polling did not start"
        began = time.monotonic()
        instance.shutdown()
        assert time.monotonic() - began < 2
        qt.processEvents()
        assert app.flow["expires_at"] == 0
        assert store.saved == [] and cache.serialize() == original_cache
        assert instance._closed and not instance.busy
        assert not instance._refresh_timer.isActive()
        assert instance._pool.activeThreadCount() == 0
        assert not list(tmp_path.rglob("*.dpapi"))
    finally:
        instance.shutdown()
