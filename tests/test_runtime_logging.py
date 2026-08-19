"""Regression coverage for durable application diagnostic logs."""

import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from bootstrap import runtime_bootstrap  # noqa: E402
from bootstrap.runtime_bootstrap import setup_global_logging  # noqa: E402


def _close_root_handlers() -> None:
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()


def test_application_log_appends_and_marks_each_launch(tmp_path):
    """A later launch must extend the prior log rather than replacing it."""
    _close_root_handlers()
    try:
        first_logger = setup_global_logging(tmp_path)
        first_logger.info("first-launch-evidence")
        _close_root_handlers()

        second_logger = setup_global_logging(tmp_path)
        second_logger.info("second-launch-evidence")
        _close_root_handlers()

        text = (tmp_path / "cspm.log").read_text(encoding="utf-8")
        assert text.count("=== CSPM APPLICATION START ") == 2
        assert "first-launch-evidence" in text
        assert "second-launch-evidence" in text
        assert "[INFO]" in text
    finally:
        _close_root_handlers()


def test_packaged_log_directory_is_outside_the_replaceable_release_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_bootstrap.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))

    assert runtime_bootstrap._resolve_log_dir() == tmp_path / "LocalAppData" / "CSPM" / "logs"
