from dataclasses import dataclass
from typing import Optional

@dataclass
class TimerState:
    accumulated_elapsed_seconds: int
    is_running: bool
    started_at_monotonic: Optional[float] = None
    
    def get_elapsed_seconds(self, current_monotonic: float) -> int:
        elapsed = self.accumulated_elapsed_seconds
        if self.is_running and self.started_at_monotonic is not None:
            # Handle simulated sleep or large jumps correctly
            elapsed += int(current_monotonic - self.started_at_monotonic)
        return elapsed

def format_elapsed(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
