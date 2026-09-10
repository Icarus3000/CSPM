from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _build_release_module():
    script = PROJECT_ROOT / "scripts" / "build_release.py"
    spec = importlib.util.spec_from_file_location("cspm_build_release", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deployment_removes_empty_stale_python_package_directories(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "_internal").mkdir(parents=True)
    (source / "_internal" / "current-runtime.pyd").write_bytes(b"current")
    (source / "CSPM.exe").write_bytes(b"new-executable")

    stale_numpy = target / "_internal" / "numpy" / "_core"
    stale_numpy.mkdir(parents=True)
    (stale_numpy / "stale-runtime.pyd").write_bytes(b"stale")
    (target / "data").mkdir(parents=True)
    (target / "data" / "CSPM.xlsm").write_bytes(b"user-data")

    module = _build_release_module()
    module.deploy_to_programs(source, target)

    assert not (target / "_internal" / "numpy").exists()
    assert (target / "_internal" / "current-runtime.pyd").read_bytes() == b"current"
    assert (target / "CSPM.exe").read_bytes() == b"new-executable"
    assert (target / "data" / "CSPM.xlsm").read_bytes() == b"user-data"
