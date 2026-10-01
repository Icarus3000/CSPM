from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject

sys.path.append(str(Path(__file__).resolve().parents[1] / "src" / "python"))

from backend.app_controller import AppController
from repositories.excel_repo import ExcelRepo
from services.matter_document_service import MatterDocumentService
from services.paths import AppPaths


def _controller(paths, repo, write_guard=lambda: None):
    controller = AppController.__new__(AppController)
    QObject.__init__(controller)
    controller._paths = paths
    controller._excel_repo = repo
    controller._sync_service = SimpleNamespace(assert_write_lease=write_guard)
    controller._report_failure = lambda *args, **kwargs: None
    return controller


@pytest.mark.parametrize("joint", [False, True])
def test_saved_agreement_survives_workbook_reload_and_another_pc(tmp_path, joint):
    paths = AppPaths(root=tmp_path, override_data_dir=tmp_path / "local",
                     override_master_dir=tmp_path / "shared")
    repo = ExcelRepo(paths)
    repo.ensure_schema()
    clients = []
    for name in ["First Client", "Second Client"]:
        result = repo.save_client_profile({"clientName": name, "legalName": name,
                                          "entityType": "Individual", "status": "Active"})
        assert result["ok"]
        clients.append({"clientId": result["clientId"], "clientName": name})
    source = tmp_path / "Signed Retainer.pdf"
    source.write_bytes(b"%PDF-1.7 signed agreement")
    payload = {"clientName": clients[0]["clientName"], "matterName": "Engagement",
               "matterNumber": "RET-26-0001", "matterType": "General",
               "dateOpened": "2026-10-01", "engagementDocumentSourcePath": source.as_uri()}
    if joint:
        payload.update(representationMode="Joint Retainer", jointNoConfidentialityConfirmed=True,
                       parties=[dict(clients[0], isFileAnchor=True, isBillingRecipient=True),
                                dict(clients[1], isBillingRecipient=True)])
    controller = _controller(paths, repo)
    result = controller.saveMatterProfile(payload)
    assert result["ok"]
    assert payload["engagementDocumentSourcePath"] == source.as_uri()
    reopened = ExcelRepo(paths).get_matter_profile(result["matterId"])["matter"]
    assert reopened["jointEngagementDocument"] == result["engagementDocument"]
    assert reopened["isJointRetainer"] is joint
    stored = controller._matter_document_service().resolve(result["engagementDocument"])
    assert stored.read_bytes() == source.read_bytes()

    # OneDrive gives another computer a different root, with the same relative file.
    other = tmp_path / "other-pc"
    other_file = other / result["engagementDocument"]
    other_file.parent.mkdir(parents=True)
    other_file.write_bytes(stored.read_bytes())
    paths.override_master_dir = other
    resolved = controller._matter_document_service().resolve(reopened["jointEngagementDocument"])
    assert resolved == other_file.resolve()
    assert MatterDocumentService.sha256(resolved) == result["engagementDocumentHash"]

    cleared = controller.saveMatterProfile(dict(
        payload, matterId=result["matterId"], engagementDocumentSourcePath="",
        jointEngagementDocument="",
    ))
    assert cleared["ok"]
    assert ExcelRepo(paths).get_matter_profile(result["matterId"])["matter"][
        "jointEngagementDocument"
    ] == ""
    assert stored.read_bytes() == source.read_bytes()
    assert other_file.read_bytes() == source.read_bytes()


def test_read_only_session_refuses_attachment_before_any_copy_or_workbook_write(tmp_path):
    paths = AppPaths(root=tmp_path, override_data_dir=tmp_path / "local")
    calls = []
    repo = SimpleNamespace(save_matter_profile=lambda payload: calls.append(payload))

    def deny():
        raise PermissionError("This session is read-only.")

    controller = _controller(paths, repo, deny)
    source = tmp_path / "retainer.pdf"
    source.write_bytes(b"agreement")
    result = controller.saveMatterProfile({"engagementDocumentSourcePath": str(source)})
    assert not result["ok"]
    assert "read-only" in result["message"]
    assert not calls
    assert not (paths.data_dir() / "Matter_Documents").exists()


def test_failed_workbook_save_reports_failure_and_preserves_source_for_retry(tmp_path):
    paths = AppPaths(root=tmp_path, override_data_dir=tmp_path / "local")

    def fail(payload):
        raise OSError("Workbook is locked.")

    controller = _controller(paths, SimpleNamespace(save_matter_profile=fail))
    source = tmp_path / "retainer.pdf"
    source.write_bytes(b"signed agreement")
    payload = {"engagementDocumentSourcePath": str(source), "matterNumber": "M-1"}
    result = controller.saveMatterProfile(payload)
    assert not result["ok"]
    assert "locked" in result["message"]
    assert payload["engagementDocumentSourcePath"] == str(source)
    assert source.read_bytes() == b"signed agreement"
