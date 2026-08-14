from pathlib import Path


def test_wip_workbench_exposes_audited_reconciliation_not_a_billing_shortcut():
    root = Path(__file__).resolve().parents[1]
    view = (root / "src" / "qml" / "views" / "WIPBillingWizardView.qml").read_text(encoding="utf-8")
    controller = (root / "src" / "python" / "backend" / "controllers" / "billing_controller.py").read_text(encoding="utf-8")

    assert 'text: "Reconcile Selected"' in view
    assert "does not create, alter, reverse, or pay an invoice" in view
    assert "billingBackend.reconcileWipEntries(" in view
    assert "nonZeroReconciliationAcknowledgement" in view
    assert "def reconcileWipEntries" in controller


def test_archived_matter_entry_guard_requires_separate_reopen_and_save_confirmations():
    root = Path(__file__).resolve().parents[1]
    guard = (root / "src" / "qml" / "components" / "ArchivedMatterEntryGuardDialog.qml").read_text(encoding="utf-8")
    time_view = (root / "src" / "qml" / "views" / "TimeDocketView.qml").read_text(encoding="utf-8")
    fee_view = (root / "src" / "qml" / "views" / "FeeDocketEntryPanel.qml").read_text(encoding="utf-8")
    ap_view = (root / "src" / "qml" / "views" / "AccountsPayableView.qml").read_text(encoding="utf-8")

    assert 'expectedConfirmation = "REOPEN " + (matterNumber || matterId)' in guard
    assert "appRef.reopenMatterForDocketing(matterId, entryKind, phrase)" in guard
    assert '"Confirm and save " + root.entryLabel()' in guard
    assert "ArchivedMatterEntryGuardDialog" in time_view
    assert "ArchivedMatterEntryGuardDialog" in fee_view
    assert "ArchivedMatterEntryGuardDialog" in ap_view
    assert 'label += " [Archived]"' in ap_view
    assert "root.appRef.listMatterDirectory()" in ap_view


def test_wip_and_bulk_move_preserve_selection_or_explain_a_required_removal():
    root = Path(__file__).resolve().parents[1]
    wip_view = (root / "src" / "qml" / "views" / "WIPBillingWizardView.qml").read_text(encoding="utf-8")
    bulk_move = (root / "src" / "qml" / "views" / "BulkDocketMovePanel.qml").read_text(encoding="utf-8")
    notice = (root / "src" / "qml" / "components" / "SelectionRemovalNoticeDialog.qml").read_text(encoding="utf-8")

    assert "function autoCheckFilterMatch() { }" in wip_view
    assert "selectionRemovalNotice.showRemoval" in wip_view
    assert "Select All adds the visible rows" in wip_view
    assert "selectionRemovalNotice.showRemoval" in bulk_move
    assert "closePolicy: Popup.NoAutoClose" in notice
    assert 'text: "OK"' in notice


def test_bulk_move_uses_a_monitor_centred_calendar_and_prominent_success_confirmation():
    root = Path(__file__).resolve().parents[1]
    bulk_move = (root / "src" / "qml" / "views" / "BulkDocketMovePanel.qml").read_text(encoding="utf-8")
    calendar = (root / "src" / "qml" / "components" / "JellyCalendar.qml").read_text(encoding="utf-8")

    assert 'root.openDatePicker("from", fromDateField, point.x, point.y)' in bulk_move
    assert 'root.openDatePicker("to", toDateField, point.x, point.y)' in bulk_move
    assert "hostWindow: root.Window.window" in bulk_move
    assert 'text: "Dockets moved successfully"' in bulk_move
    assert "closePolicy: Popup.NoAutoClose" in bulk_move
    assert "function _screenGeometryRect(screenObj)" in calendar
    assert "var targetScreen = _preferredScreen(px, py)" in calendar
    assert "Keep the original target monitor through native-window creation" in calendar


def test_matter_editor_exposes_a_visible_joint_selector_and_an_archive_action():
    root = Path(__file__).resolve().parents[1]
    wizard = (root / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(encoding="utf-8")

    assert 'text: "Joint retainer / multiple independent clients"' in wizard
    assert "contentItem: Text" in wizard
    assert 'text: "Archive Matter"' in wizard
    assert "function requestMatterArchive()" in wizard
    assert "function archiveMatterAfterConfirmation()" in wizard
    assert "protected re-open flow" in wizard
