"""Native trace ABI and result contracts without loading a DLL or opening windows."""
import ctypes
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


PATH = Path(__file__).resolve().parents[1] / "scripts/diagnostics/native_call_contract.py"
SPEC = importlib.util.spec_from_file_location("native_call_contract_under_test", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_row(sequence=1, **changes):
    row = MODULE.NativeCallRow()
    fields = dict(version=1, byteSize=896, call=2, phase=2, sequence=sequence,
        startQpc=100000000, returnQpc=100010000, qpcFrequency=10000000,
        beginSeconds=10, returnSeconds=10.001, result=1, currentThread=101,
        guiThread=101, workerThread=102, bufferIndex=0xFFFFFFFF, bufferCount=2,
        expectedHostGeneration=21, hostGeneration=21, expectedSourceGeneration=22,
        sourceGeneration=22, expectedTargetGeneration=0, targetGeneration=0,
        beforeMotion=1, diagnosticOverheadUs=1250)
    fields.update(changes)
    for name, value in fields.items():
        setattr(row, name, value)
    for index, name in enumerate(("nativeBefore", "nativeAfter", "liveBefore", "liveAfter")):
        window = getattr(row, name)
        window.window = 999 + index
        window.foreground, window.focus, window.owner = 5000, 5001, 5002
        window.thread, window.process, window.valid, window.visible = 102, 201, 1, 1
        window.windowRect[:], window.clientRect[:], window.workRect[:] = (-32, -32, 1984, 1104), (0, 0, 1984, 1104), (0, 0, 1920, 1040)
        window.dpi = 96
    return row


class TraceFunction:
    def __init__(self, value, returned=1):
        self.value, self.returned, self.calls = value, returned, []

    def __call__(self, host, pointer, capacity):
        request = ctypes.cast(pointer, ctypes.POINTER(MODULE.NativeCallTrace)).contents
        self.calls.append((host, request.version, request.byteSize, request.rowByteSize, capacity))
        ctypes.memmove(pointer, ctypes.byref(self.value), ctypes.sizeof(self.value))
        return self.returned


def make_dll(rows=None, *, total=None, pin=None, trace_changes=None):
    rows = [make_row()] if rows is None else rows
    value = MODULE.NativeCallTrace()
    value.version, value.byteSize, value.rowByteSize, value.enabled = 1, 230312, 896, 1
    value.count, value.totalRows = len(rows), len(rows) if total is None else total
    value.droppedRows = value.totalRows - value.count
    for index, row in enumerate(rows):
        value.rows[index] = row
    if pin is not None:
        value.hasFirstFailure, value.firstFailure = 1, pin
    for name, changed in (trace_changes or {}).items():
        setattr(value, name, changed)
    function = TraceFunction(value)
    def forbidden_operation(*args):
        pytest.fail("Passive native trace read cannot wait, probe events, activate, transfer, or retry")
    return SimpleNamespace(cspm_comp_native_call_trace=function,
        cspm_comp_enable_native_call_trace=forbidden_operation,
        cspm_comp_transfer_source_visibility=forbidden_operation,
        WaitForSingleObjectEx=forbidden_operation), function, value


@pytest.mark.parametrize("kind,size,offsets", [
    (MODULE.NativeWindowState, 152, dict(window=0, foreground=8, focus=16, owner=32,
        thread=40, valid=60, cloaked=76, cloakHRESULT=80, queryErrors=92,
        windowRect=96, clientRect=112, workRect=128, dpi=144, reserved=148)),
    (MODULE.NativeCallRow, 896, dict(version=0, byteSize=4, call=8, phase=12,
        sequence=16, startQpc=24, returnQpc=32, qpcFrequency=40, beginSeconds=48,
        returnSeconds=56, result=64, win32Error=68, lastErrorApplicable=72,
        timeoutMs=76, waitStateBefore=80, waitStateAfter=84, flagsBefore=92,
        currentThread=100, expectedPresentId=112, statisticsHRESULT=132,
        bufferIndex=136, expectedHostGeneration=144, hostGeneration=152,
        expectedSourceGeneration=160, sourceGeneration=168,
        expectedTargetGeneration=176, targetGeneration=184, commitBefore=192,
        commitAfter=200, adapterIdentity=208, deviceIdentity=216, swapchainIdentity=224,
        waitIdentity=232, sourceResourceIdentity=240, targetResourceIdentity=248,
        keyedMutexKey=256, keyedMutexState=264, fenceState=268, beforeMotion=272,
        diagnosticOverheadUs=276, nativeBefore=280, nativeAfter=432,
        liveBefore=584, liveAfter=736, adapterLuid=888)),
    (MODULE.NativeCallTrace, 230312, dict(version=0, byteSize=4, rowByteSize=8,
        count=12, totalRows=16, droppedRows=24, enabled=32, hasFirstFailure=36,
        firstFailure=40, rows=936)),
])
def test_exact_cross_language_abi(kind, size, offsets):
    assert ctypes.sizeof(kind) == size
    assert {name: getattr(kind, name).offset for name in offsets} == offsets


def make_creation(strategy=1, accepted=True):
    value = MODULE.NativeCreationObservation()
    value.version, value.byteSize, value.rowByteSize, value.count = 1, 4816, 392, 3 if accepted else 2
    value.enabled, value.strategy, value.expectedTopmost = 1, strategy, 1
    value.hostGeneration, value.frameRevision, value.qpcFrequency = 21, 22, 10000000
    value.sourceValidated = 1
    value.creationAccepted = value.createResult = value.initializationAccepted = int(accepted)
    value.failureStage, value.cleanupCompleted = (0, 0) if accepted else (2, 1)
    value.createBeginQpc, value.createReturnQpc, value.createWin32Error = 100000000, 100010000, 5
    value.requestedStyle, value.requestedExStyle = 0x80000000, 0x082000A0 | (8 if strategy else 0)
    for index, row in enumerate(value.rows[:value.count]):
        row.phase, row.qpc, row.seconds = index + 1, 99999900 + index * 20000, 9.99999 + index * .002
        row.live = make_row().liveBefore
        row.live.owner, row.live.visible, row.live.exstyle = 0, 1, 0x80008
        if index and accepted:
            row.native = make_row().nativeBefore
            row.native.owner, row.native.visible, row.native.exstyle = 0, 0, value.requestedExStyle
            row.nativeParent, row.nativePrevious, row.nativeNext, row.nativeMonitor = 0, 2001, 2002, 2003
    return value


@pytest.mark.parametrize("kind,size,offsets", [
    (MODULE.NativeCreationRow, 392, dict(phase=0, flags=4, qpc=8, seconds=16,
        native=24, live=176, nativeParent=328, nativeMonitor=352, liveParent=360, liveMonitor=384)),
    (MODULE.NativeCreationObservation, 4816, dict(version=0, count=12, hostGeneration=16,
        frameRevision=24, qpcFrequency=32, enabled=40, strategy=44, requestedExStyle=56,
        sourceValidated=60, failureStage=80, createBeginQpc=88, createResult=104, rows=112)),
])
def test_creation_observation_exact_additive_abi(kind, size, offsets):
    assert ctypes.sizeof(kind) == size
    assert {name: getattr(kind, name).offset for name in offsets} == offsets


class ObservedCreateFunction:
    def __init__(self, creation, trace, host, events):
        self.creation, self.trace, self.host, self.events, self.calls = creation, trace, host, events, []

    def __call__(self, frame, live, left, top, width, height, strategy, creation_pointer, creation_size,
                 trace_pointer, trace_size):
        self.events.append("create")
        self.calls.append((frame, live, (left, top, width, height), strategy, creation_size, trace_size))
        ctypes.memmove(creation_pointer, ctypes.byref(self.creation), ctypes.sizeof(self.creation))
        ctypes.memmove(trace_pointer, ctypes.byref(self.trace), ctypes.sizeof(self.trace))
        return self.host


def observed_dll(creation=None, host=999):
    events = []
    _, _, trace = make_dll([])
    function = ObservedCreateFunction(make_creation() if creation is None else creation, trace, host, events)
    def error(pointer, buffer, capacity):
        events.append("first-error")
        assert pointer is None
        ctypes.memmove(buffer, b"original hidden creation failure\0", 33)
        return 32
    # Attributes must be assignable for ctypes-like error function configuration.
    dll = SimpleNamespace(cspm_comp_create_from_frame_observed=function, cspm_comp_error=error)
    return dll, function, events


@pytest.mark.parametrize("strategy", [False, True])
def test_observed_create_both_paths_use_same_owned_source_input_and_bounded_outputs(strategy):
    dll, function, events = observed_dll(make_creation(int(strategy)))
    result = MODULE.create_observed_native_host(dll, 444, 555, (-1920, 0, 1920, 1080), strategy)
    assert result["host"] == 999 and result["nativeError"] is None and result["evidenceError"] is None
    assert function.calls == [(444, 555, (-1920, 0, 1920, 1080), int(strategy), 4816, 230312)]
    assert events == ["create"]
    assert result["creation"]["rows"][1]["nativePrevious"] == 2001
    assert result["creation"]["rows"][1]["native"]["visible"] == 0
    assert result["creation"]["physicalPresentationProven"] is False


def test_null_creation_captures_first_native_error_and_preserves_cleanup_before_decoding(monkeypatch):
    dll, function, events = observed_dll(make_creation(accepted=False), host=None)
    original = MODULE._decode_creation
    def decode(value):
        events.append("decode")
        return original(value)
    monkeypatch.setattr(MODULE, "_decode_creation", decode)
    result = MODULE.create_observed_native_host(dll, 444, 555, (0, 0, 1920, 1080), True)
    assert result["host"] is None and result["nativeError"] == "original hidden creation failure"
    assert events == ["create", "first-error", "decode"]
    assert result["creation"]["cleanupCompleted"] == 1 and result["evidenceError"] is None


def test_successful_creation_with_rejected_metadata_retains_host_for_exactly_once_caller_cleanup():
    creation = make_creation()
    creation.byteSize = 4815
    dll, function, events = observed_dll(creation)
    result = MODULE.create_observed_native_host(dll, 444, 555, (0, 0, 1920, 1080), True)
    assert result["host"] == 999 and result["nativeError"] is None
    assert result["creation"] is None and result["evidence"] is not None
    assert "creation: RuntimeError" in result["evidenceError"] and events == ["create"]


@pytest.mark.parametrize("field,changed", [("version", 2), ("count", 13), ("count", 0),
    ("enabled", 0), ("strategy", 2), ("hostGeneration", 0), ("qpcFrequency", 0),
    ("createReturnQpc", 99999999), ("createResult", 0), ("sourceValidated", 0),
    ("reserved", 1), ("frameRevision", 0), ("failureStage", 4)])
def test_creation_metadata_rejects_unmeasured_or_contradictory_evidence(field, changed):
    creation = make_creation()
    setattr(creation, field, changed)
    with pytest.raises(RuntimeError):
        MODULE._decode_creation(creation)


def test_complete_local_raw_evidence_has_no_physical_presentation_claim_or_error_inference():
    dll, function, _ = make_dll([make_row(lastErrorApplicable=1, win32Error=5,
        adapterIdentity=100, deviceIdentity=101, swapchainIdentity=102, waitIdentity=103,
        expectedPresentId=9, submittedBefore=8, submittedAfter=8,
        displayedBefore=7, displayedAfter=7, commitBefore=2, commitAfter=2)])
    result = MODULE.native_call_evidence(dll, 999)
    row = result["rows"][0]
    assert function.calls == [(999, 1, 230312, 896, 230312)]
    assert function.argtypes == [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    assert function.restype is ctypes.c_int
    assert row["win32Error"] == 5 and row["lastErrorMeaningful"] is False
    assert row["physicalPresentationProven"] is False and row["apiFailed"] is False
    assert row["elapsedMs"] == 1 and row["diagnosticMetadataOverheadMs"] == 1.25
    assert row["nativeBefore"]["foreground"] == 5000 and row["liveAfter"]["focus"] == 5001
    assert row["nativeBefore"]["windowRect"] == [-32, -32, 1984, 1104]
    assert row["waitIdentity"] == 103 and row["expectedPresentId"] == 9
    assert "no wait-state probe" in result["scope"]


@pytest.mark.parametrize("result,state,meaning,meaningful", [
    (0, 1, "WAIT_OBJECT_0", False), (0x102, 2, "WAIT_TIMEOUT", False),
    (0xFFFFFFFF, 3, "WAIT_FAILED", True), (0x80, 4, "WAIT_ABANDONED_0", False),
    (0xC0, 5, "WAIT_IO_COMPLETION", False), (17, 5, "other wait return", False),
])
@pytest.mark.parametrize("call", [1, 24])
def test_raw_wait_outcomes_and_immediate_error_applicability_are_preserved(call, result, state, meaning, meaningful):
    row = make_row(call=call, result=result, waitStateAfter=state, timeoutMs=100,
        lastErrorApplicable=1, win32Error=5, waitIdentity=700)
    dll, _, _ = make_dll([row], pin=row if result else None)
    evidence = MODULE.native_call_evidence(dll, 999)["rows"][0]
    assert evidence["result"] == result and evidence["resultMeaning"] == meaning
    assert evidence["lastErrorMeaningful"] is meaningful and evidence["win32Error"] == 5
    assert evidence["timeoutMs"] == 100 and evidence["waitStateBefore"] == 0
    assert evidence["physicalPresentationProven"] is False


@pytest.mark.parametrize("call,result,mutex,failed", [
    (7, 0, 0, False), (8, 0x80004005, 0, True), (11, 0, 1, False),
    (11, 0x102, 2, True), (12, 0, 3, False), (12, 0x80004005, 4, True),
    (13, 0x087A0001, 0, False), (13, 0x887A0005, 0, True),
    (14, 0x80004005, 0, True), (15, 0x887A000B, 0, True),
    (16, 0x80070057, 0, True), (17, 0, 0, False), (18, 0, 0, False),
    (19, 0x8007000E, 0, True), (20, 0, 0, False), (22, 0, 0, False),
    (22, 1, 0, True), (22, 2, 0, True), (25, 0, 0, False), (25, 1, 0, False),
])
def test_hresult_mutex_future_and_showwindow_have_distinct_return_contracts(call, result, mutex, failed):
    row = make_row(call=call, result=result, keyedMutexState=mutex, win32Error=5)
    terminal = failed and call not in (14, 15)
    dll, _, _ = make_dll([row], pin=row if terminal else None)
    evidence = MODULE.native_call_evidence(dll, 999)["rows"][0]
    assert evidence["apiFailed"] is failed and evidence["terminalFailure"] is terminal
    assert evidence["lastErrorMeaningful"] is False


@pytest.mark.parametrize("call", [2, 3, 4, 5, 6, 9, 10, 21, 23, 26, 27])
def test_failed_bool_or_normalized_pointer_preserves_win32_error_and_first_failure(call):
    row = make_row(call=call, result=0, lastErrorApplicable=1, win32Error=1400)
    dll, _, _ = make_dll([row], pin=row)
    evidence = MODULE.native_call_evidence(dll, 999)
    assert evidence["firstFailure"]["win32Error"] == 1400
    assert evidence["firstFailure"]["lastErrorMeaningful"] is True


@pytest.mark.parametrize("field,value", [("version", 2), ("byteSize", 895),
    ("call", 0), ("call", 34), ("phase", 0), ("phase", 6), ("sequence", 0),
    ("currentThread", 0), ("hostGeneration", 0), ("expectedHostGeneration", 20),
    ("qpcFrequency", 0), ("startQpc", 0), ("returnQpc", 99999999),
    ("beginSeconds", float("nan")), ("returnSeconds", float("inf")),
    ("beginSeconds", -1), ("returnSeconds", 9), ("returnSeconds", 10.002),
    ("bufferCount", 0), ("bufferIndex", 2), ("waitStateBefore", 1),
    ("waitStateAfter", 6), ("lastErrorApplicable", 2), ("alertable", 2),
    ("beforeMotion", 2), ("fenceState", 1), ("keyedMutexState", 5)])
def test_incompatible_or_unmeasured_row_metadata_rejects(field, value):
    dll, _, _ = make_dll([make_row(**{field: value})])
    with pytest.raises(RuntimeError):
        MODULE.native_call_evidence(dll, 999)


@pytest.mark.parametrize("before,after", [("submittedBefore", "submittedAfter"),
    ("displayedBefore", "displayedAfter"), ("commitBefore", "commitAfter")])
def test_reversed_presentation_or_commit_revisions_reject(before, after):
    dll, _, _ = make_dll([make_row(**{before: 3, after: 2})])
    with pytest.raises(RuntimeError, match="revisions"):
        MODULE.native_call_evidence(dll, 999)


@pytest.mark.parametrize("field,value", [("version", 2), ("byteSize", 230311),
    ("rowByteSize", 895), ("enabled", 0), ("enabled", 2), ("hasFirstFailure", 2),
    ("count", 257), ("count", 0), ("totalRows", 0), ("droppedRows", 1)])
def test_invalid_trace_header_or_bounds_rejects_before_rows_are_read(field, value):
    dll, _, _ = make_dll(trace_changes={field: value})
    with pytest.raises(RuntimeError):
        MODULE.native_call_evidence(dll, 999)


def test_fresh_enabled_empty_trace_is_measured_as_zero_calls_without_fabricated_identity():
    dll, _, _ = make_dll([])
    result = MODULE.native_call_evidence(dll, 999)
    assert result["rows"] == [] and result["firstFailure"] is None and result["totalRows"] == 0


def test_completion_sequences_allow_overlapping_and_nonmonotonic_start_times():
    first = make_row(1, startQpc=100005000, returnQpc=100009000, beginSeconds=10.0005, returnSeconds=10.0009)
    second = make_row(2)
    dll, _, _ = make_dll([first, second])
    evidence = MODULE.native_call_evidence(dll, 999)["rows"]
    assert [row["sequence"] for row in evidence] == [1, 2]
    assert evidence[0]["startQpc"] > evidence[1]["startQpc"]


@pytest.mark.parametrize("changes", [dict(sequence=1), dict(sequence=3),
    dict(hostGeneration=30, expectedHostGeneration=30),
    dict(qpcFrequency=20000000, startQpc=200000000, returnQpc=200020000)])
def test_mixed_generations_clocks_missing_or_duplicate_completion_sequences_reject(changes):
    metadata = dict(sequence=2)
    metadata.update(changes)
    dll, _, _ = make_dll([make_row(1), make_row(**metadata)])
    with pytest.raises(RuntimeError):
        MODULE.native_call_evidence(dll, 999)


def test_bounded_ring_retains_latest_rows_and_pins_terminal_failure_after_it_is_dropped():
    failure = make_row(1, call=1, result=0x102, waitStateAfter=2, timeoutMs=100)
    dll, _, _ = make_dll([make_row(index) for index in range(45, 301)], total=300, pin=failure)
    result = MODULE.native_call_evidence(dll, 999)
    assert result["droppedRows"] == 44 and result["truncated"] is True
    assert result["rows"][0]["sequence"] == 45 and result["rows"][-1]["sequence"] == 300
    assert result["firstFailure"]["sequence"] == 1 and result["firstFailure"]["resultMeaning"] == "WAIT_TIMEOUT"


@pytest.mark.parametrize("mode", ["missing", "successful", "later", "mismatch", "stale"])
def test_first_terminal_failure_cannot_be_missing_replaced_or_claimed_by_success(mode):
    failed = make_row(1, result=0, lastErrorApplicable=1, win32Error=5)
    second = make_row(2)
    pin = {"missing": None, "successful": second, "later": make_row(2, result=0),
        "mismatch": make_row(1, result=0, win32Error=1400),
        "stale": make_row(1, result=0, hostGeneration=30, expectedHostGeneration=30)}[mode]
    dll, _, _ = make_dll([failed, second], pin=pin)
    with pytest.raises(RuntimeError):
        MODULE.native_call_evidence(dll, 999)


def test_expected_new_import_generation_and_pre_call_actual_generation_are_preserved():
    row = make_row(call=17, result=0, expectedTargetGeneration=44, targetGeneration=30)
    dll, _, _ = make_dll([row])
    evidence = MODULE.native_call_evidence(dll, 999)["rows"][0]
    assert evidence["expectedTargetGeneration"] == 44 and evidence["targetGeneration"] == 30
    assert evidence["generationsMatch"]["targetGeneration"] is False and evidence["apiFailed"] is False
    assert "before the call" in evidence["generationObservation"]


@pytest.mark.parametrize("cloak", range(8))
def test_all_documented_cloaking_mask_combinations_remain_raw_evidence(cloak):
    row = make_row()
    row.nativeAfter.cloaked = cloak
    dll, _, _ = make_dll([row])
    assert MODULE.native_call_evidence(dll, 999)["rows"][0]["nativeAfter"]["cloaked"] == cloak


@pytest.mark.parametrize("field,value", [("valid", 2), ("visible", 2), ("iconic", 2),
    ("zoomed", 2), ("cloaked", 8), ("reserved", 1)])
def test_incompatible_window_state_rejects_without_turning_failed_queries_into_success(field, value):
    row = make_row()
    setattr(row.liveBefore, field, value)
    dll, _, _ = make_dll([row])
    with pytest.raises(RuntimeError, match="window"):
        MODULE.native_call_evidence(dll, 999)


def test_query_errors_and_unavailable_original_client_state_remain_measured_failures():
    row = make_row()
    row.liveBefore.valid, row.liveBefore.queryErrors, row.liveBefore.cloakHRESULT = 0, 7, 0x80004005
    dll, _, _ = make_dll([row])
    window = MODULE.native_call_evidence(dll, 999)["rows"][0]["liveBefore"]
    assert window["valid"] == 0 and window["queryErrors"] == 7 and window["cloakHRESULT"] == 0x80004005


@pytest.mark.parametrize("changes", [dict(call=1, result=0, waitStateAfter=2),
    dict(call=2, waitStateAfter=1), dict(call=11, result=0, keyedMutexState=2),
    dict(call=12, result=0x80004005, keyedMutexState=3), dict(call=22, result=3)])
def test_inconsistent_result_and_wait_or_mutex_state_rejects(changes):
    dll, _, _ = make_dll([make_row(**changes)])
    with pytest.raises(RuntimeError):
        MODULE.native_call_evidence(dll, 999)


@pytest.mark.parametrize("returned", [0, 1, 2])
def test_explicit_enable_is_single_call_and_requires_exact_native_acceptance(returned):
    calls = []
    class Enable:
        def __call__(self, host):
            calls.append(host)
            return returned
    function = Enable()
    dll = SimpleNamespace(cspm_comp_enable_native_call_trace=function)
    if returned == 1:
        MODULE.enable_native_call_trace(dll, 999)
    else:
        with pytest.raises(RuntimeError):
            MODULE.enable_native_call_trace(dll, 999)
    assert calls == [999]
    assert function.argtypes == [ctypes.c_void_p] and function.restype is ctypes.c_int


@pytest.mark.parametrize("host", [None, 0])
def test_null_owner_rejects_before_any_native_read(host):
    dll, function, _ = make_dll()
    with pytest.raises(RuntimeError, match="unavailable"):
        MODULE.native_call_evidence(dll, host)
    assert function.calls == []


def test_previous_bridge_without_export_fails_explicitly_without_retry():
    with pytest.raises(RuntimeError, match="unavailable"):
        MODULE.native_call_evidence(SimpleNamespace(), 999)
    with pytest.raises(RuntimeError, match="unavailable"):
        MODULE.enable_native_call_trace(SimpleNamespace(), 999)


def test_rejected_native_snapshot_is_read_once_without_overwriting_pinned_native_failure():
    dll, function, _ = make_dll()
    function.returned = 0
    with pytest.raises(RuntimeError, match="rejected"):
        MODULE.native_call_evidence(dll, 999)
    assert len(function.calls) == 1


@pytest.mark.parametrize("returned", [0, 1, 2])
def test_live_client_association_is_single_checked_call_without_native_state_change(returned):
    calls = []
    class Association:
        def __call__(self, host, live):
            calls.append((host, live))
            return returned
    function = Association()
    dll = SimpleNamespace(cspm_comp_set_native_trace_live=function)
    if returned == 1:
        MODULE.set_native_trace_live(dll, 999, 5000)
    else:
        with pytest.raises(RuntimeError, match="rejected"):
            MODULE.set_native_trace_live(dll, 999, 5000)
    assert calls == [(999, 5000)]
    assert function.argtypes == [ctypes.c_void_p, ctypes.c_size_t] and function.restype is ctypes.c_int


@pytest.mark.parametrize("host,live", [(None, 5000), (999, 0), (999, -1), (999, None),
    (999, 1 << (8 * ctypes.sizeof(ctypes.c_size_t)))])
def test_invalid_live_client_association_rejects_before_any_api_call(host, live):
    def forbidden(*args):
        pytest.fail("Invalid handle must reject before native call")
    with pytest.raises(RuntimeError, match="unavailable"):
        MODULE.set_native_trace_live(SimpleNamespace(cspm_comp_set_native_trace_live=forbidden), host, live)


def test_live_client_association_missing_export_is_explicit_unavailable():
    with pytest.raises(RuntimeError, match="unavailable"):
        MODULE.set_native_trace_live(SimpleNamespace(), 999, 5000)


@pytest.mark.parametrize("disposition", [1, 2])
def test_destroy_final_trace_records_disposition_without_native_retry(disposition):
    row = make_row(call=24, result=0 if disposition == 1 else 0x102,
        waitStateAfter=1 if disposition == 1 else 2, timeoutMs=3000, phase=5)
    _, function, _ = make_dll([row], pin=row if disposition == 2 else None)
    function.returned = disposition
    result = MODULE.destroy_native_call_evidence(SimpleNamespace(cspm_comp_destroy_with_native_call_trace=function), 999)
    assert result["hostDestroyed"] is (disposition == 1)
    assert result["hostRetained"] is (disposition == 2)
    assert result["evidenceError"] is None
    assert result["evidence"]["rows"][0]["timeoutMs"] == 3000
    assert function.calls == [(999, 1, 230312, 896, 230312)]


@pytest.mark.parametrize("disposition", [1, 2])
def test_accepted_destroy_never_raises_when_final_trace_metadata_is_invalid(disposition):
    _, function, _ = make_dll(trace_changes={"version": 2})
    function.returned = disposition
    result = MODULE.destroy_native_call_evidence(SimpleNamespace(cspm_comp_destroy_with_native_call_trace=function), 999)
    assert result["hostDestroyed"] is (disposition == 1)
    assert result["hostRetained"] is (disposition == 2)
    assert result["evidence"] is None and result["evidenceError"] == "RuntimeError"
    assert len(function.calls) == 1


def test_destroy_rejected_args_or_abi_leave_the_pointer_disposition_unconsumed():
    calls = []
    class Rejected:
        def __call__(self, host, pointer, capacity):
            value = ctypes.cast(pointer, ctypes.POINTER(MODULE.NativeCallTrace)).contents
            calls.append((host, value.version, value.byteSize, value.rowByteSize, capacity))
            return 0
    with pytest.raises(RuntimeError, match="rejected"):
        MODULE.destroy_native_call_evidence(SimpleNamespace(cspm_comp_destroy_with_native_call_trace=Rejected()), 999)
    assert calls == [(999, 1, 230312, 896, 230312)]


@pytest.mark.parametrize("host", [None, 0])
def test_destroy_null_owner_rejects_before_the_native_gate(host):
    def forbidden(*args):
        pytest.fail("Null owner cannot be passed to native destroy")
    with pytest.raises(RuntimeError, match="unavailable"):
        MODULE.destroy_native_call_evidence(SimpleNamespace(cspm_comp_destroy_with_native_call_trace=forbidden), host)


def test_destroy_old_bridge_missing_export_is_explicit_unavailable():
    with pytest.raises(RuntimeError, match="unavailable"):
        MODULE.destroy_native_call_evidence(SimpleNamespace(), 999)
