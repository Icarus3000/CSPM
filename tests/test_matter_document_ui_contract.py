from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_matter_editor_exposes_real_attachment_controls_for_all_matters() -> None:
    qml = (ROOT / "src/qml/views/PlaceholderSubmenuView.qml").read_text(
        encoding="utf-8"
    )

    assert 'import QtQuick.Dialogs' in qml
    assert 'title: "Attach retainer or engagement agreement"' in qml
    assert 'label: "Retainer / engagement agreement"' in qml
    assert 'text: "Attach"' in qml
    assert 'text: "Open"' in qml
    assert 'text: "Clear"' in qml
    assert '"engagementDocumentSourcePath": root.matterEngagementDocumentSourcePath' in qml
    assert 'label: "Joint engagement document"' not in qml
    assert qml.count('label: "Retainer / engagement agreement"') == 1


def test_matter_save_copies_attachment_before_linking_workbook_record() -> None:
    controller = (ROOT / "src/python/backend/app_controller.py").read_text(
        encoding="utf-8"
    )

    lease = controller.index("self._sync_service.assert_write_lease()")
    attach = controller.index("self._matter_document_service().attach_agreement(", lease)
    save = controller.index("self._excel_repo.save_matter_profile(matter_payload)", attach)

    assert lease < attach < save
    assert 'matter_payload["jointEngagementDocument"] = attachment["DocumentPath"]' in controller
    assert "def openMatterDocument" in controller
