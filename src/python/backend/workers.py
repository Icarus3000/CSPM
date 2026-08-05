from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QThreadPool

logger = logging.getLogger("cspm.workers")

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    
    finished: No data
    error: tuple (exctype, value, traceback.format_exc() )
    result: object data returned from processing, anything
    progress: int indicating % progress
    """
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    """
    Worker thread
    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.
    """

    def __init__(self, fn: Callable, *args: Any, name: str = "", **kwargs: Any) -> None:
        super().__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._worker_name = name or getattr(fn, "__name__", "<anonymous>")

        # Add the callback to our kwargs if the function needs to report progress
        # self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self) -> None:
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            tb_str = traceback.format_exc()
            try:
                exctype, value = type(None), None
                import sys as _sys
                exctype, value = _sys.exc_info()[:2]
            except Exception:
                pass
            logger.exception(
                "Worker task raised an unhandled exception [worker=%s]",
                self._worker_name,
            )
            # Guard against signal source being deleted during teardown
            try:
                self.signals.error.emit((exctype, value, tb_str))
            except (RuntimeError, AttributeError):
                logger.debug("Could not emit error signal (source deleted)")
        else:
            # Guard against signal source being deleted during teardown
            try:
                self.signals.result.emit(result)  # Return the result of the processing
            except (RuntimeError, AttributeError):
                logger.debug("Could not emit result signal (source deleted)")
        finally:
            # Guard against signal source being deleted during teardown
            try:
                self.signals.finished.emit()  # Done
            except (RuntimeError, AttributeError):
                logger.debug("Could not emit finished signal (source deleted)")
