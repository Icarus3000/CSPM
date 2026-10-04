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
