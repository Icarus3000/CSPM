"""Disposable full-source production/candidate A/B and lifecycle fixture.

GUI-delivered modeled frame samples never certify physical continuity. Optional
desktop marker samples use the retained independent compositor collector.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import time


def analyze_geometry(samples, source, target):
    """Conservative marker-geometry gate; texture/whole-window quality is separate."""
    if len(samples) < 8:
        return {"status": "UNMEASURED", "reason": "fewer than eight physical geometry samples"}
    vector = [b - a for a, b in zip(source, target)]
    norm = sum(x * x for x in vector)
    if norm < 16:
        return {"status": "UNMEASURED", "reason": "insufficient endpoint separation"}
    intervals = [b["t"] - a["t"] for a, b in zip(samples, samples[1:])]
    if min(intervals) <= 0 or max(intervals) > .050:
        return {"status": "UNMEASURED", "reason": "nonmonotonic or over-50ms collector gap", "maxGapMs": max(intervals) * 1000}
    progress = [sum((x - a) * v for x, a, v in zip(row["rect"], source, vector)) / norm for row in samples]
    velocities = [(b - a) / dt for a, b, dt in zip(progress, progress[1:], intervals)]
    acceleration = [(b - a) / ((intervals[i] + intervals[i + 1]) / 2) for i, (a, b) in enumerate(zip(velocities, velocities[1:]))]
    jerk = [(b - a) / ((intervals[i] + intervals[i + 2]) / 2) for i, (a, b) in enumerate(zip(acceleration, acceleration[1:]))]
    failures = []
    stationary_since = None
    stationary_rect = None
    for row, p in zip(samples, progress):
        if .1 < p < .9:
            if row["rect"] == stationary_rect:
                if stationary_since is not None and row["t"] - stationary_since >= .060:
                    failures.append("at least 60ms stationary geometry during interior motion")
            else:
                stationary_rect, stationary_since = row["rect"], row["t"]
        else:
            stationary_rect = stationary_since = None
    deltas = [b - a for a, b in zip(progress, progress[1:])]
    if any(delta < -.02 for delta in deltas):
        failures.append("over-2% backward positional step")
    if any(delta > .22 for delta in deltas):
        failures.append("over-22% endpoint-distance positional step")
    interior_speed = [abs(v) for v, a, b in zip(velocities, progress, progress[1:]) if .1 < a < .9 and .1 < b < .9 and abs(v) > .01]
    typical = statistics.median(interior_speed) if interior_speed else 0
    if typical and any(abs(v) > typical * 4 and abs(delta) > .10 for v, delta in zip(velocities, deltas)):
        failures.append("over-4x interior median velocity with over-10% positional step")
    return {"status": "FAIL" if failures else "PASS", "scope": "tested marker geometry only",
            "samples": len(samples), "failures": sorted(set(failures)), "maxGapMs": max(intervals) * 1000,
            "progress": progress, "velocity": velocities, "acceleration": acceleration, "jerk": jerk}


def finalize_physical_geometry(observations, failures):
    """Propagate measured geometry failures to the process-level result."""
    status = ("FAIL" if any(row["status"] == "FAIL" for row in observations)
              else "PASS" if observations and all(row["status"] == "PASS" for row in observations)
              else "UNMEASURED")
    if status == "FAIL":
        failures.append("independent compositor marker geometry failed")
    return {"observations": observations, "status": status,
            "scope": "independent compositor marker spans; whole texture/luminance/sharpness handoff remains unmeasured"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-label", default="cleanroom_transition_" + time.strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--engine", choices=("production", "single-clock", "compare"), default="compare")
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--screen-index", type=int)
    parser.add_argument("--pixels", action="store_true")
    parser.add_argument("--keep-visible", action="store_true")
    args = parser.parse_args()
    if args.cycles < 2 or args.cycles % 2:
        parser.error("cycles must be an even number of at least two")
    if not args.audit_label or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.audit_label):
        parser.error("audit label must contain letters, digits, underscores or hyphens")
    root = Path(__file__).resolve().parents[2]
    audit = root / "logs" / args.audit_label
    audit.mkdir(parents=True, exist_ok=False)
    mirror = audit / "tree"
    for name in ("src/qml", "src/assets", "assets"):
        shutil.copytree(root / name, mirror / name)
    # Retain completed trace arrays on the original window before the temporary
    # surface destroys itself. These additions affect only the diagnostic mirror.
    shell_path = mirror / "src/qml/DetachedShellWindow.qml"
    shell = shell_path.read_text(encoding="utf-8")
    assert shell.count("    id: mainWin\n") == 1
    shell_path.write_text(shell.replace("    id: mainWin\n", "    id: mainWin\n    property var cleanRoomProbeSurfaceTraces: ({})\n"), encoding="utf-8")
    candidate_path = mirror / "src/qml/CleanRoomTransitionSurface.qml"
    if candidate_path.exists():
        candidate = candidate_path.read_text(encoding="utf-8")
        archive = """var rows = traceEvents.slice(); rows.push(row); traceEvents = rows;
        var archive = mainWindow.cleanRoomProbeSurfaceTraces;
        archive[String(commandMs)] = rows;
        mainWindow.cleanRoomProbeSurfaceTraces = archive;"""
        assert candidate.count("var rows = traceEvents.slice(); rows.push(row); traceEvents = rows;") == 1
        candidate_path.write_text(candidate.replace("var rows = traceEvents.slice(); rows.push(row); traceEvents = rows;", archive), encoding="utf-8")
    header = mirror / "src/qml/components/ProfessionalTopHeader.qml"
    code = header.read_text(encoding="utf-8")
    assert code.count("                id: maximizeButton") == 1
    header.write_text(code.replace("                id: maximizeButton", '                id: maximizeButton\n                objectName: "CleanRoomProbeMaximizeButton"'), encoding="utf-8")
    original = Path(os.environ["LOCALAPPDATA"]) / "CSPM"
    protected = [original / "user_settings.json", *(original / "data" / n for n in ("CSPM.xlsm", "Dockets.xlsm"))]
    hash_files = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    before_hashes = hash_files()
    os.environ["CSPM_MACHINE_ID_FILE"] = str(audit / "disposable_profile/machine_id.json")
    os.environ["CSPM_EXPERIMENTAL_TRANSITION"] = "production" if args.engine == "compare" else args.engine
    probe = root / "scripts/diagnostics/window_transition_probe.py"
    source = probe.read_text(encoding="utf-8")
    source = source[:source.index("\nentry._capture_startup_launch_context = diagnostic_launch_context")]
    source = source.replace('AUDIT = ROOT / "logs/window_transition_diagnostic"', "AUDIT = Path(" + repr(str(audit)) + ")")
    source = source.replace("QTimer.singleShot(120000, self.timeout)", "QTimer.singleShot(240000, self.timeout)")
    source = source.replace("if self.index < 10:", "if self.index < " + str(args.cycles) + ":")
    source = source.replace("self.evaluate(\"_probeWindow.toggleWindowMaximize()\")", "self.invoke_toggle()")
    for callback in ("check_cycle", "minimize_maximized", "check_after_taskbar", "close_maximized"):
        source = source.replace("QTimer.singleShot(1400, self." + callback + ")", "self.wait_until_settled(self." + callback + ")")
    # The inherited fixture's DirectConnection callbacks can stall rendering
    # behind Python's GIL. Keep only our queued GUI receivers below.
    for declaration in ("('beforeFrameBegin','beforeSynchronizing','afterSynchronizing','beforeRendering','afterRendering','afterFrameEnd','frameSwapped')", "('xChanged','yChanged','widthChanged','heightChanged','finalXChanged','finalYChanged','finalWChanged','finalHChanged')"):
        source = source.replace("for name in " + declaration + ":", "for name in ():")
    if not args.pixels:
        source = source.replace("from pixel_tracker_process import PixelTracker, SENSORS", '''from pixel_tracker_process import SENSORS
class PixelTracker:
    def __init__(self, *_): pass
    def start(self): pass
    def stop(self): pass
    def command(self, name): pass
''')
    sys.path.insert(0, str(probe.parent))
    context = {"__file__": str(probe), "__name__": "cleanroom_fixture"}
    exec(compile(source, str(probe), "exec"), context)
    entry, base = context["entry"], context["ProbeApplication"]
    QTimer, Qt = context["QTimer"], context["Qt"]
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from shiboken6 import isValid
    class MirrorEngine(QQmlApplicationEngine):
        def load(self, url):
            local = url.toLocalFile() if isinstance(url, QUrl) else str(url)
            if Path(local).name == "Main.qml":
                url = QUrl.fromLocalFile(str(mirror / "src/qml/Main.qml"))
            return super().load(url)
    entry.QQmlApplicationEngine = MirrorEngine
    runs, frame_rows, traces = [], [], {}

    def plain(value):
        return value.toVariant() if hasattr(value, "toVariant") else value

    class CleanRoomApplication(base):
        def __init__(self, argv):
            self.current = None
            self.observed = set()
            self.mode = args.engine
            self.probe_written = False
            super().__init__(argv)
            self.surface_timer.setInterval(10)

        def wait_ready(self):
            windows = [w for w in self.topLevelWindows() if w.objectName() == "CSPMMainWindow"]
            if windows and windows[0].property("startupCinematicBloomActive"):
                return
            super().wait_ready()

        def begin_cycles(self):
            self.button = self.window.findChild(QObject, "CleanRoomProbeMaximizeButton")
            assert self.button is not None
            self.engine.globalObject().setProperty("_probeMaximizeButton", self.engine.newQObject(self.button))
            self.experiment = self.engine.rootContext().contextProperty("transitionExperiment")
            assert self.experiment is not None, "transitionExperiment context is unavailable"
            if args.keep_visible:
                import ctypes
                from ctypes import wintypes
                native = ctypes.windll.user32
                native.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                assert native.SetWindowPos(int(self.window.winId()), -1, 0, 0, 0, 0, 0x13)
            self.window.frameSwapped.connect(self.live_frame, Qt.QueuedConnection)
            super().begin_cycles()

        def step(self):
            if self.index < args.cycles:
                mode = ("production" if (self.index // 2) % 2 == 0 else "single-clock") if args.engine == "compare" else args.engine
                if self.experiment.setEngine(mode) is False:
                    context["failures"].append("engine selector refused " + mode)
                    self.finish()
                    return
                self.mode = mode
            super().step()

        def invoke_toggle(self):
            self.finish_run()
            self.current = {"index": len(runs), "primary": self.index < args.cycles,
                            "kind": "restore" if self.window.property("uiMaximized") else "maximize",
                            "engine": str(self.window.property("cleanRoomEngine")), "command": time.perf_counter(),
                            "sourceRect": [self.window.property(k) for k in ("finalX", "finalY", "finalW", "finalH")],
                            "modeledFrameIds": [], "physicalContinuity": {"status": "UNMEASURED"}}
            return self.evaluate("_probeMaximizeButton.clicked(); true")

        def active(self):
            return any(bool(self.window.property(p)) for p in ("professionalWindowTransitionActive", "maximizeAnimInProgress", "isRestoringFromMinimize", "isMinimizing"))

        def wait_until_settled(self, callback):
            started = time.perf_counter()
            def poll():
                if self.active():
                    if time.perf_counter() - started > 8:
                        context["failures"].append("transition did not settle in eight seconds")
                        self.finish()
                        return
                    QTimer.singleShot(25, poll)
                else:
                    self.finish_run()
                    QTimer.singleShot(150, callback)
            QTimer.singleShot(25, poll)

        def finish_run(self):
            if self.current is None:
                return
            self.current.update(inputReleaseObserved=time.perf_counter(),
                                targetRect=[self.window.property(k) for k in ("finalX", "finalY", "finalW", "finalH")],
                                exactGeometry=list(self.window.geometry().getRect()),
                                qualificationStatus="UNMEASURED")
            runs.append(self.current)
            self.current = None

        def trace_surfaces(self):
            if not hasattr(self, "engine"):
                return
            for surface in self.topLevelWindows():
                if surface.objectName() not in ("CSPMWindowTransitionSurface", "CSPMCleanRoomTransitionSurface") or id(surface) in self.observed:
                    continue
                self.observed.add(id(surface))
                surface_id = str(id(surface))
                surface.frameSwapped.connect(lambda s=surface, sid=surface_id: self.surface_frame(s, sid), Qt.QueuedConnection)
                self.surface_frame(surface, surface_id)

        def surface_frame(self, surface, surface_id):
            if not isValid(surface):
                return
            renderer = surface.findChild(QObject, "CSPMCleanRoomTransitionRenderer") or surface.findChild(QObject, "CSPMWindowTransitionRenderer")
            state = {"t": time.perf_counter(), "surface": surface_id, "sampleClock": "GUI delivery",
                     "objectName": surface.objectName(), "kind": "surface", "visible": surface.isVisible(),
                     "hostRect": list(surface.geometry().getRect())}
            for prop in ("stage", "clock", "motionClock", "modeledProgress", "progress", "preparationProgress", "settlementProgress", "targetReady", "sourceBounds", "targetBounds"):
                value = plain(surface.property(prop))
                if value is not None:
                    state[prop] = list(value.getRect()) if hasattr(value, "getRect") else value
            if surface.objectName() == "CSPMCleanRoomTransitionSurface":
                motion_ms = surface.property("motionMs")
                duration_ms = surface.property("durationMs")
                if motion_ms and duration_ms:
                    modeled_clock = max(0.0, min(1.0, (self.experiment.monotonicMs() - motion_ms) / duration_ms))
                    modeled_progress = modeled_clock ** 4 * (35 - modeled_clock * (84 - modeled_clock * (70 - 20 * modeled_clock)))
                    state.update(modeledClock=modeled_clock, modeledProgress=modeled_progress,
                                 modelScope="absolute-clock polynomial; not observed render uniform")
                    source_rect, target_rect = state.get("sourceBounds"), state.get("targetBounds")
                    if source_rect and target_rect:
                        state["modeledRect"] = [a + (b - a) * modeled_progress for a, b in zip(source_rect, target_rect)]
            if renderer:
                state["uniforms"] = {p: plain(renderer.property(p)) for p in ("clock", "motionClock", "modeledProgress", "progress") if renderer.property(p) is not None}
            frame_rows.append(state)
            if self.current is not None:
                self.current["modeledFrameIds"].append(len(frame_rows) - 1)
            events = plain(surface.property("traceEvents"))
            if events is not None:
                traces[surface_id] = events

        def live_frame(self):
            if self.current is not None:
                frame_rows.append({"t": time.perf_counter(), "sampleClock": "GUI delivery", "kind": "live",
                                   "visible": self.window.isVisible(), "active": self.active(),
                                   "rect": list(self.window.geometry().getRect())})
                self.current["modeledFrameIds"].append(len(frame_rows) - 1)

        def check_resumed(self):
            if self.window.property("isRestoringFromMinimize"):
                QTimer.singleShot(25, self.check_resumed)
                return
            super().check_resumed()

        def write_results(self):
            self.finish_run()
            super().write_results()
            if self.window is not None and isValid(self.window):
                completed = plain(self.window.property("cleanRoomProbeSurfaceTraces")) or {}
                traces.update({"completed_" + key: events for key, events in completed.items()})
            for events in traces.values():
                if any(event.get("qualificationFailure") is True or str(event.get("event", "")).startswith("qualification-failure:") for event in events if isinstance(event, dict)):
                    context["failures"].append("candidate reported qualificationFailure")
            (audit / "cleanroom_frames.json").write_text(json.dumps({"runs": runs, "frames": frame_rows, "surfaceTraces": traces,
                "failures": context["failures"], "physicalContinuity": "UNMEASURED until independent compositor analysis"}, indent=2), encoding="utf-8")

    def launch_context():
        screens = list(context["QGuiApplication"].screens())
        screen = screens[args.screen_index] if args.screen_index is not None else context["QGuiApplication"].primaryScreen()
        return {"screenIndex": screens.index(screen), "cursorX": screen.geometry().center().x(), "cursorY": screen.geometry().center().y()}
    entry._capture_startup_launch_context = launch_context
    entry.QApplication = CleanRoomApplication
    try:
        entry.main()
    except SystemExit as exc:
        if exc.code not in (None, 0):
            context["failures"].append("entry exit=" + str(exc.code))
    after_hashes = hash_files()
    (audit / "protected_hashes.json").write_text(json.dumps({"before": before_hashes, "after": after_hashes, "unchanged": before_hashes == after_hashes}, indent=2), encoding="utf-8")
    assert before_hashes == after_hashes
    physical = []
    if args.pixels and (audit / "window_transition_pixel8.csv").exists():
        with (audit / "window_transition_pixel8.csv").open(newline="") as stream:
            pixels = list(csv.DictReader(stream))
        samples = []
        for row in pixels:
            corners = [tuple(int(row[name + "_" + k]) for k in ("x", "y", "w", "h")) for name in ("top_left", "top_right", "bottom_left", "bottom_right")]
            if any(w < 2 or h < 2 for x, y, w, h in corners):
                continue
            left, top = min(x for x, y, w, h in corners), min(y for x, y, w, h in corners)
            right, bottom = max(x + w for x, y, w, h in corners), max(y + h for x, y, w, h in corners)
            samples.append({"t": float(row["timestamp"]), "rect": [left, top, right - left, bottom - top]})
        from collections import Counter
        for run in runs:
            command, release = run["command"], run["inputReleaseObserved"]
            before = [row for row in samples if command - .150 <= row["t"] < command]
            after = [row for row in samples if release + .020 <= row["t"] <= release + .140]
            def repeated_endpoint(rows):
                counts = Counter(tuple(row["rect"]) for row in rows)
                if not counts:
                    return None
                rect, count = counts.most_common(1)[0]
                return list(rect) if count >= 2 else None
            source_span, target_span = repeated_endpoint(before), repeated_endpoint(after)
            if source_span is None or target_span is None:
                observation = {"status": "UNMEASURED", "reason": "missing repeated physical source/target marker spans"}
            else:
                selected = [row for row in samples if command <= row["t"] <= release]
                observation = analyze_geometry(selected, source_span, target_span)
                changed = [row for row in selected if row["rect"] != source_span]
                observation.update(sourceMarkerSpan=source_span, targetMarkerSpan=target_span,
                                   commandToFirstMarkerMovementMs=(changed[0]["t"] - command) * 1000 if changed else None)
            physical.append({"run": run["index"], "engine": run["engine"], "kind": run["kind"], **observation})
    physical_report = finalize_physical_geometry(physical, context["failures"])
    (audit / "cleanroom_physical_geometry.json").write_text(json.dumps(physical_report, indent=2), encoding="utf-8")
    frame_report_path = audit / "cleanroom_frames.json"
    if frame_report_path.exists():
        frame_report = json.loads(frame_report_path.read_text(encoding="utf-8"))
        frame_report["failures"] = context["failures"]
        frame_report["physicalContinuity"] = {key: physical_report[key] for key in ("status", "scope")}
        frame_report_path.write_text(json.dumps(frame_report, indent=2), encoding="utf-8")
    print(json.dumps({"result": str(audit / "cleanroom_frames.json"), "runs": len(runs), "failures": context["failures"]}), flush=True)
    raise SystemExit(1 if context["failures"] else 0)


if __name__ == "__main__":
    main()
