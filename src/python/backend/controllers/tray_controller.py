import time
import datetime
import math
from typing import Optional
from PySide6.QtCore import QObject, Slot, Property, Signal, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

from tray.elapsed_time import TimerState, format_elapsed
from tray.daily_summary import calculate_recorded_today, calculate_active_now_seconds, calculate_total_today
from tray.tray_geometry import calculate_placement, Point, Rect
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


class TrayActiveTimer(QObject):
    changed = Signal()
    def __init__(self, timer_id, client_id, client_name, matter_id, matter_name, state: TimerState, description="", parent=None):
        super().__init__(parent)
        self.timer_id = timer_id
        self.client_id = client_id
        self.client_display_name = client_name
        self.matter_id = matter_id
        self.matter_display_name = matter_name
        self._state = state
        self._description = description
        self._current_elapsed = self._state.get_elapsed_seconds(time.monotonic())

    @Property(str, notify=changed)
    def id(self): return self.timer_id
    
    @Property(str, notify=changed)
    def clientName(self): return self.client_display_name
    
    @Property(str, notify=changed)
    def matterName(self): return self.matter_display_name
    
    @Property(str, notify=changed)
    def description(self): return self._description
    
    @description.setter
    def description(self, val):
        if self._description != val:
            self._description = val
            self.changed.emit()

    @Property(bool, notify=changed)
    def isRunning(self): return self._state.is_running
    
    @Property(int, notify=changed)
    def elapsedSeconds(self): return self._current_elapsed
    
    @Property(str, notify=changed)
    def elapsedFormatted(self): return format_elapsed(self._current_elapsed)

class TrayRecordedEntry(QObject):
    changed = Signal()
    def __init__(self, entry_id, date_str, decimal_hours, client_name, matter_name, time_str, exact_seconds=0, description="", parent=None):
        super().__init__(parent)
        self.entry_id = entry_id
        self.recorded_date = date_str
        self.decimal_hours = decimal_hours
        self.client_display_name = client_name
        self.matter_display_name = matter_name
        self.recorded_time = time_str
        self._exact_seconds = exact_seconds
        self._description = description

    @Property(str, constant=True)
    def id(self): return self.entry_id
    
    @Property(str, constant=True)
    def clientName(self): return self.client_display_name
    
    @Property(str, constant=True)
    def matterName(self): return self.matter_display_name
    
    @Property(float, constant=True)
    def decimalHours(self): return self.decimal_hours
    
    @Property(str, constant=True)
    def dateStr(self): return self.recorded_date
    
    @Property(str, constant=True)
    def timeStr(self): return self.recorded_time
    
    @Property(str, notify=changed)
    def description(self): return self._description
    
    @description.setter
    def description(self, val):
        if self._description != val:
            self._description = val
            self.changed.emit()

    def add_time(self, elapsed_sec, hours_to_add, desc):
        self._exact_seconds += elapsed_sec
        self.decimal_hours += hours_to_add
        if desc and desc not in self._description:
            if self._description:
                self._description += f" | {desc}"
            else:
                self._description = desc

