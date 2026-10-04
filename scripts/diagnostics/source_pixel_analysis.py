"""In-memory physical pixel diagnosis. Never writes images or pixel values.

Run comparisons on owned snapshots after the timed transition, not on its
critical path. Exact array equality is the gate; the searches below only explain a
failed comparison and never relax it. Desktop alpha is not texture alpha.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import numbers
import os
import sys
import time

if os.environ.get("CSPM_PIXEL_DEPENDENCIES"):
    sys.path.insert(0, os.environ["CSPM_PIXEL_DEPENDENCIES"])
import numpy as np


def _physical_rectangle(rectangle, *, label, positive_extent=False):
    values = tuple(rectangle)
    if len(values) != 4 or any(isinstance(value, (bool, np.bool_)) or
            not isinstance(value, numbers.Real) or not np.isfinite(value) or int(value) != value
            for value in values):
        raise ValueError(f"{label} requires four integral physical pixels")
    values = [int(value) for value in values]
    if positive_extent and (values[2] <= 0 or values[3] <= 0):
        raise ValueError(f"{label} requires positive extent")
    return values


def _pixels(array):
    array = np.asarray(array)
    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError("Expected HxWx3 or HxWx4 uint8 BGR(A) pixels")
    if not array.shape[0] or not array.shape[1]:
        raise ValueError("Empty pixel arrays cannot qualify")
    return array


def array_summary(array):
    """Aggregate identity, channel means and alpha distribution, without content."""
    array = _pixels(array)
    result = {"shape": list(array.shape), "sha256": hashlib.sha256(
        np.ascontiguousarray(array).tobytes()).hexdigest(),
        "channelMeansBGRA": array.mean(axis=(0, 1)).tolist()}
    if array.shape[2] == 4:
        alpha = array[:, :, 3]
        result["alpha"] = {"zero": int(np.count_nonzero(alpha == 0)),
            "opaque": int(np.count_nonzero(alpha == 255)),
            "partial": int(np.count_nonzero((alpha > 0) & (alpha < 255)))}
    return result


def physical_regions(comparison_xywh, client_xywh, content_xywh, *, header_height_px,
                     border_px):
    """Partition a physical crop using observed client/content/header geometry.

    All rectangles are absolute desktop physical pixels; never infer DPR from
    a tested window size. Content includes its border. The shadow/margin bin
    is an area classification, not an assertion that every pixel is a shadow.
    Rounded corners remain in their bounding-box bin and exact comparison.
    """
    def ltrb(xywh):
        x, y, width, height = _physical_rectangle(xywh,
            label="Observed physical region", positive_extent=True)
        return [x, y, x + width, y + height]
    crop, client, content = map(ltrb, (comparison_xywh, client_xywh, content_xywh))
    if not np.isfinite(header_height_px) or header_height_px < 0 or not isinstance(border_px, int) or border_px < 0:
        raise ValueError("Physical header and border metrics must be nonnegative")
    if not (client[0] <= content[0] < content[2] <= client[2] and client[1] <= content[1] < content[3] <= client[3]):
        raise ValueError("Observed content rectangle must lie inside client")
    def intersect(one, two):
        left, top = max(one[0], two[0]), max(one[1], two[1])
        right, bottom = min(one[2], two[2]), min(one[3], two[3])
        return [left, top, right, bottom] if left < right and top < bottom else None
    def subtract(one, two):
        inside = intersect(one, two)
        if inside is None:
            return [one]
        left, top, right, bottom = inside
        strips = [[one[0], one[1], one[2], top], [one[0], bottom, one[2], one[3]],
                  [one[0], top, left, bottom], [right, top, one[2], bottom]]
        return [box for box in strips if box[0] < box[2] and box[1] < box[3]]
    def local(boxes):
        result = []
        for box in boxes:
            overlap = intersect(crop, box)
            if overlap:
                result.append([overlap[0] - crop[0], overlap[1] - crop[1],
                               overlap[2] - crop[0], overlap[3] - crop[1]])
        return result
    inset = min(border_px, (content[2] - content[0]) // 2, (content[3] - content[1]) // 2)
    inside = [content[0] + inset, content[1] + inset, content[2] - inset, content[3] - inset]
    header_bottom = min(inside[3], max(inside[1], content[1] + int(round(header_height_px))))
    regions = {"header": local([[inside[0], inside[1], inside[2], header_bottom]]),
        "clientBody": local([[inside[0], header_bottom, inside[2], inside[3]]]),
        "border": local(subtract(content, inside)),
        "shadowAndMargin": local(subtract(client, content)),
        "outsideClient": local(subtract(crop, client))}
    return regions


def _box(mask):
    yy, xx = np.nonzero(mask)
    return [int(xx.min()), int(yy.min()), int(xx.max()) + 1,
            int(yy.max()) + 1] if xx.size else None


def _score(old, new):
    delta = np.abs(old.astype(np.int16) - new.astype(np.int16))
    pixels = int(old.shape[0] * old.shape[1])
    count = int(np.count_nonzero(np.any(delta, axis=2)))
    return {"pixels": pixels, "differentPixels": count,
        "differencePercent": 100 * count / pixels,
        "meanChannelDifference": float(delta.mean()),
        "maxChannelDifference": int(delta.max())}


def _search_offset(old, new, radius):
    height, width = old.shape[:2]
    radius = min(radius, (height - 1) // 2, (width - 1) // 2)
    yy = np.unique(np.linspace(radius, height - radius - 1, min(128, height - 2 * radius)).astype(int))
    xx = np.unique(np.linspace(radius, width - radius - 1, min(128, width - 2 * radius)).astype(int))
    reference = old[yy[:, None], xx, :3]
    candidates = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            score = _score(reference, new[yy[:, None] + dy, xx + dx, :3])
            candidates.append((score["meanChannelDifference"], score["differentPixels"], abs(dx) + abs(dy), dx, dy))
    best = min(candidates)
    dx, dy = best[-2:]
    x0, x1 = max(0, -dx), min(width, width - dx)
    y0, y1 = max(0, -dy), min(height, height - dy)
    return {"radiusPixels": radius, "newSampleOffsetXY": [dx, dy],
        "sampledPixels": int(reference.shape[0] * reference.shape[1]),
        "bestSampleMeanDifference": best[0],
        "overlap": _score(old[y0:y1, x0:x1, :3], new[y0 + dy:y1 + dy, x0 + dx:x1 + dx, :3]),
        "excludedPixels": height * width - (y1 - y0) * (x1 - x0),
        "channels": "BGR; alpha excluded from this explanation",
        "scope": "Constant translation explanation; cropped overlap is not endpoint qualification"}


def _search_scale(old, new, scales):
    height, width = old.shape[:2]
    yy = np.unique(np.linspace(0, height - 1, min(128, height)).astype(int))
    xx = np.unique(np.linspace(0, width - 1, min(128, width)).astype(int))
    results = []
    for scale in scales:
        # Centered nearest-pixel geometry diagnostic, no interpolation tolerance.
        sy = np.rint((yy - (height - 1) / 2) * scale + (height - 1) / 2).astype(int)
        sx = np.rint((xx - (width - 1) / 2) * scale + (width - 1) / 2).astype(int)
        valid_y, valid_x = (sy >= 0) & (sy < height), (sx >= 0) & (sx < width)
        if not valid_y.any() or not valid_x.any():
            continue
        score = _score(old[yy[valid_y, None], xx[valid_x], :3], new[sy[valid_y, None], sx[valid_x], :3])
        baseline = _score(old[yy[valid_y, None], xx[valid_x], :3],
                          new[yy[valid_y, None], xx[valid_x], :3])
        results.append({"newSampleScale": float(scale),
            "sampledPixels": int(valid_y.sum() * valid_x.sum()), **score,
            "identityOnSameSample": baseline})
    return {"candidates": results, "scope": "Centered nearest-pixel diagnostic; not rescaled endpoint qualification"}


def compare_pixels(old, new, *, regions=None, stale_frames=None, offset_radius=3,
                   scales=(0.98, 0.99, 1.0, 1.01, 1.02)):
    """Return exact totals plus privacy-safe spatial explanations of BGR(A) arrays.

    Regions are named local [left, top, right, bottom] rectangles or lists of
    rectangles (e.g. four border strips). Overlapping strips are counted once.
    Regions may
    overlap; callers define header/body/border/margin semantics explicitly.
    Histograms and hashes contain no retained colors or raster content.
    """
    old, new = _pixels(old), _pixels(new)
    if not isinstance(offset_radius, int) or offset_radius < 0 or offset_radius > 16:
        raise ValueError("Offset search radius must be an integer from 0 to 16")
    scales = tuple(scales)
    if any(not np.isfinite(scale) or scale <= 0 for scale in scales):
        raise ValueError("Scale search candidates must be finite positive values")
    result = {"before": array_summary(old), "after": array_summary(new)}
    if old.shape != new.shape:
        return {**result, "status": "FAIL", "reason": "different physical pixel arrays"}
    difference = np.any(old != new, axis=2)
    rgb_difference = np.any(old[:, :, :3] != new[:, :, :3], axis=2)
    count = int(difference.sum())
    result.update(status="PASS" if not count else "FAIL", **_score(old, new),
        rgbDifferentPixels=int(rgb_difference.sum()), mismatchBoundsLTRB=_box(difference),
        rowMismatchHistogram=difference.sum(axis=1).tolist(),
        columnMismatchHistogram=difference.sum(axis=0).tolist(),
        alphaDifferentPixels=int(np.count_nonzero(old[:, :, 3] != new[:, :, 3])) if old.shape[2] == 4 else None)
    height, width = old.shape[:2]
    result["regions"] = {}
    for name, region in (regions or {}).items():
        rectangles = [region] if len(region) == 4 and np.isscalar(region[0]) else region
        mask = np.zeros((height, width), dtype=bool)
        parsed = []
        for rectangle in rectangles:
            left, top, right, bottom = _physical_rectangle(rectangle,
                label="Comparison region")
            if not (0 <= left <= right <= width and 0 <= top <= bottom <= height):
                raise ValueError("Comparison region exceeds physical array")
            parsed.append([left, top, right, bottom])
            mask[top:bottom, left:right] = True
        region_count, changed_count = int(mask.sum()), int(np.count_nonzero(difference & mask))
        result["regions"][name] = {"rectanglesLTRB": parsed,
            "pixels": region_count, "differentPixels": changed_count,
            "differencePercent": 100 * changed_count / region_count if region_count else None,
            "mismatchBoundsLTRB": _box(difference & mask)}
    # Fixed integer BT.709 weights in BGR order. These explain brightness only.
    weights = np.array([18, 183, 54], dtype=np.int32)
    luma_old = (old[:, :, :3].astype(np.int32) * weights).sum(axis=2)
    luma_new = (new[:, :, :3].astype(np.int32) * weights).sum(axis=2)
    result["luminance"] = {"differentPixels": int(np.count_nonzero(luma_old != luma_new)),
        "meanSignedDifference": float((luma_new - luma_old).mean() / 255),
        "meanAbsoluteDifference": float(np.abs(luma_new - luma_old).mean() / 255),
        "scope": "BT.709-like integer weights on encoded BGR; not calibrated physical luminance"}
    signed_rgb = new[:, :, :3].astype(np.int16) - old[:, :, :3].astype(np.int16)
    neutral_shift = (signed_rgb[:, :, 0] == signed_rgb[:, :, 1]) & (
        signed_rgb[:, :, 1] == signed_rgb[:, :, 2]) & rgb_difference
    result["colorDifference"] = {
        "neutralBrightnessShiftPixels": int(neutral_shift.sum()),
        "chromaticChangePixels": int(np.count_nonzero(rgb_difference & ~neutral_shift)),
        "equalEncodedLuminanceChangedColorPixels": int(np.count_nonzero(
            rgb_difference & (luma_old == luma_new))),
        "meanSignedChannelDifferenceBGR": signed_rgb.mean(axis=(0, 1)).tolist(),
        "scope": "Equal B/G/R code-value shifts identify neutral brightness changes; no color-space cause inferred"}
    values = np.arange(256, dtype=np.float64) / 255
    linear = np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)
    encoded = np.where(values <= 0.0031308, values * 12.92, 1.055 * values ** (1 / 2.4) - 0.055)
    linear_lut, encoded_lut = np.rint(linear * 255).astype(np.uint8), np.rint(encoded * 255).astype(np.uint8)
    result["colorSpaceHypotheses"] = {
        "beforeSRGBDecodedToLinear": _score(linear_lut[old[:, :, :3]], new[:, :, :3]),
        "beforeLinearEncodedToSRGB": _score(encoded_lut[old[:, :, :3]], new[:, :, :3]),
        "beforeRedBlueSwapped": _score(old[:, :, 2::-1], new[:, :, :3]),
        "scope": "Whole-crop BGR transfer/swizzle hypotheses only; no tolerance or qualification change"}
    def edges(array):
        rgb = array[:, :, :3].astype(np.int16)
        mask = np.zeros((height, width), dtype=bool)
        mask[:, 1:] |= np.max(np.abs(rgb[:, 1:] - rgb[:, :-1]), axis=2) >= 4
        mask[1:] |= np.max(np.abs(rgb[1:] - rgb[:-1]), axis=2) >= 4
        return mask
    edge_old, edge_new = edges(old), edges(new)
    result["geometryEdges"] = {"thresholdChannelDifference": 4,
        "beforeEdgePixels": int(edge_old.sum()), "afterEdgePixels": int(edge_new.sum()),
        "differentEdgePixels": int(np.count_nonzero(edge_old != edge_new)),
        "scope": "Color-gradient occupancy only; exact color comparison remains the gate"}
    def gradient_summary(array):
        rgb = array[:, :, :3].astype(np.int16)
        horizontal, vertical = np.abs(np.diff(rgb, axis=1)), np.abs(np.diff(rgb, axis=0))
        return {"meanHorizontalNeighborDifference": float(horizontal.mean()) if horizontal.size else 0.0,
            "meanVerticalNeighborDifference": float(vertical.mean()) if vertical.size else 0.0}
    result["sharpnessProxy"] = {"before": gradient_summary(old), "after": gradient_summary(new),
        "scope": "Mean adjacent encoded-BGR contrast; a brightness-invariant proxy, not a calibrated sharpness metric"}
    result["constantOffsetSearch"] = _search_offset(old, new, offset_radius)
    result["scaleSearch"] = _search_scale(old, new, scales)
    result["staleFrameComparisons"] = {}
    for name, previous in (stale_frames or {}).items():
        previous = _pixels(previous)
        result["staleFrameComparisons"][name] = _score(previous, new) if previous.shape == new.shape else {"reason": "different extents"}
    return result


class _FrameInfoProxy:
    """Retain supported DXGI acquisition metadata without patching DXCAM files.

    DXCAM 0.3.0 merges desktop and pointer QPC values in latest_frame_ticks.
    Intercept only its public COM AcquireNextFrame call to retain the original
    returned DXGI_OUTDUPL_FRAME_INFO; every other COM operation is forwarded.
    The installed private object path is explicit and version-sensitive.
    """
    _session_counter = 0

    def __init__(self, delegate):
        type(self)._session_counter += 1
        self.session_generation = type(self)._session_counter
        self.observation_started = time.perf_counter()
        self.delegate = delegate
        self.sequence = 0
        self.info = None

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def AcquireNextFrame(self, timeout, frame_info, resource):
        result = self.delegate.AcquireNextFrame(timeout, frame_info, resource)
        # Exceptions leave the delivery sequence unchanged (including timeout).
        self.sequence += 1
        info = getattr(frame_info, "_obj", None)
        if info is None:
            info = getattr(frame_info, "contents", None)
        self.info = {"lastPresentQpcTicks": int(info.LastPresentTime),
            "lastMouseUpdateQpcTicks": int(info.LastMouseUpdateTime),
            "accumulatedFrames": int(info.AccumulatedFrames)} if info is not None else None
        return result


def _frame_info_observer(camera):
    duplicator = getattr(camera, "_duplicator", None)
    delegate = getattr(duplicator, "duplicator", None)
    if delegate is None:
        return None
    if not isinstance(delegate, _FrameInfoProxy):
        delegate = _FrameInfoProxy(delegate)
        duplicator.duplicator = delegate
    return delegate


def grab_observed(camera, rectangle):
    """One fresh acquisition attempt, owned array, exact call/desktop clocks.

    None means no new frame, never a silently reused crop. Callers schedule
    retries asynchronously; this helper does not sleep or hold endpoints.
    dxcam 0.3.0 one-shot timestamps live on its duplicator, not ring buffer.
    """
    x, y, width, height = _physical_rectangle(rectangle,
        label="Physical acquisition rectangle", positive_extent=True)
    if getattr(camera, "is_capturing", False):
        raise ValueError("Fresh one-shot evidence requires a camera without ring-buffer capture")
    output = getattr(camera, "_output", None)
    output_desc = getattr(output, "desc", None)
    desktop = getattr(output_desc, "DesktopCoordinates", None)
    output_origin = [int(desktop.left), int(desktop.top)] if desktop is not None else [0, 0]
    local = [x - output_origin[0], y - output_origin[1],
             x + width - output_origin[0], y + height - output_origin[1]]
    camera_width, camera_height = getattr(camera, "width", None), getattr(camera, "height", None)
    if camera_width is not None and camera_height is not None and not (
            0 <= local[0] < local[2] <= camera_width and 0 <= local[1] < local[3] <= camera_height):
        raise ValueError("Physical acquisition rectangle exceeds selected DXGI output")
    info_observer = _frame_info_observer(camera)
    previous_sequence = info_observer.sequence if info_observer is not None else None
    started = time.perf_counter()
    pixels = camera.grab(region=tuple(local), copy=True, new_frame_only=True)
    finished = time.perf_counter()
    duplicator = getattr(camera, "_duplicator", None)
    ticks = getattr(duplicator, "latest_frame_ticks", None)
    frequency = getattr(duplicator, "performance_frequency", None)
    delivered = info_observer is not None and info_observer.sequence != previous_sequence
    frame_info = info_observer.info if delivered else None
    present_ticks = frame_info["lastPresentQpcTicks"] if frame_info else None
    mouse_ticks = frame_info["lastMouseUpdateQpcTicks"] if frame_info else None
    observation = {"callStarted": started, "callFinished": finished,
        "rectangleXYWH": [x, y, width, height], "freshAcquisition": pixels is not None,
        "outputLocalRegionLTRB": local,
        "outputDesktopXYWH": [*output_origin, camera_width, camera_height],
        "cacheFallbackAllowed": False, "desktopFrameQpcTicks": present_ticks,
        "qpcFrequency": frequency,
        "desktopFrameSeconds": present_ticks / frequency if present_ticks and frequency else None,
        "acquisitionFrameQpcTicks": ticks,
        "lastMouseUpdateQpcTicks": mouse_ticks,
        "desktopPixelsUpdated": present_ticks > 0 if present_ticks is not None else None,
        "pointerOnlyFrame": present_ticks == 0 and mouse_ticks > 0 if frame_info else None,
        "acquisitionSequence": info_observer.sequence if info_observer is not None else None,
        "acquisitionSessionGeneration": info_observer.session_generation if info_observer is not None else None,
        "frameInfoObservationStarted": info_observer.observation_started if info_observer is not None else None,
        "newDeliveryObserved": delivered,
        "timestampEvidence": "DXGI_OUTDUPL_FRAME_INFO.LastPresentTime" if frame_info else "unavailable",
        "accumulatedFrames": getattr(duplicator, "accumulated_frames", None),
        "outputSize": [getattr(camera, "width", None), getattr(camera, "height", None)],
        "rotationDegrees": getattr(camera, "rotation_angle", None),
        "scope": "Supported DXGI acquisition/raster QPC via process-local version-sensitive proxy; not physical scanout or native frame identity"}
    if pixels is not None:
        pixels = _pixels(pixels)
        if pixels.shape[:2] != (height, width):
            raise ValueError("Acquired pixel extent differs from requested physical rectangle")
    return pixels.copy() if pixels is not None else None, observation


def window_observation(hwnd):
    """Observe physical Win32 state without reading titles or foreign content."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
    handle = wintypes.HWND(int(hwnd))
    for name in ("GetWindowRect", "GetClientRect"):
        getattr(user, name).argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user.GetForegroundWindow.restype = wintypes.HWND
    for name in ("IsWindowVisible", "IsIconic", "IsZoomed", "IsWindowEnabled"):
        getattr(user, name).argtypes = [wintypes.HWND]
        getattr(user, name).restype = wintypes.BOOL
    user.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetWindow.restype = wintypes.HWND
    user.GetDpiForWindow.argtypes = [wintypes.HWND]
    user.GetDpiForWindow.restype = wintypes.UINT
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user.MonitorFromWindow.restype = wintypes.HANDLE
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    def rect_value(rect):
        return [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top]
    outer, inner, origin = wintypes.RECT(), wintypes.RECT(), wintypes.POINT()
    if not user.GetWindowRect(handle, ctypes.byref(outer)) or not user.GetClientRect(handle, ctypes.byref(inner)) or not user.ClientToScreen(handle, ctypes.byref(origin)):
        raise ctypes.WinError(ctypes.get_last_error())
    extent, cloaked = wintypes.RECT(), wintypes.DWORD()
    extent_hr = dwm.DwmGetWindowAttribute(handle, 9, ctypes.byref(extent), ctypes.sizeof(extent))
    cloak_hr = dwm.DwmGetWindowAttribute(handle, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(info)
    user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    monitor_ok = user.GetMonitorInfoW(user.MonitorFromWindow(handle, 2), ctypes.byref(info))
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    class_name = ctypes.create_unicode_buffer(256)
    user.GetClassNameW(handle, class_name, len(class_name))
    exstyle = user.GetWindowLongPtrW(handle, -20) & 0xffffffff
    style = user.GetWindowLongPtrW(handle, -16) & 0xffffffff
    color, alpha, flags = wintypes.DWORD(), ctypes.c_ubyte(), wintypes.DWORD()
    user.GetLayeredWindowAttributes.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(wintypes.DWORD)]
    alpha_ok = user.GetLayeredWindowAttributes(handle, ctypes.byref(color), ctypes.byref(alpha), ctypes.byref(flags))
    above = user.GetWindow(handle, 3)  # GW_HWNDPREV; stacking, not hit testing.
    rank, current = 0, above
    while current and rank < 4096:
        rank += 1
        current = user.GetWindow(current, 3)
    user.GetWindowRgnBox.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    region = wintypes.RECT()
    region_kind = user.GetWindowRgnBox(handle, ctypes.byref(region))
    dpi = int(user.GetDpiForWindow(handle))
    pointer = wintypes.POINT()
    user.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    pointer_ok = user.GetCursorPos(ctypes.byref(pointer))
    process_id = wintypes.DWORD()
    user.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
    iconic, zoomed = bool(user.IsIconic(handle)), bool(user.IsZoomed(handle))
    return {"t": time.perf_counter(), "hwnd": int(hwnd), "className": class_name.value,
        "processId": int(process_id.value),
        "windowXYWH": rect_value(outer), "clientXYWH": [origin.x, origin.y, inner.right, inner.bottom],
        "clientOffsetInWindowXY": [origin.x - outer.left, origin.y - outer.top],
        "extendedFrameXYWH": rect_value(extent) if extent_hr == 0 else None,
        "cloaked": int(cloaked.value) if cloak_hr == 0 else None,
        "visible": bool(user.IsWindowVisible(handle)), "iconic": iconic, "nativeMaximized": zoomed,
        "nativeWindowState": "minimized" if iconic else "maximized" if zoomed else "normal",
        "nativeInputEnabled": bool(user.IsWindowEnabled(handle)),
        "foreground": user.GetForegroundWindow() == int(hwnd),
        "foregroundHwnd": int(user.GetForegroundWindow() or 0), "dpi": dpi, "scale": dpi / 96,
        "cursorPositionXY": [pointer.x, pointer.y] if pointer_ok else None,
        "windowStyle": hex(style), "extendedStyle": hex(exstyle), "topmost": bool(exstyle & 8),
        "layered": bool(exstyle & 0x80000), "layeredAlpha": int(alpha.value) if alpha_ok else None,
        "layeredAttributeFlags": int(flags.value) if alpha_ok else None,
        "windowRegionType": region_kind, "windowRegionBoundsXYWH": rect_value(region) if region_kind > 0 else None,
        "previousHwnd": int(above or 0), "topLevelZRank": rank,
        "monitorXYWH": rect_value(info.rcMonitor) if monitor_ok else None,
        "workAreaXYWH": rect_value(info.rcWork) if monitor_ok else None,
        "scope": "Win32 metadata; extent/region do not identify visible composition pixels or shadow opacity"}


