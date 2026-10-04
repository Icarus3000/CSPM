"""Additive bridge telemetry and bounded, asynchronous desktop evidence gates.

API timestamps never certify scanout. A desktop gate combines supported DXGI
acquisition information with bracketed window state and, when requested, a
visual revision witness. It never sleeps, supplies presentation pixels, or
changes the native transition clock. Raster content equality is independent
of delivery freshness: a new desktop delivery can contain identical pixels.
"""
import ctypes
import copy
import math
import time


class NativeObservation(ctypes.Structure):
    _fields_ = (
        [(name, ctypes.c_uint32) for name in ("version", "byteSize")]
        + [("sequence", ctypes.c_uint64)]
        + [(name, ctypes.c_uint32) for name in ("submittedPresentId", "lastPresentHRESULT")]
        + [(name, ctypes.c_double) for name in (
            "lastPresentBeginSeconds", "lastPresentReturnSeconds",
            "sourceCommitBeginSeconds", "sourceCommitReturnSeconds",
            "sourceWaitBeginSeconds", "sourceWaitReturnSeconds",
            "sourceShowBeginSeconds", "sourceShowReturnSeconds",
            "targetImportBeginSeconds", "targetReadySeconds",
            "endpointPresentReturnSeconds", "hostHideBeginSeconds", "hostHideReturnSeconds",
            "lastFrameElapsedSeconds", "lastFrameMotion", "lastFrameContent")]
        + [("currentRect", ctypes.c_float * 4)]
        + [(name, ctypes.c_uint32) for name in (
            "sourceWidth", "sourceHeight", "targetWidth", "targetHeight", "sourceFormat", "targetFormat")]
        + [(name, ctypes.c_int32) for name in ("hostLeft", "hostTop", "hostWidth", "hostHeight")]
    )


class NativePresentRow(ctypes.Structure):
    _fields_ = ([(name, ctypes.c_uint32) for name in ("version", "byteSize")]
        + [("sequence", ctypes.c_uint64)]
        + [(name, ctypes.c_uint32) for name in ("submittedPresentId", "presentHRESULT")]
        + [(name, ctypes.c_double) for name in (
            "presentBeginSeconds", "presentReturnSeconds", "elapsedSeconds", "motion", "content")]
        + [("currentRect", ctypes.c_float * 4)])


class NativePresentTrace(ctypes.Structure):
    _fields_ = ([(name, ctypes.c_uint32) for name in ("version", "byteSize", "rowByteSize", "count")]
        + [("totalFrames", ctypes.c_uint64), ("rows", NativePresentRow * 128)])


def configure_observer(dll):
    if ctypes.sizeof(NativeObservation) != 208:
        raise RuntimeError("Native observation layout differs from version 1")
    if hasattr(dll, "cspm_comp_hwnd"):
        dll.cspm_comp_hwnd.argtypes = [ctypes.c_void_p]
        dll.cspm_comp_hwnd.restype = ctypes.c_size_t
    if hasattr(dll, "cspm_comp_observation"):
        dll.cspm_comp_observation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        dll.cspm_comp_observation.restype = ctypes.c_int
    if hasattr(dll, "cspm_comp_present_trace"):
        dll.cspm_comp_present_trace.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        dll.cspm_comp_present_trace.restype = ctypes.c_int


def native_observation(dll, host):
    if not host or not hasattr(dll, "cspm_comp_observation"):
        return {"scope": "native observation unavailable"}
    value = NativeObservation()
    value.version, value.byteSize = 1, ctypes.sizeof(value)
    if not dll.cspm_comp_observation(host, ctypes.byref(value), ctypes.sizeof(value)):
        raise RuntimeError("Native observation version/size rejected")
    if value.version != 1 or value.byteSize != ctypes.sizeof(value):
        raise RuntimeError("Native observation returned an incompatible version/size")
    result = {name: list(getattr(value, name)) if name == "currentRect" else getattr(value, name)
              for name, _ in value._fields_}
    result["scope"] = "Absolute QPC API boundaries and submitted-frame identity; not physical scanout"
    return result


