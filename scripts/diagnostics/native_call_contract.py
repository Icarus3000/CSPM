"""Read bounded native API evidence without waiting or changing window state.

Raw handles belong to local evidence only. API success and DXGI availability are
not desktop presentation witnesses; callers must sanitize published aggregates.
"""
import ctypes
import math


CALL_NAMES = dict(enumerate((
    "WaitForSingleObjectEx(frame-latency)", "SetWindowPos(source-band)",
    "BeginDeferWindowPos", "DeferWindowPos(live-hide)",
    "DeferWindowPos(native-show)", "EndDeferWindowPos", "IDCompositionDevice::Commit",
    "IDCompositionDevice::WaitForCommitCompletion", "SetWindowPos(source-show)",
    "SetWindowPos(witness)", "IDXGIKeyedMutex::AcquireSync", "IDXGIKeyedMutex::ReleaseSync",
    "IDXGISwapChain::Present", "IDXGISwapChain::GetLastPresentCount",
    "IDXGISwapChain::GetFrameStatistics", "IDXGISwapChain::GetBuffer",
    "ID3D11Device::OpenSharedResource", "ID3D11Device::CreateTexture2D",
    "ID3D11Device::CreateShaderResourceView", "ID3D11Device::CreateRenderTargetView",
    "PostMessageW(command)", "future::wait_for(command)", "PostMessageW(destroy)",
    "WaitForSingleObject(destroy)", "ShowWindow(hide-host)", "SetTimer",
    "ValidateSourceBand",
), 1))
PHASE_NAMES = {1: "preparation", 2: "source-transfer", 3: "motion", 4: "target", 5: "cleanup"}
WAIT_STATES = {0: "unprobed", 1: "signaled-or-consumed", 2: "timeout", 3: "failed", 4: "abandoned", 5: "other"}
MUTEX_STATES = {0: "not-applicable", 1: "acquired", 2: "acquire-rejected", 3: "released", 4: "release-rejected"}


class NativeWindowState(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("window", "foreground", "focus", "active", "owner")]
    _fields_ += [(name, ctypes.c_uint32) for name in (
        "thread", "process", "foregroundThread", "foregroundProcess", "guiFlags", "valid",
        "visible", "iconic", "zoomed", "cloaked", "cloakHRESULT", "style", "exstyle", "queryErrors")]
    _fields_ += [(name, ctypes.c_int32 * 4) for name in ("windowRect", "clientRect", "workRect")]
    _fields_ += [("dpi", ctypes.c_uint32), ("reserved", ctypes.c_uint32)]


class NativeCallRow(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ("version", "byteSize", "call", "phase")]
    _fields_ += [(name, ctypes.c_uint64) for name in ("sequence", "startQpc", "returnQpc", "qpcFrequency")]
    _fields_ += [("beginSeconds", ctypes.c_double), ("returnSeconds", ctypes.c_double)]
    _fields_ += [(name, ctypes.c_uint32) for name in (
        "result", "win32Error", "lastErrorApplicable", "timeoutMs", "waitStateBefore",
        "waitStateAfter", "alertable", "flagsBefore", "flagsAfter", "currentThread", "guiThread",
        "workerThread", "expectedPresentId", "submittedBefore", "submittedAfter", "displayedBefore",
        "displayedAfter", "statisticsHRESULT", "bufferIndex", "bufferCount")]
    _fields_ += [(name, ctypes.c_uint64) for name in (
        "expectedHostGeneration", "hostGeneration", "expectedSourceGeneration", "sourceGeneration",
        "expectedTargetGeneration", "targetGeneration", "commitBefore", "commitAfter", "adapterIdentity",
        "deviceIdentity", "swapchainIdentity", "waitIdentity", "sourceResourceIdentity", "targetResourceIdentity",
        "keyedMutexKey")]
    _fields_ += [(name, ctypes.c_uint32) for name in ("keyedMutexState", "fenceState", "beforeMotion", "diagnosticOverheadUs")]
    _fields_ += [(name, NativeWindowState) for name in ("nativeBefore", "nativeAfter", "liveBefore", "liveAfter")]
    _fields_ += [("adapterLuid", ctypes.c_int64)]