def composition_windows():
    """Find only the diagnostic native hosts; never retains window titles."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    hosts = []
    @callback_type
    def callback(hwnd, _):
        name = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(hwnd, name, len(name))
        if name.value == "CSPMExperimentalDirectCompositionShader":
            hosts.append(window_observation(int(hwnd)))
        return True
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    if not user.EnumWindows(callback, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return hosts


def composition_probe_coordinates(live, overlap, native, regions, corner_radius_px):
    """Choose at most 64 source texels in recorded corners/margins only.

    Interior private content is never sampled. Changed coordinates explain a
    failure; the complete array comparison remains the qualification gate.
    """
    live, overlap, native = map(_pixels, (live, overlap, native))
    if live.shape != overlap.shape or live.shape != native.shape:
        raise ValueError("Composition controls require matching complete client arrays")
    if not isinstance(corner_radius_px, int) or not 0 <= corner_radius_px <= 128:
        raise ValueError("Measured corner radius must be an integer from 0 to 128")
    content = [box for name in ("header", "clientBody", "border") for box in regions.get(name, [])]
    if not content:
        raise ValueError("Composition controls require observed content regions")
    left, top = min(box[0] for box in content), min(box[1] for box in content)
    right, bottom = max(box[2] for box in content), max(box[3] for box in content)
    radius = min(corner_radius_px + 1, (right-left)//2, (bottom-top)//2)
    zones = {"cornerTL": [[left, top, left+radius, top+radius]],
        "cornerTR": [[right-radius, top, right, top+radius]],
        "cornerBL": [[left, bottom-radius, left+radius, bottom]],
        "cornerBR": [[right-radius, bottom-radius, right, bottom]],
        "clientMargin": regions.get("shadowAndMargin", [])}
    changed = np.any(live != overlap, axis=2) | np.any(live != native, axis=2)
    coordinates, labels, summaries = [], [], {}
    height, width = live.shape[:2]
    for label, boxes in zones.items():
        mask = np.zeros((height, width), dtype=bool)
        for box in boxes:
            x0, y0, x1, y1 = _physical_rectangle(box, label="Composition probe region")
            if not 0 <= x0 <= x1 <= width or not 0 <= y0 <= y1 <= height:
                raise ValueError("Composition probe region exceeds complete client")
            mask[y0:y1, x0:x1] = True
        yy, xx = np.nonzero(changed & mask)
        available = list(zip(xx.tolist(), yy.tolist()))
        budget = 24 if label == "clientMargin" else 4
        selected = [available[index] for index in np.unique(np.linspace(
            0, len(available)-1, min(budget, len(available))).astype(int))] if available else []
        # Keep curved-edge controls when equality leaves no changed pixels to
        # select. Reflect four radius-relative fringe locations at each corner;
        # these are diagnostic samples, never an equality mask.
        fringe = []
        curved_radius = min(corner_radius_px, radius-1)
        if label != "clientMargin" and curved_radius > 1:
            diagonal = max(1, round((1-np.sqrt(.5))*curved_radius))
            offsets = [(0, max(0, curved_radius-2)),
                       (max(0, curved_radius-2), 0),
                       (diagonal-1, diagonal), (diagonal, diagonal-1)]
            for dx, dy in offsets:
                fringe.append((left+dx if label.endswith("L") else right-1-dx,
                    top+dy if label.startswith("cornerT") else bottom-1-dy))
        # Four location controls per corner and eight fixed margin controls.
        guards = []
        for x0, y0, x1, y1 in boxes:
            if x0 < x1 and y0 < y1:
                guards.extend(((x0, y0), (x1-1, y0), (x0, y1-1), (x1-1, y1-1)))
        if label == "clientMargin":
            guards = guards[:8]
        selected = list(dict.fromkeys(selected + fringe + guards))
        if label != "clientMargin":
            selected = selected[:8]
        sampled_changed = sum(bool(changed[y, x]) for x, y in selected)
        summaries[label] = {"rectanglesLTRB": boxes, "differentPixels": len(available),
            "sampledChangedPixels": sampled_changed,
            "unsampledChangedPixels": len(available)-sampled_changed, "sampleCount": len(selected)}
        coordinates.extend(selected)
        labels.extend([label] * len(selected))
    if not coordinates or len(coordinates) > 64:
        raise ValueError("Composition probe requires between 1 and 64 bounded texels")
    return coordinates, labels, summaries


def probe_gpu_composition(dll, host, coordinates):
    """Return tiny diagnostic-only GPU samples in RAM, never presentation input."""
    if not host or not hasattr(dll, "cspm_comp_probe_pixels"):
        raise RuntimeError("Stopped-clock GPU composition probe is unavailable")
    if not 1 <= len(coordinates) <= 64:
        raise ValueError("GPU composition probe requires 1 to 64 texels")
    parsed = []
    for coordinate in coordinates:
        if len(coordinate) != 2 or any(not isinstance(v, int) or isinstance(v, bool)
                                     or v < 0 or v > 2147483647 for v in coordinate):
            raise ValueError("GPU probe coordinates must be nonnegative integer texels")
        parsed.extend(coordinate)
    xy = (ctypes.c_int * len(parsed))(*parsed)
    source = (ctypes.c_ubyte * (len(coordinates)*4))()
    submitted = (ctypes.c_ubyte * (len(coordinates)*4))()
    function = dll.cspm_comp_probe_pixels
    function.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_uint,
                        ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte)]
    function.restype = ctypes.c_int
    if not function(host, xy, len(coordinates), source, submitted):
        raise RuntimeError("Stopped-clock GPU composition probe rejected bounded texels")
    return (np.ctypeslib.as_array(source).reshape(-1, 4).copy(),
            np.ctypeslib.as_array(submitted).reshape(-1, 4).copy())


def composition_analysis(live, overlap, native, backdrop, coordinates, labels,
                         source_bgra, submitted_bgra, region_membership=None, *, single_owner=False):
    """Sanitized causal models; no raw samples escape or relax exact equality."""
    live, overlap, native, backdrop = map(_pixels, (live, overlap, native, backdrop))
    if any(array.shape != live.shape for array in (overlap, native, backdrop)):
        raise ValueError("Composition arrays require the same complete client extent")
    source, submitted = np.asarray(source_bgra), np.asarray(submitted_bgra)
    if (source.dtype != np.uint8 or submitted.dtype != np.uint8
            or source.shape != (len(coordinates), 4) or submitted.shape != source.shape
            or len(labels) != len(coordinates) or not 1 <= len(coordinates) <= 64):
        raise ValueError("Composition samples require 1 to 64 matching BGRA texels")
    xy = np.asarray(coordinates)
    if xy.shape != (len(coordinates), 2) or not np.issubdtype(xy.dtype, np.integer):
        raise ValueError("Composition sample coordinates must be integer XY texels")
    if np.any(xy < 0) or np.any(xy[:, 0] >= live.shape[1]) or np.any(xy[:, 1] >= live.shape[0]):
        raise ValueError("Composition samples exceed the complete client extent")
    x, y = xy[:, 0], xy[:, 1]
    l, o, n, b = [array[y, x, :3].astype(np.float64) for array in (live, overlap, native, backdrop)]
    s, p = source[:, :3].astype(np.float64), submitted[:, :3].astype(np.float64)
    sa, pa = source[:, 3:4].astype(np.float64)/255, submitted[:, 3:4].astype(np.float64)/255
    def score(predicted, observed):
        predicted = np.clip(np.rint(predicted), 0, 255)
        delta = np.abs(predicted-observed)
        return {"differentSamples": int(np.any(delta != 0, axis=1).sum()),
            "maxChannelDifference": float(delta.max()), "meanChannelDifference": float(delta.mean())}
    def decode(encoded):
        value = encoded/255
        return np.where(value <= .04045, value/12.92, ((value+.055)/1.055)**2.4)
    def encode(linear):
        value = np.clip(linear, 0, 1)
        return 255*np.where(value <= .0031308, value*12.92, 1.055*value**(1/2.4)-.055)
    straight = np.divide(p, pa, out=np.zeros_like(p), where=pa != 0)
    linear_native = encode(decode(straight)*pa + (1-pa)*decode(b))
    masked_live = s+(1-sa)*b
    membership = (region_membership or {}).get("included")
    if membership is not None:
        if len(membership) != len(coordinates) or any(type(value) is not bool for value in membership):
            raise ValueError("Region membership must match every sampled texel")
        masked_live = np.where(np.asarray(membership)[:, None], masked_live, b)
    result = {"sampleCount": len(coordinates),
        "ownershipMode": "single-owner transfer" if single_owner else "live/native overlap",
        "sourceSubmittedDifferentSamples": int(np.any(source != submitted, axis=1).sum()),
        "sourceAlphaHistogram": np.bincount(source[:, 3], minlength=256).tolist(),
        "submittedAlphaHistogram": np.bincount(submitted[:, 3], minlength=256).tolist(),
        "sourcePremultipliedViolations": int(np.any(s > source[:, 3:4], axis=1).sum()),
        "submittedPremultipliedViolations": int(np.any(p > submitted[:, 3:4], axis=1).sum()),
        "models": {"sourcePremultipliedOverBackdropToLive": score(s+(1-sa)*b, l),
            "sourcePremultipliedWithNativeRegionToLive": score(masked_live, l),
            "submittedPremultipliedOverBackdropToNative": score(p+(1-pa)*b, n),
            "submittedPremultipliedOverLiveToOverlap": score(p+(1-pa)*l, o),
            "submittedPremultipliedOverBackdropToTransfer": score(p+(1-pa)*b, o),
            "submittedStraightAlphaOverBackdropToNative": score(p*pa+(1-pa)*b, n),
            "submittedSRGBLinearCompositionToNative": score(linear_native, n)},
        "regions": {}, "regionMembership": region_membership,
        "scope": "Stopped-clock diagnostic texel readback and encoded-BGR composition hypotheses; no raw colors retained; complete-client equality is independent"}
    for label in sorted(set(labels)):
        selected = np.array([value == label for value in labels])
        result["regions"][label] = {"sampleCount": int(selected.sum()),
            "sourcePartialAlphaSamples": int(np.count_nonzero((source[selected, 3] > 0) & (source[selected, 3] < 255))),
            "sourceAlphaRange": [int(source[selected, 3].min()), int(source[selected, 3].max())],
            "sourceChannelMeansBGRA": source[selected].mean(axis=0).tolist(),
            "submittedChannelMeansBGRA": submitted[selected].mean(axis=0).tolist(),
            "liveOverlapDifferentSamples": int(np.any(l[selected] != o[selected], axis=1).sum()),
            "liveNativeDifferentSamples": int(np.any(l[selected] != n[selected], axis=1).sum()),
            "nativeBackdropDifferentSamples": int(np.any(n[selected] != b[selected], axis=1).sum()),
            "sourceSubmittedDifferentSamples": int(np.any(source[selected] != submitted[selected], axis=1).sum()),
            "singleLayerNativeModel": score((p+(1-pa)*b)[selected], n[selected]),
            "doubleLayerOverlapModel": score((p+(1-pa)*l)[selected], o[selected])}
    return result


def window_region_membership(hwnd, coordinates):
    """Measure the live native region at bounded client-local sample points."""
    if not 1 <= len(coordinates) <= 64:
        raise ValueError("Region membership requires 1 to 64 bounded points")
    state = window_observation(hwnd)
    user, gdi = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("gdi32", use_last_error=True)
    gdi.CreateRectRgn.argtypes, gdi.CreateRectRgn.restype = [ctypes.c_int]*4, wintypes.HANDLE
    user.GetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE]
    gdi.PtInRegion.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_int]
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    region = gdi.CreateRectRgn(0, 0, 0, 0)
    if not region:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        kind = user.GetWindowRgn(hwnd, region)
        ox, oy = state["clientOffsetInWindowXY"]
        values = [bool(gdi.PtInRegion(region, x+ox, y+oy)) for x, y in coordinates] if kind else None
        return {"nativeRegionType": kind, "included": values,
            "scope": "Live HWND region membership at sampled client-local texels; default region unspecified"}
    finally:
        gdi.DeleteObject(region)


class ControlledBackdrop:
    """Task-owned opaque Win32 source-control background, with native WndProc."""
    bgra = (83, 61, 37, 255)

    def __init__(self, rectangle, behind_hwnd):
        x, y, width, height = _physical_rectangle(rectangle, label="Controlled backdrop", positive_extent=True)
        self.hwnd = None
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = [wintypes.LPCWSTR], wintypes.HINSTANCE
        self.instance = kernel.GetModuleHandleW(None)
        self.class_name = "CSPMControlledBackdrop_" + str(os.getpid()) + "_" + str(id(self))
        class WNDCLASS(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]
        self.gdi.CreateSolidBrush.argtypes, self.gdi.CreateSolidBrush.restype = [wintypes.DWORD], wintypes.HANDLE
        self.gdi.DeleteObject.argtypes = [wintypes.HANDLE]
        self.user.RegisterClassW.argtypes, self.user.RegisterClassW.restype = [ctypes.POINTER(WNDCLASS)], wintypes.ATOM
        self.user.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        self.user.DestroyWindow.argtypes = [wintypes.HWND]
        self.user.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
            wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
        self.user.CreateWindowExW.restype = wintypes.HWND
        self.user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.HANDLE, wintypes.UINT]
        blue, green, red, _ = self.bgra
        self.brush = self.gdi.CreateSolidBrush(red | green << 8 | blue << 16)
        self.registered = False
        try:
            if not self.brush:
                raise ctypes.WinError(ctypes.get_last_error())
            definition = WNDCLASS(lpfnWndProc=ctypes.cast(self.user.DefWindowProcW, ctypes.c_void_p).value,
                hInstance=self.instance, hbrBackground=self.brush, lpszClassName=self.class_name)
            if not self.user.RegisterClassW(ctypes.byref(definition)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.registered = True
            # No activation, taskbar presence or input ownership. No user data.
            self.hwnd = self.user.CreateWindowExW(0x080000A8, self.class_name, "", 0x80000000,
                x, y, width, height, None, None, self.instance, None)
            if not self.hwnd or not self.user.SetWindowPos(self.hwnd, behind_hwnd, x, y, width, height, 0x50):
                raise ctypes.WinError(ctypes.get_last_error())
            if not self.user.RedrawWindow(self.hwnd, None, None, 0x185):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise

    def close(self):
        if self.hwnd:
            if not self.user.DestroyWindow(self.hwnd):
                raise ctypes.WinError(ctypes.get_last_error())
            self.hwnd = None
        if self.registered:
            if not self.user.UnregisterClassW(self.class_name, self.instance):
                raise ctypes.WinError(ctypes.get_last_error())
            self.registered = False
        if self.brush:
            self.gdi.DeleteObject(self.brush)
            self.brush = None


def _endpoint_probe_coordinates(coordinates):
    """Validate bounded native adapter arguments before invoking any GPU API."""
    if not 1 <= len(coordinates) <= 64:
        raise ValueError("Endpoint GPU probe requires 1 to 64 texels")
    parsed = []
    for coordinate in coordinates:
        if len(coordinate) != 2 or any(not isinstance(v, int) or isinstance(v, bool)
                                     or v < 0 or v > 2147483647 for v in coordinate):
            raise ValueError("Endpoint GPU probe coordinates must be nonnegative integer texels")
        parsed.extend(coordinate)
    return (ctypes.c_int * len(parsed))(*parsed)


def probe_gpu_endpoint_composition(dll, host, coordinates):
    """Owned target/submitted BGRA samples, only at a stopped native endpoint."""
    if not host or not hasattr(dll, "cspm_comp_probe_endpoint_pixels"):
        raise RuntimeError("Stopped-clock endpoint composition probe is unavailable")
    xy = _endpoint_probe_coordinates(coordinates)
    target = (ctypes.c_ubyte * (len(coordinates)*4))()
    submitted = (ctypes.c_ubyte * (len(coordinates)*4))()
    function = dll.cspm_comp_probe_endpoint_pixels
    function.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_uint,
                        ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte)]
    function.restype = ctypes.c_int
    if not function(host, xy, len(coordinates), target, submitted):
        raise RuntimeError("Stopped-clock endpoint composition probe rejected bounded texels")
    return (np.ctypeslib.as_array(target).reshape(-1, 4).copy(),
            np.ctypeslib.as_array(submitted).reshape(-1, 4).copy())


def probe_gpu_live_frame(dll, host, frame, coordinates):
    """Read a separate immutable live export; it never becomes a target frame."""
    if not host or not frame or not hasattr(dll, "cspm_comp_probe_frame_pixels"):
        raise RuntimeError("Stopped-clock immutable live-frame probe is unavailable")
    xy = _endpoint_probe_coordinates(coordinates)
    samples = (ctypes.c_ubyte * (len(coordinates)*4))()
    function = dll.cspm_comp_probe_frame_pixels
    function.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                        ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte)]
    function.restype = ctypes.c_int
    if not function(host, frame, xy, len(coordinates), samples):
        raise RuntimeError("Stopped-clock immutable live-frame probe rejected bounded texels")
    return np.ctypeslib.as_array(samples).reshape(-1, 4).copy()


def endpoint_composition_analysis(endpoint_desktop, live_desktop, coordinates, labels,
                                  target_bgra, submitted_bgra, live_bgra=None, *,
                                  backdrop_before=None, backdrop_after=None):
    """Bounded texture/backdrop explanations, independent of full-client equality.

    Coordinates/raw samples stay in RAM. Alpha histograms and exact identities
    describe the sampled pixels only; zero-alpha controls at other locations
    cannot explain an unsampled failure. No model changes a failing comparison.
    """
    endpoint, live = map(_pixels, (endpoint_desktop, live_desktop))
    if endpoint.shape != live.shape:
        raise ValueError("Endpoint diagnosis requires matching complete client arrays")
    _endpoint_probe_coordinates(coordinates)
    if len(labels) != len(coordinates) or any(not isinstance(label, str) for label in labels):
        raise ValueError("Endpoint labels must match every sampled texel")
    xy = np.asarray(coordinates)
    x, y = xy[:, 0], xy[:, 1]
    if np.any(x >= endpoint.shape[1]) or np.any(y >= endpoint.shape[0]):
        raise ValueError("Endpoint samples exceed the complete client extent")
    def texels(value):
        array = np.asarray(value)
        if array.dtype != np.uint8 or array.shape != (len(coordinates), 4):
            raise ValueError("Endpoint GPU samples require matching uint8 BGRA texels")
        return array
    textures = {"target": texels(target_bgra), "submitted": texels(submitted_bgra)}
    if live_bgra is not None:
        textures["live"] = texels(live_bgra)
    if (backdrop_before is None) != (backdrop_after is None):
        raise ValueError("Backdrop diagnosis requires both before and after observations")
    backdrops = None
    if backdrop_before is not None:
        backdrops = list(map(_pixels, (backdrop_before, backdrop_after)))
        if any(array.shape != endpoint.shape for array in backdrops):
            raise ValueError("Backdrop observations require the complete endpoint client extent")
    endpoint_rgb, live_rgb = endpoint[y, x, :3], live[y, x, :3]
    desktop_changed = np.any(endpoint_rgb != live_rgb, axis=1)
    def different(first, second):
        return np.any(first != second, axis=1)
    def texture_summary(array):
        alpha = array[:, 3]
        return {"sampleCount": len(array), "alphaHistogram": np.bincount(alpha, minlength=256).tolist(),
            "zeroAlphaSamples": int(np.count_nonzero(alpha == 0)),
            "opaqueSamples": int(np.count_nonzero(alpha == 255)),
            "partialAlphaSamples": int(np.count_nonzero((alpha > 0) & (alpha < 255))),
            "zeroAlphaNonzeroColorSamples": int(np.count_nonzero((alpha == 0) & np.any(array[:, :3] != 0, axis=1))),
            "premultipliedViolationSamples": int(np.count_nonzero(np.any(array[:, :3] > alpha[:, None], axis=1)))}
    def score(predicted, observed):
        predicted = np.clip(np.rint(predicted), 0, 255)
        delta = np.abs(predicted-observed.astype(np.float64))
        return {"differentSamples": int(np.count_nonzero(np.any(delta != 0, axis=1))),
            "maxChannelDifference": float(delta.max()), "meanChannelDifference": float(delta.mean())}
    def compose(samples, background):
        alpha = samples[:, 3:4].astype(np.float64)/255
        return samples[:, :3].astype(np.float64)+(1-alpha)*background.astype(np.float64)
    result = {"sampleCount": len(coordinates),
        "desktopDifferentSamples": int(desktop_changed.sum()),
        "targetSubmittedDifferentSamples": int(different(textures["target"], textures["submitted"]).sum()),
        "textures": {name: texture_summary(array) for name, array in textures.items()},
        "regions": {}, "models": {},
        "scope": "Stopped endpoint target/submitted and separately exported live-frame texels; optional independent fresh backdrop observations. Encoded-BGR premultiplied hypotheses only; no raw coordinates/colors retained. Complete-client exact equality remains the gate."}
    target_live_changed = None
    if "live" in textures:
        target_live_changed = different(textures["target"], textures["live"])
        transparent = np.all(textures["target"] == 0, axis=1) & np.all(textures["live"] == 0, axis=1)
        result.update(targetLiveDifferentSamples=int(target_live_changed.sum()),
            unchangedTargetLiveButDesktopDifferentSamples=int(np.count_nonzero(~target_live_changed & desktop_changed)),
            transparentTargetLiveButDesktopDifferentSamples=int(np.count_nonzero(transparent & desktop_changed)),
            transparentTargetSubmittedLiveButDesktopDifferentSamples=int(np.count_nonzero(
                transparent & np.all(textures["submitted"] == 0, axis=1) & desktop_changed)))
    if backdrops is not None:
        before_rgb, after_rgb = [array[y, x, :3] for array in backdrops]
        backdrop_changed = different(before_rgb, after_rgb)
        result["backdropDifferentSamples"] = int(backdrop_changed.sum())
        result["backdropChangedWhereDesktopDifferentSamples"] = int(np.count_nonzero(backdrop_changed & desktop_changed))
        result["models"].update(
            targetPremultipliedOverBeforeBackdropToEndpoint=score(compose(textures["target"], before_rgb), endpoint_rgb),
            submittedPremultipliedOverBeforeBackdropToEndpoint=score(compose(textures["submitted"], before_rgb), endpoint_rgb),
            targetPremultipliedOverAfterBackdropToLive=score(compose(textures["target"], after_rgb), live_rgb))
        if "live" in textures:
            result["models"]["livePremultipliedOverAfterBackdropToLive"] = score(compose(textures["live"], after_rgb), live_rgb)
    for label in sorted(set(labels)):
        selected = np.asarray([value == label for value in labels])
        region = {"sampleCount": int(selected.sum()),
            "desktopDifferentSamples": int(desktop_changed[selected].sum()),
            "textures": {name: texture_summary(array[selected]) for name, array in textures.items()}}
        if target_live_changed is not None:
            region["targetLiveDifferentSamples"] = int(target_live_changed[selected].sum())
        result["regions"][label] = region
    return result