def native_present_trace(dll, host):
    if not host or not hasattr(dll, "cspm_comp_present_trace"):
        return {"scope": "native present history unavailable"}
    value = NativePresentTrace()
    value.version, value.byteSize, value.rowByteSize = 1, ctypes.sizeof(value), ctypes.sizeof(NativePresentRow)
    if value.byteSize != 10264 or value.rowByteSize != 80:
        raise RuntimeError("Native present trace ABI layout differs")
    if not dll.cspm_comp_present_trace(host, ctypes.byref(value), ctypes.sizeof(value)):
        raise RuntimeError("Native present trace version/size rejected")
    if value.version != 1 or value.byteSize != ctypes.sizeof(value) or value.rowByteSize != ctypes.sizeof(NativePresentRow):
        raise RuntimeError("Native present trace returned an incompatible version/size")
    if value.count > 128 or value.count > value.totalFrames:
        raise RuntimeError("Native present history count is invalid")
    rows = [{name: list(getattr(row, name)) if name == "currentRect" else getattr(row, name)
             for name, _ in row._fields_} for row in value.rows[:value.count]]
    return {"rows": rows, "totalFrames": value.totalFrames,
        "truncated": value.totalFrames > value.count,
        "scope": "Submitted-frame history on absolute QPC; native Present return is not scanout"}


def _positive_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _finite_seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _lookup(state, path):
    value = state
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None, False
        value = value[key]
    return value, True


class DesktopFrameObserver:
    """Track one capture session without using content changes as a clock.

    ``acquisitionSequence`` must come from successful AcquireNextFrame calls,
    not caller polling or the DXCAM ring-buffer/cache. ``desktopFrameQpcTicks``
    must be DXGI_OUTDUPL_FRAME_INFO.LastPresentTime, never a mouse-update time.
    A caller may supply a content digest *after* its timed work to distinguish
    unchanged and changed deliveries; an absent digest is reported unknown.
    """

    def __init__(self, *, now=None):
        self.started_seconds = time.perf_counter() if now is None else now
        if not _finite_seconds(self.started_seconds):
            raise ValueError("Capture-session start must be finite QPC seconds")
        self.generation = 0
        self.last_comparison_generation = 0
        self.last_acquisition_sequence = 0
        self.acquisition_session_generation = None
        self.last_desktop_ticks = 0
        self.last_content_revision = None

    def observe(self, pixels, metadata, *, content_revision=None):
        metadata = copy.deepcopy(metadata)
        sequence = metadata.get("acquisitionSequence")
        session = metadata.get("acquisitionSessionGeneration")
        ticks = metadata.get("desktopFrameQpcTicks")
        frequency = metadata.get("qpcFrequency")
        fresh = metadata.get("freshAcquisition") is True
        result = {**metadata, "captureSessionStartSeconds": self.started_seconds,
            "observerGeneration": self.generation,
            "lastComparisonGeneration": self.last_comparison_generation,
            "contentDelivery": "not compared",
            "scope": "Supported DXGI desktop raster delivery and bracketed state; not physical scanout"}
        if pixels is None:
            result.update(delivery="no new observable frame", usableDesktopDelivery=False)
            return result
        if not fresh or metadata.get("cacheFallbackAllowed") is not False:
            result.update(delivery="stale cached frame", usableDesktopDelivery=False)
            return result
        if metadata.get("newDeliveryObserved") is not True:
            result.update(delivery="successful native acquisition unproved", usableDesktopDelivery=False)
            return result
        if not _positive_integer(session):
            result.update(delivery="capture session unavailable", usableDesktopDelivery=False)
            return result
        if self.acquisition_session_generation is None:
            self.acquisition_session_generation = session
        elif session != self.acquisition_session_generation:
            result.update(delivery="capture session changed", usableDesktopDelivery=False)
            return result
        if not _positive_integer(sequence):
            result.update(delivery="delivery sequence unavailable", usableDesktopDelivery=False)
            return result
        if sequence <= self.last_acquisition_sequence:
            result.update(delivery="stale cached frame", usableDesktopDelivery=False)
            return result
        self.last_acquisition_sequence = sequence
        self.generation += 1
        result["observerGeneration"] = self.generation
        result["expectedAcquisitionSessionGeneration"] = self.acquisition_session_generation
        if metadata.get("desktopPixelsUpdated") is not True:
            result.update(delivery="pointer-only or unproved raster delivery", usableDesktopDelivery=False)
            return result
        if not _positive_integer(ticks) or not _positive_integer(frequency):
            result.update(delivery="desktop presentation timestamp unavailable", usableDesktopDelivery=False)
            return result
        if ticks <= self.last_desktop_ticks:
            result.update(delivery="stale desktop presentation timestamp", usableDesktopDelivery=False)
            return result
        self.last_desktop_ticks = ticks
        if content_revision is not None:
            if self.last_content_revision is not None:
                result["contentDelivery"] = ("new delivery containing unchanged pixels"
                    if content_revision == self.last_content_revision else "new delivery containing changed pixels")
            else:
                result["contentDelivery"] = "first content revision"
            self.last_content_revision = content_revision
        result.update(delivery="fresh desktop raster delivery", usableDesktopDelivery=True,
            desktopFrameSeconds=ticks / frequency)
        return result


