from __future__ import annotations

from typing import Optional


def normalize_pct(pct: Optional[object], default_pct: float = 100.0) -> float:
    """
    Accepts "70", "70%", 0.7, "0.7" etc.
    Returns percent in 0..100.
    """
    if pct is None:
        return float(default_pct)

    s = str(pct).strip().replace("%", "").replace(",", "")
    if s == "":
        return float(default_pct)

    try:
        v = float(s)
    except Exception:
        return float(default_pct)

    # If 0..1 treat as fraction
    if 0.0 <= v <= 1.0:
        v = v * 100.0

    if v < 0.0:
        v = 0.0
    if v > 100.0:
        v = 100.0
    return float(v)


def calc_amounts(hours: float, client_rate: float, your_share_pct: float, hst_rate: float = 0.13) -> dict:
    """
    Computes:
      gross_to_client = hours * client_rate
      amount_to_you   = gross_to_client * (your_share_pct / 100)
      hst_on_you      = amount_to_you * hst_rate
      total_you_incl  = amount_to_you + hst_on_you
    """
    gross = round(float(hours) * float(client_rate), 2)
    you = round(gross * (float(your_share_pct) / 100.0), 2)
    hst = round(you * float(hst_rate), 2)
    total = round(you + hst, 2)
    return {
        "gross_to_client": gross,
        "amount_to_you": you,
        "hst_on_you": hst,
        "total_you_incl_hst": total,
    }
