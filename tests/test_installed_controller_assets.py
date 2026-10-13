"""Installed resource regressions without launching CSPM or editing workbooks."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src" / "python"))
from backend.app_controller import AppController
from services.paths import AppPaths


@pytest.fixture
def installed(tmp_path, monkeypatch):
    package = tmp_path / "installation"
    internal = package / "_internal"
    runtime = tmp_path / "profile"
    internal.mkdir(parents=True)
    runtime.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(internal), raising=False)
    monkeypatch.setattr(sys, "executable", str(package / "CSPM.exe"))
    monkeypatch.setenv("CSPM_EXECUTABLE_ROOT", str(runtime))
    return package, internal, runtime, AppPaths(runtime)


def test_version_uses_package_metadata_instead_of_profile(installed):
    _, internal, runtime, paths = installed
    (internal / "version.json").write_text(json.dumps({"version": "9.8.7"}))
    (runtime / "version.json").write_text(json.dumps({"version": "0.0.0"}))
    assert AppController._load_app_version(SimpleNamespace(_paths=paths)) == "9.8.7"


@pytest.mark.parametrize("configured", ["", "missing/custom-mark.png"])
def test_pdf_default_logo_survives_absent_or_missing_custom_logo(installed, configured):
    _, internal, _, paths = installed
    logo = internal / "assets" / "CS.svg"
    logo.parent.mkdir()
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    rasterized = []
    controller = SimpleNamespace(_paths=paths)
    controller._resolve_asset_file_path = lambda value: AppController._resolve_asset_file_path(controller, value)
    controller._coerce_file_path = lambda value: Path(value)
    controller._rasterize_svg_logo_for_pdf = lambda profile, path, color=None: rasterized.append(path) or "cached-report-mark.png"
    assert AppController._logo_path_for_pdf(controller, {"logoPath": configured}) == "cached-report-mark.png"
    assert rasterized == [logo]
    assert AppController._default_report_branding_profile(controller)["logoPath"] == str(logo)


def test_existing_custom_pdf_logo_is_preserved(installed, tmp_path):
    _, _, _, paths = installed
    logo = tmp_path / "custom-firm.png"
    logo.write_bytes(b"fixture")
    controller = SimpleNamespace(_paths=paths)
    controller._resolve_asset_file_path = lambda value: AppController._resolve_asset_file_path(controller, value)
    controller._coerce_file_path = lambda value: Path(value)
    assert AppController._logo_path_for_pdf(controller, {"id": "custom", "logoPath": str(logo)}) == str(logo)


def test_relative_asset_keeps_subdirectories_when_profile_is_separate(installed):
    _, internal, _, paths = installed
    asset = internal / "assets" / "nested" / "brand.svg"
    asset.parent.mkdir(parents=True)
    asset.write_text("fixture")
    assert AppController._resolve_asset_file_path(SimpleNamespace(_paths=paths), "assets/nested/brand.svg") == asset


@pytest.mark.parametrize("present", [True, False])
def test_frozen_recovery_uses_sibling_executable_without_relaunching_main(installed, monkeypatch, present):
    package, _, _, paths = installed
    recovery = package / "CSPM_Recovery" / "CSPM_Recovery.exe"
    if present:
        recovery.parent.mkdir()
        recovery.write_bytes(b"fixture")
    calls, errors = [], []
    monkeypatch.setattr("backend.app_controller.subprocess.Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    controller = SimpleNamespace(_paths=paths, error=SimpleNamespace(emit=errors.append))
    assert AppController.openRecoveryUtility(controller) is present
    if present:
        assert calls[0][0] == ([str(recovery)],)
        assert calls[0][1]["cwd"] == str(recovery.parent)
        assert not errors
    else:
        assert not calls
        assert "Repair the CSPM installation" in errors[0]


def test_development_recovery_uses_injected_source_root(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    script = tmp_path / "scripts" / "cspm_recovery.py"
    script.parent.mkdir()
    script.write_text("# fixture")
    calls = []
    monkeypatch.setattr("backend.app_controller.subprocess.Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    controller = SimpleNamespace(_paths=AppPaths(tmp_path), error=SimpleNamespace(emit=lambda _: None))
    assert AppController.openRecoveryUtility(controller)
    assert calls[0][0] == ([sys.executable, str(script)],)
