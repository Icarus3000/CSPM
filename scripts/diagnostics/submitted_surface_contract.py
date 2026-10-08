"""Coordinate evidence for bounded stopped-surface probes.

These are observed geometry conversions, not presentation pixels. Client-local
physical texels remain the probe inputs; Qt logical coordinates describe their
pixel centres and are never rounded back into native sampling coordinates.
"""
from __future__ import annotations

import ctypes
import math


class FrameIdentity(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("byteSize", ctypes.c_uint32),
        ("revision", ctypes.c_uint64)] + [(name, ctypes.c_uint32) for name in
        ("width", "height", "format", "mipLevels", "arraySize", "sampleCount",
         "subresource", "orientation")]


class ProbeIdentity(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ("version", "byteSize")]
    _fields_ += [(name, ctypes.c_uint64) for name in ("hostGeneration",
        "snapshotRevision", "sourceFrameRevision", "targetFrameRevision")]
    _fields_ += [(name, ctypes.c_uint32) for name in ("submittedPresentId", "phase",
        "witnessRevision", "subresource")]
    _fields_ += [(name, ctypes.c_double) for name in ("snapshotQueuedSeconds",
        "presentBeginSeconds", "presentReturnSeconds", "motion", "content")]
    _fields_ += [(name, ctypes.c_int32) for name in ("hostLeft", "hostTop", "hostWidth",
        "hostHeight", "sourceLeft", "sourceTop", "sourceWidth", "sourceHeight",
        "targetLeft", "targetTop", "targetWidth", "targetHeight")]
    _fields_ += [(name, ctypes.c_uint32) for name in ("sourceFormat", "targetFormat",
        "snapshotFormat", "snapshotWidth", "snapshotHeight", "snapshotEnabled",
        "orientation", "premultiplied")]
    _fields_ += [(name, ctypes.c_uint64) for name in ("sourceResourceIdentity",
        "targetResourceIdentity", "snapshotResourceIdentity")]


def enable_probe_snapshot(dll, host):
    if not host or not hasattr(dll, "cspm_comp_enable_probe_snapshot"):
        raise RuntimeError("Revision-keyed submitted snapshot unavailable")
    function = dll.cspm_comp_enable_probe_snapshot
    function.argtypes, function.restype = [ctypes.c_void_p], ctypes.c_int
    if not function(host):
        raise RuntimeError("Submitted snapshot must be enabled before source preparation")


def _identity(dll, owner, name, kind, size):
    if not owner or not hasattr(dll, name):
        raise RuntimeError("Revision-keyed surface identity unavailable")
    value = kind()
    if ctypes.sizeof(value) != size:
        raise RuntimeError("Surface identity ABI layout differs")
    value.version, value.byteSize = 1, size
    function = getattr(dll, name)
    function.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if not function(owner, ctypes.byref(value), size):
        raise RuntimeError("Surface identity rejected")
    if value.version != 1 or value.byteSize != size or value.subresource != 0 or value.orientation != 1:
        raise RuntimeError("Surface identity returned an incompatible contract")
    return {name: getattr(value, name) for name, _ in kind._fields_}


def frame_identity(dll, frame):
    value = _identity(dll, frame, "cspm_gpu_frame_identity", FrameIdentity, 48)
    if (not value["revision"] or not value["width"] or not value["height"]
            or value["mipLevels"] != 1 or value["arraySize"] != 1 or value["sampleCount"] != 1
            or value["format"] not in (28, 87)):
        raise RuntimeError("Captured frame identity is unsupported")
    return value


def probe_identity(dll, host, *, phase):
    if type(phase) is not int or phase not in (1, 3):
        raise ValueError("Only stopped source and complete endpoint phases may be sampled")
    value = _identity(dll, host, "cspm_comp_probe_identity", ProbeIdentity, 200)
    if (value["phase"] != phase or value["snapshotEnabled"] != 1
            or not value["hostGeneration"] or not value["snapshotRevision"]
            or not value["submittedPresentId"] or not value["snapshotResourceIdentity"]
            or not value["sourceFrameRevision"] or not value["sourceResourceIdentity"]
            or value["snapshotFormat"] != 87 or value["premultiplied"] != 1
            or value["sourceFormat"] not in (28, 87)
            or any(value[name] <= 0 for name in ("hostWidth", "hostHeight", "sourceWidth", "sourceHeight"))
            or value["snapshotWidth"] != value["hostWidth"]
            or value["snapshotHeight"] != value["hostHeight"]
            or value["motion"] != (1 if phase == 3 else 0)
            or value["content"] != (1 if phase == 3 else 0)
            or (phase == 3 and (not value["targetFrameRevision"] or not value["targetResourceIdentity"]
                or value["targetFormat"] not in (28, 87) or value["targetWidth"] <= 0 or value["targetHeight"] <= 0))):
        raise RuntimeError("Stopped submitted-surface revision is unproved")
    times = [value[name] for name in ("snapshotQueuedSeconds", "presentBeginSeconds", "presentReturnSeconds")]
    if not all(math.isfinite(v) and v > 0 for v in times) or not times[0] <= times[1] <= times[2]:
        raise RuntimeError("Submitted snapshot must precede its recorded Present")
    return value


