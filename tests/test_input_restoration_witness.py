"""Posted input witness contracts with injected operations; no desktop input."""
import ctypes
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/diagnostics"))
from input_restoration_witness import (InputRestorationWitness, QT_KEY_F24,
                                       WITNESS_QML, _QtNativeAdapter)


class Value:
    def __init__(self, **properties):
        self.values = properties

    def property(self, name):
        return self.values[name]


class Adapter:
    def __init__(self):
        self.owned = self.enabled = self.has_focus = self.posted = True
        self.actions = []
        self.timers = []
        self.item = Value(enabled=True)
        self.prior = object()
        self.posted_down = self.posted_up = self.fail_up = False
        self.quarantined = False
        self.previous_control_keys = []

    def owns(self, window):
        return self.owned

    def native_enabled(self, window):
        return self.enabled

    def previous_focus(self, window):
        return self.prior

    def create(self, window, engine, owner, pressed, released):
        self.actions.append("create")
        self.pressed, self.released = pressed, released
        return object(), self.item

    def focus(self, item):
        self.actions.append("focus")

    def focused(self, window, item):
        return self.has_focus

    def post_pair(self, window):
        self.actions.append("post-pair")
        self.posted_down = bool(self.posted)
        self.posted_up = self.posted_down and not self.fail_up
        return self.posted_down and self.posted_up

    def schedule(self, delay, callback):
        self.timers.append((delay, callback))

    def dispose(self, window, item, component, previous):
        assert item is self.item and previous is self.prior
        self.actions.append("restore-focus/dispose-own-item")

    def quarantine(self, window, *, release_consumed, record):
        self.quarantined = self.posted_down and not release_consumed
        self.quarantine_record = record
        if self.quarantined:
            self.actions.append("quarantine-before-focus-cleanup")
        return {"installed": self.quarantined, "downPosted": self.posted_down,
                "upPosted": self.posted_up, "releaseAlreadyConsumed": release_consumed,
                "scope": "Owned disposable QWindow F24 press/release only"}

    def drain_late_pair(self, *, press=True, release=True):
        for kind, posted in (("press", self.posted_down and press),
                             ("release", self.posted_up and release)):
            if not posted:
                continue
            if self.quarantined:
                self.quarantine_record("input-witness-quarantine-consumed",
                                       key="F24", eventType=kind)
                if kind == "release":
                    self.quarantined = False
            else:
                self.previous_control_keys.append(kind)


@pytest.fixture
def fixture():
    adapter = Adapter()
    owner = Value(isInteractive=True)
    records, finished = [], []
    current = [10.0]
    witness = InputRestorationWitness(object(), object(), owner,
        record=lambda event, **values: records.append({"event": event, **values}),
        finished=finished.append, disposable=True, clock=lambda: current[0], adapter=adapter)
    return SimpleNamespace(witness=witness, adapter=adapter, owner=owner,
                           records=records, finished=finished, current=current)


def test_real_delivery_callback_is_separate_from_gui_enabled_state_and_consumes_release(fixture):
    value = fixture
    value.witness.start()
    assert value.witness.result is None and value.finished == []
    assert value.adapter.actions == ["create", "focus", "post-pair"]
    value.current[0] = 10.013
    value.adapter.pressed(QT_KEY_F24, False)
    assert value.finished == []  # Keep focus until key-up is swallowed too.
    value.current[0] = 10.015
    value.adapter.released(QT_KEY_F24)
    assert value.finished[0]["status"] == "PASS"
    assert value.finished[0]["acceptedSeconds"] == 10.013
    assert value.adapter.actions[-1] == "restore-focus/dispose-own-item"
    assert [row["event"] for row in value.records] == ["input-witness-issued",
        "input-witness-accepted", "input-witness-release-consumed", "input-witness-finished"]
    assert value.records[1]["issueToAcceptedMs"] == pytest.approx(13)
    assert "not physical human input latency" in value.finished[0]["scope"]
    # A stale timer or duplicate key signal cannot resurrect the witness.
    value.adapter.timers[0][1]()
    value.adapter.pressed(QT_KEY_F24, False)
    value.adapter.released(QT_KEY_F24)
    assert len(value.finished) == 1


