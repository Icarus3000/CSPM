"""Exercise real QML wheel delivery without WebEngine or practice data."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl, Slot
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest


class ReportBackend(QObject):
    def __init__(self):
        super().__init__()
        self.requests = []
        self.fail_next = False

    @Slot(result="QVariantMap")
    def getProductivityForecastSettings(self):
        return {"ok": True, "trendMonths": 4, "trendDays": 7}

    @Slot("QVariantMap", result="QVariantMap")
    def getProductivityReport(self, payload):
        self.requests.append(dict(payload))
        if self.fail_next:
            self.fail_next = False
            return {"ok": False, "message": "Synthetic report failure"}
        return {
            "ok": True, **payload, "generatedAt": str(len(self.requests)),
            "summary": {}, "forecast": {}, "topClients": [],
            "monthlyProduction": [{"label": f"M{i}", "amount": i + 1}
                                  for i in range(payload["trendMonths"])],
            "dailyProduction": [{"label": f"D{i}", "amount": i + 1}
                                for i in range(payload["trendDays"])],
        }


def evaluate(item, expression):
    script = QQmlExpression(QQmlEngine.contextForObject(item), item, expression)
    result = script.evaluate()
    assert not script.hasError(), script.error().toString()
    return result[0] if isinstance(result, tuple) else result


def find_chart(item, title):
    if item.property("chartTitle") == title:
        return item
    for child in item.childItems():
        result = find_chart(child, title)
        if result is not None:
            return result
    return None


def wheel_over(application, item, delta):
    # Deliver through the window, not by directly calling the QML handler.
    # This covers chart hit-testing and the Zen signal connection.
    window = item.window()
    position = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    global_position = window.mapToGlobal(position.toPoint())
    event = QWheelEvent(position, QPointF(global_position), QPoint(), QPoint(0, delta),
                        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    application.sendEvent(window, event)
    QTest.qWait(25)


def main():
    application = QGuiApplication(sys.argv)
    backend = ReportBackend()
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.resize(1280, 850)
    view.setInitialProperties({"appRef": backend, "autoGenerate": False})
    source = (Path(sys.argv[1]) if len(sys.argv) > 1 else
              Path(__file__).resolve().parents[1] /
              "src/qml/components/ProductivityReportPanel.qml")
    view.setSource(QUrl.fromLocalFile(str(source.resolve())))
    assert view.status() == QQuickView.Ready, [error.toString() for error in view.errors()]
    root = view.rootObject()
    view.show()
    evaluate(root, "generateReport()")
    QTest.qWait(80)
    monthly_inline = evaluate(root, "monthlyChartRow")
    daily_inline = evaluate(root, "dailyChartRow")
    wheel_over(application, monthly_inline, 120)
    assert root.property("trendMonths") == 5
    wheel_over(application, daily_inline, -120)
    assert root.property("trendDays") == 6

    evaluate(root, "openZenView()")
    QTest.qWait(100)
    zen = root.property("zenPanel")
    assert zen is not None
    monthly_zen = find_chart(zen, "MONTHLY PRODUCTION")
    daily_zen = find_chart(zen, "DAILY PRODUCTION")
    assert monthly_zen is not None and daily_zen is not None

    def assert_snapshot(months, days):
        assert root.property("trendMonths") == months
        assert root.property("trendDays") == days
        # QML-side assertions inspect the actual displayed snapshot and rows.
        assert evaluate(root, f"zenPanel.reportData.trendMonths === {months}")
        assert evaluate(root, f"zenPanel.reportData.trendDays === {days}")
        assert evaluate(root, f"zenPanel.monthly.length === {months}")
        assert evaluate(root, f"zenPanel.daily.length === {days}")
        assert evaluate(root, "zenPanel.statusText === statusText")
        assert evaluate(root, "zenPanel.reportData.generatedAt === reportData.generatedAt")

    assert_snapshot(5, 6)
    # Direction and one-unit steps match inline, regardless of delta magnitude.
    for title, sign, expected in [
        ("MONTHLY PRODUCTION", 120, (6, 6)),
        ("MONTHLY PRODUCTION", -120, (5, 6)),
        ("DAILY PRODUCTION", 240, (5, 7)),
        ("DAILY PRODUCTION", -240, (5, 6)),
    ]:
        wheel_over(application, find_chart(zen, title), sign)
        assert_snapshot(*expected)

    # A regular-view refresh while Zen is open must update the same display.
    wheel_over(application, monthly_inline, 120)
    assert_snapshot(6, 6)
    for property_name, title, minimum, maximum in [
        ("trendMonths", "MONTHLY PRODUCTION", 1, 12),
        ("trendDays", "DAILY PRODUCTION", 1, 14),
    ]:
        for boundary, delta in [(maximum, 120), (minimum, -120)]:
            root.setProperty(property_name, boundary)
            evaluate(root, "generateReport()")
            QTest.qWait(25)
            wheel_over(application, find_chart(zen, title), delta)
            assert_snapshot(root.property("trendMonths"), root.property("trendDays"))
            assert root.property(property_name) == boundary
    count = len(backend.requests)
    evaluate(root, "adjustTrendMonths(0)")
    evaluate(root, "adjustTrendDays(0)")
    assert len(backend.requests) == count

    backend.fail_next = True
    wheel_over(application, find_chart(zen, "MONTHLY PRODUCTION"), 120)
    assert not evaluate(root, "zenPanel.hasReport")
    assert evaluate(root, 'zenPanel.statusText === "Synthetic report failure"')
    wheel_over(application, find_chart(zen, "MONTHLY PRODUCTION"), -120)
    assert_snapshot(1, 1)

    # Close and recreate the Loader; the latest timeframe survives reopening.
    evaluate(root, "zenWindow.close()")
    QTest.qWait(30)
    evaluate(root, "openZenView()")
    QTest.qWait(80)
    assert_snapshot(1, 1)
    evaluate(root, "zenWindow.close()")
    view.close()
    print(json.dumps({"ok": True, "reportRequests": len(backend.requests),
                      "source": str(source), "realWheelDelivery": True}), flush=True)


if __name__ == "__main__":
    main()