def _rectangle(value, name):
    if (len(value) != 4 or any(type(v) is not int for v in value)
            or value[2] <= 0 or value[3] <= 0):
        raise ValueError(name + " requires integral physical XYWH and positive extent")
    return list(value)


def coordinate_contract(coordinates, *, client_xywh, window_xywh, output_xywh,
                        host_xywh, content_xywh, dpr, framebuffer_wh):
    """Map every requested top-left texel, retaining all margins and padding.

    All rectangles are measured desktop physical XYWH. A source or target
    framebuffer has exactly the complete native client extent. The submitted
    surface has exactly the fixed transition host extent. Bounds are half-open.
    """
    client = _rectangle(client_xywh, "client")
    window = _rectangle(window_xywh, "window frame")
    output = _rectangle(output_xywh, "output")
    host = _rectangle(host_xywh, "transition host")
    content = _rectangle(content_xywh, "content")
    if (isinstance(dpr, bool) or not isinstance(dpr, (int, float))
            or not math.isfinite(dpr) or dpr <= 0):
        raise ValueError("DPR must be positive and finite")
    if list(framebuffer_wh) != client[2:] or any(type(v) is not int for v in framebuffer_wh):
        raise ValueError("Framebuffer must match the complete physical client extent")
    if not 1 <= len(coordinates) <= 64:
        raise ValueError("Coordinate evidence requires 1 to 64 texels")
    for name, outer in (("window", window), ("output", output), ("host", host)):
        if not (outer[0] <= client[0] and outer[1] <= client[1]
                and client[0]+client[2] <= outer[0]+outer[2]
                and client[1]+client[3] <= outer[1]+outer[3]):
            raise ValueError("Complete client must lie inside " + name)
    if not (client[0] <= content[0] and client[1] <= content[1]
            and content[0]+content[2] <= client[0]+client[2]
            and content[1]+content[3] <= client[1]+client[3]):
        raise ValueError("Content must lie inside the complete client")
    padding = [content[0]-client[0], content[1]-client[1],
        client[0]+client[2]-content[0]-content[2],
        client[1]+client[3]-content[1]-content[3]]
    rows = []
    for point in coordinates:
        if (len(point) != 2 or any(type(v) is not int for v in point)
                or not 0 <= point[0] < client[2] or not 0 <= point[1] < client[3]):
            raise ValueError("Texel must lie inside the complete half-open client extent")
        x, y = point
        desktop = [client[0]+x, client[1]+y]
        rows.append({"clientPhysicalXY": [x, y], "desktopPhysicalXY": desktop,
            "outputPhysicalXY": [desktop[0]-output[0], desktop[1]-output[1]],
            "windowFramePhysicalXY": [desktop[0]-window[0], desktop[1]-window[1]],
            "qtLogicalPixelCentreXY": [(x+.5)/dpr, (y+.5)/dpr],
            "framebufferTexelXY": [x, y], "endpointTextureTexelXY": [x, y],
            "submittedSurfaceTexelXY": [desktop[0]-host[0], desktop[1]-host[1]],
            "contentPhysicalXY": [desktop[0]-content[0], desktop[1]-content[1]]})
    return {"clientXYWH": client, "windowXYWH": window, "outputXYWH": output,
        "hostXYWH": host, "contentXYWH": content, "dpr": dpr,
        "framebufferWH": list(framebuffer_wh), "submittedSurfaceWH": host[2:],
        "contentPaddingPhysicalLTRB": padding,
        "contentPaddingLogicalLTRB": [v/dpr for v in padding],
        "orientation": "top-left origin; x right, y down; no vertical inversion",
        "bounds": "half-open [0,width) and [0,height); no margin cropping",
        "subresource": 0,
        "rowPitch": "Native Map.RowPitch per row, four bytes per BGRA/RGBA texel",
        "alpha": "premultiplied encoded UNORM; BGRA returned, RGBA source reordered",
        "colourSpace": "UNORM channels; no diagnostic gamma/alpha conversion",
        "samples": rows,
        "scope": "Geometry evidence only; native revision identity and fresh desktop gates are separate"}
