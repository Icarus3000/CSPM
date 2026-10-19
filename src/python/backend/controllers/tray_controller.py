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
    def __init__(self, timer_id, client_id, client_name, matter_id, matter_name, state: TimerState, description="", parent=None, sqlite_entry_id=""):
        super().__init__(parent)
        self.timer_id = timer_id
        self.client_id = client_id
        self.client_display_name = client_name
        self.matter_id = matter_id
        self.matter_display_name = matter_name
        self._state = state
        self._description = description
        self._current_elapsed = self._state.get_elapsed_seconds(time.monotonic())
        today_iso = datetime.date.today().isoformat()
        self.sqlite_entry_id = str(sqlite_entry_id or f"T-LIVE-{timer_id}-{today_iso}").strip()
        self.linked_entry_id = str(sqlite_entry_id or "").strip() if str(sqlite_entry_id or "").startswith("T") and not str(sqlite_entry_id or "").startswith("T-LIVE-") else ""
        self.started_at_utc = (
            datetime.datetime.now(datetime.timezone.utc).isoformat()
            if self._state.is_running
            else None
        )
        self.legacy_dockets_sync_status = "PENDING_CRASH_RECOVERY"
        self.legacy_dockets_row_signature = None

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


def _format_matter_directory_label(m: dict) -> str:
    if not isinstance(m, dict):
        return ""
    m_num = str(m.get("matterNumber") or "").strip()
    m_name = str(m.get("matterName") or m.get("displayName") or "").strip()
    if m_num and m_name:
        if m_name.lower().startswith(m_num.lower()):
            return _normalize_matter_label(m_name)
        return f"{m_num} — {m_name}"
    return _normalize_matter_label(m_num or m_name)


def _parse_manual_time_input(raw_time: str) -> Optional[int]:
    import re
    text = str(raw_time or "").strip().lower()
    if not text:
        return None
    # 1. HH:MM:SS or MM:SS / HH:MM
    if ":" in text:
        parts = [p.strip() for p in text.split(":")]
        try:
            if len(parts) == 3:
                h = float(parts[0] or 0)
                m = float(parts[1] or 0)
                s = float(parts[2] or 0)
                return max(0, int(round(h * 3600 + m * 60 + s)))
            if len(parts) == 2:
                h = float(parts[0] or 0)
                m = float(parts[1] or 0)
                return max(0, int(round(h * 3600 + m * 60)))
        except (ValueError, TypeError):
            return None
    # 2. Combined hours and minutes e.g. "1h 30m", "2hr 15min"
    hm_match = re.match(
        r"^\s*(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\s*(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)?\s*$",
        text,
    )
    if hm_match:
        h = float(hm_match.group(1))
        m = float(hm_match.group(2))
        return max(0, int(round(h * 3600 + m * 60)))
    # 3. Minutes only e.g. "45m", "45 min", "90mins"
    m_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)\s*$", text)
    if m_match:
        m = float(m_match.group(1))
        return max(0, int(round(m * 60)))
    # 4. Seconds only e.g. "90s", "90 sec"
    s_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\s*$", text)
    if s_match:
        s = float(s_match.group(1))
        return max(0, int(round(s)))
    # 5. Decimal hours with optional h/hr/hrs suffix e.g. "2.8", "1.5h", "0.5 hrs"
    h_match = re.match(r"^\s*(\d+(?:\.\d+)?|\.\d+)\s*(?:h|hr|hrs|hour|hours)?\s*$", text)
    if h_match:
        h = float(h_match.group(1))
        return max(0, int(round(h * 3600)))
    return None


def _compute_tab_short_label(matter_name: str, client_name: str, fallback_index: int = 1) -> str:
    m_clean = str(matter_name or "").strip()
    if m_clean and m_clean not in {"Unassigned Matter", "Start a timer in CSPM", "General Consultation"}:
        if " — " in m_clean:
            prefix = m_clean.split(" — ", 1)[0].strip()
            if prefix:
                return prefix[:22]
        if " - " in m_clean:
            prefix = m_clean.split(" - ", 1)[0].strip()
            if prefix:
                return prefix[:22]
        return m_clean[:20]

    c_clean = str(client_name or "").strip()
    if c_clean and c_clean not in {"Unassigned Client", "No active timer", "Ad Hoc Client"}:
        words = [w for w in c_clean.split() if w]
        if len(words) >= 2 and len(words[0]) + len(words[1]) + 1 <= 18:
            return f"{words[0]} {words[1]}"
        return c_clean[:18]

    return f"Draft #{max(1, int(fallback_index))}"


def _extract_matter_number_token(matter_label: str) -> str:
    m_clean = str(matter_label or "").strip()
    if not m_clean:
        return ""
    for sep in (" — ", " - "):
        if sep in m_clean:
            left = m_clean.split(sep, 1)[0].strip()
            if left and "-" in left:
                return left
    if "-" in m_clean and " " not in m_clean:
        return m_clean
    return ""


