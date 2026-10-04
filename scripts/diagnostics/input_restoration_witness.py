"""Owned disposable-window keyboard delivery witness; no global input injection.

The accepted timestamp is taken during a real QML key handler's signal delivery.
It measures deterministic posted-message acceptance, not human input latency,
physical keyboard timing, compositor presentation or scanout. Importing this
module does not load Qt or native libraries or create a window.
"""
from __future__ import annotations

import math
import time


SCOPE = ("Synthetic disposable-window PostMessage F24 delivery accepted by QML; "
         "GUI signal timestamp, not physical human input latency")
WITNESS_QML = b'''import QtQuick
Item {
    objectName: "CleanroomInputRestorationWitness"
    property var interactionOwner
    enabled: interactionOwner !== null && interactionOwner.isInteractive
    width: 1
    height: 1
    opacity: 0
    signal witnessPressed(int key, bool autoRepeat)
    signal witnessReleased(int key)
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_F24) {
            event.accepted = true
            witnessPressed(event.key, event.isAutoRepeat)
        }
    }
    Keys.onReleased: function(event) {
        if (event.key === Qt.Key_F24) {
            event.accepted = true
            witnessReleased(event.key)
        }
    }
}
'''
QT_KEY_F24 = 0x01000047


class InputRestorationWitness:
    """One asynchronous press/release proof, restricted to an owned fixture.

    ``record`` receives an event name and keyword evidence. ``finished`` receives
    one terminal dictionary after resource/focus cleanup. The adapter is injected
    only for no-window tests; the default lazily creates an owned Qt Quick Item
    and posts to the current process's one verified HWND. Keep this object alive
    until finished, and call cancel() before closing its fixture.
    """

    def __init__(self, window, engine, interaction_owner, *, record, finished,
                 disposable=False, timeout_ms=750, clock=time.perf_counter,
                 adapter=None):
        if disposable is not True:
            raise ValueError("Input witness requires an explicitly disposable fixture")
        if not isinstance(timeout_ms, (int, float)) or isinstance(timeout_ms, bool) or not math.isfinite(timeout_ms) or timeout_ms <= 0:
            raise ValueError("Input witness timeout must be finite and positive")
        self.window, self.engine, self.interaction_owner = window, engine, interaction_owner
        self.record, self.finished, self.clock = record, finished, clock
        self.timeout_ms = timeout_ms
        self.adapter = adapter
        self.item = self.component = self.previous_focus = None
        self.started = False
        self.result = None
        self.issued_seconds = self.deadline_seconds = self.accepted_seconds = None
        self.press_key = None
        self.release_consumed = False

    def _now(self):
        value = self.clock()
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise RuntimeError("Input witness requires finite QPC seconds")
        return value

    def _state(self):
        return {"nativeEnabled": bool(self.adapter.native_enabled(self.window)),
                "qmlInteractive": bool(self.interaction_owner.property("isInteractive")),
                "witnessFocused": self.item is not None and self.adapter.focused(self.window, self.item),
                "witnessEnabled": self.item is not None and bool(self.item.property("enabled"))}

    def start(self):
        if self.started or self.result is not None:
            raise RuntimeError("Input witness can issue only one key pair")
        self.started = True
        try:
            if self.adapter is None:
                self.adapter = _QtNativeAdapter()
            if not self.adapter.owns(self.window):
                raise RuntimeError("Input witness HWND is not owned by this fixture process")
            if not self.adapter.native_enabled(self.window) or not bool(self.interaction_owner.property("isInteractive")):
                raise RuntimeError("Input witness requires restored native and QML input")
            self.previous_focus = self.adapter.previous_focus(self.window)
            self.component, self.item = self.adapter.create(
                self.window, self.engine, self.interaction_owner, self._pressed, self._released)
            self.adapter.focus(self.item)
            state = self._state()
            if not all(state.values()):
                raise RuntimeError("Input witness could not own enabled keyboard focus")
            self.issued_seconds = self._now()
            self.deadline_seconds = self.issued_seconds + self.timeout_ms / 1000
            self.record("input-witness-issued", issuedSeconds=self.issued_seconds,
                        deadlineSeconds=self.deadline_seconds, scope=SCOPE, **state)
            if not self.adapter.post_pair(self.window):
                raise RuntimeError("Disposable HWND rejected the F24 message pair")
            if self.result is None:
                self.adapter.schedule(self.timeout_ms, self.poll)
        except Exception as exc:
            self._finish("FAIL", str(exc))
        return self

    def _pressed(self, key, auto_repeat):
        if self.result is not None or self.accepted_seconds is not None:
            return
        try:
            self._accept_press(key, auto_repeat)
        except Exception:
            self._finish("FAIL", "Input witness could not verify its delivered key or input state")

    def _accept_press(self, key, auto_repeat):
        observed = self._now()
        state = self._state()
        if key != QT_KEY_F24 or auto_repeat or self.issued_seconds is None or not (
                self.issued_seconds <= observed < self.deadline_seconds) or not all(state.values()):
            self._finish("FAIL", "Unexpected or late key delivery, focus or input state")
            return
        self.accepted_seconds, self.press_key = observed, key
        self.record("input-witness-accepted", acceptedSeconds=observed,
                    issuedSeconds=self.issued_seconds,
                    issueToAcceptedMs=(observed - self.issued_seconds) * 1000,
                    key="F24", scope=SCOPE, **state)

    def _released(self, key):
        # The QML handler accepts F24 before calling us, including a release
        # whose timing or corresponding press cannot qualify the witness.
        if key == QT_KEY_F24:
            self.release_consumed = True
        if self.result is not None:
            return
        try:
            self._accept_release(key)
        except Exception:
            self._finish("FAIL", "Input witness could not verify its consumed key release")

    def _accept_release(self, key):
        observed = self._now()
        if key != QT_KEY_F24 or self.accepted_seconds is None or not (
                self.accepted_seconds <= observed < self.deadline_seconds) or not all(self._state().values()):
            self._finish("FAIL", "F24 release was not consumed after its accepted press")
            return
        self.record("input-witness-release-consumed", releasedSeconds=observed,
                    key="F24", scope=SCOPE)
        self._finish("PASS", "Posted F24 press and release accepted by the owned QML Item")

    def poll(self):
        if self.result is not None:
            return
        try:
            self._poll_delivery()
        except Exception:
            self._finish("FAIL", "Input witness could not observe its bounded delivery deadline")

    def _poll_delivery(self):
        observed = self._now()
        if observed < self.issued_seconds:
            self._finish("FAIL", "Input witness QPC clock reversed")
        elif observed >= self.deadline_seconds:
            self._finish("FAIL", "No complete accepted F24 pair before bounded delivery deadline")
        else:
            self.adapter.schedule(max(1, math.ceil((self.deadline_seconds - observed) * 1000)), self.poll)

    def cancel(self):
        if self.result is None:
            self._finish("CANCELLED", "Owned fixture closed before input witness completed")

    def _finish(self, status, reason):
        if self.result is not None:
            return
        self.result = {"status": status, "reason": reason,
            "issuedSeconds": self.issued_seconds, "acceptedSeconds": self.accepted_seconds,
            "scope": SCOPE}
        if self.adapter is not None and self.item is not None:
            cleanup_allowed = True
            if status != "PASS":
                try:
                    quarantine = self.adapter.quarantine(
                        self.window, release_consumed=self.release_consumed,
                        record=self.record)
                    self.result["quarantine"] = quarantine
                    self.record("input-witness-quarantine", **quarantine)
                except Exception:
                    # Retain the window-owned witness until fixture teardown
                    # rather than expose its pending keys to previous content.
                    cleanup_allowed = False
                    self.result.update(status="FAIL", cleanupFailure=True,
                        focusCleanupDeferred=True,
                        reason="Input witness could not quarantine its pending F24 messages")
            try:
                if cleanup_allowed:
                    self.adapter.dispose(self.window, self.item, self.component, self.previous_focus)
            except Exception:
                self.result.update(status="FAIL", cleanupFailure=True,
                    reason="Input witness could not release its owned focus and Item")
            self.item = self.component = self.previous_focus = None
        self.record("input-witness-finished", **self.result)
        self.finished(dict(self.result))


