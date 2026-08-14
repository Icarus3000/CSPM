from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
THEME_SOURCE = (REPO_ROOT / "src" / "qml" / "standards" / "SemanticTheme.js").read_text(
    encoding="utf-8"
)
WIP_SOURCE = (REPO_ROOT / "src" / "qml" / "views" / "WIPBillingWizardView.qml").read_text(
    encoding="utf-8"
)


def test_selected_table_row_has_a_defined_opaque_theme_surface_for_both_modes():
    assert "function tableSelectedBackground(theme, appStyle)" in THEME_SOURCE
    assert "isDarkMode(theme) ? 0.30 : 0.18" in THEME_SOURCE
    assert "tableRowBackground(theme, appStyle)" in THEME_SOURCE
    assert "accentPrimary(theme, appStyle)" in THEME_SOURCE


def test_wip_workbench_uses_the_shared_selected_row_theme_token():
    assert "SemanticTheme.tableSelectedBackground(root.t, root.appStyle)" in WIP_SOURCE
