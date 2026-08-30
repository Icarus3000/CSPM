from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shell_preload_is_async_and_component_errors_are_not_retried() -> None:
    bootstrap = (ROOT / "src" / "qml" / "BootstrapRoot.qml").read_text(encoding="utf-8")
    main_py = (ROOT / "src" / "python" / "main.py").read_text(encoding="utf-8")

    assert 'Qt.createComponent("DetachedShellWindow.qml", Component.Asynchronous)' in bootstrap
    assert "signal mainWindowLoadFailed(string message)" in bootstrap
    assert "function _failMainWindowLoad(reason)" in bootstrap
    assert '_failMainWindowLoad("component-error:" + reason)' in bootstrap
    assert '_failMainWindowLoad("component-status-error")' in bootstrap
    assert '_scheduleCreateRetry("component-error:" + reason' not in bootstrap
    assert '_scheduleCreateRetry("component-status-error"' not in bootstrap
    assert "def _handle_main_window_load_failure(message: str)" in main_py
    assert "main_window_load_failed.connect(_handle_main_window_load_failure)" in main_py
    assert "QTimer.singleShot(1500, app.quit)" in main_py
