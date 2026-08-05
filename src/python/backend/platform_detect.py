"""
Platform / hardware detection utilities.

Extracted from app_controller.py to reduce monolith size and allow
independent testing of platform detection logic.
"""
import ctypes
import os
import sys


def env_low_perf_override():
    """Check CSPM_LOW_PERF env var. Returns True/False/None."""
    raw = os.environ.get("CSPM_LOW_PERF", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def detect_total_memory_gb() -> float:
    """Return total physical memory in GB, or 0.0 on failure."""
    try:
        if sys.platform.startswith("win"):
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return float(status.ullTotalPhys) / (1024.0 ** 3)
            return 0.0
        if hasattr(os, "sysconf"):
            pages = getattr(os, "sysconf", lambda x: 0)("SC_PHYS_PAGES")
            page_size = getattr(os, "sysconf", lambda x: 0)("SC_PAGE_SIZE")
            if (
                isinstance(pages, int)
                and isinstance(page_size, int)
                and pages > 0
                and page_size > 0
            ):
                return float(pages * page_size) / (1024.0 ** 3)
    except Exception:
        pass
    return 0.0


def detect_low_performance_mode() -> bool:
    """Return True if the machine appears to be low-spec."""
    override = env_low_perf_override()
    if override is not None:
        return override
    cpu_cores = os.cpu_count() or 0
    memory_gb = detect_total_memory_gb()
    low_cpu = 0 < cpu_cores <= 4
    low_memory = 0 < memory_gb <= 8.5
    return low_cpu or low_memory
