from typing import List
from tray.elapsed_time import TimerState

def calculate_recorded_today(entries_decimal_hours: List[float]) -> float:
    return sum(entries_decimal_hours)
    
def calculate_active_now_seconds(timers: List[TimerState], current_monotonic: float) -> int:
    return sum(t.get_elapsed_seconds(current_monotonic) for t in timers)
    
def calculate_total_today(recorded_decimal: float, active_now_seconds: int) -> float:
    # Convert active seconds to decimal hours (1 hour = 3600 seconds)
    active_decimal = active_now_seconds / 3600.0
    return recorded_decimal + active_decimal
