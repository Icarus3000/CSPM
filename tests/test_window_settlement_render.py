"""Opt-in desktop GPU regression for title size and exact endpoint pixels."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

@pytest.mark.skipif(os.environ.get('CSPM_RUN_WINDOW_GPU_TESTS') != '1',
                    reason='Requires an outside-sandbox desktop GPU')
def test_title_glyph_dimensions_and_endpoint_pixels_survive_both_directions():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root/'tests/window_settlement_render_probe.py')],
                            cwd=root, capture_output=True, text=True, timeout=55)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"failures": []' in result.stdout


@pytest.mark.skipif(os.environ.get('CSPM_RUN_WINDOW_GPU_TESTS') != '1',
                    reason='Requires an outside-sandbox desktop GPU')
def test_native_frame_and_transition_endpoint_match_across_attached_screen_dpis():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root/'tests/window_handoff_pixel_probe.py')],
                            cwd=root, capture_output=True, text=True, timeout=100)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"failures": []' in result.stdout