@pytest.mark.parametrize("failure", ["foreign-hwnd", "native-disabled", "qml-disabled"])
def test_input_and_process_guards_reject_before_creating_or_posting(fixture, failure):
    if failure == "foreign-hwnd":
        fixture.adapter.owned = False
    elif failure == "native-disabled":
        fixture.adapter.enabled = False
    else:
        fixture.owner.values["isInteractive"] = False
    fixture.witness.start()
    assert fixture.finished[0]["status"] == "FAIL"
    assert fixture.adapter.actions == []
    assert fixture.finished[0]["acceptedSeconds"] is None


@pytest.mark.parametrize("failure", ["no-focus", "witness-disabled", "post-rejected"])
def test_issue_failure_restores_owned_focus_and_disposes_only_the_witness(fixture, failure):
    if failure == "no-focus":
        fixture.adapter.has_focus = False
    elif failure == "witness-disabled":
        fixture.adapter.item.values["enabled"] = False
    else:
        fixture.adapter.posted = False
    fixture.witness.start()
    assert fixture.finished[0]["status"] == "FAIL"
    assert fixture.adapter.actions[-1] == "restore-focus/dispose-own-item"
    assert fixture.adapter.actions.count("restore-focus/dispose-own-item") == 1
    if failure != "post-rejected":
        assert "post-pair" not in fixture.adapter.actions


@pytest.mark.parametrize("failure", ["wrong-key", "repeat", "lost-focus", "input-relocked", "late"])
def test_unexpected_or_unusable_press_never_reports_acceptance(fixture, failure):
    fixture.witness.start()
    fixture.current[0] = 10.05
    if failure == "lost-focus":
        fixture.adapter.has_focus = False
    elif failure == "input-relocked":
        fixture.owner.values["isInteractive"] = False
    elif failure == "late":
        fixture.current[0] = 10.75
    fixture.adapter.pressed(1 if failure == "wrong-key" else QT_KEY_F24, failure == "repeat")
    assert fixture.finished[0]["status"] == "FAIL"
    assert not any(row["event"] == "input-witness-accepted" for row in fixture.records)


def test_release_without_press_is_a_failure_and_does_not_invent_input_time(fixture):
    fixture.witness.start()
    fixture.adapter.released(QT_KEY_F24)
    assert fixture.finished[0]["status"] == "FAIL"
    assert fixture.finished[0]["acceptedSeconds"] is None
    assert fixture.finished[0]["quarantine"]["releaseAlreadyConsumed"]
    assert not fixture.adapter.quarantined


def test_bounded_timeout_and_early_timer_reschedule_require_no_blocking_wait(fixture):
    fixture.witness.start()
    fixture.current[0] = 10.70
    fixture.adapter.timers[0][1]()
    assert fixture.finished == []
    assert 49 <= fixture.adapter.timers[-1][0] <= 51
    fixture.current[0] = 10.75
    fixture.adapter.timers[-1][1]()
    assert fixture.finished[0]["status"] == "FAIL"
    assert "bounded delivery deadline" in fixture.finished[0]["reason"]


def test_cancel_restores_focus_and_prevents_late_delivery_from_qualifying(fixture):
    fixture.witness.start()
    fixture.witness.cancel()
    fixture.adapter.pressed(QT_KEY_F24, False)
    assert fixture.finished[0]["status"] == "CANCELLED"
    assert fixture.finished[0]["acceptedSeconds"] is None
    fixture.adapter.drain_late_pair()
    assert fixture.adapter.previous_control_keys == []
    assert not fixture.adapter.quarantined
    assert len(fixture.finished) == 1
    with pytest.raises(RuntimeError, match="only one"):
        fixture.witness.start()


