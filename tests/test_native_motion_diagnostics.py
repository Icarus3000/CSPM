"""Measurements must not change engine policy or consume presentation slots."""
import ctypes
from types import SimpleNamespace
import struct
import pytest

from backend import native_candidate, native_motion
from backend.native_motion_diagnostics import MotionDiagnostics, TRACE_BYTES, ROW_BYTES, ROWS_OFFSET


def test_measurement_flag_is_ignored_without_disposable_candidate(monkeypatch):
    monkeypatch.setenv("CSPM_MOTION_DIAGNOSTICS", "1")
    monkeypatch.setattr(native_candidate, "_profile", None)
    monkeypatch.setattr(native_motion, "read_mode", lambda: "native")
    monkeypatch.setattr(native_motion, "system_reduced_motion", lambda: False)
    runtime = native_motion.NativeMotion(bridge_factory=lambda _: SimpleNamespace(dll=object()))
    assert runtime.engine == "native" and runtime.available
    assert runtime._diagnostics is None


def test_existing_abi_snapshot_preserves_slot_results_and_overhead():
    called = []
    def enable(_):
        called.append("enable")
        return 1
    def set_live(*_):
        called.append("set_live")
        return 1
    def elapsed(_):
        return 250.0
    def observation(_, target, capacity):
        assert capacity == 208
        data = (ctypes.c_char * capacity).from_address(ctypes.addressof(target._obj))
        struct.pack_into("<16d", data, 24, *range(16))
        return 1
    def trace(_, target, capacity):
        assert capacity == TRACE_BYTES
        data = (ctypes.c_char * capacity).from_address(ctypes.addressof(target._obj))
        struct.pack_into("<I", data, 12, 2)
        for index, result in enumerate((0, 258)):
            start = ROWS_OFFSET + index*ROW_BYTES
            struct.pack_into("<II", data, start+8, 1, 3)
            struct.pack_into("<dd", data, start+48, 5.0, 5.025)
            struct.pack_into("<4I", data, start+64, result, 0, 1, 100)
            struct.pack_into("<I", data, start+276, 75)
        return 1
    dll = SimpleNamespace(cspm_comp_enable_native_call_trace=enable,
        cspm_comp_set_native_trace_live=set_live, cspm_comp_elapsed_ms=elapsed,
        cspm_comp_observation=observation, cspm_comp_native_call_trace=trace)
    window = SimpleNamespace(devicePixelRatio=lambda: 2.0, winId=lambda: 123)
    transaction = dict(sequence=1, direction="restore", source=[0,0,20,20], target=[0,0,10,10],
        window=window, host=42, started=True)
    recorder = MotionDiagnostics(dll)
    recorder.begin(transaction)
    recorder.enable_native_trace(transaction)
    recorder.snapshot(transaction, "safe-rejection")
    report = transaction["diagnostic"]
    assert report["nativeObservation"]["targetImportBegin"] == 8
    assert report["nativeObservation"]["targetReady"] == 9
    assert [row["result"] for row in report["nativeCalls"]] == [0, 258]
    assert all(row["timeoutMs"] == 100 for row in report["nativeCalls"])
    assert report["nativeMetadataOverheadMs"] == .15
    assert report["timingGatesChanged"] is False
    assert called == ["enable", "set_live"]
    transaction["cancelled"] = True
    dll.cspm_comp_elapsed_ms = lambda _: pytest.fail("A cancelled transaction queried a retired host")
    recorder.mark(transaction, "after_synchronous_cancellation")
    assert "nativeElapsedMs" not in report["events"][-1]
