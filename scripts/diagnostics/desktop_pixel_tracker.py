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
        output_index = int(os.environ.get('CSPM_PIXEL_OUTPUT', '0'))
        camera = dxcam.create(device_idx=0, output_idx=output_index, output_color='BGRA', processor_backend='numpy', max_buffer_len=2)
        rect = wintypes.RECT()
        region_text = os.environ.get('CSPM_PIXEL_REGION', '').strip()
        region = tuple(int(value) for value in region_text.split(',')) if region_text else None
        if region is not None and (len(region) != 4 or region[0] >= region[2] or region[1] >= region[3]):
            raise ValueError('CSPM_PIXEL_REGION requires left,top,right,bottom')
        origin_x, origin_y = region[:2] if region else (0, 0)
        pitch = 1 if region else 2
        interval = max(0.0, float(os.environ.get('CSPM_PIXEL_INTERVAL_MS', '0'))) / 1000
        keep_awake = ctypes.windll.kernel32.SetThreadExecutionState
        keep_awake(0x80000003)
        try:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                pixels = camera.grab(region=region, copy=False, new_frame_only=True)
                if pixels is None:
                    self.stop_event.wait(.001)
                    continue
                user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
                height, width = pixels.shape[:2]
                sample = pixels.view(np.uint32).reshape(height, width)[::pitch, ::pitch] & 0x00FFFFFF
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
                        tile_columns = (sample.shape[1]+15)//16
                        tiles = (yy // 16) * tile_columns + xx // 16
                        tile = int(np.bincount(tiles).argmax())
                        center_x = (tile % tile_columns) * 16 + 8
                        center_y = (tile // tile_columns) * 16 + 8
                        near = (abs(xx-center_x) < 25) & (abs(yy-center_y) < 25)
                        xx, yy = xx[near], yy[near]
                    boxes.extend([origin_x+int(xx.min())*pitch, origin_y+int(yy.min())*pitch,
                                  (int(xx.max())-int(xx.min()))*pitch+pitch,
                                  (int(yy.max())-int(yy.min()))*pitch+pitch] if xx.size else [-1, -1, 0, 0])
                finished = time.perf_counter()
                self.rows.append([started, (finished-started)*1000, rect.left, rect.top,
                                  rect.right-rect.left, rect.bottom-rect.top, *boxes])
                self.stop_event.wait(max(0.0, interval-(finished-started)))
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
