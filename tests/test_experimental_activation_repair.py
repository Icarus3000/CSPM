"""Actual fixture icon/activation helpers without loading the CSPM application."""
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/python/main.py"


def helper_namespace(*, repair=False, window_class=None):
    # Execute the reviewed real helper declarations only. Importing main would
    # initialize application/data/runtime globals beyond this safe unit scope.
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer
    from PySide6.QtGui import QIcon, QWindow
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"_apply_app_icon_to_window", "_AppIconSync", "_StartupInputProbe"}
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in names]
    namespace = {"QObject": QObject, "QEvent": QEvent, "QTimer": QTimer,
        "QIcon": QIcon, "QWindow": window_class or QWindow,
        "QApplication": QCoreApplication, "Any": Any,
        "Optional": Any, "_env_flag": lambda name, default=False: repair
            if name == "CSPM_EXPERIMENTAL_ACTIVATION_REPAIR" else default,
        "_APP_ICON_SYNC_EVENT_TYPES": {QEvent.PlatformSurface, QEvent.Show, QEvent.WindowActivate},
        "_report_nonfatal_startup_failure": lambda *_: None}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def test_actual_icon_helper_repair_avoids_all_item_icon_work_and_preserves_recursion():
    from PySide6.QtCore import QCoreApplication, QEvent, QObject
    from PySide6.QtQuick import QQuickItem
    from shiboken6 import delete
    app = QCoreApplication.instance() or QCoreApplication([])
    root = QQuickItem()
    children = [QQuickItem(root) for _ in range(63)]

    class Recipient(QObject):
        def __init__(self):
            super().__init__()
            self.events = []
        def eventFilter(self, watched, event):
            if event.type() in (QEvent.WindowActivate, QEvent.WindowDeactivate):
                self.events.append(event.type())
            return False

    leaf = Recipient()
    children[-1].installEventFilter(leaf)
    attempts = []
    for repair in (False, True):
        namespace = helper_namespace(repair=repair)
        original = namespace["_apply_app_icon_to_window"]
        namespace["_apply_app_icon_to_window"] = lambda watched, icon: (
            attempts.append(watched), original(watched, icon))[1]
        sync = namespace["_AppIconSync"](app, SimpleNamespace(isNull=lambda: False))
        app.installEventFilter(sync)
        try:
            before = len(attempts)
            for kind in (QEvent.WindowActivate, QEvent.WindowDeactivate):
                assert QCoreApplication.sendEvent(root, QEvent(kind))
            assert len(attempts) - before == (0 if repair else 64)
        finally:
            app.removeEventFilter(sync)
            # Queued ordinary callbacks retain the object until the next loop.
            app.processEvents()
            sync.deleteLater()
            app.sendPostedEvents(None, QEvent.DeferredDelete)
    assert leaf.events == [QEvent.WindowActivate, QEvent.WindowDeactivate] * 2
    children[-1].removeEventFilter(leaf)
    delete(leaf)
    delete(root)


@pytest.mark.parametrize("repair", [False, True])
def test_real_window_discovery_events_keep_icons_and_coalesce_apply_for_later_windows(repair):
    from PySide6.QtCore import QCoreApplication, QEvent, QObject
    app = QCoreApplication.instance() or QCoreApplication([])

    class Window(QObject):
        def __init__(self):
            super().__init__()
            self.icons = []
        def setIcon(self, icon):
            self.icons.append(icon)

    namespace = helper_namespace(repair=repair, window_class=Window)
    scheduled, app_icons, windows = [], [], [Window()]
    namespace["QTimer"] = SimpleNamespace(singleShot=lambda ms, callback: scheduled.append((ms, callback)))
    icon = SimpleNamespace(isNull=lambda: False)
    fixture_app = SimpleNamespace(setWindowIcon=app_icons.append, topLevelWindows=lambda: list(windows))
    sync = namespace["_AppIconSync"](app, icon)
    sync._app = fixture_app
    assert sync.eventFilter(windows[0], QEvent(QEvent.Show)) is False
    assert sync.eventFilter(windows[0], QEvent(QEvent.WindowActivate)) is False
    assert windows[0].icons == [icon, icon] and len(scheduled) == 1
    new_window = Window()
    windows.append(new_window)
    assert sync.eventFilter(new_window, QEvent(QEvent.PlatformSurface)) is False
    assert new_window.icons == [icon] and len(scheduled) == 1
    scheduled.pop()[1]()
    assert app_icons == [icon] and not sync._pending_apply
    assert windows[0].icons == [icon, icon, icon] and new_window.icons == [icon, icon]
    sync.queue_apply_all()
    assert len(scheduled) == 1
    scheduled.pop()[1]()
    for obj in (sync, *windows):
        obj.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)


def test_startup_input_probe_still_handles_each_recognized_input_and_notifies_after_first_capture():
    import logging
    import time
    from PySide6.QtCore import QCoreApplication, QEvent
    app = QCoreApplication.instance() or QCoreApplication([])
    namespace = helper_namespace(repair=True)
    calls = []
    namespace.update(logging=logging, time=time, t0=time.perf_counter(),
        _startup_first_input_perf=None, _startup_first_input_label=None,
        _splash_first_pixel_perf=None, _splash_gone_perf=None,
        _startup_input_notify_callback=calls.append)
    probe = namespace["_StartupInputProbe"](app)
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick,
            QEvent.KeyPress, QEvent.TouchBegin, QEvent.Wheel):
        assert probe.eventFilter(None, QEvent(kind)) is False
    assert calls == ["mouse-press", "mouse-double-click", "key-press", "touch-begin", "wheel"]
    assert namespace["_startup_first_input_label"] == "mouse-press" and probe._captured
    assert probe.eventFilter(None, QEvent(QEvent.WindowActivate)) is False
    assert len(calls) == 5
    probe.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)


def test_only_experimental_branch_omits_the_effect_free_global_splash_filter():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    guarded = [node for node in ast.walk(tree) if isinstance(node, ast.If)
        and ast.unparse(node.test) == "not _env_flag('CSPM_EXPERIMENTAL_ACTIVATION_REPAIR', False)"]
    assert len(guarded) == 1
    body = ast.unparse(guarded[0])
    assert "class GlobalSplashSkipFilter" in body and "app.installEventFilter(_splash_skip_filter)" in body
    filter_class = next(node for node in guarded[0].body if isinstance(node, ast.ClassDef))
    handler = next(node for node in filter_class.body if isinstance(node, ast.FunctionDef))
    assert len(handler.body) == 1 and isinstance(handler.body[0], ast.Return)
    assert handler.body[0].value.value is False
