from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PYTHON = REPO_ROOT / "src" / "python"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PYTHON) not in sys.path:
    sys.path.insert(0, str(SRC_PYTHON))

from domain import schema_constants as sc
from prototypes.sqlite_architecture.connection import close_connection
from prototypes.sqlite_architecture.migration import perform_dry_run_migration
from prototypes.sqlite_architecture.sqlite_repo import SQLiteRepository
from repositories.client_repo import ClientRepo
from repositories.excel_repo import ExcelRepo, TBL_CORP_ENTITIES, TBL_CORP_RELATIONSHIPS, TBL_CORP_TRANSACTIONS
from services.matter_document_service import MatterDocumentService
from services.paths import AppPaths

EXPECTED_REFERRER = "Nathan T. Choran, CPA, C.A. (Zeifmans LLP)"
EXPECTED_RETAINER_REL = (
    "Matter_Documents/MEGA-CRP-26-0209/"
    "2026-10-16 Joint Retainer Agreement - Reorganization - Signed--6a74e1a2d691.pdf"
)
EXPECTED_RETAINER_SHA256 = "6a74e1a2d6919a0f5aa869393bb0872fe03c0df026a0b7666e18644253ca7aad"


def test_megatech_hamilton_onboarding_excel_and_sqlite_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    work_data_dir = tmp_path / "data"
    work_data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "data" / "CSPM.xlsm", work_data_dir / "CSPM.xlsm")
    if (REPO_ROOT / "data" / "Matter_Documents").exists():
        shutil.copytree(
            REPO_ROOT / "data" / "Matter_Documents",
            work_data_dir / "Matter_Documents",
            dirs_exist_ok=True,
        )

    paths = AppPaths(root=REPO_ROOT, override_data_dir=work_data_dir)
    excel_repo = ExcelRepo(paths)
    excel_repo.ensure_schema()
    client_repo = ClientRepo(excel_repo)

    # 1. Verify Megatech Integrated Services Ltd. (MEGA) in Excel
    mega_res = client_repo.get_client_profile("MEGA")
    assert mega_res["ok"] is True
    mega = mega_res["client"]
    assert mega["clientId"] == "MEGA"
    assert mega["clientName"] == "Megatech Integrated Services Ltd."
    assert mega["entityType"] == "Corporation (CCPC)"
    assert mega["status"] == "Active"
    assert mega["active"] == 1
    assert mega["primaryEmail"] == "dhamilton@youravexperts.ca"
    assert mega["primaryPhone"] == "416-722-5757"
    assert "351 Steelcase Road West" in mega["fullAddress"]
    assert float(mega["defaultBillingRate"]) == pytest.approx(475.00)
    assert int(mega["hstExempt"]) == 0
    assert mega["openingDate"] == "2026-10-15"
    assert mega["kycStatus"] == "Completed"
    assert mega["kycVerifiedDate"] == "2026-10-15"
    assert mega["referredBy"] == EXPECTED_REFERRER
    assert mega["referralFrom"] == EXPECTED_REFERRER

    # 2. Verify Fawzia Hamilton (HAMI) in Excel
    hami_res = client_repo.get_client_profile("HAMI")
    assert hami_res["ok"] is True
    hami = hami_res["client"]
    assert hami["clientId"] == "HAMI"
    assert hami["clientName"] == "Fawzia Hamilton"
    assert hami["legalName"] == "HAMILTON, B-FAWZIA"
    assert hami["entityType"] == "Individual"
    assert hami["status"] == "Active"
    assert hami["active"] == 1
    assert hami["primaryEmail"] == "fawzhamilton@gmail.com"
    assert hami["primaryPhone"] == "416-662-6359"
    assert "61 Prince Edward Blvd." in hami["fullAddress"]
    assert float(hami["defaultBillingRate"]) == pytest.approx(475.00)
    assert int(hami["hstExempt"]) == 0
    assert hami["openingDate"] == "2026-10-15"
    assert hami["kycStatus"] == "Completed"
    assert hami["kycVerifiedDate"] == "2026-10-15"
    assert hami["referredBy"] == EXPECTED_REFERRER
    assert hami["referralFrom"] == EXPECTED_REFERRER

    # 3. Verify Corporate Reorganization Matter (M_megatech_s86_2026 / MEGA-CRP-26-0209) in Excel
    matter_res = client_repo.get_matter_profile("M_megatech_s86_2026")
    assert matter_res["ok"] is True
    matter = matter_res["matter"]
    assert matter["matterId"] == "M_megatech_s86_2026"
    assert matter["matterNumber"] == "MEGA-CRP-26-0209"
    assert matter["matterName"] == "Corporate Reorganization"
    assert matter["displayName"] == "Stage 1 Corporate Reorganization"
    assert matter["clientId"] == "MEGA"
    assert matter["status"] == "Active"
    assert matter["active"] == 1
    assert matter["dateOpened"] == "2026-10-15"
    assert matter["targetCompletionDate"] == "2026-10-31"
    assert float(matter["defaultRate"]) == pytest.approx(475.00)
    assert float(matter["feeEstimate"]) == pytest.approx(7000.00)
    assert int(matter["kycCompleted"]) == 1
    assert matter["referredBy"] == EXPECTED_REFERRER
    assert matter["referralFrom"] == EXPECTED_REFERRER
    assert matter["representationMode"] == "Joint Retainer"
    assert matter["jointEngagementDocument"] == EXPECTED_RETAINER_REL

    parties = matter["parties"]
    assert len(parties) == 5
    party_by_id = {p["partyId"]: p for p in parties}
    assert set(party_by_id.keys()) == {
        "MP_megatech_01",
        "MP_megatech_02",
        "MP_megatech_03",
        "MP_megatech_04",
        "MP_megatech_05",
    }
    assert party_by_id["MP_megatech_01"]["clientId"] == "MEGA"
    assert party_by_id["MP_megatech_02"]["clientId"] == "HAMI"
    assert party_by_id["MP_megatech_05"]["partyName"] == EXPECTED_REFERRER
    assert party_by_id["MP_megatech_05"]["partyRole"] == "Referrer & Tax Adviser"

    # 4. Verify No Client Cap-Table Records in Excel Corporate Tables
    corp_entities_excel = excel_repo._read_table_rows(TBL_CORP_ENTITIES)
    corp_rels_excel = excel_repo._read_table_rows(TBL_CORP_RELATIONSHIPS)
    corp_txns_excel = excel_repo._read_table_rows(TBL_CORP_TRANSACTIONS)
    for row in corp_entities_excel:
        legal_name = str(row.get(sc.COL_CORP_LEGAL_NAME) or "").upper()
        assert "MEGATECH" not in legal_name
        assert "HAMILTON" not in legal_name
        assert str(row.get(sc.COL_CORP_CLIENT_ID) or "").upper() not in ("MEGA", "HAMI")
    for row in corp_rels_excel:
        assert not str(row.get("RelationshipID") or "").upper().startswith("CR-MEGA")
    for row in corp_txns_excel:
        assert not str(row.get("TransactionID") or "").upper().startswith("CT-MEGA")

    # 5. Verify SQLite Migration & Parity
    proto_dir = Path.home() / ".cspm_sqlite_proto_test"
    proto_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CSPM_PROTOTYPE_ROOT", str(proto_dir))
    try:
        mig_res = perform_dry_run_migration(work_data_dir / "CSPM.xlsm")
        assert mig_res["ok"] is True

        sq = SQLiteRepository()
        sq_mega = sq.get_client_profile("MEGA")["client"]
        assert sq_mega["clientName"] == "Megatech Integrated Services Ltd."
        assert sq_mega["referredBy"] == EXPECTED_REFERRER
        assert sq_mega["kycStatus"] == "Completed"
        assert float(sq_mega["defaultBillingRate"]) == pytest.approx(475.00)

        sq_hami = sq.get_client_profile("HAMI")["client"]
        assert sq_hami["clientName"] == "Fawzia Hamilton"
        assert sq_hami["legalName"] == "HAMILTON, B-FAWZIA"
        assert sq_hami["referredBy"] == EXPECTED_REFERRER
        assert sq_hami["kycStatus"] == "Completed"

        sq_matter = sq.get_matter_profile("M_megatech_s86_2026")["matter"]
        assert sq_matter["matterNumber"] == "MEGA-CRP-26-0209"
        assert sq_matter["referredBy"] == EXPECTED_REFERRER
        assert sq_matter["jointEngagementDocument"] == EXPECTED_RETAINER_REL
        assert len(sq_matter["parties"]) == 5
        sq_mp5 = next(p for p in sq_matter["parties"] if p["partyId"] == "MP_megatech_05")
        assert sq_mp5["partyName"] == EXPECTED_REFERRER
        assert sq_mp5["partyRole"] == "Referrer & Tax Adviser"

        sq_corp_entities = sq.list_corp_entities()
        assert [e["EntityID"] for e in sq_corp_entities] == ["CE-CSLPC-2026"]
    finally:
        close_connection()
        shutil.rmtree(proto_dir, ignore_errors=True)


