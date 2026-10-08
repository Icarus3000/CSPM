"""Activation fixture spans; no desktop window, WebEngine or input APIs."""
from pathlib import Path
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/diagnostics"))
from activation_cost_profile import ActivationCostProfile


@pytest.fixture
def fixture():
    window, other, now = object(), object(), [10.0]
    adapter = SimpleNamespace(owns=lambda obj: obj is window,
        QEvent=SimpleNamespace(WindowActivate=24, WindowDeactivate=25, FocusIn=8, FocusOut=9))
    profile = ActivationCostProfile(window, disposable=True, clock=lambda: now[0], adapter=adapter)
    return SimpleNamespace(profile=profile, window=window, other=other, now=now,
        event=lambda kind: SimpleNamespace(type=lambda: kind))


def test_owned_activation_dispatch_is_once_with_exact_nested_icon_spans_and_restored_hooks(fixture):
    f, calls = fixture, []

    def apply_window(window, icon):
        calls.append(("apply-window", window))
        f.now[0] += .004
        return True

    entry = SimpleNamespace(_apply_app_icon_to_window=apply_window)

    class Icon:
        def eventFilter(self, watched, event):
            calls.append(("icon-filter", watched))
            entry._apply_app_icon_to_window(watched, object())
            f.now[0] += .002
            return False

        def apply_all(self):
            calls.append(("apply-all",))
            entry._apply_app_icon_to_window(f.window, object())

    entry._AppIconSync = Icon
    originals = (entry._apply_app_icon_to_window, Icon.eventFilter, Icon.apply_all)
    f.profile.start(entry)
    icon = Icon()

    def dispatch():
        calls.append(("notify",))
        assert icon.eventFilter(f.window, f.event(24)) is False
        f.now[0] += .400
        return "original result"

    assert f.profile.notify(f.window, f.event(24), dispatch) == "original result"
    icon.apply_all()
    # The same callbacks for another window must execute but cannot create an
    # owned-window profile row or expose the foreign object in evidence.
    assert icon.eventFilter(f.other, f.event(24)) is False
    result = f.profile.stop()
    assert result["status"] == "COMPLETE"
    rows = result["events"]
    assert [r["stage"] for r in rows] == ["qt-notify", "icon-apply-owned-window",
        "icon-apply-all", "icon-apply-owned-window"]
    by_stage = {r["stage"]: r for r in rows[:2]}
    assert by_stage["qt-notify"]["inclusiveMs"] == pytest.approx(406)
    assert by_stage["qt-notify"]["exclusiveHookMs"] == pytest.approx(402)
    assert by_stage["icon-apply-owned-window"]["inclusiveMs"] == pytest.approx(4)
    assert all(set(r) == {"stage", "beginSeconds", "endSeconds", "inclusiveMs",
        "exclusiveHookMs", "spanId", "parentSpanId", "status"} | ({"eventKind"} if r["stage"] == "qt-notify" else set()) for r in rows)
    assert (entry._apply_app_icon_to_window, Icon.eventFilter, Icon.apply_all) == originals
    assert f.profile.stop() is result
    assert calls.count(("notify",)) == 1


@pytest.mark.parametrize("kind,foreign", [(24, True), (8, True), (1, False)])
def test_foreign_and_nonactivation_events_have_unchanged_dispatch_without_measurement(fixture, kind, foreign):
    f, calls = fixture, []
    f.profile.start()
    assert f.profile.notify(f.other if foreign else f.window, f.event(kind), lambda: calls.append(1)) is None
    assert calls == [1] and f.profile.stop()["events"] == []


def test_focus_in_and_dispatch_exception_are_profiled_without_changing_exception(fixture):
    f = fixture
    f.profile.start()

    def dispatch():
        f.now[0] += .020
        raise LookupError("must remain the original exception")

    with pytest.raises(LookupError, match="original exception"):
        f.profile.notify(f.window, f.event(8), dispatch)
    row = f.profile.stop()["events"][0]
    assert row["eventKind"] == "focus-in" and row["status"] == "RAISED"
    assert row["inclusiveMs"] == pytest.approx(20)
    assert "exception" not in row


