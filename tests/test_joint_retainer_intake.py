from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo, TBL_TIME
from services.invoice_draft_service import InvoiceDraftService
from services.paths import AppPaths


def _repo(tmp_path: Path) -> ExcelRepo:
    repo = ExcelRepo(AppPaths(root=tmp_path, override_data_dir=tmp_path))
    repo.ensure_schema()
    return repo


def _save_individual(repo: ExcelRepo, name: str, email: str, address: str) -> str:
    saved = repo.save_client_profile(
        {
            "clientName": name,
            "legalName": name,
            "displayName": name,
            "entityType": "Individual",
            "primaryEmail": email,
            "addressLine1": address,
            "city": "Toronto",
            "stateProvince": "ON",
            "postalCode": "M1M 1M1",
            "country": "Canada",
            "status": "Active",
        }
    )
    assert saved["ok"]
    return str(saved["clientId"])


def test_joint_retainer_keeps_client_identity_independent_and_requires_bill_to_choice(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    alex_id = _save_individual(repo, "Alex Britton", "alex@example.test", "10 First Avenue")
    blair_id = _save_individual(repo, "Blair Britton", "blair@example.test", "20 Second Avenue")

    saved = repo.save_matter_profile(
        {
            "clientId": alex_id,
            "clientName": "Alex Britton",
            "matterName": "Corporate Reorganization",
            "displayName": "Britton Corporate Reorganization",
            "practiceArea": "Corporate / Commercial",
            "matterType": "Corporate Reorganization",
            "dateOfEngagement": "2026-08-10",
            "dateOpened": "2026-08-12",
            "representationMode": "Joint Retainer",
            "jointNoConfidentialityConfirmed": True,
            "jointInstructionsRequireAll": True,
            "jointEngagementDocument": "C:/engagement.pdf",
            "parties": [
                {
                    "clientId": alex_id,
                    "clientName": "Alex Britton",
                    "role": "Joint client",
                    "isFileAnchor": True,
                    "isBillingRecipient": True,
                },
                {
                    "clientId": blair_id,
                    "clientName": "Blair Britton",
                    "role": "Joint client",
                    "isBillingRecipient": True,
                },
            ],
        }
    )

    assert saved["ok"]
    assert saved["partyCount"] == 2
    matter_id = str(saved["matterId"])
    profile = repo.get_matter_profile(matter_id)["matter"]
    assert profile["isJointRetainer"] is True
    assert profile["clientId"] == alex_id
    assert profile["parentId"] == ""
    assert [(party["clientId"], party["role"]) for party in profile["parties"]] == [
        (alex_id, "Joint client"),
        (blair_id, "Joint client"),
    ]

    # The directory records retain separate contact details; the only link is
    # through the matter party relationship.
    assert repo.get_client_profile(alex_id)["client"]["fullAddress"].startswith("10 First Avenue")
    assert repo.get_client_profile(blair_id)["client"]["fullAddress"].startswith("20 Second Avenue")

    repo._write_table_rows(
        TBL_TIME,
        [
            {
                sc.COL_TIME_ENTRY_ID: "TIME-JOINT-1",
                sc.COL_TIME_DATE: "2026-08-12",
                sc.COL_TIME_CLIENT_ID: alex_id,
                sc.COL_TIME_MATTER_ID: matter_id,
                sc.COL_TIME_DESC: "Initial reorganization review",
                sc.COL_TIME_HOURS: 1.0,
                sc.COL_TIME_RATE: 475.0,
                sc.COL_TIME_SHARE_PCT: 100.0,
                sc.COL_TIME_STATUS: "Draft",
            }
        ],
    )
    options = repo.list_invoice_bill_to_options(["TIME-JOINT-1"])
    assert [option["clientId"] for option in options] == [alex_id, blair_id]

    service = InvoiceDraftService(repo)
    try:
        service.create_draft(alex_id, "Alex Britton", ["TIME-JOINT-1"])
    except ValueError as exc:
        assert "Select a bill-to client" in str(exc)
    else:
        raise AssertionError("Joint invoice draft was created without selecting a bill-to client")

    draft_num = service.create_draft(
        alex_id,
        "Alex Britton",
        ["TIME-JOINT-1"],
        billing_recipient=options[1],
    )
    draft = service.get_draft(draft_num)
    snapshot = json.loads(draft[sc.COL_DRAFT_BILL_TO_SNAPSHOT])
    assert snapshot["clientId"] == blair_id
    assert snapshot["fullAddress"].startswith("20 Second Avenue")

    assert service.finalize_draft(draft_num, "26-0999", str(tmp_path)) is True
    invoice_log = repo._read_table_rows(sc.TBL_INVOICE_LOG)
    finalized = next(row for row in invoice_log if row[sc.COL_INV_INVOICE_NUM] == "26-0999")
    assert finalized[sc.COL_INV_CLIENT_NAME] == "Blair Britton"
    assert json.loads(finalized[sc.COL_INV_BILL_TO_SNAPSHOT])["clientId"] == blair_id


def test_joint_retainer_rejects_parent_billing_link_and_duplicate_party(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    alex_id = _save_individual(repo, "Alex Britton", "alex@example.test", "10 First Avenue")
    blair_id = _save_individual(repo, "Blair Britton", "blair@example.test", "20 Second Avenue")
    payload = {
        "clientId": alex_id,
        "clientName": "Alex Britton",
        "matterName": "Joint Work",
        "dateOpened": "2026-08-12",
        "representationMode": "Joint Retainer",
        "parties": [
            {"clientId": alex_id, "clientName": "Alex Britton", "isFileAnchor": True},
            {"clientId": alex_id, "clientName": "Alex Britton"},
        ],
    }
    try:
        repo.save_matter_profile(payload)
    except ValueError as exc:
        assert "only once" in str(exc)
    else:
        raise AssertionError("Duplicate party was accepted")

    payload["parties"][1] = {"clientId": blair_id, "clientName": "Blair Britton"}
    payload["parentName"] = "Not a joint-client relationship"
    try:
        repo.save_matter_profile(payload)
    except ValueError as exc:
        assert "cannot use a Billing Client relationship" in str(exc)
    else:
        raise AssertionError("Parent billing link was accepted for a joint retainer")


def test_matter_profile_panel_uses_the_refreshed_joint_profile_rows() -> None:
    """The panel must not retain a directory-row snapshot after a full profile load."""
    workspace = (PROJECT_ROOT / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(
        encoding="utf-8"
    )
    panel = (PROJECT_ROOT / "src" / "qml" / "views" / "placeholder" / "MatterProfilePanel.qml").read_text(
        encoding="utf-8"
    )

    assert "property var matterProfileRows: []" in workspace
    assert "selectedMatterProfile = loaded\n            refreshMatterProfileRows()" in workspace
    assert "function refreshMatterProfileRows()" in workspace
    assert "model: root.matterProfileRows" in panel
