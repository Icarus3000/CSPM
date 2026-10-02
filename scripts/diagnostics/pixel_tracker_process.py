"""Separate-process collector: no NumPy/GIL work inside the tested app."""
import csv
from pathlib import Path
import subprocess
import sys
import time

SENSORS = [('top_left', (252, 5, 188)), ('top_middle', (6, 252, 130)),
           ('top_right', (250, 80, 5)), ('right_middle', (6, 80, 252)),
           ('bottom_right', (252, 240, 6)), ('bottom_middle', (110, 6, 252)),
           ('bottom_left', (6, 240, 252)), ('left_middle', (252, 6, 54))]


class PixelTracker:
    def __init__(self, hwnd, output):
        self.hwnd, self.output = hwnd, output
        self.commands = []
        self.stopped = False

    def start(self):
        script = Path(__file__).resolve().with_name('desktop_pixel_tracker.py')
        self.log = self.output.with_suffix('.collector.txt').open('w')
        self.process = subprocess.Popen([sys.executable, str(script), str(self.hwnd), str(self.output)],
                                        stdin=subprocess.PIPE, stdout=self.log, stderr=self.log,
                                        creationflags=subprocess.CREATE_NO_WINDOW)

    def command(self, name):
        self.commands.append((time.perf_counter(), name))

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b'STOP\n')
                self.process.stdin.flush()
                self.process.stdin.close()
            except BrokenPipeError:
                pass
        self.process.wait(timeout=8)
        self.log.close()
        with self.output.with_suffix('.commands.csv').open('w', newline='') as f:
            csv.writer(f).writerows(self.commands)

        if self.process.returncode:
            raise RuntimeError('Pixel collector failed; inspect ' + str(self.output.with_suffix('.collector.txt')))
        with self.output.open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        valid = [r for r in rows if int(r['top_left_w']) > 0]
        if len(rows) < 50 or len(valid) < 10:
            raise RuntimeError('Insufficient actual pixel samples; final state is not motion evidence')
        if self.commands and not any(float(r['timestamp']) < self.commands[0][0] for r in valid):
            raise RuntimeError('No detected source marker before first command; rerun collector initialization')
