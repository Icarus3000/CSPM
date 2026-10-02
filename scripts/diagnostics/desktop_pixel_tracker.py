"""Read compositor pixels in memory; persist coordinates only, never images."""
import ctypes
from ctypes import wintypes
import csv
import threading
import time
import sys
from pathlib import Path
import os
if os.environ.get('CSPM_PIXEL_DEPENDENCIES'):
    sys.path.insert(0, os.environ['CSPM_PIXEL_DEPENDENCIES'])
import numpy as np

SENSORS = [('top_left', (252, 5, 188)), ('top_middle', (6, 252, 130)),
           ('top_right', (250, 80, 5)), ('right_middle', (6, 80, 252)),
           ('bottom_right', (252, 240, 6)), ('bottom_middle', (110, 6, 252)),
           ('bottom_left', (6, 240, 252)), ('left_middle', (252, 6, 54))]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class PixelTracker:
    def __init__(self, hwnd, output):
        self.hwnd = hwnd
        self.output = output
        self.rows = []
        self.commands = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def command(self, name):
        stamp = time.perf_counter()
        self.commands.append((stamp, name))
        return stamp

    def stop(self):
        self.stop_event.set()
        self.thread.join(5)
        with self.output.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'read_ms', 'native_x', 'native_y', 'native_w', 'native_h'] +
                            [f'{name}_{axis}' for name, _ in SENSORS for axis in ('x', 'y', 'w', 'h')])
            writer.writerows(self.rows)
        with self.output.with_suffix('.commands.csv').open('w', newline='') as f:
            csv.writer(f).writerows(self.commands)

    def run(self):
        import dxcam
        user32 = ctypes.WinDLL('user32')
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        camera = dxcam.create(device_idx=0, output_idx=0, output_color='BGRA', processor_backend='numpy', max_buffer_len=2)
        rect = wintypes.RECT()
        keep_awake = ctypes.windll.kernel32.SetThreadExecutionState
        keep_awake(0x80000003)
        try:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                pixels = camera.grab(copy=False, new_frame_only=True)
                if pixels is None:
                    self.stop_event.wait(.001)
                    continue
                user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
                height, width = pixels.shape[:2]
                sample = pixels.view(np.uint32).reshape(height, width)[::2, ::2] & 0x00FFFFFF
                palette = [(r << 16) | (g << 8) | b for _, (r,g,b) in SENSORS]
                mask = np.zeros(sample.shape, dtype=bool)
                for color in palette:
                    mask |= sample == color
                mask[:-1, :-1] &= mask[1:, :-1] & mask[:-1, 1:] & mask[1:, 1:]
                yy_all, xx_all = np.nonzero(mask)
                values = sample[yy_all, xx_all]
                boxes = []
                for color in palette:
                    matching = values == color
                    xx, yy = xx_all[matching], yy_all[matching]
                    if xx.size:
                        tiles = (yy // 16) * ((width+31)//32) + xx // 16
                        tile = int(np.bincount(tiles).argmax())
                        center_x = (tile % ((width+31)//32)) * 16 + 8
                        center_y = (tile // ((width+31)//32)) * 16 + 8
                        near = (abs(xx-center_x) < 25) & (abs(yy-center_y) < 25)
                        xx, yy = xx[near], yy[near]
                    boxes.extend([int(xx.min())*2, int(yy.min())*2,
                                  (int(xx.max())-int(xx.min()))*2+2,
                                  (int(yy.max())-int(yy.min()))*2+2] if xx.size else [-1, -1, 0, 0])
                finished = time.perf_counter()
                self.rows.append([started, (finished-started)*1000, rect.left, rect.top,
                                  rect.right-rect.left, rect.bottom-rect.top, *boxes])
        except Exception as exc:
            print('PIXEL TRACKER ERROR',repr(exc),flush=True)
        finally:
            keep_awake(0x80000000)
            camera.release()


if __name__ == '__main__':
    tracker = PixelTracker(int(sys.argv[1]), Path(sys.argv[2]))
    tracker.start()
    sys.stdin.readline()
    tracker.stop()
