from __future__ import annotations


def seconds_to_hms(total: float) -> str:
    t = int(total or 0)
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
