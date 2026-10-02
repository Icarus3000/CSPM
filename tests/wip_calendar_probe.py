"""Exercise the real calendar-to-workbench signal and live range filtering."""
import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

app = QGuiApplication([])
engine = QQmlEngine()
root_dir = Path(__file__).resolve().parents[1]
component = QQmlComponent(engine, QUrl.fromLocalFile(str(root_dir / 'src/qml/views/WIPBillingWizardView.qml')))
view = component.create()
assert view is not None, '\n'.join(e.toString() for e in component.errors())
engine.globalObject().setProperty('view', engine.newQObject(view))


def evaluate(code):
    result = engine.evaluate(code)
    assert not result.isError(), result.toString()
    return result.toVariant()


def pump():
    for _ in range(6):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def pick(target, date_expression):
    evaluate(f"view.openDatePicker('{target}', -1, -1)")
    pump()
    calendars = [w for w in app.topLevelWindows() if w.objectName() == 'CSPMJellyCalendar']
    assert len(calendars) == 1 and calendars[0].isVisible()
    engine.globalObject().setProperty('calendar', engine.newQObject(calendars[0]))
    evaluate(f'calendar.acceptDateAndClose({date_expression})')
    pump()


evaluate("view.wipItems = [{id:'before',date:'2026-07-30'}, {id:'start',date:'2026-07-31'}, {id:'middle',date:'2026-08-15'}, {id:'end',date:'2026-08-31'}, {id:'after',date:'2026-09-01'}]")
pick('from', 'new Date(2026, 6, 31)')
assert evaluate('view.fromDateFilter') == '2026-07-31', evaluate('view.fromDateFilter')
assert view.findChild(QObject, 'WIPFromDateInput').property('text') == '2026-07-31'
assert evaluate('view.filteredItems.map(function(x){return x.id})') == ['start', 'middle', 'end', 'after']
pick('to', 'new Date(2026, 7, 31)')
assert evaluate('view.toDateFilter') == '2026-08-31'
assert view.findChild(QObject, 'WIPToDateInput').property('text') == '2026-08-31'
assert evaluate('view.filteredItems.map(function(x){return x.id})') == ['start', 'middle', 'end']
pick('from', 'new Date(2026, 7, 15)')
assert evaluate('view.fromDateFilter') == '2026-08-15'
assert evaluate('view.filteredItems.map(function(x){return x.id})') == ['middle', 'end']
evaluate("view.openDatePicker('to', -1, -1)")
pump()
calendar = next(w for w in app.topLevelWindows() if w.objectName() == 'CSPMJellyCalendar')
engine.globalObject().setProperty('calendar', engine.newQObject(calendar))
evaluate('calendar.hideCalendar()')
pump()
assert evaluate('view.toDateFilter') == '2026-08-31'
assert not any(w.objectName() == 'CSPMJellyCalendar' for w in app.topLevelWindows())
evaluate("view.applyDatePreset('all')")
assert len(evaluate('view.filteredItems')) == 5
print(json.dumps({'calendarSelectionAndRangeFiltering': True}))
view.deleteLater()
pump()