@pytest.mark.parametrize("failure", ["timeout", "cancel", "accepted-press-timeout", "up-post-failed"])
def test_failed_pair_is_quarantined_before_focus_cleanup_without_qualifying(fixture, failure):
    if failure == "up-post-failed":
        fixture.adapter.fail_up = True
    fixture.witness.start()
    if failure == "cancel":
        fixture.witness.cancel()
    elif failure != "up-post-failed":
        if failure == "accepted-press-timeout":
            fixture.current[0] = 10.05
            fixture.adapter.pressed(QT_KEY_F24, False)
        fixture.current[0] = 10.75
        fixture.witness.poll()
    assert fixture.adapter.actions[-2:] == ["quarantine-before-focus-cleanup",
                                           "restore-focus/dispose-own-item"]
    terminal = dict(fixture.finished[0])
    assert terminal["status"] == ("CANCELLED" if failure == "cancel" else "FAIL")
    assert terminal["quarantine"]["installed"]
    fixture.adapter.drain_late_pair(press=failure != "accepted-press-timeout")
    assert fixture.adapter.previous_control_keys == []
    assert fixture.finished == [terminal]
    assert fixture.adapter.quarantined is (failure == "up-post-failed")


def test_nonposted_startup_failure_restores_focus_without_installing_a_filter(fixture):
    fixture.adapter.posted = False
    fixture.witness.start()
    assert fixture.finished[0]["status"] == "FAIL"
    assert not fixture.finished[0]["quarantine"]["installed"]
    assert not fixture.adapter.quarantined
    assert "quarantine-before-focus-cleanup" not in fixture.adapter.actions


def test_quarantine_failure_retains_owned_witness_focus_until_window_teardown(fixture):
    def reject(*args, **kwargs):
        raise RuntimeError("Filter installation failed")

    fixture.adapter.quarantine = reject
    fixture.witness.start()
    fixture.witness.cancel()
    assert fixture.finished[0]["status"] == "FAIL"
    assert fixture.finished[0]["focusCleanupDeferred"]
    assert "restore-focus/dispose-own-item" not in fixture.adapter.actions


@pytest.mark.parametrize("timeout", [0, -1, True, float("inf"), float("nan")])
def test_invalid_timeout_and_missing_disposable_authorization_do_not_load_qt(timeout):
    with pytest.raises(ValueError, match="timeout"):
        InputRestorationWitness(None, None, None, record=None, finished=None,
                                disposable=True, timeout_ms=timeout)
    with pytest.raises(ValueError, match="explicitly disposable"):
        InputRestorationWitness(None, None, None, record=None, finished=None)


def test_native_adapter_posts_exact_f24_pair_only_to_verified_owned_hwnd():
    adapter = object.__new__(_QtNativeAdapter)
    posts = []
    adapter.owns = lambda window: True
    adapter.user = SimpleNamespace(PostMessageW=lambda *values: posts.append(values) or 1)
    assert adapter.post_pair(SimpleNamespace(winId=lambda: 123))
    assert posts == [(123, 0x0100, 0x87, 1), (123, 0x0101, 0x87, 0xC0000001)]
    adapter.owns = lambda window: False
    assert not adapter.post_pair(SimpleNamespace(winId=lambda: 456))
    assert len(posts) == 2


def test_native_adapter_tracks_partial_post_success_for_failure_cleanup():
    adapter = object.__new__(_QtNativeAdapter)
    adapter.owns = lambda window: True
    posts = []

    def post(hwnd, message, key, flags):
        posts.append(message)
        return message == 0x0100

    adapter.user = SimpleNamespace(PostMessageW=post)
    assert not adapter.post_pair(SimpleNamespace(winId=lambda: 123))
    assert posts == [0x0100, 0x0101]
    assert adapter.posted_down and not adapter.posted_up


