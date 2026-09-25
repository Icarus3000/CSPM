from pathlib import Path


def test_time_docket_exposes_a_prefilled_flat_fee_path():
    root = Path(__file__).resolve().parents[1]
    time_view = (root / "src" / "qml" / "views" / "TimeDocketView.qml").read_text(
        encoding="utf-8"
    )
    fee_panel = (root / "src" / "qml" / "views" / "FeeDocketEntryPanel.qml").read_text(
        encoding="utf-8"
    )

    assert 'function openFlatFeeEntrySubwindow()' in time_view
    assert 'text: root.activeIsFeeDocket() ? "Time Entry" : "Flat Fee"' in time_view
    assert 'feeDocketEntryPanel.prefillFromTimeEntry(' in time_view
    assert 'function prefillFromTimeEntry(dateText, clientText, matterText, descriptionText)' in fee_panel
    assert 'root.activeSubwindowId = "B02"' in time_view


def test_wip_rows_never_render_identity_columns_as_empty_text():
    root = Path(__file__).resolve().parents[1]
    wip_view = (root / "src" / "qml" / "views" / "WIPBillingWizardView.qml").read_text(
        encoding="utf-8"
    )

    assert 'item.date || "Date unavailable"' in wip_view
    assert 'item.clientName || item.clientId || "Client unavailable"' in wip_view
    assert 'item.matterName || item.matterId || "No matter"' in wip_view
    assert 'item.description || "Client disbursement"' in wip_view
