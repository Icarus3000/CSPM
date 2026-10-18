"""Isolated tmp_path unit tests for VaultService, AppPaths Vault helpers, and AppController Vault slots.

Does NOT touch any live .xlsm workbooks on disk.
"""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PYTHON = REPO_ROOT / "src" / "python"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PYTHON) not in sys.path:
    sys.path.insert(0, str(SRC_PYTHON))

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from backend.app_controller import AppController
from services.paths import AppPaths
from services.vault_service import VaultService

RETAINER_FILENAME = "2026-10-16 Joint Retainer Agreement - Reorganization - Signed.pdf"


def test_app_paths_shared_and_local_vault_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    shared_data = tmp_path / "OneDrive - Test" / "CSPM_Shared_Data"
    local_data = tmp_path / "LocalAppData" / "CSPM" / "data"
    shared_data.mkdir(parents=True)
    local_data.mkdir(parents=True)

    monkeypatch.setenv("CSPM_MASTER_DATA_DIR", str(shared_data))
    monkeypatch.setenv("CSPM_LOCAL_DATA_DIR", str(local_data))

    paths = AppPaths(root=tmp_path)
    assert paths.shared_vault_dir() == shared_data / "Vault"
    assert paths.local_vault_dir() == local_data / "Vault"


def test_vault_service_ingest_and_multi_path_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    shared_data = tmp_path / "shared" / "CSPM_Shared_Data"
    local_data = tmp_path / "local" / "data"
    onedrive_root = tmp_path / "OneDrive - Firm"
    shared_data.mkdir(parents=True)
    local_data.mkdir(parents=True)
    onedrive_root.mkdir(parents=True)

    monkeypatch.setenv("OneDriveCommercial", str(onedrive_root))
    paths = AppPaths(
        root=tmp_path,
        override_data_dir=local_data,
        override_master_dir=shared_data,
    )
    vault = VaultService(paths, onedrive_roots=[onedrive_root])

    # 1. Test ingest_document copies into both shared and local Vaults
    src_file = tmp_path / RETAINER_FILENAME
    src_file.write_bytes(b"%PDF-1.7 signed retainer bytes")

    canonical_rel = vault.ingest_document(
        scope_type="Matters",
        scope_id="MEGA-COR-26-0093",
        category="Retainer",
        source_path=src_file,
    )
    assert canonical_rel == f"Vault/Matters/MEGA-COR-26-0093/Retainer/{RETAINER_FILENAME}"
    assert (shared_data / "Vault" / "Matters" / "MEGA-COR-26-0093" / "Retainer" / RETAINER_FILENAME).is_file()
    assert (local_data / "Vault" / "Matters" / "MEGA-COR-26-0093" / "Retainer" / RETAINER_FILENAME).is_file()

    # Resolve by canonical Vault/... path
    resolved_vault = vault.resolve_document_path(canonical_rel)
    assert resolved_vault is not None
    assert resolved_vault.is_file()

    # Resolve by bare filename + matter_number
    resolved_bare = vault.resolve_document_path(RETAINER_FILENAME, matter_number="MEGA-COR-26-0093")
    assert resolved_bare is not None
    assert resolved_bare.is_file()

    # 2. Test Client KYC ingestion & resolution
    kyc_src = tmp_path / "2026-10-15 KYC Identification - Verified.pdf"
    kyc_src.write_bytes(b"%PDF-1.7 kyc bytes")
    kyc_rel = vault.ingest_document("Clients", "MEGA", "KYC", kyc_src)
    assert kyc_rel == "Vault/Clients/MEGA/KYC/2026-10-15 KYC Identification - Verified.pdf"
    resolved_kyc = vault.resolve_document_path(
        "2026-10-15 KYC Identification - Verified.pdf",
        client_id="MEGA",
    )
    assert resolved_kyc is not None and resolved_kyc.is_file()


