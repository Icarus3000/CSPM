"""Matched Qt Item-tree activation control without a window or desktop input.

Qt recursively dispatches WindowActivate/Deactivate through QQuickItem children.
This control measures the additional Python event-filter calls on that same
tree. It models filter scope only, not CSPM's complete activation cost, palette
bindings, a physical window, interactivity or collector overhead.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time


VARIANTS = ("no-added-filter", "global-count-only", "global-typed",
            "global-three-typed", "root-typed")
SCOPE = ("Synthetic Qt QQuickItem activation/deactivation tree; QCoreApplication "
         "only, no QQuickWindow/WebEngine/native HWND; matched Python filter "
         "scope CPU-wall-clock control, not application or physical latency")


def run_controls(*, child_count=4000, samples=8):
    if type(child_count) is not int or not 1 <= child_count <= 20000:
        raise ValueError("Synthetic child count must be an integer in 1..20000")
    if type(samples) is not int or not 1 <= samples <= 30:
        raise ValueError("Synthetic sample count must be an integer in 1..30")
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, qVersion
    from PySide6.QtQuick import QQuickItem
    from shiboken6 import delete

    app = QCoreApplication.instance() or QCoreApplication([])
    root = QQuickItem()
    children = [QQuickItem(root) for _ in range(child_count)]
    node_count = child_count + 1

    class Filter(QObject):
        def __init__(self, typed):
            super().__init__()
            self.typed, self.calls, self.activations = typed, 0, 0

        def eventFilter(self, watched, event):
            self.calls += 1
            if self.typed and event.type() in (QEvent.WindowActivate, QEvent.WindowDeactivate):
                self.activations += 1
            return False

    rows = []
    try:
        for variant in VARIANTS:
            count = 3 if variant == "global-three-typed" else 0 if variant == "no-added-filter" else 1
            filters = [Filter(variant != "global-count-only") for _ in range(count)]
            target = root if variant == "root-typed" else app
            for event_filter in filters:
                target.installEventFilter(event_filter)
            try:
                # Warm the same native tree and keep all palette/activation
                # handlers intact. Timed pairs alternate the actual Qt events.
                for kind in (QEvent.WindowActivate, QEvent.WindowDeactivate):
                    QCoreApplication.sendEvent(root, QEvent(kind))
                for event_filter in filters:
                    event_filter.calls = event_filter.activations = 0
                elapsed = []
                returned = True
                for _ in range(samples):
                    began = time.perf_counter()
                    returned &= bool(QCoreApplication.sendEvent(root, QEvent(QEvent.WindowActivate)))
                    returned &= bool(QCoreApplication.sendEvent(root, QEvent(QEvent.WindowDeactivate)))
                    elapsed.append((time.perf_counter() - began) * 1000)
                observed = sum(event_filter.calls for event_filter in filters)
                expected = 2 * samples * count * (1 if target is root else node_count)
                rows.append({"variant": variant, "samples": samples,
                    "filterCount": count, "observedFilterCalls": observed,
                    "expectedFilterCalls": expected,
                    "observedTypedActivationCalls": sum(event_filter.activations for event_filter in filters),
                    "allDispatchReturnedTrue": returned,
                    "pairWallMs": elapsed, "medianPairWallMs": statistics.median(elapsed),
                    "status": "PASS" if observed == expected and returned else "FAIL"})
            finally:
                for event_filter in filters:
                    target.removeEventFilter(event_filter)
                    delete(event_filter)
        return {"status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL",
            "qtVersion": qVersion(), "nodeCount": node_count, "childCount": child_count,
            "sameTreeAcrossVariants": True, "variants": rows, "scope": SCOPE}
    finally:
        delete(root)
        children.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--children", type=int, default=4000)
    parser.add_argument("--samples", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(run_controls(child_count=args.children, samples=args.samples), indent=2))


if __name__ == "__main__":
    main()
