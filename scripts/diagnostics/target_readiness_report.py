"""Summarize ignored native-spike JSON without exporting private log content.

No Qt import or window is needed. API boundary intervals form one additive
chain; Qt frame/layout observations explain portions of that chain and must
not be added again. Qt timestamps are Python message-handler observations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re


QT_SOURCE = "https://github.com/qt/qtdeclarative/blob/v6.10.3/src/quick/scenegraph/qsgthreadedrenderloop.cpp"
LAYOUT_SOURCE = "https://github.com/qt/qtdeclarative/blob/v6.10.3/src/quicklayouts/qquicklayout.cpp"
LABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
POLISH = re.compile(r"^updatePolish\(\) (ENTERING|LEAVING) ([A-Za-z_][A-Za-z0-9_]*)\((0x[0-9a-fA-F]+)(?:[, )])")
WINDOW = re.compile(r"\[window (0x[0-9a-fA-F]+)\]")
GUI = re.compile(r"Frame prepared, polish=(\d+) ms, lock=(\d+) ms, blockedForSync=(\d+) ms, animations=(\d+) ms")
RENDER = re.compile(r"frame rendered in (\d+)ms, sync=(\d+), render=(\d+), swap=(\d+)")
RENDERER = re.compile(r"time in renderer: total=(\d+)ms, preprocess=(\d+), updates=(\d+), rendering=(\d+)")
MARKER_NAMES = {
    "suppression", "finalX", "finalY", "finalW", "finalH", "uiMaximized",
    "adoptTargetScreen", "updateTargetScreen", "refreshVisibleRect",
    "hostEnvelope", "canvasGeometry", "clearMaximizedOwner", "metricsHold",
    "metricsPublication",
}


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid numeric " + name)
    return float(value)


def ms(value):
    return round(value * 1000, 3)


def rows_by_cycle(rows, name):
    result = defaultdict(list)
    if not isinstance(rows, list):
        raise ValueError(name + " must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(name + " has a non-object row")
        cycle = row.get("cycle")
        if type(cycle) is not int or cycle < 0:
            raise ValueError(name + " has an invalid cycle")
        number(row.get("t"), name + " timestamp")
        result[cycle].append(row)
    for grouped in result.values():
        grouped.sort(key=lambda row: row["t"])
    return result


def interval(name, start, end, command, clock, thread, scope, blocking=None):
    if end < start:
        raise ValueError("Reversed interval: " + name)
    return {
        "stage": name, "thread": thread,
        "startAfterCommandMs": ms(start - command),
        "endAfterCommandMs": ms(end - command),
        "startAfterClockMs": ms(start - clock),
        "endAfterClockMs": ms(end - clock), "durationMs": ms(end - start),
        "blocking": blocking, "evidence": "direct boundary observation",
        "scope": scope,
    }


def safe_label(value):
    return value if isinstance(value, str) and LABEL.fullmatch(value) else "unknown"


def layout_summary(rows, metadata, command, clock):
    """Use nesting to avoid counting a child updatePolish twice."""
    stack, observations = [], []
    objects = Counter()
    for row in rows:
        match = POLISH.match(str(row.get("message", "")))
        if not match:
            raise ValueError("Unrecognized layout polish boundary")
        direction, class_name, address = match.groups()
        if direction == "ENTERING":
            stack.append({"address": address, "class": class_name, "t": row["t"], "children": 0.0})
            continue
        if not stack or stack[-1]["address"] != address or stack[-1]["class"] != class_name:
            raise ValueError("Unpaired or crossing layout polish boundaries")
        entry = stack.pop()
        duration = row["t"] - entry["t"]
        own = duration - entry["children"]
        if own < -1e-9:
            raise ValueError("Layout child spans exceed parent span")
        if stack:
            stack[-1]["children"] += duration
        objects[address] += 1
        meta = metadata.get(address, {})
        ancestors = [{"class": safe_label(item.get("class")), "id": safe_label(item.get("id"))}
                     for item in meta.get("ancestors", []) if isinstance(item, dict)]
        observations.append({
            **interval("layoutUpdatePolish", entry["t"], row["t"], command, clock,
                       "GUI", "Includes QML bindings and Python logging overhead; child spans overlap."),
            "class": safe_label(class_name), "ancestors": ancestors,
            "visibleAtInitialMetadataCollection": meta.get("visible") if type(meta.get("visible")) is bool else None,
            "inclusiveMs": ms(duration), "ownMs": ms(max(0.0, own)),
        })
    if stack:
        raise ValueError("Unclosed layout polish boundaries")
    groups = {}
    for item in observations:
        key = (item["class"], json.dumps(item["ancestors"], sort_keys=True), item["visibleAtInitialMetadataCollection"])
        group = groups.setdefault(key, {"class": item["class"], "ancestors": item["ancestors"],
            "visibleAtInitialMetadataCollection": item["visibleAtInitialMetadataCollection"],
            "calls": 0, "inclusiveMs": 0.0, "ownMs": 0.0})
        group["calls"] += 1
        group["inclusiveMs"] += item["inclusiveMs"]
        group["ownMs"] += item["ownMs"]
    for group in groups.values():
        group["inclusiveMs"] = round(group["inclusiveMs"], 3)
        group["ownMs"] = round(group["ownMs"], 3)
    return {"pairedCalls": len(observations), "distinctObjects": len(objects),
            "repeatedObjectCalls": sum(count - 1 for count in objects.values()),
            "observedOwnTotalMs": round(sum(item["ownMs"] for item in observations), 3),
            "groups": sorted(groups.values(), key=lambda item: -item["ownMs"]),
            "scope": "Only captured updatePolish boundaries after commit; excludes synchronous rearrange, other item polish and uncaptured invalidations. Visibility metadata is an initial snapshot."}


def qt_summary(rows, command, clock):
    pending, observations, renderer, unpaired = {}, [], [], Counter()
    for row in rows:
        message = str(row.get("message", ""))
        window = WINDOW.search(message)
        if row.get("category") == "qt.scenegraph.time.renderloop" and window:
            kind = "GUI" if "[gui thread]" in message else "render"
            key = (window.group(1), kind)
            start = "polishAndSync: start" in message or "syncAndRender: start" in message
            match = GUI.search(message) if kind == "GUI" else RENDER.search(message)
            if start:
                if key in pending:
                    raise ValueError("Duplicate Qt frame start without summary")
                pending[key] = row["t"]
            elif match:
                begin = pending.pop(key, None)
                if begin is None:
                    unpaired[kind + "Summary"] += 1
                    continue
                names = ("polishMs", "lockMs", "blockedForSyncMs", "animationsMs") if kind == "GUI" else ("frameMs", "syncCompositeMs", "renderCompositeMs", "swapCompositeMs")
                item = interval("qtGuiFrame" if kind == "GUI" else "qtRenderFrame", begin, row["t"], command, clock, kind,
                    "Qt integer CPU timers include Python callback/logging overhead; GUI blockedForSync overlaps render-thread work.")
                item["qtReported"] = dict(zip(names, map(int, match.groups())))
                observations.append(item)
        elif row.get("category") == "qt.scenegraph.time.renderer":
            match = RENDERER.search(message)
            if match:
                renderer.append(dict(zip(("totalMs", "preprocessMs", "updatesMs", "renderingMs"), map(int, match.groups()))))
    for _, kind in pending:
        unpaired[kind + "Start"] += 1
    return {"frames": observations, "rendererCalls": len(renderer),
            "rendererReportedTotalsMs": dict(Counter({name: sum(item[name] for item in renderer) for name in ("totalMs", "preprocessMs", "updatesMs", "renderingMs")})),
            "unpairedBoundaryCounts": dict(unpaired),
            "scope": "syncComposite includes swapchain resize/beginFrame and actual sync; renderComposite includes renderSceneGraph and after-pass capture; swapComposite includes submission and trailing work. Renderer rows may nest and are not additive. GPU execution/completion and physical presentation are unmeasured."}


def summarize(payload):
    events = rows_by_cycle(payload.get("events", []), "events")
    profiles = rows_by_cycle(payload.get("profileBoundaries", []), "profileBoundaries")
    stages = rows_by_cycle(payload.get("qtStageTimings", []), "qtStageTimings")
    layouts = rows_by_cycle(payload.get("qtLayoutPolish", []), "qtLayoutPolish")
    cycles = []
    for cycle, rows in sorted(events.items()):
        commands = [row for row in rows if row.get("event") == "command"]
        if not commands:
            if any(row.get("event") in ("layout-begin", "layout-committed", "gpu-capture") for row in rows):
                raise ValueError("Capture/layout cycle has no command")
            continue  # Final fixture cleanup is commonly recorded in completedCycles.
        if len(commands) != 1:
            raise ValueError("Cycle must contain exactly one command")
        command = commands[0]["t"]
        unique = {}
        for row in rows:
            if row.get("event") in ("native-clock-start", "layout-profile-start", "layout-begin", "layout-committed", "target-gpu-composition-committed", "live-handoff"):
                if row["event"] in unique:
                    raise ValueError("Duplicate transition boundary")
                unique[row["event"]] = row
        anchors = [unique[name] for name in ("native-clock-start", "layout-profile-start") if name in unique]
        if len(anchors) > 1:
            raise ValueError("Cycle has both native and layout-only clocks")
        if not anchors:
            cycles.append({"cycle": cycle, "kind": commands[0].get("kind") if commands[0].get("kind") in ("maximize", "restore") else "unknown", "status": "incomplete before target preparation"})
            continue
        clock = anchors[0]["t"]
        if clock < command:
            raise ValueError("Transition clock precedes command")
        targets = [row for row in rows if row.get("event") == "gpu-capture" and row.get("kind") == "target"]
        if len(targets) > 1:
            raise ValueError("Cycle contains multiple target captures")
        chain = []
        if "layout-begin" in unique and "layout-committed" in unique:
            begin, commit = unique["layout-begin"]["t"], unique["layout-committed"]["t"]
            if commit < begin:
                raise ValueError("Layout commit precedes begin")
            if begin >= clock:
                chain.append(interval("clockToGeometryBegin", clock, begin, command, clock, "GUI", "Intentional delay, calibration and fixture dispatch.", True))
            elif not payload.get("configuration", {}).get("prepared_target"):
                raise ValueError("Cold geometry preparation precedes transition clock")
            chain.append(interval("geometryCommit", begin, commit, command, clock, "GUI", "Synchronous QML geometry propagation and native host adoption.", True))
            if targets:
                target = targets[0]
                if target.get("error"):
                    target = None
                if target is not None:
                    request, callback, finished, delivery = [number(target.get(name), name) for name in ("requested", "renderCallback", "captureFinished", "t")]
                    if not commit <= request <= callback <= finished <= delivery:
                        raise ValueError("Inconsistent target capture ordering")
                    if isinstance(target.get("client"), list) and isinstance(target.get("size"), list) and target["client"][2:] != target["size"]:
                        raise ValueError("Target texture/client dimensions disagree")
                    chain.extend([
                        interval("commitToCaptureRequest", commit, request, command, clock, "GUI", "Fixture logging/category activation and client query.", True),
                        interval("captureRequestToRenderCallback", request, callback, command, clock, "GUI/render", "Scheduling, polish, synchronization and rendering; stage timers overlap this interval.", False),
                        interval("textureExportBoundary", callback, finished, command, clock, "render", "Native API CPU span: allocation, keyed mutex, GPU copy submission and flush; GPU completion is not isolated.", True),
                        interval("queuedGuiDelivery", finished, delivery, command, clock, "GUI/render", "Queued signal delivery plus GUI/GIL scheduling; render may continue in parallel.", False),
                    ])
                    imported = unique.get("target-gpu-composition-committed")
                    if imported:
                        chain.append(interval("bridgeImportBoundary", delivery, imported["t"], command, clock, "GUI/native", "Native command queue, shared-resource acquisition/copy/SRV creation; no separate target DComp Commit.", True))
        marker_rows = profiles.get(cycle, [])
        marker_by_name = {}
        for row in marker_rows:
            name = row.get("boundary")
            if name in marker_by_name:
                raise ValueError("Duplicate profile boundary in cycle")
            marker_by_name[name] = row
        statements = []
        for name in sorted(MARKER_NAMES):
            first, last = marker_by_name.get("before:" + name), marker_by_name.get("after:" + name)
            if (first is None) != (last is None):
                raise ValueError("Unpaired QML statement boundary")
            if first and last:
                statements.append(interval(name, first["t"], last["t"], command, clock, "GUI", "QML Date.now calibrated per cycle; 1 ms resolution; contained within geometryCommit.", True))
        cycles.append({"cycle": cycle, "kind": commands[0].get("kind") if commands[0].get("kind") in ("maximize", "restore") else "unknown",
            "clock": "native" if "native-clock-start" in unique else "layout isolation",
            "commandToClockMs": ms(clock - command), "apiBoundaryChain": chain,
            "chainTotalMs": round(sum(item["durationMs"] for item in chain), 3),
            "targetGuiArrivalMs": ms(targets[0]["t"] - clock) if targets and not targets[0].get("error") else None,
            "qmlStatements": statements, "qt": qt_summary(stages.get(cycle, []), command, clock),
            "layoutPolish": layout_summary(layouts.get(cycle, []), payload.get("qtLayoutObjects", {}), command, clock),
            "qualificationFailureCount": sum(row.get("event") == "qualification-failure" for row in rows),
            "unmeasured": ["first visible motion", "pure GPU execution", "GPU copy completion", "bridge keyed-mutex wait separately", "first target-bearing native Present", "physical desktop presentation", "unconfigured endpoint hold", "matching live pixels", "input restored"]})
    known = {item["cycle"] for item in cycles}
    if any(cycle not in known for source in (profiles, stages, layouts) for cycle in source):
        raise ValueError("Stage/profile rows refer to a cycle without command")
    return {"schemaVersion": 1, "qtVersionInterpretation": "6.10.3", "sources": [QT_SOURCE, LAYOUT_SOURCE],
        "cycles": cycles, "completedCycles": payload.get("completedCycles"),
        "fixtureFailureCount": len(payload.get("failures", [])),
        "interpretation": "API chain intervals add to target delivery/import. QML statements, Qt GUI/render frames and layout spans overlap that chain and each other; do not sum them into another critical path. Prepared-target and layout-only fixtures are not cold motion evidence.",
        "configuration": {key: payload.get("configuration", {}).get(key) for key in ("prepared_target", "layout_only", "layout_repair", "gui_delay_ms", "endpoint_hold_ms", "duration_ms", "blend_start_ms", "profile_boundaries", "qt_render_timings", "qt_layout_polish")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    report = summarize(json.loads(raw))
    report["inputSha256"] = hashlib.sha256(raw).hexdigest()
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
