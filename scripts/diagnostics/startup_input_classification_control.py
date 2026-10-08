"""Counterbalanced no-window control of the actual startup input classifier.

Only the startup probe class is parsed from governed source; main is not
imported. An AST prototype changes only its event-to-label lookup, preserving
the first input capture and every subsequent callback. This is diagnostic code,
not a production repair or application interactivity measurement.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import statistics
import time
from typing import Any, Optional


SCOPE = ("Counterbalanced actual startup-probe versus AST map classifier on the "
         "same synthetic QQuickItem tree; QCoreApplication only, no window, "
         "WebEngine, native input, CSPM data or production latency proof")


def load_classifiers(*, clock=time.perf_counter, callback=None):
    from PySide6.QtCore import QEvent, QObject
    source = Path(__file__).resolve().parents[2] / "src/python/main.py"
    data = source.read_bytes()
    tree = ast.parse(data.decode("utf-8"))
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "_StartupInputProbe")
    prototype = copy.deepcopy(original)
    handler = next(node for node in prototype.body if isinstance(node, ast.FunctionDef)
                   and node.name == "eventFilter")
    # Verify the complete classification anchor before replacing it; the rest
    # of the original first-capture/callback handler remains the identical AST.
    begin = next(index for index, node in enumerate(handler.body)
        if isinstance(node, ast.Try) and any(isinstance(item, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "event_type"
                for target in item.targets) for item in node.body))
    end = next(index for index, node in enumerate(handler.body[begin:], begin)
               if isinstance(node, ast.If) and ast.unparse(node.test) == "not self._captured")
    old = ast.unparse(ast.Module(body=handler.body[begin:end], type_ignores=[]))
    kinds = ("MouseButtonPress", "MouseButtonDblClick", "KeyPress", "TouchBegin", "Wheel")
    if any("QEvent.Type." + kind not in old for kind in kinds) or "callback" in old:
        raise RuntimeError("Startup classifier anchor changed; no diagnostic replacement made")
    replacement = ast.parse('''try:
    label = _diagnostic_labels.get(event.type(), "")
except Exception:
    return False
if not label:
    return False
''').body
    handler.body[begin:end] = replacement
    ast.fix_missing_locations(prototype)
    labels = {QEvent.MouseButtonPress: "mouse-press", QEvent.MouseButtonDblClick: "mouse-double-click",
              QEvent.KeyPress: "key-press", QEvent.TouchBegin: "touch-begin", QEvent.Wheel: "wheel"}

    class QuietLogger:
        def info(self, *_args):
            pass

    namespace_base = {"QObject": QObject, "QEvent": QEvent, "Any": Any, "Optional": Optional,
        "time": type("Clock", (), {"perf_counter": staticmethod(clock)}), "t0": clock(),
        "logging": type("Logs", (), {"getLogger": staticmethod(lambda name: QuietLogger())}),
        "_startup_first_input_perf": None, "_startup_first_input_label": None,
        "_splash_first_pixel_perf": None, "_splash_gone_perf": None,
        "_startup_input_notify_callback": callback,
        "_report_nonfatal_startup_failure": lambda *_args: None, "_diagnostic_labels": labels}
    result = {}
    for name, definition in (("source", original), ("map-prototype", prototype)):
        namespace = dict(namespace_base)
        exec(compile(ast.Module(body=[definition], type_ignores=[]), str(source), "exec"), namespace)
        result[name] = {"class": namespace["_StartupInputProbe"], "namespace": namespace}
    return result, hashlib.sha256(data).hexdigest()


def run_control(*, child_count=4000, samples=10):
    if type(child_count) is not int or not 1 <= child_count <= 20000:
        raise ValueError("Synthetic child count must be an integer in 1..20000")
    if type(samples) is not int or not 2 <= samples <= 30 or samples % 2:
        raise ValueError("Counterbalanced sample count must be even in 2..30")
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtQuick import QQuickItem
    from shiboken6 import delete
    app = QCoreApplication.instance() or QCoreApplication([])
    definitions, source_hash = load_classifiers()
    root = QQuickItem()
    children = [QQuickItem(root) for _ in range(child_count)]
    filters, observations = {}, {}

    def counting_class(base):
        class Counted(base):
            def __init__(self):
                super().__init__()
                self.calls = 0
            def eventFilter(self, watched, event):
                self.calls += 1
                return super().eventFilter(watched, event)
        return Counted

    try:
        for name, definition in definitions.items():
            filters[name] = counting_class(definition["class"])()
            observations[name] = []
            app.installEventFilter(filters[name])
            for kind in (QEvent.WindowActivate, QEvent.WindowDeactivate):
                QCoreApplication.sendEvent(root, QEvent(kind))
            app.removeEventFilter(filters[name])
            filters[name].calls = 0
        order_rows = []
        for sample in range(samples):
            order = ("source", "map-prototype") if sample % 2 == 0 else ("map-prototype", "source")
            order_rows.append(list(order))
            for name in order:
                app.installEventFilter(filters[name])
                try:
                    began = time.perf_counter()
                    first = QCoreApplication.sendEvent(root, QEvent(QEvent.WindowActivate))
                    second = QCoreApplication.sendEvent(root, QEvent(QEvent.WindowDeactivate))
                    observations[name].append({"sample": sample,
                        "pairWallMs": (time.perf_counter() - began) * 1000,
                        "allDispatchReturnedTrue": bool(first and second)})
                finally:
                    app.removeEventFilter(filters[name])
        expected = 2 * samples * (child_count + 1)
        return {"status": "PASS" if all(filters[name].calls == expected
                    and all(row["allDispatchReturnedTrue"] for row in observations[name])
                    for name in definitions) else "FAIL",
            "sourceSha256": source_hash, "nodeCount": child_count + 1,
            "samplesPerVariant": samples, "sampleOrders": order_rows,
            "variants": [{"variant": name, "observedFilterCalls": filters[name].calls,
                "expectedFilterCalls": expected, "observations": observations[name],
                "medianPairWallMs": statistics.median(row["pairWallMs"] for row in observations[name])}
                for name in definitions], "scope": SCOPE}
    finally:
        for event_filter in filters.values():
            app.removeEventFilter(event_filter)
            delete(event_filter)
        delete(root)
        children.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--children", type=int, default=4000)
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(run_control(child_count=args.children, samples=args.samples), indent=2))


if __name__ == "__main__":
    main()