@pytest.mark.parametrize("up_posted", [False, True])
def test_actual_owned_object_filter_drains_f24_only_and_retains_python_lifetime(up_posted):
    # Deliver real Qt key events to a QObject recipient, with no QWindow, HWND,
    # desktop activation or keyboard API. The filter is the runtime filter.
    import gc
    import weakref
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
    from PySide6.QtGui import QKeyEvent
    from shiboken6 import delete, isValid

    class Recipient(QObject):
        def __init__(self):
            super().__init__()
            self.keys = []

        def event(self, event):
            if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
                self.keys.append(event.key())
            return super().event(event)

    application = QCoreApplication.instance() or QCoreApplication([])
    owned, other = Recipient(), Recipient()
    adapter = object.__new__(_QtNativeAdapter)
    adapter.owns = lambda window: window is owned
    adapter.posted_down, adapter.posted_up = True, up_posted
    records = []
    evidence = adapter.quarantine(owned, release_consumed=False,
        record=lambda event, **values: records.append({"event": event, **values}))
    assert evidence["installed"]
    held = weakref.ref(owned._cleanroom_f24_quarantines[0])
    del adapter
    gc.collect()
    assert held() is not None and held().parent() is owned
    QCoreApplication.sendEvent(other, QKeyEvent(QEvent.KeyPress, Qt.Key_F24, Qt.NoModifier))
    QCoreApplication.sendEvent(owned, QKeyEvent(QEvent.KeyPress, Qt.Key_F23, Qt.NoModifier))
    QCoreApplication.postEvent(owned, QKeyEvent(QEvent.KeyPress, Qt.Key_F24, Qt.NoModifier))
    if up_posted:
        QCoreApplication.postEvent(owned, QKeyEvent(QEvent.KeyRelease, Qt.Key_F24, Qt.NoModifier))
    application.processEvents()
    assert owned.keys == [Qt.Key_F23] and other.keys == [Qt.Key_F24]
    assert [row["eventType"] for row in records] == (["press", "release"] if up_posted else ["press"])
    assert bool(owned._cleanroom_f24_quarantines) is (not up_posted)
    if up_posted:
        QCoreApplication.sendEvent(owned, QKeyEvent(QEvent.KeyPress, Qt.Key_F24, Qt.NoModifier))
        assert owned.keys == [Qt.Key_F23, Qt.Key_F24]
    else:
        retained = held()
        delete(owned)
        assert not isValid(retained)
    delete(other)
    if isValid(owned):
        delete(owned)


def test_native_adapter_requires_current_process_owner_before_posting():
    adapter = object.__new__(_QtNativeAdapter)
    adapter.ctypes, adapter.wintypes = ctypes, SimpleNamespace(DWORD=ctypes.c_uint32)
    adapter.pid, adapter.is_valid = 99, lambda window: True
    process_id = [99]

    def identify(hwnd, pointer):
        pointer._obj.value = process_id[0]
        return 33

    adapter.user = SimpleNamespace(GetWindowThreadProcessId=identify)
    window = SimpleNamespace(winId=lambda: 123)
    assert adapter.owns(window)
    process_id[0] = 100
    assert not adapter.owns(window)


def test_qml_handler_enables_from_real_interactive_owner_and_only_accepts_f24():
    # Compile/instantiate the real Item with QtQml; no QQuickWindow, WebEngine,
    # HWND or native input. This check proves binding/handler availability only.
    from PySide6.QtCore import QCoreApplication, QObject, Property, Signal, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    class Owner(QObject):
        changed = Signal()

        def __init__(self):
            super().__init__()
            self.value = False

        @Property(bool, notify=changed)
        def isInteractive(self):
            return self.value

    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(WITNESS_QML, QUrl("file:///NoWindowInputWitness.qml"))
    assert component.isReady(), component.errorString()
    owner = Owner()
    item = component.createWithInitialProperties({"interactionOwner": owner})
    assert item is not None, component.errorString()
    assert item.property("enabled") is False
    owner.value = True
    owner.changed.emit()
    assert item.property("enabled") is True
    assert item.property("opacity") == 0
    assert hasattr(item, "witnessPressed") and hasattr(item, "witnessReleased")
    item.deleteLater()
    application.processEvents()
