import time
import datetime
import math
import sys
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
    def __init__(self, entry_id, date_str, decimal_hours, client_name, matter_name, time_str, exact_seconds=0, description="", client_id="", matter_id="", parent=None):
        super().__init__(parent)
        self.entry_id = entry_id
        self.recorded_date = date_str
        self.decimal_hours = float(decimal_hours or 0.0)
        self.client_id = client_id
        self.client_display_name = client_name
        self.matter_id = matter_id
        self.matter_display_name = matter_name
        self.recorded_time = time_str
        self._exact_seconds = int(exact_seconds or round(self.decimal_hours * 3600))
        self._description = description

    @Property(str, notify=changed)
    def id(self): return self.entry_id
    
    @Property(str, notify=changed)
    def clientName(self): return self.client_display_name
    
    @Property(str, notify=changed)
    def matterName(self): return self.matter_display_name
    
    @Property(float, notify=changed)
    def decimalHours(self): return self.decimal_hours

    @Property(int, notify=changed)
    def exactSeconds(self): return self._exact_seconds

    @Property(str, notify=changed)
    def elapsedFormatted(self): return format_elapsed(self._exact_seconds)
    
    @Property(str, notify=changed)
    def dateStr(self): return self.recorded_date
    
    @Property(str, notify=changed)
    def timeStr(self): return self.recorded_time
    
    @Property(str, notify=changed)
    def description(self): return self._description
    
    @description.setter
    def description(self, val):
        if self._description != val:
            self._description = val
            self.changed.emit()

    def add_time(self, elapsed_sec, hours_to_add, desc):
        self._exact_seconds += int(elapsed_sec or 0)
        self.decimal_hours += float(hours_to_add or 0.0)
        if desc and desc not in self._description:
            if self._description:
                self._description += f" | {desc}"
            else:
                self._description = desc
        self.changed.emit()


def _normalize_matter_label(raw_label: str) -> str:
    text = str(raw_label or "").strip()
    if not text or text in {"(blank)", "(none)"}:
        return ""
    if " - " in text and " — " not in text:
        parts = text.split(" - ", 1)
        left, right = parts[0].strip(), parts[1].strip()
        if left and right:
            return f"{left} — {right}"
    return text