@pytest.mark.parametrize("kind,label", [(25,"window-deactivate"), (9,"focus-out")])
def test_source_deactivation_dispatch_is_measured_once_without_changing_delivery(fixture, kind, label):
    f, calls = fixture, []
    f.profile.start()

    def dispatch():
        calls.append(kind)
        f.now[0] += .175
        return False

    assert f.profile.notify(f.window, f.event(kind), dispatch) is False
    result = f.profile.stop()
    assert calls == [kind] and result["status"] == "COMPLETE"
    assert len(result["events"]) == 1
    row = result["events"][0]
    assert row["eventKind"] == label and row["inclusiveMs"] == pytest.approx(175)


def test_clock_error_and_event_conversion_are_passive_and_mark_incomplete(fixture):
    f, calls = fixture, []
    f.profile.start()
    f.now[0] = float("nan")
    assert f.profile.notify(f.window, f.event(24), lambda: calls.append(1)) is None
    event = SimpleNamespace(type=lambda: (_ for _ in ()).throw(RuntimeError("type")))
    f.profile.notify(f.window, event, lambda: calls.append(2))
    result = f.profile.stop()
    assert calls == [1, 2] and result["status"] == "INCOMPLETE"
    assert result["observationErrors"] == 2 and result["events"] == []


def test_bounded_overflow_and_stopped_profile_do_not_affect_dispatch(fixture):
    f, calls = fixture, []
    f.profile.capacity = 1
    f.profile.start()
    for _ in range(3):
        f.profile.notify(f.window, f.event(24), lambda: calls.append(1))
    result = f.profile.stop()
    assert len(result["events"]) == 1 and result["droppedRows"] == 2
    assert result["status"] == "INCOMPLETE"
    f.profile.notify(f.window, f.event(24), lambda: calls.append(2))
    assert calls == [1, 1, 1, 2]


def test_failed_hook_installation_restores_partial_hooks(fixture):
    entry = SimpleNamespace(_apply_app_icon_to_window=lambda *args: True)
    original = entry._apply_app_icon_to_window
    with pytest.raises(AttributeError):
        fixture.profile.start(entry)
    assert entry._apply_app_icon_to_window is original and fixture.profile.closed


def test_hook_restoration_does_not_overwrite_later_fixture_edit(fixture):
    class Icon:
        def eventFilter(self, *args):
            return False
        def apply_all(self):
            pass
    entry = SimpleNamespace(_AppIconSync=Icon, _apply_app_icon_to_window=lambda *args: True)
    fixture.profile.start(entry)
    later = lambda *args: "later"
    entry._apply_app_icon_to_window = later
    result = fixture.profile.stop()
    assert entry._apply_app_icon_to_window is later
    assert result["status"] == "INCOMPLETE" and len(result["cleanupErrors"]) == 1


def test_authorization_ownership_and_parameter_gates_precede_hooks(fixture):
    with pytest.raises(ValueError, match="disposable"):
        ActivationCostProfile(None)
    for capacity in (0, 4097, True, 1.5):
        with pytest.raises(ValueError, match="capacity"):
            ActivationCostProfile(None, disposable=True, capacity=capacity)
    fixture.profile.window = fixture.other
    with pytest.raises(RuntimeError, match="not owned"):
        fixture.profile.start()


