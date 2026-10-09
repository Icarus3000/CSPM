"""Repeatable local collector; publish aggregates only, never images/private paths."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
JSON_OUT = ROOT / "docs/CLEANROOM_PHYSICAL_QUALIFICATION_RESULTS_2026-10-04.json"
MD_OUT = ROOT / "docs/CLEANROOM_PHYSICAL_QUALIFICATION_2026-10-04.md"
HASH = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_ERROR_PREFIXES = ("physical observer", "fixture integration", "fixture deadline", "target readiness",
    "DirectComposition presentation", "physical-pixel mapping", "source removal", "source-live-to-",
    "gpu-to-live-target-pixels", "source-gpu-to-native-removed-pixels", "source visibility control")

def read(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def subset(value, keys):
    return {key: value[key] for key in keys if key in value}

def relative(seconds, origin):
    return round((seconds - origin) * 1000, 3) if isinstance(seconds, (float, int)) and seconds and origin is not None else None

def safe_error(value):
    value = str(value)
    if value.startswith(SAFE_ERROR_PREFIXES) and not re.search(r"[A-Z]:[\\/]|@|\.xlsm|\n", value):
        return value
    return "Retained local fixture failure; raw detail omitted from portable aggregate"

def state(value):
    result = subset(value, ("qtDpr", "qtOpacity", "windowState", "transitionGeneration",
        "presentationRevision", "compositionCommitGeneration", "finalGeometry", "glowPadding",
        "cornerRadius", "witnessAbsent", "webengineStatus", "webengine"))
    for owner in ("live", "transition"):
        if owner in value:
            result[owner] = subset(value[owner], ("windowXYWH", "clientXYWH", "clientOffsetInWindowXY",
                "extendedFrameXYWH", "visible", "iconic", "nativeMaximized", "nativeWindowState",
                "nativeInputEnabled", "foreground", "foregroundHwnd", "cursorPositionXY", "dpi", "scale", "topmost", "layered", "layeredAlpha",
                "windowRegionType", "windowRegionBoundsXYWH", "topLevelZRank", "monitorXYWH", "workAreaXYWH", "hwnd"))
    if "native" in value:
        result["native"] = subset(value["native"], ("version", "byteSize", "sequence", "submittedPresentId", "lastPresentHRESULT", "lastFrameMotion", "lastFrameContent", "currentRect", "sourceWidth", "sourceHeight", "targetWidth", "targetHeight", "sourceFormat", "targetFormat", "hostLeft", "hostTop", "hostWidth", "hostHeight"))
    return result

def pixels(value):
    result = subset(value, ("comparison", "sampledCycle", "status", "contentDelivery", "contentDeliveryScope", "pixels", "differentPixels",
        "differencePercent", "rgbDifferentPixels", "maxChannelDifference", "meanChannelDifference",
        "alphaDifferentPixels", "mismatchBoundsLTRB", "rowMismatchHistogram", "columnMismatchHistogram",
        "regions", "luminance", "geometryEdges", "constantOffsetSearch", "scaleSearch", "staleFrameComparisons",
        "colorDifference", "colorSpaceHypotheses", "sharpnessProxy"))
    for owner in ("before", "after"):
        if owner in value:
            result[owner] = subset(value[owner], ("shape", "sha256", "alpha"))
    if "pixels" not in result and "before" in result:
        shape = result["before"].get("shape", [])
        if len(shape) == 3:
            result["pixels"] = shape[0] * shape[1]
    if "differencePercent" not in result and result.get("pixels"):
        result["differencePercent"] = 100 * result.get("differentPixels", 0) / result["pixels"]
    for region in result.get("regions", {}).values():
        if "differencePercent" not in region:
            region["differencePercent"] = 100 * region["differentPixels"] / region["pixels"] if region["pixels"] else None
    result["comparisonRole"] = ("Deliberate native-removal negative control; difference is expected"
        if result["comparison"] == "source-gpu-to-native-removed-pixels" else
        "Two visible endpoint surfaces overlap; every nonzero pixel remains visible evidence"
        if result["comparison"] == "source-live-to-overlap-pixels" else "Required endpoint equality")
    return result

def observation(event, command, native_start):
    result = subset(event, ("label", "status", "comparisonRectangleXYWH", "expectedRectangleXYWH",
        "polls", "minimumObserverGeneration", "stateMismatchesBefore", "stateMismatchesAfter",
        "expectedVisualWitness", "rejectedObservations", "reason"))
    result.update(observedAfterCommandMs=relative(event.get("observedAtSeconds"), command),
        observedAfterNativeStartMs=relative(event.get("observedAtSeconds"), native_start),
        lowerBoundAfterCommandMs=relative(event.get("afterPresentationSeconds"), command),
        observationWaitMs=relative(event.get("observedAtSeconds"), event.get("observationStartedSeconds")))
    frame = event.get("frame", {})
    result["frame"] = subset(frame, ("freshAcquisition", "cacheFallbackAllowed", "desktopPixelsUpdated",
        "pointerOnlyFrame", "newDeliveryObserved", "timestampEvidence", "acquisitionSequence",
        "acquisitionSessionGeneration", "observerGeneration", "lastComparisonGeneration", "delivery",
        "usableDesktopDelivery", "contentDelivery", "accumulatedFrames", "visualWitness",
        "witnessMatchedPixels", "witnessRectangleXYWH", "rectangleXYWH", "outputLocalRegionLTRB", "outputDesktopXYWH", "rotationDegrees", "qpcFrequency"))
    result["frame"].update(desktopRasterAfterCommandMs=relative(frame.get("desktopFrameSeconds"), command),
        rasterAfterPresentationLowerBoundMs=relative(frame.get("desktopFrameSeconds"), event.get("afterPresentationSeconds")),
        acquisitionCallMs=relative(frame.get("callFinished"), frame.get("callStarted")))
    result["stateBefore"], result["stateAfter"] = state(event.get("stateBefore", {})), state(event.get("stateAfter", {}))
    return result

def cycle_summary(number, events, data):
    command_row = next((e for e in events if e["event"] == "command"), {})
    command = command_row.get("t")
    notification = next((e.get("t") for e in events if e["event"] == "native-clock-start"), None)
    # Native elapsed is sampled by the wrapper immediately before its event timestamp.
    # Infer the native start from that sample; retain GUI notification separately.
    elapsed_row = next((e for e in events if e["event"] == "native-endpoint-submitted"), None)
    if elapsed_row is None:
        elapsed_row = next((e for e in events if e["event"] == "target-gpu-composition-committed"), None)
    inferred_start = elapsed_row["t"] - elapsed_row["elapsedMs"] / 1000 if elapsed_row else None
    composition = next((e for e in events if e["event"] == "source-composition-committed"), {})
    cycle = {"cycle": number, "direction": command_row.get("kind"),
        "clockScope": "Inferred native QPC start from adjacent elapsed API sample; GUI boundary includes scheduling overhead; not scanout",
        "nativeStartAfterCommandMs": relative(inferred_start, command),
        "nativeNotificationAfterCommandMs": relative(notification, command),
        "geometry": subset(composition, ("source", "target", "envelope")), "timings": [],
        "observations": [], "pixelComparisons": [], "windowStates": [], "qtStages": []}
    accepted_names = {"input-lock-issued", "input-locked", "source-composition-committed", "native-clock-start",
        "intentional-gui-delay-end", "layout-begin", "layout-committed", "target-gpu-composition-committed",
        "native-endpoint-submitted", "desktop-endpoint-measurement", "live-host-revealed", "first-live-host-frame",
        "live-handoff", "input-restore-issued", "input-restored", "webengine-html-ready"}
    for event in events:
        name = event["event"]
        if name == "desktop-observation":
            cycle["observations"].append(observation(event, command, inferred_start))
        elif name == "physical-window-state":
            cycle["windowStates"].append({"label": event.get("label"), **state(event)})
        elif name == "gpu-capture":
            timing = subset(event, ("kind", "client", "size", "graphicsApi", "gpuOnly", "targetImported"))
            timing["event"] = name
            for key in ("requested", "renderCallback", "captureFinished", "targetImportStarted", "targetImportFinished"):
                if key in event:
                    timing[key + "AfterCommandMs"] = relative(event[key], command)
                    timing[key + "AfterNativeStartMs"] = relative(event[key], inferred_start)
            timing["exportMs"] = relative(event.get("captureFinished"), event.get("renderCallback"))
            timing["renderRequestToCallbackMs"] = relative(event.get("renderCallback"), event.get("requested"))
            timing["importCallMs"] = relative(event.get("targetImportFinished"), event.get("targetImportStarted"))
            cycle["timings"].append(timing)
        elif name in accepted_names:
            timing = {"event": name, "afterCommandMs": relative(event.get("t"), command),
                "afterNativeStartMs": relative(event.get("t"), inferred_start),
                **subset(event, ("actualClient", "commandToLiveMs", "elapsedMs", "diagnosticHoldMs",
                    "durationMs", "transferDeadlineMs", "importThread", "measuredMs", "nativeEnabled", "qmlInteractive"))}
            native = event.get("native", {})
            for key, value in native.items():
                if key.endswith("Seconds") and value:
                    timing.setdefault("nativeApi", {})[key + "AfterNativeStartMs"] = relative(value, inferred_start)
            for key in ("importStarted", "importFinished"):
                if event.get(key):
                    timing[key + "AfterNativeStartMs"] = relative(event[key], inferred_start)
            cycle["timings"].append(timing)
        elif name in ("physical-source-regions", "physical-target-regions"):
            cycle.setdefault("physicalRegions", []).append({"event": name,
                **subset(event, ("contentXYWH", "clientXYWH", "comparisonXYWH", "headerHeightPx", "borderPx", "regions"))})
        elif name == "native-present-history":
            rows = []
            for raw in event.get("rows", []):
                row = subset(raw, ("sequence", "submittedPresentId", "presentHRESULT", "elapsedSeconds", "motion", "content", "currentRect"))
                row.update(presentBeginAfterNativeStartMs=relative(raw.get("presentBeginSeconds"), inferred_start),
                    presentReturnAfterNativeStartMs=relative(raw.get("presentReturnSeconds"), inferred_start))
                rows.append(row)
            cycle["nativeSubmittedHistory"] = {"totalFrames": event.get("totalFrames"),
                "truncated": event.get("truncated"), "rows": rows}
            cycle["firstMovingSubmittedFrame"] = next((r for r in rows if r.get("motion", 0) > 0 and not r.get("presentHRESULT", 0) & 0x80000000), None)
            cycle["firstTargetBearingSubmittedFrame"] = next((r for r in rows if r.get("content", 0) > 0 and not r.get("presentHRESULT", 0) & 0x80000000), None)
    for event in data.get("events", []):
        if event["event"] == "physical-pixel-analysis" and event.get("sampledCycle") == number:
            cycle["pixelComparisons"].append(pixels(event))
    boundaries = [b for b in data.get("profileBoundaries", []) if b.get("cycle") == number]
    cycle["boundaryDurationsMs"] = {}
    for before in boundaries:
        if before.get("boundary", "").startswith("before:"):
            name = before["boundary"][7:]
            after = next((b for b in boundaries if b.get("boundary") == "after:" + name), None)
            if after:
                cycle["boundaryDurationsMs"][name] = relative(after.get("t"), before.get("t"))
    for qt in data.get("qtStageTimings", []):
        if qt.get("cycle") == number:
            stages = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+) ms", qt.get("message", ""))}
            if stages:
                cycle["qtStages"].append({"afterCommandMs": relative(qt.get("t"), command), "cpuCompositeMs": stages})
    begin = next((e.get("t") for e in events if e["event"] == "layout-begin"), None)
    committed = next((e.get("t") for e in events if e["event"] == "layout-committed"), None)
    cycle["geometryCommitMs"] = relative(committed, begin)
    return cycle

def collect(folder):
    path = folder / "native_gpu_spike.json"
    data = read(path)
    if data is None:
        failed = read(folder / "fixture_failure.json") or read(folder / "fixture_stall.json") or read(folder / "continuation_classification.json")
        return {"runId": folder.name, "status": "FAILED BEFORE NORMAL RESULT" if failed else "INCOMPLETE",
            "rawFailurePreserved": failed is not None, "reason": safe_error((failed or {}).get("reason", "No completed raw result")),
            "resultSha256": sha(folder / ("fixture_failure.json" if (folder / "fixture_failure.json").exists() else "fixture_stall.json" if (folder / "fixture_stall.json").exists() else "continuation_classification.json")) if failed else None}
    config = subset(data.get("configuration", {}), ("cycles", "gui_delay_ms", "duration_ms", "blend_start_ms",
        "capture_only", "prepared_target", "endpoint_pixels", "endpoint_hold_ms", "layout_repair", "qt_render_timings",
        "qt_layout_polish", "layout_only", "render_target_import", "first_direction", "workspace", "keep_visible",
        "physical_diagnostics", "source_observation_only", "source_unlocked", "source_markers", "restored_size", "fanout_variant"))
    events = data.get("events", [])
    failures = [safe_error(failure) for failure in data.get("failures", [])]
    protected = read(folder / "protected_hashes.json")
    result = {"runId": folder.name, "resultSha256": sha(path), "status": "FAIL" if failures else
        "INCOMPLETE" if data.get("completedCycles", 0) < config.get("cycles", 1) else
        "SOURCE CONTROL; NOT CANDIDATE" if config.get("source_observation_only") else
        "LAYOUT CONTROL; NOT CANDIDATE" if config.get("layout_only") else "ENDPOINT RUN COMPLETE; CANDIDATE UNQUALIFIED",
        "configuration": config, "completedInternalDirections": data.get("completedCycles", 0),
        "normalFinishRecorded": any(e["event"] == "spike-finished" for e in events), "failures": failures,
        "candidateQualified": False, "rawImagesPublished": 0, "dllSha256": data.get("dllHash"),
        "sourceSha256": {k: v for k, v in data.get("sourceProvenance", {}).get("sources", {}).items()
            if not re.search(r"[A-Z]:|^[/\\]", k) and HASH.fullmatch(v)},
        "protectedOriginals": {"manifestPresent": protected is not None,
            "unchanged": (protected or {}).get("unchanged"), "artifactCount": len((protected or {}).get("before", {}))},
        "cycles": [], "freshObserverGateCounts": dict(Counter(e.get("status", "UNKNOWN") for e in events if e["event"] == "desktop-observation")),
        "pixelAnalysisFailures": [{"sampledCycle": e.get("sampledCycle"), "comparison": e.get("comparison")}
            for e in events if e["event"] == "physical-pixel-analysis-failure"]}
    ids = sorted({e["cycle"] for e in events if e["event"] == "command"})
    for number in ids:
        result["cycles"].append(cycle_summary(number, [e for e in events if e.get("cycle") == number], data))
    # Cleanup input unlock can be stamped one cycle beyond the final control.
    result["inputRestorationEvents"] = [{"cycle": e.get("cycle"), **subset(e, ("nativeEnabled", "qmlInteractive"))}
        for e in events if e["event"] == "input-restored"]
    result["webEngineHTMLLoadObserved"] = any(e["event"] == "webengine-html-ready" for e in events)
    comparisons = [p for c in result["cycles"] for p in c["pixelComparisons"]]
    result["requiredEndpointEqualityCounts"] = dict(Counter(p["status"] for p in comparisons
        if p["comparisonRole"] == "Required endpoint equality"))
    result["sourceOverlapDifferentPixelCounts"] = [p.get("differentPixels") for p in comparisons
        if p["comparison"] == "source-live-to-overlap-pixels"]
    result["allSourcePresentationPixelsExact"] = (not any(result["sourceOverlapDifferentPixelCounts"]) and all(
        p["status"] == "PASS" for p in comparisons if p["comparison"] == "source-live-to-gpu-pixels")
        ) if comparisons else None
    result["sourcePresentationComparisonsRecorded"] = sum(p["comparison"].startswith("source-live-to-") for p in comparisons)
    if any(result["sourceOverlapDifferentPixelCounts"]) or result["requiredEndpointEqualityCounts"].get("FAIL", 0):
        result["rawRecordedStatus"] = result["status"]
        result["status"] = "FAIL"
        result["qualificationFailureReason"] = "Every observed nonzero source overlap or required endpoint difference remains a failure"
    return result

def validate(result):
    """Conservation/freshness checks on the exported evidence, not GUI execution."""
    checked_pixels = checked_gates = 0
    for run in result["runs"]:
        for cycle in run.get("cycles", []):
            for comparison in cycle["pixelComparisons"]:
                if "differentPixels" not in comparison:
                    continue
                checked_pixels += 1
                count = comparison["differentPixels"]
                assert 0 <= count <= comparison["pixels"]
                assert comparison.get("rgbDifferentPixels", count) <= count
                for histogram in ("rowMismatchHistogram", "columnMismatchHistogram"):
                    if histogram in comparison:
                        assert sum(comparison[histogram]) == count
                for region in comparison.get("regions", {}).values():
                    assert 0 <= region["differentPixels"] <= region["pixels"]
                assert comparison["status"] == ("PASS" if count == 0 else "FAIL")
            for gate in cycle["observations"]:
                if gate["status"] != "PASS":
                    continue
                checked_gates += 1
                frame = gate["frame"]
                assert frame["freshAcquisition"] and frame["newDeliveryObserved"]
                assert frame["desktopPixelsUpdated"] and frame["usableDesktopDelivery"]
                assert frame["cacheFallbackAllowed"] is False
                assert frame["rasterAfterPresentationLowerBoundMs"] > 0
                assert frame["rectangleXYWH"] == gate["expectedRectangleXYWH"]
                assert frame["observerGeneration"] > frame["lastComparisonGeneration"]
                if gate.get("expectedVisualWitness"):
                    assert all(frame["visualWitness"].get(k) == v for k,v in gate["expectedVisualWitness"].items())
    return {"pixelConservationChecks": checked_pixels, "freshGateChecks": checked_gates,
        "scope": "Sandbox-safe aggregate conservation and accepted-gate evidence checks only"}

def main():
    folders = sorted(p for p in (ROOT / "logs").glob("native_gpu_*20261004_run*") if p.is_dir())
    runs = [collect(folder) for folder in folders]
    result = {"schemaVersion": 1, "recordedDate": "2026-10-04", "status": "CANDIDATE NOT QUALIFIED",
        "scope": "Sanitized observer, geometry, API and exact pixel evidence; all raw failures stay ignored locally. No private raster or absolute personal paths.",
        "measurementLimits": ["Fresh DXGI raster delivery is distinct from physical scanout and submitted Present.",
            "Same-swapchain visual witness must match intended revision/phase; static content hashes alone do not prove freshness.",
            "compositionCommitGeneration is the fixture's source-commit indicator, not a per-frame compositor presentation revision.",
            "Overlap source corners remain nonzero visible evidence, without owner visual acceptance.",
            "No production A/B speed ratio, complete continuous-motion trace, mixed-DPI acceptance or installed package validation is established.",
            "Input timings are GUI-observed native enabled/QML interactive state, not physical click-to-input acceptance.",
            "Qt composite CPU timers contain export/import when performed in render callbacks; nested stages cannot be added twice."],
        "runs": runs,
        "validationSplit": {"aggregateCollection": "Sandbox-safe read-only JSON/hash inspection",
            "desktopRuns": "Outside sandbox on disposable profiles, as recorded by root",
            "webEngine": "Actual existing-preview HTML load only where event is present; PDF and packaged startup unvalidated",
            "productionChanges": False, "ownerAcceptance": False}}
    result["aggregateValidation"] = validate(result)
    serialized = json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    if re.search(r"[A-Z]:[\\/]|@|\.xlsm", serialized) or Path.home().name.lower() in serialized.lower():
        raise ValueError("Portable aggregate privacy screening rejected content")
    JSON_OUT.write_text(serialized, encoding="utf-8")
    lines = ["# Physical qualification continuation — 2026-10-04", "",
        "The observer now distinguishes fresh DXGI desktop raster deliveries from cached results and pointer-only updates. Exact same-swapchain revision witnesses additionally test the intended native representation. The complete cold candidate remains **unqualified**; every failed predecessor is retained.", "",
        "Full counts, mismatch histograms, named regions, alignment/color diagnostics, geometry, source/DLL provenance and relative timing chains are in `CLEANROOM_PHYSICAL_QUALIFICATION_RESULTS_2026-10-04.json`. Raw captures, profiles and logs remain ignored locally; no private screenshot is published.", "",
        "| Run | Status | Internal directions | Fresh gates pass/fail | Required source / target comparisons |", "| --- | --- | ---: | --- | --- |"]
    for run in runs:
        comparisons = [p for c in run.get("cycles", []) for p in c.get("pixelComparisons", []) if p["comparisonRole"] == "Required endpoint equality"]
        source = [p.get("differentPixels") for p in comparisons if p["comparison"] == "source-live-to-gpu-pixels"]
        target = [p.get("differentPixels") for p in comparisons if p["comparison"] == "gpu-to-live-target-pixels"]
        gates = run.get("freshObserverGateCounts", {})
        lines.append(f"| `{run['runId']}` | {run['status']} | {run.get('completedInternalDirections', 0)} | {gates.get('PASS', 0)} / {gates.get('FAIL', 0)} | source {source or 'unmeasured'}; target {target or 'unmeasured'} |")
    lines.extend(["", "Cold target readiness and later observation remain separate measured boundaries:", "",
        "| Cold run / cycle | Direction | Geometry commit ms | Render-callback target import after native start ms | Fresh endpoint / live desktop observation after native start ms | Input-restored GUI observation after command ms |",
        "| --- | --- | ---: | ---: | --- | ---: |"])
    for run in runs:
        if not run.get("configuration", {}).get("physical_diagnostics") or run.get("configuration", {}).get("source_observation_only"):
            continue
        for cycle in run.get("cycles", []):
            if cycle.get("nativeStartAfterCommandMs") is None:
                continue
            captures = [e for e in cycle["timings"] if e["event"] == "gpu-capture" and e.get("kind") == "target"]
            imported = next((e.get("targetImportFinishedAfterNativeStartMs") for e in captures), None)
            observed = {e["label"]: e["observedAfterNativeStartMs"] for e in cycle["observations"] if e["status"] == "PASS"}
            restored = next((e["afterCommandMs"] for e in cycle["timings"] if e["event"] == "input-restored"), None)
            lines.append(f"| `{run['runId']}` / {cycle['cycle']} | {cycle['direction']} | {cycle.get('geometryCommitMs')} | {imported} | {observed.get('target-endpoint')} / {observed.get('target-live')} | {restored} |")
    lines.extend(["", "Source overlap comparisons retain every mismatching pixel. The recurring sixteen differences fall at the four rounded content corners: rows `8, 10, 11, 15, 540, 544, 545, 547` and columns `8, 10, 11, 15, 760, 764, 765, 767`, two differences at each listed row/column in the small Time Entry control. Stacking partially transparent source corners is a working explanation. Exact hidden-source equality and a deliberate native-removal difference are separate controls; they do not authorize ignoring those corner pixels. **Cory remains the authority for every nonzero visual difference.**", "",
        "The first fresh source run fails its witness despite newly delivered raster frames: its marker occupied the taskbar band while the native host was below the live host in observed Z-order. The source-only control chooses an observable margin outside its actual source; cold qualification must keep the witness outside both true endpoints. A native `HWND_TOP` ordering trial has passing samples, but later witness failures remain failures and do not certify universal visibility.", "",
        "Later fixture startup explicitly requests activation. The final sampler brackets the observed foreground HWND, visibility, client rectangle and state; the app can remain observable above another foreground window. It never treats activation API success as visible-frame proof. Earlier Home, Directory and Productivity acquisition crops exceeded the selected output; the first invoice fixture also produced inconsistent content/client geometry. These preserved setup failures do not measure the engine's source fidelity or restore readiness. The foreground Client Directory source control subsequently supplies a fresh source witness and exact hidden-source pixels, while its nonzero overlap remains a recorded failure.", "",
        "The first cold Time Entry run completed four internal directions and twenty passing fresh observations, then failed deferred spatial analysis because source regions were reused for a differently sized target. Its incomplete analysis and cleanup timeout remain failed evidence. Root retained the raw result and normally closed only its owned fixture. Per-cycle target regions and bounded exception cleanup were corrected before follow-up runs.", "",
        "The restored target now adopts normal visibility padding before host-envelope and canvas geometry, then publishes its complete target metrics. The earlier instrumented layout-only restore/maximize control observes normal restored client extent `1122×782` for `1100×760` content. Restore width/height propagation is `12/10 ms`, padding `1 ms`, metrics publication `74 ms`; maximize is `11/11 ms`, padding `2 ms`, publication `62 ms`. These perturbed CPU observations do not establish cold native readiness or a causal speed ratio.", "",
        "All motion/delivery settings remain fixed at 350 ms native motion / 240 ms target-transfer deadline; qualifying cold configurations have zero prepared target, zero configured endpoint hold and zero intentional GUI delay. A fresh-observer wait is measurement overhead and can leave a static endpoint visible while qualification proceeds. No passing endpoint comparison here proves uninterrupted handoff or the requested threefold speed gain.", "",
        "Validation split: this report's collector performs **sandbox-safe JSON, hash and privacy checks only**. Root's actual desktop/Qt runs occur **outside sandbox** with disposable settings/workbooks and protected-original manifests. WebEngine evidence is the existing-preview HTML load event only where recorded. New PDF, installed-package, physical mixed-DPI, complete lifecycle and owner acceptance gates remain open. Production and the installed package are unchanged.", ""])
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"runs": len(runs), "statuses": dict(Counter(r["status"] for r in runs)),
        "freshGateCounts": dict(sum((Counter(r.get("freshObserverGateCounts", {})) for r in runs), Counter())),
        "outputBytes": len(serialized)}, sort_keys=True))

if __name__ == "__main__":
    main()
