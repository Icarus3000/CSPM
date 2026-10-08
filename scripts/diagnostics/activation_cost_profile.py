"""Bounded passive activation CPU spans in an explicitly disposable fixture.

The caller brackets its QApplication.notify implementation with notify(). Icon
hooks affect only the fixture's imported Python module, are restored on stop(),
and never change dispatch results. No inputs or activation requests are issued.
Importing this module does not load Qt or a native library.
"""
from __future__ import annotations

import math
import time


SCOPE = ("Disposable owned-window Qt activation notify and fixture icon callback "
         "wall-clock spans; inclusive/exclusive observed hooks, not pure Qt CPU, "
         "GPU completion, physical input or scanout")


class ActivationCostProfile:
    def __init__(self, window, *, disposable=False, capacity=512,
                 clock=time.perf_counter, adapter=None):
        if disposable is not True:
            raise ValueError("Activation profile requires an explicitly disposable fixture")
        if type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ValueError("Activation profile capacity must be an integer in 1..4096")
        self.window, self.adapter, self.clock = window, adapter, clock
        self.capacity, self.rows = capacity, []
        self.started = self.closed = False
        self.dropped_rows = self.observation_errors = 0
        self.stack, self.hooks = [], []
        self.next_span = 0
        self.stop_result = None

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise RuntimeError("Activation profile requires finite QPC seconds")
        return value

    def start(self, entry=None):
        if self.started or self.closed:
            raise RuntimeError("Activation profile can start only once")
        if self.adapter is None:
            from input_delivery_trace import _QtTraceAdapter
            self.adapter = _QtTraceAdapter()
        if not self.adapter.owns(self.window):
            raise RuntimeError("Activation profile HWND is not owned by this fixture process")
        self.started = True
        if entry is not None:
            try:
                self._install_icon_hooks(entry)
            except Exception:
                self.stop()
                raise
        return self

    def _event_kind(self, watched, event):
        if self.closed or not self.started:
            return None
        try:
            if watched != self.window:
                return None
            kind = event.type()
            return ("window-activate" if kind == self.adapter.QEvent.WindowActivate
                    else "window-deactivate" if kind == self.adapter.QEvent.WindowDeactivate
                    else "focus-in" if kind == self.adapter.QEvent.FocusIn
                    else "focus-out" if kind == self.adapter.QEvent.FocusOut else None)
        except Exception:
            self.observation_errors += 1
            return None

    def notify(self, watched, event, dispatch):
        """Call the real notify once, bracketing owned activation/deactivation.

        Integrate at the fixture QApplication subclass, before ordinary Qt event
        dispatch. Other events and foreign windows receive unchanged dispatch.
        """
        kind = self._event_kind(watched, event)
        return self._measure("qt-notify", dispatch, eventKind=kind) if kind else dispatch()

    def _measure(self, stage, dispatch, **fields):
        if self.closed or not self.started:
            return dispatch()
        try:
            began = self._now()
            self.next_span += 1
            span = {"spanId": self.next_span,
                    "parentSpanId": self.stack[-1]["spanId"] if self.stack else None,
                    "childrenSeconds": 0.0}
            self.stack.append(span)
        except Exception:
            self.observation_errors += 1
            return dispatch()
        status = "RETURNED"
        try:
            return dispatch()
        except BaseException:
            status = "RAISED"
            raise
        finally:
            # Profiling must never change the original return or exception.
            self.stack.pop()
            try:
                ended = self._now()
                elapsed = ended - began
                if elapsed < 0:
                    raise RuntimeError("Activation profile QPC reversed")
                if self.stack:
                    self.stack[-1]["childrenSeconds"] += elapsed
                if len(self.rows) >= self.capacity:
                    self.dropped_rows += 1
                else:
                    self.rows.append({"stage": stage, "beginSeconds": began,
                        "endSeconds": ended, "inclusiveMs": elapsed * 1000,
                        "exclusiveHookMs": max(0.0, elapsed - span["childrenSeconds"]) * 1000,
                        "spanId": span["spanId"], "parentSpanId": span["parentSpanId"],
                        "status": status, **fields})
            except Exception:
                self.observation_errors += 1

    def _hook(self, owner, name, wrap):
        original = getattr(owner, name)
        if not callable(original):
            raise TypeError("Disposable activation hook anchor is not callable")
        wrapper = wrap(original)
        setattr(owner, name, wrapper)
        self.hooks.append((owner, name, original, wrapper))

    def _install_icon_hooks(self, entry):
        def apply_window(original):
            def wrapper(window, icon):
                dispatch = lambda: original(window, icon)
                return self._measure("icon-apply-owned-window", dispatch) if window == self.window else dispatch()
            return wrapper

        def apply_all(original):
            def wrapper(sync):
                return self._measure("icon-apply-all", lambda: original(sync))
            return wrapper

        # Explicit callable anchors fail before measurement if this disposable
        # application's icon contract changed. Qt virtual eventFilter methods
        # are never monkeypatched: their Shiboken dispatch lifetime is distinct
        # from ordinary Python callback hooks. The real notify bracket and the
        # icon application's ordinary function isolate its expensive work.
        self._hook(entry, "_apply_app_icon_to_window", apply_window)
        self._hook(entry._AppIconSync, "apply_all", apply_all)

    def stop(self):
        if self.closed:
            return self.stop_result
        self.closed = True
        cleanup_errors = []
        for owner, name, original, wrapper in reversed(self.hooks):
            try:
                if getattr(owner, name) is wrapper:
                    setattr(owner, name, original)
                else:
                    cleanup_errors.append("fixture hook changed before restoration")
            except Exception:
                cleanup_errors.append("fixture activation hook restoration failed")
        self.hooks.clear()
        self.stop_result = {"status": "COMPLETE" if not (self.dropped_rows
                or self.observation_errors or cleanup_errors or self.stack) else "INCOMPLETE",
            "events": sorted(self.rows, key=lambda row: (row["beginSeconds"], row["spanId"])),
            "capacity": self.capacity, "droppedRows": self.dropped_rows,
            "observationErrors": self.observation_errors,
            "cleanupErrors": cleanup_errors, "activeSpansAtStop": len(self.stack),
            "scope": SCOPE}
        return self.stop_result
