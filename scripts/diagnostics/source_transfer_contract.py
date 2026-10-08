"""Passive bounded evidence for the owned source visibility transfer.

No retry, activation, message delivery or native state change belongs to reading
this contract. Diagnostic tracing is enabled explicitly before source preparation.
"""
import ctypes
import math


class SourceTransferObservation(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ("version", "byteSize")]
    _fields_ += [(name, ctypes.c_uint64) for name in ("hostGeneration", "sequence")]
    _fields_ += [(name, ctypes.c_uint32) for name in (
        "stage", "accepted", "win32Error", "expectedTopmost", "currentThreadId",
        "currentProcessId", "liveThreadId", "liveProcessId", "nativeThreadId",
        "nativeProcessId", "sameParent", "sameProcess", "liveThreadOwned",
        "nativeThreadOwned", "liveForegroundEntry", "liveForegroundExit",
        "liveOwnerRelation", "nativeOwnerRelation", "liveStyleEntry",
        "nativeStyleEntry", "liveStyleExit", "nativeStyleExit", "liveVisibleEntry",
        "nativeVisibleEntry", "liveVisibleExit", "nativeVisibleExit", "beginAccepted",
        "liveDeferAccepted", "nativeDeferAccepted", "endAccepted")]
    _fields_ += [(name, ctypes.c_double) for name in ("entrySeconds", "beginBatchSeconds",
        "endBatchBeginSeconds", "endBatchReturnSeconds", "exitSeconds")]
    _fields_ += [(name, ctypes.c_uint32) for name in ("traceEnabled", "policySampled")]


class SourceWindowposRow(ctypes.Structure):
    _fields_ = [("sequence", ctypes.c_uint64), ("timeSeconds", ctypes.c_double)]
    _fields_ += [(name, ctypes.c_uint32) for name in ("message", "phase",
        "insertAfterBandBefore", "insertAfterBandAfter", "flagsBefore", "flagsAfter",
        "styleBefore", "styleAfter", "currentThreadId", "expectedTopmost",
        "visibleAfter", "reserved")]


class SourceWindowposTrace(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ("version", "byteSize", "rowByteSize", "count")]
    _fields_ += [("totalRows", ctypes.c_uint64), ("rows", SourceWindowposRow * 16)]


def enable_source_transfer_trace(dll, host):
    if not host or not hasattr(dll, "cspm_comp_enable_source_transfer_trace"):
        raise RuntimeError("Owned source-transfer trace unavailable")
    function = dll.cspm_comp_enable_source_transfer_trace
    function.argtypes, function.restype = [ctypes.c_void_p], ctypes.c_int
    if not function(host):
        raise RuntimeError("Owned source-transfer trace must precede source preparation")


def _read(dll, host, name, kind, size):
    if not host or not hasattr(dll, name) or ctypes.sizeof(kind) != size:
        raise RuntimeError("Owned source-transfer observation ABI unavailable")
    value = kind()
    value.version, value.byteSize = 1, size
    if isinstance(value, SourceWindowposTrace):
        value.rowByteSize = ctypes.sizeof(SourceWindowposRow)
    function = getattr(dll, name)
    function.argtypes, function.restype = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint], ctypes.c_int
    if not function(host, ctypes.byref(value), size):
        raise RuntimeError("Owned source-transfer observation rejected")
    if value.version != 1 or value.byteSize != size:
        raise RuntimeError("Owned source-transfer observation ABI differs")
    return value


def source_transfer_evidence(dll, host):
    observation = _read(dll, host, "cspm_comp_source_transfer_observation", SourceTransferObservation, 192)
    trace = _read(dll, host, "cspm_comp_source_windowpos_trace", SourceWindowposTrace, 1048)
    if (not observation.hostGeneration or not observation.sequence
            or observation.traceEnabled != 1 or not 2 <= observation.stage <= 11
            or observation.accepted != int(observation.stage == 9)):
        raise RuntimeError("Owned source-transfer terminal evidence is unmeasured")
    boolean_fields = ("expectedTopmost", "sameParent", "sameProcess", "liveThreadOwned",
        "nativeThreadOwned", "liveForegroundEntry", "liveForegroundExit", "liveVisibleEntry",
        "nativeVisibleEntry", "liveVisibleExit", "nativeVisibleExit", "beginAccepted",
        "liveDeferAccepted", "nativeDeferAccepted", "endAccepted", "policySampled")
    if (any(getattr(observation, name) > 1 for name in boolean_fields)
            or observation.liveOwnerRelation > 5 or observation.nativeOwnerRelation > 5):
        raise RuntimeError("Owned source-transfer observation contains incompatible enum or boolean metadata")
    if (not math.isfinite(observation.entrySeconds) or not math.isfinite(observation.exitSeconds)
            or not 0 < observation.entrySeconds <= observation.exitSeconds):
        raise RuntimeError("Owned source-transfer API timestamps are invalid")
    previous_time = observation.entrySeconds
    for name in ("beginBatchSeconds", "endBatchBeginSeconds", "endBatchReturnSeconds"):
        measured = getattr(observation, name)
        if not math.isfinite(measured) or measured < 0:
            raise RuntimeError("Owned source-transfer intermediate timestamp is invalid")
        if measured:
            if not previous_time <= measured <= observation.exitSeconds:
                raise RuntimeError("Owned source-transfer intermediate timestamps are reversed")
            previous_time = measured
    if trace.rowByteSize != 64 or trace.count > 16 or trace.count > trace.totalRows:
        raise RuntimeError("Owned source-transfer message trace is invalid")
    rows = []
    previous_sequence, previous_time = 0, 0
    for row in trace.rows[:trace.count]:
        if (row.sequence <= previous_sequence or row.sequence > trace.totalRows or not math.isfinite(row.timeSeconds)
                or row.timeSeconds < observation.entrySeconds or row.timeSeconds < previous_time
                or row.message not in (0x46, 0x47) or row.insertAfterBandBefore > 7
                or row.insertAfterBandAfter > 7 or not 1 <= row.phase <= 11
                or row.expectedTopmost > 1 or row.visibleAfter > 1 or row.reserved != 0):
            raise RuntimeError("Owned window-position row is invalid")
        rows.append({name: getattr(row, name) for name, _ in SourceWindowposRow._fields_})
        previous_sequence, previous_time = row.sequence, row.timeSeconds
    return {"observation": {name: getattr(observation, name)
                for name, _ in SourceTransferObservation._fields_},
        "messages": rows, "totalRows": trace.totalRows, "truncated": trace.totalRows > trace.count,
        "scope": "Passive owned HWND API/message evidence; late messages retain timestamps; no activation/retry or pixel proof"}