class NativeCallTrace(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ("version", "byteSize", "rowByteSize", "count")]
    _fields_ += [(name, ctypes.c_uint64) for name in ("totalRows", "droppedRows")]
    _fields_ += [("enabled", ctypes.c_uint32), ("hasFirstFailure", ctypes.c_uint32)]
    _fields_ += [("firstFailure", NativeCallRow), ("rows", NativeCallRow * 256)]


def enable_native_call_trace(dll, host):
    if not host or not hasattr(dll, "cspm_comp_enable_native_call_trace"):
        raise RuntimeError("Native call trace unavailable")
    function = dll.cspm_comp_enable_native_call_trace
    function.argtypes, function.restype = [ctypes.c_void_p], ctypes.c_int
    if function(host) != 1:
        raise RuntimeError("Native call trace must precede source preparation")


def set_native_trace_live(dll, host, live_hwnd):
    """Associate the existing client for passive queries; the native gate verifies ownership."""
    if (not host or not isinstance(live_hwnd, int) or live_hwnd <= 0
            or live_hwnd >= 1 << (8 * ctypes.sizeof(ctypes.c_size_t))
            or not hasattr(dll, "cspm_comp_set_native_trace_live")):
        raise RuntimeError("Native trace live-client association unavailable")
    function = dll.cspm_comp_set_native_trace_live
    function.argtypes, function.restype = [ctypes.c_void_p, ctypes.c_size_t], ctypes.c_int
    if function(host, live_hwnd) != 1:
        raise RuntimeError("Native trace live-client association rejected")


def _window_evidence(value):
    if (any(getattr(value, field) > 1 for field in ("valid", "visible", "iconic", "zoomed"))
            or value.cloaked & ~7 or value.reserved):
        raise RuntimeError("Native window evidence contains incompatible metadata")
    return {name: list(getattr(value, name)) if name.endswith("Rect") else getattr(value, name)
            for name, _ in NativeWindowState._fields_}


def _result_evidence(row):
    """Interpret API result codes without equating a returned slot with scanout."""
    if row.call in (1, 24):
        expected = {0: 1, 0x102: 2, 0xFFFFFFFF: 3, 0x80: 4}.get(row.result, 5)
        if row.waitStateAfter != expected:
            raise RuntimeError("Native wait result and state disagree")
        kind, failed = "Win32 wait", row.result != 0
        meaning = {0: "WAIT_OBJECT_0", 0x102: "WAIT_TIMEOUT", 0xFFFFFFFF: "WAIT_FAILED",
                   0x80: "WAIT_ABANDONED_0", 0xC0: "WAIT_IO_COMPLETION"}.get(row.result, "other wait return")
    else:
        if row.waitStateAfter:
            raise RuntimeError("Non-wait call contains a probed wait state")
        if row.call == 22:
            if row.result > 2:
                raise RuntimeError("Native future completion result is incompatible")
            kind, failed, meaning = "future status", row.result != 0, ("ready", "timeout", "deferred")[row.result]
        elif row.call == 25:
            kind, failed, meaning = "prior visibility", False, "previously visible" if row.result else "previously hidden"
        elif row.call in (7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20):
            kind, failed = "HRESULT", row.result != 0 if row.call == 11 else bool(row.result & 0x80000000)
            meaning = "rejected" if failed else "successful API return"
        else:
            kind, failed, meaning = "Win32 boolean or normalized handle", row.result == 0, "accepted" if row.result else "rejected"
    expected_mutex = (1 if row.result == 0 else 2) if row.call == 11 else (
        (4 if row.result & 0x80000000 else 3) if row.call == 12 else 0)
    if row.keyedMutexState != expected_mutex:
        raise RuntimeError("Native mutex result and state disagree")
    meaningful_error = bool(row.lastErrorApplicable and failed and
                            (row.call not in (1, 24) or row.result == 0xFFFFFFFF))
    return {"resultKind": kind, "resultMeaning": meaning, "apiFailed": failed,
            "terminalFailure": failed and row.call not in (14, 15),
            "lastErrorMeaningful": meaningful_error,
            "lastErrorMeaning": "immediately captured for failing call" if meaningful_error else
                                "captured value has no defined error meaning for this return"}


