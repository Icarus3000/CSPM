"""Ignored one-change launcher for the existing unavailable-native QML fallback.

This exposes an already registered selector to the disposable existing probe.
It does not implement native bridge dispatch or native failure recovery.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


project = Path(__file__).resolve().parents[4]
original = project / "scripts/diagnostics/cleanroom_transition_probe.py"
run = Path(os.environ["CSPM_EXISTING_SAFETY_RUN_DIR"]).resolve()
owned_root = (project / "outputs/created_band_resume_20261008").resolve()
if run.drive.upper() != "Y:" or not run.is_relative_to(owned_root) or run == owned_root:
    raise RuntimeError("Existing safety launcher output must be an owned Y: run directory")
source_bytes = original.read_bytes()
source = source_bytes.decode("utf-8")
old = 'choices=("production", "single-clock", "compare"), default="compare"'
new = 'choices=("production", "single-clock", "native-composition", "compare"), default="compare"'
if source.count(old) != 1:
    raise RuntimeError("Expected exactly one unchanged existing engine parser declaration")
executed = source.replace(old, new, 1)
snapshot = run / "executed_probe.py.txt"
snapshot.write_bytes(executed.encode("utf-8"))
(run / "constructor_manifest.json").write_text(json.dumps({
    "originalRelativePath": "scripts/diagnostics/cleanroom_transition_probe.py",
    "originalSha256": hashlib.sha256(source_bytes).hexdigest(),
    "constructorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "executedSha256": hashlib.sha256(executed.encode("utf-8")).hexdigest(),
    "replacementCount": 1,
    "change": "Add existing native-composition selector to disposable probe parser choices only",
    "executionFileContext": "Original diagnostic path retained for root and resource resolution",
    "scope": "Existing QML selector-unavailable fallback; real native bridge failure recovery is unimplemented",
}, indent=2), encoding="utf-8")
namespace = {"__file__": str(original), "__name__": "__main__"}
exec(compile(executed, str(original), "exec"), namespace)