def test_runtime_qt_virtual_filter_is_unchanged_while_ordinary_icon_hooks_dispatch():
    # QObject delivery verifies ordinary callbacks used by an unchanged Qt
    # virtual method, without a QQuickWindow, HWND or WebEngine.
    from PySide6.QtCore import QCoreApplication, QEvent, QObject
    from shiboken6 import delete

    application = QCoreApplication.instance() or QCoreApplication([])
    window, other, calls = QObject(), QObject(), []
    entry = SimpleNamespace(_apply_app_icon_to_window=lambda watched, icon: calls.append(watched))

    class Icon(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.WindowActivate:
                entry._apply_app_icon_to_window(watched, object())
            return False
        def apply_all(self):
            pass

    entry._AppIconSync = Icon
    icon = Icon()
    window.installEventFilter(icon)
    other.installEventFilter(icon)
    adapter = SimpleNamespace(owns=lambda watched: watched == window, QEvent=QEvent)
    original_filter = Icon.eventFilter
    profile = ActivationCostProfile(window, disposable=True, adapter=adapter).start(entry)
    assert Icon.eventFilter is original_filter
    event = QEvent(QEvent.WindowActivate)
    profile.notify(window, event, lambda: QCoreApplication.sendEvent(window, event))
    QCoreApplication.sendEvent(other, QEvent(QEvent.WindowActivate))
    result = profile.stop()
    assert result["status"] == "COMPLETE"
    assert [r["stage"] for r in result["events"]] == ["qt-notify", "icon-apply-owned-window"]
    assert calls == [window, other]
    QCoreApplication.sendEvent(window, QEvent(QEvent.WindowActivate))
    assert calls == [window, other, window]
    assert len(profile.rows) == 2
    window.removeEventFilter(icon)
    other.removeEventFilter(icon)
    for obj in (icon, window, other):
        delete(obj)


def test_qcore_notify_override_and_ordinary_hooks_complete_in_isolated_no_window_process():
    source = textwrap.dedent('''
        from types import SimpleNamespace
        from PySide6.QtCore import QCoreApplication, QEvent, QObject
        from shiboken6 import delete
        from activation_cost_profile import ActivationCostProfile

        class FixtureApplication(QCoreApplication):
            def notify(self, watched, event):
                profile = getattr(self, "activation_profile", None)
                dispatch = lambda: super(FixtureApplication, self).notify(watched, event)
                return profile.notify(watched, event, dispatch) if profile is not None else dispatch()

        app = FixtureApplication([])
        window, other, calls = QObject(), QObject(), []
        entry = SimpleNamespace(_apply_app_icon_to_window=lambda watched, icon: calls.append(watched))

        class Icon(QObject):
            def eventFilter(self, watched, event):
                if event.type() == QEvent.WindowActivate:
                    entry._apply_app_icon_to_window(watched, object())
                return False
            def apply_all(self):
                entry._apply_app_icon_to_window(window, object())

        entry._AppIconSync = Icon
        icon = Icon()
        window.installEventFilter(icon)
        other.installEventFilter(icon)
        original_filter = Icon.eventFilter
        app.activation_profile = ActivationCostProfile(window, disposable=True,
            adapter=SimpleNamespace(owns=lambda candidate: candidate == window, QEvent=QEvent)).start(entry)
        assert Icon.eventFilter is original_filter
        QCoreApplication.sendEvent(window, QEvent(QEvent.WindowActivate))
        QCoreApplication.sendEvent(other, QEvent(QEvent.WindowActivate))
        icon.apply_all()
        QCoreApplication.sendEvent(window, QEvent(QEvent.WindowDeactivate))
        result = app.activation_profile.stop()
        app.activation_profile = None
        assert result["status"] == "COMPLETE", result
        assert [row["stage"] for row in result["events"]] == ["qt-notify", "icon-apply-owned-window", "icon-apply-all", "icon-apply-owned-window", "qt-notify"]
        assert result["events"][-1]["eventKind"] == "window-deactivate"
        assert calls == [window, other, window]
        QCoreApplication.sendEvent(window, QEvent(QEvent.WindowActivate))
        assert calls == [window, other, window, window]
        window.removeEventFilter(icon)
        other.removeEventFilter(icon)
        for obj in (icon, window, other):
            delete(obj)
        app.processEvents()
        print("owned notify and ordinary callbacks complete; no window created")
    ''')
    diagnostics = Path(__file__).resolve().parents[1] / "scripts/diagnostics"
    result = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, "
        + repr(str(diagnostics)) + ");\n" + source], capture_output=True, text=True,
        timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ordinary callbacks complete" in result.stdout
