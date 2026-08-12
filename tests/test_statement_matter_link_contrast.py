from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATEMENT_VIEW = (
    ROOT / "src" / "qml" / "views" / "StatementOfAccountView.qml"
).read_text(encoding="utf-8")


def test_dark_mode_matter_links_override_qt_default_link_colour_only_in_dark_mode():
    assert "readonly property bool darkTheme: SemanticTheme.isDarkMode(root.t)" in STATEMENT_VIEW
    assert 'readonly property string darkMatterLinkColor: "#93C5FD"' in STATEMENT_VIEW
    assert "root.darkTheme ? \"<font color=\\\"\" + root.darkMatterLinkColor" in STATEMENT_VIEW
    assert 'root.darkTheme ? "</font>" : ""' in STATEMENT_VIEW