class _QtNativeAdapter:
    """Lazy Qt/native operations; no desktop activation and no global key API."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        import os
        from PySide6.QtCore import QTimer, QUrl, Qt
        from PySide6.QtQml import QQmlComponent
        from shiboken6 import isValid
        self.ctypes, self.wintypes, self.pid = ctypes, wintypes, os.getpid()
        self.QTimer, self.QUrl, self.Qt = QTimer, QUrl, Qt
        self.QQmlComponent, self.is_valid = QQmlComponent, isValid
        self.posted_down = self.posted_up = False
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user.IsWindowEnabled.argtypes = [wintypes.HWND]
        self.user.IsWindowEnabled.restype = wintypes.BOOL
        self.user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user.PostMessageW.restype = wintypes.BOOL

    def owns(self, window):
        if not self.is_valid(window):
            return False
        process = self.wintypes.DWORD()
        thread = self.user.GetWindowThreadProcessId(int(window.winId()), self.ctypes.byref(process))
        return bool(thread) and process.value == self.pid

    def native_enabled(self, window):
        return self.is_valid(window) and bool(self.user.IsWindowEnabled(int(window.winId())))

    def previous_focus(self, window):
        return window.activeFocusItem()

    def create(self, window, engine, owner, pressed, released):
        component = self.QQmlComponent(engine)
        component.setData(WITNESS_QML, self.QUrl("file:///CleanroomInputRestorationWitness.qml"))
        if not component.isReady():
            component.deleteLater()
            raise RuntimeError("Input witness QML failed to compile")
        item = component.createWithInitialProperties({"parent": window.contentItem(), "interactionOwner": owner})
        if item is None:
            component.deleteLater()
            raise RuntimeError("Input witness QML failed to instantiate")
        item.setParent(window.contentItem())
        item.witnessPressed.connect(pressed, self.Qt.DirectConnection)
        item.witnessReleased.connect(released, self.Qt.DirectConnection)
        return component, item

    def focus(self, item):
        item.forceActiveFocus(self.Qt.OtherFocusReason)

    def focused(self, window, item):
        return self.is_valid(window) and self.is_valid(item) and window.activeFocusItem() == item

    def post_pair(self, window):
        self.posted_down = self.posted_up = False
        if not self.owns(window):
            return False
        hwnd, key = int(window.winId()), 0x87  # VK_F24, not text/character input.
        # Repeat count 1; key-up sets previous-state/transition bits. Both
        # messages go only to this HWND; no foreground or global input changes.
        self.posted_down = bool(self.user.PostMessageW(hwnd, 0x0100, key, 1))
        if self.posted_down:
            self.posted_up = bool(self.user.PostMessageW(hwnd, 0x0101, key, 0xC0000001))
        return self.posted_down and self.posted_up

    def quarantine(self, window, *, release_consumed, record):
        """Consume only this failed witness's F24 keys on its owned window.

        A successful pair was already consumed by QML. A failed pair can still
        be queued when focus is restored, so keep a window-parented filter until
        its queued release is consumed or the disposable window is destroyed.
        A partially posted press has no queued release: retain its filter until
        window destruction. There is no application/global filter or wait.
        """
        down, up = self.posted_down, self.posted_up
        evidence = {"installed": False, "downPosted": down, "upPosted": up,
                    "releaseAlreadyConsumed": release_consumed,
                    "scope": "Owned disposable QWindow F24 press/release only"}
        if not down or release_consumed:
            return {**evidence, "reason": "No pending posted F24 pair"}
        if not self.owns(window):
            return {**evidence, "reason": "Owned disposable window no longer exists"}

        from PySide6.QtCore import QEvent, QObject

        class F24Quarantine(QObject):
            def __init__(self):
                super().__init__(window)
                self.owner = window
                window.destroyed.connect(self.owner_destroyed)

            def owner_destroyed(self):
                self.owner = None

            def eventFilter(self, watched, event):
                kind = event.type()
                if watched != self.owner or kind not in (QEvent.KeyPress, QEvent.KeyRelease) or event.key() != QT_KEY_F24:
                    return False
                event.accept()
                # Diagnostic reporting cannot make an already quarantined key
                # continue to the previous content if its recorder has closed.
                try:
                    record("input-witness-quarantine-consumed",
                           key="F24", eventType="press" if kind == QEvent.KeyPress else "release",
                           scope=evidence["scope"])
                except Exception:
                    pass
                if kind == QEvent.KeyRelease and up:
                    owner = self.owner
                    owner.removeEventFilter(self)
                    owner._cleanroom_f24_quarantines.remove(self)
                    self.owner = None
                    self.deleteLater()
                return True

        quarantine = F24Quarantine()
        # QObject parenting protects native lifetime; the window reference also
        # retains the Python override after this adapter/witness is released.
        if not hasattr(window, "_cleanroom_f24_quarantines"):
            window._cleanroom_f24_quarantines = []
        window._cleanroom_f24_quarantines.append(quarantine)
        window.installEventFilter(quarantine)
        return {**evidence, "installed": True,
                "removeAfter": "queued F24 release" if up else "owned window destruction"}

    def schedule(self, milliseconds, callback):
        self.QTimer.singleShot(math.ceil(milliseconds), callback)

    def dispose(self, window, item, component, previous):
        if self.is_valid(item):
            if self.focused(window, item):
                if previous is not None and self.is_valid(previous) and previous.window() == window:
                    previous.forceActiveFocus(self.Qt.OtherFocusReason)
                else:
                    item.setFocus(False)
            item.deleteLater()
        if component is not None and self.is_valid(component):
            component.deleteLater()
