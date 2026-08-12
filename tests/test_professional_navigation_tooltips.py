from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_RAIL = (
    ROOT / "src" / "qml" / "components" / "ProfessionalModuleRail.qml"
).read_text(encoding="utf-8")


def test_module_rail_tooltip_is_suppressed_when_opening_a_flyout():
    assert "property bool tooltipSuppressed: false" in MODULE_RAIL
    assert "onPressed: function(mouse)" in MODULE_RAIL
    assert "railButton.tooltipSuppressed = true" in MODULE_RAIL
    assert "onExited: railButton.tooltipSuppressed = false" in MODULE_RAIL
    assert "&& !railButton.tooltipSuppressed" in MODULE_RAIL
    assert "&& !railButton.flyoutActive" in MODULE_RAIL
