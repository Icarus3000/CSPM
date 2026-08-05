from __future__ import annotations

import re
from typing import Any, Dict, Tuple


_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
_SAFE_LIGHT_TEXT = "#F7F9FC"
_SAFE_DARK_TEXT = "#0B0D10"
_SEMANTIC_SUCCESS = "#2DB67C"
_SEMANTIC_WARNING = "#E8B03B"
_SEMANTIC_ERROR = "#D95763"
_SEMANTIC_DANGER = "#F0626E"


def _normalize_hex(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not _HEX_RE.fullmatch(text):
        return fallback
    if not text.startswith("#"):
        text = "#" + text
    return text.upper()


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    normalized = _normalize_hex(hex_color, "#000000")
    return (
        int(normalized[1:3], 16) / 255.0,
        int(normalized[3:5], 16) / 255.0,
        int(normalized[5:7], 16) / 255.0,
    )


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, round(rgb[0] * 255))),
        max(0, min(255, round(rgb[1] * 255))),
        max(0, min(255, round(rgb[2] * 255))),
    )


def _mix_rgb(
    left: Tuple[float, float, float],
    right: Tuple[float, float, float],
    amount: float,
) -> Tuple[float, float, float]:
    t = max(0.0, min(1.0, float(amount)))
    return (
        (left[0] * (1.0 - t)) + (right[0] * t),
        (left[1] * (1.0 - t)) + (right[1] * t),
        (left[2] * (1.0 - t)) + (right[2] * t),
    )


def _linearize(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    rgb = _hex_to_rgb(hex_color)
    linear = tuple(_linearize(channel) for channel in rgb)
    return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2])


def contrast_ratio(foreground: str, background: str) -> float:
    fg_luma = relative_luminance(foreground)
    bg_luma = relative_luminance(background)
    lighter = max(fg_luma, bg_luma)
    darker = min(fg_luma, bg_luma)
    return (lighter + 0.05) / (darker + 0.05)


def _best_ink(background: str, prefer_light: bool | None = None) -> str:
    light_ratio = contrast_ratio(_SAFE_LIGHT_TEXT, background)
    dark_ratio = contrast_ratio(_SAFE_DARK_TEXT, background)
    if prefer_light is True and light_ratio >= 4.5:
        return _SAFE_LIGHT_TEXT
    if prefer_light is False and dark_ratio >= 4.5:
        return _SAFE_DARK_TEXT
    return _SAFE_LIGHT_TEXT if light_ratio >= dark_ratio else _SAFE_DARK_TEXT


def _ensure_contrast(
    foreground: Any,
    background: str,
    min_ratio: float,
    prefer_light: bool | None = None,
) -> str:
    bg_hex = _normalize_hex(background, "#000000")
    fallback = _best_ink(bg_hex, prefer_light)
    fg_hex = _normalize_hex(foreground, fallback)
    if contrast_ratio(fg_hex, bg_hex) >= min_ratio:
        return fg_hex

    target_hex = _best_ink(bg_hex, prefer_light)
    if contrast_ratio(target_hex, bg_hex) < min_ratio:
        return target_hex

    source_rgb = _hex_to_rgb(fg_hex)
    target_rgb = _hex_to_rgb(target_hex)
    best = target_hex
    low = 0.0
    high = 1.0
    for _ in range(18):
        mid = (low + high) / 2.0
        candidate = _rgb_to_hex(_mix_rgb(source_rgb, target_rgb, mid))
        if contrast_ratio(candidate, bg_hex) >= min_ratio:
            best = candidate
            high = mid
        else:
            low = mid
    return best


def _ensure_contrast_multi(
    foreground: Any,
    backgrounds: Tuple[str, ...],
    min_ratio: float,
    prefer_light: bool | None = None,
) -> str:
    bg_list = tuple(_normalize_hex(bg, "#000000") for bg in backgrounds if bg)
    if not bg_list:
        return _normalize_hex(foreground, _SAFE_LIGHT_TEXT)

    fallback = _best_ink(bg_list[0], prefer_light)
    result = _normalize_hex(foreground, fallback)
    for _ in range(6):
        for background in bg_list:
            result = _ensure_contrast(result, background, min_ratio, prefer_light)
        if all(contrast_ratio(result, background) >= min_ratio for background in bg_list):
            return result

    light_min = min(contrast_ratio(_SAFE_LIGHT_TEXT, background) for background in bg_list)
    dark_min = min(contrast_ratio(_SAFE_DARK_TEXT, background) for background in bg_list)
    if prefer_light is True and light_min >= min_ratio:
        return _SAFE_LIGHT_TEXT
    if prefer_light is False and dark_min >= min_ratio:
        return _SAFE_DARK_TEXT
    return _SAFE_LIGHT_TEXT if light_min >= dark_min else _SAFE_DARK_TEXT


