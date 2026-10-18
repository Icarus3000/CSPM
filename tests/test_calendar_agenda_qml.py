"""Exercise the real calendar agenda with synthetic data and no WebEngine/network."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_calendar_agenda_scrolls_all_events_and_preserves_startup_gates():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       QT_QUICK_CONTROLS_STYLE="Basic", QSG_RENDER_LOOP="basic", PYTHONFAULTHANDLER="1")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--probe"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Calendar agenda checks passed" in result.stdout


def test_home_uses_calendar_snapshot_without_the_docket_keyword_queue():
    home = (ROOT / "src/qml/components/DailyOperationsHome.qml").read_text(encoding="utf-8")
    assert "CalendarAgendaPanel {" in home
    assert "queueRowLimit" not in home
    assert "priorityItems()" not in home
    assert 'onPracticeBriefingRequested: root.openScreenRequested("home", "H01")' in home
    assert "applyPreparedStartupBriefing()" in home
    assert "startupSnapshotApplied" in home
    assert '"label": "Deadline risk"' in home


def run_probe():
    from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QPointF, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest

    application = QGuiApplication([])
    engine = QQmlEngine()
    components = []
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))

    class CalendarController(QObject):
        snapshotChanged = Signal()
        configurationChanged = Signal()
        busyChanged = Signal()

        def __init__(self):
            super().__init__()
            self.refresh_count = 0
            self.connect_count = 0
            self.disconnect_count = 0
            self.cancel_count = 0
            self._busy = False
            self.toggles = []
            self.links = []
            self.saved = []
            self._configuration = {
                "clientId": "00000000-0000-0000-0000-000000000001",
                "tenantId": "organizations", "accountEmail": "test@example.com",
                "timeZone": "America/Toronto", "disabledCalendarIds": [],
                "holidaySources": {"CA": True, "US": True, "JEWISH": True},
            }
            events = [{
                "id": str(index), "title": f"Meeting {index}",
                "start": "2026-10-13T14:30:00-04:00", "end": "2026-10-13T15:15:00-04:00",
                "date": "2026-10-13", "allDay": False, "kind": "appointment",
                "sourceCalendars": ["Main calendar", "Shared calendar"], "location": "Office",
                "webUrl": "https://outlook.office.com/calendar/item/example", "isCurrent": index == 0,
            } for index in range(11)]
            self._snapshot = {
                "state": "ready", "message": "", "accountEmail": "test@example.com",
                "asOf": "2026-10-13T13:45:00-04:00", "timeZone": "America/Toronto",
                "today": events,
                "next7Days": [{"id": "holiday", "title": "Holiday", "date": "2026-10-15",
                               "allDay": True, "sourceCalendars": ["Canadian holidays"], "kind": "holiday"},
                              {"id": "later", "title": "Later meeting", "date": "2026-10-16",
                               "start": "2026-10-16T14:00:00-04:00", "end": "2026-10-16T15:00:00-04:00",
                               "allDay": False, "sourceCalendars": ["Main calendar"], "kind": "appointment"}],
                "calendars": [{"id": "main", "name": "Main calendar", "owner": "test@example.com", "enabled": True},
                              {"id": "holidays:JEWISH", "name": "Jewish holidays", "provider": "Hebcal.com", "source": "holiday"}],
                "stale": False, "errors": [], "signInCode": "EXAMPLE12",
                "signInUrl": "https://microsoft.com/devicelogin",
            }

        @Property("QVariantMap", notify=snapshotChanged)
        def snapshot(self):
            return self._snapshot

        @Property("QVariantMap", notify=configurationChanged)
        def configuration(self):
            return self._configuration

        @Property(bool, notify=busyChanged)
        def busy(self):
            return self._busy

        @Slot()
        def refresh(self):
            self.refresh_count += 1

        @Slot("QVariantMap", result=bool)
        def saveConfiguration(self, payload):
            self.saved.append(payload)
            self._configuration = payload
            self.configurationChanged.emit()
            return True

        @Slot()
        def connectAccount(self):
            self.connect_count += 1

        @Slot()
        def disconnectAccount(self):
            self.disconnect_count += 1

        @Slot()
        def cancelConnection(self):
            self.cancel_count += 1

        @Slot(str, bool)
        def setCalendarEnabled(self, calendar_id, enabled):
            self.toggles.append((calendar_id, enabled))

        @Slot(str, result=bool)
        def openEventLink(self, link):
            self.links.append(link)
            return True

        @Slot(str, result=bool)
        def copyToClipboard(self, text):
            cleaned = str(text or "").strip()
            if not cleaned:
                return False
            QGuiApplication.clipboard().setText(cleaned)
            return True

    class AppRef(QObject):
        startupReadinessChanged = Signal()

        def __init__(self, controller):
            super().__init__()
            self.controller = controller
            self.readiness = "phase1-loading"

        @Property(QObject, constant=True)
        def calendarController(self):
            return self.controller

        @Property(bool, constant=True)
        def backendBooted(self):
            return True

        @Property(str, notify=startupReadinessChanged)
        def startupReadinessState(self):
            return self.readiness

        @Property(bool, constant=True)
        def startupBriefingSnapshotReady(self):
            return True

        @Property("QVariantMap", constant=True)
        def startupBriefingSnapshot(self):
            return {"ok": True, "todaysTasks": [], "recentWork": [], "overdueDeadlines": [],
                    "upcomingDeadlines": [], "readyToBillMatters": []}

    def create(name, properties):
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "src/qml/components" / name)))
        components.append(component)
        assert component.isReady(), component.errorString()
        item = component.createWithInitialProperties(properties)
        assert item is not None, component.errorString()
        item.setParent(engine)
        return item

    def evaluate(item, source):
        expression = QQmlExpression(QQmlEngine.contextForObject(item), item, source)
        value = expression.evaluate()
        assert not expression.hasError(), expression.error().toString()
        value = value[0] if isinstance(value, tuple) else value
        return value.toVariant() if hasattr(value, "toVariant") else value

    def visual_child(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            result = visual_child(child, name)
            if result is not None:
                return result
        return None

    try:
        controller = CalendarController()
        app_ref = AppRef(controller)
        window = QQuickWindow()
        window.resize(960, 680)
        panel = create("CalendarAgendaPanel.qml", {"width": 620, "height": 350, "appRef": app_ref})
        panel.setParentItem(window.contentItem())
        application.processEvents()
        evaluate(panel, "requestInitialRefresh()")
        QTest.qWait(700)
        assert controller.refresh_count == 0, "Hidden startup must not perform network work"
        app_ref.readiness = "ready-to-reveal"
        app_ref.startupReadinessChanged.emit()
        QTest.qWait(700)
        assert controller.refresh_count == 0, "Prepared hidden home must still wait for visibility"
        window.show()
        panel.setProperty("interactive", False)
        QTest.qWait(700)
        assert controller.refresh_count == 0, "Non-interactive startup must not refresh"
        panel.setProperty("interactive", True)
        QTest.qWait(700)
        assert controller.refresh_count == 1
        evaluate(panel, "requestInitialRefresh()")
        assert controller.refresh_count == 1, "Visibility should trigger only one initial refresh"
        assert evaluate(panel, "events.length") == 11
        agenda_list = panel.findChild(QObject, "calendarAgendaList")
        assert agenda_list.property("count") == 11
        assert agenda_list.property("contentHeight") > agenda_list.property("height")
        evaluate(agenda_list, "positionViewAtEnd()")
        application.processEvents()
        assert agenda_list.property("contentY") > 0, "Meetings beyond the first four must be reachable"
        assert evaluate(panel, "eventTimeLabel(events[0])") == "Now · 2:30 PM – 3:15 PM"
        assert evaluate(panel, "sourceLabel(events[0])") == "Main calendar · Shared calendar"
        assert evaluate(panel, 'dateLabel("2026-10-15")') == "Thu, Oct 15"
        panel.setProperty("selectedHorizon", 1)
        application.processEvents()
        assert evaluate(panel, "events.length") == 2
        assert evaluate(panel, "eventTimeLabel(events[0])") == "All day"
        assert agenda_list.property("count") == 2
        headers = [header.property("text") for header in agenda_list.findChildren(QObject, "calendarDateHeader")]
        assert headers == ["Thu, Oct 15", "Fri, Oct 16"], headers
        # The compact home can allocate roughly 350 px to this panel. Its
        # actions must remain inside the card without losing the refresh button.
        panel.setProperty("compact", True)
        for narrow_width in (500, 350):
            panel.setProperty("width", narrow_width)
            QTest.qWait(80)
            for action_name in ("calendarManageButton", "calendarRefreshButton", "calendarHorizon0", "calendarHorizon1"):
                action = visual_child(panel, action_name)
                assert action is not None, action_name
                position = action.mapToItem(panel, QPointF(0, 0))
                assert position.x() >= 9, (action_name, position.x())
                assert position.x() + action.property("width") <= narrow_width - 9, (action_name, position.x(), action.property("width"))
                assert action.property("height") >= 27
        panel.setProperty("width", 620)
        panel.setProperty("compact", False)
        timestamp = panel.findChild(QObject, "calendarRefreshTimestamp")
        assert timestamp.property("text") == "Updated 1:45 PM · America/Toronto"
        evaluate(panel, "refreshAgenda()")
        assert controller.refresh_count == 2

        assert panel.findChild(QObject, "calendarConnectionDialog") is None
        application.clipboard().setText("")
        evaluate(panel, "openConnectionSettings()")
        QTest.qWait(100)
        dialog = panel.findChild(QObject, "calendarConnectionDialog")
        assert dialog is not None, "Management dialog remains available from the panel"
        assert dialog.property("visible") is True
        assert application.clipboard().text() == "EXAMPLE12"
        assert dialog.property("signInCodeCopied") is True
        copied_label = dialog.findChild(QObject, "calendarSignInCodeCopiedLabel")
        assert copied_label is not None and copied_label.property("visible") is True
        assert "Copied to clipboard" in copied_label.property("text")
        controller._snapshot["signInCode"] = "F5CHSERFA"
        controller.snapshotChanged.emit()
        application.processEvents()
        assert application.clipboard().text() == "F5CHSERFA"
        evaluate(dialog, "loadConfiguration()")
        field = dialog.findChild(QObject, "calendarAccountEmailField")
        assert field.property("text") == "test@example.com"
        canada = dialog.findChild(QObject, "calendarCanadaHolidays")
        canada.setProperty("checked", False)
        evaluate(dialog, "connectCalendarAccount()")
        assert controller.connect_count == 1
        assert controller.saved[-1]["holidaySources"] == {"CA": False, "US": True, "JEWISH": True}
        assert controller.saved[-1]["tenantId"] == "organizations"
        controller._configuration["disabledCalendarIds"] = ["holidays:CA", "shared"]
        controller.configurationChanged.emit()
        evaluate(dialog, "loadConfiguration()")
        assert canada.property("checked") is False
        canada.setProperty("checked", True)
        assert evaluate(dialog, "saveSettings()") is True
        assert controller.saved[-1]["holidaySources"]["CA"] is True
        assert controller.saved[-1]["disabledCalendarIds"] == ["shared"], "Re-enabled holidays must not stay hidden by the legacy calendar-ID setting"
        evaluate(dialog, 'setCalendarSelected("shared", false)')
        assert controller.toggles == [("shared", False)]
        application.clipboard().setText("OVERWRITTEN")
        evaluate(dialog, "openMicrosoftSignIn()")
        assert controller.links == ["https://microsoft.com/devicelogin"]
        assert application.clipboard().text() == "F5CHSERFA"
        evaluate(dialog, "disconnectCalendarAccount()")
        assert controller.disconnect_count == 1
        controller._busy = True
        controller.busyChanged.emit()
        controller._snapshot["state"] = "signing-in"
        controller.snapshotChanged.emit()
        application.processEvents()
        assert dialog.property("hasAccount") is False
        cancel_button = dialog.findChild(QObject, "calendarCancelSignInButton")
        assert cancel_button.property("visible") is True
        assert cancel_button.property("enabled") is True
        assert dialog.findChild(QObject, "calendarConnectAccountButton").property("enabled") is False
        assert dialog.findChild(QObject, "calendarSaveSettingsButton").property("enabled") is False
        assert panel.findChild(QObject, "calendarRefreshButton").property("enabled") is False
        evaluate(dialog, "cancelSignIn()")
        assert controller.cancel_count == 1
        controller._busy = False
        controller.busyChanged.emit()
        controller._snapshot["state"] = "disconnected"
        controller.snapshotChanged.emit()
        application.processEvents()
        assert dialog.property("hasAccount") is False
        disconnect_button = dialog.findChild(QObject, "calendarDisconnectAccountButton")
        assert disconnect_button.property("enabled") is True
        assert panel.property("hasAccount") is False
        evaluate(dialog, "close()")

        # Errors and an in-progress refresh retain the last successful agenda
        # and mark it as last known, rather than presenting an empty fresh list.
        controller._snapshot.update(state="error", stale=True, message="One calendar could not be refreshed.")
        controller.snapshotChanged.emit()
        application.processEvents()
        assert agenda_list.property("count") == 2
        assert disconnect_button.property("enabled") is True, "Authentication errors must allow clearing the saved session"
        assert "Last known" in timestamp.property("text")
        assert panel.findChild(QObject, "calendarAgendaStatus").property("text") == "One calendar could not be refreshed."
        controller._busy = True
        controller.busyChanged.emit()
        application.processEvents()
        assert agenda_list.property("count") == 2
        assert panel.findChild(QObject, "calendarAgendaStatus").property("text") == "Refreshing calendars…"

        # Older synthetic fixtures have no calendar controller; the home still
        # consumes its prepared briefing snapshot and the panel has a safe empty state.
        absent = create("CalendarAgendaPanel.qml", {"width": 500, "height": 230})
        absent.setParentItem(window.contentItem())
        assert evaluate(absent, "events.length") == 0
        assert evaluate(absent, "refreshAllowed") is False
        assert "unavailable" in evaluate(absent, "statusLabel()")
        home = create("DailyOperationsHome.qml", {"width": 1100, "height": 760, "appRef": app_ref, "interactive": False})
        assert home.property("startupSnapshotApplied") is True
        assert home.findChild(QObject, "dailyCalendarAgenda") is not None
        evaluate(home, 'var updated = Object.assign({}, briefing); updated.todaysTasks = '
                 '[{kind:"deadline",date:localTodayIso(),description:"Filing deadline"},'
                 '{kind:"meeting",date:localTodayIso(),description:"Recorded consultation"},'
                 '{kind:"meeting",date:localTodayIso(),description:"Flat-fee summary with client meetings"}]; '
                 'briefing = updated')
        assert evaluate(home, "currentDayItems().length") == 1
        assert evaluate(home, 'currentDayItems()[0].description') == "Filing deadline"
        assert evaluate(home, "dailyMetrics[0].value") == "1"
        assert evaluate(home, "dailyMetrics[0].detail") == "0 overdue · 1 today"
        application.processEvents()
        errors = [message for message in messages if any(term in message for term in (
            "TypeError", "ReferenceError", "binding loop", "Binding loop", "Unable to assign", "Cannot assign", "Cannot read"))]
        assert not errors, "\n".join(errors)
        print("Calendar agenda checks passed")
        window.close()
        home.deleteLater()
        absent.deleteLater()
        panel.deleteLater()
        application.processEvents()
    finally:
        qInstallMessageHandler(None)
        # Destroy the engine while synthetic QObject providers and the GUI
        # application still exist; Python's local teardown order is otherwise
        # unsafe for QML property bindings that observe those providers.
        from shiboken6 import delete
        delete(engine)
        delete(window)


if __name__ == "__main__":
    run_probe()