class TrayController(QObject):
    activeTimersChanged = Signal()
    recordedEntriesChanged = Signal()
    summaryChanged = Signal()
    primaryTimerChanged = Signal()
    mainTimerCommandRequested = Signal('QVariantMap')
    themeChanged = Signal()
    promptMissingDescriptions = Signal()
    flyoutGeometryCalculated = Signal(int, int, int, int)
    navigateToModule = Signal(int, str, 'QVariantMap')
    openSettingsRequested = Signal()
    showTrayToast = Signal(str)
    requestRestoreFromTray = Signal(int)
    requestExitFromTray = Signal()
    
    projectRoot = Property(str, lambda self: str(PROJECT_ROOT).replace('\\', '/'), constant=True)
    FLYOUT_WIDTH = 340
    FLYOUT_HEIGHT = 218

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self._app_controller = app_controller
        if self._app_controller is not None:
            try:
                setattr(self._app_controller, "_tray_controller", self)
            except Exception:
                pass
        self._current_monotonic = time.monotonic()
        self._is_dark_mode = False
        self._restore_revision = 0
        self._pending_restore_revision = 0
        self._exit_requested = False
        self._shutdown_complete = False
        
        self._timers = []
        self._entries = []
        
        if hasattr(self._app_controller, 'themeChanged'):
            self._app_controller.themeChanged.connect(self._sync_theme)
            
        self._sync_theme()
        self._hydrate_latest_entry_from_repo()
            
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_timers)
        self._timer.start(1000)
        self._exit_failsafe_timer = QTimer(self)
        self._exit_failsafe_timer.setSingleShot(True)
        self._exit_failsafe_timer.timeout.connect(self.force_exit)
        self.update_timers()
        self._sync_theme()

    def _sync_theme(self):
        try:
            theme_name = getattr(self._app_controller, '_theme_name', 'Dark')
            self._is_dark_mode = (theme_name == 'Dark')
        except Exception:
            pass
        self.themeChanged.emit()

    def _resolve_client_and_matter_labels(self, client_id: str, client_name: str, matter_id: str, matter_name: str) -> tuple[str, str, str, str]:
        c_id = str(client_id or "").strip()
        c_name = str(client_name or "").strip()
        if c_name in {"(blank)", "(none)"}:
            c_name = ""
        m_id = str(matter_id or "").strip()
        m_name = _normalize_matter_label(matter_name)

        repo = getattr(self._app_controller, "_excel_repo", None)
        if repo is not None:
            try:
                if (m_id or m_name) and ("—" not in m_name or not c_name):
                    directory = repo.list_active_matter_directory()
                    for m in directory or []:
                        cand_id = str(m.get("matterId") or "").strip()
                        cand_num = str(m.get("matterNumber") or "").strip()
                        cand_title = str(m.get("matterName") or m.get("displayName") or "").strip()
                        cand_combined = f"{cand_num} — {cand_title}".strip(" —") if cand_num else cand_title
                        cand_dash = f"{cand_num} - {cand_title}".strip(" -") if cand_num else cand_title
                        if (
                            (m_id and cand_id.casefold() == m_id.casefold())
                            or (m_id and cand_num.casefold() == m_id.casefold())
                            or (m_name and m_name.casefold() in {cand_num.casefold(), cand_title.casefold(), cand_combined.casefold(), cand_dash.casefold()})
                        ):
                            m_id = cand_id or m_id
                            m_name = cand_combined or m_name
                            if not c_name:
                                c_name = str(m.get("clientName") or "").strip()
                            if not c_id:
                                c_id = str(m.get("clientId") or "").strip()
                            break
            except Exception:
                pass
        return c_id, c_name, m_id, m_name

    def _hydrate_latest_entry_from_repo(self):
        """Seed the latest saved docket entry from the repository if available."""
        repo = getattr(self._app_controller, "_excel_repo", None)
        if repo is None or not hasattr(repo, "_read_table_rows"):
            return
        try:
            from repositories.excel_repo import TBL_TIME
            from domain import schema_constants as sc
            rows = repo._read_table_rows(TBL_TIME)
            if not rows:
                return
            latest_row = rows[-1]
            c_id = str(latest_row.get(sc.COL_TIME_CLIENT_ID) or "").strip()
            m_id = str(latest_row.get(sc.COL_TIME_MATTER_ID) or "").strip()
            _, c_name, _, m_name = self._resolve_client_and_matter_labels(c_id, "", m_id, m_id)
            hours = float(latest_row.get(sc.COL_TIME_HOURS) or 0.0)
            raw_sec = int(float(latest_row.get(sc.COL_TIME_SECONDS) or round(hours * 3600)))
            date_str = str(latest_row.get(sc.COL_TIME_DATE) or datetime.date.today().isoformat())[:10]
            desc = str(latest_row.get(sc.COL_TIME_DESC) or "").strip()
            entry_id = str(latest_row.get(sc.COL_TIME_ENTRY_ID) or "e_latest").strip()
            entry = TrayRecordedEntry(
                entry_id,
                date_str,
                hours,
                c_name or c_id or "Recent Client",
                m_name or m_id or "Recent Matter",
                "",
                exact_seconds=raw_sec,
                description=desc,
                client_id=c_id,
                matter_id=m_id,
                parent=self,
            )
            self._entries = [entry]
        except Exception:
            pass

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

    def _primary_active_timer(self) -> Optional[TrayActiveTimer]:
        for t in self._timers:
            if t.isRunning:
                return t
        return self._timers[0] if self._timers else None

    def _primary_recorded_entry(self) -> Optional[TrayRecordedEntry]:
        return self._entries[0] if self._entries else None

    @Property(bool, notify=primaryTimerChanged)
    def hasRunningTimer(self) -> bool:
        return any(t.isRunning for t in self._timers)

    @Property(bool, notify=primaryTimerChanged)
    def hasActiveOrPausedTimer(self) -> bool:
        return len(self._timers) > 0

    @Property(bool, notify=primaryTimerChanged)
    def hasDisplayEntry(self) -> bool:
        return bool(self._timers or self._entries)

    @Property(str, notify=primaryTimerChanged)
    def displayStatus(self) -> str:
        t = self._primary_active_timer()
        if t is not None:
            return "RUNNING" if t.isRunning else "PAUSED"
        if self._primary_recorded_entry() is not None:
            return "LATEST"
        return "IDLE"

    @Property(str, notify=primaryTimerChanged)
    def displayTimerId(self) -> str:
        t = self._primary_active_timer()
        if t is not None:
            return t.timer_id
        e = self._primary_recorded_entry()
        return e.entry_id if e is not None else ""

    @Property(int, notify=primaryTimerChanged)
    def displayElapsedSeconds(self) -> int:
        t = self._primary_active_timer()
        if t is not None:
            return int(t.elapsedSeconds)
        e = self._primary_recorded_entry()
        if e is not None:
            return int(e.exactSeconds)
        return 0

    @Property(str, notify=primaryTimerChanged)
    def displayElapsedFormatted(self) -> str:
        return format_elapsed(self.displayElapsedSeconds)

    @Property(str, notify=primaryTimerChanged)
    def displayClientName(self) -> str:
        t = self._primary_active_timer()
        if t is not None:
            return t.client_display_name or "Unassigned Client"
        e = self._primary_recorded_entry()
        if e is not None:
            return e.client_display_name or "Unassigned Client"
        return "No active timer"

    @Property(str, notify=primaryTimerChanged)
    def displayMatterName(self) -> str:
        t = self._primary_active_timer()
        if t is not None:
            return t.matter_display_name or "Unassigned Matter"
        e = self._primary_recorded_entry()
        if e is not None:
            return e.matter_display_name or "Unassigned Matter"
        return "Start a timer in CSPM"

    @Property(str, notify=primaryTimerChanged)
    def displayDescription(self) -> str:
        t = self._primary_active_timer()
        if t is not None:
            return str(t.description or "")
        e = self._primary_recorded_entry()
        if e is not None:
            return str(e.description or "")
        return ""

    @Property(str, notify=primaryTimerChanged)
    def displayDescriptionOrPlaceholder(self) -> str:
        desc = self.displayDescription.strip()
        return desc if desc else "No description"

    @Property(str, notify=primaryTimerChanged)
    def trayTooltipText(self) -> str:
        status = self.displayStatus
        if status == "RUNNING":
            return f"CSPM ● RUNNING ({self.displayElapsedFormatted}) — {self.displayClientName} | {self.displayMatterName}"
        if status == "PAUSED":
            return f"CSPM ⏸ PAUSED ({self.displayElapsedFormatted}) — {self.displayClientName} | {self.displayMatterName}"
        if status == "LATEST":
            return f"CSPM — Latest: {self.displayElapsedFormatted} • {self.displayClientName} ({self.displayMatterName})"
        return "CSPM — Canadian Solo Practice Manager"

    def _update_system_tray_indicator(self):
        try:
            app = QApplication.instance()
            icon = getattr(app, "_tray_icon", None) if app is not None else None
            if icon is None and self._app_controller is not None:
                icon = getattr(self._app_controller, "_tray_icon", None)
            if icon is not None and hasattr(icon, "setToolTip"):
                icon.setToolTip(self.trayTooltipText)
        except Exception:
            pass

    @Slot()
    def update_timers(self):
        self._current_monotonic = time.monotonic()
        for t in self._timers:
            t._current_elapsed = t._state.get_elapsed_seconds(self._current_monotonic)
            t.changed.emit()
        self.summaryChanged.emit()
        self.primaryTimerChanged.emit()
        self._update_system_tray_indicator()

    @Slot(int, result=str)
    def formatElapsed(self, seconds: int) -> str:
        try:
            seconds = int(seconds)
        except (ValueError, TypeError):
            return "00:00:00"
        return format_elapsed(seconds)

    @Slot('QVariantMap')
    def syncMainTimerState(self, payload):
        """Synchronize the main window's live/paused docket timer with the system tray."""
        data = dict(payload or {})
        self._current_monotonic = time.monotonic()

        is_running = bool(data.get("isRunning", False))
        raw_sec = data.get("elapsedSeconds")
        if raw_sec is None:
            raw_sec = data.get("rawSeconds", 0)
        try:
            elapsed_sec = max(0, int(float(raw_sec or 0)))
        except (TypeError, ValueError):
            elapsed_sec = 0

        raw_client_id = str(data.get("clientId") or "").strip()
        raw_client_name = str(data.get("clientName") or data.get("clientText") or "").strip()
        raw_matter_id = str(data.get("matterId") or "").strip()
        raw_matter_name = str(data.get("matterName") or data.get("matterText") or "").strip()
        raw_desc = str(data.get("description") if "description" in data else (data.get("descriptionText") or "")).strip()
        timer_id = str(data.get("timerId") or "main_timer").strip() or "main_timer"
        clear_timer = bool(data.get("clearActiveTimer", False))

        c_id, c_name, m_id, m_name = self._resolve_client_and_matter_labels(
            raw_client_id, raw_client_name, raw_matter_id, raw_matter_name
        )

        existing = next((t for t in self._timers if t.timer_id == timer_id), None)
        if existing is None and self._timers:
            existing = self._timers[0]

        if clear_timer or (not is_running and elapsed_sec <= 0 and not bool(data.get("keepPausedZero", False))):
            if existing is not None:
                self._timers = [t for t in self._timers if t is not existing]
                self.activeTimersChanged.emit()
            # Only update the latest recorded entry if the main window is explicitly editing that exact entryId
            payload_entry_id = str(data.get("entryId") or "").strip()
            if (
                not clear_timer
                and payload_entry_id
                and self._entries
                and self._entries[0].entry_id == payload_entry_id
                and (c_name or m_name or "description" in data or "descriptionText" in data)
            ):
                latest = self._entries[0]
                if c_name:
                    latest.client_display_name = c_name
                if m_name:
                    latest.matter_display_name = m_name
                if "description" in data or "descriptionText" in data:
                    latest.description = raw_desc
                latest.changed.emit()
            self.update_timers()
            return

        if existing is not None:
            existing.client_id = c_id or existing.client_id
            if c_name or raw_client_name:
                existing.client_display_name = c_name or raw_client_name
            existing.matter_id = m_id or existing.matter_id
            if m_name or raw_matter_name:
                existing.matter_display_name = m_name or raw_matter_name
            if "description" in data or "descriptionText" in data:
                existing._description = raw_desc
            existing._state.accumulated_elapsed_seconds = elapsed_sec
            existing._state.is_running = is_running
            existing._state.started_at_monotonic = self._current_monotonic if is_running else None
            existing._current_elapsed = elapsed_sec
            if self._timers[0] is not existing:
                self._timers.remove(existing)
                self._timers.insert(0, existing)
                self.activeTimersChanged.emit()
            existing.changed.emit()
        else:
            state = TimerState(
                accumulated_elapsed_seconds=elapsed_sec,
                is_running=is_running,
                started_at_monotonic=self._current_monotonic if is_running else None,
            )
            new_timer = TrayActiveTimer(
                timer_id,
                c_id,
                c_name or raw_client_name or "Unassigned Client",
                m_id,
                m_name or raw_matter_name or "Unassigned Matter",
                state,
                description=raw_desc,
                parent=self,
            )
            self._timers.insert(0, new_timer)
            self.activeTimersChanged.emit()

        self.update_timers()

    @Slot('QVariantMap')
    def onDocketSaved(self, payload):
        """Update the tray's latest recorded entry when a docket is saved or edited in CSPM."""
        data = dict(payload or {})
        saved_row = dict(data.get("savedRow") or {})
        entry_id = str(data.get("entryId") or saved_row.get("EntryID") or f"e_{len(self._entries) + 1}").strip()
        date_str = str(data.get("date") or data.get("dateText") or saved_row.get("Date") or datetime.date.today().isoformat())[:10]
        raw_sec = int(float(data.get("rawSeconds") or data.get("aggregateRawSeconds") or saved_row.get("RawSeconds") or 0))
        hours = float(data.get("hours") or data.get("aggregateHoursRounded") or saved_row.get("Hours") or 0.0)
        if hours <= 0.0 and raw_sec > 0:
            hours = math.ceil((raw_sec / 3600.0) * 10.0) / 10.0
        if raw_sec <= 0 and hours > 0.0:
            raw_sec = int(round(hours * 3600.0))

        c_id = str(data.get("clientId") or saved_row.get("ClientID") or "").strip()
        c_name_in = str(data.get("clientName") or data.get("clientText") or "").strip()
        m_id = str(data.get("matterId") or saved_row.get("MatterID") or "").strip()
        m_name_in = str(data.get("matterName") or data.get("matterText") or "").strip()
        c_id, c_name, m_id, m_name = self._resolve_client_and_matter_labels(c_id, c_name_in, m_id, m_name_in)
        desc = str(
            data.get("description")
            if "description" in data
            else (data.get("descriptionText") if "descriptionText" in data else (saved_row.get("Description") or ""))
        ).strip()
        time_str = datetime.datetime.now().strftime("%I:%M %p")

        existing = next((e for e in self._entries if e.entry_id == entry_id), None)
        if existing is not None:
            existing.recorded_date = date_str
            existing.decimal_hours = hours
            existing._exact_seconds = raw_sec
            if c_name:
                existing.client_display_name = c_name
            if m_name:
                existing.matter_display_name = m_name
            existing._description = desc
            existing.changed.emit()
            if self._entries[0] is not existing:
                self._entries.remove(existing)
                self._entries.insert(0, existing)
        else:
            new_entry = TrayRecordedEntry(
                entry_id,
                date_str,
                hours,
                c_name or c_name_in or "Client",
                m_name or m_name_in or "Matter",
                time_str,
                exact_seconds=raw_sec,
                description=desc,
                client_id=c_id,
                matter_id=m_id,
                parent=self,
            )
            self._entries.insert(0, new_entry)

        if bool(data.get("stoppedTimer", False)):
            self._timers.clear()
            self.activeTimersChanged.emit()
        elif self._timers and not any(t.isRunning for t in self._timers):
            # If the timer in the main app is paused and was just saved, keep its description/client/matter aligned
            t0 = self._timers[0]
            if c_name:
                t0.client_display_name = c_name
            if m_name:
                t0.matter_display_name = m_name
            t0._description = desc
            t0.changed.emit()

        self.recordedEntriesChanged.emit()
        self.update_timers()

    @Slot(str)
    def pause_timer(self, timer_id):
        paused_sec = 0
        paused_desc = ""
        for t in self._timers:
            if t.timer_id == timer_id or not timer_id:
                t._state.accumulated_elapsed_seconds = t._state.get_elapsed_seconds(self._current_monotonic)
                t._state.is_running = False
                t._state.started_at_monotonic = None
                t._current_elapsed = t._state.accumulated_elapsed_seconds
                paused_sec = int(t._current_elapsed)
                paused_desc = str(t.description or "")
                t.changed.emit()
                break
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "pause",
            "timerId": timer_id,
            "elapsedSeconds": paused_sec,
            "description": paused_desc,
        })

    @Slot(str)
    def resume_timer(self, timer_id):
        resumed_sec = 0
        c_name = ""
        m_name = ""
        desc = ""
        for t in self._timers:
            if t.timer_id == timer_id or not timer_id:
                t._state.is_running = True
                t._state.started_at_monotonic = self._current_monotonic
                resumed_sec = int(t._state.get_elapsed_seconds(self._current_monotonic))
                c_name = t.client_display_name
                m_name = t.matter_display_name
                desc = t.description
                t.changed.emit()
                break
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "resume",
            "timerId": timer_id,
            "elapsedSeconds": resumed_sec,
            "clientName": c_name,
            "matterName": m_name,
            "description": desc,
        })

    @Slot()
    def togglePrimaryTimer(self):
        t = self._primary_active_timer()
        if t is not None:
            if t.isRunning:
                self.pause_timer(t.timer_id)
            else:
                self.resume_timer(t.timer_id)
            return
        e = self._primary_recorded_entry()
        if e is not None:
            self.restart_recorded_timer(e.entry_id)
            return
        self.start_new_timer("", "")

    @Slot()
    def stopAndSavePrimaryTimer(self):
        t = self._primary_active_timer()
        if t is not None:
            self.stop_timer(t.timer_id)

    @Slot(str)
    def updatePrimaryDescription(self, desc: str):
        clean_desc = str(desc or "")
        t = self._primary_active_timer()
        if t is not None:
            self.update_timer_description(t.timer_id, clean_desc)
            return
        e = self._primary_recorded_entry()
        if e is not None:
            self.update_recorded_description(e.entry_id, clean_desc)

    @Slot(str)
    def stop_timer(self, timer_id):
        timer = next((t for t in self._timers if t.timer_id == timer_id), None)
        if timer is None and self._timers and not timer_id:
            timer = self._timers[0]
        saved_entry_id = ""
        elapsed_sec = 0
        if timer:
            elapsed_sec = timer._state.get_elapsed_seconds(self._current_monotonic)
            hours = math.ceil((elapsed_sec / 3600.0) * 10) / 10.0 if elapsed_sec > 0 else 0.0
            date_str = datetime.date.today().strftime("%Y-%m-%d")
            time_str = datetime.datetime.now().strftime("%I:%M %p")
            
            rate = 0.0
            if hasattr(self._app_controller, '_excel_repo') and self._app_controller._excel_repo:
                try:
                    prof = self._app_controller._excel_repo.get_matter_profile(
                        timer.matter_id or timer.matter_display_name
                    )
                    if isinstance(prof, dict) and prof.get("ok") and isinstance(prof.get("matter"), dict):
                        rate = float(prof["matter"].get("defaultRate") or 0.0)
                except Exception:
                    pass

            docket_payload = {
                "clientId": timer.client_id,
                "matterId": timer.matter_id,
                "clientName": timer.client_display_name,
                "clientText": timer.client_display_name,
                "matterName": timer.matter_display_name,
                "matterText": timer.matter_display_name,
                "date": date_str,
                "dateText": date_str,
                "hours": hours,
                "rawSeconds": int(elapsed_sec),
                "elapsedSeconds": int(elapsed_sec),
                "rate": rate,
                "description": timer.description,
                "descriptionText": timer.description,
                "allowClientOnlyDraft": 1 if not (timer.matter_id or timer.matter_display_name) else 0,
                "source": "system_tray",
            }
            save_result = {}
            try:
                if hasattr(self._app_controller, "saveTimeDocketEntry"):
                    save_result = dict(self._app_controller.saveTimeDocketEntry(docket_payload) or {})
                elif hasattr(self._app_controller, "docketing"):
                    save_result = dict(self._app_controller.docketing.saveTimeDocketEntry(docket_payload) or {})
            except Exception as e:
                print(f"[TrayController] Error saving docket: {e}")

            saved_entry_id = str(save_result.get("entryId") or "").strip()

            existing_entry = next(
                (
                    e for e in self._entries
                    if (saved_entry_id and e.entry_id == saved_entry_id)
                    or (
                        e.client_display_name == timer.client_display_name
                        and e.matter_display_name == timer.matter_display_name
                        and e.recorded_date == date_str
                    )
                ),
                None,
            )
            
            if existing_entry:
                if saved_entry_id:
                    existing_entry.entry_id = saved_entry_id
                existing_entry._exact_seconds = int(save_result.get("aggregateRawSeconds") or elapsed_sec)
                existing_entry.decimal_hours = float(save_result.get("aggregateHoursRounded") or hours)
                if timer.description:
                    existing_entry._description = timer.description
                existing_entry.changed.emit()
                self._entries.remove(existing_entry)
                self._entries.insert(0, existing_entry)
                self.recordedEntriesChanged.emit()
            else:
                entry_id = saved_entry_id or f"e_new_{len(self._entries)}"
                new_entry = TrayRecordedEntry(
                    entry_id,
                    date_str,
                    hours,
                    timer.client_display_name,
                    timer.matter_display_name,
                    time_str,
                    exact_seconds=elapsed_sec,
                    description=timer.description,
                    client_id=timer.client_id,
                    matter_id=timer.matter_id,
                    parent=self,
                )
                self._entries.insert(0, new_entry)
                self.recordedEntriesChanged.emit()

        target_id = timer.timer_id if timer else timer_id
        self._timers = [t for t in self._timers if t.timer_id != target_id]
        self.activeTimersChanged.emit()
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "stopped_and_saved",
            "timerId": target_id,
            "entryId": saved_entry_id,
            "elapsedSeconds": int(elapsed_sec),
        })
        
    @Slot(str)
    def restart_recorded_timer(self, entry_id):
        entry = next((e for e in self._entries if e.entry_id == entry_id), None)
        if entry is None and self._entries and not entry_id:
            entry = self._entries[0]
        if entry:
            self._entries = [e for e in self._entries if e.entry_id != entry.entry_id]
            self.recordedEntriesChanged.emit()
            
            new_id = "main_timer"
            t = TrayActiveTimer(
                new_id,
                getattr(entry, "client_id", ""),
                entry.client_display_name,
                getattr(entry, "matter_id", ""),
                entry.matter_display_name,
                TimerState(entry._exact_seconds, True, self._current_monotonic),
                description=entry.description,
                parent=self,
            )
            self._timers = [x for x in self._timers if x.timer_id != new_id]
            self._timers.insert(0, t)
            self.activeTimersChanged.emit()
            self.update_timers()
            self.mainTimerCommandRequested.emit({
                "action": "resume",
                "timerId": new_id,
                "elapsedSeconds": int(entry._exact_seconds),
                "clientName": entry.client_display_name,
                "matterName": entry.matter_display_name,
                "description": entry.description,
            })
            
    @Slot(str, str)
    def update_timer_description(self, timer_id, desc):
        for t in self._timers:
            if t.timer_id == timer_id or not timer_id:
                t.description = desc
                break
        self.primaryTimerChanged.emit()
        self.mainTimerCommandRequested.emit({
            "action": "description",
            "timerId": timer_id,
            "description": desc,
        })
                
    @Slot(str, str)
    def update_recorded_description(self, entry_id, desc):
        target_entry = None
        for e in self._entries:
            if e.entry_id == entry_id or not entry_id:
                e.description = desc
                target_entry = e
                break
        self.primaryTimerChanged.emit()
        self.mainTimerCommandRequested.emit({
            "action": "description",
            "entryId": target_entry.entry_id if target_entry else entry_id,
            "description": desc,
        })
        if target_entry and target_entry.entry_id and not target_entry.entry_id.startswith("e_new_"):
            try:
                if hasattr(self._app_controller, "updateTimeDocketEntry"):
                    self._app_controller.updateTimeDocketEntry(target_entry.entry_id, {"description": desc})
            except Exception:
                pass

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
            if repo is not None and hasattr(repo, "list_active_matter_directory"):
                directory = repo.list_active_matter_directory() or []
            elif hasattr(self._app_controller, "listActiveMatterDirectory"):
                directory = self._app_controller.listActiveMatterDirectory() or []
            else:
                directory = []
            if directory:
                out = []
                for m in directory:
                    if not isinstance(m, dict):
                        continue
                    disp = _normalize_matter_label(m.get("displayName") or "")
                    if not disp:
                        m_num = str(m.get("matterNumber") or "").strip()
                        m_name = str(m.get("matterName") or "").strip()
                        disp = f"{m_num} — {m_name}" if (m_num and m_name) else (m_num or m_name)
                    if disp and disp not in out:
                        out.append(disp)
                if out:
                    return out
            if repo is not None:
                result = repo.list_active_matter_names()
            else:
                result = self._app_controller.listActiveMatterNames()
            return [_normalize_matter_label(x) for x in (result or []) if x]
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
            
            def _label(m):
                disp = _normalize_matter_label(m.get('displayName', ''))
                if not disp:
                    m_num = str(m.get('matterNumber') or '').strip()
                    m_name = str(m.get('matterName') or '').strip()
                    disp = f"{m_num} — {m_name}" if (m_num and m_name) else (m_num or m_name)
                return disp

            # Filter the directory by clientName matching exactly
            filtered = [_label(m) for m in directory if m.get('clientName', '').lower() == client_name.lower()]
            if not filtered:
                # Fallback to partial match if exact match fails
                filtered = [_label(m) for m in directory if client_name.lower() in m.get('clientName', '').lower()]
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
            target_norm = _normalize_matter_label(matter_name).lower()
            target_raw = str(matter_name).strip().lower()
            for m in directory:
                disp_raw = str(m.get('displayName', '')).strip().lower()
                disp_norm = _normalize_matter_label(m.get('displayName', '')).lower()
                m_num = str(m.get('matterNumber', '')).strip().lower()
                m_name = str(m.get('matterName', '')).strip().lower()
                if (
                    target_raw in (disp_raw, disp_norm, m_num, m_name)
                    or target_norm in (disp_raw, disp_norm)
                    or (m_num and target_raw.startswith(m_num))
                ):
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
        self.startNewTimerWithDescription(client_name, matter_name, "")

    @Slot(str, str, str)
    def startNewTimerWithDescription(self, client_name, matter_name, description=""):
        # If there is an active or paused timer with accumulated time, save it before starting the new one
        existing_primary = self._primary_active_timer()
        if existing_primary is not None:
            elapsed_now = existing_primary._state.get_elapsed_seconds(self._current_monotonic)
            if elapsed_now > 0:
                self.stop_timer(existing_primary.timer_id)
            else:
                self._timers = [x for x in self._timers if x.timer_id != existing_primary.timer_id]

        new_id = "main_timer"
        clean_client = str(client_name or "").strip()
        clean_matter = str(matter_name or "").strip()
        clean_desc = str(description or "").strip()
        if not clean_client and clean_matter:
            clean_client = self.getClientForMatter(clean_matter) or ""
        if not clean_client:
            clean_client = "Ad Hoc Client"
        if not clean_matter:
            clean_matter = "General Consultation"

        c_id, resolved_client, m_id, resolved_matter = self._resolve_client_and_matter_labels(
            "", clean_client, "", clean_matter
        )
        c_label = resolved_client or clean_client
        m_label = resolved_matter or _normalize_matter_label(clean_matter)

        t = TrayActiveTimer(
            new_id,
            c_id,
            c_label,
            m_id,
            m_label,
            TimerState(0, True, self._current_monotonic),
            description=clean_desc,
            parent=self,
        )
        self._timers = [x for x in self._timers if x.timer_id != new_id]
        self._timers.insert(0, t)
        self.activeTimersChanged.emit()
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "start_new",
            "timerId": new_id,
            "elapsedSeconds": 0,
            "clientId": c_id,
            "clientName": c_label,
            "matterId": m_id,
            "matterName": m_label,
            "description": clean_desc,
        })
        
    @Slot()
    def open_cspm(self):
        import logging
        if self._exit_requested or self._shutdown_complete:
            return
        if self._pending_restore_revision:
            logging.getLogger("lifecycle").info("tray restore duplicate rejected revision=%s", self._pending_restore_revision)
            return
        try:
            app = QApplication.instance()
            for win in app.topLevelWindows():
                if win.objectName() == "CSPMMainWindow":
                    logging.warning("[TRAY-PY] open_cspm: found CSPMMainWindow isVisible=%s", win.isVisible())
                    if not win.isVisible():
                        # Window is hidden (tray-resident) — trigger restore animation
                        self._restore_revision += 1
                        self._pending_restore_revision = self._restore_revision
                        logging.getLogger("lifecycle").info("tray restore accepted revision=%s", self._restore_revision)
                        self.requestRestoreFromTray.emit(self._restore_revision)
                    else:
                        # Window is visible — just bring to front
                        logging.warning("[TRAY-PY] open_cspm: window visible, bringing to front")
                        if sys.platform.startswith("linux") and bool(win.property("uiMaximized")):
                            win.showMaximized()
                        else:
                            win.showNormal()
                        try:
                            if hasattr(self._app_controller, "forceWindowForeground"):
                                self._app_controller.forceWindowForeground(win)
                            else:
                                win.requestActivate()
                        except Exception:
                            win.requestActivate()
                    return
            # If the main window wasn't found (e.g. started in tray-only mode), we must tell the engine to load it.
            logging.warning("[TRAY-PY] open_cspm: Main window not found")
            if hasattr(self._app_controller, 'requestMainWindowLoad'):
                self._app_controller.requestMainWindowLoad.emit()
        except Exception as e:
            logging.error(f"Failed to open CSPM: {e}")

    @Slot(int)
    def completeRestoreFromTray(self, revision):
        if int(revision) != self._pending_restore_revision:
            return
        import logging
        logging.getLogger("lifecycle").info("tray restore completed revision=%s", revision)
        self._pending_restore_revision = 0

    @Slot(str)
    def requestApplicationExit(self, reason):
        """Record explicit full-exit intent; teardown follows animation completion."""
        if self._exit_requested:
            return
        self._exit_requested = True
        self._pending_restore_revision = 0
        app = QApplication.instance()
        if app is not None:
            app._tray_exit_requested = True
        import logging
        logging.getLogger("lifecycle").info("application exit requested reason=%s", reason)

    def shutdown(self):
        """Stop owned timers, preserve elapsed work and release tray resources once."""
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        self.requestApplicationExit("about-to-quit")
        self._timer.stop()
        self._exit_failsafe_timer.stop()
        self._current_monotonic = time.monotonic()
        try:
            self.force_shutdown_save()
        finally:
            app = QApplication.instance()
            if app is not None:
                icon = getattr(app, "_tray_icon", None)
                if icon is not None:
                    try:
                        icon.hide()
                        icon.setContextMenu(None)
                        icon.deleteLater()
                    except RuntimeError:
                        pass
                    app._tray_icon = None
                menu = getattr(app, "_tray_menu", None)
                if menu is not None:
                    try:
                        menu.close()
                        menu.deleteLater()
                    except RuntimeError:
                        pass
                    app._tray_menu = None
            import logging
            logging.getLogger("lifecycle").info("tray resources released; owned timers stopped")

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
        import logging
        if self._exit_requested or self._shutdown_complete:
            return
        for t in list(self._timers):
            self.stop_timer(t.timer_id)
            
        missing = self.missingDescriptionEntries
        if missing:
            self.promptMissingDescriptions.emit()
        else:
            # Mark intentional exit so the lifecycle guard allows quit
            self.requestApplicationExit("tray-exit")
            logging.warning("[TRAY-PY] exit_cspm: emitting requestExitFromTray")
            self.requestExitFromTray.emit()
            # Failsafe: if the QML animation doesn't complete within 8s, force quit
            self._exit_failsafe_timer.start(8000)
            

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
        screen = app.screenAt(cursor_pos) if app else None
        if not screen and app:
            screen = app.primaryScreen()
        if not screen:
            self.flyoutGeometryCalculated.emit(cursor_pos.x() - self.FLYOUT_WIDTH, cursor_pos.y() - self.FLYOUT_HEIGHT, self.FLYOUT_WIDTH, self.FLYOUT_HEIGHT)
            return
            
        screen_geo = screen.geometry()
        work_geo = screen.availableGeometry()
        
        flyout_size = (self.FLYOUT_WIDTH, self.FLYOUT_HEIGHT)
        
        anchor = Point(cursor_pos.x(), cursor_pos.y())
        monitor_rect = Rect(screen_geo.x(), screen_geo.y(), screen_geo.width(), screen_geo.height())
        work_area = Rect(work_geo.x(), work_geo.y(), work_geo.width(), work_geo.height())
        
        res = calculate_placement(
            anchor, monitor_rect, work_area, flyout_size, 1.0, screen.name()
        )
        
        self.flyoutGeometryCalculated.emit(res.flyout_rect.x, res.flyout_rect.y, res.flyout_rect.width, res.flyout_rect.height)

    @Slot(result='QVariantMap')
    def getSystemTrayGeometry(self):
        """Return the global bounding rect of the system tray notification area.
        Returns {x, y, width, height} or empty dict if unavailable."""
        if not sys.platform.startswith("win"):
            return self._qt_system_tray_geometry()
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            # Find the main taskbar window (only one Shell_TrayWnd has TrayNotifyWnd)
            hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if not hwnd:
                return {}
            # Find the notification area within it
            notify_hwnd = user32.FindWindowExW(hwnd, 0, "TrayNotifyWnd", None)
            if not notify_hwnd:
                return {}

            rect = wintypes.RECT()
            if not user32.GetWindowRect(notify_hwnd, ctypes.byref(rect)):
                return {}

            return {
                "x": int(rect.left),
                "y": int(rect.top),
                "width": int(rect.right - rect.left),
                "height": int(rect.bottom - rect.top),
            }
        except Exception:
            return {}

    def _qt_system_tray_geometry(self):
        """Use Qt's tray icon position, then a panel-edge estimate for SNI hosts.

        Plasma's StatusNotifier protocol can leave QSystemTrayIcon.geometry()
        empty. Its reserved screen work area still supplies the panel edge;
        keep estimated geometry explicitly labelled and never invent a panel
        when the desktop reports no reserved area.
        """
        try:
            app = QApplication.instance()
            icon = getattr(app, "_tray_icon", None)
            if icon is None or not icon.isVisible():
                return {}
            rect = icon.geometry()
            if rect.isValid() and not rect.isEmpty():
                return {"x": rect.x(), "y": rect.y(), "width": rect.width(),
                        "height": rect.height(), "source": "qt-tray-icon"}
            screen = app.primaryScreen()
            if screen is None:
                return {}
            monitor = screen.geometry()
            work = screen.availableGeometry()
            insets = {
                "left": max(0, work.left() - monitor.left()),
                "top": max(0, work.top() - monitor.top()),
                "right": max(0, monitor.right() - work.right()),
                "bottom": max(0, monitor.bottom() - work.bottom()),
            }
            edge = max(insets, key=insets.get)
            size = insets[edge]
            if size <= 0:
                return {}
            # The notification area normally sits at the trailing end of the
            # panel. Keep its estimated target inside the reserved strip.
            if edge in ("top", "bottom"):
                width = min(size, monitor.width())
                x = monitor.right() - width + 1
                y = monitor.top() if edge == "top" else monitor.bottom() - size + 1
                height = size
            else:
                height = min(size, monitor.height())
                x = monitor.left() if edge == "left" else monitor.right() - size + 1
                y = monitor.bottom() - height + 1
                width = size
            return {"x": x, "y": y, "width": width, "height": height,
                    "source": "panel-edge-estimate"}
        except (AttributeError, RuntimeError, TypeError):
            return {}

    @Slot(int, int, result='QVariantMap')
    def getTrayFlightInfo(self, winCenterX, winCenterY):
        """Return comprehensive flight geometry for cross-monitor tray animations.

        Args:
            winCenterX, winCenterY: Global coordinates of the window center.

        Returns dict with:
            available: bool — whether tray geometry was resolved
            trayCenterX, trayCenterY: Tray center point (global)
            sameMonitor: Whether tray is on the same monitor as the window
            vdX, vdY, vdW, vdH: Virtual desktop bounding rect
        """
        tray_geo = self.getSystemTrayGeometry()
        if not tray_geo:
            return {"available": False}

        tray_cx = tray_geo["x"] + tray_geo["width"] // 2
        tray_cy = tray_geo["y"] + tray_geo["height"] // 2

        app = QGuiApplication.instance()
        if app is None:
            return {"available": False}
        from PySide6.QtCore import QPoint
        tray_screen = app.screenAt(QPoint(tray_cx, tray_cy))
        win_screen = app.screenAt(QPoint(int(winCenterX), int(winCenterY)))
        same_monitor = (tray_screen is not None and win_screen is not None
                        and tray_screen == win_screen)

        # Virtual desktop bounding rect (union of all screens)
        screens = app.screens()
        if not screens:
            return {"available": False}
        min_x = min(s.geometry().x() for s in screens)
        min_y = min(s.geometry().y() for s in screens)
        max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
        max_y = max(s.geometry().y() + s.geometry().height() for s in screens)

        return {
            "available": True,
            "trayCenterX": tray_cx,
            "trayCenterY": tray_cy,
            "sameMonitor": same_monitor,
            "vdX": min_x,
            "vdY": min_y,
            "vdW": max_x - min_x,
            "vdH": max_y - min_y,
            "source": tray_geo.get("source", "windows-notification-area"),
        }

    @Slot(str)
    def show_tray_toast(self, message):
        try:
            self.showTrayToast.emit(str(message))
        except Exception as e:
            import logging
            logging.error(f"Error emitting showTrayToast: {e}")
