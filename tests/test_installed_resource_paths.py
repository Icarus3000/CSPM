from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from services.paths import AppPaths
from services.sync_service import SyncService
from services.theme_service import ThemeService
from services.workbook_integrity_service import WorkbookIntegrityService


def _freeze_at(monkeypatch: pytest.MonkeyPatch, bundle: Path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)


def test_frozen_profile_uses_shipped_resources_and_keeps_writable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, profile = tmp_path / "installed/_internal", tmp_path / "profile"
    local = profile / "local-data"
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(profile))
    monkeypatch.setenv("CSPM_DATA_DIR", str(profile))
    _freeze_at(monkeypatch, bundle)
    paths = AppPaths(profile, override_data_dir=local)

    assert paths.docs_dir() == bundle / "docs"
    assert paths.workbook_schema_path() == bundle / "schema/workbook_schema.yml"
    assert paths.themes_json_path() == bundle / "src/qml/themes/themes.json"
    assert paths.workbook_path() == local / "CSPM.xlsm"
    assert paths.user_settings_path() == profile / "user_settings.json"
    assert paths.exports_dir() == profile / "exports"


def test_development_resources_preserve_explicit_source_or_fixture_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(AppPaths, "project_root", staticmethod(lambda: tmp_path / "other-source"))
    paths = AppPaths(tmp_path / "fixture")

    assert paths.docs_dir() == tmp_path / "fixture/docs"
    assert paths.schema_dir() == tmp_path / "fixture/schema"
    assert paths.themes_json_path() == tmp_path / "fixture/src/qml/themes/themes.json"


def test_frozen_theme_reader_ignores_profile_resource_shadow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SOURCE_ROOT.parent / "qml/themes/themes.json"
    bundle, profile = tmp_path / "installed/_internal", tmp_path / "profile"
    shipped = bundle / "src/qml/themes/themes.json"
    shipped.parent.mkdir(parents=True)
    shipped.write_bytes(source.read_bytes())
    shadow = profile / "src/qml/themes/themes.json"
    shadow.parent.mkdir(parents=True)
    shadow.write_text("invalid profile resource", encoding="utf-8")
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(profile))
    monkeypatch.setenv("CSPM_DATA_DIR", str(profile))
    _freeze_at(monkeypatch, bundle)

    service = ThemeService(AppPaths(profile))

    assert service.theme_names()
    assert service.current_theme()["name"] in service.theme_names()
    assert shadow.read_text(encoding="utf-8") == "invalid profile resource"


def test_frozen_workbook_integrity_reads_shipped_schema_without_workbook_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = SOURCE_ROOT.parent.parent
    bundle, profile = tmp_path / "installed/_internal", tmp_path / "profile"
    schema = bundle / "schema/workbook_schema.yml"
    schema.parent.mkdir(parents=True)
    schema.write_bytes((project / "schema/workbook_schema.yml").read_bytes())
    shadow = profile / "schema/workbook_schema.yml"
    shadow.parent.mkdir(parents=True)
    shadow.write_text("invalid profile schema", encoding="utf-8")
    local = profile / "data/CSPM.xlsm"
    local.parent.mkdir(parents=True)
    payload = (project / "src/templates/CSPM.xlsm").read_bytes()
    local.write_bytes(payload)
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(profile))
    monkeypatch.setenv("CSPM_DATA_DIR", str(profile))
    _freeze_at(monkeypatch, bundle)

    report = WorkbookIntegrityService(AppPaths(profile)).check()

    assert report.schema_path == str(schema)
    assert report.tables_checked > 0
    assert not {"missing_schema", "schema_read_failed", "schema_invalid"}.intersection(
        issue.code for issue in report.issues
    )
    assert local.read_bytes() == payload
    assert shadow.read_text(encoding="utf-8") == "invalid profile schema"


@pytest.mark.parametrize("name", SyncService._FILES)
def test_frozen_seed_identity_uses_bundle_approval_without_changing_local_copy(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, profile = tmp_path / "installed/_internal", tmp_path / "profile"
    templates = bundle / "src/templates"
    templates.mkdir(parents=True)
    # Synthetic bytes isolate path selection; the existing checkout suite
    # separately validates real workbook approval and modified-metadata guards.
    payload = b"synthetic approved empty fixture"
    (templates / name).write_bytes(payload)
    approval = {"templates": [{
        "approved_filename": name,
        "human_approval_status": "APPROVED",
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
    }]}
    (templates / "template_approval.json").write_text(json.dumps(approval), encoding="utf-8")
    local = profile / "data" / name
    local.parent.mkdir(parents=True)
    local.write_bytes(payload)
    shadow = profile / "src/templates"
    shadow.mkdir(parents=True)
    (shadow / "template_approval.json").write_text("invalid profile approval", encoding="utf-8")
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(profile))
    monkeypatch.setenv("CSPM_DATA_DIR", str(profile))
    _freeze_at(monkeypatch, bundle)
    service = SyncService(AppPaths(profile), machine_identity_file=profile / "machine.json")

    assert service._is_blank_seed(name, local)
    assert local.read_bytes() == payload
    local.write_bytes(payload + b" populated local records")
    assert not service._is_blank_seed(name, local)
    assert local.read_bytes() == payload + b" populated local records"