class TrayController(QObject):
    activeTimersChanged = Signal()
    recordedEntriesChanged = Signal()
    summaryChanged = Signal()
    primaryTimerChanged = Signal()
    todayDocketTabsChanged = Signal()
    selectedTabChanged = Signal()
    simultaneousTimerWarningChanged = Signal()
    simultaneousTimerWarningRequested = Signal('QVariantMap')
    legacySyncConflictChanged = Signal()
    legacySyncConflictDetected = Signal('QVariantMap')
    crashRecoveryChanged = Signal()
    crashRecoveryRequested = Signal('QVariantMap')
    closeSafeguardChanged = Signal()
    closeSafeguardRequested = Signal('QVariantMap')
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
    MIN_FLYOUT_WIDTH = 320
    MIN_FLYOUT_HEIGHT = 220

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self._app_controller = app_controller
        if self._app_controller is not None:
            try:
                setattr(self._app_controller, "_tray_controller", self)
                dock_ctrl = getattr(self._app_controller, "_docketing_controller", None)
                if dock_ctrl is not None:
                    setattr(dock_ctrl, "_tray_controller", self)
            except Exception:
                pass
        self._current_monotonic = time.monotonic()
        self._last_sqlite_heartbeat_monotonic = self._current_monotonic
        self._is_dark_mode = False
        self._restore_revision = 0
        self._pending_restore_revision = 0
        self._exit_requested = False
        self._shutdown_complete = False
        self._pending_quit_after_conflict = False
        self._pause_sync_quit_completed = False
        
        self._timers = []
        self._entries = []
        self._draft_tabs = []
        self._draft_counter = 0
        self._hidden_tab_ids = set()
        self._selected_tab_id = ""
        self._simultaneous_warning = {}
        self._legacy_sync_conflict = {}
        self._last_sync_status_message = ""
        self._crash_recovery_dockets = []
        self._close_safeguard_visible = False
        self._close_safeguard_source = ""
        
        if hasattr(self._app_controller, 'themeChanged'):
            self._app_controller.themeChanged.connect(self._sync_theme)
            
        self._sync_theme()
        self._hydrate_latest_entry_from_repo()
        self.reconcileUnsyncedDocketsOnStartup()
            
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_timers)
        self._timer.start(1000)

        self._sqlite_edit_debounce_timer = QTimer(self)
        self._sqlite_edit_debounce_timer.setSingleShot(True)
        self._sqlite_edit_debounce_timer.setInterval(1000)
        self._sqlite_edit_debounce_timer.timeout.connect(self._flush_debounced_sqlite_heartbeat)

        self._exit_failsafe_timer = QTimer(self)
        self._exit_failsafe_timer.setSingleShot(True)
        self._exit_failsafe_timer.timeout.connect(self.force_exit)

        app_inst = QGuiApplication.instance()
        if app_inst is not None:
            try:
                if hasattr(app_inst, "commitDataRequest"):
                    app_inst.commitDataRequest.connect(self._on_commit_data_request)
                if hasattr(app_inst, "aboutToQuit"):
                    app_inst.aboutToQuit.connect(self.flush_active_timers_to_sqlite)
            except Exception:
                pass

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
        raw_m_name = str(matter_name or "").strip()
        if raw_m_name in {"(blank)", "(none)"}:
            raw_m_name = ""
        m_name = _normalize_matter_label(raw_m_name)

        repo = getattr(self._app_controller, "_excel_repo", None)
        if repo is not None:
            try:
                if m_id or m_name:
                    directory = repo.list_active_matter_directory() or []
                    for m in directory:
                        cand_id = str(m.get("matterId") or "").strip()
                        cand_num = str(m.get("matterNumber") or "").strip()
                        cand_title = str(m.get("matterName") or m.get("displayName") or "").strip()
                        cand_type = str(m.get("matterType") or "").strip()
                        cand_combined = _format_matter_directory_label(m)
                        cand_dash = f"{cand_num} - {cand_title}".strip(" -") if cand_num else cand_title
                        short_suffix = ""
                        if cand_num and "-" in cand_num:
                            parts = [p.strip() for p in cand_num.split("-") if p.strip()]
                            if len(parts) >= 2:
                                short_suffix = f"{parts[-2]}-{parts[-1]}"
                        match_set = {
                            s.casefold()
                            for s in (
                                cand_id,
                                cand_num,
                                cand_title,
                                cand_combined,
                                cand_dash,
                                f"{cand_title} - {cand_num}" if (cand_title and cand_num) else "",
                                f"{cand_title} — {cand_num}" if (cand_title and cand_num) else "",
                                f"{cand_title} - {short_suffix}" if (cand_title and short_suffix) else "",
                                f"{cand_title} — {short_suffix}" if (cand_title and short_suffix) else "",
                                f"{cand_type} - {short_suffix}" if (cand_type and short_suffix) else "",
                                f"{cand_type} — {short_suffix}" if (cand_type and short_suffix) else "",
                            )
                            if s
                        }
                        cand_client_name = str(m.get("clientName") or "").strip()
                        cand_client_id = str(m.get("clientId") or "").strip()
                        if c_id and cand_client_id and cand_client_id.casefold() != c_id.casefold():
                            continue
                        if c_name and cand_client_name and cand_client_name.casefold() != c_name.casefold():
                            if not (
                                (m_id and m_id.casefold() in {cand_id.casefold(), cand_num.casefold()})
                                or (cand_num and m_name.casefold().startswith(cand_num.casefold()))
                            ):
                                continue
                        if (
                            (m_id and m_id.casefold() in match_set)
                            or (m_name and m_name.casefold() in match_set)
                            or (raw_m_name and raw_m_name.casefold() in match_set)
                            or (cand_num and m_name.casefold().startswith(f"{cand_num.casefold()} —"))
                            or (cand_num and raw_m_name.casefold().startswith(f"{cand_num.casefold()} -"))
                        ):
                            m_id = cand_id or m_id
                            m_name = cand_combined or m_name
                            if not c_name:
                                c_name = cand_client_name
                            if not c_id:
                                c_id = cand_client_id
                            break
            except Exception:
                pass
        return c_id, c_name, m_id, m_name

    def _hydrate_latest_entry_from_repo(self):
        """Seed today's saved dockets (and fallback latest entry) from tblTimeEntries."""
        repo = getattr(self._app_controller, "_excel_repo", None)
        if repo is None or not hasattr(repo, "_read_table_rows"):
            return
        try:
            from repositories.excel_repo import TBL_TIME
            from domain import schema_constants as sc
            rows = repo._read_table_rows(TBL_TIME)
            if not rows:
                return
            today_iso = datetime.date.today().isoformat()
            non_merged_rows = [
                r for r in rows
                if str(r.get(sc.COL_TIME_STATUS) or "").strip().casefold() != "merged"
            ]
            if not non_merged_rows:
                return

            today_rows = [
                r for r in non_merged_rows
                if str(r.get(sc.COL_TIME_DATE) or "").strip()[:10] == today_iso
            ]
            target_rows = today_rows if today_rows else [non_merged_rows[-1]]

            hydrated_entries: list[TrayRecordedEntry] = []
            for row in reversed(target_rows):
                c_id = str(row.get(sc.COL_TIME_CLIENT_ID) or "").strip()
                m_id = str(row.get(sc.COL_TIME_MATTER_ID) or "").strip()
                _, c_name, _, m_name = self._resolve_client_and_matter_labels(c_id, "", m_id, m_id)
                hours = float(row.get(sc.COL_TIME_HOURS) or 0.0)
                raw_sec = int(float(row.get(sc.COL_TIME_SECONDS) or round(hours * 3600)))
                date_str = str(row.get(sc.COL_TIME_DATE) or today_iso)[:10]
                desc = str(row.get(sc.COL_TIME_DESC) or "").strip()
                entry_id = str(row.get(sc.COL_TIME_ENTRY_ID) or f"e_{len(hydrated_entries) + 1}").strip()
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
                entry.is_today_tab = (date_str == today_iso) or bool(today_rows)
                hydrated_entries.append(entry)

            self._entries = hydrated_entries
            if self._entries and not self._selected_tab_id:
                self._selected_tab_id = f"entry:{self._entries[0].entry_id}"
        except Exception:
            pass

    @Slot()
    def refreshTodayDockets(self):
        self._hydrate_latest_entry_from_repo()
        self.recordedEntriesChanged.emit()
        self.todayDocketTabsChanged.emit()
        self.primaryTimerChanged.emit()

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

    def _build_today_docket_tabs(self) -> list[dict]:
        tabs: list[dict] = []
        seen_entry_ids: set[str] = set()
        today_iso = datetime.date.today().isoformat()

        # 1. Active or paused timers
        for idx, t in enumerate(self._timers, start=1):
            tab_id = f"timer:{t.timer_id}"
            if tab_id in self._hidden_tab_ids:
                continue
            linked_entry_id = str(getattr(t, "linked_entry_id", "") or "").strip()
            if linked_entry_id:
                seen_entry_ids.add(linked_entry_id)
            status = "RUNNING" if t.isRunning else "PAUSED"
            dot_state = "running" if t.isRunning else "paused"
            short_lbl = _compute_tab_short_label(t.matter_display_name, t.client_display_name, idx)
            tabs.append({
                "tabId": tab_id,
                "timerId": t.timer_id,
                "entryId": linked_entry_id,
                "status": status,
                "statusDot": dot_state,
                "label": short_lbl,
                "shortLabel": short_lbl,
                "elapsedSeconds": int(t.elapsedSeconds),
                "elapsedFormatted": format_elapsed(int(t.elapsedSeconds)),
                "clientId": str(t.client_id or ""),
                "clientName": str(t.client_display_name or ""),
                "matterId": str(t.matter_id or ""),
                "matterName": str(t.matter_display_name or ""),
                "description": str(t.description or ""),
                "date": today_iso,
                "isSaved": bool(linked_entry_id),
                "isDraft": not bool(linked_entry_id),
                "canClose": True,
                "isSelected": False,
            })

        # 2. Saved entries from today (or added/updated during this session)
        for idx, e in enumerate(self._entries, start=1):
            if e.entry_id in seen_entry_ids:
                continue
            tab_id = f"entry:{e.entry_id}"
            if tab_id in self._hidden_tab_ids:
                continue
            is_today = (
                str(e.recorded_date or "")[:10] == today_iso
                or bool(getattr(e, "is_today_tab", False))
                or len(self._entries) == 1
            )
            if not is_today:
                continue
            short_lbl = _compute_tab_short_label(e.matter_display_name, e.client_display_name, idx)
            tabs.append({
                "tabId": tab_id,
                "timerId": "",
                "entryId": e.entry_id,
                "status": "SAVED",
                "statusDot": "saved",
                "label": short_lbl,
                "shortLabel": short_lbl,
                "elapsedSeconds": int(e.exactSeconds),
                "elapsedFormatted": format_elapsed(int(e.exactSeconds)),
                "clientId": str(getattr(e, "client_id", "") or ""),
                "clientName": str(e.client_display_name or ""),
                "matterId": str(getattr(e, "matter_id", "") or ""),
                "matterName": str(e.matter_display_name or ""),
                "description": str(e.description or ""),
                "date": str(e.recorded_date or today_iso)[:10],
                "isSaved": True,
                "isDraft": False,
                "canClose": True,
                "isSelected": False,
            })

        # 3. Unsaved blank/draft tabs created today via '+'
        for d in self._draft_tabs:
            tab_id = str(d.get("tabId") or "")
            if not tab_id or tab_id in self._hidden_tab_ids:
                continue
            draft_num = int(d.get("draftNumber") or 1)
            short_lbl = _compute_tab_short_label(
                str(d.get("matterName") or ""),
                str(d.get("clientName") or ""),
                draft_num,
            )
            sec = int(d.get("elapsedSeconds") or 0)
            tabs.append({
                "tabId": tab_id,
                "timerId": "",
                "entryId": "",
                "status": "IDLE",
                "statusDot": "idle",
                "label": short_lbl,
                "shortLabel": short_lbl,
                "elapsedSeconds": sec,
                "elapsedFormatted": format_elapsed(sec),
                "clientId": str(d.get("clientId") or ""),
                "clientName": str(d.get("clientName") or ""),
                "matterId": str(d.get("matterId") or ""),
                "matterName": str(d.get("matterName") or ""),
                "description": str(d.get("description") or ""),
                "date": today_iso,
                "isSaved": False,
                "isDraft": True,
                "canClose": True,
                "isSelected": False,
            })

        # If no tabs exist at all, provide a default Draft #1 tab
        if not tabs:
            default_tab_id = "draft:1"
            tabs.append({
                "tabId": default_tab_id,
                "timerId": "",
                "entryId": "",
                "status": "IDLE",
                "statusDot": "idle",
                "label": "Draft #1",
                "shortLabel": "Draft #1",
                "elapsedSeconds": 0,
                "elapsedFormatted": "00:00:00",
                "clientId": "",
                "clientName": "",
                "matterId": "",
                "matterName": "",
                "description": "",
                "date": today_iso,
                "isSaved": False,
                "isDraft": True,
                "canClose": True,
                "isSelected": True,
            })

        valid_ids = {item["tabId"] for item in tabs}
        if not self._selected_tab_id or self._selected_tab_id not in valid_ids:
            running_tab = next((item["tabId"] for item in tabs if item["status"] == "RUNNING"), "")
            self._selected_tab_id = running_tab or tabs[0]["tabId"]

        for item in tabs:
            item["isSelected"] = (item["tabId"] == self._selected_tab_id)

        return tabs

    @Property(list, notify=todayDocketTabsChanged)
    def todayDocketTabs(self) -> list:
        return self._build_today_docket_tabs()

    @Property(str, notify=selectedTabChanged)
    def selectedTabId(self) -> str:
        tabs = self._build_today_docket_tabs()
        return self._selected_tab_id or (tabs[0]["tabId"] if tabs else "")

    def _find_selected_draft(self) -> Optional[dict]:
        sel = str(self._selected_tab_id or "")
        if not sel.startswith("draft:"):
            return None
        for d in self._draft_tabs:
            if str(d.get("tabId") or "") == sel:
                return d
        return None

    def _selected_active_timer(self) -> Optional[TrayActiveTimer]:
        sel = str(self._selected_tab_id or "")
        if sel.startswith("timer:"):
            tid = sel.split(":", 1)[1]
            found = next((t for t in self._timers if t.timer_id == tid), None)
            if found is not None:
                return found
        if sel.startswith("entry:") or sel.startswith("draft:"):
            return None
        return self._primary_active_timer()

    def _selected_recorded_entry(self) -> Optional[TrayRecordedEntry]:
        sel = str(self._selected_tab_id or "")
        if sel.startswith("entry:"):
            eid = sel.split(":", 1)[1]
            found = next((e for e in self._entries if e.entry_id == eid), None)
            if found is not None:
                return found
        if sel.startswith("timer:") or sel.startswith("draft:"):
            return None
        return self._primary_recorded_entry()

    def _primary_active_timer(self) -> Optional[TrayActiveTimer]:
        sel = str(self._selected_tab_id or "")
        if sel.startswith("timer:"):
            tid = sel.split(":", 1)[1]
            found = next((t for t in self._timers if t.timer_id == tid), None)
            if found is not None:
                return found
        for t in self._timers:
            if t.isRunning:
                return t
        return self._timers[0] if self._timers else None

    def _primary_recorded_entry(self) -> Optional[TrayRecordedEntry]:
        sel = str(self._selected_tab_id or "")
        if sel.startswith("entry:"):
            eid = sel.split(":", 1)[1]
            found = next((e for e in self._entries if e.entry_id == eid), None)
            if found is not None:
                return found
        return self._entries[0] if self._entries else None

    @Slot(str, result=bool)
    def selectDocketTab(self, tab_id: str) -> bool:
        clean_id = str(tab_id or "").strip()
        if not clean_id:
            return False
        tabs = self._build_today_docket_tabs()
        target = next((item for item in tabs if item["tabId"] == clean_id), None)
        if target is None:
            return False
        self._selected_tab_id = clean_id
        self.selectedTabChanged.emit()
        self.todayDocketTabsChanged.emit()
        self.primaryTimerChanged.emit()
        self.mainTimerCommandRequested.emit({
            "action": "select_tab",
            "tabId": clean_id,
            "timerId": str(target.get("timerId") or ""),
            "entryId": str(target.get("entryId") or ""),
            "status": str(target.get("status") or ""),
            "elapsedSeconds": int(target.get("elapsedSeconds") or 0),
            "clientId": str(target.get("clientId") or ""),
            "clientName": str(target.get("clientName") or ""),
            "matterId": str(target.get("matterId") or ""),
            "matterName": str(target.get("matterName") or ""),
            "description": str(target.get("description") or ""),
        })
        return True

    @Slot(result=str)
    def createNewDraftTab(self) -> str:
        self._draft_counter += 1
        draft_num = self._draft_counter
        tab_id = f"draft:{draft_num}"
        today_iso = datetime.date.today().isoformat()
        sqlite_eid = f"T-DRAFT-{draft_num}-{today_iso}"
        draft_dict = {
            "tabId": tab_id,
            "draftNumber": draft_num,
            "sqliteEntryId": sqlite_eid,
            "clientId": "",
            "clientName": "",
            "matterId": "",
            "matterName": "",
            "description": "",
            "elapsedSeconds": 0,
            "date": today_iso,
            "legacyDocketsSyncStatus": "PENDING_CRASH_RECOVERY",
        }
        self._draft_tabs.append(draft_dict)
        self._selected_tab_id = tab_id
        self._upsert_draft_to_sqlite(draft_dict, force=True)
        self.selectedTabChanged.emit()
        self.todayDocketTabsChanged.emit()
        self.primaryTimerChanged.emit()
        return tab_id

    @Slot(result=str)
    def createNewBlankDocketTab(self) -> str:
        return self.createNewDraftTab()

    @Slot(str, result=bool)
    def closeOrHideDocketTab(self, tab_id: str) -> bool:
        clean_id = str(tab_id or "").strip()
        if not clean_id:
            return False
        if clean_id.startswith("draft:"):
            target_draft = next((d for d in self._draft_tabs if str(d.get("tabId") or "") == clean_id), None)
            if target_draft is not None:
                sq_id = str(target_draft.get("sqliteEntryId") or "").strip()
                sq = self._get_sqlite_repo()
                if sq is not None and sq_id:
                    try:
                        sq.delete_time_entry(sq_id)
                    except Exception:
                        pass
            self._draft_tabs = [d for d in self._draft_tabs if str(d.get("tabId") or "") != clean_id]
        elif clean_id.startswith("timer:"):
            tid = clean_id.split(":", 1)[1]
            t_obj = next((t for t in self._timers if t.timer_id == tid), None)
            if t_obj is not None and t_obj.elapsedSeconds <= 0 and not t_obj.isRunning:
                sq = self._get_sqlite_repo()
                if sq is not None and getattr(t_obj, "sqlite_entry_id", ""):
                    try:
                        sq.delete_time_entry(t_obj.sqlite_entry_id)
                    except Exception:
                        pass
                self._timers = [t for t in self._timers if t.timer_id != tid]
                self.activeTimersChanged.emit()
            else:
                self._hidden_tab_ids.add(clean_id)
        else:
            # Saved entry: hide from strip without deleting from CSPM.xlsm
            self._hidden_tab_ids.add(clean_id)

        if self._selected_tab_id == clean_id:
            self._selected_tab_id = ""
        tabs = self._build_today_docket_tabs()
        if tabs:
            self._selected_tab_id = tabs[0]["tabId"]
        self.selectedTabChanged.emit()
        self.todayDocketTabsChanged.emit()
        self.primaryTimerChanged.emit()
        return True

    @Slot(result="QVariantMap")
    @Slot(str, result="QVariantMap")
    @Slot(str, bool, result="QVariantMap")
    def cancelOrDeleteDocketTab(
        self,
        tab_or_entry_id: str = "",
        remove_from_legacy_dockets: bool = True,
    ) -> dict:
        """
        Stop the target timer (if running) and permanently remove the docket tab/entry
        from the active tab model, SQLite time_entries, CSPM.xlsm (tblTimeEntries),
        timer_recovery.json, and (if unbilled) Dockets.xlsm (Table1_1).
        """
        raw_id = str(tab_or_entry_id or self.selectedTabId or "").strip()
        if not raw_id:
            return {"ok": False, "message": "No docket tab or entry ID specified."}

        prior_tabs = self._build_today_docket_tabs()
        prior_index = next(
            (i for i, item in enumerate(prior_tabs) if item.get("tabId") == raw_id),
            0,
        )

        bare_id = raw_id
        for prefix in ("entry:", "timer:"):
            if bare_id.lower().startswith(prefix):
                bare_id = bare_id[len(prefix):]
                break

        # 1. Locate matching in-memory timer, recorded entry, or draft tab
        t_obj = next(
            (
                t
                for t in self._timers
                if f"timer:{t.timer_id}" == raw_id
                or t.timer_id == raw_id
                or t.timer_id == bare_id
                or (bare_id and str(getattr(t, "linked_entry_id", "") or "") == bare_id)
                or (bare_id and str(getattr(t, "sqlite_entry_id", "") or "") == bare_id)
            ),
            None,
        )
        e_obj = next(
            (
                e
                for e in self._entries
                if f"entry:{e.entry_id}" == raw_id
                or e.entry_id == raw_id
                or e.entry_id == bare_id
                or (t_obj is not None and str(getattr(t_obj, "linked_entry_id", "") or "") == e.entry_id)
            ),
            None,
        )
        d_obj = next(
            (
                d
                for d in self._draft_tabs
                if str(d.get("tabId") or "") == raw_id
                or (bare_id and str(d.get("sqliteEntryId") or "") == bare_id)
            ),
            None,
        )

        # 2. If timer is running, stop it immediately
        if t_obj is not None and t_obj.isRunning:
            self._current_monotonic = time.monotonic()
            t_obj._state.accumulated_elapsed_seconds = t_obj._state.get_elapsed_seconds(self._current_monotonic)
            t_obj._state.is_running = False
            t_obj._state.started_at_monotonic = None
            t_obj._current_elapsed = t_obj._state.accumulated_elapsed_seconds
            t_obj.changed.emit()

        # 3. Collect all persistent entry IDs and context for legacy Dockets.xlsm cleanup
        entry_ids_to_delete: list[str] = []
        for candidate in (
            getattr(e_obj, "entry_id", "") if e_obj is not None else "",
            getattr(t_obj, "linked_entry_id", "") if t_obj is not None else "",
            getattr(t_obj, "sqlite_entry_id", "") if t_obj is not None else "",
            str(d_obj.get("sqliteEntryId") or "") if d_obj is not None else "",
            bare_id if not raw_id.lower().startswith(("timer:", "draft:")) else "",
        ):
            c_str = str(candidate or "").strip()
            if c_str and c_str not in entry_ids_to_delete:
                entry_ids_to_delete.append(c_str)

        today_iso = datetime.date.today().isoformat()
        fallback_payload = {
            "clientId": (
                (getattr(t_obj, "client_id", "") if t_obj is not None else "")
                or (getattr(e_obj, "client_id", "") if e_obj is not None else "")
                or (str(d_obj.get("clientId") or "") if d_obj is not None else "")
            ),
            "clientName": (
                (getattr(t_obj, "client_display_name", "") if t_obj is not None else "")
                or (getattr(e_obj, "client_display_name", "") if e_obj is not None else "")
                or (str(d_obj.get("clientName") or "") if d_obj is not None else "")
            ),
            "matterId": (
                (getattr(t_obj, "matter_id", "") if t_obj is not None else "")
                or (getattr(e_obj, "matter_id", "") if e_obj is not None else "")
                or (str(d_obj.get("matterId") or "") if d_obj is not None else "")
            ),
            "matterNumber": _extract_matter_number_token(
                (getattr(t_obj, "matter_display_name", "") if t_obj is not None else "")
                or (getattr(e_obj, "matter_display_name", "") if e_obj is not None else "")
                or (str(d_obj.get("matterName") or "") if d_obj is not None else "")
            ),
            "entryDate": (
                (str(getattr(e_obj, "recorded_date", "") or "")[:10] if e_obj is not None else "")
                or today_iso
            ),
            "description": (
                (getattr(t_obj, "description", "") if t_obj is not None else "")
                or (getattr(e_obj, "description", "") if e_obj is not None else "")
                or (str(d_obj.get("description") or "") if d_obj is not None else "")
            ),
        }

        # 4. Remove from in-memory tab models
        if t_obj is not None:
            self._timers = [t for t in self._timers if t.timer_id != t_obj.timer_id]
            self._hidden_tab_ids.discard(f"timer:{t_obj.timer_id}")
        if e_obj is not None or entry_ids_to_delete:
            del_set = set(entry_ids_to_delete)
            if e_obj is not None:
                del_set.add(e_obj.entry_id)
            self._entries = [e for e in self._entries if e.entry_id not in del_set]
            for eid in del_set:
                self._hidden_tab_ids.discard(f"entry:{eid}")
        if d_obj is not None or raw_id.startswith("draft:"):
            self._draft_tabs = [
                d for d in self._draft_tabs if str(d.get("tabId") or "") != raw_id
            ]
            self._hidden_tab_ids.discard(raw_id)
        if self._crash_recovery_dockets and entry_ids_to_delete:
            del_set = set(entry_ids_to_delete)
            self._crash_recovery_dockets = [
                row
                for row in self._crash_recovery_dockets
                if str(row.get("entryId") or row.get("EntryID") or "") not in del_set
            ]

        # 5. Delete from persistent stores (CSPM.xlsm, SQLite time_entries, timer_recovery.json, Dockets.xlsm)
        repo = getattr(self._app_controller, "_excel_repo", None)
        sq = self._get_sqlite_repo()
        repo_res: dict = {}
        target_ids_for_repo = entry_ids_to_delete if entry_ids_to_delete else [raw_id]
        if repo is not None and hasattr(repo, "cancel_or_delete_docket_entry"):
            for eid in target_ids_for_repo:
                try:
                    r = repo.cancel_or_delete_docket_entry(
                        eid,
                        remove_from_legacy_dockets=bool(remove_from_legacy_dockets),
                        fallback_payload=fallback_payload,
                    )
                    if isinstance(r, dict):
                        if not repo_res or r.get("deletedExcel") or r.get("billedLocked") or r.get("legacyDocketsDelete"):
                            repo_res = dict(r)
                except Exception:
                    pass
        if sq is not None:
            for eid in target_ids_for_repo:
                try:
                    sq.delete_time_entry(eid)
                except Exception:
                    pass

        # 6. Select the next available tab (or initialize clean 00:00:00 draft if none remain)
        remaining_tabs = self._build_today_docket_tabs()
        if remaining_tabs:
            next_idx = min(max(0, prior_index), len(remaining_tabs) - 1)
            self._selected_tab_id = str(remaining_tabs[next_idx].get("tabId") or "draft:1")
        else:
            self._selected_tab_id = "draft:1"
        remaining_tabs = self._build_today_docket_tabs()

        self.activeTimersChanged.emit()
        self.recordedEntriesChanged.emit()
        self.summaryChanged.emit()
        self.selectedTabChanged.emit()
        self.todayDocketTabsChanged.emit()
        self.primaryTimerChanged.emit()

        primary_deleted_id = entry_ids_to_delete[0] if entry_ids_to_delete else raw_id
        self.mainTimerCommandRequested.emit({
            "action": "cancel_or_delete",
            "tabId": raw_id,
            "entryId": primary_deleted_id,
            "selectedTabId": self._selected_tab_id,
        })

        warning_msg = str(repo_res.get("warning") or "").strip()
        billed_locked = bool(repo_res.get("billedLocked"))
        if warning_msg:
            self._last_sync_status_message = warning_msg
            self.legacySyncConflictChanged.emit()
            self.show_tray_toast(warning_msg)
        else:
            self._last_sync_status_message = "Docket cancelled / deleted"
            self.legacySyncConflictChanged.emit()

        return {
            "ok": True,
            "cancelledTabId": raw_id,
            "deletedEntryId": primary_deleted_id,
            "selectedTabId": self._selected_tab_id,
            "remainingTabCount": len(remaining_tabs),
            "billedLocked": billed_locked,
            "billedInvoice": str(repo_res.get("billedInvoice") or ""),
            "warning": warning_msg,
            "message": str(repo_res.get("message") or "Docket cancelled and removed."),
        }

    @Slot(result="QVariantMap")
    @Slot(str, result="QVariantMap")
    def resetDocketTimer(self, tab_or_entry_id: str = "") -> dict:
        """
        Stop the target timer if running, reset raw_seconds to 0 (00:00:00),
        clear any 'Auto-saved on system shutdown' placeholder text, and keep the
        client/matter tab open so the user can start fresh.
        """
        raw_id = str(tab_or_entry_id or self.selectedTabId or "").strip()
        if not raw_id:
            return {"ok": False, "message": "No docket tab or entry ID specified."}

        bare_id = raw_id
        for prefix in ("entry:", "timer:"):
            if bare_id.lower().startswith(prefix):
                bare_id = bare_id[len(prefix):]
                break

        def _strip_auto_shutdown_desc(desc: str) -> str:
            text = str(desc or "").strip()
            return "" if text.casefold() == "auto-saved on system shutdown" else text

        t_obj = next(
            (
                t
                for t in self._timers
                if f"timer:{t.timer_id}" == raw_id
                or t.timer_id == raw_id
                or t.timer_id == bare_id
                or (bare_id and str(getattr(t, "linked_entry_id", "") or "") == bare_id)
                or (bare_id and str(getattr(t, "sqlite_entry_id", "") or "") == bare_id)
            ),
            None,
        )
        e_obj = next(
            (
                e
                for e in self._entries
                if f"entry:{e.entry_id}" == raw_id
                or e.entry_id == raw_id
                or e.entry_id == bare_id
                or (t_obj is not None and str(getattr(t_obj, "linked_entry_id", "") or "") == e.entry_id)
            ),
            None,
        )
        d_obj = next(
            (
                d
                for d in self._draft_tabs
                if str(d.get("tabId") or "") == raw_id
                or (bare_id and str(d.get("sqliteEntryId") or "") == bare_id)
            ),
            None,
        )

        cleaned_desc = ""
        client_name = ""
        matter_name = ""
        target_entry_ids: list[str] = []

        if t_obj is not None:
            self._current_monotonic = time.monotonic()
            t_obj._state.is_running = False
            t_obj._state.started_at_monotonic = None
            t_obj._state.accumulated_elapsed_seconds = 0
            t_obj._current_elapsed = 0
            t_obj._description = _strip_auto_shutdown_desc(t_obj._description)
            cleaned_desc = t_obj._description
            client_name = t_obj.client_display_name
            matter_name = t_obj.matter_display_name
            t_obj.changed.emit()
            for cand in (getattr(t_obj, "linked_entry_id", ""), getattr(t_obj, "sqlite_entry_id", "")):
                if cand and cand not in target_entry_ids:
                    target_entry_ids.append(str(cand))

        if e_obj is not None:
            e_obj._exact_seconds = 0
            e_obj.decimal_hours = 0.0
            e_obj._description = _strip_auto_shutdown_desc(e_obj._description)
            cleaned_desc = e_obj._description
            client_name = client_name or e_obj.client_display_name
            matter_name = matter_name or e_obj.matter_display_name
            e_obj.changed.emit()
            if e_obj.entry_id and e_obj.entry_id not in target_entry_ids:
                target_entry_ids.append(e_obj.entry_id)

        if d_obj is not None:
            d_obj["elapsedSeconds"] = 0
            d_obj["description"] = _strip_auto_shutdown_desc(str(d_obj.get("description") or ""))
            cleaned_desc = d_obj["description"]
            client_name = client_name or str(d_obj.get("clientName") or "")
            matter_name = matter_name or str(d_obj.get("matterName") or "")
            sq_id = str(d_obj.get("sqliteEntryId") or "").strip()
            if sq_id and sq_id not in target_entry_ids:
                target_entry_ids.append(sq_id)

        if not target_entry_ids and not raw_id.lower().startswith(("timer:", "draft:")):
            target_entry_ids.append(bare_id)

        repo = getattr(self._app_controller, "_excel_repo", None)
        sq = self._get_sqlite_repo()
        for eid in target_entry_ids:
            if repo is not None and hasattr(repo, "reset_docket_timer"):
                try:
                    repo.reset_docket_timer(eid, fallback_payload={"description": cleaned_desc})
                except Exception:
                    pass
            if sq is not None and hasattr(sq, "reset_docket_timer"):
                try:
                    sq.reset_docket_timer(eid)
                except Exception:
                    pass

        if t_obj is not None:
            self._upsert_timer_to_sqlite(t_obj, force=True)

        self.activeTimersChanged.emit()
        self.recordedEntriesChanged.emit()
        self.summaryChanged.emit()
        self.todayDocketTabsChanged.emit()
        self.primaryTimerChanged.emit()

        self.mainTimerCommandRequested.emit({
            "action": "reset_timer",
            "tabId": raw_id,
            "entryId": target_entry_ids[0] if target_entry_ids else "",
            "clientName": client_name,
            "matterName": matter_name,
            "description": cleaned_desc,
            "elapsedSeconds": 0,
        })

        return {
            "ok": True,
            "tabId": raw_id,
            "entryId": target_entry_ids[0] if target_entry_ids else "",
            "rawSeconds": 0,
            "elapsedFormatted": "00:00:00",
            "clientName": client_name,
            "matterName": matter_name,
            "description": cleaned_desc,
            "message": "Timer reset to 00:00:00.",
        }

    @Slot(str, str)
    @Slot(str, str, str)
    def setSelectedTabClientAndMatter(self, client_name: str, matter_name: str, description: str = ""):
        clean_c = str(client_name or "").strip()
        clean_m = str(matter_name or "").strip()
        clean_desc = str(description or "").strip()
        if not clean_c and clean_m:
            clean_c = self.getClientForMatter(clean_m) or ""
        c_id, resolved_c, m_id, resolved_m = self._resolve_client_and_matter_labels("", clean_c, "", clean_m)
        final_c = resolved_c or clean_c
        final_m = resolved_m or _normalize_matter_label(clean_m)

        d = self._find_selected_draft()
        if d is not None:
            if final_c:
                d["clientId"] = c_id
                d["clientName"] = final_c
            if final_m:
                d["matterId"] = m_id
                d["matterName"] = final_m
            if clean_desc:
                d["description"] = clean_desc
            self._schedule_debounced_sqlite_heartbeat()
            self.todayDocketTabsChanged.emit()
            self.primaryTimerChanged.emit()
            return

        t = self._selected_active_timer()
        if t is not None:
            if final_c:
                t.client_id = c_id or t.client_id
                t.client_display_name = final_c
            if final_m:
                t.matter_id = m_id or t.matter_id
                t.matter_display_name = final_m
            if clean_desc:
                t.description = clean_desc
            t.legacy_dockets_sync_status = "PENDING_CRASH_RECOVERY"
            t.changed.emit()
            self._schedule_debounced_sqlite_heartbeat()
            self.todayDocketTabsChanged.emit()
            self.primaryTimerChanged.emit()
            return

        e = self._selected_recorded_entry()
        if e is not None:
            if final_c:
                e.client_id = c_id or getattr(e, "client_id", "")
                e.client_display_name = final_c
            if final_m:
                e.matter_id = m_id or getattr(e, "matter_id", "")
                e.matter_display_name = final_m
            if clean_desc:
                e.description = clean_desc
            e.changed.emit()
            self.todayDocketTabsChanged.emit()
            self.primaryTimerChanged.emit()

    @Property(bool, notify=primaryTimerChanged)
    def hasRunningTimer(self) -> bool:
        return any(t.isRunning for t in self._timers)

    @Property(int, notify=primaryTimerChanged)
    def runningTimerCount(self) -> int:
        return sum(1 for t in self._timers if t.isRunning)

    @Property(str, notify=primaryTimerChanged)
    def runningTimerSummaryLabel(self) -> str:
        running = [t for t in self._timers if t.isRunning]
        if not running:
            return ""
        t0 = running[0]
        parts = [p for p in (t0.client_display_name, t0.matter_display_name) if p]
        return " / ".join(parts) if parts else "Active Timer"

    @Property(bool, notify=primaryTimerChanged)
    def hasActiveOrPausedTimer(self) -> bool:
        return len(self._timers) > 0

    @Property(bool, notify=primaryTimerChanged)
    def hasDisplayEntry(self) -> bool:
        if self._find_selected_draft() is not None:
            d = self._find_selected_draft() or {}
            return bool(d.get("clientName") or d.get("matterName") or d.get("description") or d.get("elapsedSeconds"))
        return bool(self._timers or self._entries)

    @Property(str, notify=primaryTimerChanged)
    def displayStatus(self) -> str:
        if self._find_selected_draft() is not None:
            return "IDLE"
        t = self._selected_active_timer()
        if t is not None:
            return "RUNNING" if t.isRunning else "PAUSED"
        e = self._selected_recorded_entry()
        if e is not None:
            return "LATEST"
        return "IDLE"

    @Property(str, notify=primaryTimerChanged)
    def displayTimerId(self) -> str:
        d = self._find_selected_draft()
        if d is not None:
            return str(d.get("tabId") or "")
        t = self._selected_active_timer()
        if t is not None:
            return t.timer_id
        e = self._selected_recorded_entry()
        return e.entry_id if e is not None else ""

    @Property(int, notify=primaryTimerChanged)
    def displayElapsedSeconds(self) -> int:
        d = self._find_selected_draft()
        if d is not None:
            return int(d.get("elapsedSeconds") or 0)
        t = self._selected_active_timer()
        if t is not None:
            return int(t.elapsedSeconds)
        e = self._selected_recorded_entry()
        if e is not None:
            return int(e.exactSeconds)
        return 0

    @Property(str, notify=primaryTimerChanged)
    def displayElapsedFormatted(self) -> str:
        return format_elapsed(self.displayElapsedSeconds)

    @Property(str, notify=primaryTimerChanged)
    def displayClientName(self) -> str:
        d = self._find_selected_draft()
        if d is not None:
            return str(d.get("clientName") or "") or "No active timer"
        t = self._selected_active_timer()
        if t is not None:
            return t.client_display_name or "Unassigned Client"
        e = self._selected_recorded_entry()
        if e is not None:
            return e.client_display_name or "Unassigned Client"
        return "No active timer"

    @Property(str, notify=primaryTimerChanged)
    def displayMatterName(self) -> str:
        d = self._find_selected_draft()
        if d is not None:
            return str(d.get("matterName") or "") or "Start a timer in CSPM"
        t = self._selected_active_timer()
        if t is not None:
            return t.matter_display_name or "Unassigned Matter"
        e = self._selected_recorded_entry()
        if e is not None:
            return e.matter_display_name or "Unassigned Matter"
        return "Start a timer in CSPM"

    @Property(str, notify=primaryTimerChanged)
    def displayDescription(self) -> str:
        d = self._find_selected_draft()
        if d is not None:
            return str(d.get("description") or "")
        t = self._selected_active_timer()
        if t is not None:
            return str(t.description or "")
        e = self._selected_recorded_entry()
        if e is not None:
            return str(e.description or "")
        return ""

    @Property(str, notify=primaryTimerChanged)
    def displayDescriptionOrPlaceholder(self) -> str:
        desc = self.displayDescription.strip()
        return desc if desc else "No description"

    @Property(str, notify=primaryTimerChanged)
    def trayTooltipText(self) -> str:
        running = [t for t in self._timers if t.isRunning]
        if len(running) > 1:
            t0 = running[0]
            return (
                f"CSPM ● {len(running)} TIMERS RUNNING ({format_elapsed(t0.elapsedSeconds)}) — "
                f"{t0.client_display_name} | {t0.matter_display_name}"
            )
        status = self.displayStatus
        if status == "RUNNING" or len(running) == 1:
            t_run = running[0] if running else self._primary_active_timer()
            if t_run is not None:
                return f"CSPM ● RUNNING ({format_elapsed(t_run.elapsedSeconds)}) — {t_run.client_display_name} | {t_run.matter_display_name}"
        if status == "PAUSED":
            return f"CSPM ⏸ PAUSED ({self.displayElapsedFormatted}) — {self.displayClientName} | {self.displayMatterName}"
        if status == "LATEST":
            return f"CSPM — Latest: {self.displayElapsedFormatted} • {self.displayClientName} ({self.displayMatterName})"
        return "CSPM — Canadian Solo Practice Manager"

    @Property(bool, notify=simultaneousTimerWarningChanged)
    def simultaneousTimerWarningVisible(self) -> bool:
        return bool(self._simultaneous_warning.get("visible"))

    @Property(str, notify=simultaneousTimerWarningChanged)
    def simultaneousTimerWarningMessage(self) -> str:
        return str(self._simultaneous_warning.get("message") or "")

    @Property("QVariantMap", notify=simultaneousTimerWarningChanged)
    def simultaneousTimerWarning(self) -> dict:
        return dict(self._simultaneous_warning or {})

    def _trigger_simultaneous_timer_warning(
        self,
        running_timer: TrayActiveTimer,
        pending_action: dict,
    ) -> None:
        self._current_monotonic = time.monotonic()
        running_sec = int(running_timer._state.get_elapsed_seconds(self._current_monotonic))
        running_hms = format_elapsed(running_sec)
        client_part = str(running_timer.client_display_name or "Unassigned Client").strip()
        matter_part = str(running_timer.matter_display_name or "Unassigned Matter").strip()
        summary_label = f"{client_part} / {matter_part}" if (client_part and matter_part) else (client_part or matter_part)
        msg = f"Another timer is already running for [{summary_label} — {running_hms}]. What would you like to do?"
        self._simultaneous_warning = {
            "visible": True,
            "runningTimerId": running_timer.timer_id,
            "runningClientName": client_part,
            "runningMatterName": matter_part,
            "runningElapsedSeconds": running_sec,
            "runningElapsedFormatted": running_hms,
            "runningSummary": f"{summary_label} — {running_hms}",
            "message": msg,
            "pendingAction": dict(pending_action),
        }
        self.simultaneousTimerWarningChanged.emit()
        self.simultaneousTimerWarningRequested.emit(dict(self._simultaneous_warning))

    @Slot(str, result=bool)
    def resolveSimultaneousTimerWarning(self, choice: str) -> bool:
        norm = str(choice or "").strip().casefold().replace("-", "_").replace(" ", "_")
        if not self._simultaneous_warning.get("visible"):
            return False
        pending = dict(self._simultaneous_warning.get("pendingAction") or {})
        self._simultaneous_warning = {}
        self.simultaneousTimerWarningChanged.emit()

        if norm in {"cancel", "dismiss", "no"}:
            return True

        allow_both = norm in {"run_both", "run_both_simultaneously", "both", "simultaneous"}
        pause_other = norm in {"pause_other", "pause_other_&_start_this_one", "pause_other_and_start_this_one", "switch", "takeover"}
        if not (allow_both or pause_other):
            return False

        if pause_other:
            for t in list(self._timers):
                if t.isRunning:
                    self.pause_timer(t.timer_id)

        kind = str(pending.get("kind") or "")
        if kind == "resume_timer":
            self._execute_resume_timer(str(pending.get("timerId") or ""), allow_simultaneous=True)
            return True
        if kind == "restart_entry":
            self._execute_restart_recorded_timer(str(pending.get("entryId") or ""), allow_simultaneous=True)
            return True
        if kind == "start_new":
            self._execute_start_new_timer(
                str(pending.get("clientName") or ""),
                str(pending.get("matterName") or ""),
                str(pending.get("description") or ""),
                str(pending.get("timeText") or ""),
                allow_simultaneous=True,
                draft_tab_id=str(pending.get("draftTabId") or ""),
            )
            return True
        return False

    @Slot(result=bool)
    def resolveSimultaneousTimerPauseOther(self) -> bool:
        return self.resolveSimultaneousTimerWarning("pause_other")

    @Slot(result=bool)
    def resolveSimultaneousTimerRunBoth(self) -> bool:
        return self.resolveSimultaneousTimerWarning("run_both")

    @Slot(result=bool)
    def resolveSimultaneousTimerCancel(self) -> bool:
        return self.resolveSimultaneousTimerWarning("cancel")

    @Property(bool, notify=legacySyncConflictChanged)
    def hasLegacySyncConflict(self) -> bool:
        return bool(self._legacy_sync_conflict.get("conflict"))

    @Property("QVariantMap", notify=legacySyncConflictChanged)
    def legacySyncConflict(self) -> dict:
        return dict(self._legacy_sync_conflict or {})

    @Property(str, notify=legacySyncConflictChanged)
    def lastSyncStatusMessage(self) -> str:
        return str(self._last_sync_status_message or "")

    def onLegacyDocketsSyncConflict(self, conflict_payload: dict) -> None:
        if not isinstance(conflict_payload, dict):
            return
        self._legacy_sync_conflict = dict(conflict_payload)
        self._last_sync_status_message = "Conflict detected in Dockets.xlsm — choose resolution"
        self.legacySyncConflictChanged.emit()
        self.legacySyncConflictDetected.emit(dict(self._legacy_sync_conflict))

    def clearLegacyDocketsSyncConflict(self) -> None:
        if self._legacy_sync_conflict:
            self._legacy_sync_conflict = {}
            self.legacySyncConflictChanged.emit()

    @Slot(str, int, bool, result="QVariantMap")
    def resolveLegacyDocketsConflict(
        self,
        resolution_mode: str,
        target_row: int = 0,
        confirm_billed_overwrite: bool = True,
    ) -> dict:
        conflict_id = str(self._legacy_sync_conflict.get("conflictId") or "").strip()
        res: dict = {}
        try:
            if hasattr(self._app_controller, "resolveLegacyDocketsSyncConflict"):
                res = dict(
                    self._app_controller.resolveLegacyDocketsSyncConflict(
                        conflict_id,
                        str(resolution_mode or ""),
                        int(target_row or 0),
                        bool(confirm_billed_overwrite),
                    )
                    or {}
                )
            else:
                repo = getattr(self._app_controller, "_excel_repo", None)
                if repo is not None and hasattr(repo, "resolve_legacy_dockets_conflict"):
                    res = dict(
                        repo.resolve_legacy_dockets_conflict(
                            self._legacy_sync_conflict or conflict_id,
                            str(resolution_mode or ""),
                            target_row=int(target_row) if int(target_row or 0) > 0 else None,
                            confirm_billed_overwrite=bool(confirm_billed_overwrite),
                        )
                        or {}
                    )
        except Exception as exc:
            res = {"ok": False, "status": "ERROR", "conflict": False, "message": str(exc)}

        if res.get("requiresBilledConfirmation"):
            self._legacy_sync_conflict = dict(res)
            self.legacySyncConflictChanged.emit()
            return res

        if not res.get("conflict"):
            self._legacy_sync_conflict = {}
            toast_msg = str(res.get("toastMessage") or "").strip()
            self._last_sync_status_message = toast_msg or "Dockets.xlsm conflict resolved"
            self.legacySyncConflictChanged.emit()
            if toast_msg:
                self.show_tray_toast(toast_msg)
            if self._pending_quit_after_conflict:
                self._pending_quit_after_conflict = False
                self._perform_confirmed_exit(skip_force_stop=self._pause_sync_quit_completed)
        return res

    @Slot(result="QVariantMap")
    def dismissLegacyDocketsConflict(self) -> dict:
        return self.resolveLegacyDocketsConflict("skip", 0, True)

    def _get_sqlite_repo(self):
        repo = getattr(self._app_controller, "_excel_repo", None)
        if repo is not None and hasattr(repo, "_get_sqlite_repo"):
            try:
                return repo._get_sqlite_repo()
            except Exception:
                pass
        dock = getattr(self._app_controller, "docketing", None)
        if dock is not None and hasattr(dock, "sqlite_repo"):
            try:
                return dock.sqlite_repo
            except Exception:
                pass
        return None

    def _upsert_timer_to_sqlite(self, t: TrayActiveTimer, *, sync_status: Optional[str] = None) -> dict:
        sq = self._get_sqlite_repo()
        if sq is None or t is None:
            return {"ok": False, "message": "SQLite repository unavailable"}
        try:
            self._current_monotonic = time.monotonic()
            elapsed_sec = max(0, int(t._state.get_elapsed_seconds(self._current_monotonic)))
            t._current_elapsed = elapsed_sec
            is_run = bool(t.isRunning)
            entry_status = "RUNNING" if is_run else "PAUSED"
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if is_run:
                if not getattr(t, "started_at_utc", None):
                    t.started_at_utc = now_utc
                started_utc = t.started_at_utc
            else:
                t.started_at_utc = None
                started_utc = None

            eff_sync_status = str(sync_status or "PENDING_CRASH_RECOVERY").strip().upper()
            t.legacy_dockets_sync_status = eff_sync_status
            today_iso = datetime.date.today().isoformat()
            eid = str(getattr(t, "sqlite_entry_id", "") or getattr(t, "linked_entry_id", "") or f"T-LIVE-{t.timer_id}-{today_iso}").strip()
            t.sqlite_entry_id = eid
            hrs = round(math.ceil(((elapsed_sec / 3600.0) * 10.0) - 1e-9) / 10.0, 2) if elapsed_sec > 0 else 0.0
            payload = {
                "entry_id": eid,
                "matter_id": str(t.matter_id or ""),
                "matter_name": str(t.matter_display_name or ""),
                "client_id": str(t.client_id or ""),
                "client_name": str(t.client_display_name or ""),
                "date": today_iso,
                "raw_seconds": elapsed_sec,
                "hours": hrs,
                "description": str(t.description or ""),
                "status": "Draft",
                "entry_status": entry_status,
                "started_at_utc": started_utc,
                "last_heartbeat_utc": now_utc,
                "legacy_dockets_sync_status": eff_sync_status,
                "legacy_dockets_row_signature": getattr(t, "legacy_dockets_row_signature", None),
            }
            repo = getattr(self._app_controller, "_excel_repo", None)
            if repo is not None and hasattr(repo, "_upsert_timer_recovery_entry"):
                try:
                    repo._upsert_timer_recovery_entry(payload)
                except Exception:
                    pass
            return dict(sq.upsert_live_docket_heartbeat(payload) or {})
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def _upsert_draft_to_sqlite(self, d: dict, *, force: bool = False) -> dict:
        sq = self._get_sqlite_repo()
        if sq is None or not isinstance(d, dict):
            return {"ok": False, "message": "SQLite repository unavailable"}
        has_content = bool(
            d.get("clientName")
            or d.get("matterName")
            or d.get("description")
            or int(d.get("elapsedSeconds") or 0) > 0
        )
        if not force and not has_content:
            return {"ok": True, "skipped": True}
        try:
            today_iso = str(d.get("date") or datetime.date.today().isoformat())[:10]
            draft_num = int(d.get("draftNumber") or 1)
            eid = str(d.get("sqliteEntryId") or f"T-DRAFT-{draft_num}-{today_iso}").strip()
            d["sqliteEntryId"] = eid
            sec = max(0, int(d.get("elapsedSeconds") or 0))
            hrs = round(math.ceil(((sec / 3600.0) * 10.0) - 1e-9) / 10.0, 2) if sec > 0 else 0.0
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            d["legacyDocketsSyncStatus"] = "PENDING_CRASH_RECOVERY"
            payload = {
                "entry_id": eid,
                "matter_id": str(d.get("matterId") or ""),
                "matter_name": str(d.get("matterName") or ""),
                "client_id": str(d.get("clientId") or ""),
                "client_name": str(d.get("clientName") or ""),
                "date": today_iso,
                "raw_seconds": sec,
                "hours": hrs,
                "description": str(d.get("description") or ""),
                "status": "Draft",
                "entry_status": "PAUSED",
                "started_at_utc": None,
                "last_heartbeat_utc": now_utc,
                "legacy_dockets_sync_status": "PENDING_CRASH_RECOVERY",
            }
            repo = getattr(self._app_controller, "_excel_repo", None)
            if repo is not None and hasattr(repo, "_upsert_timer_recovery_entry"):
                try:
                    repo._upsert_timer_recovery_entry(payload)
                except Exception:
                    pass
            return dict(sq.upsert_live_docket_heartbeat(payload) or {})
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def _schedule_debounced_sqlite_heartbeat(self) -> None:
        if hasattr(self, "_sqlite_edit_debounce_timer") and self._sqlite_edit_debounce_timer is not None:
            self._sqlite_edit_debounce_timer.start(1000)
        else:
            self._flush_debounced_sqlite_heartbeat()

    @Slot()
    def _flush_debounced_sqlite_heartbeat(self) -> None:
        d = self._find_selected_draft()
        if d is not None:
            self._upsert_draft_to_sqlite(d, force=True)
            return
        t = self._selected_active_timer() or self._primary_active_timer()
        if t is not None:
            self._upsert_timer_to_sqlite(t, sync_status="PENDING_CRASH_RECOVERY")

    def _heartbeat_running_timers_to_sqlite(self) -> None:
        self._last_sqlite_heartbeat_monotonic = self._current_monotonic
        for t in self._timers:
            if t.isRunning:
                self._upsert_timer_to_sqlite(t, sync_status="PENDING_CRASH_RECOVERY")

    def _on_commit_data_request(self, _manager=None) -> None:
        self.flush_active_timers_to_sqlite()

    @Slot(result=int)
    def flush_active_timers_to_sqlite(self) -> int:
        """Flush exact elapsed seconds of all active/paused timers and edited drafts to SQLite time_entries."""
        if self._pause_sync_quit_completed:
            return 0
        if hasattr(self, "_sqlite_edit_debounce_timer") and self._sqlite_edit_debounce_timer is not None:
            if self._sqlite_edit_debounce_timer.isActive():
                self._sqlite_edit_debounce_timer.stop()
        self._current_monotonic = time.monotonic()
        flushed = 0
        for t in self._timers:
            sync_st = getattr(t, "legacy_dockets_sync_status", "PENDING_CRASH_RECOVERY")
            if t.isRunning:
                sync_st = "PENDING_CRASH_RECOVERY"
            res = self._upsert_timer_to_sqlite(t, sync_status=sync_st)
            if res.get("ok"):
                flushed += 1
        for d in self._draft_tabs:
            res = self._upsert_draft_to_sqlite(d, force=False)
            if res.get("ok") and not res.get("skipped"):
                flushed += 1
        return flushed

    @Property(bool, notify=crashRecoveryChanged)
    def hasCrashRecoveryPrompt(self) -> bool:
        return len(self._crash_recovery_dockets) > 0

    @Property(list, notify=crashRecoveryChanged)
    def crashRecoveryDockets(self) -> list:
        return list(self._crash_recovery_dockets)

    @Property("QVariantMap", notify=crashRecoveryChanged)
    def activeCrashRecoveryDocket(self) -> dict:
        if not self._crash_recovery_dockets:
            return {}
        return dict(self._crash_recovery_dockets[0])

    @Slot(result="QVariantMap")
    def reconcileUnsyncedDocketsOnStartup(self) -> dict:
        """Query SQLite time_entries on startup for PENDING_SYNC and PENDING_CRASH_RECOVERY rows."""
        repo = getattr(self._app_controller, "_excel_repo", None)
        if repo is None or not hasattr(repo, "reconcile_unsynced_dockets_on_startup"):
            return {"ok": True, "syncedEntries": [], "conflicts": [], "crashRecoveryDockets": []}
        try:
            res = dict(repo.reconcile_unsynced_dockets_on_startup() or {})
        except Exception as exc:
            return {"ok": False, "message": str(exc), "syncedEntries": [], "conflicts": [], "crashRecoveryDockets": []}

        # 1. Handle any conflicts from PENDING_SYNC rows
        conflicts = list(res.get("conflicts") or [])
        if conflicts:
            self.onLegacyDocketsSyncConflict(conflicts[0])

        synced_entries = list(res.get("syncedEntries") or [])
        if synced_entries and not conflicts:
            self._last_sync_status_message = "Saved & synced to Dockets.xlsm"
            self.legacySyncConflictChanged.emit()
            self._hydrate_latest_entry_from_repo()

        # 2. Restore cleanly paused & synced dockets from previous session
        restored_paused = list(res.get("restoredPausedDockets") or [])
        for idx, item in enumerate(restored_paused, start=1):
            eid = str(item.get("entryId") or item.get("EntryID") or f"restored_{idx}").strip()
            if any(getattr(t, "sqlite_entry_id", "") == eid for t in self._timers):
                continue
            c_id, c_name, m_id, m_name = self._resolve_client_and_matter_labels(
                str(item.get("ClientID") or ""),
                str(item.get("ClientName") or ""),
                str(item.get("MatterID") or ""),
                str(item.get("MatterName") or item.get("MatterID") or ""),
            )
            sec = max(0, int(item.get("heartbeatSeconds") or item.get("RawSeconds") or 0))
            tid = f"restored_{eid}"
            t_obj = TrayActiveTimer(
                tid,
                c_id,
                c_name or str(item.get("ClientName") or "Unassigned Client"),
                m_id,
                m_name or str(item.get("MatterName") or "Unassigned Matter"),
                TimerState(sec, False, None),
                description=str(item.get("Description") or ""),
                parent=self,
                sqlite_entry_id=eid,
            )
            t_obj.linked_entry_id = eid
            t_obj.legacy_dockets_sync_status = "SYNCED"
            t_obj.legacy_dockets_row_signature = item.get("LegacyDocketsRowSignature")
            self._timers.append(t_obj)
            if not self._selected_tab_id:
                self._selected_tab_id = f"timer:{tid}"

        # 3. Restore PENDING_CRASH_RECOVERY rows into Today's Tabs as PAUSED and open Crash Recovery Modal
        raw_crash_list = list(res.get("crashRecoveryDockets") or [])
        formatted_crash_list: list[dict] = []
        for idx, item in enumerate(raw_crash_list, start=1):
            eid = str(item.get("entryId") or item.get("EntryID") or f"crash_{idx}").strip()
            c_id, c_name, m_id, m_name = self._resolve_client_and_matter_labels(
                str(item.get("ClientID") or ""),
                str(item.get("ClientName") or ""),
                str(item.get("MatterID") or ""),
                str(item.get("MatterName") or item.get("MatterID") or ""),
            )
            disp_c = c_name or str(item.get("ClientName") or "Unassigned Client")
            disp_m = m_name or str(item.get("MatterName") or item.get("MatterID") or "Unassigned Matter")
            desc = str(item.get("Description") or "")
            hb_sec = max(0, int(item.get("heartbeatSeconds") or item.get("RawSeconds") or 0))
            wc_sec = max(hb_sec, int(item.get("wallClockSeconds") or hb_sec))
            was_running = bool(item.get("wasRunningAtCrash", False))

            tid = f"recovered_{eid}"
            existing_t = next((t for t in self._timers if getattr(t, "sqlite_entry_id", "") == eid or t.timer_id == tid), None)
            if existing_t is None:
                t_obj = TrayActiveTimer(
                    tid,
                    c_id,
                    disp_c,
                    m_id,
                    disp_m,
                    TimerState(hb_sec, False, None),
                    description=desc,
                    parent=self,
                    sqlite_entry_id=eid,
                )
                t_obj.linked_entry_id = eid
                t_obj.legacy_dockets_sync_status = "PENDING_CRASH_RECOVERY"
                t_obj.legacy_dockets_row_signature = item.get("LegacyDocketsRowSignature")
                self._timers.insert(0, t_obj)
                self._selected_tab_id = f"timer:{tid}"

            formatted_item = {
                "entryId": eid,
                "timerId": tid,
                "clientId": c_id,
                "clientName": disp_c,
                "matterId": m_id,
                "matterName": disp_m,
                "description": desc,
                "date": str(item.get("Date") or datetime.date.today().isoformat())[:10],
                "wasRunningAtCrash": was_running,
                "entryStatusAtCrash": str(item.get("entryStatusAtCrash") or ("RUNNING" if was_running else "PAUSED")),
                "heartbeatSeconds": hb_sec,
                "heartbeatFormatted": format_elapsed(hb_sec),
                "wallClockSeconds": wc_sec,
                "wallClockFormatted": format_elapsed(wc_sec),
                "startedAtUtc": str(item.get("startedAtUtc") or ""),
                "lastHeartbeatUtc": str(item.get("lastHeartbeatUtc") or ""),
            }
            formatted_crash_list.append(formatted_item)

        self._crash_recovery_dockets = formatted_crash_list
        if formatted_crash_list or restored_paused:
            self.activeTimersChanged.emit()
            self.selectedTabChanged.emit()
            self.todayDocketTabsChanged.emit()
            self.primaryTimerChanged.emit()
        if formatted_crash_list:
            self.crashRecoveryChanged.emit()
            self.crashRecoveryRequested.emit(dict(formatted_crash_list[0]))
        return {
            "ok": True,
            "syncedEntries": synced_entries,
            "conflicts": conflicts,
            "crashRecoveryDockets": formatted_crash_list,
            "restoredPausedDockets": restored_paused,
        }

    @Slot(str, str, str, result="QVariantMap")
    def resolveCrashRecoveryDocket(
        self,
        entry_id: str,
        action: str,
        time_option: str = "heartbeat",
    ) -> dict:
        """Resolve a recovered crashed docket:
        action:
          - 'save_and_sync': Save & Enter into Dockets.xlsm Now (marks SAVED)
          - 'sync_and_keep_paused': Enter Current Time into Dockets.xlsm Now & Keep Tab Open (Paused)
          - 'discard': Discard Recovered Draft
        time_option:
          - 'heartbeat': Option A (time recorded at last_heartbeat_utc)
          - 'wall_clock': Option B (time including wall-clock gap since started_at_utc)
        """
        target_id = str(entry_id or "").strip()
        if not target_id and self._crash_recovery_dockets:
            target_id = str(self._crash_recovery_dockets[0].get("entryId") or "").strip()
        if not target_id:
            return {"ok": False, "message": "No crash recovery entry specified"}

        crash_meta = next((c for c in self._crash_recovery_dockets if str(c.get("entryId") or "") == target_id), {})
        wc_override = int(crash_meta.get("wallClockSeconds") or 0) if crash_meta else None

        repo = getattr(self._app_controller, "_excel_repo", None)
        res: dict = {"ok": False}
        if repo is not None and hasattr(repo, "resolve_crash_recovery_docket"):
            try:
                res = dict(
                    repo.resolve_crash_recovery_docket(
                        target_id,
                        str(action or ""),
                        time_option=str(time_option or "heartbeat"),
                        wall_clock_seconds=wc_override,
                    )
                    or {}
                )
            except Exception as exc:
                res = {"ok": False, "message": str(exc)}

        norm_action = str(action or "").strip().lower()
        chosen_sec = int(res.get("rawSeconds") or crash_meta.get("heartbeatSeconds") or 0)
        t_obj = next(
            (t for t in self._timers if getattr(t, "sqlite_entry_id", "") == target_id or t.timer_id == f"recovered_{target_id}"),
            None,
        )

        if norm_action == "discard":
            if t_obj is not None:
                self._timers = [t for t in self._timers if t is not t_obj]
            self._entries = [e for e in self._entries if e.entry_id != target_id]
        elif norm_action in ("sync_and_keep_paused", "keep_paused", "pause_and_sync"):
            sync_info = res.get("legacyDocketsSync") if isinstance(res.get("legacyDocketsSync"), dict) else {}
            if t_obj is not None:
                t_obj._state.accumulated_elapsed_seconds = chosen_sec
                t_obj._state.is_running = False
                t_obj._state.started_at_monotonic = None
                t_obj._current_elapsed = chosen_sec
                t_obj.legacy_dockets_sync_status = (
                    "SYNCED" if (sync_info.get("ok") and not sync_info.get("conflict")) else "PENDING_SYNC"
                )
                if sync_info.get("rowSignature"):
                    t_obj.legacy_dockets_row_signature = sync_info.get("rowSignature")
                t_obj.changed.emit()
                self._selected_tab_id = f"timer:{t_obj.timer_id}"
            if sync_info.get("conflict") or sync_info.get("status") == "CONFLICT":
                self.onLegacyDocketsSyncConflict(sync_info)
            elif sync_info.get("toastMessage"):
                self._last_sync_status_message = str(sync_info.get("toastMessage"))
                self.legacySyncConflictChanged.emit()
                self.show_tray_toast(self._last_sync_status_message)
        else:
            # 'save_and_sync'
            sync_info = res.get("legacyDocketsSync") if isinstance(res.get("legacyDocketsSync"), dict) else {}
            c_name = t_obj.client_display_name if t_obj else str(crash_meta.get("clientName") or "Client")
            m_name = t_obj.matter_display_name if t_obj else str(crash_meta.get("matterName") or "Matter")
            c_id = t_obj.client_id if t_obj else str(crash_meta.get("clientId") or "")
            m_id = t_obj.matter_id if t_obj else str(crash_meta.get("matterId") or "")
            desc = t_obj.description if t_obj else str(crash_meta.get("description") or "")
            date_str = str(crash_meta.get("date") or datetime.date.today().isoformat())[:10]
            hrs = math.ceil((chosen_sec / 3600.0) * 10.0) / 10.0 if chosen_sec > 0 else 0.0
            if t_obj is not None:
                self._timers = [t for t in self._timers if t is not t_obj]
            existing_e = next((e for e in self._entries if e.entry_id == target_id), None)
            if existing_e is not None:
                existing_e._exact_seconds = chosen_sec
                existing_e.decimal_hours = hrs
                existing_e._description = desc
                existing_e.is_today_tab = True
                existing_e.changed.emit()
            else:
                new_e = TrayRecordedEntry(
                    target_id,
                    date_str,
                    hrs,
                    c_name,
                    m_name,
                    datetime.datetime.now().strftime("%I:%M %p"),
                    exact_seconds=chosen_sec,
                    description=desc,
                    client_id=c_id,
                    matter_id=m_id,
                    parent=self,
                )
                new_e.is_today_tab = True
                self._entries.insert(0, new_e)
            self._selected_tab_id = f"entry:{target_id}"
            if sync_info.get("conflict") or sync_info.get("status") == "CONFLICT":
                self.onLegacyDocketsSyncConflict(sync_info)
            elif sync_info.get("toastMessage"):
                self._last_sync_status_message = str(sync_info.get("toastMessage"))
                self.legacySyncConflictChanged.emit()
                self.show_tray_toast(self._last_sync_status_message)

        self._crash_recovery_dockets = [
            c for c in self._crash_recovery_dockets if str(c.get("entryId") or "") != target_id
        ]
        self.crashRecoveryChanged.emit()
        self.activeTimersChanged.emit()
        self.recordedEntriesChanged.emit()
        self.selectedTabChanged.emit()
        self.todayDocketTabsChanged.emit()
        self.primaryTimerChanged.emit()
        return res

    def _collect_unsaved_or_active_dockets(self) -> list[dict]:
        self._current_monotonic = time.monotonic()
        items: list[dict] = []
        for t in self._timers:
            elapsed_sec = max(0, int(t._state.get_elapsed_seconds(self._current_monotonic)))
            sync_st = str(getattr(t, "legacy_dockets_sync_status", "PENDING_CRASH_RECOVERY") or "").upper()
            if t.isRunning or (elapsed_sec > 0 and sync_st != "SYNCED"):
                items.append({
                    "timerId": t.timer_id,
                    "entryId": str(getattr(t, "sqlite_entry_id", "") or ""),
                    "status": "RUNNING" if t.isRunning else "PAUSED",
                    "clientName": str(t.client_display_name or "Unassigned Client"),
                    "matterName": str(t.matter_display_name or "Unassigned Matter"),
                    "description": str(t.description or ""),
                    "elapsedSeconds": elapsed_sec,
                    "elapsedFormatted": format_elapsed(elapsed_sec),
                    "legacyDocketsSyncStatus": sync_st,
                })
        for d in self._draft_tabs:
            sec = max(0, int(d.get("elapsedSeconds") or 0))
            sync_st = str(d.get("legacyDocketsSyncStatus") or "PENDING_CRASH_RECOVERY").upper()
            if sec > 0 and sync_st != "SYNCED":
                items.append({
                    "timerId": str(d.get("tabId") or ""),
                    "entryId": str(d.get("sqliteEntryId") or ""),
                    "status": "PAUSED",
                    "clientName": str(d.get("clientName") or "Ad Hoc Client"),
                    "matterName": str(d.get("matterName") or "General Consultation"),
                    "description": str(d.get("description") or ""),
                    "elapsedSeconds": sec,
                    "elapsedFormatted": format_elapsed(sec),
                    "legacyDocketsSyncStatus": sync_st,
                })
        return items

    @Property(bool, notify=closeSafeguardChanged)
    def closeSafeguardVisible(self) -> bool:
        return bool(self._close_safeguard_visible)

    @Property(list, notify=closeSafeguardChanged)
    def unsavedActiveDockets(self) -> list:
        return self._collect_unsaved_or_active_dockets()

    @Property(str, notify=closeSafeguardChanged)
    def closeSafeguardSummary(self) -> str:
        items = self._collect_unsaved_or_active_dockets()
        if not items:
            return ""
        first = items[0]
        label = f"{first['clientName']} / {first['matterName']} ({first['elapsedFormatted']} • {first['status']})"
        if len(items) > 1:
            return f"{label} +{len(items) - 1} more unsaved docket(s)"
        return label

    @Slot(result=bool)
    def hasUnsavedOrActiveDocketOnClose(self) -> bool:
        return len(self._collect_unsaved_or_active_dockets()) > 0

    @Slot(str, result=bool)
    def requestCloseWithSafeguard(self, source: str = "main_window") -> bool:
        if not self.hasUnsavedOrActiveDocketOnClose():
            return False
        self._close_safeguard_visible = True
        self._close_safeguard_source = str(source or "main_window")
        self.closeSafeguardChanged.emit()
        self.closeSafeguardRequested.emit({
            "visible": True,
            "source": self._close_safeguard_source,
            "summary": self.closeSafeguardSummary,
            "dockets": self.unsavedActiveDockets,
        })
        return True

    @Slot()
    def dismissCloseSafeguard(self) -> None:
        if self._close_safeguard_visible:
            self._close_safeguard_visible = False
            self.closeSafeguardChanged.emit()

    @Slot()
    def minimizeMainWindowToTray(self) -> None:
        self.dismissCloseSafeguard()
        try:
            app = QApplication.instance()
            if app is not None:
                for win in app.topLevelWindows():
                    if win.objectName() == "CSPMMainWindow" and win.isVisible():
                        win.hide()
                        break
        except Exception:
            pass

    def _perform_confirmed_exit(self, *, skip_force_stop: bool = False) -> None:
        import logging
        self._pause_sync_quit_completed = bool(skip_force_stop)
        self.requestApplicationExit("tray-exit")
        logging.warning("[TRAY-PY] _perform_confirmed_exit: emitting requestExitFromTray")
        self.requestExitFromTray.emit()
        self._exit_failsafe_timer.start(8000)

    @Slot(str, result="QVariantMap")
    def resolveCloseSafeguard(self, action: str) -> dict:
        """Resolve the Unsaved / Active Docket Safeguard Dialog with one of 4 options:
        1. 'save_and_sync_then_quit' — Save & Sync All to Dockets.xlsm, Then Quit
        2. 'pause_sync_and_quit' — Pause, Sync Current Time to Dockets.xlsm & Quit (Resume Next Launch)
        3. 'minimize_to_tray' — Minimize to System Tray Instead
        4. 'cancel' — Cancel
        """
        norm = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        self._close_safeguard_visible = False
        self.closeSafeguardChanged.emit()

        if norm in ("cancel", "dismiss", "no"):
            return {"ok": True, "action": "cancel", "quitting": False}

        if norm in ("minimize_to_tray", "minimize", "tray"):
            self.minimizeMainWindowToTray()
            return {"ok": True, "action": "minimize_to_tray", "quitting": False}

        if norm in ("pause_sync_and_quit", "pause_and_sync_then_quit", "pause_sync_quit"):
            self._current_monotonic = time.monotonic()
            repo = getattr(self._app_controller, "_excel_repo", None)
            for t in list(self._timers):
                if t.isRunning:
                    t._state.accumulated_elapsed_seconds = t._state.get_elapsed_seconds(self._current_monotonic)
                    t._state.is_running = False
                    t._state.started_at_monotonic = None
                    t._current_elapsed = t._state.accumulated_elapsed_seconds
                    t.changed.emit()
                self._upsert_timer_to_sqlite(t, sync_status="PENDING_CRASH_RECOVERY")
                if repo is not None and hasattr(repo, "resolve_crash_recovery_docket"):
                    res = dict(
                        repo.resolve_crash_recovery_docket(
                            t.sqlite_entry_id,
                            "sync_and_keep_paused",
                            time_option="heartbeat",
                        )
                        or {}
                    )
                    sync_info = res.get("legacyDocketsSync") if isinstance(res.get("legacyDocketsSync"), dict) else {}
                    if sync_info.get("conflict") or sync_info.get("status") == "CONFLICT":
                        self.onLegacyDocketsSyncConflict(sync_info)
                    else:
                        t.legacy_dockets_sync_status = "SYNCED"
                        if sync_info.get("rowSignature"):
                            t.legacy_dockets_row_signature = sync_info.get("rowSignature")

            for d in list(self._draft_tabs):
                sec = int(d.get("elapsedSeconds") or 0)
                if sec > 0:
                    self._upsert_draft_to_sqlite(d, force=True)
                    sq_id = str(d.get("sqliteEntryId") or "")
                    if repo is not None and sq_id and hasattr(repo, "resolve_crash_recovery_docket"):
                        res = dict(
                            repo.resolve_crash_recovery_docket(
                                sq_id,
                                "sync_and_keep_paused",
                                time_option="heartbeat",
                            )
                            or {}
                        )
                        sync_info = res.get("legacyDocketsSync") if isinstance(res.get("legacyDocketsSync"), dict) else {}
                        if sync_info.get("conflict") or sync_info.get("status") == "CONFLICT":
                            self.onLegacyDocketsSyncConflict(sync_info)
                        else:
                            d["legacyDocketsSyncStatus"] = "SYNCED"

            self._pause_sync_quit_completed = True
            if self.hasLegacySyncConflict:
                self._pending_quit_after_conflict = True
                return {"ok": True, "action": "pause_sync_and_quit", "quitting": False, "awaitingConflictResolution": True}
            self._perform_confirmed_exit(skip_force_stop=True)
            return {"ok": True, "action": "pause_sync_and_quit", "quitting": True}

        # Default Option 1: 'save_and_sync_then_quit'
        for t in list(self._timers):
            self.stop_timer(t.timer_id)
        for d in list(self._draft_tabs):
            sec = int(d.get("elapsedSeconds") or 0)
            if sec > 0:
                self.saveManualTimeEntry(
                    str(d.get("clientName") or ""),
                    str(d.get("matterName") or ""),
                    str(d.get("description") or ""),
                    format_elapsed(sec),
                )
        if self.hasLegacySyncConflict:
            self._pending_quit_after_conflict = True
            return {"ok": True, "action": "save_and_sync_then_quit", "quitting": False, "awaitingConflictResolution": True}
        self._perform_confirmed_exit(skip_force_stop=False)
        return {"ok": True, "action": "save_and_sync_then_quit", "quitting": True}

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
        any_running = False
        for t in self._timers:
            t._current_elapsed = t._state.get_elapsed_seconds(self._current_monotonic)
            if t.isRunning:
                any_running = True
            t.changed.emit()
        if any_running and (self._current_monotonic - self._last_sqlite_heartbeat_monotonic) >= 5.0:
            self._heartbeat_running_timers_to_sqlite()
        self.summaryChanged.emit()
        self.primaryTimerChanged.emit()
        self.todayDocketTabsChanged.emit()
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
        allow_simultaneous = bool(data.get("allowSimultaneous", False))
        pause_others = bool(data.get("pauseOtherRunningTimers", False))
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
        timer_id = str(data.get("timerId") or data.get("ownerId") or "main_timer").strip() or "main_timer"
        clear_timer = bool(data.get("clearActiveTimer", False))

        c_id, c_name, m_id, m_name = self._resolve_client_and_matter_labels(
            raw_client_id, raw_client_name, raw_matter_id, raw_matter_name
        )

        existing = next((t for t in self._timers if t.timer_id == timer_id), None)
        if existing is None and self._timers and not allow_simultaneous and len(self._timers) == 1:
            if not is_running or pause_others or self._timers[0].timer_id == "main_timer":
                existing = self._timers[0]

        if is_running and pause_others:
            for other in self._timers:
                if other is not existing and other.isRunning:
                    other._state.accumulated_elapsed_seconds = other._state.get_elapsed_seconds(self._current_monotonic)
                    other._state.is_running = False
                    other._state.started_at_monotonic = None
                    other._current_elapsed = other._state.accumulated_elapsed_seconds
                    other.started_at_utc = None
                    self._upsert_timer_to_sqlite(other, sync_status="PENDING_CRASH_RECOVERY")
                    other.changed.emit()

        if clear_timer or (not is_running and elapsed_sec <= 0 and not bool(data.get("keepPausedZero", False))):
            if existing is not None:
                sq = self._get_sqlite_repo()
                if sq is not None and getattr(existing, "sqlite_entry_id", "") and str(existing.sqlite_entry_id).startswith("T-LIVE-"):
                    try:
                        sq.delete_time_entry(existing.sqlite_entry_id)
                    except Exception:
                        pass
                self._timers = [t for t in self._timers if t is not existing]
                self.activeTimersChanged.emit()
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
            was_running = existing.isRunning
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
            if is_running and not was_running:
                existing.started_at_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            elif not is_running:
                existing.started_at_utc = None
            if self._timers[0] is not existing:
                self._timers.remove(existing)
                self._timers.insert(0, existing)
                self.activeTimersChanged.emit()
            self._selected_tab_id = f"timer:{existing.timer_id}"
            self._upsert_timer_to_sqlite(existing, sync_status="PENDING_CRASH_RECOVERY")
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
                sqlite_entry_id=str(data.get("entryId") or ""),
            )
            self._timers.insert(0, new_timer)
            self._selected_tab_id = f"timer:{new_timer.timer_id}"
            self._upsert_timer_to_sqlite(new_timer, sync_status="PENDING_CRASH_RECOVERY")
            self.activeTimersChanged.emit()

        self.selectedTabChanged.emit()
        self.update_timers()

    @Slot('QVariantMap')
    def onDocketSaved(self, payload):
        """Update the tray's recorded entries and tabs when a docket is saved or edited in CSPM."""
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
            existing.is_today_tab = True
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
            new_entry.is_today_tab = True
            self._entries.insert(0, new_entry)

        if bool(data.get("stoppedTimer", False)):
            stopped_tid = str(data.get("timerId") or "").strip()
            sq = self._get_sqlite_repo()
            for t_rem in list(self._timers):
                if not stopped_tid or t_rem.timer_id == stopped_tid:
                    if sq is not None and getattr(t_rem, "sqlite_entry_id", "") and t_rem.sqlite_entry_id != entry_id:
                        try:
                            sq.delete_time_entry(t_rem.sqlite_entry_id)
                        except Exception:
                            pass
            if stopped_tid:
                self._timers = [t for t in self._timers if t.timer_id != stopped_tid]
            else:
                self._timers.clear()
            self._selected_tab_id = f"entry:{entry_id}"
            self.activeTimersChanged.emit()
        elif self._timers and not any(t.isRunning for t in self._timers):
            t0 = self._timers[0]
            if c_name:
                t0.client_display_name = c_name
            if m_name:
                t0.matter_display_name = m_name
            t0._description = desc
            t0.changed.emit()

        sync_info = data.get("legacyDocketsSync")
        if isinstance(sync_info, dict):
            if sync_info.get("conflict") or sync_info.get("status") == "CONFLICT":
                self.onLegacyDocketsSyncConflict(sync_info)
            elif sync_info.get("toastMessage"):
                self._last_sync_status_message = str(sync_info.get("toastMessage"))
                self.legacySyncConflictChanged.emit()

        self.selectedTabChanged.emit()
        self.recordedEntriesChanged.emit()
        self.update_timers()

    @Slot(str)
    def pause_timer(self, timer_id):
        paused_sec = 0
        paused_desc = ""
        target_tid = str(timer_id or "")
        for t in self._timers:
            if t.timer_id == target_tid or not target_tid:
                t._state.accumulated_elapsed_seconds = t._state.get_elapsed_seconds(self._current_monotonic)
                t._state.is_running = False
                t._state.started_at_monotonic = None
                t._current_elapsed = t._state.accumulated_elapsed_seconds
                t.started_at_utc = None
                paused_sec = int(t._current_elapsed)
                paused_desc = str(t.description or "")
                target_tid = t.timer_id
                self._upsert_timer_to_sqlite(t, sync_status="PENDING_CRASH_RECOVERY")
                t.changed.emit()
                break
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "pause",
            "timerId": target_tid,
            "elapsedSeconds": paused_sec,
            "description": paused_desc,
        })

    def _execute_resume_timer(self, timer_id: str, *, allow_simultaneous: bool = False):
        self._current_monotonic = time.monotonic()
        resumed_sec = 0
        c_name = ""
        m_name = ""
        desc = ""
        target_tid = str(timer_id or "")
        for t in self._timers:
            if t.timer_id == target_tid or not target_tid:
                t._state.is_running = True
                t._state.started_at_monotonic = self._current_monotonic
                t.started_at_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                resumed_sec = int(t._state.get_elapsed_seconds(self._current_monotonic))
                c_name = t.client_display_name
                m_name = t.matter_display_name
                desc = t.description
                target_tid = t.timer_id
                self._selected_tab_id = f"timer:{t.timer_id}"
                self._upsert_timer_to_sqlite(t, sync_status="PENDING_CRASH_RECOVERY")
                t.changed.emit()
                break
        self.selectedTabChanged.emit()
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "resume",
            "timerId": target_tid,
            "allowSimultaneous": bool(allow_simultaneous),
            "elapsedSeconds": resumed_sec,
            "clientName": c_name,
            "matterName": m_name,
            "description": desc,
        })

    @Slot(str)
    def resume_timer(self, timer_id):
        target = next((t for t in self._timers if t.timer_id == timer_id or not timer_id), None)
        if target is None:
            return
        other_running = next((t for t in self._timers if t.isRunning and t is not target), None)
        if other_running is not None:
            self._trigger_simultaneous_timer_warning(
                other_running,
                {"kind": "resume_timer", "timerId": target.timer_id},
            )
            return
        self._execute_resume_timer(target.timer_id)

    @Slot()
    def togglePrimaryTimer(self):
        d = self._find_selected_draft()
        if d is not None:
            self.startNewTimerWithManualTime(
                str(d.get("clientName") or ""),
                str(d.get("matterName") or ""),
                str(d.get("description") or ""),
                format_elapsed(int(d.get("elapsedSeconds") or 0)) if int(d.get("elapsedSeconds") or 0) > 0 else "",
            )
            return

        t = self._selected_active_timer()
        if t is not None:
            if t.isRunning:
                self.pause_timer(t.timer_id)
            else:
                self.resume_timer(t.timer_id)
            return

        e = self._selected_recorded_entry()
        if e is not None:
            self.restart_recorded_timer(e.entry_id)
            return
        self.start_new_timer("", "")

    @Slot()
    def stopAndSavePrimaryTimer(self):
        d = self._find_selected_draft()
        if d is not None and int(d.get("elapsedSeconds") or 0) > 0:
            self.saveManualTimeEntry(
                str(d.get("clientName") or ""),
                str(d.get("matterName") or ""),
                str(d.get("description") or ""),
                format_elapsed(int(d.get("elapsedSeconds") or 0)),
            )
            return
        t = self._selected_active_timer() or self._primary_active_timer()
        if t is not None:
            self.stop_timer(t.timer_id)

    @Slot(str, result=int)
    def parseManualTimeSeconds(self, time_text: str) -> int:
        parsed = _parse_manual_time_input(time_text)
        return int(parsed) if parsed is not None else -1

    @Slot(str, result=bool)
    def setPrimaryManualTime(self, time_text: str) -> bool:
        parsed_sec = _parse_manual_time_input(time_text)
        if parsed_sec is None:
            return False
        self._current_monotonic = time.monotonic()
        d = self._find_selected_draft()
        if d is not None:
            d["elapsedSeconds"] = int(parsed_sec)
            self._upsert_draft_to_sqlite(d, force=True)
            self.todayDocketTabsChanged.emit()
            self.primaryTimerChanged.emit()
            return True

        t = self._selected_active_timer()
        if t is not None:
            t._state.accumulated_elapsed_seconds = int(parsed_sec)
            if t._state.is_running:
                t._state.started_at_monotonic = self._current_monotonic
            t._current_elapsed = int(parsed_sec)
            self._upsert_timer_to_sqlite(t, sync_status="PENDING_CRASH_RECOVERY")
            t.changed.emit()
            self.update_timers()
            self.mainTimerCommandRequested.emit({
                "action": "set_manual_time",
                "timerId": t.timer_id,
                "elapsedSeconds": int(parsed_sec),
                "isRunning": bool(t.isRunning),
            })
            return True

        e = self._selected_recorded_entry()
        if e is not None:
            c_id, c_name, m_id, m_name = self._resolve_client_and_matter_labels(
                getattr(e, "client_id", ""),
                e.client_display_name,
                getattr(e, "matter_id", ""),
                e.matter_display_name,
            )
            new_tid = f"timer_{e.entry_id}"
            new_timer = TrayActiveTimer(
                new_tid,
                c_id,
                c_name or e.client_display_name,
                m_id,
                m_name or e.matter_display_name,
                TimerState(int(parsed_sec), False, None),
                description=e.description,
                parent=self,
                sqlite_entry_id=e.entry_id,
            )
            new_timer.linked_entry_id = e.entry_id
            self._timers.insert(0, new_timer)
            self._selected_tab_id = f"timer:{new_tid}"
            self._upsert_timer_to_sqlite(new_timer, sync_status="PENDING_CRASH_RECOVERY")
            self.selectedTabChanged.emit()
            self.activeTimersChanged.emit()
            self.update_timers()
            self.mainTimerCommandRequested.emit({
                "action": "set_manual_time",
                "timerId": new_tid,
                "elapsedSeconds": int(parsed_sec),
                "isRunning": False,
                "clientId": c_id,
                "clientName": new_timer.client_display_name,
                "matterId": m_id,
                "matterName": new_timer.matter_display_name,
                "description": new_timer.description,
            })
            return True

        new_timer = TrayActiveTimer(
            "main_timer",
            "",
            "Ad Hoc Client",
            "",
            "General Consultation",
            TimerState(int(parsed_sec), False, None),
            description="",
            parent=self,
        )
        self._timers = [new_timer]
        self._selected_tab_id = "timer:main_timer"
        self._upsert_timer_to_sqlite(new_timer, sync_status="PENDING_CRASH_RECOVERY")
        self.selectedTabChanged.emit()
        self.activeTimersChanged.emit()
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "set_manual_time",
            "timerId": "main_timer",
            "elapsedSeconds": int(parsed_sec),
            "isRunning": False,
        })
        return True

    @Slot(str)
    def updatePrimaryDescription(self, desc: str):
        clean_desc = str(desc or "")
        d = self._find_selected_draft()
        if d is not None:
            d["description"] = clean_desc
            self._schedule_debounced_sqlite_heartbeat()
            self.todayDocketTabsChanged.emit()
            self.primaryTimerChanged.emit()
            return
        t = self._selected_active_timer()
        if t is not None:
            self.update_timer_description(t.timer_id, clean_desc)
            return
        e = self._selected_recorded_entry()
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
            if not timer.matter_id or not timer.client_id:
                c_id, c_name, m_id, m_name = self._resolve_client_and_matter_labels(
                    timer.client_id,
                    timer.client_display_name,
                    timer.matter_id,
                    timer.matter_display_name,
                )
                if c_id:
                    timer.client_id = c_id
                if c_name:
                    timer.client_display_name = c_name
                if m_id:
                    timer.matter_id = m_id
                if m_name:
                    timer.matter_display_name = m_name

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

            linked_eid = str(getattr(timer, "linked_entry_id", "") or "").strip()
            sqlite_eid = str(getattr(timer, "sqlite_entry_id", "") or linked_eid).strip()
            docket_payload = {
                "entryId": linked_eid,
                "sqliteEntryId": sqlite_eid,
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

            saved_entry_id = str(save_result.get("entryId") or linked_eid or "").strip()
            sync_info = save_result.get("legacyDocketsSync")
            if isinstance(sync_info, dict):
                if sync_info.get("conflict") or sync_info.get("status") == "CONFLICT":
                    self.onLegacyDocketsSyncConflict(sync_info)
                elif sync_info.get("toastMessage"):
                    self._last_sync_status_message = str(sync_info.get("toastMessage"))
                    self.legacySyncConflictChanged.emit()

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
                existing_entry.is_today_tab = True
                existing_entry.changed.emit()
                self._entries.remove(existing_entry)
                self._entries.insert(0, existing_entry)
                saved_entry_id = existing_entry.entry_id
                self.recordedEntriesChanged.emit()
            else:
                entry_id = saved_entry_id or f"e_new_{len(self._entries)}"
                saved_entry_id = entry_id
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
                new_entry.is_today_tab = True
                self._entries.insert(0, new_entry)
                self.recordedEntriesChanged.emit()

        target_id = timer.timer_id if timer else timer_id
        self._timers = [t for t in self._timers if t.timer_id != target_id]
        if saved_entry_id:
            self._selected_tab_id = f"entry:{saved_entry_id}"
        self.selectedTabChanged.emit()
        self.activeTimersChanged.emit()
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "stopped_and_saved",
            "timerId": target_id,
            "entryId": saved_entry_id,
            "elapsedSeconds": int(elapsed_sec),
        })

    def _execute_restart_recorded_timer(self, entry_id: str, *, allow_simultaneous: bool = False):
        entry = next((e for e in self._entries if e.entry_id == entry_id), None)
        if entry is None and self._entries and not entry_id:
            entry = self._entries[0]
        if entry:
            self._current_monotonic = time.monotonic()
            new_id = f"timer_{entry.entry_id}" if allow_simultaneous or self._timers else "main_timer"
            t = TrayActiveTimer(
                new_id,
                getattr(entry, "client_id", ""),
                entry.client_display_name,
                getattr(entry, "matter_id", ""),
                entry.matter_display_name,
                TimerState(entry._exact_seconds, True, self._current_monotonic),
                description=entry.description,
                parent=self,
                sqlite_entry_id=entry.entry_id,
            )
            t.linked_entry_id = entry.entry_id
            self._entries = [e for e in self._entries if e.entry_id != entry.entry_id]
            self.recordedEntriesChanged.emit()
            self._timers = [x for x in self._timers if x.timer_id != new_id]
            self._timers.insert(0, t)
            self._selected_tab_id = f"timer:{new_id}"
            self._upsert_timer_to_sqlite(t, sync_status="PENDING_CRASH_RECOVERY")
            self.selectedTabChanged.emit()
            self.activeTimersChanged.emit()
            self.update_timers()
            self.mainTimerCommandRequested.emit({
                "action": "resume",
                "timerId": new_id,
                "entryId": entry.entry_id,
                "allowSimultaneous": bool(allow_simultaneous),
                "elapsedSeconds": int(entry._exact_seconds),
                "clientName": entry.client_display_name,
                "matterName": entry.matter_display_name,
                "description": entry.description,
            })

    @Slot(str)
    def restart_recorded_timer(self, entry_id):
        entry = next((e for e in self._entries if e.entry_id == entry_id), None)
        if entry is None and self._entries and not entry_id:
            entry = self._entries[0]
        if entry is None:
            return
        other_running = next((t for t in self._timers if t.isRunning), None)
        if other_running is not None:
            self._trigger_simultaneous_timer_warning(
                other_running,
                {"kind": "restart_entry", "entryId": entry.entry_id},
            )
            return
        self._execute_restart_recorded_timer(entry.entry_id)
            
    @Slot(str, str)
    def update_timer_description(self, timer_id, desc):
        for t in self._timers:
            if t.timer_id == timer_id or not timer_id:
                t.description = desc
                t.legacy_dockets_sync_status = "PENDING_CRASH_RECOVERY"
                break
        self._schedule_debounced_sqlite_heartbeat()
        self.primaryTimerChanged.emit()
        self.todayDocketTabsChanged.emit()
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
        self.todayDocketTabsChanged.emit()
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
                    disp = _format_matter_directory_label(m)
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

            # Filter the directory by clientName matching exactly
            filtered = [_format_matter_directory_label(m) for m in directory if m.get('clientName', '').lower() == client_name.lower()]
            if not filtered:
                # Fallback to partial match if exact match fails
                filtered = [_format_matter_directory_label(m) for m in directory if client_name.lower() in m.get('clientName', '').lower()]
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
                disp_full = _format_matter_directory_label(m).lower()
                m_num = str(m.get('matterNumber', '')).strip().lower()
                m_name = str(m.get('matterName', '')).strip().lower()
                if (
                    target_raw in (disp_raw, disp_norm, disp_full, m_num, m_name)
                    or target_norm in (disp_raw, disp_norm, disp_full)
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
        self.startNewTimerWithManualTime(client_name, matter_name, description, "")

    def _execute_start_new_timer(
        self,
        client_name: str,
        matter_name: str,
        description: str = "",
        time_text: str = "",
        *,
        allow_simultaneous: bool = False,
        draft_tab_id: str = "",
    ) -> bool:
        draft_sqlite_id = ""
        if draft_tab_id:
            matched_draft = next(
                (d for d in self._draft_tabs if str(d.get("tabId") or "") == draft_tab_id),
                None,
            )
            if matched_draft is not None:
                draft_sqlite_id = str(matched_draft.get("sqliteEntryId") or "").strip()
            self._draft_tabs = [d for d in self._draft_tabs if str(d.get("tabId") or "") != draft_tab_id]

        if not allow_simultaneous:
            existing_primary = self._selected_active_timer() or self._primary_active_timer()
            if existing_primary is not None and not existing_primary.isRunning:
                elapsed_now = existing_primary._state.get_elapsed_seconds(self._current_monotonic)
                if elapsed_now <= 0:
                    if not draft_sqlite_id and getattr(existing_primary, "sqlite_entry_id", ""):
                        draft_sqlite_id = str(existing_primary.sqlite_entry_id)
                    self._timers = [x for x in self._timers if x.timer_id != existing_primary.timer_id]

        initial_sec = 0
        if str(time_text or "").strip():
            parsed = _parse_manual_time_input(time_text)
            if parsed is not None:
                initial_sec = max(0, int(parsed))

        used_ids = {t.timer_id for t in self._timers}
        if "main_timer" not in used_ids:
            new_id = "main_timer"
        else:
            idx = 2
            while f"timer_{idx}" in used_ids:
                idx += 1
            new_id = f"timer_{idx}"

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

        self._current_monotonic = time.monotonic()
        t = TrayActiveTimer(
            new_id,
            c_id,
            c_label,
            m_id,
            m_label,
            TimerState(initial_sec, True, self._current_monotonic),
            description=clean_desc,
            sqlite_entry_id=draft_sqlite_id,
            parent=self,
        )
        self._timers = [x for x in self._timers if x.timer_id != new_id]
        self._timers.insert(0, t)
        self._selected_tab_id = f"timer:{new_id}"
        self._upsert_timer_to_sqlite(t)
        self.selectedTabChanged.emit()
        self.activeTimersChanged.emit()
        self.update_timers()
        self.mainTimerCommandRequested.emit({
            "action": "start_new",
            "timerId": new_id,
            "allowSimultaneous": bool(allow_simultaneous),
            "elapsedSeconds": int(initial_sec),
            "clientId": c_id,
            "clientName": c_label,
            "matterId": m_id,
            "matterName": m_label,
            "description": clean_desc,
        })
        return True

    @Slot(str, str, str, str, result=bool)
    def startNewTimerWithManualTime(self, client_name, matter_name, description="", time_text="") -> bool:
        running_timer = next((t for t in self._timers if t.isRunning), None)
        sel_draft = self._find_selected_draft()
        draft_tab_id = str(sel_draft.get("tabId") or "") if sel_draft is not None else ""
        if running_timer is not None:
            self._trigger_simultaneous_timer_warning(
                running_timer,
                {
                    "kind": "start_new",
                    "clientName": str(client_name or ""),
                    "matterName": str(matter_name or ""),
                    "description": str(description or ""),
                    "timeText": str(time_text or ""),
                    "draftTabId": draft_tab_id,
                },
            )
            return False

        return self._execute_start_new_timer(
            str(client_name or ""),
            str(matter_name or ""),
            str(description or ""),
            str(time_text or ""),
            allow_simultaneous=False,
            draft_tab_id=draft_tab_id,
        )

    @Slot(str, str, str, str, result=bool)
    def saveManualTimeEntry(self, client_name, matter_name, description="", time_text="") -> bool:
        parsed = _parse_manual_time_input(time_text)
        if parsed is None or parsed <= 0:
            return False

        draft_sqlite_id = ""
        sel_draft = self._find_selected_draft()
        if sel_draft is not None:
            draft_id = str(sel_draft.get("tabId") or "")
            draft_sqlite_id = str(sel_draft.get("sqliteEntryId") or "").strip()
            self._draft_tabs = [d for d in self._draft_tabs if str(d.get("tabId") or "") != draft_id]

        existing_primary = self._selected_active_timer()
        if existing_primary is not None and not existing_primary.isRunning:
            elapsed_now = existing_primary._state.get_elapsed_seconds(self._current_monotonic)
            if elapsed_now <= 0:
                if not draft_sqlite_id and getattr(existing_primary, "sqlite_entry_id", ""):
                    draft_sqlite_id = str(existing_primary.sqlite_entry_id)
                self._timers = [x for x in self._timers if x.timer_id != existing_primary.timer_id]

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

        self._current_monotonic = time.monotonic()
        temp_id = f"manual_{int(time.time() * 1000)}"
        temp_timer = TrayActiveTimer(
            temp_id,
            c_id,
            c_label,
            m_id,
            m_label,
            TimerState(int(parsed), False, None),
            description=clean_desc,
            sqlite_entry_id=draft_sqlite_id,
            parent=self,
        )
        self._timers.insert(0, temp_timer)
        self.stop_timer(temp_id)
        return True
        
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
                        self._restore_revision += 1
                        self._pending_restore_revision = self._restore_revision
                        logging.getLogger("lifecycle").info("tray restore accepted revision=%s", self._restore_revision)
                        self.requestRestoreFromTray.emit(self._restore_revision)
                    else:
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
            self.flush_active_timers_to_sqlite()
            if not self._pause_sync_quit_completed:
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
        if self.hasUnsavedOrActiveDocketOnClose():
            self.requestCloseWithSafeguard("tray_exit")
            self.calculate_flyout_geometry()
            return
        for t in list(self._timers):
            self.stop_timer(t.timer_id)
            
        missing = self.missingDescriptionEntries
        if missing:
            self.promptMissingDescriptions.emit()
        else:
            self.requestApplicationExit("tray-exit")
            logging.warning("[TRAY-PY] exit_cspm: emitting requestExitFromTray")
            self.requestExitFromTray.emit()
            self._exit_failsafe_timer.start(8000)

    @Slot()
    def force_shutdown_save(self):
        """Forcefully stops all timers and fills in missing descriptions so the app can shutdown safely."""
        if self._pause_sync_quit_completed:
            return
        import logging
        logging.info("Forcing shutdown save of all running timers.")
        for t in list(self._timers):
            if not t.description or not t.description.strip():
                t.description = "Auto-saved on system shutdown"
            self.stop_timer(t.timer_id)
            
        for e in self._entries:
            if not e.description or not e.description.strip():
                e.description = "Auto-saved on system shutdown"

    @Slot()
    def force_exit(self):
        app = QGuiApplication.instance()
        if app:
            app.quit()

    def _flyout_geometry_state_path(self) -> Path:
        paths_obj = getattr(self._app_controller, "_paths", None)
        if paths_obj is not None and hasattr(paths_obj, "state_dir"):
            return Path(paths_obj.state_dir()) / "tray_mini_popup_geometry.json"
        repo = getattr(self._app_controller, "_excel_repo", None)
        repo_paths = getattr(repo, "paths", None) if repo is not None else None
        if repo_paths is not None and hasattr(repo_paths, "state_dir"):
            return Path(repo_paths.state_dir()) / "tray_mini_popup_geometry.json"
        import os
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
        return base / "CSPM" / "state" / "tray_mini_popup_geometry.json"

    @staticmethod
    def _rect_intersects_any_screen(x: int, y: int, width: int, height: int, screen_rects: list[tuple[int, int, int, int]]) -> bool:
        if not screen_rects:
            return True
        r_left = int(x)
        r_top = int(y)
        r_right = r_left + max(1, int(width))
        r_bottom = r_top + max(1, int(height))
        for sx, sy, sw, sh in screen_rects:
            s_right = sx + sw
            s_bottom = sy + sh
            overlap_w = min(r_right, s_right) - max(r_left, sx)
            overlap_h = min(r_bottom, s_bottom) - max(r_top, sy)
            if overlap_w >= 40 and overlap_h >= 24:
                return True
        return False

    @Slot(int, int, int, int, result=bool)
    def saveMiniPopupGeometry(self, x: int, y: int, width: int, height: int) -> bool:
        import json
        import os
        try:
            w = max(self.MIN_FLYOUT_WIDTH, int(width))
            h = max(int(self.FLYOUT_HEIGHT), int(height))
            payload = {
                "x": int(x),
                "y": int(y),
                "width": w,
                "height": h,
                "updatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            state_path = self._flyout_geometry_state_path()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = state_path.with_name(f".{state_path.name}.tmp")
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(str(tmp_path), str(state_path))
            return True
        except Exception:
            return False

    @Slot(result="QVariantMap")
    def getSavedMiniPopupGeometry(self) -> dict:
        import json
        try:
            state_path = self._flyout_geometry_state_path()
            if not state_path.is_file():
                return {}
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            x = int(data["x"])
            y = int(data["y"])
            w = max(self.MIN_FLYOUT_WIDTH, int(data.get("width", self.FLYOUT_WIDTH)))
            h = max(int(self.FLYOUT_HEIGHT), int(data.get("height", self.FLYOUT_HEIGHT)))

            app = QGuiApplication.instance()
            screens = list(app.screens()) if (app is not None and hasattr(app, "screens")) else []
            screen_rects = [
                (s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height())
                for s in screens
            ]
            if self._rect_intersects_any_screen(x, y, w, h, screen_rects):
                return {"x": x, "y": y, "width": w, "height": h, "valid": True}
        except Exception:
            pass
        return {}

    @Slot()
    def calculate_flyout_geometry(self):
        saved = self.getSavedMiniPopupGeometry()
        if saved.get("valid"):
            self.flyoutGeometryCalculated.emit(
                int(saved["x"]),
                int(saved["y"]),
                int(saved["width"]),
                int(saved["height"]),
            )
            return

        cursor_pos = QCursor.pos()
        app = QGuiApplication.instance()
        screen = app.screenAt(cursor_pos) if (app and hasattr(app, "screenAt")) else None
        if not screen and app and hasattr(app, "primaryScreen"):
            screen = app.primaryScreen()
        if not screen:
            self.flyoutGeometryCalculated.emit(
                cursor_pos.x() - self.FLYOUT_WIDTH,
                cursor_pos.y() - self.FLYOUT_HEIGHT,
                self.FLYOUT_WIDTH,
                self.FLYOUT_HEIGHT,
            )
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
        self.flyoutGeometryCalculated.emit(
            res.flyout_rect.x,
            res.flyout_rect.y,
            res.flyout_rect.width,
            res.flyout_rect.height,
        )

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