def sanitize_theme_palette(raw_theme: Dict[str, Any]) -> Dict[str, Any]:
    theme = dict(raw_theme or {})
    bg = _normalize_hex(theme.get("bg"), "#040405")
    panel = _normalize_hex(theme.get("panel"), bg)
    panel2 = _normalize_hex(theme.get("panel2"), panel)
    accent = _normalize_hex(theme.get("accent"), "#2979FF")
    hover = _normalize_hex(theme.get("hover"), panel2)
    glow = _normalize_hex(theme.get("glow"), accent)

    prefer_light_ink = relative_luminance(panel2) < 0.34
    text = _ensure_contrast_multi(theme.get("text"), (panel2, panel, bg), 4.8, prefer_light_ink)

    text_rgb = _hex_to_rgb(text)
    panel2_rgb = _hex_to_rgb(panel2)
    muted_seed = theme.get("muted")
    if contrast_ratio(_normalize_hex(muted_seed, "#000000"), panel2) < 3.6:
        muted_seed = _rgb_to_hex(_mix_rgb(text_rgb, panel2_rgb, 0.34))
    muted = _ensure_contrast_multi(muted_seed, (panel2, panel), 3.6, prefer_light_ink)

    subtle_seed = _rgb_to_hex(_mix_rgb(text_rgb, panel2_rgb, 0.48))
    subtle = _ensure_contrast_multi(subtle_seed, (panel2, panel), 3.0, prefer_light_ink)

    accent_prefer_light = relative_luminance(accent) < 0.44
    btn_text = _ensure_contrast(theme.get("btn_text"), accent, 4.5, accent_prefer_light)
    semantic_info = _normalize_hex(theme.get("semanticInfo"), accent)
    semantic_success = _normalize_hex(theme.get("semanticSuccess"), _SEMANTIC_SUCCESS)
    semantic_warning = _normalize_hex(theme.get("semanticWarning"), _SEMANTIC_WARNING)
    semantic_error = _normalize_hex(theme.get("semanticError"), _SEMANTIC_ERROR)
    semantic_danger = _normalize_hex(theme.get("semanticDanger"), _SEMANTIC_DANGER)

    theme.update(
        {
            "bg": bg,
            "panel": panel,
            "panel2": panel2,
            "accent": accent,
            "hover": hover,
            "glow": glow,
            "text": text,
            "muted": muted,
            "btn_text": btn_text,
            "textStrong": text,
            "textMuted": muted,
            "textSubtle": subtle,
            "panelText": _ensure_contrast(text, panel2, 4.8, prefer_light_ink),
            "panelMuted": _ensure_contrast(muted, panel2, 3.6, prefer_light_ink),
            "accentText": _ensure_contrast(btn_text, accent, 4.5, accent_prefer_light),
            "semanticInfo": semantic_info,
            "semanticInfoText": _ensure_contrast(
                theme.get("semanticInfoText"),
                semantic_info,
                4.5,
                relative_luminance(semantic_info) < 0.44,
            ),
            "semanticSuccess": semantic_success,
            "semanticSuccessText": _ensure_contrast(
                theme.get("semanticSuccessText"),
                semantic_success,
                4.5,
                relative_luminance(semantic_success) < 0.44,
            ),
            "semanticWarning": semantic_warning,
            "semanticWarningText": _ensure_contrast(
                theme.get("semanticWarningText"),
                semantic_warning,
                4.5,
                relative_luminance(semantic_warning) < 0.44,
            ),
            "semanticError": semantic_error,
            "semanticErrorText": _ensure_contrast(
                theme.get("semanticErrorText"),
                semantic_error,
                4.5,
                relative_luminance(semantic_error) < 0.44,
            ),
            "semanticDanger": semantic_danger,
            "semanticDangerText": _ensure_contrast(
                theme.get("semanticDangerText"),
                semantic_danger,
                4.5,
                relative_luminance(semantic_danger) < 0.44,
            ),
        }
    )
    return theme


def sanitize_theme_map(raw_themes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    clean: Dict[str, Dict[str, Any]] = {}
    for name, theme in dict(raw_themes or {}).items():
        clean[str(name)] = sanitize_theme_palette(theme if isinstance(theme, dict) else {})
    return clean