class FreshPresentationGate:
    """One bounded frame-and-state gate, polled by the caller's event loop.

    ``after_seconds`` is a conservative QPC lower bound for the relevant commit
    or state change. State fields use dotted dictionary paths and must match on
    both sides of acquisition. Numeric minimums support submitted revision IDs;
    they remain API evidence. Required ``expected_witness`` values are checked
    in metadata.visualWitness and are the caller's independent sampled visual
    revision evidence. A missing witness never silently weakens the gate.
    """

    def __init__(self, observer, rectangle, after_seconds, *, timeout_ms=750,
                 expected_state=None, minimum_state=None, expected_witness=None,
                 now=None):
        self.observer = observer
        rectangle = list(rectangle)
        if len(rectangle) != 4 or any(not isinstance(value, int) or isinstance(value, bool)
                                    for value in rectangle) or rectangle[2] <= 0 or rectangle[3] <= 0:
            raise ValueError("Expected sample must be an integer physical XYWH rectangle")
        self.rectangle = rectangle
        if not _finite_seconds(after_seconds) or after_seconds < observer.started_seconds:
            raise ValueError("Presentation lower bound must follow capture-session start")
        if not _finite_seconds(timeout_ms) or timeout_ms <= 0:
            raise ValueError("Observation timeout must be finite and positive")
        self.started_seconds = time.perf_counter() if now is None else now
        if not _finite_seconds(self.started_seconds) or self.started_seconds < after_seconds:
            raise ValueError("Observation must begin after its presentation lower bound")
        self.after_seconds = after_seconds
        self.deadline_seconds = self.started_seconds + timeout_ms / 1000
        self.minimum_generation = max(observer.generation, observer.last_comparison_generation)
        self.expected_state = dict(expected_state or {})
        self.minimum_state = dict(minimum_state or {})
        if any(not _finite_seconds(value) for value in self.minimum_state.values()):
            raise ValueError("State revision minimums must be finite numeric values")
        self.expected_witness = None if expected_witness is None else dict(expected_witness)
        if not self.expected_state and not self.minimum_state:
            raise ValueError("A presentation comparison requires observable window state")
        if self.expected_witness == {}:
            raise ValueError("Required visual witness must have an expected revision")
        self.polls = 0
        self.last_poll_seconds = self.started_seconds
        self.reasons = {}
        self.terminal_evidence = None

    def _state_mismatches(self, state):
        mismatches = []
        for path, expected in self.expected_state.items():
            observed, available = _lookup(state, path)
            if not available or observed != expected:
                mismatches.append({"path": path, "expected": expected,
                    "observed": observed, "available": available})
        for path, minimum in self.minimum_state.items():
            observed, available = _lookup(state, path)
            if not available or not _finite_seconds(observed) or observed < minimum:
                mismatches.append({"path": path, "minimum": minimum,
                    "observed": observed, "available": available})
        return mismatches

    def poll(self, pixels, metadata, *, state_before, state_after, now=None,
             content_revision=None):
        if self.terminal_evidence is not None:
            return None, copy.deepcopy(self.terminal_evidence)
        current_seconds = time.perf_counter() if now is None else now
        if not _finite_seconds(current_seconds) or current_seconds < self.last_poll_seconds:
            raise ValueError("Observation poll must use advancing finite QPC seconds")
        self.last_poll_seconds = current_seconds
        self.polls += 1
        frame = self.observer.observe(pixels, metadata, content_revision=content_revision)
        before_misses = self._state_mismatches(state_before)
        after_misses = self._state_mismatches(state_after)
        shape = getattr(pixels, "shape", ()) if pixels is not None else ()
        times = [frame.get(key) for key in ("callStarted", "callFinished", "desktopFrameSeconds")]
        reason = None
        if before_misses or after_misses:
            reason = "wrong visible state"
        elif not frame["usableDesktopDelivery"]:
            reason = frame["delivery"]
        elif frame.get("rectangleXYWH") != self.rectangle or tuple(shape[:2]) != (self.rectangle[3], self.rectangle[2]):
            reason = "wrong sampled physical rectangle"
        elif not all(_finite_seconds(value) for value in times):
            reason = "desktop arrival timestamp unavailable"
        elif not (self.started_seconds <= times[0] <= times[1] <= current_seconds):
            reason = "acquisition timestamps outside observation attempt"
        elif times[2] <= self.after_seconds:
            reason = "desktop frame precedes presentation lower bound"
        elif times[2] > times[1]:
            reason = "desktop presentation timestamp follows acquisition return"
        elif frame["observerGeneration"] <= self.minimum_generation:
            reason = "observer generation already used for comparison"
        elif self.expected_witness is not None:
            witness = frame.get("visualWitness")
            if not isinstance(witness, dict) or any(witness.get(key) != value
                                                  for key, value in self.expected_witness.items()):
                reason = "intended presentation visual witness unavailable"
        evidence = {"status": "PENDING", "afterPresentationSeconds": self.after_seconds,
            "observationStartedSeconds": self.started_seconds,
            "observationDeadlineSeconds": self.deadline_seconds,
            "observedAtSeconds": current_seconds, "polls": self.polls,
            "minimumObserverGeneration": self.minimum_generation,
            "expectedRectangleXYWH": self.rectangle,
            "stateBefore": copy.deepcopy(state_before), "stateAfter": copy.deepcopy(state_after),
            "stateMismatchesBefore": before_misses, "stateMismatchesAfter": after_misses,
            "expectedVisualWitness": self.expected_witness,
            "frame": frame, "reason": reason,
            "scope": "Desktop raster newer than commit, observed state and optional visual revision; scanout unmeasured"}
        if reason:
            self.reasons[reason] = self.reasons.get(reason, 0) + 1
        evidence["rejectedObservations"] = dict(self.reasons)
        if current_seconds >= self.deadline_seconds:
            evidence.update(status="FAIL", reason=reason or "fresh desktop frame arrived after bounded timeout")
            self.terminal_evidence = evidence
            return None, copy.deepcopy(evidence)
        if reason is None:
            self.observer.last_comparison_generation = frame["observerGeneration"]
            evidence.update(status="PASS", reason="successful fresh-frame observation")
            self.terminal_evidence = evidence
            return pixels, copy.deepcopy(evidence)
        return None, evidence
