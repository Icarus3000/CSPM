import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional


class TelemetryLogger:
    def __init__(self, data_dir: Path):
        self._log_file = data_dir / "usage_telemetry.csv"
        self._ensure_header()

    def _ensure_header(self):
        """Creates the CSV header if the file does not exist or is empty."""
        try:
            write_header = not self._log_file.exists() or self._log_file.stat().st_size == 0
            if write_header:
                with open(self._log_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Action", "DurationMs", "Details"])
        except Exception as e:
            logging.error(f"Failed to initialize telemetry file: {e}")

    def record_activity(self, action: str, duration_ms: Optional[int] = None, details: str = ""):
        """Appends a telemetry record to the CSV file."""
        try:
            timestamp = datetime.now().isoformat()
            duration_str = str(duration_ms) if duration_ms is not None else ""
            with open(self._log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, action, duration_str, details])
        except Exception as e:
            logging.error(f"Failed to write telemetry: {e}")