def _row_evidence(row):
    if (row.version != 1 or row.byteSize != 896 or row.call not in CALL_NAMES
            or row.phase not in PHASE_NAMES or not row.sequence or not row.currentThread
            or not row.hostGeneration or row.expectedHostGeneration != row.hostGeneration):
        raise RuntimeError("Native call row ABI, identity or enum is invalid")
    if (row.waitStateBefore != 0 or row.waitStateAfter not in WAIT_STATES
            or row.keyedMutexState not in MUTEX_STATES or row.fenceState != 0
            or any(getattr(row, field) > 1 for field in ("lastErrorApplicable", "alertable", "beforeMotion"))):
        raise RuntimeError("Native call state contains incompatible metadata")
    if (not row.qpcFrequency or not row.startQpc or row.returnQpc < row.startQpc
            or not math.isfinite(row.beginSeconds) or not math.isfinite(row.returnSeconds)
            or not 0 < row.beginSeconds <= row.returnSeconds):
        raise RuntimeError("Native call timestamps are invalid")
    tolerance = max(1e-7, 2 / row.qpcFrequency)
    if (abs(row.beginSeconds - row.startQpc / row.qpcFrequency) > tolerance
            or abs(row.returnSeconds - row.returnQpc / row.qpcFrequency) > tolerance):
        raise RuntimeError("Native call QPC and seconds disagree")
    if (not row.bufferCount or (row.bufferIndex != 0xFFFFFFFF and row.bufferIndex >= row.bufferCount)
            or row.submittedAfter < row.submittedBefore or row.displayedAfter < row.displayedBefore
            or row.commitAfter < row.commitBefore):
        raise RuntimeError("Native call presentation revisions are reversed or invalid")
    result = {name: _window_evidence(getattr(row, name)) if kind is NativeWindowState else getattr(row, name)
              for name, kind in NativeCallRow._fields_}
    result.update(callName=CALL_NAMES[row.call], phaseName=PHASE_NAMES[row.phase],
        elapsedMs=(row.returnQpc - row.startQpc) * 1000 / row.qpcFrequency,
        returnHex=f"0x{row.result:08X}", waitStateBeforeName=WAIT_STATES[row.waitStateBefore],
        waitStateAfterName=WAIT_STATES[row.waitStateAfter], keyedMutexStateName=MUTEX_STATES[row.keyedMutexState],
        generationsMatch={name: getattr(row, "expected" + name[0].upper() + name[1:]) == getattr(row, name)
                          for name in ("hostGeneration", "sourceGeneration", "targetGeneration")},
        generationObservation="resource generations sampled before the call; import may expect a new generation",
        diagnosticMetadataOverheadMs=row.diagnosticOverheadUs / 1000,
        physicalPresentationProven=False)
    result.update(_result_evidence(row))
    return result


def native_call_evidence(dll, host):
    """Copy and validate one local snapshot; no event probes, retries or HWND calls."""
    if (not host or not hasattr(dll, "cspm_comp_native_call_trace")
            or ctypes.sizeof(NativeWindowState) != 152 or ctypes.sizeof(NativeCallRow) != 896
            or ctypes.sizeof(NativeCallTrace) != 230312):
        raise RuntimeError("Native call observation ABI unavailable")
    value = NativeCallTrace()
    value.version, value.byteSize, value.rowByteSize = 1, 230312, 896
    function = dll.cspm_comp_native_call_trace
    function.argtypes, function.restype = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint], ctypes.c_int
    if function(host, ctypes.byref(value), ctypes.sizeof(value)) != 1:
        raise RuntimeError("Native call observation rejected")
    return _decode_trace(value)


