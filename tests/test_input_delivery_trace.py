"""Passive delivery trace contracts; no QWindow, WebEngine or desktop input."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/diagnostics"))
from input_delivery_trace import InputDeliveryTrace, _QtTraceAdapter


class Adapter:
    def __init__(self):
        self.owned = True
        self.actions = []
        self.state = {"qtActive": False, "nativeFocusOwned": True}

    def owns(self, window):
        return self.owned

    def install(self, window, observe, heartbeat, interval):
        self.actions.append(("install", interval))
        self.observe, self.heartbeat = observe, heartbeat

    def snapshot(self, window):
        return dict(self.state)

    def set_heartbeat(self, enabled):
        self.actions.append(("heartbeat", enabled))

    def dispose(self, window):
        self.actions.append(("dispose",))
        return []


@pytest.fixture
def fixture():
    adapter, now = Adapter(), [10.0]
    trace = InputDeliveryTrace(object(), disposable=True, adapter=adapter, clock=lambda: now[0])
    return SimpleNamespace(trace=trace, adapter=adapter, now=now)


def test_native_qt_and_heartbeat_observations_are_buffered_distinct_and_do_not_accept_input(fixture):
    value = fixture
    value.trace.start()
    value.trace.set_pending(True, cycle=3)
    value.now[0] = 10.025
    value.adapter.heartbeat()
    value.now[0] = 10.640
    value.adapter.observe("native-ingress", messageKind="f24-press", messageTimeMs=100)
    value.adapter.observe("qt-window-key", eventKind="press", autoRepeat=False)
    value.adapter.heartbeat()
    value.trace.set_pending(False, cycle=3)
    rows = list(value.trace.rows)
    value.now[0] = 10.700
    value.adapter.heartbeat()
    assert value.trace.rows == rows
    result = value.trace.stop()
    assert result["status"] == "COMPLETE"
    assert [row["kind"] for row in result["events"]] == ["trace-started", "witness-pending-changed",
        "gui-heartbeat", "native-ingress", "qt-window-key", "gui-heartbeat", "witness-pending-changed", "trace-stopping"]
    heartbeats = [row for row in result["events"] if row["kind"] == "gui-heartbeat"]
    assert [row["gapMs"] for row in heartbeats] == pytest.approx([25, 615])
    assert result["events"][3]["state"] == {"qtActive": False, "nativeFocusOwned": True}
    assert all("acceptedSeconds" not in row for row in result["events"])
    assert value.adapter.actions == [("install", 25), ("heartbeat", True), ("heartbeat", False), ("dispose",)]
    assert value.trace.stop() is result
    value.adapter.observe("late-native", messageKind="f24-release")
    assert len(value.trace.rows) == 8
    with pytest.raises(RuntimeError, match="only once"):
        value.trace.start()


def test_trace_is_finitely_bounded_and_overflow_cannot_look_complete(fixture):
    value = fixture
    value.trace.capacity = 3
    value.trace.start()
    for _ in range(20):
        value.adapter.observe("native-ingress", messageKind="f24-press")
    result = value.trace.stop()
    assert result["status"] == "INCOMPLETE"
    assert len(result["events"]) == 3 and result["droppedRows"] == 19
    assert value.adapter.actions[-1] == ("dispose",)


def test_snapshot_failure_is_passive_and_cleanup_still_runs(fixture):
    fixture.trace.start()
    fixture.adapter.snapshot = lambda window: (_ for _ in ()).throw(RuntimeError("closed window"))
    fixture.adapter.observe("native-ingress", messageKind="f24-press")
    result = fixture.trace.stop()
    assert result["status"] == "INCOMPLETE" and result["observationErrors"] == 2
    assert fixture.adapter.actions[-1] == ("dispose",)


def test_failed_installation_disposes_partial_filters_before_raising(fixture):
    fixture.adapter.install = lambda *args: (_ for _ in ()).throw(RuntimeError("install"))
    with pytest.raises(RuntimeError, match="install"):
        fixture.trace.start()
    assert fixture.trace.closed
    assert fixture.adapter.actions == [("dispose",)]


def test_foreign_process_cannot_install_a_trace(fixture):
    fixture.adapter.owned = False
    with pytest.raises(RuntimeError, match="not owned"):
        fixture.trace.start()
    assert fixture.adapter.actions == []
    fixture.trace.stop()


@pytest.mark.parametrize("capacity", [0, 4097, True, 1.5])
def test_invalid_capacity_rejects_before_loading_qt(capacity):
    with pytest.raises(ValueError, match="capacity"):
        InputDeliveryTrace(None, disposable=True, capacity=capacity)


@pytest.mark.parametrize("interval", [0, 1001, True, float("nan"), float("inf")])
def test_invalid_heartbeat_rejects_before_loading_qt(interval):
    with pytest.raises(ValueError, match="heartbeat"):
        InputDeliveryTrace(None, disposable=True, heartbeat_ms=interval)


def test_disposable_authorization_is_required_without_loading_qt():
    with pytest.raises(ValueError, match="explicitly disposable"):
        InputDeliveryTrace(None)


def test_runtime_passive_filters_only_observe_owned_f24_and_never_consume_events():
    from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QEvent, QObject, QTimer, Signal, Qt
    from PySide6.QtGui import QKeyEvent
    from shiboken6 import delete, isValid

    class Recipient(QObject):
        activeChanged, activeFocusItemChanged = Signal(), Signal()

        def __init__(self):
            super().__init__()
            self.keys = []

        def winId(self):
            return 123

        def event(self, event):
            if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
                self.keys.append(event.key())
            return super().event(event)

    class FakeSignal:
        def __init__(self):
            self.callbacks = []
        def connect(self, callback):
            self.callbacks.append(callback)
        def disconnect(self, callback):
            self.callbacks.remove(callback)

    application = QCoreApplication.instance() or QCoreApplication([])
    owned, other = Recipient(), Recipient()
    filters = []
    adapter = object.__new__(_QtTraceAdapter)
    adapter.ctypes, adapter.wintypes = ctypes, wintypes
    adapter.NativeFilter, adapter.QEvent, adapter.QObject, adapter.QTimer = QAbstractNativeEventFilter, QEvent, QObject, QTimer
    adapter.is_valid = isValid
    adapter.native_filter = adapter.qt_filter = adapter.timer = None
    adapter.connections = []
    adapter.snapshot = lambda window: {"qtActive": False}
    adapter.app = SimpleNamespace(installNativeEventFilter=filters.append,
        removeNativeEventFilter=filters.remove, applicationStateChanged=FakeSignal(),
        focusWindowChanged=FakeSignal(), focusObjectChanged=FakeSignal())
    observations = []
    adapter.install(owned, lambda kind, **values: observations.append({"kind": kind, **values}), lambda: None, 25)
    native_filter = filters[0]
    for hwnd, key, kind in ((999, 0x87, 0x0100), (123, 0x86, 0x0100),
            (123, 0x87, 0x0100), (123, 0x87, 0x0101), (123, 0, 0x0007)):
        msg = wintypes.MSG()
        msg.hWnd, msg.wParam, msg.message, msg.time = hwnd, key, kind, 600
        assert native_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)) == (False, 0)
    assert native_filter.nativeEventFilter(b"unrelated", 0) == (False, 0)
    assert [row["messageKind"] for row in observations] == ["f24-press", "f24-release", "set-focus"]
    QCoreApplication.sendEvent(other, QKeyEvent(QEvent.KeyPress, Qt.Key_F24, Qt.NoModifier))
    QCoreApplication.sendEvent(owned, QKeyEvent(QEvent.KeyPress, Qt.Key_F23, Qt.NoModifier))
    QCoreApplication.sendEvent(owned, QKeyEvent(QEvent.KeyPress, Qt.Key_F24, Qt.NoModifier))
    QCoreApplication.sendEvent(owned, QKeyEvent(QEvent.KeyRelease, Qt.Key_F24, Qt.NoModifier))
    assert owned.keys == [Qt.Key_F23, Qt.Key_F24, Qt.Key_F24] and other.keys == [Qt.Key_F24]
    assert [row["eventKind"] for row in observations if row["kind"] == "qt-window-key"] == ["press", "release"]
    adapter.set_heartbeat(True)
    assert adapter.timer.isActive()
    assert adapter.dispose(owned) == []
    assert filters == [] and adapter.connections == []
    before = list(observations)
    owned.activeChanged.emit()
    QCoreApplication.sendEvent(owned, QKeyEvent(QEvent.KeyPress, Qt.Key_F24, Qt.NoModifier))
    assert observations == before
    application.processEvents()
    delete(owned)
    delete(other)


def test_runtime_cleanup_attempts_every_resource_even_after_a_failure():
    adapter = object.__new__(_QtTraceAdapter)
    actions = []
    adapter.is_valid = lambda item: True
    adapter.timer = SimpleNamespace(stop=lambda: actions.append("timer-stop"),
        deleteLater=lambda: actions.append("timer-delete"))
    adapter.native_filter = object()
    adapter.qt_filter = SimpleNamespace(deleteLater=lambda: actions.append("filter-delete"))
    adapter.app = SimpleNamespace(removeNativeEventFilter=lambda item: (_ for _ in ()).throw(RuntimeError("remove")))
    signal = SimpleNamespace(disconnect=lambda callback: actions.append("disconnect"))
    adapter.connections = [(signal, object())]
    window = SimpleNamespace(removeEventFilter=lambda item: actions.append("window-remove-filter"))
    assert adapter.dispose(window) == ["owned trace cleanup operation failed"]
    assert actions == ["timer-stop", "timer-delete", "window-remove-filter", "filter-delete", "disconnect"]
    assert adapter.connections == []


def test_filter_conversion_failures_mark_trace_incomplete_without_consuming_input():
    class Signal:
        def connect(self, callback):
            pass
        def disconnect(self, callback):
            pass

    class InertObject:
        def __init__(self, *args):
            pass
        def deleteLater(self):
            pass

    class InertTimer(InertObject):
        timeout = Signal()
        def setInterval(self, value):
            pass
        def start(self):
            pass
        def stop(self):
            pass

    native_filters, qt_filters = [], []
    window = SimpleNamespace(winId=lambda: 123, activeChanged=Signal(), activeFocusItemChanged=Signal(),
        installEventFilter=qt_filters.append, removeEventFilter=qt_filters.remove)
    adapter = object.__new__(_QtTraceAdapter)
    adapter.NativeFilter, adapter.QObject, adapter.QTimer = InertObject, InertObject, InertTimer
    adapter.ctypes, adapter.wintypes = ctypes, wintypes
    adapter.QEvent = SimpleNamespace()
    adapter.owns, adapter.is_valid = lambda window: True, lambda item: True
    adapter.snapshot = lambda window: {"qtActive": False}
    adapter.native_filter = adapter.qt_filter = adapter.timer = None
    adapter.connections = []
    adapter.app = SimpleNamespace(installNativeEventFilter=native_filters.append,
        removeNativeEventFilter=native_filters.remove, applicationStateChanged=Signal(),
        focusWindowChanged=Signal(), focusObjectChanged=Signal())
    trace = InputDeliveryTrace(window, disposable=True, adapter=adapter)
    trace.start()

    class BadNativeType:
        def __bytes__(self):
            raise RuntimeError("conversion")

    def bad_event_type():
        raise RuntimeError("type unavailable")

    assert native_filters[0].nativeEventFilter(BadNativeType(), 0) == (False, 0)
    assert qt_filters[0].eventFilter(window, SimpleNamespace(type=bad_event_type)) is False
    result = trace.stop()
    assert result["status"] == "INCOMPLETE" and result["observationErrors"] == 2
    failures = [row for row in result["events"] if row["kind"] == "trace-observation-error"]
    assert [row["stage"] for row in failures] == ["native-filter", "qt-window-filter"]
    assert native_filters == qt_filters == []
