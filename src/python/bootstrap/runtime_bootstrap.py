from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO

from PySide6.QtCore import QtMsgType, qInstallMessageHandler


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that tolerates Windows file-lock rollover failures."""

    def doRollover(self) -> None:  # noqa: N802 - stdlib override name
        try:
            super().doRollover()
        except PermissionError:
            if self.stream is None and not self.delay:
                self.stream = self._open()
        except OSError as exc:
            if getattr(exc, "winerror", None) == 32:
                if self.stream is None and not self.delay:
                    self.stream = self._open()
            else:
                raise

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802 - stdlib override name
        # Prevent Python's internal "--- Logging error ---" traceback flood.
        return

_fault_log_stream: TextIO | None = None


def _resolve_log_dir(log_dir: Path | None = None) -> Path:
    if log_dir is not None:
        return Path(log_dir)
    return Path(__file__).resolve().parents[3] / "logs"


def setup_global_logging(log_dir: Path | None = None) -> logging.Logger:
    resolved_log_dir = _resolve_log_dir(log_dir)
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    log_file = resolved_log_dir / "cspm.log"
    trace_mode = "--trace-docket" in sys.argv or os.environ.get("CSPM_DOCKET_TRACE") == "1"
    level = logging.DEBUG if trace_mode else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Do not let logging handler rollover issues flood the terminal.
    logging.raiseExceptions = False

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    file_handler = SafeRotatingFileHandler(
        str(log_file),
        mode='w',
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    
    verbose_terminal = os.environ.get("CSPM_VERBOSE_LOGGING", "0") == "1"
    if not verbose_terminal and not trace_mode:
        stream_handler.setLevel(logging.WARNING)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    return root_logger


def qt_message_handler(mode: QtMsgType, context: Any, message: str) -> None:
    logger = logging.getLogger("QML")
    if mode == QtMsgType.QtWarningMsg:
        logger.warning(message)
    elif mode == QtMsgType.QtCriticalMsg:
        logger.error(message)
    elif mode == QtMsgType.QtFatalMsg:
        logger.critical(message)
    else:
        logger.debug(message)


def install_qt_message_bridge() -> None:
    qInstallMessageHandler(qt_message_handler)


def bootstrap_logging_and_qt_bridge(log_dir: Path | None = None) -> logging.Logger:
    logger = setup_global_logging(log_dir)
    install_qt_message_bridge()
    return logger


def _exc_info_tuple(
    exc_type: Any,
    exc_value: Any,
    exc_traceback: Any,
) -> (
    tuple[type[BaseException], BaseException, TracebackType | None]
    | tuple[None, None, None]
):
    if (
        isinstance(exc_type, type)
        and issubclass(exc_type, BaseException)
        and isinstance(exc_value, BaseException)
    ):
        return (exc_type, exc_value, exc_traceback)
    return (None, None, None)


def _log_uncaught_exception(exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
    if isinstance(exc_type, type) and issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger("crash").critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


def _log_thread_exception(args: Any) -> None:
    logging.getLogger("crash").critical(
        "Unhandled thread exception [thread=%s]",
        getattr(getattr(args, "thread", None), "name", "<unknown>"),
        exc_info=_exc_info_tuple(args.exc_type, args.exc_value, args.exc_traceback),
    )


def _log_unraisable_exception(unraisable: Any) -> None:
    exc_value = getattr(unraisable, "exc_value", None)
    exc_type = getattr(
        unraisable,
        "exc_type",
        type(exc_value) if exc_value else Exception,
    )
    exc_traceback = getattr(unraisable, "exc_traceback", None)
    logging.getLogger("crash").critical(
        "Unraisable exception [object=%r, message=%s]",
        getattr(unraisable, "object", None),
        getattr(unraisable, "err_msg", ""),
        exc_info=_exc_info_tuple(exc_type, exc_value, exc_traceback),
    )


def install_global_exception_hooks(log_dir: Path | None = None) -> None:
    global _fault_log_stream
    sys.excepthook = _log_uncaught_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = _log_thread_exception
    if hasattr(sys, "unraisablehook"):
        sys.unraisablehook = _log_unraisable_exception
    try:
        import faulthandler

        resolved_log_dir = _resolve_log_dir(log_dir)
        resolved_log_dir.mkdir(parents=True, exist_ok=True)
        fault_log = resolved_log_dir / "faults.log"
        _fault_log_stream = open(fault_log, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_log_stream, all_threads=True)
    except Exception:
        logging.getLogger("crash").debug("Could not enable faulthandler.", exc_info=True)


def report_terminal_failure(message: str) -> None:
    text = str(message or "").strip()
    if not text:
        return
    try:
        sys.stderr.write(text + os.linesep)
        sys.stderr.flush()
    except Exception:
        pass


def report_nonfatal_startup_failure(context: str, exc: BaseException) -> None:
    logging.getLogger("startup").warning(
        "Non-fatal startup/shutdown failure [context=%s]: %s",
        str(context or "unknown"),
        str(exc),
        exc_info=(type(exc), exc, exc.__traceback__),
    )

