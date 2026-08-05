from dataclasses import dataclass
from typing import Tuple

@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int

@dataclass
class Point:
    x: int
    y: int

@dataclass
class GeometryResult:
    flyout_rect: Rect
    direction: str
    clamped: bool
    monitor_id: str

def calculate_placement(
    anchor: Point,
    monitor_rect: Rect,
    work_area: Rect,
    flyout_size: Tuple[int, int],
    dpi_scale: float,
    monitor_id: str
) -> GeometryResult:
    width, height = flyout_size
    width = int(width * dpi_scale)
    height = int(height * dpi_scale)
    
    x = anchor.x - (width // 2)
    clamped = False
    
    # Clamp to work area X
    if x < work_area.x:
        x = work_area.x
        clamped = True
    elif x + width > work_area.x + work_area.width:
        x = work_area.x + work_area.width - width
        clamped = True
        
    direction = "up"
    # Decide direction based on anchor's vertical position relative to the work area center
    if anchor.y > work_area.y + work_area.height // 2:
        # Bottom taskbar: place flyout above the anchor
        y = anchor.y - height
        if y < work_area.y:
            y = work_area.y
            clamped = True
    else:
        # Top taskbar: place flyout below the anchor
        y = anchor.y
        direction = "down"
        if y + height > work_area.y + work_area.height:
            y = work_area.y + work_area.height - height
            clamped = True
            
    # Additional bounds checking: Ensure we never cross monitor boundaries
    # Even if anchor is weird, force it inside monitor_rect
    if x < monitor_rect.x: x = monitor_rect.x
    if x + width > monitor_rect.x + monitor_rect.width: x = monitor_rect.x + monitor_rect.width - width
    if y < monitor_rect.y: y = monitor_rect.y
    if y + height > monitor_rect.y + monitor_rect.height: y = monitor_rect.y + monitor_rect.height - height
            
    return GeometryResult(
        flyout_rect=Rect(x, y, width, height),
        direction=direction,
        clamped=clamped,
        monitor_id=monitor_id
    )