def test_vault_service_onedrive_clients_cs_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify fallback resolution to %OneDrive%/Clients (CS)/Megatech/2026 - Corporate Reorganization/01 - Retainer & Engagement/..."""
    shared_data = tmp_path / "shared_empty" / "CSPM_Shared_Data"
    local_data = tmp_path / "local_empty" / "data"
    onedrive_root = tmp_path / "OneDrive - Workstation"
    retainer_dir = (
        onedrive_root
        / "Clients (CS)"
        / "Megatech"
        / "2026 - Corporate Reorganization"
        / "01 - Retainer & Engagement"
    )
    retainer_dir.mkdir(parents=True)
    onedrive_retainer = retainer_dir / RETAINER_FILENAME
    onedrive_retainer.write_bytes(b"%PDF-1.7 onedrive working copy")

    monkeypatch.setenv("OneDrive", str(onedrive_root))
    paths = AppPaths(
        root=tmp_path,
        override_data_dir=local_data,
        override_master_dir=shared_data,
    )
    vault = VaultService(paths, onedrive_roots=[onedrive_root])

    # Resolve via OneDrive-relative working path
    rel_working = (
        "Clients (CS)/Megatech/2026 - Corporate Reorganization/"
        f"01 - Retainer & Engagement/{RETAINER_FILENAME}"
    )
    resolved_direct = vault.resolve_document_path(rel_working)
    assert resolved_direct is not None
    assert resolved_direct.resolve() == onedrive_retainer.resolve()

    # Resolve via Vault/... path when file only exists in OneDrive Clients (CS) working folder
    resolved_fallback = vault.resolve_document_path(
        f"Vault/Matters/MEGA-COR-26-0093/Retainer/{RETAINER_FILENAME}",
        matter_number="MEGA-COR-26-0093",
    )
    assert resolved_fallback is not None
    assert resolved_fallback.resolve() == onedrive_retainer.resolve()

    # Resolve with empty doc_ref using matter_number="MEGA-COR-26-0093"
    resolved_by_matter = vault.resolve_document_path("", matter_number="MEGA-COR-26-0093")
    assert resolved_by_matter is not None
    assert resolved_by_matter.resolve() == onedrive_retainer.resolve()


def test_app_controller_vault_slots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    shared_data = tmp_path / "shared" / "CSPM_Shared_Data"
    local_data = tmp_path / "local" / "data"
    onedrive_root = tmp_path / "OneDrive - Test"
    retainer_dir = (
        onedrive_root
        / "Clients (CS)"
        / "Megatech"
        / "2026 - Corporate Reorganization"
        / "01 - Retainer & Engagement"
    )
    retainer_dir.mkdir(parents=True)
    retainer_pdf = retainer_dir / RETAINER_FILENAME
    retainer_pdf.write_bytes(b"%PDF-1.7 signed retainer")

    monkeypatch.setenv("OneDriveCommercial", str(onedrive_root))
    paths = AppPaths(
        root=tmp_path,
        override_data_dir=local_data,
        override_master_dir=shared_data,
    )

    opened_urls: list[QUrl] = []

    def _fake_open_url(url: QUrl) -> bool:
        opened_urls.append(url)
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(_fake_open_url))

    # Construct a lightweight AppController instance without booting Excel workbooks
    ctrl = AppController.__new__(AppController)
    ctrl._paths = paths
    toasts: list[str] = []
    ctrl.toast = SimpleNamespace(emit=lambda msg: toasts.append(str(msg)))
    ctrl.error = SimpleNamespace(emit=lambda msg: None)
    ctrl._report_failure = lambda *args, **kwargs: None

    stub_matters: dict[str, dict[str, Any]] = {
        "MEGA-COR-26-0093": {
            "matterId": "M_megatech_s86_2026",
            "matterNumber": "MEGA-COR-26-0093",
            "clientId": "MEGA",
            "jointEngagementDocument": f"Vault/Matters/MEGA-COR-26-0093/Retainer/{RETAINER_FILENAME}",
            "notes": "",
        }
    }
    ctrl._excel_repo = SimpleNamespace(
        get_matter_profile=lambda key: (
            {"ok": True, "matter": stub_matters[key]}
            if key in stub_matters
            else {"ok": False, "matter": {}}
        )
    )

    # 1. openMatterRetainer resolves fallback in OneDrive Clients (CS)
    assert ctrl.openMatterRetainer("MEGA-COR-26-0093") is True
    assert len(opened_urls) == 1
    assert Path(opened_urls[-1].toLocalFile()).resolve() == retainer_pdf.resolve()

    # 2. ingestDocumentToVault copies retainer into Vault and returns canonical Vault/... path
    ingested_rel = ctrl.ingestDocumentToVault(
        "Matters",
        "MEGA-COR-26-0093",
        "Retainer",
        str(retainer_pdf),
    )
    assert ingested_rel == f"Vault/Matters/MEGA-COR-26-0093/Retainer/{RETAINER_FILENAME}"

    # 3. openVaultDocument opens the ingested Vault document
    assert ctrl.openVaultDocument(ingested_rel) is True
    assert len(opened_urls) == 2

    # 4. openMatterVaultFolder creates and opens Vault/Matters/MEGA-COR-26-0093
    assert ctrl.openMatterVaultFolder("MEGA-COR-26-0093") is True
    assert (shared_data / "Vault" / "Matters" / "MEGA-COR-26-0093").is_dir()

    # 5. openClientKYCVaultFolder creates and opens Vault/Clients/MEGA/KYC
    assert ctrl.openClientKYCVaultFolder("MEGA") is True
    assert (shared_data / "Vault" / "Clients" / "MEGA" / "KYC").is_dir()
