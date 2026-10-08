"""Measured-coordinate conversions must never shift a bounded native sample."""
import importlib.util
import ctypes
from pathlib import Path
from types import SimpleNamespace

import pytest

path = Path(__file__).resolve().parents[1]/"scripts/diagnostics/submitted_surface_contract.py"
spec = importlib.util.spec_from_file_location("submitted_surface_contract", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(**changes):
    values = dict(client_xywh=[-1690, 132, 1124, 784],
        window_xywh=[-1692, 130, 1128, 788], output_xywh=[-1920, 0, 1920, 1080],
        host_xywh=[-1920, 0, 1920, 1040], content_xywh=[-1678, 144, 1100, 760],
        dpr=1.25, framebuffer_wh=[1124, 784])
    values.update(changes)
    return values


@pytest.mark.parametrize("dpr", [1, 1.25, 2.25])
def test_known_corners_edges_centre_and_directory_band_keep_exact_physical_texels(dpr):
    points = [(0,0), (1123,0), (0,783), (1123,783), (562,0), (562,783),
        (0,392), (1123,392), (562,392), (1111,646), (1121,654)]
    result = module.coordinate_contract(points, **fixture(dpr=dpr))
    assert result["contentPaddingPhysicalLTRB"] == [12]*4
    assert result["contentPaddingLogicalLTRB"] == [12/dpr]*4
    assert result["samples"][9] == {
        "clientPhysicalXY": [1111,646], "desktopPhysicalXY": [-579,778],
        "outputPhysicalXY": [1341,778], "windowFramePhysicalXY": [1113,648],
        "qtLogicalPixelCentreXY": [1111.5/dpr,646.5/dpr],
        "framebufferTexelXY": [1111,646], "endpointTextureTexelXY": [1111,646],
        "submittedSurfaceTexelXY": [1341,778], "contentPhysicalXY": [1099,634]}
    assert result["samples"][3]["submittedSurfaceTexelXY"] == [1353,915]
    assert result["samples"][0]["submittedSurfaceTexelXY"] == [230,132]
    for row, point in zip(result["samples"], points):
        assert row["framebufferTexelXY"] == row["endpointTextureTexelXY"] == list(point)


@pytest.mark.parametrize("points", [[], [(0,0)]*65, [(-1,0)], [(1124,0)],
    [(0,784)], [(True,0)], [(0.5,0)]])
def test_invalid_or_exclusive_edge_coordinates_reject(points):
    with pytest.raises(ValueError):
        module.coordinate_contract(points, **fixture())


@pytest.mark.parametrize("changes", [dict(dpr=0), dict(dpr=float("nan")),
    dict(dpr=True), dict(framebuffer_wh=[1123,784]),
    dict(host_xywh=[-1689,132,1124,784]), dict(output_xywh=[0,0,1920,1080]),
    dict(content_xywh=[-1691,144,1100,760]), dict(window_xywh=[-1690,132,1123,784])])
def test_mismatched_origins_extents_and_dpi_reject_without_inferred_crops(changes):
    with pytest.raises(ValueError):
        module.coordinate_contract([(0,0)], **fixture(**changes))


class IdentityFunction:
    """Emulate only the C metadata ABI; never instantiate a GPU resource."""
    def __init__(self, kind, fields, returned=1):
        self.kind, self.fields, self.returned = kind, fields, returned
        self.calls = []

    def __call__(self, owner, output, capacity):
        value = ctypes.cast(output, ctypes.POINTER(self.kind)).contents
        self.calls.append((owner, value.version, value.byteSize, capacity))
        for name, item in self.fields.items():
            setattr(value, name, item)
        return self.returned


def frame_dll(**changes):
    values = dict(version=1, byteSize=48, revision=201, width=100, height=80,
        format=87, mipLevels=1, arraySize=1, sampleCount=1, subresource=0, orientation=1)
    values.update(changes)
    function = IdentityFunction(module.FrameIdentity, values)
    return SimpleNamespace(cspm_gpu_frame_identity=function), function, values


def probe_dll(phase=3, **changes):
    values = dict(version=1, byteSize=200, hostGeneration=9, snapshotRevision=2,
        sourceFrameRevision=201, targetFrameRevision=202 if phase == 3 else 0,
        submittedPresentId=7, phase=phase, witnessRevision=11, subresource=0,
        snapshotQueuedSeconds=12.0, presentBeginSeconds=12.1, presentReturnSeconds=12.2,
        motion=1 if phase == 3 else 0, content=1 if phase == 3 else 0,
        hostLeft=-1920, hostTop=-1080, hostWidth=100, hostHeight=80,
        sourceLeft=0, sourceTop=0, sourceWidth=100, sourceHeight=80,
        targetLeft=0, targetTop=0, targetWidth=100 if phase == 3 else 0,
        targetHeight=80 if phase == 3 else 0, sourceFormat=87,
        targetFormat=28 if phase == 3 else 0, snapshotFormat=87,
        snapshotWidth=100, snapshotHeight=80, snapshotEnabled=1, orientation=1,
        premultiplied=1, sourceResourceIdentity=301,
        targetResourceIdentity=302 if phase == 3 else 0, snapshotResourceIdentity=303)
    values.update(changes)
    function = IdentityFunction(module.ProbeIdentity, values)
    return SimpleNamespace(cspm_comp_probe_identity=function), function, values


@pytest.mark.parametrize("kind,size,offsets", [
    (module.FrameIdentity, 48, dict(version=0, byteSize=4, revision=8, width=16,
        height=20, format=24, mipLevels=28, arraySize=32, sampleCount=36,
        subresource=40, orientation=44)),
    (module.ProbeIdentity, 200, dict(version=0, byteSize=4, hostGeneration=8,
        snapshotRevision=16, sourceFrameRevision=24, targetFrameRevision=32,
        submittedPresentId=40, phase=44, witnessRevision=48, subresource=52,
        snapshotQueuedSeconds=56, presentBeginSeconds=64, presentReturnSeconds=72,
        motion=80, content=88, hostLeft=96, hostTop=100, hostWidth=104,
        hostHeight=108, sourceLeft=112, sourceTop=116, sourceWidth=120,
        sourceHeight=124, targetLeft=128, targetTop=132, targetWidth=136,
        targetHeight=140, sourceFormat=144, targetFormat=148, snapshotFormat=152,
        snapshotWidth=156, snapshotHeight=160, snapshotEnabled=164,
        orientation=168, premultiplied=172, sourceResourceIdentity=176,
        targetResourceIdentity=184, snapshotResourceIdentity=192)),
])
def test_ctypes_layout_preserves_native_fixed_width_field_offsets(kind, size, offsets):
    assert ctypes.sizeof(kind) == size
    assert {name: getattr(kind, name).offset for name, _ in kind._fields_} == offsets


@pytest.mark.parametrize("format", [28, 87])
def test_supported_immutable_frame_identity_is_revision_keyed_with_exact_abi_handshake(format):
    dll, function, values = frame_dll(format=format)
    assert module.frame_identity(dll, 101) == values
    assert function.calls == [(101, 1, 48, 48)]
    assert function.argtypes == [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    assert function.restype is ctypes.c_int


@pytest.mark.parametrize("phase", [1, 3])
def test_stopped_identity_requires_complete_revision_metadata_and_preserves_negative_origin(phase):
    dll, function, values = probe_dll(phase)
    assert module.probe_identity(dll, 101, phase=phase) == values
    assert function.calls == [(101, 1, 200, 200)]


@pytest.mark.parametrize("operation", ["frame", "probe", "enable"])
def test_previous_dll_without_revision_snapshot_api_rejects_instead_of_using_time(operation):
    old_dll = SimpleNamespace(cspm_comp_observation=object())
    with pytest.raises(RuntimeError, match="unavailable"):
        if operation == "frame":
            module.frame_identity(old_dll, 101)
        elif operation == "probe":
            module.probe_identity(old_dll, 101, phase=3)
        else:
            module.enable_probe_snapshot(old_dll, 101)


@pytest.mark.parametrize("operation", ["frame", "probe"])
def test_null_owner_rejects_before_calling_the_identity_api(operation):
    dll, function, _ = frame_dll() if operation == "frame" else probe_dll()
    with pytest.raises(RuntimeError, match="unavailable"):
        if operation == "frame":
            module.frame_identity(dll, None)
        else:
            module.probe_identity(dll, None, phase=3)
    assert function.calls == []


@pytest.mark.parametrize("operation", ["frame", "probe"])
def test_native_identity_rejection_cannot_become_partial_metadata_evidence(operation):
    dll, function, _ = frame_dll() if operation == "frame" else probe_dll()
    function.returned = 0
    with pytest.raises(RuntimeError, match="identity rejected"):
        if operation == "frame":
            module.frame_identity(dll, 101)
        else:
            module.probe_identity(dll, 101, phase=3)


@pytest.mark.parametrize("field,value", [("version", 2), ("byteSize", 47),
    ("subresource", 1), ("orientation", 2), ("revision", 0), ("width", 0),
    ("height", 0), ("format", 29), ("mipLevels", 2), ("arraySize", 2),
    ("sampleCount", 2)])
def test_unknown_incompatible_or_unidentified_frame_metadata_rejects(field, value):
    dll, _, _ = frame_dll(**{field: value})
    with pytest.raises(RuntimeError):
        module.frame_identity(dll, 101)


@pytest.mark.parametrize("field,value", [("version", 2), ("byteSize", 199),
    ("subresource", 1), ("orientation", 2), ("phase", 1),
    ("snapshotEnabled", 0), ("snapshotEnabled", 2), ("hostGeneration", 0),
    ("snapshotRevision", 0), ("submittedPresentId", 0),
    ("sourceFrameRevision", 0), ("targetFrameRevision", 0),
    ("sourceResourceIdentity", 0), ("targetResourceIdentity", 0),
    ("snapshotResourceIdentity", 0), ("sourceFormat", 29), ("targetFormat", 29),
    ("snapshotFormat", 28), ("snapshotWidth", 99), ("snapshotHeight", 79),
    ("premultiplied", 0), ("motion", .999), ("content", .999),
    ("sourceWidth", 0), ("sourceHeight", 0), ("targetWidth", 0), ("targetHeight", 0)])
def test_endpoint_without_exact_supported_revision_phase_and_extent_metadata_rejects(field, value):
    dll, _, _ = probe_dll(**{field: value})
    with pytest.raises(RuntimeError):
        module.probe_identity(dll, 101, phase=3)


@pytest.mark.parametrize("phase", [0, 2, 4, True])
def test_only_stopped_source_and_complete_endpoint_are_supported_probe_phases(phase):
    dll, function, _ = probe_dll(phase)
    with pytest.raises(ValueError, match="stopped source"):
        module.probe_identity(dll, 101, phase=phase)
    assert function.calls == []


@pytest.mark.parametrize("field", ["snapshotQueuedSeconds", "presentBeginSeconds", "presentReturnSeconds"])
@pytest.mark.parametrize("value", [0, float("nan"), float("inf")])
def test_unmeasured_or_nonfinite_snapshot_present_boundaries_reject(field, value):
    dll, _, _ = probe_dll(**{field: value})
    with pytest.raises(RuntimeError, match="precede"):
        module.probe_identity(dll, 101, phase=3)


@pytest.mark.parametrize("changes", [dict(snapshotQueuedSeconds=12.15),
    dict(presentReturnSeconds=12.05), dict(hostWidth=0, snapshotWidth=0),
    dict(hostHeight=0, snapshotHeight=0)])
def test_reversed_submission_boundaries_or_empty_submitted_extent_reject(changes):
    dll, _, _ = probe_dll(**changes)
    with pytest.raises(RuntimeError):
        module.probe_identity(dll, 101, phase=3)


def test_snapshot_opt_in_is_explicit_and_native_refusal_is_retained():
    calls = []
    class EnableFunction:
        def __call__(self, host):
            calls.append(host)
            return 0
    function = EnableFunction()
    dll = SimpleNamespace(cspm_comp_enable_probe_snapshot=function)
    with pytest.raises(RuntimeError, match="before source preparation"):
        module.enable_probe_snapshot(dll, 101)
    assert calls == [101] and function.argtypes == [ctypes.c_void_p]
    assert function.restype is ctypes.c_int
