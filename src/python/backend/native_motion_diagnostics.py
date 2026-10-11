"""Opt-in candidate timing; reads existing ABI snapshots, never consumes slots.

No financial records or framebuffer pixels are collected. Native call tracing
does add metadata cost, which is reported; uninstrumented comparisons remain
separate. Snapshots are copied before owned teardown and logged after cleanup.
"""
from __future__ import annotations

import ctypes
import json
import logging
import struct
import time

log = logging.getLogger("motion")
TRACE_BYTES, ROW_BYTES, ROWS_OFFSET = 230312, 896, 936


class MotionDiagnostics:
    def __init__(self, dll):
        self.dll = dll
        pointer, uint = ctypes.c_void_p, ctypes.c_uint
        for name, arguments, result in (
            ("cspm_comp_enable_native_call_trace", [pointer], ctypes.c_int),
            ("cspm_comp_set_native_trace_live", [pointer, ctypes.c_size_t], ctypes.c_int),
            ("cspm_comp_native_call_trace", [pointer, pointer, uint], ctypes.c_int),
            ("cspm_comp_observation", [pointer, pointer, uint], ctypes.c_int),
            ("cspm_comp_elapsed_ms", [pointer], ctypes.c_double),
        ):
            function = getattr(dll, name)
            function.argtypes, function.restype = arguments, result

    def begin(self, transaction):
        transaction["diagnostic"] = dict(sequence=transaction["sequence"], direction=transaction["direction"],
            source=transaction["source"], target=transaction["target"], dpr=transaction["window"].devicePixelRatio(),
            events=[], nativeTraceEnabled=False, observationalOnly=True, timingGatesChanged=False)
        self.mark(transaction, "begin")

    def mark(self, transaction, stage):
        event = dict(stage=stage, qpcSeconds=time.perf_counter())
        if transaction["started"] and transaction["host"] and not transaction.get("cancelled", False):
            event["nativeElapsedMs"] = self.dll.cspm_comp_elapsed_ms(transaction["host"])
        transaction["diagnostic"]["events"].append(event)

    def enable_native_trace(self, transaction):
        host = transaction["host"]
        enabled = bool(self.dll.cspm_comp_enable_native_call_trace(host))
        if enabled:
            enabled = bool(self.dll.cspm_comp_set_native_trace_live(host, int(transaction["window"].winId())))
        transaction["diagnostic"]["nativeTraceEnabled"] = enabled
        self.mark(transaction, "native_trace_configured")

    def snapshot(self, transaction, outcome):
        report = transaction["diagnostic"]
        report["outcome"] = outcome
        self.mark(transaction, "live_recovered_before_teardown")
        if not transaction["host"]:
            return
        started = time.perf_counter()
        observation = ctypes.create_string_buffer(208)
        struct.pack_into("<II", observation, 0, 1, 208)
        if self.dll.cspm_comp_observation(transaction["host"], ctypes.byref(observation), 208):
            raw = observation.raw
            times = struct.unpack_from("<16d", raw, 24)
            names = ("lastPresentBegin", "lastPresentReturn", "sourceCommitBegin", "sourceCommitReturn",
                "sourceWaitBegin", "sourceWaitReturn", "sourceShowBegin", "sourceShowReturn",
                "targetImportBegin", "targetReady", "endpointPresentReturn", "hostHideBegin", "hostHideReturn",
                "lastFrameElapsed", "lastFrameMotion", "lastFrameContent")
            # Observation has sixteen doubles followed by currentRect[4].
            report["nativeObservation"] = dict(zip(names, times[:16]))
        buffer = ctypes.create_string_buffer(TRACE_BYTES)
        struct.pack_into("<4I", buffer, 0, 1, TRACE_BYTES, ROW_BYTES, 0)
        if self.dll.cspm_comp_native_call_trace(transaction["host"], ctypes.byref(buffer), TRACE_BYTES):
            raw = buffer.raw
            count = min(struct.unpack_from("<I", raw, 12)[0], 256)
            calls = []
            for index in range(count):
                offset = ROWS_OFFSET + index*ROW_BYTES
                call, phase = struct.unpack_from("<II", raw, offset+8)
                begin, end = struct.unpack_from("<dd", raw, offset+48)
                result, error, _, timeout = struct.unpack_from("<4I", raw, offset+64)
                overhead = struct.unpack_from("<I", raw, offset+276)[0]
                calls.append(dict(call=call, phase=phase, beginSeconds=begin, returnSeconds=end,
                    durationMs=(end-begin)*1000, result=result, win32Error=error,
                    timeoutMs=timeout, diagnosticOverheadUs=overhead))
            report["nativeCalls"] = calls
            report["nativeCallRowsDropped"] = struct.unpack_from("<Q", raw, 24)[0]
            report["nativeMetadataOverheadMs"] = sum(row["diagnosticOverheadUs"] for row in calls)/1000
        report["postOutcomeSnapshotMs"] = (time.perf_counter()-started)*1000

    def publish(self, transaction):
        log.info("motion measurement=%s", json.dumps(transaction["diagnostic"], separators=(",", ":")))