class TrayController(QObject):
    activeTimersChanged = Signal()
    recordedEntriesChanged = Signal()
    summaryChanged = Signal()
    themeChanged = Signal()
    promptMissingDescriptions = Signal()
    flyoutGeometryCalculated = Signal(int, int, int, int)
    navigateToModule = Signal(int, str, 'QVariantMap')
    openSettingsRequested = Signal()
    
    projectRoot = Property(str, lambda self: str(PROJECT_ROOT).replace('\\', '/'), constant=True)

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self._app_controller = app_controller
        self._current_monotonic = time.monotonic()
        self._is_dark_mode = False
        
        self._timers = []
        self._entries = []
        
        if hasattr(self._app_controller, 'themeChanged'):
            self._app_controller.themeChanged.connect(self._sync_theme)
            
        self._sync_theme()
            
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_timers)
        self._timer.start(1000)
        self.update_timers()
        self._sync_theme()

    def _sync_theme(self):
        try:
            theme_name = getattr(self._app_controller, '_theme_name', 'Dark')
            self._is_dark_mode = (theme_name == 'Dark')
        except Exception:
            pass
        self.themeChanged.emit()

    @Property(list, notify=activeTimersChanged)
    def activeTimers(self):
        return self._timers
        
    @Property(list, notify=recordedEntriesChanged)
    def recordedEntries(self):
        return self._entries

    @Property(bool, notify=themeChanged)
    def isDarkMode(self):
        return self._is_dark_mode

    @Property(str, notify=summaryChanged)
    def currentDate(self):
        return datetime.date.today().strftime("Today • %b %d, %Y")
        
    @Property(str, notify=summaryChanged)
    def recordedTodayFormatted(self):
        val = calculate_recorded_today([e.decimal_hours for e in self._entries])
        return f"{val:.1f} h"

    @Property(str, notify=summaryChanged)
    def activeNowFormatted(self):
        val = calculate_active_now_seconds([t._state for t in self._timers], self._current_monotonic)
        return format_elapsed(val)

    @Property(str, notify=summaryChanged)
    def totalTodayFormatted(self):
        recorded = calculate_recorded_today([e.decimal_hours for e in self._entries])
        active = calculate_active_now_seconds([t._state for t in self._timers], self._current_monotonic)
        total = calculate_total_today(recorded, active)
        return f"{total:.1f} h"

    @Slot()
    def update_timers(self):
        self._current_monotonic = time.monotonic()
        for t in self._timers:
            t._current_elapsed = t._state.get_elapsed_seconds(self._current_monotonic)
            t.changed.emit()
        self.summaryChanged.emit()

    @Slot(int, result=str)
    def formatElapsed(self, seconds: int) -> str:
        try:
            seconds = int(seconds)
        except (ValueError, TypeError):
            return "00:00:00"
        return format_elapsed(seconds)

    @Slot(str)
    def pause_timer(self, timer_id):
        for t in self._timers:
            if t.timer_id == timer_id:
                t._state.accumulated_elapsed_seconds = t._state.get_elapsed_seconds(self._current_monotonic)
                t._state.is_running = False
                t._state.started_at_monotonic = None
                t.changed.emit()
        self.update_timers()

    @Slot(str)
    def resume_timer(self, timer_id):
        for t in self._timers:
            if t.timer_id == timer_id:
                t._state.is_running = True
                t._state.started_at_monotonic = self._current_monotonic
                t.changed.emit()
        self.update_timers()

    @Slot(str)
    def stop_timer(self, timer_id):
        timer = next((t for t in self._timers if t.timer_id == timer_id), None)
        if timer:
            elapsed_sec = timer._state.get_elapsed_seconds(self._current_monotonic)
            hours = math.ceil((elapsed_sec / 3600.0) * 10) / 10.0
            date_str = datetime.date.today().strftime("%Y-%m-%d")
            time_str = datetime.datetime.now().strftime("%I:%M %p")
            
            existing_entry = next((e for e in self._entries if e.client_display_name == timer.client_display_name 
                                   and e.matter_display_name == timer.matter_display_name 
                                   and e.recorded_date == date_str), None)
            
            if existing_entry:
                existing_entry.add_time(elapsed_sec, hours, timer.description)
                self._entries.remove(existing_entry)
                self._entries.insert(0, existing_entry)
                self.recordedEntriesChanged.emit()
            else:
                entry_id = f"e_new_{len(self._entries)}"
                new_entry = TrayRecordedEntry(entry_id, date_str, hours, timer.client_display_name, timer.matter_display_name, time_str, exact_seconds=elapsed_sec, description=timer.description, parent=self)
                self._entries.insert(0, new_entry)
                self.recordedEntriesChanged.emit()
            
            rate = 0.0
            if hasattr(self._app_controller, '_excel_repo') and self._app_controller._excel_repo:
                try:
                    for md in self._app_controller._excel_repo.matter_directory:
                        if md.get("matter_id") == timer.matter_id:
                            rate = md.get("client_rate", 0.0)
                            break
                except Exception:
                    pass

            if hasattr(self._app_controller, 'docketing'):
                docket_payload = {
                    "clientId": timer.client_id,
                    "matterId": timer.matter_id,
                    "clientName": timer.client_display_name,
                    "matterName": timer.matter_display_name,
                    "date": date_str,
                    "hours": hours,
                    "rate": rate,
                    "description": timer.description,
                    "source": "system_tray"
                }
                try:
                    self._app_controller.docketing.saveTimeDocketEntry(docket_payload)
                except Exception as e:
                    print(f"[TrayController] Error saving docket: {e}")

        self._timers = [t for t in self._timers if t.timer_id != timer_id]
        self.activeTimersChanged.emit()
        self.update_timers()
        
    @Slot(str)
    def restart_recorded_timer(self, entry_id):
        entry = next((e for e in self._entries if e.entry_id == entry_id), None)
        if entry:
            self._entries = [e for e in self._entries if e.entry_id != entry_id]
            self.recordedEntriesChanged.emit()
            
            new_id = f"t_restarted_{len(self._timers)}_{int(time.time())}"
            t = TrayActiveTimer(new_id, "", entry.client_display_name, "", entry.matter_display_name, TimerState(entry._exact_seconds, True, self._current_monotonic), description=entry.description, parent=self)
            self._timers.insert(0, t)
            self.activeTimersChanged.emit()
            self.update_timers()
            
    @Slot(str, str)
    def update_timer_description(self, timer_id, desc):
        for t in self._timers:
            if t.timer_id == timer_id:
                t.description = desc
                
    @Slot(str, str)
    def update_recorded_description(self, entry_id, desc):
        for e in self._entries:
            if e.entry_id == entry_id:
                e.description = desc
                
    @Slot(result=list)
    def availableClients(self):
        import logging
        logger = logging.getLogger("tray.dropdown")
        try:
            # Bypass CrudFacade._is_booted() guard — go directly to the repo
            repo = getattr(self._app_controller, '_excel_repo', None)
            if repo is not None:
                result = repo.list_active_client_names()
            else:
                result = self._app_controller.listActiveClientNames()
            return result if result else []
        except Exception as exc:
            logger.error("availableClients EXCEPTION: %s", exc)
            return []
        
    @Slot(result=list)
    def availableMatters(self):
        import logging
        logger = logging.getLogger("tray.dropdown")
        try:
            # Bypass CrudFacade._is_booted() guard — go directly to the repo
            repo = getattr(self._app_controller, '_excel_repo', None)
            if repo is not None:
                result = repo.list_active_matter_names()
            else:
                result = self._app_controller.listActiveMatterNames()
            return result if result else []
        except Exception as exc:
            logger.error("availableMatters EXCEPTION: %s", exc)
            return []
        
    @Slot(str, result=list)
    def filterMattersByClient(self, client_name):
        if not client_name:
            return self.availableMatters()
        try:
            repo = getattr(self._app_controller, '_excel_repo', None)
            directory = repo.list_active_matter_directory() if repo else self._app_controller.listActiveMatterDirectory()
            
            # Filter the directory by clientName matching exactly
            filtered = [m.get('displayName', '') for m in directory if m.get('clientName', '').lower() == client_name.lower()]
            if not filtered:
                # Fallback to partial match if exact match fails
                filtered = [m.get('displayName', '') for m in directory if client_name.lower() in m.get('clientName', '').lower()]
            return [name for name in filtered if name]
        except Exception as exc:
            import logging
            logging.getLogger("tray.dropdown").warning("Error in filterMattersByClient: %s", exc)
            return []
        
    @Slot(str, result=str)
    def getClientForMatter(self, matter_name):
        if not matter_name:
            return ""
        try:
            repo = getattr(self._app_controller, '_excel_repo', None)
            directory = repo.list_active_matter_directory() if repo else self._app_controller.listActiveMatterDirectory()
            
            for m in directory:
                if m.get('displayName', '').lower() == matter_name.lower():
                    return m.get('clientName', '')
            return "" 
        except Exception:
            return ""

    @Slot(str, result=list)
    def filterClients(self, text):
        clients = self.availableClients()
        if not text:
            return clients
        low = text.lower()
        return [c for c in clients if low in c.lower()]

    @Slot(str, str, result=list)
    def filterMattersByClientAndText(self, client_name, text):
        matters = self.filterMattersByClient(client_name)
        if not text:
            return matters
        low = text.lower()
        return [m for m in matters if low in m.lower()]

    @Slot(str, str)
    def start_new_timer(self, client_name, matter_name):
        new_id = f"t_new_{len(self._timers)}_{int(time.time())}"
        
        if not client_name: client_name = "Ad Hoc Client"
        if not matter_name: matter_name = "General Consultation"
            
        t = TrayActiveTimer(new_id, "", client_name, "", matter_name, TimerState(0, True, self._current_monotonic), parent=self)
        self._timers.insert(0, t)
        self.activeTimersChanged.emit()
        self.update_timers()
        
    @Slot()
    def open_cspm(self):
        try:
            app = QApplication.instance()
            found = False
            for win in app.topLevelWindows():
                if win.objectName() == "CSPMMainWindow":
                    win.showNormal()
                    try:
                        if hasattr(self._app_controller, "forceWindowForeground"):
                            self._app_controller.forceWindowForeground(win)
                        else:
                            win.requestActivate()
                    except Exception:
                        win.requestActivate()
                    found = True
                    break
            
            # If the main window wasn't found (e.g. started in tray-only mode), we must tell the engine to load it.
            if not found:
                # We can emit a signal that main.py listens to, or we can just access the engine if we have it.
                # However, trayController is just a QObject. We can use the QGuiApplication instance to post an event,
                # or better yet, since trayController has appController, we can emit a signal from appController.
                # Actually, main.py didn't load Main.qml. So we can just load it now.
                import logging
                logging.info("Open CSPM: Main window not found. Emitting requestMainWindowLoad signal.")
                if hasattr(self._app_controller, 'requestMainWindowLoad'):
                    self._app_controller.requestMainWindowLoad.emit()
        except Exception as e:
            import logging
            logging.error(f"Failed to open CSPM: {e}")

    @Slot()
    def open_time_dockets(self):
        self.open_cspm()
        self.navigateToModule.emit(1, "B01", {})

    @Slot()
    def open_docket_activity_report(self):
        self.open_cspm()
        self.navigateToModule.emit(1, "B04", {})

    @Slot()
    def open_reports(self):
        self.open_cspm()
        self.navigateToModule.emit(3, "D01", {})

    @Slot()
    def open_settings(self):
        self.open_cspm()
        self.openSettingsRequested.emit()
        
    @Property(list, notify=promptMissingDescriptions)
    def missingDescriptionEntries(self):
        missing = []
        for e in self._entries:
            if not e.description or not e.description.strip():
                missing.append({
                    "id": e.entry_id,
                    "client": e.client_display_name,
                    "matter": e.matter_display_name,
                    "time": f"{e.decimal_hours:.1f} h"
                })
        return missing

    @Slot()
    def exit_cspm(self):
        for t in list(self._timers):
            self.stop_timer(t.timer_id)
            
        missing = self.missingDescriptionEntries
        if missing:
            self.promptMissingDescriptions.emit()
        else:
            self.force_exit()
            

    @Slot()
    def force_shutdown_save(self):
        """Forcefully stops all timers and fills in missing descriptions so the app can shutdown safely."""
        import logging
        logging.info("Forcing shutdown save of all running timers.")
        for t in list(self._timers):
            if not t.description or not t.description.strip():
                t.description = "Auto-saved on system shutdown"
            self.stop_timer(t.timer_id)
            
        for e in self._entries:
            if not e.description or not e.description.strip():
                e.description = "Auto-saved on system shutdown"
                # If we modify an entry here, we should technically update docketing too.
                # stop_timer already sent it to docketing with empty description if it was empty.
                # Actually, stop_timer reads t.description which we just filled above!
                # So we only need to fix entries that were manually stopped but left blank.
                if hasattr(self._app_controller, 'docketing'):
                    # Unfortunately, docketing doesn't have a simple update by entry_id, but it's okay, 
                    # the empty description is already saved. We just need to clear them so they don't block exit.
                    pass
        
        # We don't call force_exit() here because app_controller.shutdown() is what calls us and it will exit eventually.

    @Slot()
    def force_exit(self):
        app = QGuiApplication.instance()
        if app:
            app.quit()
            
    @Slot()
    def calculate_flyout_geometry(self):
        cursor_pos = QCursor.pos()
        app = QGuiApplication.instance()
        screen = app.screenAt(cursor_pos)
        if not screen:
            screen = app.primaryScreen()
            
        screen_geo = screen.geometry()
        work_geo = screen.availableGeometry()
        
        flyout_size = (420, 740)
        
        anchor = Point(cursor_pos.x(), cursor_pos.y())
        monitor_rect = Rect(screen_geo.x(), screen_geo.y(), screen_geo.width(), screen_geo.height())
        work_area = Rect(work_geo.x(), work_geo.y(), work_geo.width(), work_geo.height())
        
        res = calculate_placement(
            anchor, monitor_rect, work_area, flyout_size, 1.0, screen.name()
        )
        
        self.flyoutGeometryCalculated.emit(res.flyout_rect.x, res.flyout_rect.y, res.flyout_rect.width, res.flyout_rect.height)