def test_workstation_agnostic_onedrive_retainer_attachment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify MatterDocumentService discovers and rebases OneDrive paths across different workstation folder names."""
    fake_onedrive = tmp_path / "OneDrive - WorkStationB"
    intake_dir = fake_onedrive / "Clients (CS)" / "Megatech" / "01 - Client Intake, Retainer & KYC"
    intake_dir.mkdir(parents=True, exist_ok=True)
    retainer_pdf = intake_dir / "2026-10-16 Joint Retainer Agreement - Reorganization - Signed.pdf"

    repo_governed_copy = REPO_ROOT / "data" / EXPECTED_RETAINER_REL
    if repo_governed_copy.exists():
        shutil.copy2(repo_governed_copy, retainer_pdf)
    else:
        retainer_pdf.write_bytes(b"%PDF-1.7 signed joint retainer test bytes")

    monkeypatch.setenv("OneDriveCommercial", str(fake_onedrive))
    shared_dir = tmp_path / "shared_data"
    local_dir = tmp_path / "local_data"
    svc = MatterDocumentService(shared_data_dir=shared_dir, local_data_dir=local_dir)

    discovered = svc.find_onedrive_file(
        "Clients (CS)/Megatech/01 - Client Intake, Retainer & KYC/"
        "2026-10-16 Joint Retainer Agreement - Reorganization - Signed.pdf"
    )
    assert discovered is not None
    assert discovered.resolve() == retainer_pdf.resolve()

    attach_res = svc.attach_agreement(
        "Clients (CS)/Megatech/01 - Client Intake, Retainer & KYC/"
        "2026-10-16 Joint Retainer Agreement - Reorganization - Signed.pdf",
        matter_number="MEGA-CRP-26-0209",
        matter_name="Corporate Reorganization",
    )
    rel_ref = attach_res["DocumentPath"]
    assert rel_ref.startswith("Matter_Documents/MEGA-CRP-26-0209/2026-10-16 Joint Retainer Agreement - Reorganization - Signed--")
    resolved = svc.resolve(rel_ref)
    assert resolved is not None and resolved.exists()
    if repo_governed_copy.exists():
        assert rel_ref == EXPECTED_RETAINER_REL
        assert hashlib.sha256(resolved.read_bytes()).hexdigest() == EXPECTED_RETAINER_SHA256