def _decode_trace(value):
    if (value.version != 1 or value.byteSize != 230312 or value.rowByteSize != 896
            or value.enabled != 1 or value.hasFirstFailure > 1 or value.count != min(value.totalRows, 256)
            or value.count > value.totalRows or value.droppedRows != value.totalRows - value.count):
        raise RuntimeError("Native call trace ABI, bounds or measurement is invalid")
    rows, previous_sequence, generation, frequency = [], value.totalRows - value.count, None, None
    for row in value.rows[:value.count]:
        evidence = _row_evidence(row)
        if row.sequence != previous_sequence + 1 or row.sequence > value.totalRows:
            raise RuntimeError("Native call sequence is invalid")
        if generation is not None and row.hostGeneration != generation:
            raise RuntimeError("Native call trace mixes host generations")
        if frequency is not None and row.qpcFrequency != frequency:
            raise RuntimeError("Native call trace mixes QPC frequencies")
        generation, previous_sequence, frequency = row.hostGeneration, row.sequence, row.qpcFrequency
        rows.append(evidence)
    first_failure = _row_evidence(value.firstFailure) if value.hasFirstFailure else None
    if first_failure and (not first_failure["terminalFailure"] or first_failure["sequence"] > value.totalRows
            or (generation is not None and first_failure["hostGeneration"] != generation)
            or (frequency is not None and first_failure["qpcFrequency"] != frequency)):
        raise RuntimeError("Native first failure has stale sequence or host generation")
    failures = [row for row in rows if row["terminalFailure"]]
    if failures and (not first_failure or first_failure["sequence"] > failures[0]["sequence"]):
        raise RuntimeError("Native first terminal failure is absent or overwritten")
    if first_failure:
        retained = next((row for row in rows if row["sequence"] == first_failure["sequence"]), None)
        if retained is not None and retained != first_failure:
            raise RuntimeError("Native pinned failure differs from retained evidence")
    return {"version": 1, "byteSize": 230312, "rowByteSize": 896,
        "enabled": True, "rows": rows, "totalRows": value.totalRows,
        "droppedRows": value.droppedRows, "truncated": bool(value.droppedRows),
        "firstFailure": first_failure,
        "scope": "Passive native API/QPC evidence with local handles; no wait-state probe, activation, retry or physical presentation proof"}


def destroy_native_call_evidence(dll, host):
    """Consume the native destroy disposition before validating its final evidence.

    Accepted destruction may free the pointer. A metadata failure then returns a
    separate error classification and never invites a second native destruction.
    """
    if (not host or not hasattr(dll, "cspm_comp_destroy_with_native_call_trace")
            or ctypes.sizeof(NativeWindowState) != 152 or ctypes.sizeof(NativeCallRow) != 896
            or ctypes.sizeof(NativeCallTrace) != 230312):
        raise RuntimeError("Native destroy trace ABI unavailable")
    value = NativeCallTrace()
    value.version, value.byteSize, value.rowByteSize = 1, 230312, 896
    function = dll.cspm_comp_destroy_with_native_call_trace
    function.argtypes, function.restype = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint], ctypes.c_int
    disposition = function(host, ctypes.byref(value), ctypes.sizeof(value))
    if disposition not in (1, 2):
        raise RuntimeError("Native destroy trace disposition rejected or incompatible")
    result = {"hostDestroyed": disposition == 1, "hostRetained": disposition == 2,
              "evidence": None, "evidenceError": None}
    try:
        result["evidence"] = _decode_trace(value)
    except Exception as error:
        result["evidenceError"] = type(error).__name__
    return result
