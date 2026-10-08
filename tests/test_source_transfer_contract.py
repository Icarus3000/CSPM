"""Passive owned-transfer metadata contracts; no Qt, HWND or native DLL load."""
import ctypes
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


path = Path(__file__).resolve().parents[1] / "scripts/diagnostics/source_transfer_contract.py"
spec = importlib.util.spec_from_file_location("source_transfer_contract_under_test", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MetadataFunction:
    def __init__(self, kind, fields, rows=None, returned=1):
        self.kind, self.fields, self.rows, self.returned = kind, fields, rows, returned
        self.calls = []

    def __call__(self, host, pointer, capacity):
        value = ctypes.cast(pointer, ctypes.POINTER(self.kind)).contents
        self.calls.append((host, value.version, value.byteSize, capacity,
            getattr(value, "rowByteSize", None)))
        for field, item in self.fields.items():
            setattr(value, field, item)
        for index, fields in enumerate(self.rows or []):
            for field, item in fields.items():
                setattr(value.rows[index], field, item)
        return self.returned


def synthetic_dll(*, stage=9, observation_changes=None, trace_changes=None, row_changes=None):
    observation = dict(version=1, byteSize=192, hostGeneration=21, sequence=3,
        stage=stage, accepted=int(stage == 9), win32Error=0 if stage == 9 else 5,
        expectedTopmost=1, currentThreadId=101, currentProcessId=201,
        liveThreadId=101, liveProcessId=201, nativeThreadId=102, nativeProcessId=201,
        sameParent=1, sameProcess=1, liveThreadOwned=1, nativeThreadOwned=1,
        liveForegroundEntry=1, liveForegroundExit=0, liveOwnerRelation=0,
        nativeOwnerRelation=0, liveStyleEntry=0x80008, nativeStyleEntry=0x80008,
        liveStyleExit=0x80008, nativeStyleExit=0x80008,
        liveVisibleEntry=1, nativeVisibleEntry=0, liveVisibleExit=0,
        nativeVisibleExit=1, beginAccepted=1, liveDeferAccepted=1,
        nativeDeferAccepted=1, endAccepted=int(stage == 9),
        entrySeconds=10.0, beginBatchSeconds=10.01, endBatchBeginSeconds=10.02,
        endBatchReturnSeconds=10.03, exitSeconds=10.04, traceEnabled=1, policySampled=1)
    observation.update(observation_changes or {})
    rows = [dict(sequence=index + 1, timeSeconds=10.02 + index * .001,
        message=0x46 if index == 0 else 0x47, phase=1 if index == 0 else 2,
        insertAfterBandBefore=2, insertAfterBandAfter=2,
        flagsBefore=0x53, flagsAfter=0x53, styleBefore=0x80008,
        styleAfter=0x80008, currentThreadId=102, expectedTopmost=1,
        visibleAfter=1, reserved=0) for index in range(2)]
    if row_changes:
        for index, changes in row_changes.items():
            rows[index].update(changes)
    trace = dict(version=1, byteSize=1048, rowByteSize=64, count=2, totalRows=2)
    trace.update(trace_changes or {})
    observation_function = MetadataFunction(module.SourceTransferObservation, observation)
    trace_function = MetadataFunction(module.SourceWindowposTrace, trace, rows)
    def forbidden_state_operation(*args):
        pytest.fail("Reading passive metadata cannot retry a transfer or change native state")
    dll = SimpleNamespace(cspm_comp_source_transfer_observation=observation_function,
        cspm_comp_source_windowpos_trace=trace_function,
        cspm_comp_transfer_source_visibility=forbidden_state_operation,
        cspm_comp_raise_source_visibility=forbidden_state_operation,
        cspm_comp_enable_source_transfer_trace=forbidden_state_operation)
    return dll, observation_function, trace_function, observation, rows


@pytest.mark.parametrize("kind,size,offsets", [
    (module.SourceTransferObservation, 192, dict(version=0, byteSize=4,
        hostGeneration=8, sequence=16, stage=24, accepted=28, win32Error=32,
        expectedTopmost=36, currentThreadId=40, currentProcessId=44,
        liveThreadId=48, liveProcessId=52, nativeThreadId=56, nativeProcessId=60,
        sameParent=64, sameProcess=68, liveThreadOwned=72, nativeThreadOwned=76,
        liveForegroundEntry=80, liveForegroundExit=84, liveOwnerRelation=88,
        nativeOwnerRelation=92, liveStyleEntry=96, nativeStyleEntry=100,
        liveStyleExit=104, nativeStyleExit=108, liveVisibleEntry=112,
        nativeVisibleEntry=116, liveVisibleExit=120, nativeVisibleExit=124,
        beginAccepted=128, liveDeferAccepted=132, nativeDeferAccepted=136,
        endAccepted=140, entrySeconds=144, beginBatchSeconds=152,
        endBatchBeginSeconds=160, endBatchReturnSeconds=168, exitSeconds=176,
        traceEnabled=184, policySampled=188)),
    (module.SourceWindowposRow, 64, dict(sequence=0, timeSeconds=8, message=16,
        phase=20, insertAfterBandBefore=24, insertAfterBandAfter=28,
        flagsBefore=32, flagsAfter=36, styleBefore=40, styleAfter=44,
        currentThreadId=48, expectedTopmost=52, visibleAfter=56, reserved=60)),
    (module.SourceWindowposTrace, 1048, dict(version=0, byteSize=4,
        rowByteSize=8, count=12, totalRows=16, rows=24)),
])
def test_exact_cross_language_abi_layout(kind, size, offsets):
    assert ctypes.sizeof(kind) == size
    assert {name: getattr(kind, name).offset for name, _ in kind._fields_} == offsets


def test_actual_windowpos_flags_styles_and_thread_fields_survive_without_policy_rewriting():
    dll, observed, trace, expected, rows = synthetic_dll(row_changes={0: dict(
        insertAfterBandBefore=1, insertAfterBandAfter=2, flagsBefore=0x93,
        flagsAfter=0x53, styleBefore=0x80000, styleAfter=0x80008)})
    result = module.source_transfer_evidence(dll, 999)
    assert result["observation"] == expected and result["messages"] == rows
    assert result["totalRows"] == 2 and result["truncated"] is False
    assert "no activation/retry or pixel proof" in result["scope"]
    assert observed.calls == [(999, 1, 192, 192, None)]
    assert trace.calls == [(999, 1, 1048, 1048, 64)]
    for function in (observed, trace):
        assert function.argtypes == [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        assert function.restype is ctypes.c_int


@pytest.mark.parametrize("stage", [2, 3, 4, 5, 6, 7, 8, 10, 11])
def test_rejected_transfer_safety_findings_and_win32_error_remain_failed_measured_evidence(stage):
    dll, _, _, expected, _ = synthetic_dll(stage=stage, observation_changes=dict(
        sameProcess=0, sameParent=0, liveThreadOwned=0, nativeThreadOwned=0,
        endAccepted=0, beginBatchSeconds=0, endBatchBeginSeconds=0, endBatchReturnSeconds=0))
    result = module.source_transfer_evidence(dll, 999)
    assert result["observation"] == expected
    assert result["observation"]["accepted"] == 0
    assert result["observation"]["win32Error"] == 5


@pytest.mark.parametrize("field,value", [("version", 2), ("byteSize", 191),
    ("hostGeneration", 0), ("sequence", 0), ("traceEnabled", 0),
    ("traceEnabled", 2), ("stage", 1), ("stage", 12), ("accepted", 0),
    ("accepted", 2), ("entrySeconds", 0), ("entrySeconds", float("nan")),
    ("exitSeconds", float("inf")), ("exitSeconds", 9.0)])
def test_incompatible_unmeasured_or_nonterminal_transfer_observation_rejects(field, value):
    dll, _, _, _, _ = synthetic_dll(observation_changes={field: value})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


@pytest.mark.parametrize("field,value", [("version", 2), ("byteSize", 1047),
    ("rowByteSize", 63), ("count", 17), ("count", 3)])
def test_incompatible_or_out_of_bounds_trace_rejects_without_reading_excess_rows(field, value):
    dll, _, _, _, _ = synthetic_dll(trace_changes={field: value})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


@pytest.mark.parametrize("field,value", [("sequence", 0), ("timeSeconds", 9.99),
    ("timeSeconds", float("nan")), ("timeSeconds", float("inf")),
    ("message", 0x48), ("insertAfterBandBefore", 8), ("insertAfterBandAfter", 8),
    ("phase", 0), ("phase", 12), ("expectedTopmost", 2), ("visibleAfter", 2),
    ("reserved", 1)])
def test_invalid_actual_windowpos_row_rejects(field, value):
    dll, _, _, _, _ = synthetic_dll(row_changes={0: {field: value}})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


@pytest.mark.parametrize("changes", [dict(sequence=1), dict(timeSeconds=10.019)])
def test_windowpos_order_must_follow_both_sequence_and_observed_time(changes):
    dll, _, _, _, _ = synthetic_dll(row_changes={1: changes})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


def test_windowpos_sequence_cannot_exceed_the_reported_total_message_count():
    dll, _, _, _, _ = synthetic_dll(row_changes={1: dict(sequence=3)})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


@pytest.mark.parametrize("field", ["expectedTopmost", "sameParent", "sameProcess",
    "liveThreadOwned", "nativeThreadOwned", "liveForegroundEntry", "liveForegroundExit",
    "liveVisibleEntry", "nativeVisibleEntry", "liveVisibleExit", "nativeVisibleExit",
    "beginAccepted", "liveDeferAccepted", "nativeDeferAccepted", "endAccepted", "policySampled"])
def test_unknown_observation_boolean_values_are_not_interpreted_as_safety_evidence(field):
    dll, _, _, _, _ = synthetic_dll(observation_changes={field: 2})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


@pytest.mark.parametrize("field", ["liveOwnerRelation", "nativeOwnerRelation"])
def test_unknown_owner_relationship_code_rejects_without_revealing_a_handle(field):
    dll, _, _, _, _ = synthetic_dll(observation_changes={field: 6})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


def test_late_actual_windowpos_message_keeps_its_after_api_timestamp():
    dll, _, _, expected, rows = synthetic_dll(row_changes={1: dict(timeSeconds=10.9)})
    result = module.source_transfer_evidence(dll, 999)
    assert result["messages"][1] == rows[1]
    assert result["messages"][1]["timeSeconds"] > expected["exitSeconds"]
    assert result["observation"]["exitSeconds"] == 10.04


def test_bounded_trace_reports_truncation_without_discarding_retained_actual_rows():
    dll, _, _, _, rows = synthetic_dll(trace_changes=dict(totalRows=19))
    result = module.source_transfer_evidence(dll, 999)
    assert result["totalRows"] == 19 and result["truncated"] is True
    assert result["messages"] == rows


@pytest.mark.parametrize("missing", ["cspm_comp_source_transfer_observation", "cspm_comp_source_windowpos_trace"])
def test_previous_dll_missing_api_fails_explicitly_without_retry(missing):
    dll, observation, trace, _, _ = synthetic_dll()
    delattr(dll, missing)
    with pytest.raises(RuntimeError, match="unavailable"):
        module.source_transfer_evidence(dll, 999)
    assert len(observation.calls) <= 1 and len(trace.calls) == 0


def test_null_owner_rejects_before_any_api_call():
    dll, observation, trace, _, _ = synthetic_dll()
    with pytest.raises(RuntimeError, match="unavailable"):
        module.source_transfer_evidence(dll, None)
    assert observation.calls == trace.calls == []


@pytest.mark.parametrize("failed", ["observation", "trace"])
def test_rejected_metadata_api_is_called_once_without_transfer_or_activation_retry(failed):
    dll, observation, trace, _, _ = synthetic_dll()
    (observation if failed == "observation" else trace).returned = 0
    with pytest.raises(RuntimeError, match="rejected"):
        module.source_transfer_evidence(dll, 999)
    assert len(observation.calls) == 1
    assert len(trace.calls) == int(failed == "trace")


@pytest.mark.parametrize("field,value", [("beginBatchSeconds", float("nan")),
    ("endBatchBeginSeconds", float("inf")), ("endBatchReturnSeconds", -1),
    ("beginBatchSeconds", 9.99), ("endBatchReturnSeconds", 10.05),
    ("endBatchBeginSeconds", 10.005)])
def test_measured_batch_timestamps_are_finite_ordered_and_inside_the_transfer_interval(field, value):
    dll, _, _, _, _ = synthetic_dll(observation_changes={field: value})
    with pytest.raises(RuntimeError):
        module.source_transfer_evidence(dll, 999)


@pytest.mark.parametrize("returned", [0, 1])
def test_explicit_enable_calls_the_native_gate_once_without_retry(returned):
    calls = []
    class EnableFunction:
        def __call__(self, host):
            calls.append(host)
            return returned
    function = EnableFunction()
    dll = SimpleNamespace(cspm_comp_enable_source_transfer_trace=function)
    if returned:
        module.enable_source_transfer_trace(dll, 999)
    else:
        with pytest.raises(RuntimeError, match="precede"):
            module.enable_source_transfer_trace(dll, 999)
    assert calls == [999]
    assert function.argtypes == [ctypes.c_void_p] and function.restype is ctypes.c_int


def test_enable_missing_api_is_rejected_before_source_preparation():
    with pytest.raises(RuntimeError, match="unavailable"):
        module.enable_source_transfer_trace(SimpleNamespace(), 999)
