"""Inspect the actual report preview header using synthetic branding only."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def evaluate(item, expression):
    script = QQmlExpression(QQmlEngine.contextForObject(item), item, expression)
    result = script.evaluate()
    assert not script.hasError(), script.error().toString()
    return result[0] if isinstance(result, tuple) else result


def document(logo, contact):
    return {
        "reportId": "statement_of_account",
        "title": "Statement of Account",
        "generatedAt": "2026-10-13 09:00",
        "filterSummary": "Billing Client: Example Company | All invoices | As of: 2026-10-13",
        "branding": {
            "firmName": "Example Law Office",
            "firmContact": contact,
            "logoUrl": logo,
        },
        "sections": [{
            "sectionId": "detail",
            "title": "Invoices",
            "columns": [{"key": "invoice", "label": "Invoice"}],
            "rows": [{"invoice": "26-0001"}],
        }],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=PROJECT_ROOT / "src/qml/components/ReportWindow.qml")
    parser.add_argument("--screenshots", type=Path)
    options = parser.parse_args()
    application = QGuiApplication([sys.argv[0]])
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(options.source.resolve())))
    assert component.status() == QQmlComponent.Ready, [
        error.toString() for error in component.errors()
    ]
    root = component.createWithInitialProperties({
        "reportDocument": document("", ""), "t": {"mode": "Light"},
    })
    assert root is not None, [error.toString() for error in component.errors()]
    assert isinstance(root, QQuickWindow)
    root.show()
    QTest.qWait(150)
    contacts = ["10 Example Street\nExample City, ON\n555-0100 | example@example.test", ""]
    results = []
    with tempfile.TemporaryDirectory(prefix="cspm-preview-logo-") as folder:
        custom_logo = Path(folder) / "custom-brand.svg"
        custom_logo.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="158" height="100">'
            '<rect width="158" height="100" fill="#E06020"/></svg>',
            encoding="utf-8",
        )
        logos = {
            "builtin": QUrl.fromLocalFile(str(PROJECT_ROOT / "assets/CS.svg")).toString(),
            "none": "",
            "custom": QUrl.fromLocalFile(str(custom_logo)).toString(),
        }
        for theme in ("Dark", "Light"):
            root.setProperty("t", {"mode": theme})
            for logo_kind, logo_url in logos.items():
                for contact in contacts:
                    root.setProperty("reportDocument", document(logo_url, contact))
                    for orientation in ("portrait", "landscape"):
                        root.setProperty("orientationMode", orientation)
                        for zoom in (0.35, 1.0, 2.6):
                            root.setProperty("zoomScale", zoom)
                            QTest.qWait(35)
                            delegate = evaluate(root, "pageList.itemAtIndex(0)")
                            assert delegate is not None, "First preview page was not created"
                            geometry = json.loads(evaluate(delegate, """
                                JSON.stringify({
                                    nameX: firmName.x, nameY: firmName.y,
                                    nameWidth: firmName.width,
                                    nameBottom: firmName.y + firmName.height,
                                    contactX: firmContact.x, contactY: firmContact.y,
                                    contactBottom: firmContact.y + firmContact.height,
                                    logoX: reportLogo.x, logoY: reportLogo.y,
                                    logoWidth: reportLogo.width,
                                    logoBottom: reportLogo.y + reportLogo.height,
                                    logoVisible: reportLogo.visible,
                                    overlayVisible: reportLogoTint.visible,
                                    brandHeight: brandBlock.height,
                                    ruleY: headerRule.y,
                                    stampBottom: generatedStamp.y + generatedStamp.height,
                                    pageNumberBottom: pageNumber.y + pageNumber.height
                                })
                            """))
                            case = {"theme": theme, "logo": logo_kind,
                                    "contact": bool(contact), "orientation": orientation,
                                    "zoom": zoom, **geometry}
                            if logo_url:
                                assert geometry["nameX"] >= geometry["logoX"] + geometry["logoWidth"] + 15, case
                                assert geometry["contactX"] == geometry["nameX"], case
                                assert abs(geometry["logoBottom"] - geometry["brandHeight"]) < 0.1, case
                                assert geometry["logoVisible"] or geometry["overlayVisible"], case
                                assert geometry["overlayVisible"] == (theme == "Dark" and logo_kind == "builtin"), case
                            else:
                                assert geometry["nameX"] == 0, case
                                assert not geometry["logoVisible"] and not geometry["overlayVisible"], case
                            assert geometry["nameWidth"] > 200, case
                            if contact:
                                assert geometry["contactY"] >= geometry["nameBottom"] + 5, case
                                assert geometry["brandHeight"] >= geometry["contactBottom"], case
                            assert geometry["ruleY"] >= max(
                                geometry["brandHeight"], geometry["stampBottom"],
                                geometry["pageNumberBottom"],
                            ) + 11, case
                            if (options.screenshots and logo_kind == "builtin"
                                    and contact and zoom == 1.0 and orientation == "portrait"):
                                options.screenshots.mkdir(parents=True, exist_ok=True)
                                QTest.qWait(100)
                                snapshot = root.grabWindow()
                                assert not snapshot.isNull(), "Preview framebuffer unavailable"
                                assert snapshot.save(str(options.screenshots / f"header_{theme.lower()}.png"))
                            results.append(case)
    root.hide()
    root.deleteLater()
    QTest.qWait(30)
    print(json.dumps({"ok": True, "cases": len(results),
                      "source": str(options.source.resolve()), "results": results}), flush=True)


if __name__ == "__main__":
    main()
