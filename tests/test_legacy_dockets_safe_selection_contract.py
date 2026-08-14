from pathlib import Path


def test_review_grid_can_select_only_new_dockets_and_their_required_setup():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "qml" / "views" / "AnalysisReviewGridWindow.qml").read_text(
        encoding="utf-8"
    )

    assert 'text: "Select Safe Docket Update"' in source
    assert "function selectSafeDocketUpdate()" in source
    assert 'String(docket.sheet || "") !== "Dockets"' in source
    assert "docket.safeDocketCandidate !== true" in source
    assert 'String(matter.sheet || "") !== "Matters"' in source
    assert 'String(client.sheet || "") !== "Clients"' in source
    assert 'sourceText(docket, "Matter_ID")' in source
    assert 'sourceText(matter, "Client_ID")' in source
    assert "No financial or unrelated legacy rows are selected." in source
    assert "SAFE DOCKET UPDATE READY" in source
    assert 'text: "WIP"' in source


def test_safe_docket_selection_remains_an_explicit_user_choice():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "qml" / "views" / "AnalysisReviewGridWindow.qml").read_text(
        encoding="utf-8"
    )

    # The selection helper prepares the review grid only. The existing
    # Import Selected Data click remains the sole path that starts an import.
    helper_start = source.index("function selectSafeDocketUpdate()")
    helper_end = source.index("\n    function refreshMetrics()", helper_start)
    helper = source[helper_start:helper_end]
    assert "startFilteredImport" not in helper
    assert "gridWindow.importView.startFilteredImport(allowedRows)" in source
