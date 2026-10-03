"""Explicit, process-local selector for the isolated transition experiment.

No ordinary settings field or persisted production preference is introduced.
"""
import logging
import os
import weakref

from PySide6.QtCore import QObject, Property, QElapsedTimer, Signal, Slot


class TransitionExperiment(QObject):
    ENGINES = frozenset(("production", "single-clock", "native-composition"))
    engineChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._owners = []
        self._clock = QElapsedTimer()
        self._clock.start()
        selected = os.environ.get("CSPM_EXPERIMENTAL_TRANSITION", "production")
        if selected not in self.ENGINES:
            logging.getLogger(__name__).warning(
                "Unknown experimental transition selector; using production"
            )
            selected = "production"
        self._engine = selected
        self._reduced = os.environ.get("CSPM_EXPERIMENTAL_REDUCED_MOTION") == "1"
        logging.getLogger(__name__).info("Window transition engine=%s", selected)

    @Property(str, notify=engineChanged)
    def engine(self):
        return self._engine

    @Property(bool, constant=True)
    def reducedMotion(self):
        return self._reduced

    @Slot(result=float)
    def monotonicMs(self):
        return self._clock.nsecsElapsed() / 1_000_000

    @Slot(QObject)
    def registerWindow(self, window):
        if not any(ref() is window for ref in self._owners):
            self._owners.append(weakref.ref(window))

    @Slot(str, result=bool)
    def setEngine(self, selected):
        if selected not in self.ENGINES:
            logging.getLogger(__name__).warning("Rejected transition engine selection")
            return False
        for ref in self._owners:
            owner = ref()
            if owner is None:
                continue
            try:
                if owner.property("professionalWindowTransitionActive"):
                    logging.getLogger(__name__).warning(
                        "Rejected transition engine change during active transaction"
                    )
                    return False
            except RuntimeError:
                continue
        if selected != self._engine:
            self._engine = selected
            logging.getLogger(__name__).info("Window transition engine=%s", selected)
            self.engineChanged.emit()
        return True
