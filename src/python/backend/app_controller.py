import ctypes
import json
import logging
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QObject, Property, QRect, QTimer, QUrl, Signal, Slot, QThreadPool
from PySide6.QtGui import QCursor, QDesktopServices, QGuiApplication
from backend.workers import Worker
from services.paths import AppPaths
from services.sync_service import SyncService
from services.project_snapshot_service import ProjectSnapshotService
from services.backup_service import BackupService
from services.theme_contrast import sanitize_theme_map
from backend.themes import DEFAULT_THEME_PALETTE, THEMES_FILE, load_default_themes
from backend.platform_detect import detect_total_memory_gb, env_low_perf_override, detect_low_performance_mode
from backend.controllers.docketing_controller import DocketingController
from backend.controllers.billing_controller import BillingController
from backend.controllers.ap_controller import APController
from backend.controllers.corporate_controller import CorporateController
from backend.runtime_config import RuntimeConfig
from backend.repo_facade import LazyRepoFacade
from backend.crud_facade import CrudFacade
from backend.session_recovery import SessionRecoveryManager
from backend.omni_search import handle_omni_search_command
from backend.telemetry import TelemetryLogger

SETTINGS_FILE = "user_settings.json"
DRAFT_SESSION_FILE = "session_draft_snapshot.json"
RUNTIME_SESSION_FILE = "runtime_session_state.json"
REPORT_BRANDING_PROFILES_KEY = "reportBrandingProfiles"
LAST_REPORT_BRANDING_PROFILE_KEY = "lastReportBrandingProfileId"
LEGACY_DOCKETS_RECENT_FILES_KEY = "legacyDocketsRecentFiles"
TABLE_PREFERENCES_KEY = "tablePreferences"
DEFAULT_REPORT_BRANDING_PROFILE_ID = "cs_law"
REPORT_BRANDING_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}
DEFAULT_AUTO_BACKUP_MINUTES = 15
MIN_AUTO_BACKUP_MINUTES = 5
MAX_AUTO_BACKUP_MINUTES = 240
HOME_SUMMARY_CACHE_KEY = "homeDashboardSummaryCache"
PRACTICE_BRIEFING_FILTERS_KEY = "practiceBriefingFilters"
MAIN_WINDOW_LAYOUT_KEY = "mainWindowLayout"
PRODUCTIVITY_FORECAST_BASIS_KEY = "productivityForecastBasisDays"
PRODUCTIVITY_FORECAST_WORK_DAYS_KEY = "productivityForecastWorkDaysPerWeek"
PRODUCTIVITY_FORECAST_VACATION_DAYS_KEY = "productivityForecastVacationDays"
PRODUCTIVITY_FORECAST_HOLIDAY_DAYS_KEY = "productivityForecastHolidayDays"
PRODUCTIVITY_FORECAST_OTHER_UNAVAILABLE_DAYS_KEY = "productivityForecastOtherUnavailableDays"
PRODUCTIVITY_FORECAST_MANUAL_OVERRIDE_KEY = "productivityForecastManualOverrideEnabled"
PRODUCTIVITY_FORECAST_MANUAL_BASIS_KEY = "productivityForecastManualBasisDays"
DEFAULT_PRODUCTIVITY_FORECAST_BASIS_DAYS = 336
MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS = 1
MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS = 366
PRODUCTIVITY_FORECAST_WEEKS_PER_YEAR = 52
DEFAULT_PRODUCTIVITY_FORECAST_WORK_DAYS = 5
DEFAULT_PRODUCTIVITY_FORECAST_VACATION_DAYS = 0
DEFAULT_PRODUCTIVITY_FORECAST_HOLIDAY_DAYS = 0
DEFAULT_PRODUCTIVITY_FORECAST_OTHER_UNAVAILABLE_DAYS = 0
VALID_APP_STYLES = ("Professional",)
DEFAULT_APP_STYLE = "Professional"
AR_AGING_REPORT_IDS = {"ar_aging", "ar_aging_report", "accounts_receivable"}


def _restart_command(
    executable: Optional[str] = None,
    argv: Optional[list[str]] = None,
    frozen: Optional[bool] = None,
) -> list[str]:
    """Return the exact command that starts this app again in either mode."""
    app_executable = str(executable or sys.executable)
    app_argv = list(argv if argv is not None else sys.argv)
    if not app_argv:
        return [app_executable]
    is_frozen = bool(getattr(sys, "frozen", False) if frozen is None else frozen)
    if is_frozen:
        return [app_executable, *app_argv[1:]]
    return [app_executable, str(Path(app_argv[0]).resolve()), *app_argv[1:]]


def _powershell_wait_and_launch_script(parent_pid: int, command: list[str], working_dir: str) -> str:
    """Build a Windows-only, injection-safe delayed relaunch script."""
    if not command:
        raise ValueError("Restart command is empty.")

    def quote(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    argument_values = ", ".join(quote(value) for value in command[1:])
    argument_array = "@(" + argument_values + ")"
    return (
        "$ErrorActionPreference = 'Stop'; "
        f"Wait-Process -Id {int(parent_pid)} -ErrorAction SilentlyContinue; "
        f"Start-Process -FilePath {quote(command[0])} "
        f"-ArgumentList {argument_array} -WorkingDirectory {quote(working_dir)}"
    )


def _schedule_application_restart() -> None:
    """Launch CSPM after this single-instance process has fully exited."""
    import base64

    command = _restart_command()
    working_dir = os.getcwd()
    if not sys.platform.startswith("win"):
        subprocess.Popen(command, cwd=working_dir)
        return

    script = _powershell_wait_and_launch_script(os.getpid(), command, working_dir)
    encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    powershell_exe = os.path.join(
        os.environ.get("WINDIR", r"C:\\Windows"),
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )
    creation_flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    )
    subprocess.Popen(
        [
            powershell_exe,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded_script,
        ],
        cwd=working_dir,
        creationflags=creation_flags,
        close_fds=True,
    )


def _safe_atomic_json_write(target_path: Path, payload: dict) -> bool:
    import tempfile
    import os
    import json
    tmp_path = None
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path_str = tempfile.mkstemp(dir=str(target_path.parent), prefix="settings_", suffix=".json.tmp")
        tmp_path = Path(tmp_path_str)
        
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
            f.flush()
            if hasattr(os, "fsync"):
                os.fsync(f.fileno())
        
        # verify it's valid
        with open(tmp_path, "r", encoding="utf-8") as f:
            json.load(f)
        
        # replace target atomically
        tmp_path.replace(target_path)
        return True
    except Exception as exc:
        logging.getLogger("theme.persistence").warning(
            "_safe_atomic_json_write failed path=%s err=%s",
            str(target_path),
            str(exc),
        )
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return False

def _normalize_startup_launch_context(context: Optional[Dict[str, Any]]) -> Dict[str, int]:
    normalized = {"cursorX": 0, "cursorY": 0, "screenIndex": 0}
    try:
        if isinstance(context, dict):
            normalized["cursorX"] = int(context.get("cursorX", 0) or 0)
            normalized["cursorY"] = int(context.get("cursorY", 0) or 0)
            normalized["screenIndex"] = int(context.get("screenIndex", 0) or 0)
        else:
            cursor_pos = QCursor.pos()
            normalized["cursorX"] = int(cursor_pos.x())
            normalized["cursorY"] = int(cursor_pos.y())
            screens = list(QGuiApplication.screens() or [])
            cursor_screen = QGuiApplication.screenAt(cursor_pos) if screens else None
            if cursor_screen is None and screens:
                for screen in screens:
                    if screen.geometry().contains(cursor_pos):
                        cursor_screen = screen
                        break
            if cursor_screen is not None:
                for index, screen in enumerate(screens):
                    if screen is cursor_screen or (
                        screen.name() == cursor_screen.name()
                        and screen.geometry() == cursor_screen.geometry()
                    ):
                        normalized["screenIndex"] = int(index)
                        break
        screens = list(QGuiApplication.screens() or [])
        if screens:
            normalized["screenIndex"] = max(
                0,
                min(int(normalized["screenIndex"]), len(screens) - 1),
            )
        else:
            normalized["screenIndex"] = 0
    except Exception:
        normalized = {"cursorX": 0, "cursorY": 0, "screenIndex": 0}
    return normalized


class AppController(QObject):
    themeChanged = Signal()
    appStyleChanged = Signal()
    soundEffectsChanged = Signal()
    masterDataDirChanged = Signal()
    localDataDirChanged = Signal()
    autoBackupMinutesChanged = Signal()
    autoBackupIntervalMinsChanged = Signal()
    settingsChanged = Signal()
    toast = Signal(str)
    error = Signal(str)
    clientDataChanged = Signal()
    transactionDataChanged = Signal()
    transactionLookupDataChanged = Signal()
    backendBootChanged = Signal()
    requestMainWindowLoad = Signal()
    runAtStartupChanged = Signal()
    keepTrayAliveChanged = Signal()
    homeDashboardSummaryUpdated = Signal(dict)
    startupFirstInputSeenChanged = Signal()
    importProgress = Signal(str, int, int)  # phase, current, total
    importFinished = Signal(dict)  # full results dict
    importDuplicateFound = Signal(dict)  # duplicate prompt payload with requestId
    # Statement preparation reads and reconciles workbook data.  These signals
    # keep that work off the QML event loop so a report tab can render its
    # loading state immediately instead of appearing to hang.
    statementBillingClientsReady = Signal(str, "QVariantList")
    statementBillingClientsFailed = Signal(str, str)
    statementOfAccountReady = Signal(str, "QVariantMap")
    statementOfAccountFailed = Signal(str, str)
    # Matter financial cards must not make the editable Matter screen look
    # frozen while Excel-backed WIP/A/R data is being read.
    matterFinancialSummaryReady = Signal(str, "QVariantMap")
    matterFinancialSummaryFailed = Signal(str, str)

    def __init__(
        self,
        paths=None,
        runtime_config: Optional[RuntimeConfig] = None,
        defer_settings_load: bool = False,
        startup_launch_context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        import time
        t0 = time.perf_counter()
        startup_logger = logging.getLogger("startup")
        self._startup_launch_context = _normalize_startup_launch_context(startup_launch_context)
        
        def _elapsed() -> str:
            return f"[{time.perf_counter()-t0:.3f}s]"
        
        startup_logger.info("%s AppController.__init__ BEGIN", _elapsed())
        self._paths = paths if paths is not None else self._resolve_paths()
        startup_logger.info("%s AppController resolved paths", _elapsed())
        self._runtime_config = runtime_config if runtime_config is not None else RuntimeConfig()
        self._legacy_settings_path = self._paths.executable_root() / SETTINGS_FILE
        self._settings_path = self._paths.user_settings_path()
        self._prefs_settings_path = self._paths.prefs_path()
        
        # --- PHASE 2: SYNCHRONOUS MINIMUM LOAD FOR PATH SELECTION ---
        startup_logger.info("%s AppController synchronous minimum settings load for paths", _elapsed())
        _init_payload = self._collect_settings_payload(
            self._settings_path,
            self._legacy_settings_path,
            self._prefs_settings_path,
        )
        _init_loaded = _init_payload.get("loaded", {})
        _init_local = str(_init_loaded.get("localDataDir", "")).strip()
        _init_master = str(_init_loaded.get("masterDataDir", "")).strip()
        
        # --- PHASE 4: EMPTY-DATA SAFETY BARRIER ---
        from PySide6.QtWidgets import QMessageBox, QApplication
        import sys as _sys
        import json as _json
        
        def is_valid_package(d: Path) -> bool:
            return (d / "CSPM.xlsm").exists() and (d / "Dockets.xlsm").exists()

        def is_blank_seeded_package(d: Path) -> bool:
            c = d / "CSPM.xlsm"
            if not c.exists(): return False
            return c.stat().st_size < 50000

        project_data_path = self._paths.project_root() / "data"
        frozen_dev_data_path = self._paths.executable_root().parent.parent / "data"
        
        if _init_local:
            local_path = Path(_init_local)
            if not local_path.exists() or not is_valid_package(local_path):
                if QApplication.instance():
                    QMessageBox.critical(
                        None, 
                        "Data Unavailable", 
                        f"The configured active data folder is unavailable or invalid:\n{local_path}\n\nPlease locate it in settings or restore it."
                    )
                _sys.exit(1)
            else:
                self._paths.override_data_dir = local_path
        else:
            default_data = self._paths._persistent_data_root() / "data"
            is_blank = not default_data.exists() or is_blank_seeded_package(default_data)
            
            detected_existing_path = None
            if is_valid_package(project_data_path) and not is_blank_seeded_package(project_data_path):
                detected_existing_path = project_data_path
            elif is_valid_package(frozen_dev_data_path) and not is_blank_seeded_package(frozen_dev_data_path):
                detected_existing_path = frozen_dev_data_path
                
            if is_blank and detected_existing_path:
                if QApplication.instance():
                    msg = QMessageBox(None)
                    msg.setWindowTitle("Data Package Detected")
                    msg.setText("An existing CSPM data package was detected, but no active folder is configured. What would you like to do?")
                    msg.setInformativeText(f"Detected: {detected_existing_path}")
                    btn_use = msg.addButton("Use Existing Data Folder", QMessageBox.AcceptRole)
                    btn_new = msg.addButton("Start a New Empty Practice", QMessageBox.DestructiveRole)
                    btn_cancel = msg.addButton("Cancel", QMessageBox.RejectRole)
                    msg.exec()
                    
                    if msg.clickedButton() == btn_use:
                        self._paths.override_data_dir = detected_existing_path
                        _init_local = str(detected_existing_path)
                        _init_loaded["localDataDir"] = _init_local
                        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            with open(self._settings_path, "w", encoding="utf-8") as f:
                                _json.dump(_init_loaded, f, indent=4)
                        except Exception as e:
                            startup_logger.error(f"Failed to save selected data folder: {e}")
                    elif msg.clickedButton() == btn_cancel:
                        _sys.exit(0)

        if _init_master:
            self._paths.override_master_dir = Path(_init_master)
            
        self._local_data_dir = _init_local
        self._master_data_dir = _init_master
        
        startup_logger.info("%s AppController creating snapshot service", _elapsed())
        self._snapshot_service = ProjectSnapshotService(self._paths)
        self._sync_service = SyncService(self._paths)
        self._shutdown_sync_complete = False
        
        self._app_version = self._load_app_version()
        
        startup_logger.info("%s AppController creating backup service", _elapsed())
        self._backup_service = BackupService(self._paths, app_version=self._app_version)
        
        startup_logger.info("%s AppController creating excel repo", _elapsed())
        self._excel_repo = LazyRepoFacade(
            self._paths,
            write_guard=self._sync_service.assert_write_lease,
        )
        self._telemetry = TelemetryLogger(self._paths.data_dir())
        self._is_booted = False
        
        startup_logger.info("%s AppController creating CRUD facade", _elapsed())
        self._crud = CrudFacade(
            repo=self._excel_repo,
            report_failure=self._report_failure,
            is_booted=lambda: self._is_booted,
        )
        startup_logger.info("%s AppController creating session manager", _elapsed())
        self._draft_session_path = self._paths.root / DRAFT_SESSION_FILE
        self._runtime_session_path = self._paths.state_dir() / RUNTIME_SESSION_FILE
        self._session_mgr = SessionRecoveryManager(
            draft_session_path=self._draft_session_path,
            runtime_session_path=self._runtime_session_path,
            report_failure=self._report_failure,
        )
        self._pending_close_recovery = self._session_mgr.load_pending_close_recovery()
        self._auto_backup_minutes = self._resolve_auto_backup_minutes()
        self._auto_backup_enabled = self._auto_backup_minutes > 0
        self._auto_backup_timer = QTimer(self)
        self._startup_snapshot_scheduled = False
        self._themes_data = {}
        self._theme_name = "Dark"
        self._app_style = DEFAULT_APP_STYLE
        self._sound_effects_enabled = True
        # Removed duplicate assignments to preserve Phase 2/4 values
        # self._master_data_dir = ""
        # self._local_data_dir = ""
        self._auto_backup_interval_mins = 0
        self._run_at_startup = False
        self._keep_tray_alive = True
        self._settings_data: Dict[str, Any] = {}
        self._low_performance_mode = self._detect_low_performance_mode()
        self._global_timer_lock: Dict[str, Any] = {}
        self._startup_trace_logger = logging.getLogger("startup")
        self._startup_trace_epoch_perf = time.perf_counter()
        self._startup_lag_trace_active = True
        self._startup_lag_trace_auto_off_ms = 45000
        self._startup_first_input_seen = False
        self._expert_preview_process = None
        
        startup_logger.info("%s AppController loading dashboard cache", _elapsed())
        self._home_dashboard_summary_cache = self._load_home_dashboard_summary_cache()
        self._startup_boot_inflight = False
        self._startup_metadata_warm_running = False
        self._startup_metadata_warm_scheduled = False
        self._settings_load_started = False
        self._settings_load_complete = False
        # Keep bootstrap work independent from the deferred settings read.  The
        # previous one-thread pool could leave the data backend queued forever
        # if the settings worker stalled, which made workbook-backed screens
        # appear empty even though the workbook contained data.
        self._background_pool = QThreadPool(self)
        self._background_pool.setMaxThreadCount(2)
        self._background_pool.setExpiryTimeout(60000)
        self._background_low_priority = -2
        # QThreadPool owns the native QRunnable after start(), but keeping a
        # Python reference until its finished signal prevents wrapper lifetime
        # differences (notably in frozen builds) from dropping a queued task.
        self._background_workers: Dict[int, Worker] = {}
        self._legacy_import_state_lock = threading.Lock()
        self._legacy_import_active = False
        self._legacy_import_cancellation = None
        self._legacy_import_duplicate_lock = threading.Lock()
        self._legacy_import_duplicate_pending: Dict[str, Dict[str, Any]] = {}
        self.error.connect(self._record_error_signal)
        self.toast.connect(self._record_toast_signal)

        startup_logger.info("%s AppController creating docketing controller", _elapsed())
        self._docketing_controller = DocketingController(self._excel_repo)
        self._docketing_controller.error.connect(self.error.emit)
        self._docketing_controller.toast.connect(self.toast.emit)
        self._docketing_controller.transactionDataChanged.connect(
            self.transactionDataChanged.emit
        )
        self._docketing_controller.transactionLookupDataChanged.connect(
            self.transactionLookupDataChanged.emit
        )

        startup_logger.info("%s AppController creating billing controller", _elapsed())
        from services.invoice_draft_service import InvoiceDraftService
        from services.invoice_document_service import InvoiceDocumentService
        from services.paths import AppPaths
        _templates_dir = str(AppPaths.executable_root() / "src" / "templates" / "invoices")
        self._invoice_draft_svc = InvoiceDraftService(self._excel_repo)
        self._invoice_doc_svc = InvoiceDocumentService(_templates_dir)
        self._billing_controller = BillingController(
            self._excel_repo, self._invoice_draft_svc, self._invoice_doc_svc
        )
        self._billing_controller.error.connect(self.error.emit)
        self._billing_controller.toast.connect(self.toast.emit)

        # Accounts Payable: owned on the same public app surface as docketing/billing.
        # ExcelRepo remains the Transactions Master / matter-disbursement gateway;
        # APWorkbookRepository owns APBills and APPayments.
        startup_logger.info("%s AppController creating accounts payable controller", _elapsed())
        from repositories.ap_workbook_repository import APWorkbookRepository
        from services.ap_orchestration_service import APOrchestrationService
        from services.supplier_document_service import SupplierDocumentService

        ap_workbook_path = self._paths.workbook_path()
        self._ap_repository = None
        self._ap_orchestration = None
        self._ap_controller = None
        if ap_workbook_path.is_file():
            self._ap_repository = APWorkbookRepository(ap_workbook_path)
            self._ap_orchestration = APOrchestrationService(
                self._ap_repository,
                self._excel_repo,
                SupplierDocumentService(
                    self._paths.master_data_dir(),
                    self._paths.data_dir(),
                ),
            )
            self._ap_controller = APController(
                self._excel_repo,
                orchestration_service=self._ap_orchestration,
                parent=self,
            )
            self._ap_controller.error.connect(self.error.emit)
            self._ap_controller.toast.connect(self.toast.emit)
        else:
            startup_logger.warning(
                "%s AP controller deferred; workbook not found at %s",
                _elapsed(),
                ap_workbook_path,
            )

        startup_logger.info("%s AppController creating corporate controller", _elapsed())
        self._corporate_controller = CorporateController(self._excel_repo)

        startup_logger.info("%s AppController reloading themes", _elapsed())
        self.reload_themes()
        if defer_settings_load:
            startup_logger.info("%s AppController priming deferred theme preference", _elapsed())
            self._prime_deferred_theme_preference()
            self._settings_data["theme"] = self._theme_name
            self._settings_data["appStyle"] = self._app_style
            self._settings_data["soundEffectsEnabled"] = self._sound_effects_enabled
            self._ensure_report_branding_settings()
            startup_logger.info(
                "%s AppController deferring settings load until post-settle request",
                _elapsed(),
            )
        else:
            startup_logger.info("%s AppController loading settings", _elapsed())
            self.load_settings()
        self._session_mgr.mark_runtime_open()

        if self._auto_backup_enabled:
            self._auto_backup_timer.setInterval(self._auto_backup_minutes * 60 * 1000)
            self._auto_backup_timer.timeout.connect(self._run_auto_backup_tick)
            self._auto_backup_timer.start()
        
        startup_logger.info("%s AppController.__init__ END", _elapsed())

    def _load_app_version(self) -> str:
        try:
            ver_path = self._paths.root / "version.json"
            if ver_path.exists():
                with open(ver_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return str(data.get("version", "2.4.0"))
        except Exception:
            pass
        return "2.4.0"

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return self._app_version

    def _record_error_signal(self, message: str) -> None:
        logging.getLogger("app.error").error("ui-error-signal message=%s", str(message or ""))

    def _record_toast_signal(self, message: str) -> None:
        logging.getLogger("app.toast").info("ui-toast-signal message=%s", str(message or ""))

    def _report_failure(
        self,
        user_message: str,
        *,
        context: str,
        exc: Optional[BaseException] = None,
        emit_signal: bool = True,
    ) -> None:
        logger = logging.getLogger("app.failure")
        if exc is None:
            logger.error("context=%s message=%s", context, user_message)
            message = user_message
        else:
            logger.exception("context=%s message=%s", context, user_message, exc_info=(type(exc), exc, exc.__traceback__))
            detail = str(exc).strip()
            message = user_message if not detail else f"{user_message}: {detail}"
        if emit_signal:
            self.error.emit(message)

    @Slot(str, str)
    @Slot(str, str, str)
    def reportUiFailure(self, context: str, detail: str, user_message: str = "") -> None:
        fallback = str(user_message or "Operation failed.")
        detail_text = str(detail or "").strip()
        if detail_text:
            self._report_failure(fallback, context=str(context or "qml"), exc=RuntimeError(detail_text))
        else:
            self._report_failure(fallback, context=str(context or "qml"), exc=None)

    @Slot(str, str)
    def reportUiSilentFailure(self, context: str, detail: str) -> None:
        detail_text = str(detail or "").strip()
        context_str = str(context or "qml.silent")
        if detail_text:
            self._report_failure("Silent UI exception caught", context=context_str, exc=RuntimeError(detail_text), emit_signal=False)
        else:
            self._report_failure("Silent UI exception caught", context=context_str, exc=None, emit_signal=False)

    # ── SECTION: Startup / Trace ──────────────────────────────────────────────

    def _is_startup_lag_trace_active(self) -> bool:
        if not self._startup_lag_trace_active:
            return False
        try:
            elapsed_ms = max(
                0.0, (time.perf_counter() - self._startup_trace_epoch_perf) * 1000.0
            )
            if elapsed_ms > float(self._startup_lag_trace_auto_off_ms):
                self._startup_lag_trace_active = False
                return False
        except Exception:
            self._startup_lag_trace_active = False
            return False
        return True

    def _trace_startup_backend_step(
        self, step: str, started_perf: Optional[float] = None
    ) -> None:
        if not self._is_startup_lag_trace_active():
            return
        try:
            now_perf = time.perf_counter()
            t_plus = max(0.0, now_perf - self._startup_trace_epoch_perf)
            if isinstance(started_perf, (int, float)):
                dur_s = max(0.0, now_perf - float(started_perf))
                self._startup_trace_logger.info(
                    "[BACKEND-TRACE] %s [t+%.3fs, dur=%.3fs]", step, t_plus, dur_s
                )
            else:
                self._startup_trace_logger.info(
                    "[BACKEND-TRACE] %s [t+%.3fs]", step, t_plus
                )
        except Exception:
            pass

    @Slot()
    def markStartupFirstPixelSeen(self):
        if self._startup_lag_trace_active:
            self._trace_startup_backend_step("markStartupFirstPixelSeen")
        self._startup_lag_trace_active = False

    @Property(bool, notify=startupFirstInputSeenChanged)
    def startupFirstInputSeen(self) -> bool:
        return bool(self._startup_first_input_seen)

    @Slot(str)
    def markStartupFirstInputSeen(self, input_type: str = "") -> None:
        if self._startup_first_input_seen:
            return
        self._startup_first_input_seen = True
        self.startupFirstInputSeenChanged.emit()
        try:
            self._trace_startup_backend_step(
                "markStartupFirstInputSeen type=" + str(input_type or "")
            )
        except Exception:
            pass

    def _start_background_worker(
        self,
        fn,
        *,
        name: str,
        on_result=None,
        on_error=None,
        priority: Optional[int] = None,
    ) -> None:
        worker = Worker(fn, name=name)
        worker_key = id(worker)
        self._background_workers[worker_key] = worker

        def release_worker() -> None:
            self._background_workers.pop(worker_key, None)

        worker.signals.finished.connect(release_worker)
        if callable(on_result):
            def dispatch_result(res):
                QTimer.singleShot(0, lambda r=res: on_result(r))
            worker.signals.result.connect(dispatch_result)
        if callable(on_error):
            def dispatch_error(err):
                QTimer.singleShot(0, lambda e=err: on_error(e))
            worker.signals.error.connect(dispatch_error)
        prio = self._background_low_priority if priority is None else int(priority)
        try:
            self._background_pool.start(worker, prio)
        except Exception:
            self._background_workers.pop(worker_key, None)
            raise

    def _schedule_startup_metadata_warm(self) -> None:
        if not self._is_booted:
            return
        if self._startup_metadata_warm_running:
            return
        self._startup_metadata_warm_running = True
        self._trace_startup_backend_step("startup_metadata_warm start")
        warm_start = time.perf_counter()

        def _do_warm() -> Dict[str, Any]:
            return dict(self._excel_repo.warm_startup_metadata_cache() or {})

        def _on_warm_done(result: Dict[str, Any]) -> None:
            self._startup_metadata_warm_running = False
            warmed = int(result.get("tablesWarmed", 0) or 0) if isinstance(result, dict) else 0
            failed = int(result.get("tablesFailed", 0) or 0) if isinstance(result, dict) else 0
            logging.getLogger("startup").info(
                "[BACKEND-TRACE] startup_metadata_warm complete [%.3fs] tables=%d failed=%d",
                max(0.0, time.perf_counter() - warm_start),
                warmed,
                failed,
            )
            self._trace_startup_backend_step("startup_metadata_warm complete", warm_start)

        def _on_warm_error(err_tuple) -> None:
            self._startup_metadata_warm_running = False
            _, exc, _ = err_tuple
            logging.getLogger("startup").warning("startup_metadata_warm failed: %s", exc)

        self._start_background_worker(
            _do_warm,
            name="startup_metadata_warm",
            on_result=_on_warm_done,
            on_error=_on_warm_error,
            priority=self._background_low_priority,
        )

    @Slot()
    def boot_backend(self):
        """
        Deferred initialization triggered by QML after splash + opening animation settles.
        """
        startup_logger = logging.getLogger("startup")
        if self._is_booted:
            startup_logger.info("[BACKEND-TRACE] boot_backend skipped (already booted)")
            return
        if self._startup_boot_inflight:
            startup_logger.info("[BACKEND-TRACE] boot_backend skipped (inflight)")
            return
        
        self._startup_boot_inflight = True
        boot_start = time.perf_counter()
        self._trace_startup_backend_step("boot_backend invoked")
        startup_logger.info("[BACKEND-TRACE] boot_backend start")
        startup_logger.info("Booting backend (Excel schemas, data models)...")

        def _do_boot():
            schema_start = time.perf_counter()
            self._trace_startup_backend_step("_bootstrap_workbook_schema start")
            self._bootstrap_workbook_schema()
            self._trace_startup_backend_step("_bootstrap_workbook_schema complete", schema_start)
            return boot_start

        self._start_background_worker(
            _do_boot,
            name="backend_boot",
            on_result=self._on_boot_complete,
            on_error=lambda err: self._on_boot_failed(err, boot_start),
            priority=self._background_low_priority,
        )

    def _on_boot_complete(self, boot_start: float):
        startup_logger = logging.getLogger("startup")
        self._startup_boot_inflight = False
        self._is_booted = True
        self.backendBootChanged.emit()
        if self._auto_backup_enabled and not self._startup_snapshot_scheduled:
            self._startup_snapshot_scheduled = True
            QTimer.singleShot(15000, self._run_startup_snapshot)
        if not self._startup_metadata_warm_scheduled:
            self._startup_metadata_warm_scheduled = True
            QTimer.singleShot(2200, self._schedule_startup_metadata_warm)
        startup_logger.info("Backend boot complete.")
        self._trace_startup_backend_step("boot_backend complete", boot_start)
        startup_logger.info(
            "[BACKEND-TRACE] boot_backend complete [%.3fs]",
            max(0.0, time.perf_counter() - boot_start),
        )

    def _on_boot_failed(self, err_tuple, boot_start: float):
        startup_logger = logging.getLogger("startup")
        self._startup_boot_inflight = False
        _, exc, _ = err_tuple
        self._is_booted = False
        self.error.emit(f"Backend boot failed: {exc}")
        startup_logger.error("Backend boot failed: %s", exc)
        startup_logger.exception(
            "[BACKEND-TRACE] boot_backend failed after %.3fs",
            max(0.0, time.perf_counter() - boot_start),
        )

    def _resolve_paths(self, paths=None) -> AppPaths:
        if isinstance(paths, AppPaths):
            return paths
        if isinstance(paths, (str, Path)):
            return AppPaths(Path(paths))
        return AppPaths(AppPaths.project_root())

    @staticmethod
    def _resolve_auto_backup_minutes() -> int:
        raw = os.environ.get("CSPM_AUTOBACKUP_MINUTES", "").strip()
        if raw == "":
            return DEFAULT_AUTO_BACKUP_MINUTES
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return DEFAULT_AUTO_BACKUP_MINUTES
        if value <= 0:
            return 0
        if value < MIN_AUTO_BACKUP_MINUTES:
            return MIN_AUTO_BACKUP_MINUTES
        if value > MAX_AUTO_BACKUP_MINUTES:
            return MAX_AUTO_BACKUP_MINUTES
        return value

    def _run_startup_snapshot(self) -> None:
        self._create_project_snapshot("startup-baseline", emit_toast=False)

    def _run_auto_backup_tick(self) -> None:
        self._create_project_snapshot("scheduled-auto-backup", emit_toast=False)

    def _create_project_snapshot(self, reason: str, emit_toast: bool) -> bool:
        try:
            # We now use the new BackupService for snapshots as well, or we can keep ProjectSnapshotService
            # We'll keep ProjectSnapshotService for the old 'snapshot' auto-backups, and use BackupService for the new managed packages.
            snapshot_dir = self._snapshot_service.create_snapshot(reason=reason or "manual")
            if not snapshot_dir:
                return False
            if emit_toast:
                self.toast.emit(f"Backup snapshot saved: {snapshot_dir.name}")
            return True
        except Exception as exc:
            self._report_failure("Snapshot creation failed.", context="snapshot.create", exc=exc)
            return False

    @Slot(str, bool, result=str)
    def createManagedBackup(self, reason: str, protected: bool) -> str:
        try:
            res = self._backup_service.create_snapshot(reason=reason, protected=protected, force=True)
            if res.get("ok"):
                self.toast.emit(f"Backup created: {res.get('package_name')}")
            else:
                self.error.emit(f"Backup failed: {res.get('message')}")
            return json.dumps(res)
        except Exception as exc:
            self._report_failure("Managed backup creation failed", context="backup.create", exc=exc)
            return json.dumps({"ok": False, "message": str(exc)})

    @Slot(result=str)
    def listManagedBackups(self) -> str:
        try:
            snaps = self._backup_service.list_snapshots()
            return json.dumps({"ok": True, "snapshots": snaps})
        except Exception as exc:
            return json.dumps({"ok": False, "message": str(exc)})

    @Slot(str, bool, result=bool)
    def protectManagedBackup(self, pkg: str, protected: bool) -> bool:
        try:
            res = self._backup_service.protect_snapshot(pkg, protected)
            if res:
                self.toast.emit(f"Snapshot protection updated.")
            return res
        except Exception:
            return False

    @Slot(str, result=str)
    def prepareManagedRestore(self, pkg: str) -> str:
        try:
            res = self._backup_service.prepare_restore(pkg)
            if res.get("ok"):
                self.toast.emit("Restore prepared. Please open the recovery utility.")
            else:
                self.error.emit(f"Prepare restore failed: {res.get('message')}")
            return json.dumps(res)
        except Exception as exc:
            self._report_failure("Restore preparation failed", context="backup.restore", exc=exc)
            return json.dumps({"ok": False, "message": str(exc)})

    @Slot(result=bool)
    def openRecoveryUtility(self) -> bool:
        try:
            # Launch cspm_recovery.py in a new console window
            script_path = self._paths.root / "scripts" / "cspm_recovery.py"
            if not script_path.exists():
                self.error.emit("Recovery utility script not found.")
                return False
            
            # Start in a new terminal window
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "cmd.exe", "/k", sys.executable, str(script_path)],
                cwd=str(self._paths.root),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            return True
        except Exception as exc:
            self._report_failure("Failed to open recovery utility", context="backup.recovery", exc=exc)
            return False

    def _bootstrap_workbook_schema(self) -> None:
        try:
            workbook_exists = self._paths.workbook_path().exists()
            startup_logger = logging.getLogger("startup")
            migration_probe = getattr(self._excel_repo, "schema_requires_migration", None)
            ensure_schema_fn = getattr(self._excel_repo, "ensure_schema", None)
            if not callable(ensure_schema_fn):
                self._report_failure(
                    "Workbook schema bootstrap failed.",
                    context="startup.schema_bootstrap",
                    exc=RuntimeError("repo missing ensure_schema"),
                )
                return
            needs_migration = False
            probe_supported = callable(migration_probe)
            if probe_supported:
                needs_migration = bool(migration_probe())
            else:
                startup_logger.warning(
                    "Workbook schema migration probe unavailable; running ensure_schema defensively."
                )
            
            # Yield the GIL explicitly to allow PySide6 main thread to process 
            # native window move/resize events before the next heavy openpyxl block.
            time.sleep(0.05)
            
            if workbook_exists and needs_migration:
                self._create_project_snapshot("pre-workbook-schema-migration", emit_toast=False)
            
            if not workbook_exists or needs_migration or not probe_supported:
                ensure_schema_fn()
        except Exception as exc:
            self._report_failure("Workbook schema bootstrap failed.", context="startup.schema_bootstrap", exc=exc)

    @staticmethod
    def _env_low_perf_override():
        return env_low_perf_override()

    @staticmethod
    def _detect_total_memory_gb() -> float:
        return detect_total_memory_gb()

    def _detect_low_performance_mode(self) -> bool:
        return detect_low_performance_mode()

    def reload_themes(self):
        from backend.themes import load_themes_from_file, load_default_themes as _load_default_themes
        self._themes_data = load_themes_from_file(THEMES_FILE)
        if self._theme_name not in self._themes_data:
            self._theme_name = "Dark"

    def _normalize_theme_name(self, value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return "Light"
        normalized = value.strip().lower()
        if not normalized:
            return "Light"
            
        if normalized in ("light", "white", "professional", "professional-light", "classic", "legacy", "default", "system", "auto"):
            return "Light"
            
        if normalized in ("dark", "gray", "blue", "red", "green", "purple", "navy", "professional-dark", "console-dark", "console", "highcontrast"):
            return "Dark"
            
        # Failsafe
        return "Light"

    @staticmethod
    def _normalize_sound_effects_enabled(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"0", "false", "f", "no", "n", "off", "disabled"}:
                return False
            if normalized in {"1", "true", "t", "yes", "y", "on", "enabled"}:
                return True
        return True

    @staticmethod
    def _normalize_app_style(value: Any) -> str:
        return "Professional"

    def _prime_deferred_theme_preference(self) -> None:
        """
        Read the persisted theme before QML asks for app.theme, while keeping the
        broader settings load deferred until after startup motion settles.
        """
        theme_logger = logging.getLogger("theme.persistence")
        try:
            payload = self._collect_settings_payload(
                self._paths.user_settings_path(),
                self._legacy_settings_path,
                self._prefs_settings_path,
            )
        except Exception as exc:
            theme_logger.warning("deferred_theme_prime failed err=%s", str(exc))
            self._settings_data["theme"] = self._theme_name
            return

        runtime_settings_path = payload.get("runtime_settings_path")
        if isinstance(runtime_settings_path, Path):
            self._settings_path = runtime_settings_path

        selected_path = payload.get("selected_path")
        if isinstance(selected_path, Path):
            self._settings_path = selected_path

        loaded = payload.get("loaded")
        if isinstance(loaded, dict):
            self._settings_data.update(loaded)

        resolved = self._normalize_theme_name(self._settings_data.get("theme"))
        if resolved:
            self._theme_name = resolved
            
        self._app_style = self._normalize_app_style(self._settings_data.get("appStyle"))
            
        self._sound_effects_enabled = self._normalize_sound_effects_enabled(
            self._settings_data.get("soundEffectsEnabled")
        )
        if hasattr(self, '_paths') and self._paths is not None:
            self._paths.override_master_dir = Path(self._master_data_dir) if self._master_data_dir else None
            self._paths.override_data_dir = Path(self._local_data_dir) if self._local_data_dir else None

        self._master_data_dir = str(self._settings_data.get("masterDataDir", ""))
        self._local_data_dir = str(self._settings_data.get("localDataDir", ""))
        if "autoBackupMinutes" in self._settings_data:
            self.autoBackupMinutes = int(self._settings_data.get("autoBackupMinutes", 0))
        self._auto_backup_interval_mins = int(self._settings_data.get("autoBackupIntervalMins", 0))
        self._run_at_startup = bool(self._settings_data.get("runAtStartup", False))
        self._keep_tray_alive = bool(self._settings_data.get("keepTrayAlive", True))
        self._settings_data["theme"] = self._theme_name
        self._settings_data["appStyle"] = self._app_style
        self._settings_data["soundEffectsEnabled"] = self._sound_effects_enabled
        theme_logger.info(
            "deferred_theme_prime resolved theme=%s app_style=%s sound_effects=%s active_path=%s",
            self._theme_name,
            self._app_style,
            self._sound_effects_enabled,
            str(self._settings_path),
        )

    @Slot(result=str)
    def fetchProductivityDashboard(self) -> str:
        """Fetches the productivity dashboard JSON data from excel_repo."""
        try:
            data = self._excel_repo.get_productivity_dashboard_data()
            return json.dumps(data)
        except Exception as e:
            return json.dumps({"ok": False, "message": str(e)})

    @Slot("QVariantMap", result=dict)
    def getProductivityReport(self, payload) -> Dict[str, Any]:
        """Return the native, legacy-compatible Productivity Report payload."""
        try:
            request = payload.toVariant() if hasattr(payload, "toVariant") else payload
            request = dict(request or {})
            request.setdefault("annualBasisDays", self.productivityForecastBasisDays)
            return self._excel_repo.productivity_report(request)
        except Exception as exc:
            self._report_failure(
                "Failed to generate Productivity Report",
                context="app.report.productivity.failed",
                exc=exc,
            )
            return {"ok": False, "message": str(exc)}

    @Slot(result=dict)
    def getHomeDashboardSummary(self) -> Dict[str, Any]:
        """Provides summary metrics (active clients/matters, queue, etc.) for the dashboard."""
        # The launch shell can ask for this before the workbook repositories are
        # ready.  A cache keeps that first paint inexpensive, but it must never
        # win over live data once the backend boot is complete.
        if not self._is_booted:
            return self._load_home_dashboard_summary_cache()

        try:
            payload = self._excel_repo.home_dashboard_summary()
            if payload and payload.get("ok"):
                self._persist_home_dashboard_summary_cache(payload)
                self.homeDashboardSummaryUpdated.emit(payload)
                return payload
        except Exception as exc:
            self._report_failure("Failed to refresh dashboard summary", context="dashboard.summary", exc=exc, emit_signal=False)
        return self._load_home_dashboard_summary_cache()

    @Slot(result=dict)
    @Slot(int, result=dict)
    def getFinancialDashboardReport(self, year=None) -> Dict[str, Any]:
        """Return the CSPM-native financial dashboard report payload."""
        try:
            selected_year = int(year) if year not in (None, "") else None
            return self._excel_repo.financial_dashboard_report(selected_year)
        except Exception as exc:
            self._report_failure(
                "Failed to refresh financial dashboard",
                context="dashboard.financial",
                exc=exc,
                emit_signal=False,
            )
            return {
                "ok": False,
                "year": int(year) if str(year or "").isdigit() else datetime.now().year,
                "asOfDate": datetime.now().strftime("%Y-%m-%d"),
                "message": str(exc),
                "cards": [],
                "quarters": [],
                "arDetails": [],
                "topBillingClients": [],
                "topWorkClients": [],
                "notes": [],
            }

    @Slot(result=dict)
    @Slot("QVariantMap", result=dict)
    def getARAgingReport(self, filters=None) -> Dict[str, Any]:
        """Return the A/R Aging & Detail report payload."""
        try:
            payload = dict(filters or {}) if isinstance(filters, dict) else {}
            payload["excludedInvoices"] = self._settings_data.get("excludedARInvoices", [])
            return self._excel_repo.ar_aging_report(payload)
        except Exception as exc:
            self._report_failure(
                "Failed to refresh A/R aging report",
                context="reports.ar_aging",
                exc=exc,
                emit_signal=False,
            )
            return {
                "ok": False,
                "asOfDate": datetime.now().strftime("%Y-%m-%d"),
                "message": str(exc),
                "summary": {},
                "cards": [],
                "rows": [],
                "summaryRows": [],
                "bucketRows": [],
                "issueRows": [],
                "notes": [],
            }

    def _default_practice_briefing_filters(self) -> Dict[str, Any]:
        return {
            "upcomingDeadlineDays": 14,
            "includeOverdueDeadlinesInToday": True,
            "overdueBillGraceDays": 30,
            "readyToBillMode": "wip_and_ready",
            "readyToBillMinEntries": 1,
            "readyToBillMinAgeDays": 28,
            "considerBillingWipThreshold": 5000,
        }

    def _sanitize_practice_briefing_filters(self, payload: Any) -> Dict[str, Any]:
        base = self._default_practice_briefing_filters()
        if not isinstance(payload, dict):
            return base

        def _safe_int(key: str, minimum: int, maximum: int, default: int) -> int:
            try:
                value = int(payload.get(key, default) or default)
            except (TypeError, ValueError):
                value = default
            return max(minimum, min(maximum, value))

        mode = str(payload.get("readyToBillMode", base["readyToBillMode"]) or "").strip().lower()
        if mode not in {"wip_and_ready", "ready_only"}:
            mode = base["readyToBillMode"]

        min_age_days = _safe_int("readyToBillMinAgeDays", 0, 3650, base["readyToBillMinAgeDays"])
        min_age_days = _safe_int("considerBillingMinAgeDays", 0, 3650, min_age_days)
        wip_threshold = _safe_int("considerBillingWipThreshold", 0, 10000000, base["considerBillingWipThreshold"])

        sanitized = dict(base)
        sanitized["upcomingDeadlineDays"] = _safe_int("upcomingDeadlineDays", 1, 365, base["upcomingDeadlineDays"])
        sanitized["includeOverdueDeadlinesInToday"] = bool(
            payload.get("includeOverdueDeadlinesInToday", base["includeOverdueDeadlinesInToday"])
        )
        sanitized["overdueBillGraceDays"] = _safe_int("overdueBillGraceDays", 0, 365, base["overdueBillGraceDays"])
        sanitized["readyToBillMode"] = mode
        sanitized["readyToBillMinEntries"] = _safe_int("readyToBillMinEntries", 1, 9999, base["readyToBillMinEntries"])
        sanitized["readyToBillMinAgeDays"] = min_age_days
        sanitized["considerBillingMinAgeDays"] = min_age_days
        sanitized["considerBillingWipThreshold"] = wip_threshold
        return sanitized

    @Slot(result=dict)
    def getPracticeBriefingFilters(self) -> Dict[str, Any]:
        raw = self._settings_data.get(PRACTICE_BRIEFING_FILTERS_KEY, {})
        return self._sanitize_practice_briefing_filters(raw)

    @Slot("QVariantMap", result=bool)
    def savePracticeBriefingFilters(self, payload) -> bool:
        try:
            clean = self._sanitize_practice_briefing_filters(dict(payload or {}))
            self._settings_data[PRACTICE_BRIEFING_FILTERS_KEY] = clean
            self.save_settings()
            return True
        except Exception:
            return False

    def _default_main_window_layout(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "maximized": False,
            "widthPct": 0.0,
            "heightPct": 0.0,
            "centerXPct": 0.5,
            "centerYPct": 0.5,
        }

    def _sanitize_main_window_layout(self, payload: Any) -> Dict[str, Any]:
        base = self._default_main_window_layout()
        if not isinstance(payload, dict):
            return base

        def _safe_float(key: str, minimum: float, maximum: float, default: float) -> float:
            try:
                value = float(payload.get(key, default) or default)
            except (TypeError, ValueError):
                value = default
            if not math.isfinite(value):
                value = default
            return max(minimum, min(maximum, value))

        sanitized = dict(base)
        sanitized["ok"] = bool(payload.get("ok", True))
        sanitized["maximized"] = bool(payload.get("maximized", False))
        sanitized["widthPct"] = _safe_float("widthPct", 0.0, 1.0, 0.0)
        sanitized["heightPct"] = _safe_float("heightPct", 0.0, 1.0, 0.0)
        sanitized["centerXPct"] = _safe_float("centerXPct", 0.0, 1.0, 0.5)
        sanitized["centerYPct"] = _safe_float("centerYPct", 0.0, 1.0, 0.5)
        return sanitized

    @Slot(result=dict)
    def getMainWindowLayout(self) -> Dict[str, Any]:
        raw = self._settings_data.get(MAIN_WINDOW_LAYOUT_KEY, {})
        layout = self._sanitize_main_window_layout(raw)
        layout["ok"] = isinstance(raw, dict) and bool(raw)
        return layout

    @Slot("QVariantMap", result=bool)
    def saveMainWindowLayout(self, payload) -> bool:
        try:
            clean = self._sanitize_main_window_layout(dict(payload or {}))
            clean["ok"] = True
            self._settings_data[MAIN_WINDOW_LAYOUT_KEY] = clean
            self.save_settings()
            return True
        except Exception:
            return False

    def _safe_table_preferences_id(self, table_id: Any) -> str:
        raw = str(table_id or "").strip()
        safe = re.sub(r"[^A-Za-z0-9_.:-]+", "_", raw).strip("_")
        return safe[:100]

    def _sanitize_table_preferences_payload(self, payload: Any) -> Dict[str, Any]:
        source = dict(payload or {}) if isinstance(payload, dict) else {}
        sanitized: Dict[str, Any] = {
            "version": 1,
            "columns": [],
        }
        raw_columns = source.get("columns", [])
        if not isinstance(raw_columns, list):
            raw_columns = []
        seen_keys = set()
        for raw_column in raw_columns[:128]:
            if not isinstance(raw_column, dict):
                continue
            key = str(raw_column.get("key", "") or "").strip()
            if not key or not re.match(r"^[A-Za-z0-9_.:-]+$", key) or key in seen_keys:
                continue
            seen_keys.add(key)
            column: Dict[str, Any] = {"key": key}
            try:
                width = int(round(float(raw_column.get("width", 0))))
            except (TypeError, ValueError):
                width = 0
            if width > 0:
                column["width"] = max(24, min(4000, width))
            if "visible" in raw_column:
                column["visible"] = bool(raw_column.get("visible"))
            sanitized["columns"].append(column)
        saved_at = source.get("savedAt")
        if isinstance(saved_at, str) and saved_at.strip():
            sanitized["savedAt"] = saved_at.strip()[:40]
        sort_key = str(source.get("sortKey", "") or "").strip()
        if sort_key and re.match(r"^[A-Za-z0-9_.:-]+$", sort_key):
            sanitized["sortKey"] = sort_key[:100]
        if "sortAscending" in source:
            sanitized["sortAscending"] = bool(source.get("sortAscending"))
        return sanitized

    def _table_preferences_map(self) -> Dict[str, Any]:
        raw = self._settings_data.get(TABLE_PREFERENCES_KEY, {})
        if not isinstance(raw, dict):
            raw = {}
        self._settings_data[TABLE_PREFERENCES_KEY] = raw
        return raw

    @Slot(str, result=dict)
    def getTablePreferences(self, table_id: str) -> Dict[str, Any]:
        if not self._settings_load_complete:
            self.load_settings()
        safe_id = self._safe_table_preferences_id(table_id)
        if not safe_id:
            return {"ok": False, "tableId": "", "columns": [], "message": "Missing table id."}
        raw = self._table_preferences_map().get(safe_id, {})
        clean = self._sanitize_table_preferences_payload(raw)
        return {
            "ok": True,
            "tableId": safe_id,
            "version": clean.get("version", 1),
            "columns": clean.get("columns", []),
            "savedAt": clean.get("savedAt", ""),
            "sortKey": clean.get("sortKey", ""),
            "sortAscending": bool(clean.get("sortAscending", True)),
        }

    @Slot(str, "QVariantMap", result=bool)
    def saveTablePreferences(self, table_id: str, payload) -> bool:
        if not self._settings_load_complete:
            self.load_settings()
        safe_id = self._safe_table_preferences_id(table_id)
        if not safe_id:
            return False
        try:
            clean = self._sanitize_table_preferences_payload(dict(payload or {}))
            clean["savedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._table_preferences_map()[safe_id] = clean
            self.save_settings()
            self.settingsChanged.emit()
            return True
        except Exception as exc:
            self._report_failure(
                "Table preferences could not be saved.",
                context=f"settings.table_preferences.{safe_id}",
                exc=exc,
                emit_signal=False,
            )
            return False

    @Slot(result=dict)
    def getPracticeBriefing(self) -> Dict[str, Any]:
        """Daily operational briefing for the Practice Briefing home screen."""
        try:
            filters = self.getPracticeBriefingFilters()
            payload = self._excel_repo.practice_briefing(filters)
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            self._report_failure(
                "Failed to load practice briefing",
                context="home.practice_briefing",
                exc=exc,
                emit_signal=False,
            )
        return {
            "ok": False,
            "asOfDate": "",
            "todaysTasks": [],
            "upcomingDeadlines": [],
            "recentWork": [],
            "overdueDeadlines": [],
            "overdueBills": [],
            "readyToBillMatters": [],
            "arSummary": {
                "totalAr": 0.0,
                "openInvoiceCount": 0,
                "overdueAr": 0.0,
                "overdueInvoiceCount": 0,
                "overdueGraceDays": 30,
            },
            "summary": self._default_home_dashboard_summary(),
            "productivitySummary": {
                "today": {"hours": 0.0, "gross": 0.0},
                "wtd": {"hours": 0.0, "gross": 0.0},
                "last7": {"hours": 0.0, "gross": 0.0},
                "last90": {"hours": 0.0, "gross": 0.0},
                "ytd": {"hours": 0.0, "gross": 0.0},
            },
        }

    def _default_home_dashboard_summary(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "asOfDate": "",
            "deadlinesCount": 0,
            "unbilledDraftCount": 0,
            "clientMeetingCount": 0,
            "queueCount": 0,
            "activeClientCount": 0,
            "activeMatterCount": 0,
            "recentWorkHours": 0.0,
            "recentWorkCount": 0,
            "fromCache": False,
        }

    def _sanitize_home_dashboard_summary(self, payload: Any) -> Dict[str, Any]:
        base = self._default_home_dashboard_summary()
        if not isinstance(payload, dict):
            return base

        def _safe_int(key: str) -> int:
            try:
                return max(0, int(payload.get(key, 0) or 0))
            except (ValueError, TypeError):
                return 0

        sanitized = dict(base)
        as_of = payload.get("asOfDate", "")
        sanitized["asOfDate"] = str(as_of or "")
        sanitized["ok"] = bool(payload.get("ok", False))
        sanitized["deadlinesCount"] = _safe_int("deadlinesCount")
        sanitized["unbilledDraftCount"] = _safe_int("unbilledDraftCount")
        sanitized["clientMeetingCount"] = _safe_int("clientMeetingCount")
        sanitized["queueCount"] = _safe_int("queueCount")
        sanitized["activeClientCount"] = _safe_int("activeClientCount")
        sanitized["activeMatterCount"] = _safe_int("activeMatterCount")
        sanitized["fromCache"] = bool(payload.get("fromCache", False))
        return sanitized

    def _load_home_dashboard_summary_cache(self) -> Dict[str, Any]:
        try:
            state = self._load_runtime_state()
            raw = state.get(HOME_SUMMARY_CACHE_KEY)
            if isinstance(raw, dict):
                cached = self._sanitize_home_dashboard_summary(raw)
                cached["fromCache"] = True
                cached["ok"] = True
                return cached
        except Exception:
            pass
        return self._default_home_dashboard_summary()

    def _persist_home_dashboard_summary_cache(self, payload: Dict[str, Any]) -> None:
        try:
            next_summary = self._sanitize_home_dashboard_summary(payload)
            next_summary["fromCache"] = False
            next_summary["ok"] = True
            prev = self._sanitize_home_dashboard_summary(self._home_dashboard_summary_cache)
            changed = any(
                prev.get(k) != next_summary.get(k)
                for k in (
                    "asOfDate",
                    "deadlinesCount",
                    "unbilledDraftCount",
                    "clientMeetingCount",
                    "queueCount",
                    "activeClientCount",
                    "activeMatterCount",
                )
            )
            if not changed:
                self._home_dashboard_summary_cache = dict(next_summary)
                return
            self._home_dashboard_summary_cache = dict(next_summary)
            state = self._load_runtime_state()
            state[HOME_SUMMARY_CACHE_KEY] = dict(next_summary)
            state["homeDashboardSummaryCachedAtUtc"] = datetime.now(timezone.utc).isoformat()
            self._save_runtime_state(state)
        except Exception:
            pass

    # ── SECTION: System / Window Management ───────────────────────────────────

    @Slot(result=int)
    def getStartupLaunchScreenIndex(self):
        trace_start = time.perf_counter()
        selected_index = 0
        try:
            selected_index = int(self._startup_launch_context.get("screenIndex", 0))
            screens = QGuiApplication.screens()
            if screens:
                selected_index = max(0, min(selected_index, len(screens) - 1))
            else:
                selected_index = 0
            return selected_index
        except Exception:
            selected_index = 0
            return selected_index
        finally:
            self._trace_startup_backend_step(
                f"getStartupLaunchScreenIndex -> {selected_index}", trace_start
            )

    @Slot(result=dict)
    def getStartupLaunchCursorGlobalPos(self):
        trace_start = time.perf_counter()
        result = {
            "x": int(self._startup_launch_context.get("cursorX", 0)),
            "y": int(self._startup_launch_context.get("cursorY", 0)),
        }
        try:
            return result
        finally:
            self._trace_startup_backend_step(
                "getStartupLaunchCursorGlobalPos -> ("
                + str(result.get("x", 0))
                + ","
                + str(result.get("y", 0))
                + ")",
                trace_start,
            )

    @Slot(result=dict)
    def getStartupLaunchScreenGeometry(self):
        trace_start = time.perf_counter()
        result: Dict[str, Any] = {}
        try:
            result = self.getScreenGeometry(self.getStartupLaunchScreenIndex())
            return result
        except Exception:
            result = {}
            return result
        finally:
            if result:
                detail = (
                    str(result.get("w", 0))
                    + "x"
                    + str(result.get("h", 0))
                    + " @("
                    + str(result.get("x", 0))
                    + ","
                    + str(result.get("y", 0))
                    + ")"
                )
            else:
                detail = "{}"
            self._trace_startup_backend_step(
                "getStartupLaunchScreenGeometry -> " + detail,
                trace_start,
            )

    @Slot(result=int)
    def getCursorScreenIndex(self):
        trace_start = time.perf_counter()
        selected_index = 0
        try:
            cursor_pos = QCursor.pos()
            screens = QGuiApplication.screens()
            if not screens:
                selected_index = 0
                return selected_index

            cursor_screen = QGuiApplication.screenAt(cursor_pos)
            if cursor_screen is None:
                for screen in screens:
                    if screen.geometry().contains(cursor_pos):
                        cursor_screen = screen
                        break
            if cursor_screen is None:
                cursor_screen = screens[0]

            selected_index = 0
            for i, screen in enumerate(screens):
                if screen is cursor_screen or (
                    cursor_screen is not None
                    and screen.name() == cursor_screen.name()
                    and screen.geometry() == cursor_screen.geometry()
                ):
                    selected_index = i
        except Exception:
            selected_index = 0
        finally:
            self._trace_startup_backend_step(
                f"getCursorScreenIndex -> {selected_index}", trace_start
            )
        return selected_index

    @Slot(int, result=dict)
    def getScreenGeometry(self, index):
        trace_start = time.perf_counter()
        result: Dict[str, Any] = {}
        try:
            screens = QGuiApplication.screens()
            if not screens:
                result = {}
                return result
            if index < 0 or index >= len(screens):
                index = 0
            screen = screens[index]
            geom = screen.geometry()
            avail = screen.availableGeometry()
            dpr = float(screen.devicePixelRatio())
            logical_dpi_x = float(screen.logicalDotsPerInchX())
            logical_dpi_y = float(screen.logicalDotsPerInchY())

            left_inset = max(0, int(avail.x() - geom.x()))
            top_inset = max(0, int(avail.y() - geom.y()))
            right_inset = max(
                0, int((geom.x() + geom.width()) - (avail.x() + avail.width()))
            )
            bottom_inset = max(
                0, int((geom.y() + geom.height()) - (avail.y() + avail.height()))
            )

            taskbar_insets = {
                "left": left_inset,
                "top": top_inset,
                "right": right_inset,
                "bottom": bottom_inset,
            }
            taskbar_edge = "none"
            taskbar_size = 0
            for edge, size in taskbar_insets.items():
                if size > taskbar_size:
                    taskbar_edge = edge
                    taskbar_size = size

            scale_factor = (
                dpr if dpr > 0 else (logical_dpi_x / 96.0 if logical_dpi_x > 0 else 1.0)
            )
            scale_percent = int(round(scale_factor * 100.0))

            result = {
                "index": int(index),
                "name": screen.name() or "",
                "x": int(geom.x()),
                "y": int(geom.y()),
                "w": int(geom.width()),
                "h": int(geom.height()),
                "availX": int(avail.x()),
                "availY": int(avail.y()),
                "availW": int(avail.width()),
                "availH": int(avail.height()),
                "dpr": dpr,
                "logicalDpiX": logical_dpi_x,
                "logicalDpiY": logical_dpi_y,
                "scaleFactor": scale_factor,
                "scalePercent": scale_percent,
                "taskbarEdge": taskbar_edge,
                "taskbarSize": int(taskbar_size),
                "taskbarInsetLeft": left_inset,
                "taskbarInsetTop": top_inset,
                "taskbarInsetRight": right_inset,
                "taskbarInsetBottom": bottom_inset,
            }
            return result
        except Exception:
            result = {}
            return result
        finally:
            if result:
                self._trace_startup_backend_step(
                    (
                        "getScreenGeometry("
                        + str(index)
                        + ") -> "
                        + str(result.get("w", 0))
                        + "x"
                        + str(result.get("h", 0))
                        + " @("
                        + str(result.get("x", 0))
                        + ","
                        + str(result.get("y", 0))
                        + ")"
                    ),
                    trace_start,
                )
            else:
                self._trace_startup_backend_step(
                    "getScreenGeometry(" + str(index) + ") -> {}", trace_start
                )

    @Slot(result=dict)
    def getCursorGlobalPos(self):
        trace_start = time.perf_counter()
        result: Dict[str, int] = {}
        try:
            p = QCursor.pos()
            result = {"x": int(p.x()), "y": int(p.y())}
            return result
        except Exception:
            result = {}
            return result
        finally:
            if result:
                self._trace_startup_backend_step(
                    "getCursorGlobalPos -> ("
                    + str(result.get("x", 0))
                    + ","
                    + str(result.get("y", 0))
                    + ")",
                    trace_start,
                )
            else:
                self._trace_startup_backend_step("getCursorGlobalPos -> {}", trace_start)

    def _top_level_windows(self):
        try:
            return list(QGuiApplication.topLevelWindows())
        except Exception:
            return []

    def _find_main_shell_window(self):
        windows = self._top_level_windows()
        for window_obj in windows:
            if window_obj is None:
                continue
            try:
                name = str(window_obj.objectName() or "")
            except Exception:
                name = ""
            if name == "CSPMMainWindow":
                return window_obj
        return None

    def _force_window_foreground(self, target, trace_label: str):
        """Show and request activation without taking Windows foreground focus.

        CSPM may ask to be activated when launched or restored from the tray,
        but it must never change its topmost state or seize focus from another
        application.  Windows remains free to accept or decline this request.
        """
        trace_start = time.perf_counter()
        if target is None:
            self._trace_startup_backend_step(
                f"{trace_label} -> False (no target)", trace_start
            )
            return False

        focused = False
        try:
            show_normal = getattr(target, "showNormal", None)
            if callable(show_normal):
                show_normal()
                focused = True
        except Exception:
            pass
        try:
            show_fn = getattr(target, "show", None)
            if callable(show_fn):
                show_fn()
                focused = True
        except Exception:
            pass
        try:
            raise_fn = getattr(target, "raise_", None)
            if raise_fn is None:
                raise_fn = getattr(target, "raise", None)
            if callable(raise_fn):
                raise_fn()
                focused = True
        except Exception:
            pass
        try:
            activate_fn = getattr(target, "requestActivate", None)
            if activate_fn is None:
                activate_fn = getattr(target, "activateWindow", None)
            if callable(activate_fn):
                activate_fn()
                focused = True
        except Exception:
            pass

        self._trace_startup_backend_step(
            f"{trace_label} -> {focused}", trace_start
        )
        return focused

    @Slot(QObject, result=bool)
    def forceWindowForeground(self, target):
        return self._force_window_foreground(target, "forceWindowForeground")

    @Slot(result=bool)
    def forceMainWindowForeground(self):
        target = self._find_main_shell_window()
        return self._force_window_foreground(target, "forceMainWindowForeground")

    # ── SECTION: Themes / Settings ────────────────────────────────────────────



    @Property(QObject, constant=True)
    def docketing(self):
        return self._docketing_controller

    @Property(QObject, constant=True)
    def billing(self):
        return self._billing_controller

    @Property(QObject, constant=True)
    def apController(self):
        """QML-facing Accounts Payable controller (load/save bills, record payments)."""
        return self._ap_controller

    @Property(QObject, constant=True)
    def corporateController(self):
        """QML-facing Corporate controller (Entities, Relationships, Tapestry)."""
        return self._corporate_controller

    @Property(QObject, constant=True)
    def runtimeConfig(self):
        return self._runtime_config

    @Property(dict, notify=themeChanged)
    def theme(self):
        return self._themes_data.get(self._theme_name, self._themes_data.get("Dark", {}))

    @Property(list, constant=True)
    def themeNames(self):
        order = ["Light", "Dark"]
        return [name for name in order if name in self._themes_data]

    @Property(str, notify=appStyleChanged)
    def appStyle(self):
        return self._app_style

    @Property(str, notify=settingsChanged)
    def option3PinnedTabs(self) -> str:
        return str(self._settings_data.get("option3PinnedTabs", ""))

    @option3PinnedTabs.setter
    def option3PinnedTabs(self, val: str) -> None:
        self._settings_data["option3PinnedTabs"] = str(val)
        self.save_settings()
        self.settingsChanged.emit()

    @Property(str, notify=settingsChanged)
    def option3Favorites(self) -> str:
        return str(self._settings_data.get("option3Favorites", ""))

    @option3Favorites.setter
    def option3Favorites(self, val: str) -> None:
        self._settings_data["option3Favorites"] = str(val)
        self.save_settings()
        self.settingsChanged.emit()

    @staticmethod
    def _bounded_productivity_setting(
        value: Any,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        """Return an integer setting only when it is safe for annualization."""
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return default
        return normalized if minimum <= normalized <= maximum else default

    @staticmethod
    def _productivity_bool_setting(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "on"}:
                return True
            if text in {"false", "0", "no", "off"}:
                return False
        if value is None:
            return default
        return bool(value)

    def _productivity_forecast_settings_payload(self) -> Dict[str, Any]:
        """Build the complete, backwards-compatible productivity planning model.

        Vacation, holiday, and unavailable time are deliberately expressed as
        *scheduled workdays*.  A person's ordinary day off is therefore never
        deducted a second time from the annual planning basis.
        """
        work_days = self._bounded_productivity_setting(
            self._settings_data.get(
                PRODUCTIVITY_FORECAST_WORK_DAYS_KEY,
                DEFAULT_PRODUCTIVITY_FORECAST_WORK_DAYS,
            ),
            DEFAULT_PRODUCTIVITY_FORECAST_WORK_DAYS,
            1,
            7,
        )
        vacation_days = self._bounded_productivity_setting(
            self._settings_data.get(
                PRODUCTIVITY_FORECAST_VACATION_DAYS_KEY,
                DEFAULT_PRODUCTIVITY_FORECAST_VACATION_DAYS,
            ),
            DEFAULT_PRODUCTIVITY_FORECAST_VACATION_DAYS,
            0,
            MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS,
        )
        holiday_days = self._bounded_productivity_setting(
            self._settings_data.get(
                PRODUCTIVITY_FORECAST_HOLIDAY_DAYS_KEY,
                DEFAULT_PRODUCTIVITY_FORECAST_HOLIDAY_DAYS,
            ),
            DEFAULT_PRODUCTIVITY_FORECAST_HOLIDAY_DAYS,
            0,
            MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS,
        )
        other_unavailable_days = self._bounded_productivity_setting(
            self._settings_data.get(
                PRODUCTIVITY_FORECAST_OTHER_UNAVAILABLE_DAYS_KEY,
                DEFAULT_PRODUCTIVITY_FORECAST_OTHER_UNAVAILABLE_DAYS,
            ),
            DEFAULT_PRODUCTIVITY_FORECAST_OTHER_UNAVAILABLE_DAYS,
            0,
            MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS,
        )
        manual_basis_days = self._bounded_productivity_setting(
            self._settings_data.get(
                PRODUCTIVITY_FORECAST_MANUAL_BASIS_KEY,
                self._settings_data.get(
                    PRODUCTIVITY_FORECAST_BASIS_KEY,
                    DEFAULT_PRODUCTIVITY_FORECAST_BASIS_DAYS,
                ),
            ),
            DEFAULT_PRODUCTIVITY_FORECAST_BASIS_DAYS,
            MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS,
            MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS,
        )
        # Existing installations keep their established 336-day basis until a
        # user expressly elects to use the schedule calculation.
        manual_override_enabled = self._productivity_bool_setting(
            self._settings_data.get(PRODUCTIVITY_FORECAST_MANUAL_OVERRIDE_KEY),
            True,
        )
        calculated_basis_days = (
            PRODUCTIVITY_FORECAST_WEEKS_PER_YEAR * work_days
            - vacation_days
            - holiday_days
            - other_unavailable_days
        )
        effective_basis_days = manual_basis_days if manual_override_enabled else calculated_basis_days
        return {
            "weeksPerYear": PRODUCTIVITY_FORECAST_WEEKS_PER_YEAR,
            "workDaysPerWeek": work_days,
            "vacationDays": vacation_days,
            "holidayDays": holiday_days,
            "otherUnavailableDays": other_unavailable_days,
            "manualOverrideEnabled": manual_override_enabled,
            "manualBasisDays": manual_basis_days,
            "calculatedBasisDays": calculated_basis_days,
            "effectiveBasisDays": effective_basis_days,
        }

    @Property(int, notify=settingsChanged)
    def productivityForecastBasisDays(self) -> int:
        """The effective safe annual planning days used by the report/PDF."""
        settings = self._productivity_forecast_settings_payload()
        basis_days = int(settings["effectiveBasisDays"])
        if not (MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS <= basis_days <= MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS):
            return DEFAULT_PRODUCTIVITY_FORECAST_BASIS_DAYS
        return basis_days

    @Slot(result=dict)
    def getProductivityForecastSettings(self) -> Dict[str, Any]:
        """Return the full schedule and override inputs behind forecast basis."""
        if not self._settings_load_complete:
            self.load_settings()
        return {"ok": True, **self._productivity_forecast_settings_payload()}

    @Slot("QVariantMap", result=dict)
    def setProductivityForecastSettings(self, value: Any) -> Dict[str, Any]:
        """Persist schedule-based productivity planning assumptions safely."""
        try:
            payload = value.toVariant() if hasattr(value, "toVariant") else value
            payload = dict(payload or {})
        except (TypeError, ValueError):
            return {"ok": False, "message": "Productivity settings must be a valid settings record."}

        if not self._settings_load_complete:
            self.load_settings()
        current = self._productivity_forecast_settings_payload()

        def requested_int(key: str, default: int, minimum: int, maximum: int) -> int:
            raw = payload.get(key, default)
            try:
                candidate = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be a whole number.") from exc
            if not minimum <= candidate <= maximum:
                raise ValueError(f"{key} must be between {minimum} and {maximum}.")
            return candidate

        try:
            work_days = requested_int("workDaysPerWeek", current["workDaysPerWeek"], 1, 7)
            vacation_days = requested_int("vacationDays", current["vacationDays"], 0, MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS)
            holiday_days = requested_int("holidayDays", current["holidayDays"], 0, MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS)
            other_unavailable_days = requested_int(
                "otherUnavailableDays",
                current["otherUnavailableDays"],
                0,
                MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS,
            )
            manual_basis_days = requested_int(
                "manualBasisDays",
                current["manualBasisDays"],
                MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS,
                MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS,
            )
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}

        manual_override_enabled = self._productivity_bool_setting(
            payload.get("manualOverrideEnabled"),
            bool(current["manualOverrideEnabled"]),
        )
        calculated_basis_days = (
            PRODUCTIVITY_FORECAST_WEEKS_PER_YEAR * work_days
            - vacation_days
            - holiday_days
            - other_unavailable_days
        )
        if not (MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS <= calculated_basis_days <= MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS):
            return {
                "ok": False,
                "message": (
                    "The scheduled workdays calculation must produce between "
                    f"{MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS} and {MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS} days."
                ),
            }

        effective_basis_days = manual_basis_days if manual_override_enabled else calculated_basis_days
        self._settings_data.update({
            PRODUCTIVITY_FORECAST_WORK_DAYS_KEY: work_days,
            PRODUCTIVITY_FORECAST_VACATION_DAYS_KEY: vacation_days,
            PRODUCTIVITY_FORECAST_HOLIDAY_DAYS_KEY: holiday_days,
            PRODUCTIVITY_FORECAST_OTHER_UNAVAILABLE_DAYS_KEY: other_unavailable_days,
            PRODUCTIVITY_FORECAST_MANUAL_OVERRIDE_KEY: manual_override_enabled,
            PRODUCTIVITY_FORECAST_MANUAL_BASIS_KEY: manual_basis_days,
            # Retain the historic field as the current effective value for all
            # older callers while preserving the manual value independently.
            PRODUCTIVITY_FORECAST_BASIS_KEY: effective_basis_days,
        })
        try:
            self.save_settings()
            self.settingsChanged.emit()
            return {
                "ok": True,
                **self._productivity_forecast_settings_payload(),
                "message": f"Productivity forecast basis saved: {effective_basis_days} days.",
            }
        except Exception as exc:
            self._report_failure(
                "Productivity forecast settings could not be saved.",
                context="settings.productivity_forecast_basis",
                exc=exc,
                emit_signal=False,
            )
            return {"ok": False, "message": str(exc)}

    @Slot(int, result=dict)
    def setProductivityForecastBasisDays(self, value: int) -> Dict[str, Any]:
        """Compatibility API: explicitly set and enable a manual basis."""
        try:
            basis_days = int(value)
        except (TypeError, ValueError):
            return {"ok": False, "message": "Forecast basis must be a whole number of days."}
        if not (MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS <= basis_days <= MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS):
            return {
                "ok": False,
                "message": f"Forecast basis must be between {MIN_PRODUCTIVITY_FORECAST_BASIS_DAYS} and {MAX_PRODUCTIVITY_FORECAST_BASIS_DAYS} days.",
            }
        current = self._productivity_forecast_settings_payload()
        result = self.setProductivityForecastSettings({
            "workDaysPerWeek": current["workDaysPerWeek"],
            "vacationDays": current["vacationDays"],
            "holidayDays": current["holidayDays"],
            "otherUnavailableDays": current["otherUnavailableDays"],
            "manualOverrideEnabled": True,
            "manualBasisDays": basis_days,
        })
        if result.get("ok"):
            result["basisDays"] = basis_days
        return result

    @Property(list, constant=True)
    def appStyles(self):
        return list(VALID_APP_STYLES)

    @Property(bool, notify=soundEffectsChanged)
    def soundEffectsEnabled(self):
        return bool(self._sound_effects_enabled)

    @Property(bool, constant=True)
    def lowPerformanceMode(self):
        return self._low_performance_mode

    @Property(bool, constant=True)
    def autoBackupEnabled(self):
        return self._auto_backup_enabled

    @Property(int, notify=autoBackupMinutesChanged)
    def autoBackupMinutes(self):
        return self._auto_backup_minutes

    @autoBackupMinutes.setter
    def autoBackupMinutes(self, value):
        if self._auto_backup_minutes != value:
            self._auto_backup_minutes = value
            self._settings_data["autoBackupMinutes"] = value
            try:
                self.save_settings()
            except Exception:
                pass
            self.autoBackupMinutesChanged.emit()
            self._update_auto_backup_timer()
            
    def _update_auto_backup_timer(self):
        if hasattr(self, '_auto_backup_timer') and self._auto_backup_timer:
            self._auto_backup_timer.stop()
            if self._auto_backup_minutes > 0:
                self._auto_backup_timer.start(self._auto_backup_minutes * 60 * 1000)



    @Property(str, notify=masterDataDirChanged)
    def masterDataDir(self):
        return self._master_data_dir

    @masterDataDir.setter
    def masterDataDir(self, value):
        if self._master_data_dir != value:
            self._master_data_dir = value
            self._settings_data["masterDataDir"] = value
            if hasattr(self, "_paths") and self._paths is not None:
                self._paths.override_master_dir = Path(value) if value else None
            try:
                self.save_settings()
            except Exception:
                pass
            self.masterDataDirChanged.emit()

    @Property(str, notify=localDataDirChanged)
    def localDataDir(self):
        return self._local_data_dir

    @localDataDir.setter
    def localDataDir(self, value):
        if self._local_data_dir != value:
            self._local_data_dir = value
            self._settings_data["localDataDir"] = value
            if hasattr(self, "_paths") and self._paths is not None:
                self._paths.override_data_dir = Path(value) if value else None
            try:
                self.save_settings()
            except Exception:
                pass
            self.localDataDirChanged.emit()

    @Property(bool, notify=backendBootChanged)
    def backendBooted(self):
        return bool(self._is_booted)

    @Slot(str)
    def setTheme(self, name):
        if not self._settings_load_complete:
            self.load_settings()
        theme_logger = logging.getLogger("theme.persistence")
        normalized = self._normalize_theme_name(name) or str(name or "").strip()
        theme_logger.info(
            "setTheme request=%s normalized=%s current=%s settings_path=%s",
            str(name),
            normalized,
            self._theme_name,
            str(self._settings_path),
        )
        if normalized in self._themes_data:
            if normalized == self._theme_name and self._settings_data.get("theme") == self._theme_name:
                theme_logger.info("setTheme no-op unchanged=%s", self._theme_name)
                return
            self._theme_name = normalized
            self._settings_data["theme"] = self._theme_name
            self.save_settings()
            self.themeChanged.emit()
            theme_logger.info(
                "setTheme applied=%s settings_path=%s",
                self._theme_name,
                str(self._settings_path),
            )
        else:
            theme_logger.info(
                "setTheme ignored unknown name=%s available=%s",
                normalized,
                ",".join(sorted(self._themes_data.keys())),
            )

    @Slot(str)
    def setAppStyle(self, style):
        if not self._settings_load_complete:
            self.load_settings()
        next_style = self._normalize_app_style(style)
        if self._app_style != next_style:
            self._app_style = next_style
            self._settings_data["appStyle"] = self._app_style
            self.save_settings()
            self.appStyleChanged.emit()

    @Slot(bool, result=bool)
    def setSoundEffectsEnabled(self, enabled):
        if not self._settings_load_complete:
            self.load_settings()
        next_value = bool(enabled)
        if next_value == self._sound_effects_enabled and (
            self._settings_data.get("soundEffectsEnabled") is next_value
        ):
            return True
        self._sound_effects_enabled = next_value
        self._settings_data["soundEffectsEnabled"] = next_value
        try:
            self.save_settings()
            self.soundEffectsChanged.emit()
            return True
        except Exception as exc:
            self._report_failure(
                "Sound setting could not be saved.",
                context="settings.sound_effects",
                exc=exc,
                emit_signal=False,
            )
            return False

    @Slot(str, result=dict)
    def getThemeByName(self, name):
        if isinstance(name, str) and name in self._themes_data:
            return dict(self._themes_data[name])
        return {}

    @staticmethod
    def _settings_path_writable_static(path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        test_path = path
        cleanup_test_path = False
        if not path.exists():
            test_path = path.parent / f".{path.name}.writetest.{os.getpid()}"
            cleanup_test_path = True
        try:
            with open(test_path, "a", encoding="utf-8"):
                pass
            if cleanup_test_path and test_path.exists():
                try:
                    test_path.unlink()
                except OSError:
                    pass
            return True
        except OSError:
            return False

    def _settings_path_writable(self, path: Path) -> bool:
        return self._settings_path_writable_static(path)

    @staticmethod
    def _collect_settings_payload(
        runtime_settings_path: Path,
        legacy_settings_path: Path,
        prefs_settings_path: Path,
    ) -> Dict[str, Any]:
        theme_logger = logging.getLogger("theme.persistence")
        loaded: Dict[str, Any] = {}
        selected_path: Optional[Path] = None
        
        # 1. Try authoritative LocalAppData
        if runtime_settings_path.exists():
            try:
                with open(runtime_settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    loaded = dict(data)
                    selected_path = runtime_settings_path
                    theme_logger.info(
                        "load_settings selected authoritative path=%s theme=%s",
                        str(runtime_settings_path),
                        str(data.get("theme", "")),
                    )
                    return {
                        "loaded": loaded,
                        "selected_path": selected_path,
                        "runtime_settings_path": runtime_settings_path,
                    }
            except (OSError, json.JSONDecodeError):
                theme_logger.info("load_settings unreadable authoritative path=%s", str(runtime_settings_path))

        # 2. Migration fallback
        theme_logger.info("load_settings authoritative missing or invalid, checking legacy migration sources")
        legacy_candidates = [legacy_settings_path, prefs_settings_path]
        existing_legacy = [p for p in legacy_candidates if p.exists()]
        if existing_legacy:
            try:
                existing_legacy.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            except OSError:
                pass
                
            for candidate in existing_legacy:
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        loaded = dict(data)
                        
                        # Normalize for migration
                        loaded["appStyle"] = "Professional"
                        
                        # Normalize theme to Light or Dark
                        t = str(loaded.get("theme", "")).strip()
                        loaded["theme"] = t if t in ["Light", "Dark"] else "Light"
                        
                        theme_logger.info(
                            "load_settings migrating from legacy path=%s",
                            str(candidate)
                        )
                        
                        # Atomic write to authoritative path
                        success = _safe_atomic_json_write(runtime_settings_path, loaded)
                        if success:
                            selected_path = runtime_settings_path
                            theme_logger.info("load_settings successfully migrated to authoritative path=%s", str(runtime_settings_path))
                        else:
                            # Do not claim authoritative if migration fails
                            selected_path = candidate
                            theme_logger.error("load_settings migration save failed, falling back to read-only legacy path=%s", str(candidate))
                        break
                except (OSError, json.JSONDecodeError):
                    theme_logger.info("load_settings unreadable legacy path=%s", str(candidate))

        return {
            "loaded": loaded,
            "selected_path": selected_path,
            "runtime_settings_path": runtime_settings_path,
        }

    def _apply_settings_payload(self, payload: Dict[str, Any], *, emit_theme_signal: bool) -> None:
        theme_logger = logging.getLogger("theme.persistence")
        previous_theme = self._theme_name
        previous_app_style = self._app_style
        previous_sound_effects = self._sound_effects_enabled
        runtime_settings_path = payload.get("runtime_settings_path")
        if not isinstance(runtime_settings_path, Path):
            runtime_settings_path = self._paths.user_settings_path()
        selected_path = payload.get("selected_path")
        if not isinstance(selected_path, Path):
            selected_path = None
        loaded = payload.get("loaded")
        if not isinstance(loaded, dict):
            loaded = {}
        self._settings_path = runtime_settings_path
        self._settings_data = dict(loaded)
        resolved_theme = self._normalize_theme_name(self._settings_data.get("theme"))
        if resolved_theme:
            self._theme_name = resolved_theme
        self._app_style = self._normalize_app_style(self._settings_data.get("appStyle"))
        self._sound_effects_enabled = self._normalize_sound_effects_enabled(
            self._settings_data.get("soundEffectsEnabled")
        )
        if hasattr(self, '_paths') and self._paths is not None:
            self._paths.override_master_dir = Path(self._master_data_dir) if self._master_data_dir else None
            self._paths.override_data_dir = Path(self._local_data_dir) if self._local_data_dir else None

        self._master_data_dir = str(self._settings_data.get("masterDataDir", ""))
        self._local_data_dir = str(self._settings_data.get("localDataDir", ""))
        if "autoBackupMinutes" in self._settings_data:
            self.autoBackupMinutes = int(self._settings_data.get("autoBackupMinutes", 0))
        self._auto_backup_interval_mins = int(self._settings_data.get("autoBackupIntervalMins", 0))
        self._run_at_startup = bool(self._settings_data.get("runAtStartup", False))
        self._keep_tray_alive = bool(self._settings_data.get("keepTrayAlive", True))
        if selected_path is not None:
            self._settings_path = selected_path
        self._settings_data["theme"] = self._theme_name
        self._settings_data["appStyle"] = self._app_style
        self._settings_data["soundEffectsEnabled"] = self._sound_effects_enabled
        self._ensure_report_branding_settings()
        if emit_theme_signal and self._theme_name != previous_theme:
            self.themeChanged.emit()
        if emit_theme_signal and self._app_style != previous_app_style:
            self.appStyleChanged.emit()
        if self._sound_effects_enabled != previous_sound_effects:
            self.soundEffectsChanged.emit()
        theme_logger.info(
            "load_settings resolved theme=%s app_style=%s sound_effects=%s active_path=%s",
            self._theme_name,
            self._app_style,
            self._sound_effects_enabled,
            str(self._settings_path),
        )

    def _default_report_branding_profile(self) -> Dict[str, Any]:
        return {
            "id": DEFAULT_REPORT_BRANDING_PROFILE_ID,
            "profileId": DEFAULT_REPORT_BRANDING_PROFILE_ID,
            "name": "CS Law",
            "firmName": "Cory Schneider Law Office",
            "subtitle": "Cory Schneider Law Office Practice Management",
            "addressLines": ["14 Parsons Court", "Thornhill, ON L4K 6Z4"],
            "phone": "416-725-9364",
            "email": "cory@coryschneiderlaw.ca",
            "logoPath": str(self._paths.root / "assets" / "CS.svg"),
        }

    def _safe_profile_id(self, text: Any, fallback: str = "") -> str:
        raw = str(text or "").strip().lower()
        safe = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
        if safe:
            return safe[:80]
        return str(fallback or "").strip() or self._new_report_branding_profile_id()

    def _new_report_branding_profile_id(self) -> str:
        return f"profile_{uuid.uuid4().hex[:12]}"

    def _normalize_report_branding_profile(
        self,
        profile: Any,
        *,
        fallback_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        src = dict(profile or {}) if isinstance(profile, dict) else {}
        default = self._default_report_branding_profile()
        profile_id = self._safe_profile_id(
            src.get("id") or src.get("profileId") or fallback_id or "",
            fallback_id or self._new_report_branding_profile_id(),
        )
        
        name = src.get("name")
        if name is None:
            name = src.get("profileName")
        if name is None:
            name = "CS Law" if profile_id == DEFAULT_REPORT_BRANDING_PROFILE_ID else "Report Profile"
        else:
            name = str(name).strip()
            if not name:
                name = "CS Law" if profile_id == DEFAULT_REPORT_BRANDING_PROFILE_ID else "Report Profile"

        firm_name = src.get("firmName")
        if firm_name is None:
            firm_name = src.get("firm_name")
        if firm_name is None:
            firm_name = default["firmName"]
        else:
            firm_name = str(firm_name).strip()
            if not firm_name:
                firm_name = default["firmName"]

        subtitle = src.get("subtitle")
        if subtitle is None:
            subtitle = src.get("firmSubtitle")
        if subtitle is None:
            subtitle = default["subtitle"] if profile_id == DEFAULT_REPORT_BRANDING_PROFILE_ID else ""
        else:
            subtitle = str(subtitle).strip()

        address_value = src.get("addressLines")
        if address_value is None:
            address_value = src.get("address")
        
        if address_value is None:
            if profile_id == DEFAULT_REPORT_BRANDING_PROFILE_ID:
                address_lines = list(default["addressLines"])
            else:
                address_lines = []
        else:
            if isinstance(address_value, (list, tuple)):
                address_lines = [str(line or "").strip() for line in address_value]
            else:
                address_lines = [
                    line.strip()
                    for line in str(address_value or "").splitlines()
                ]

        phone = src.get("phone")
        if phone is None:
            phone = default["phone"] if profile_id == DEFAULT_REPORT_BRANDING_PROFILE_ID else ""
        else:
            phone = str(phone).strip()

        email = src.get("email")
        if email is None:
            email = default["email"] if profile_id == DEFAULT_REPORT_BRANDING_PROFILE_ID else ""
        else:
            email = str(email).strip()

        logo_path = src.get("logoPath")
        if logo_path is None:
            logo_path = src.get("logo")
        if logo_path is None:
            logo_path = default["logoPath"] if profile_id == DEFAULT_REPORT_BRANDING_PROFILE_ID else ""
        else:
            logo_path = str(logo_path).strip()

        return {
            "id": profile_id,
            "profileId": profile_id,
            "name": name,
            "firmName": firm_name,
            "subtitle": subtitle,
            "addressLines": address_lines,
            "phone": phone,
            "email": email,
            "logoPath": logo_path,
        }

    def _ensure_report_branding_settings(self) -> bool:
        changed = False
        raw_profiles = self._settings_data.get(REPORT_BRANDING_PROFILES_KEY)
        if not isinstance(raw_profiles, list) or not raw_profiles:
            profiles = [self._default_report_branding_profile()]
            changed = True
        else:
            profiles = []
            seen_ids = set()
            for index, raw_profile in enumerate(raw_profiles):
                profile = self._normalize_report_branding_profile(
                    raw_profile,
                    fallback_id=DEFAULT_REPORT_BRANDING_PROFILE_ID if index == 0 else None,
                )
                if profile["id"] in seen_ids:
                    profile["id"] = self._new_report_branding_profile_id()
                    profile["profileId"] = profile["id"]
                    changed = True
                seen_ids.add(profile["id"])
                profiles.append(profile)
            if profiles != raw_profiles:
                changed = True
        if not profiles:
            profiles = [self._default_report_branding_profile()]
            changed = True
        ids = {profile["id"] for profile in profiles}
        last_id = str(self._settings_data.get(LAST_REPORT_BRANDING_PROFILE_KEY) or "").strip()
        if last_id not in ids:
            last_id = profiles[0]["id"]
            changed = True
        self._settings_data[REPORT_BRANDING_PROFILES_KEY] = profiles
        self._settings_data[LAST_REPORT_BRANDING_PROFILE_KEY] = last_id
        return changed

    def _report_branding_profiles(self) -> list[Dict[str, Any]]:
        self._ensure_report_branding_settings()
        return [
            self._normalize_report_branding_profile(profile)
            for profile in self._settings_data.get(REPORT_BRANDING_PROFILES_KEY, [])
        ]

    def _report_branding_profile_by_id(self, profile_id: Any) -> Dict[str, Any]:
        target = str(profile_id or "").strip()
        profiles = self._report_branding_profiles()
        for profile in profiles:
            if profile["id"] == target or profile.get("profileId") == target:
                return profile
        last_id = str(self._settings_data.get(LAST_REPORT_BRANDING_PROFILE_KEY) or "").strip()
        for profile in profiles:
            if profile["id"] == last_id:
                return profile
        return profiles[0] if profiles else self._default_report_branding_profile()

    def _report_profile_contact_lines(self, profile: Dict[str, Any]) -> list[str]:
        lines = []
        subtitle = str(profile.get("subtitle") or "").strip()
        if subtitle:
            lines.append(subtitle)
        for line in profile.get("addressLines") or []:
            line_text = str(line or "").strip()
            if line_text:
                lines.append(line_text)
        
        phone = str(profile.get("phone") or "").strip()
        email = str(profile.get("email") or "").strip()
        if phone and email:
            lines.append(f"{phone}  |  {email}")
        elif phone:
            lines.append(phone)
        elif email:
            lines.append(email)
        return lines

    def _report_profile_firm_contact(self, profile: Dict[str, Any]) -> str:
        return "\n".join(self._report_profile_contact_lines(profile))

    def _path_to_file_url(self, path_text: Any) -> str:
        source = str(path_text or "").strip()
        if not source:
            return ""
        lowered = source.lower()
        if lowered.startswith(("file:", "qrc:", "http://", "https://", "../", "./")):
            return source
        candidate = Path(source)
        if not candidate.is_absolute():
            candidate = (self._paths.root / candidate).resolve()
        if candidate.exists():
            try:
                return candidate.as_uri()
            except ValueError:
                return ""
        return ""

    def _normalize_external_url(self, url: Any) -> str:
        raw = str(url or "").strip()
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered.startswith(("http://", "https://", "file:", "mailto:", "microsoft-edge:")):
            return raw
        return f"https://{raw}"

    @Slot(str, result=bool)
    def openUrlInEdge(self, url):
        target = self._normalize_external_url(url)
        if not target:
            return False
        try:
            if sys.platform.startswith("win") and hasattr(os, "startfile"):
                edge_target = target if target.lower().startswith("microsoft-edge:") else f"microsoft-edge:{target}"
                os.startfile(edge_target)  # type: ignore[attr-defined]
                return True
        except Exception as exc:
            self._report_failure("Could not open URL in Microsoft Edge", context="system.open_edge", exc=exc)
        try:
            return bool(QDesktopServices.openUrl(QUrl(target)))
        except Exception as exc:
            self._report_failure("Could not open URL", context="system.open_url", exc=exc)
            return False

    def _expert_preview_url(self) -> str:
        return "http://127.0.0.1:5174/"

    def _is_expert_preview_reachable(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", 5174), timeout=0.20):
                return True
        except OSError:
            return False

    def _start_expert_preview_server(self) -> bool:
        if self._is_expert_preview_reachable():
            return True
        if self._expert_preview_process is not None and self._expert_preview_process.poll() is None:
            return True

        client_dir = self._paths.root / "expert_client"
        package_json = client_dir / "package.json"
        if not package_json.exists():
            self._report_failure(
                "Expert preview is not installed yet.",
                context="expert.preview.missing_client",
                emit_signal=True,
            )
            return False

        npm_executable = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm_executable:
            self._report_failure(
                "Expert preview requires Node.js/npm.",
                context="expert.preview.missing_npm",
                emit_signal=True,
            )
            return False

        log_dir = self._paths.root / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            stdout_path = log_dir / "expert_preview.out.log"
            stderr_path = log_dir / "expert_preview.err.log"
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0
            with stdout_path.open("ab") as stdout_file, stderr_path.open("ab") as stderr_file:
                self._expert_preview_process = subprocess.Popen(
                    [
                        npm_executable,
                        "run",
                        "dev",
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "5174",
                    ],
                    cwd=str(client_dir),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    creationflags=creationflags,
                )
            return True
        except Exception as exc:
            self._report_failure(
                "Expert preview could not be started.",
                context="expert.preview.start",
                exc=exc,
                emit_signal=True,
            )
            return False

    @Slot(result=bool)
    def openExpertPreview(self):
        if not self._start_expert_preview_server():
            return False
        target = self._expert_preview_url()
        try:
            ok = bool(QDesktopServices.openUrl(QUrl(target)))
            if not ok:
                self._report_failure(
                    "Expert preview could not be opened.",
                    context="expert.preview.open",
                    emit_signal=True,
                )
            return ok
        except Exception as exc:
            self._report_failure(
                "Expert preview could not be opened.",
                context="expert.preview.open",
                exc=exc,
                emit_signal=True,
            )
            return False

    @Slot(result=bool)
    def openExpertFlutterPreview(self):
        launch_script = self._paths.root / "launch.ps1"
        if not launch_script.exists():
            self._report_failure(
                "Expert Flutter launcher is missing.",
                context="expert.flutter_preview.missing_launcher",
                emit_signal=True,
            )
            return False

        powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or shutil.which("pwsh")
        if not powershell:
            self._report_failure(
                "Expert Flutter preview requires PowerShell.",
                context="expert.flutter_preview.missing_powershell",
                emit_signal=True,
            )
            return False

        try:
            creationflags = 0
            if sys.platform.startswith("win"):
                creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(launch_script),
                    "-ExpertFlutter",
                ],
                cwd=str(self._paths.root),
                creationflags=creationflags,
            )
            return True
        except Exception as exc:
            self._report_failure(
                "Expert Flutter preview could not be started.",
                context="expert.flutter_preview.start",
                exc=exc,
                emit_signal=True,
            )
            return False

    def _public_report_branding_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_report_branding_profile(profile)
        logo_path = str(normalized.get("logoPath") or "").strip()
        public = dict(normalized)
        public["firmContact"] = self._report_profile_firm_contact(normalized)
        public["logoUrl"] = self._path_to_file_url(logo_path)
        public["logoSource"] = public["logoUrl"]
        return public

    def _report_branding_payload_for_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        public = self._public_report_branding_profile(profile)
        return {
            "id": public["id"],
            "profileId": public["id"],
            "name": public["name"],
            "firmName": public["firmName"],
            "subtitle": public["subtitle"],
            "addressLines": list(public.get("addressLines") or []),
            "phone": public.get("phone", ""),
            "email": public.get("email", ""),
            "firmContact": public.get("firmContact", ""),
            "logoPath": public.get("logoPath", ""),
            "logoUrl": public.get("logoUrl", ""),
            "logoSource": public.get("logoSource", ""),
        }

    def _coerce_file_path(self, file_path: Any) -> Path:
        raw = str(file_path or "").strip()
        if not raw:
            return Path()
        if raw.lower().startswith("file:"):
            parsed = urlparse(raw)
            raw = unquote(parsed.path or "")
            if re.match(r"^/[A-Za-z]:/", raw):
                raw = raw[1:]
        return Path(raw)

    @Slot(str, int, int, int, int)
    def saveReportWindowGeometry(self, reportId, x, y, width, height):
        try:
            self._ensure_report_branding_settings()
            geometries = self._settings_data.get("reportWindowGeometries", {})
            geometries[str(reportId)] = {
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height)
            }
            self._settings_data["reportWindowGeometries"] = geometries
            self.save_settings()
        except Exception:
            pass

    @Slot(str, result=dict)
    def getReportWindowGeometry(self, reportId):
        try:
            geometries = self._settings_data.get("reportWindowGeometries", {})
            return geometries.get(str(reportId)) or {}
        except Exception:
            return {}

    def _report_branding_logo_dir(self) -> Path:
        return self._paths.runtime_dir() / "report_branding" / "logos"

    def _report_branding_logo_cache_dir(self) -> Path:
        return self._paths.runtime_dir() / "report_branding" / "logo_cache"

    def _rasterize_svg_logo_for_pdf(self, profile_id: str, svg_path: Path) -> str:
        try:
            from PySide6.QtGui import QImage, QPainter
            from PySide6.QtSvg import QSvgRenderer

            if not svg_path.exists():
                return ""
            renderer = QSvgRenderer(str(svg_path))
            if not renderer.isValid():
                return ""
            default_size = renderer.defaultSize()
            source_w = default_size.width() if default_size.isValid() else 512
            source_h = default_size.height() if default_size.isValid() else 512
            scale = min(512.0 / max(1, source_w), 512.0 / max(1, source_h), 1.0)
            width = max(1, int(source_w * scale))
            height = max(1, int(source_h * scale))
            cache_dir = self._report_branding_logo_cache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)
            stamp = str(svg_path.stat().st_mtime_ns)
            cache_path = cache_dir / f"{self._safe_profile_id(profile_id)}_{stamp}_trimmed.png"
            if cache_path.exists():
                return str(cache_path)
            image_format = getattr(QImage, "Format_ARGB32_Premultiplied", QImage.Format.Format_ARGB32_Premultiplied)
            image = QImage(width, height, image_format)
            image.fill(0)
            painter = QPainter(image)
            try:
                renderer.render(painter)
            finally:
                painter.end()
            left, top = width, height
            right = bottom = -1
            for y in range(height):
                for x in range(width):
                    if image.pixelColor(x, y).alpha() > 0:
                        left = min(left, x)
                        top = min(top, y)
                        right = max(right, x)
                        bottom = max(bottom, y)
            if right >= left and bottom >= top:
                image = image.copy(QRect(left, top, right - left + 1, bottom - top + 1))
            if image.save(str(cache_path), "PNG"):  # type: ignore
                return str(cache_path)
        except Exception as exc:
            logging.getLogger("cspm.pdf").warning("Could not rasterize SVG logo for PDF: %s", exc)
        return ""

    def _logo_path_for_pdf(self, profile: Dict[str, Any]) -> str:
        """Resolve a printable report mark, always retaining the CSPM default.

        A branding profile may predate the report-logo setting or point to a
        file that was moved.  In either case, exports should remain branded
        rather than silently dropping the firm mark from the header.
        """
        candidates = []
        configured_logo = str(profile.get("logoPath") or "").strip()
        firm_report_logo = self._paths.root / "assets" / "CS.svg"
        legacy_report_logo = self._paths.root / "src" / "qml" / "assets" / "CS.svg"
        legacy_app_icon = self._paths.root / "src" / "assets" / "app_icon_preview.png"
        configured_path = self._coerce_file_path(configured_logo) if configured_logo else None
        default_logo_paths = {
            str(path.resolve()).casefold()
            for path in (firm_report_logo, legacy_report_logo, legacy_app_icon)
        }
        configured_key = str(configured_path.resolve()).casefold() if configured_path else ""
        # Existing default profiles may contain the former app icon or the
        # pre-report SVG location.  They all resolve to the firm's canonical
        # invoice/report mark.  A genuinely custom profile logo is untouched.
        if configured_key and configured_key in default_logo_paths:
            candidates.append((DEFAULT_REPORT_BRANDING_PROFILE_ID, str(firm_report_logo)))
        elif configured_logo:
            candidates.append((str(profile.get("id") or "profile"), configured_logo))
        candidates.append((DEFAULT_REPORT_BRANDING_PROFILE_ID, str(firm_report_logo)))
        candidates.append((DEFAULT_REPORT_BRANDING_PROFILE_ID, str(legacy_report_logo)))
        candidates.append((DEFAULT_REPORT_BRANDING_PROFILE_ID, str(legacy_app_icon)))

        for profile_id, logo_path in candidates:
            candidate = self._coerce_file_path(logo_path)
            if not candidate.exists():
                continue
            ext = candidate.suffix.lower()
            if ext in {".png", ".jpg", ".jpeg"}:
                return str(candidate)
            if ext == ".svg":
                rendered = self._rasterize_svg_logo_for_pdf(profile_id, candidate)
                if rendered:
                    return rendered
        return ""

    def _apply_report_branding_to_payload(self, payload: Any) -> tuple[Dict[str, Any], Dict[str, Any]]:
        if self._ensure_report_branding_settings():
            self.save_settings()
        payload_dict = dict(payload or {}) if isinstance(payload, dict) else {}
        config = dict(payload_dict.get("config", {}) or {})
        profile = None
        profile_payload = config.get("brandingProfile") or payload_dict.get("brandingProfile")
        if isinstance(profile_payload, dict):
            profile = self._normalize_report_branding_profile(profile_payload)
        profile_id = (
            config.get("brandingProfileId")
            or payload_dict.get("brandingProfileId")
            or (profile.get("id") if profile else "")
            or self._settings_data.get(LAST_REPORT_BRANDING_PROFILE_KEY)
        )
        if not profile or not profile.get("id"):
            profile = self._report_branding_profile_by_id(profile_id)
        else:
            stored_profile = self._report_branding_profile_by_id(profile.get("id"))
            if stored_profile.get("id") == profile.get("id"):
                profile = stored_profile
        branding = self._report_branding_payload_for_profile(profile)
        config["brandingProfileId"] = branding["id"]
        config["brandingProfile"] = branding
        config["firmName"] = branding["firmName"]
        config["firmContact"] = branding["firmContact"]
        config["firmSubtitle"] = branding["subtitle"]
        config["addressLines"] = list(branding.get("addressLines") or [])
        config["phone"] = branding.get("phone", "")
        config["email"] = branding.get("email", "")
        config["logoPath"] = branding.get("logoPath", "")
        payload_dict["config"] = config
        payload_dict["branding"] = branding
        payload_dict["brandingProfileId"] = branding["id"]
        return payload_dict, profile

    def _checkout_shared_data(self, phase: str) -> None:
        """Acquire the cloud writer checkout before enabling workbook writes."""
        try:
            result = self._sync_service.pull_from_master()
        except Exception as exc:
            logging.exception("Shared-data checkout crashed during %s", phase)
            self.toast.emit("Shared data opened read-only: cloud checkout failed.")
            return
        if result.get("ok"):
            logging.info("Shared-data checkout %s during %s: %s", result.get("status"), phase, result.get("message"))
            return
        message = str(result.get("message", "Cloud checkout was not acquired."))
        logging.error("Shared-data checkout blocked during %s: %s", phase, message)
        self.toast.emit(f"Shared data opened read-only: {message}")

    def load_settings(self, *, emit_theme_signal: bool = False):
        self._settings_load_started = True
        payload = self._collect_settings_payload(
            self._paths.user_settings_path(),
            self._legacy_settings_path,
            self._prefs_settings_path,
        )
        self._apply_settings_payload(payload, emit_theme_signal=emit_theme_signal)
        self._checkout_shared_data("startup settings load")
        self._settings_load_complete = True
        self._settings_load_started = False

    @Slot(str)
    def requestDeferredSettingsLoad(self, reason: str = "") -> None:
        reason_tag = str(reason or "unspecified")
        if self._settings_load_complete:
            self._trace_startup_backend_step(
                f"settings_load_deferred skipped complete reason={reason_tag}"
            )
            return
        if self._settings_load_started:
            self._trace_startup_backend_step(
                f"settings_load_deferred skipped inflight reason={reason_tag}"
            )
            return
        self._settings_load_started = True
        self._trace_startup_backend_step(
            f"settings_load_deferred queued reason={reason_tag}"
        )

        runtime_settings_path = self._paths.user_settings_path()
        legacy_settings_path = self._legacy_settings_path
        prefs_settings_path = self._prefs_settings_path

        def _do_load() -> Dict[str, Any]:
            return AppController._collect_settings_payload(
                runtime_settings_path,
                legacy_settings_path,
                prefs_settings_path,
            )

        def _on_loaded(payload: Dict[str, Any]) -> None:
            self._apply_settings_payload(payload, emit_theme_signal=True)
            self._checkout_shared_data("deferred settings load")
            self._settings_load_complete = True
            self._settings_load_started = False
            self._trace_startup_backend_step("settings_load_deferred complete")

        def _on_failed(err_tuple) -> None:
            self._settings_load_started = False
            _, exc, _ = err_tuple
            detail = exc if isinstance(exc, BaseException) else RuntimeError(str(exc))
            self._report_failure(
            "Settings could not be loaded.",
                context="settings.load.deferred",
                exc=detail,
                emit_signal=False,
            )
            self._trace_startup_backend_step("settings_load_deferred failed")

        self._start_background_worker(
            _do_load,
            name="settings_load_deferred",
            on_result=_on_loaded,
            on_error=_on_failed,
            priority=self._background_low_priority,
        )

    @Slot()
    def promptDataFolderSetup(self) -> None:
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                       QLabel, QPushButton, QFileDialog, 
                                       QMessageBox, QLineEdit, QGroupBox, QApplication)
        from PySide6.QtCore import Qt
        import os
        import sys
        import subprocess

        dialog = QDialog()
        dialog.setWindowTitle("Data Folder Setup Wizard")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout(dialog)
        
        # --- One-time seed source ---
        baseline_group = QGroupBox("1. One-time Seed Source (only if cloud is empty)")
        baseline_layout = QVBoxLayout()
        baseline_lbl = QLabel(
            "Optional. Used only to initialize an empty shared folder. It never replaces data already in the cloud."
        )
        baseline_lbl.setWordWrap(True)
        baseline_layout.addWidget(baseline_lbl)
        
        baseline_row = QHBoxLayout()
        baseline_edit = QLineEdit(self._local_data_dir)
        baseline_btn = QPushButton("Browse...")
        baseline_row.addWidget(baseline_edit)
        baseline_row.addWidget(baseline_btn)
        baseline_layout.addLayout(baseline_row)
        baseline_group.setLayout(baseline_layout)
        layout.addWidget(baseline_group)
        
        def pick_baseline():
            d = QFileDialog.getExistingDirectory(dialog, "Select Baseline Folder", baseline_edit.text(), QFileDialog.ShowDirsOnly)
            if d: baseline_edit.setText(os.path.normpath(d))
        baseline_btn.clicked.connect(pick_baseline)

        # --- Shared Data Source ---
        shared_group = QGroupBox("2. Shared Data Source (Cloud — Canonical)")
        shared_layout = QVBoxLayout()
        shared_lbl = QLabel("This is the single source of truth. Existing cloud data is never overwritten by setup.")
        shared_layout.addWidget(shared_lbl)
        
        shared_row = QHBoxLayout()
        shared_edit = QLineEdit(self._master_data_dir if self._master_data_dir else "")
        shared_btn = QPushButton("Browse...")
        shared_row.addWidget(shared_edit)
        shared_row.addWidget(shared_btn)
        shared_layout.addLayout(shared_row)
        shared_group.setLayout(shared_layout)
        layout.addWidget(shared_group)
        
        def pick_shared():
            d = QFileDialog.getExistingDirectory(dialog, "Select Shared Folder", shared_edit.text(), QFileDialog.ShowDirsOnly)
            if d: shared_edit.setText(os.path.normpath(d))
        shared_btn.clicked.connect(pick_shared)

        # --- Local Data Folder ---
        local_group = QGroupBox("3. Local Working Folder (Replica)")
        local_layout = QVBoxLayout()
        local_lbl = QLabel("This machine works from a checked-out replica. Existing differences are blocked as a conflict, never copied over automatically.")
        local_layout.addWidget(local_lbl)
        
        local_row = QHBoxLayout()
        local_edit = QLineEdit(self._local_data_dir)
        local_btn = QPushButton("Browse...")
        local_row.addWidget(local_edit)
        local_row.addWidget(local_btn)
        local_layout.addLayout(local_row)
        local_group.setLayout(local_layout)
        layout.addWidget(local_group)
        
        def pick_local():
            d = QFileDialog.getExistingDirectory(dialog, "Select Local Folder", local_edit.text(), QFileDialog.ShowDirsOnly)
            if d: local_edit.setText(os.path.normpath(d))
        local_btn.clicked.connect(pick_local)
        
        # --- Actions ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        apply_btn = QPushButton("Apply and Restart")
        apply_btn.setDefault(True)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)
        
        cancel_btn.clicked.connect(dialog.reject)
        
        def on_apply():
            b_dir = baseline_edit.text().strip()
            s_dir = shared_edit.text().strip()
            l_dir = local_edit.text().strip()
            
            if not s_dir or not l_dir:
                QMessageBox.warning(dialog, "Validation Error", "Shared Cloud and Local Working folders must be specified.")
                return

            configured_paths = AppPaths(
                root=self._paths.root,
                override_data_dir=Path(l_dir),
                override_master_dir=Path(s_dir),
            )
            configured_sync = SyncService(configured_paths)
            seed_dir = Path(b_dir) if b_dir else None
            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
                sync_result = configured_sync.initialize_shared_source(seed_dir)
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(dialog, "Setup Failed", f"Could not validate the data package:\n{e}")
                return
            QApplication.restoreOverrideCursor()
            if not sync_result.get("ok"):
                QMessageBox.critical(
                    dialog,
                    "Data Synchronization Not Applied",
                    f"{sync_result.get('message', 'Cloud setup was blocked.')}\n\n"
                    "No cloud or local workbook was overwritten.",
                )
                return

            msg = (
                "Cloud-canonical setup completed safely.\n\n"
                f"Shared Source: {s_dir}\n"
                f"Local Working: {l_dir}\n\n"
                "CSPM will now restart and check out the shared package before allowing edits."
            )
            QMessageBox.information(dialog, "Setup Complete", msg)
            
            # Save settings
            self._master_data_dir = s_dir
            self._local_data_dir = l_dir
            self._settings_data["masterDataDir"] = s_dir
            self._settings_data["localDataDir"] = l_dir
            self.save_settings()
            
            try:
                _schedule_application_restart()
            except Exception as exc:
                QMessageBox.critical(
                    dialog,
                    "Restart Could Not Be Scheduled",
                    f"Your folder settings were saved, but CSPM could not restart automatically:\n{exc}",
                )
                return

            dialog.accept()
            from PySide6.QtCore import QCoreApplication
            QTimer.singleShot(0, QCoreApplication.instance().quit)

        apply_btn.clicked.connect(on_apply)
        
        dialog.exec_()

    @Property(bool, notify=runAtStartupChanged)
    def runAtStartup(self) -> bool:
        return self._run_at_startup

    @runAtStartup.setter
    def runAtStartup(self, value: bool) -> None:
        if self._run_at_startup != value:
            self._run_at_startup = value
            self.runAtStartupChanged.emit()
            self._apply_run_at_startup()
            self.save_settings()

    def _apply_run_at_startup(self) -> None:
        import winreg
        import sys
        import os
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if self._run_at_startup:
                import subprocess
                # Use python executable if running from source, otherwise sys.argv[0] if compiled
                if sys.argv[0].endswith(".py"):
                    exe = sys.executable
                    script = os.path.abspath(sys.argv[0])
                    cmd = f'"{exe}" "{script}" --tray-only'
                else:
                    exe = os.path.abspath(sys.argv[0])
                    cmd = f'"{exe}" --tray-only'
                winreg.SetValueEx(key, "CSPM", 0, winreg.REG_SZ, cmd)
                logging.info(f"Added CSPM to startup with command: {cmd}")
            else:
                try:
                    winreg.DeleteValue(key, "CSPM")
                    logging.info("Removed CSPM from startup.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logging.error(f"Failed to set run at startup: {e}")


    @Property(bool, notify=keepTrayAliveChanged)
    def keepTrayAlive(self) -> bool:
        return self._keep_tray_alive

    @keepTrayAlive.setter
    def keepTrayAlive(self, value: bool) -> None:
        if self._keep_tray_alive != value:
            self._keep_tray_alive = value
            self.keepTrayAliveChanged.emit()
            self.save_settings()

    def shutdown(self):
        if self._shutdown_sync_complete:
            return
        self._shutdown_sync_complete = True
        try:
            if hasattr(self, "_sync_service"):
                result = self._sync_service.push_to_master()
                if result.get("ok"):
                    logging.info("Shared-data publish on shutdown: %s", result.get("message"))
                else:
                    logging.error("Shared-data publish was not completed: %s", result.get("message"))
        except Exception as e:
            logging.error(f"Error during shutdown sync push: {e}")

    def save_settings(self):
        theme_logger = logging.getLogger("theme.persistence")
        self._ensure_report_branding_settings()
        payload = dict(self._settings_data or {})
        payload["theme"] = self._theme_name
        payload["appStyle"] = self._app_style
        payload["soundEffectsEnabled"] = bool(self._sound_effects_enabled)
        payload["masterDataDir"] = self._master_data_dir
        payload["localDataDir"] = self._local_data_dir
        payload["autoBackupMinutes"] = self._auto_backup_minutes
        payload["autoBackupIntervalMins"] = self._auto_backup_interval_mins
        payload["runAtStartup"] = self._run_at_startup
        payload["keepTrayAlive"] = self._keep_tray_alive
        
        target_path = self._paths.user_settings_path()
        self._settings_path = target_path
        
        success = _safe_atomic_json_write(target_path, payload)
        if success:
            theme_logger.info(
                "save_settings atomically wrote path=%s theme=%s appStyle=%s",
                str(target_path),
                self._theme_name,
                self._app_style,
            )
        else:
            theme_logger.warning("save_settings failed to atomically write to path=%s", str(target_path))
        return



    @Slot(result=dict)
    def getReportBrandingProfiles(self):
        try:
            if not self._settings_load_complete:
                self.load_settings()
            changed = self._ensure_report_branding_settings()
            if changed:
                self.save_settings()
            profiles = [self._public_report_branding_profile(profile) for profile in self._report_branding_profiles()]
            return {
                "ok": True,
                "profiles": profiles,
                "lastProfileId": self._settings_data.get(LAST_REPORT_BRANDING_PROFILE_KEY, DEFAULT_REPORT_BRANDING_PROFILE_ID),
            }
        except Exception as exc:
            self._report_failure("Could not load report branding profiles", context="settings.report_branding.list", exc=exc)
            default_profile = self._public_report_branding_profile(self._default_report_branding_profile())
            return {
                "ok": False,
                "profiles": [default_profile],
                "lastProfileId": DEFAULT_REPORT_BRANDING_PROFILE_ID,
                "message": str(exc),
            }

    @Slot("QVariantMap", result=dict)
    def saveReportBrandingProfile(self, profile):
        try:
            if not self._settings_load_complete:
                self.load_settings()
            self._ensure_report_branding_settings()
            incoming = dict(profile or {}) if isinstance(profile, dict) else {}
            profile_id = incoming.get("id") or incoming.get("profileId") or self._new_report_branding_profile_id()
            saved_profile = self._normalize_report_branding_profile(incoming, fallback_id=str(profile_id))
            profiles = self._report_branding_profiles()
            replaced = False
            for index, existing in enumerate(profiles):
                if existing["id"] == saved_profile["id"]:
                    profiles[index] = saved_profile
                    replaced = True
                    break
            if not replaced:
                profiles.append(saved_profile)
            self._settings_data[REPORT_BRANDING_PROFILES_KEY] = profiles
            self._settings_data[LAST_REPORT_BRANDING_PROFILE_KEY] = saved_profile["id"]
            self.save_settings()
            return {
                "ok": True,
                "profile": self._public_report_branding_profile(saved_profile),
                "profiles": [self._public_report_branding_profile(item) for item in profiles],
                "lastProfileId": saved_profile["id"],
            }
        except Exception as exc:
            self._report_failure("Could not save report branding profile", context="settings.report_branding.save", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot(str, result=dict)
    def deleteReportBrandingProfile(self, profileId):
        try:
            if not self._settings_load_complete:
                self.load_settings()
            self._ensure_report_branding_settings()
            profiles = self._report_branding_profiles()
            if len(profiles) <= 1:
                return {
                    "ok": False,
                    "message": "At least one report branding profile is required.",
                    "profiles": [self._public_report_branding_profile(item) for item in profiles],
                    "lastProfileId": profiles[0]["id"] if profiles else DEFAULT_REPORT_BRANDING_PROFILE_ID,
                }
            target = str(profileId or "").strip()
            next_profiles = [profile for profile in profiles if profile["id"] != target]
            if len(next_profiles) == len(profiles):
                return {
                    "ok": False,
                    "message": "Report branding profile was not found.",
                    "profiles": [self._public_report_branding_profile(item) for item in profiles],
                    "lastProfileId": self._settings_data.get(LAST_REPORT_BRANDING_PROFILE_KEY, DEFAULT_REPORT_BRANDING_PROFILE_ID),
                }
            last_id = str(self._settings_data.get(LAST_REPORT_BRANDING_PROFILE_KEY) or "")
            if last_id == target or last_id not in {profile["id"] for profile in next_profiles}:
                last_id = next_profiles[0]["id"]
            self._settings_data[REPORT_BRANDING_PROFILES_KEY] = next_profiles
            self._settings_data[LAST_REPORT_BRANDING_PROFILE_KEY] = last_id
            self.save_settings()
            return {
                "ok": True,
                "profiles": [self._public_report_branding_profile(item) for item in next_profiles],
                "lastProfileId": last_id,
            }
        except Exception as exc:
            self._report_failure("Could not delete report branding profile", context="settings.report_branding.delete", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot(str, result=dict)
    def setLastReportBrandingProfile(self, profileId):
        try:
            if not self._settings_load_complete:
                self.load_settings()
            self._ensure_report_branding_settings()
            target = str(profileId or "").strip()
            profiles = self._report_branding_profiles()
            if target not in {profile["id"] for profile in profiles}:
                return {
                    "ok": False,
                    "message": "Report branding profile was not found.",
                    "profiles": [self._public_report_branding_profile(item) for item in profiles],
                    "lastProfileId": self._settings_data.get(LAST_REPORT_BRANDING_PROFILE_KEY, DEFAULT_REPORT_BRANDING_PROFILE_ID),
                }
            self._settings_data[LAST_REPORT_BRANDING_PROFILE_KEY] = target
            self.save_settings()
            return {
                "ok": True,
                "profile": self._public_report_branding_profile(self._report_branding_profile_by_id(target)),
                "profiles": [self._public_report_branding_profile(item) for item in profiles],
                "lastProfileId": target,
            }
        except Exception as exc:
            self._report_failure("Could not remember report branding profile", context="settings.report_branding.last", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot(str, str, result=dict)
    def importReportBrandingLogo(self, profileId, filePath):
        try:
            if not self._settings_load_complete:
                self.load_settings()
            self._ensure_report_branding_settings()
            target = str(profileId or "").strip()
            profiles = self._report_branding_profiles()
            profile = None
            for item in profiles:
                if item["id"] == target:
                    profile = item
                    break
            if profile is None:
                return {"ok": False, "message": "Save the report branding profile before importing a logo."}
            source_path = self._coerce_file_path(filePath)
            if not source_path.exists() or not source_path.is_file():
                return {"ok": False, "message": "Logo file was not found."}
            ext = source_path.suffix.lower()
            if ext not in REPORT_BRANDING_LOGO_EXTENSIONS:
                return {"ok": False, "message": "Logo must be an SVG, PNG, JPG, or JPEG file."}
            logo_dir = self._report_branding_logo_dir()
            logo_dir.mkdir(parents=True, exist_ok=True)
            destination = logo_dir / f"{self._safe_profile_id(profile['id'])}_{int(time.time() * 1000)}{ext}"
            shutil.copy2(source_path, destination)
            profile["logoPath"] = str(destination)
            next_profiles = [profile if item["id"] == profile["id"] else item for item in profiles]
            self._settings_data[REPORT_BRANDING_PROFILES_KEY] = next_profiles
            self._settings_data[LAST_REPORT_BRANDING_PROFILE_KEY] = profile["id"]
            self.save_settings()
            return {
                "ok": True,
                "profile": self._public_report_branding_profile(profile),
                "profiles": [self._public_report_branding_profile(item) for item in next_profiles],
                "lastProfileId": profile["id"],
            }
        except Exception as exc:
            self._report_failure("Could not import report branding logo", context="settings.report_branding.logo", exc=exc)
            return {"ok": False, "message": str(exc)}

    def _sanitize_deadline_calendar_filters(self, payload: Any) -> Dict[str, Any]:
        src = dict(payload or {}) if isinstance(payload, dict) else {}
        out = {
            "matter": str(src.get("matter", "All") or "All").strip() or "All",
            "client": str(src.get("client", "All") or "All").strip() or "All",
            "showOpen": bool(src.get("showOpen", True)),
            "showCompleted": bool(src.get("showCompleted", True)),
            "showInformationOnly": bool(src.get("showInformationOnly", True)),
            "actionableOnly": bool(src.get("actionableOnly", False)),
        }
        if out["actionableOnly"]:
            out["showInformationOnly"] = False
        if not out["showOpen"] and not out["showCompleted"] and not out["showInformationOnly"]:
            if out["actionableOnly"]:
                out["showOpen"] = True
            else:
                out["showInformationOnly"] = True
        return out

    @Slot(result=dict)
    def getDeadlineCalendarFilters(self):
        raw = self._settings_data.get("deadlineCalendarFilters", {})
        return self._sanitize_deadline_calendar_filters(raw)

    @Slot("QVariantMap", result=bool)
    def saveDeadlineCalendarFilters(self, payload):
        try:
            clean = self._sanitize_deadline_calendar_filters(dict(payload or {}))
            self._settings_data["deadlineCalendarFilters"] = clean
            self.save_settings()
            return True
        except Exception:
            return False

    @Slot(result=list)
    def listFirmLawyers(self):
        try:
            if not self._settings_load_complete:
                self.load_settings()
            lawyers = self._settings_data.get("firmLawyers", [])
            if not isinstance(lawyers, list):
                lawyers = []
            # Ensure unique, non-empty strings, alphabetically sorted
            clean = sorted(list({str(L).strip() for L in lawyers if str(L).strip()}))
            return clean
        except Exception as exc:
            self._report_failure("Could not list firm lawyers", context="settings.firm_lawyers.list", exc=exc)
            return []

    @Slot("QVariantList", result=dict)
    def saveFirmLawyers(self, payload):
        try:
            if not self._settings_load_complete:
                self.load_settings()
            raw_list = list(payload or [])
            clean = sorted(list({str(L).strip() for L in raw_list if str(L).strip()}))
            self._settings_data["firmLawyers"] = clean
            self.save_settings()
            return {"ok": True, "lawyers": clean}
        except Exception as exc:
            self._report_failure("Could not save firm lawyers", context="settings.firm_lawyers.save", exc=exc)
            return {"ok": False, "message": str(exc), "lawyers": []}

    # ── SECTION: Snapshot / Backup ────────────────────────────────────────────

    @Slot(str, result=bool)
    def createProjectSnapshot(self, reason):
        return self._create_project_snapshot(reason or "manual", emit_toast=True)

    @Slot(int, result=list)
    def listProjectSnapshots(self, limit):
        try:
            return self._snapshot_service.list_snapshots(limit=max(1, int(limit or 1)))
        except Exception as exc:
            self._report_failure("Could not list snapshots", context="snapshot.list", exc=exc)
            return []

    @Slot(str, result=bool)
    def restoreProjectSnapshot(self, snapshot_id):
        try:
            ok = self._snapshot_service.restore_snapshot(snapshot_id)
            if ok:
                self.toast.emit(f"Project snapshot restored: {snapshot_id}")
                return True
            self.error.emit(f"Snapshot not found: {snapshot_id}")
            return False
        except Exception as exc:
            self._report_failure("Snapshot restore failed", context="snapshot.restore", exc=exc)
            return False

    # ── SECTION: Client & Matter ──────────────────────────────────────────────

    @Slot(result=list)
    def listClientNames(self):
        return self._crud.list_client_names()

    @Slot(result=list)
    def listActiveClientNames(self):
        return self._crud.list_active_client_names()

    @Slot(result=list)
    def listClientDirectory(self):
        return self._crud.list_client_directory()

    @Slot(str, result=dict)
    def getClientProfile(self, client_key):
        return self._crud.get_client_profile(client_key)

    @Slot(str, str, result=dict)
    def searchGlobalEntities(self, query, mode):
        return self._crud.search_global_entities(query, mode)

    @Slot(str, result=dict)
    def getReceivable(self, invoice_num):
        return self._crud.get_receivable(invoice_num)

    @Slot(str, dict, result=dict)
    def updateReceivable(self, invoice_num, changes):
        return self._crud.update_receivable(invoice_num, changes)


    # ── SECTION: Deadlines ────────────────────────────────────────────────────

    # --- deadline API for NP-10 -------------------------------------------------
    @Slot(result=list)
    def listDeadlines(self):
        return self._crud.list_deadlines()

    @Slot(dict, result=dict)
    def createDeadline(self, payload):
        return self._crud.create_deadline(payload)

    @Slot(str, dict, result=dict)
    def updateDeadline(self, entry_id, changes):
        return self._crud.update_deadline(entry_id, changes)

    @Slot(str, result=bool)
    def deleteDeadline(self, entry_id):
        return self._crud.delete_deadline(entry_id)

    # ---------------------------------------------------------------------------

    @Slot(result=list)
    def listMatterNames(self):
        return self._crud.list_matter_names()

    @Slot(result=list)
    def listMatterDirectory(self):
        return self._crud.list_matter_directory()

    @Slot(str, result=dict)
    def getMatterProfile(self, matter_key):
        return self._crud.get_matter_profile(matter_key)

    @Slot(str, str, str, str, result=str)
    def previewMatterNumber(self, client_name, matter_type, date_opened, existing_matter_id):
        return self._crud.preview_matter_number(client_name, matter_type, date_opened, existing_matter_id)

    @Slot(result=list)
    def listParentNames(self):
        return self._crud.list_parent_names()

    @Slot(result=list)
    def listActiveMatterNames(self):
        return self._crud.list_active_matter_names()

    @Slot(result=list)
    def listActiveMatterDirectory(self):
        return self._crud.list_active_matter_directory()

    @Slot(str, result=list)
    def listTrademarkDirectory(self, query):
        return self._crud.list_trademark_directory(query)

    # ── SECTION: Transactions ─────────────────────────────────────────────────

    @Slot(result=list)
    def listTransactionAccounts(self):
        return self._crud.list_transaction_accounts()

    @Slot(bool, result=list)
    def listTransactionAccountsAll(self, include_inactive):
        return self._crud.list_transaction_accounts_all(include_inactive)

    @Slot(str, str, bool, result=list)
    def listTransactionCategories(self, txn_type, txn_class, include_inactive):
        return self._crud.list_transaction_categories(txn_type, txn_class, include_inactive)

    @Slot(result=list)
    def listTransactionBusinessUnits(self):
        return self._crud.list_transaction_business_units()

    @Slot(bool, result=list)
    def listTransactionBusinessUnitsAll(self, include_inactive):
        return self._crud.list_transaction_business_units_all(include_inactive)

    @Slot(result=list)
    def listTransactionPayees(self):
        return self._crud.list_transaction_payees()

    @Slot(bool, result=list)
    def listTransactionPayeesAll(self, include_inactive):
        return self._crud.list_transaction_payees_all(include_inactive)

    @Slot("QVariantMap", result=list)
    def listTransactions(self, filters):
        return self._crud.list_transactions(dict(filters or {}))

    @Slot(result=list)
    def listAllTransactions(self):
        return self._crud.list_all_transactions()

    @Slot("QVariantMap", result=list)
    def listOpenPaymentInvoices(self, filters):
        try:
            return self._excel_repo.list_open_payment_invoices(dict(filters or {}))
        except Exception as exc:
            self._report_failure("Could not list open invoices", context="repo.payment.invoices", exc=exc)
            return []

    @Slot(str, result=list)
    def listInvoicePaymentHistory(self, invoice_ref):
        try:
            return self._excel_repo.list_invoice_payment_history(str(invoice_ref or ""))
        except Exception as exc:
            self._report_failure("Could not list invoice payment history", context="repo.payment.history", exc=exc)
            return []

    @Slot("QVariantMap", result=dict)
    def saveTransaction(self, payload):
        try:
            result = dict(self._excel_repo.save_transaction(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Transaction saved: {result.get('transactionId', '')}")
                self.transactionDataChanged.emit()
            else:
                message = str(result.get("message", "Transaction verification failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save transaction", context="repo.txn.save", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def saveClientProfile(self, payload):
        try:
            result = dict(self._excel_repo.save_client_profile(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Client saved: {result.get('clientId', '')}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Client profile validation failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save client profile", context="repo.client.save_profile", exc=exc)
            return {"ok": False, "clientId": "", "message": str(exc)}

    @Slot(str, result=dict)
    def deleteMatterProfile(self, matter_id: str):
        try:
            result = dict(self._excel_repo.delete_matter_profile(matter_id) or {})
            if result.get("ok"):
                self.toast.emit("Matter deleted permanently")
                self.clientDataChanged.emit()
            return result
        except Exception as exc:
            self._report_failure("Could not delete matter", context="matter.delete", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot(str, result=dict)
    def deleteArchivedMatterProfile(self, matter_id: str):
        try:
            result = dict(self._excel_repo.delete_archived_matter_profile(matter_id) or {})
            if result.get("ok"):
                self.toast.emit("Archived matter permanently deleted")
                self.clientDataChanged.emit()
            return result
        except Exception as exc:
            self._report_failure("Could not delete archived matter", context="matter.archive.delete", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot(str, result=dict)
    def checkMatterDependencies(self, matter_id: str):
        try:
            return dict(self._excel_repo.check_matter_dependencies(matter_id) or {})
        except Exception as exc:
            self._report_failure("Could not check matter dependencies", context="matter.dependencies", exc=exc)
            return {"ok": False, "message": str(exc), "canDelete": False}

    @Slot(str, result=dict)
    def getMatterFinancialSummary(self, matter_id: str):
        """Synchronous compatibility endpoint for a small matter financial read."""
        try:
            return dict(self._excel_repo.get_matter_financial_summary(matter_id) or {})
        except Exception as exc:
            self._report_failure("Could not load matter financial summary", context="matter.financial_summary", exc=exc)
            return {"ok": False, "message": str(exc), "matterId": str(matter_id or "")}

    @Slot(str, str)
    def requestMatterFinancialSummary(self, request_id: str, matter_id: str) -> None:
        """Load a matter's WIP/unpaid-invoice summary without blocking QML."""
        token = str(request_id or "")
        normalized_matter_id = str(matter_id or "")

        def _load() -> Dict[str, Any]:
            return dict(self._excel_repo.get_matter_financial_summary(normalized_matter_id) or {})

        def _ready(result: Any) -> None:
            self.matterFinancialSummaryReady.emit(token, dict(result or {}))

        def _failed(error_info: tuple) -> None:
            _type, exc, _traceback = error_info
            message = str(exc or "Could not load matter financial summary.")
            self._report_failure(
                "Could not load matter financial summary",
                context="matter.financial_summary.async",
                exc=exc,
            )
            self.matterFinancialSummaryFailed.emit(token, message)

        self._start_background_worker(
            _load,
            name="matter_financial_summary",
            on_result=_ready,
            on_error=_failed,
        )

    @Slot(str, str, result=dict)
    def mergeMatters(self, source_matter_id: str, target_matter_name: str):
        try:
            payload = {
                "sourceKey": source_matter_id,
                "targetKey": target_matter_name,
                "reason": "Manual UI Merge",
                "actor": "AppController"
            }
            result = dict(self._excel_repo.merge_duplicate_matters(payload) or {})
            if result.get("ok"):
                self.toast.emit(f"Matter merged into {target_matter_name}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Merge failed.") or "").strip()
                self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not merge matters", context="matter.merge", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def saveMatterProfile(self, payload):
        try:
            result = dict(self._excel_repo.save_matter_profile(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Matter saved: {result.get('matterId', '')}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Matter profile verification failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save matter profile", context="repo.matter.save_profile", exc=exc)
            return {"ok": False, "matterId": "", "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def runConflictCheck(self, payload):
        result = self._crud.run_conflict_check(payload)
        if result.get("ok"):
            total = int(result.get("totalMatches", 0) or 0)
            risk = str(result.get("riskLevel", "") or "").strip().lower()
            note = f"Conflict check complete: {total} match(es)"
            if risk:
                note = f"{note} [{risk}]"
            self.toast.emit(note)
        else:
            message = str(result.get("message", "") or "").strip()
            if message:
                self.error.emit(message)
        return result

    @Slot("QVariantMap", result=dict)
    def reassignMatter(self, payload):
        result = self._crud.reassign_matter(payload)
        if result.get("ok"):
            if result.get("changed"):
                matter_label = str(result.get("matterName") or result.get("matterId") or "").strip()
                self.toast.emit(
                    f"Matter reassigned: {matter_label}" if matter_label else "Matter reassignment saved."
                )
                self.clientDataChanged.emit()
            else:
                self.toast.emit(str(result.get("message", "Matter reassignment checked.")))
        else:
            message = str(result.get("message", "") or "").strip()
            if message:
                self.error.emit(message)
        return result

    @Slot("QVariantMap", result=dict)
    def mergeDuplicateEntities(self, payload):
        result = self._crud.merge_duplicate_entities(payload)
        if result.get("ok"):
            if result.get("changed"):
                merge_type = str(result.get("mergeType", "entity") or "entity").strip()
                source_name = str(result.get("sourceName", "") or "").strip()
                target_name = str(result.get("targetName", "") or "").strip()
                label = f"{source_name} -> {target_name}".strip(" ->")
                if label:
                    self.toast.emit(f"{merge_type.title()} merge saved: {label}")
                else:
                    self.toast.emit(f"{merge_type.title()} merge saved.")
                self.clientDataChanged.emit()
            else:
                self.toast.emit(str(result.get("message", "Merge request checked.")))
        else:
            message = str(result.get("message", "") or "").strip()
            if message:
                self.error.emit(message)
        return result
    @Slot(str, result=dict)
    def handleOmniSearchCommand(self, query):
        return handle_omni_search_command(query, self._excel_repo, self._report_failure)

    @Slot("QVariantMap", result=bool)
    def recordUndockRequest(self, payload):
        try:
            event = dict(payload or {})
            state = self._load_runtime_state()
            raw_events = state.get("undockEvents")
            events = raw_events if isinstance(raw_events, list) else []

            events.append(
                {
                    "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
                    "tileIndex": int(event.get("tileIndex", -1)),
                    "titleText": str(event.get("titleText", "")),
                    "originX": int(event.get("originX", 0)),
                    "originY": int(event.get("originY", 0)),
                    "originW": int(event.get("originW", 0)),
                    "originH": int(event.get("originH", 0)),
                }
            )
            if len(events) > 40:
                events = events[-40:]

            state["undockEvents"] = events
            self._save_runtime_state(state)
            return True
        except Exception as exc:
            self._report_failure("Could not record undock event", context="session.record_undock", exc=exc)
            return False

    @Slot("QVariantMap", result=dict)
    def saveTimeDocketEntry(self, payload):
        try:
            result = dict(self._excel_repo.add_time_entry(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Time entry saved: {result.get('entryId', '')}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Time entry verification failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save time entry", context="repo.time.save_entry", exc=exc)
            return {"ok": False, "entryId": "", "message": str(exc)}

    @Slot(str, str, str, result=dict)
    def reopenMatterForDocketing(self, matter_id, entry_kind, confirmation_phrase):
        """Perform the explicit, audited re-open used by docket entry guards."""
        try:
            result = dict(
                self._excel_repo.reopen_matter_for_docketing(
                    str(matter_id or ""),
                    str(entry_kind or ""),
                    str(confirmation_phrase or ""),
                )
                or {}
            )
            if result.get("ok"):
                self.toast.emit(result.get("message", "Matter re-opened."))
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Matter re-open failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not re-open archived matter", context="matter.docket_reopen", exc=exc)
            return {"ok": False, "matterId": str(matter_id or ""), "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def saveFeeDocketEntry(self, payload):
        """Save a direct, matter-linked fee line into invoiceable WIP."""
        try:
            result = dict(self._excel_repo.add_fee_entry(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Fee entry saved: {result.get('entryId', '')}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Fee entry verification failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save fee entry", context="repo.time.save_fee_entry", exc=exc)
            return {"ok": False, "entryId": "", "message": str(exc)}

    @Slot(str, "QVariantMap", result=dict)
    def updateTimeDocketEntry(self, entry_id, changes):
        try:
            result = dict(self._excel_repo.update_time_entry(str(entry_id), dict(changes or {})) or {})
            result["verifiedExact"] = True
            if result.get("ok"):
                self.toast.emit(f"Time entry updated: {entry_id}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Time entry update failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not update time entry", context="repo.time.update_entry", exc=exc)
            return {"ok": False, "entryId": str(entry_id), "message": str(exc)}

    @Slot(str, result=dict)
    def deleteTimeEntry(self, entry_id):
        try:
            result = dict(self._excel_repo.delete_time_entry(str(entry_id)) or {})
            if result.get("ok"):
                self.toast.emit(f"Time entry deleted.")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Time entry deletion failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not delete time entry", context="repo.time.delete_entry", exc=exc)
            return {"ok": False, "entryId": str(entry_id), "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def saveTrademarkFiling(self, payload):
        try:
            result = dict(self._excel_repo.save_trademark_filing(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Trademark filing saved: {result.get('trademarkId', '')}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Trademark verification failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save trademark", context="repo.trademark.save", exc=exc)
            return {"ok": False, "trademarkId": "", "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def acquireGlobalTimerLock(self, payload):
        try:
            data = dict(payload or {})
            owner_id = str(data.get("ownerId", "") or "").strip()
            force_takeover = bool(data.get("forceTakeover", False))
            if not owner_id:
                return {
                    "ok": False,
                    "granted": False,
                    "message": "ownerId is required.",
                    "holder": dict(self._global_timer_lock or {}),
                }

            now_utc = datetime.now(timezone.utc).isoformat()
            holder = dict(self._global_timer_lock or {})
            holder_id = str(holder.get("ownerId", "") or "").strip()
            takeover_happened = False
            previous_holder = {}

            if holder_id and holder_id != owner_id:
                if not force_takeover:
                    return {
                        "ok": True,
                        "granted": False,
                        "message": "A timer is already running in another window.",
                        "holder": holder,
                        "takenOver": False,
                    }
                takeover_happened = True
                previous_holder = dict(holder)

            lock_payload = {
                "ownerId": owner_id,
                "ownerLabel": str(data.get("ownerLabel", "") or "").strip(),
                "descriptor": str(data.get("descriptor", "") or "").strip(),
                "tileIndex": int(data.get("tileIndex", -1)),
                "laneKey": str(data.get("laneKey", "") or "").strip(),
                "acquiredAtUtc": str(holder.get("acquiredAtUtc", "") or now_utc),
                "updatedAtUtc": now_utc,
            }
            self._global_timer_lock = lock_payload
            state = self._load_runtime_state()
            state["globalTimerLock"] = lock_payload
            self._save_runtime_state(state)
            return {
                "ok": True,
                "granted": True,
                "message": "",
                "holder": dict(lock_payload),
                "takenOver": bool(takeover_happened),
                "previousHolder": dict(previous_holder),
            }
        except Exception as exc:
            self._report_failure("Could not acquire timer lock", context="session.timer_lock.acquire", exc=exc)
            return {
                "ok": False,
                "granted": False,
                "message": str(exc),
                "holder": dict(self._global_timer_lock or {}),
                "takenOver": False,
                "previousHolder": {},
            }

    @Slot("QVariantMap", result=bool)
    def releaseGlobalTimerLock(self, payload):
        try:
            data = dict(payload or {})
            owner_id = str(data.get("ownerId", "") or "").strip()
            if not owner_id:
                return False
            holder = dict(self._global_timer_lock or {})
            holder_id = str(holder.get("ownerId", "") or "").strip()
            if holder_id and holder_id != owner_id:
                return False

            self._global_timer_lock = {}
            state = self._load_runtime_state()
            state["globalTimerLock"] = {}
            self._save_runtime_state(state)
            return True
        except Exception as exc:
            self._report_failure("Could not release timer lock", context="session.timer_lock.release", exc=exc)
            return False

    @Slot(result=dict)
    def getGlobalTimerLock(self):
        try:
            holder = dict(self._global_timer_lock or {})
            if not holder:
                state = self._load_runtime_state()
                raw = state.get("globalTimerLock", {})
                if isinstance(raw, dict):
                    holder = dict(raw)
                    self._global_timer_lock = dict(raw)
            return {
                "ok": True,
                "active": bool(holder and str(holder.get("ownerId", "") or "").strip()),
                "holder": holder,
            }
        except Exception as exc:
            self._report_failure("Could not read timer lock", context="session.timer_lock.read", exc=exc)
            return {"ok": False, "active": False, "holder": {}, "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def mergeDuplicateEntities(self, payload):
        result = self._crud.merge_duplicate_entities(payload)
        if result.get("ok"):
            if result.get("changed"):
                merge_type = str(result.get("mergeType", "entity") or "entity").strip()
                source_name = str(result.get("sourceName", "") or "").strip()
                target_name = str(result.get("targetName", "") or "").strip()
                label = f"{source_name} -> {target_name}".strip(" ->")
                if label:
                    self.toast.emit(f"{merge_type.title()} merge saved: {label}")
                else:
                    self.toast.emit(f"{merge_type.title()} merge saved.")
                self.clientDataChanged.emit()
            else:
                self.toast.emit(str(result.get("message", "Merge request checked.")))
        else:
            message = str(result.get("message", "") or "").strip()
            if message:
                self.error.emit(message)
        return result
    @Slot(str, result=dict)
    def handleOmniSearchCommand(self, query):
        return handle_omni_search_command(query, self._excel_repo, self._report_failure)

    @Slot("QVariantMap", result=bool)
    def recordUndockRequest(self, payload):
        try:
            event = dict(payload or {})
            state = self._load_runtime_state()
            raw_events = state.get("undockEvents")
            events = raw_events if isinstance(raw_events, list) else []

            events.append(
                {
                    "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
                    "tileIndex": int(event.get("tileIndex", -1)),
                    "titleText": str(event.get("titleText", "")),
                    "originX": int(event.get("originX", 0)),
                    "originY": int(event.get("originY", 0)),
                    "originW": int(event.get("originW", 0)),
                    "originH": int(event.get("originH", 0)),
                }
            )
            if len(events) > 40:
                events = events[-40:]

            state["undockEvents"] = events
            self._save_runtime_state(state)
            return True
        except Exception as exc:
            self._report_failure("Could not record undock event", context="session.record_undock", exc=exc)
            return False

    @Slot("QVariantMap", result=dict)
    def saveTimeDocketEntry(self, payload):
        try:
            result = dict(self._excel_repo.add_time_entry(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Time entry saved: {result.get('entryId', '')}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Time entry verification failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save time entry", context="repo.time.save_entry", exc=exc)
            return {"ok": False, "entryId": "", "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def saveTrademarkFiling(self, payload):
        try:
            result = dict(self._excel_repo.save_trademark_filing(dict(payload or {})) or {})
            if result.get("ok"):
                self.toast.emit(f"Trademark filing saved: {result.get('trademarkId', '')}")
                self.clientDataChanged.emit()
            else:
                message = str(result.get("message", "Trademark verification failed.") or "").strip()
                if message:
                    self.error.emit(message)
            return result
        except Exception as exc:
            self._report_failure("Could not save trademark", context="repo.trademark.save", exc=exc)
            return {"ok": False, "trademarkId": "", "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def acquireGlobalTimerLock(self, payload):
        try:
            data = dict(payload or {})
            owner_id = str(data.get("ownerId", "") or "").strip()
            force_takeover = bool(data.get("forceTakeover", False))
            if not owner_id:
                return {
                    "ok": False,
                    "granted": False,
                    "message": "ownerId is required.",
                    "holder": dict(self._global_timer_lock or {}),
                }

            now_utc = datetime.now(timezone.utc).isoformat()
            holder = dict(self._global_timer_lock or {})
            holder_id = str(holder.get("ownerId", "") or "").strip()
            takeover_happened = False
            previous_holder = {}

            if holder_id and holder_id != owner_id:
                if not force_takeover:
                    return {
                        "ok": True,
                        "granted": False,
                        "message": "A timer is already running in another window.",
                        "holder": holder,
                        "takenOver": False,
                    }
                takeover_happened = True
                previous_holder = dict(holder)

            lock_payload = {
                "ownerId": owner_id,
                "ownerLabel": str(data.get("ownerLabel", "") or "").strip(),
                "descriptor": str(data.get("descriptor", "") or "").strip(),
                "tileIndex": int(data.get("tileIndex", -1)),
                "laneKey": str(data.get("laneKey", "") or "").strip(),
                "acquiredAtUtc": str(holder.get("acquiredAtUtc", "") or now_utc),
                "updatedAtUtc": now_utc,
            }
            self._global_timer_lock = lock_payload
            state = self._load_runtime_state()
            state["globalTimerLock"] = lock_payload
            self._save_runtime_state(state)
            return {
                "ok": True,
                "granted": True,
                "message": "",
                "holder": dict(lock_payload),
                "takenOver": bool(takeover_happened),
                "previousHolder": dict(previous_holder),
            }
        except Exception as exc:
            self._report_failure("Could not acquire timer lock", context="session.timer_lock.acquire", exc=exc)
            return {
                "ok": False,
                "granted": False,
                "message": str(exc),
                "holder": dict(self._global_timer_lock or {}),
                "takenOver": False,
                "previousHolder": {},
            }

    @Slot("QVariantMap", result=bool)
    def releaseGlobalTimerLock(self, payload):
        try:
            data = dict(payload or {})
            owner_id = str(data.get("ownerId", "") or "").strip()
            if not owner_id:
                return False
            holder = dict(self._global_timer_lock or {})
            holder_id = str(holder.get("ownerId", "") or "").strip()
            if holder_id and holder_id != owner_id:
                return False

            self._global_timer_lock = {}
            state = self._load_runtime_state()
            state["globalTimerLock"] = {}
            self._save_runtime_state(state)
            return True
        except Exception as exc:
            self._report_failure("Could not release timer lock", context="session.timer_lock.release", exc=exc)
            return False

    @Slot(result=dict)
    def getGlobalTimerLock(self):
        try:
            holder = dict(self._global_timer_lock or {})
            if not holder:
                state = self._load_runtime_state()
                raw = state.get("globalTimerLock", {})
                if isinstance(raw, dict):
                    holder = dict(raw)
                    self._global_timer_lock = dict(raw)
            return {
                "ok": True,
                "active": bool(holder and str(holder.get("ownerId", "") or "").strip()),
                "holder": holder,
            }
        except Exception as exc:
            self._report_failure("Could not read timer lock", context="session.timer_lock.read", exc=exc)
            return {"ok": False, "active": False, "holder": {}, "message": str(exc)}


    @Slot("QVariantMap", result=dict)
    def getTimeDocketAggregate(self, payload):
        """Synchronous aggregate lookup used by TimeDocketView for local bucket restore."""
        try:
            return dict(self._excel_repo.get_time_docket_aggregate(dict(payload or {})) or {})
        except Exception as exc:
            self._report_failure("Could not load time aggregate", context="repo.time.aggregate", exc=exc)
            return {"ok": False, "exists": False, "message": str(exc)}

    # NOTE: getTimeDocketAggregate and getDocketActivityReport have been removed.
    # These operations are now handled exclusively by the async DocketingController
    # (docketApp) which dispatches to QThreadPool workers.
    # The blocking versions caused UI freezes during large data aggregations.

    def _strip_file_uri(self, raw_path: str) -> str:
        """Strip file:/// prefix that QML FileDialog adds on Windows."""
        p = raw_path
        if p.startswith("file:///"):
            p = p[8:]
        elif p.startswith("file://"):
            p = p[7:]
        elif p.startswith("file:"):
            p = p[5:]
        return unquote(p)

    def _normalize_legacy_dockets_recent_files(self, raw_files: Any) -> list[str]:
        files = raw_files if isinstance(raw_files, list) else []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in files:
            item_path = item.get("path") if isinstance(item, dict) else item
            raw_path = str(item_path or "").strip()
            if not raw_path:
                continue
            try:
                path_text = str(self._coerce_file_path(raw_path).expanduser().resolve(strict=False))
            except (OSError, RuntimeError):
                path_text = str(self._coerce_file_path(raw_path).expanduser())
            key = os.path.normcase(os.path.normpath(path_text))
            if key in seen:
                continue
            seen.add(key)
            normalized.append(path_text)
        return normalized

    def _legacy_dockets_recent_files(self) -> list[str]:
        if not self._settings_load_complete:
            self.load_settings()
        files = self._normalize_legacy_dockets_recent_files(
            self._settings_data.get(LEGACY_DOCKETS_RECENT_FILES_KEY, [])
        )
        self._settings_data[LEGACY_DOCKETS_RECENT_FILES_KEY] = files
        return files

    def _remember_legacy_dockets_import_file(self, raw_file_path: str) -> Dict[str, Any]:
        raw_path = str(raw_file_path or "").strip()
        if not raw_path:
            return {"ok": False, "files": self._legacy_dockets_recent_files(), "message": "Select an import file."}

        source_path = self._coerce_file_path(raw_path).expanduser()
        if not source_path.exists() or not source_path.is_file():
            return {
                "ok": False,
                "files": self._legacy_dockets_recent_files(),
                "message": "The selected import file was not found.",
            }
        if source_path.suffix.lower() not in {".xlsm", ".xlsx"}:
            return {
                "ok": False,
                "files": self._legacy_dockets_recent_files(),
                "message": "Legacy Dockets import files must be XLSM or XLSX workbooks.",
            }

        source_text = str(source_path.resolve(strict=False))
        source_key = os.path.normcase(os.path.normpath(source_text))
        files = [
            path
            for path in self._legacy_dockets_recent_files()
            if os.path.normcase(os.path.normpath(path)) != source_key
        ]
        files.insert(0, source_text)
        self._settings_data[LEGACY_DOCKETS_RECENT_FILES_KEY] = files
        self.save_settings()
        return {
            "ok": True,
            "files": files,
            "lastUsedPath": source_text,
        }

    @Slot(result=dict)
    def getLegacyDocketsRecentFiles(self):
        try:
            files = self._legacy_dockets_recent_files()
            return {
                "ok": True,
                "files": files,
                "lastUsedPath": files[0] if files else "",
            }
        except Exception as exc:
            self._report_failure(
                "Could not load recent Legacy Dockets import files.",
                context="import.legacy.recent_files.load",
                exc=exc,
            )
            return {"ok": False, "files": [], "lastUsedPath": "", "message": str(exc)}

    @Slot(result=str)
    def browseLegacyDocketsFile(self):
        """Open a file dialog that bypasses Windows native file-lock checks."""
        try:
            from PySide6.QtWidgets import QFileDialog
            options = QFileDialog.DontUseNativeDialog
            path, _ = QFileDialog.getOpenFileName(
                None,
                "Select Legacy Dockets File",
                "",
                "Excel files (*.xlsm *.xlsx);;All files (*)",
                options=options
            )
            return path or ""
        except Exception as e:
            self.error.emit(f"Error opening file dialog: {e}")
            return ""

    @Slot(str, result=dict)
    def rememberLegacyDocketsImportFile(self, raw_file_path):
        try:
            return self._remember_legacy_dockets_import_file(raw_file_path)
        except Exception as exc:
            self._report_failure(
                "Could not remember the Legacy Dockets import file.",
                context="import.legacy.recent_files.save",
                exc=exc,
            )
            return {"ok": False, "files": [], "lastUsedPath": "", "message": str(exc)}

    def _parse_legacy_import_date(self, raw_value) -> Optional[datetime]:
        text = str(raw_value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    @Slot(str, result=dict)
    @Slot(str, str, str, str, result=dict)
    def previewLegacyDockets(self, raw_file_path, mode="all", start_date="", end_date=""):
        """Quick row-count preview without importing anything."""
        from services.dockets_import_service import DocketsImportService
        try:
            service = DocketsImportService(self._excel_repo)
            target_path = self._strip_file_uri(raw_file_path)
            return service.count_rows(
                target_path,
                mode=mode or "all",
                start_date=self._parse_legacy_import_date(start_date),
                end_date=self._parse_legacy_import_date(end_date),
            )
        except Exception as exc:
            self._report_failure("Could not preview legacy dockets", context="import.preview", exc=exc)
            return {"total": 0}

    @Slot(str, str, str, str, str, str, result=dict)
    def analyzeLegacyDockets(self, raw_file_path, mode, start_date, end_date, data_types_json, client_filter):
        """Build a read-only row review report for a legacy Dockets workbook."""
        from services.dockets_import_service import DocketsImportService
        import json

        data_types = None
        if data_types_json:
            try:
                parsed = json.loads(data_types_json)
                if isinstance(parsed, list) and parsed:
                    data_types = [str(s) for s in parsed]
            except (json.JSONDecodeError, TypeError):
                pass

        try:
            target_path = self._strip_file_uri(raw_file_path)
            parsed = urlparse(str(target_path or ""))
            if parsed.scheme in {"http", "https"}:
                return {
                    "success": False,
                    "message": (
                        "For this first phase, select the locally synced OneDrive/SharePoint "
                        "copy of Dockets.xlsm. Direct SharePoint web links require an "
                        "authenticated download path that will be added in a later phase."
                    ),
                    "summary": {},
                    "rows": [],
                    "warnings": [],
                    "errors": ["Direct SharePoint web links are not supported in this phase."],
                }

            service = DocketsImportService(self._excel_repo)
            result = service.analyze_legacy_workbook(
                target_path,
                mode=mode or "all",
                start_date=self._parse_legacy_import_date(start_date),
                end_date=self._parse_legacy_import_date(end_date),
                data_types=data_types,
                client_filter=client_filter.strip() if client_filter else None,
            )
            if result.get("success"):
                try:
                    self._remember_legacy_dockets_import_file(target_path)
                except Exception as remember_exc:
                    logging.getLogger("import.legacy").warning(
                        "Could not remember analyzed Legacy Dockets file: %s",
                        str(remember_exc),
                    )
            return result
        except Exception as exc:
            self._report_failure("Could not analyze legacy dockets", context="import.legacy.analyze", exc=exc)
            return {
                "success": False,
                "message": str(exc),
                "summary": {},
                "rows": [],
                "warnings": [],
                "errors": [str(exc)],
            }

    @Slot(str, result=list)
    def listLegacySourceClients(self, raw_file_path):
        """Quick scan of source workbook to extract unique client names for filter UI."""
        from services.dockets_import_service import DocketsImportService
        try:
            target_path = self._strip_file_uri(raw_file_path)
            service = DocketsImportService(self._excel_repo)
            return service.list_source_clients(target_path)
        except Exception as exc:
            self._report_failure("Could not list source clients", context="import.legacy.source_clients", exc=exc)
            return []
    @Slot("QVariantMap", result=dict)
    def exportLegacyDocketsAnalysisExcel(self, payload):
        """Export the analysis result rows to an Excel file."""
        from services.dockets_import_service import DocketsImportService
        try:
            payload_dict = dict(payload or {})
            rows = payload_dict.get("rows", [])
            if not isinstance(rows, list):
                rows = []

            service = DocketsImportService(self._excel_repo)
            candidate_dirs = [
                self._paths.exports_dir(),
                self._paths.data_dir() / "exports",
                self._paths.root / "outputs",
            ]
            filepath = ""
            last_error = None
            for export_dir in candidate_dirs:
                try:
                    export_dir.mkdir(parents=True, exist_ok=True)
                    filepath = service.export_analysis_to_excel(rows, str(export_dir))
                    if filepath:
                        break
                except Exception as exc:
                    last_error = exc
                    continue

            if not filepath:
                raise RuntimeError(f"Excel export failed for all output locations: {last_error}")
            filepath = os.path.abspath(filepath)
            if not os.path.exists(filepath):
                raise RuntimeError(f"Excel exporter returned a non-existent path: {filepath}")
            
            return {
                "ok": True,
                "path": filepath,
                "filename": os.path.basename(filepath),
                "message": f"Excel exported: {os.path.basename(filepath)} | Saved to: {os.path.dirname(filepath)}"
            }
        except Exception as exc:
            self._report_failure("Could not export analysis to Excel", context="import.legacy.export_excel", exc=exc)
            return {"ok": False, "message": str(exc)}

    @Slot(str, str, str, str, result=bool)
    def startLegacyDocketsImport(self, raw_file_path, mode, start_date, end_date):
        """Start the legacy dockets import process."""
        try:
            with self._legacy_import_state_lock:
                if getattr(self, "_legacy_import_active", False):
                    return False
                self._legacy_import_active = True
                self._legacy_import_cancellation = object()
                cancellation = self._legacy_import_cancellation

            target_path = self._strip_file_uri(raw_file_path)

            def _worker():
                from services.dockets_import_service import DocketsImportService
                try:
                    service = DocketsImportService(self._excel_repo)
                    
                    def progress_cb(phase, current, total):
                        self.importProgress.emit(phase, current, total)

                    def duplicate_cb(duplicate_record):
                        with self._legacy_import_duplicate_lock:
                            self._legacy_import_duplicate_payload = duplicate_record
                            self._legacy_import_duplicate_decision = None
                            self.importDuplicateFound.emit(duplicate_record)
                            
                        # Wait for decision
                        while True:
                            with self._legacy_import_state_lock:
                                if self._legacy_import_cancellation is not cancellation:
                                    return {"action": "skip", "scope": "one"}
                            
                            with self._legacy_import_duplicate_lock:
                                if getattr(self, "_legacy_import_duplicate_decision", None) is not None:
                                    decision = self._legacy_import_duplicate_decision
                                    self._legacy_import_duplicate_payload = None
                                    self._legacy_import_duplicate_decision = None
                                    return decision
                            import time
                            time.sleep(0.1)

                    result = service.import_legacy_workbook(
                        target_path,
                        mode=mode or "all",
                        start_date=self._parse_legacy_import_date(start_date),
                        end_date=self._parse_legacy_import_date(end_date),
                        progress_callback=progress_cb,
                        duplicate_callback=duplicate_cb
                    )
                    
                    self.importFinished.emit(result)
                except Exception as exc:
                    self._report_failure("Background import error", context="import.legacy.worker", exc=exc)
                    self.importFinished.emit({"success": False, "errors": [str(exc)]})
                finally:
                    with self._legacy_import_state_lock:
                        if getattr(self, "_legacy_import_cancellation", None) is cancellation:
                            self._legacy_import_active = False
                            self._legacy_import_cancellation = None

            worker = Worker(_worker)
            self._background_pool.start(worker)
            return True

        except Exception as exc:
            with self._legacy_import_state_lock:
                if getattr(self, "_legacy_import_cancellation", None) is not None:
                    self._legacy_import_active = False
                    self._legacy_import_cancellation = None
            self._report_failure("Could not start legacy dockets import", context="import.legacy.start", exc=exc)
            self.importFinished.emit({"success": False, "errors": [str(exc)]})
            return False

    @Slot("QVariantMap", result=bool)
    def startLegacyDocketsFilteredImport(self, payload):
        """Start the legacy dockets import process with filtered rows."""
        try:
            data = dict(payload or {})
            raw_file_path = str(data.get("filePath", ""))
            mode = str(data.get("mode", "all"))
            start_date = str(data.get("startDate", ""))
            end_date = str(data.get("endDate", ""))
            data_types_json = str(data.get("dataTypes", ""))
            client_filter = str(data.get("clientFilter", ""))
            allowed_rows = data.get("allowedRows", {})
            import logging
            logging.getLogger("import.debug").info(f"startLegacyDocketsFilteredImport payload: {payload}")
            logging.getLogger("import.debug").info(f"allowed_rows: {allowed_rows}")
            
            with self._legacy_import_state_lock:
                if getattr(self, "_legacy_import_active", False):
                    return False
                self._legacy_import_active = True
                self._legacy_import_cancellation = object()
                cancellation = self._legacy_import_cancellation

            target_path = self._strip_file_uri(raw_file_path)

            def _worker():
                from services.dockets_import_service import DocketsImportService
                try:
                    service = DocketsImportService(self._excel_repo)
                    
                    def progress_cb(phase, current, total):
                        self.importProgress.emit(phase, current, total)

                    def duplicate_cb(duplicate_record):
                        with self._legacy_import_duplicate_lock:
                            self._legacy_import_duplicate_payload = duplicate_record
                            self._legacy_import_duplicate_decision = None
                            self.importDuplicateFound.emit(duplicate_record)
                            
                        # Wait for decision
                        while True:
                            with self._legacy_import_state_lock:
                                if self._legacy_import_cancellation is not cancellation:
                                    return {"action": "skip", "scope": "one"}
                            
                            with self._legacy_import_duplicate_lock:
                                if getattr(self, "_legacy_import_duplicate_decision", None) is not None:
                                    decision = self._legacy_import_duplicate_decision
                                    self._legacy_import_duplicate_payload = None
                                    self._legacy_import_duplicate_decision = None
                                    return decision
                            import time
                            time.sleep(0.1)

                    import json
                    data_types = None
                    if data_types_json:
                        try:
                            parsed = json.loads(data_types_json)
                            if isinstance(parsed, list) and parsed:
                                data_types = [str(s) for s in parsed]
                        except (json.JSONDecodeError, TypeError):
                            pass

                    result = service.import_legacy_workbook(
                        target_path,
                        mode=mode or "all",
                        start_date=self._parse_legacy_import_date(start_date),
                        end_date=self._parse_legacy_import_date(end_date),
                        progress_callback=progress_cb,
                        duplicate_callback=duplicate_cb,
                        allowed_rows=allowed_rows,
                        data_types=data_types,
                        client_filter=client_filter.strip() if client_filter else None
                    )
                    
                    self.importFinished.emit(result)
                except Exception as exc:
                    self._report_failure("Background import error", context="import.legacy.worker", exc=exc)
                    self.importFinished.emit({"success": False, "errors": [str(exc)]})
                finally:
                    with self._legacy_import_state_lock:
                        if getattr(self, "_legacy_import_cancellation", None) is cancellation:
                            self._legacy_import_active = False
                            self._legacy_import_cancellation = None

            worker = Worker(_worker)
            self._background_pool.start(worker)
            return True

        except Exception as exc:
            with self._legacy_import_state_lock:
                if getattr(self, "_legacy_import_cancellation", None) is not None:
                    self._legacy_import_active = False
                    self._legacy_import_cancellation = None
            self._report_failure("Could not start legacy dockets import", context="import.legacy.start", exc=exc)
            self.importFinished.emit({"success": False, "errors": [str(exc)]})
            return False

    @Slot("QVariantMap", result=bool)
    def resolveLegacyDocketsDuplicate(self, payload):
        """Bridge slot for QML duplicate prompt resolution."""
        data = dict(payload or {})
        action = str(data.get("action", "skip"))
        scope = str(data.get("scope", "one"))
        return self.respondToDuplicatePrompt(action, scope)

    @Slot(str, str, result=bool)
    def respondToDuplicatePrompt(self, action, scope):
        """Handle user response to a duplicate prompt during import."""
        with self._legacy_import_duplicate_lock:
            self._legacy_import_duplicate_decision = {"action": action, "scope": scope}
        return True

    @Slot(result=bool)
    def cancelLegacyDocketsImport(self):
        with self._legacy_import_state_lock:
            self._legacy_import_cancellation = None
            self._legacy_import_active = False
        with self._legacy_import_duplicate_lock:
            self._legacy_import_duplicate_decision = {"action": "skip", "scope": "all"}
        return True

    @Slot("QVariantMap", result=dict)
    def exportReportCsv(self, payload):
        payload_dict = dict(payload or {})
        report_id = str(payload_dict.get("reportId") or payload_dict.get("report_id") or "").strip().lower()
        if report_id in {"docket_activity", "docket_activity_report", ""}:
            export_payload = payload_dict.get("exportPayload")
            if not isinstance(export_payload, dict):
                export_payload = payload_dict
            return self.exportDocketActivityCsv(export_payload)
        if report_id == "statement_of_account":
            export_payload = payload_dict.get("exportPayload")
            if not isinstance(export_payload, dict):
                export_payload = payload_dict
            try:
                return self._excel_repo.export_statement_of_account_csv(export_payload)
            except Exception as exc:
                self._report_failure(
                    "Could not export Statement of Account CSV",
                    context="report.statement_of_account.export_csv",
                    exc=exc,
                )
                return {
                    "ok": False,
                    "path": "",
                    "filename": "",
                    "rowCount": 0,
                    "message": str(exc),
                }
        if report_id in {"ar_aging", "ar_aging_report", "accounts_receivable"} or report_id.startswith("ar_aging_"):
            export_payload = payload_dict.get("exportPayload")
            if not isinstance(export_payload, dict):
                export_payload = payload_dict
            try:
                return self._excel_repo.export_ar_aging_csv(export_payload)
            except Exception as exc:
                self._report_failure("Could not export A/R aging CSV", context="report.ar_aging.export_csv", exc=exc)
                return {
                    "ok": False,
                    "path": "",
                    "filename": "",
                    "rowCount": 0,
                    "message": str(exc),
                }
        return {
            "ok": False,
            "path": "",
            "filename": "",
            "rowCount": 0,
            "message": f"CSV export is not available for report: {report_id}",
        }

    # ── SECTION: Session & Shutdown ──────────────────────────────────────────

    @Slot("QVariantMap", result=bool)
    def saveCloseSessionSnapshot(self, payload):
        return self._session_mgr.save_close_session_snapshot(dict(payload or {}))

    @Slot(result=dict)
    def getPendingCloseRecovery(self):
        return self._session_mgr.get_pending_close_recovery(self._pending_close_recovery)

    @Slot(str, result=bool)
    def resolvePendingCloseRecovery(self, action):
        result = self._session_mgr.resolve_pending_close_recovery(action)
        if result:
            self._pending_close_recovery = None
        return result

    @Slot(bool, result=bool)
    def markExpectedShutdown(self, clear_recovery_snapshot=True):
        self._global_timer_lock = {}
        try:
            payload = self._excel_repo.home_dashboard_summary()
            if payload and payload.get("ok"):
                self._persist_home_dashboard_summary_cache(payload)
        except Exception:
            pass
        result = self._session_mgr.mark_expected_shutdown(clear_recovery_snapshot)
        if result and clear_recovery_snapshot:
            self._pending_close_recovery = None
        return result

    def _load_pending_close_recovery(self) -> Optional[Dict[str, Any]]:
        return self._session_mgr.load_pending_close_recovery()

    def _build_recovery_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return SessionRecoveryManager.build_recovery_summary(payload)

    def _payload_has_close_risk(self, payload: Any) -> bool:
        return SessionRecoveryManager.payload_has_close_risk(payload)

    def _mark_runtime_open(self) -> None:
        self._global_timer_lock = {}
        self._session_mgr.mark_runtime_open()

    def _load_runtime_state(self) -> Dict[str, Any]:
        return self._session_mgr.load_runtime_state()

    def _save_runtime_state(self, state: Dict[str, Any]) -> None:
        self._session_mgr.save_runtime_state(state)

    def _load_close_session_snapshot(self) -> Optional[Dict[str, Any]]:
        return self._session_mgr.load_close_session_snapshot()

    def _write_json_atomic(self, target_path: Path, payload: Dict[str, Any]) -> None:
        self._session_mgr.write_json_atomic(target_path, payload)

    def _delete_file_if_exists(self, path: Path) -> None:
        self._session_mgr.delete_file_if_exists(path)

    @Slot("QVariantMap", result=dict)
    def exportDocketActivityPdf(self, payload):
        try:
            from services.report_pdf_exporter import generate_docket_pdf
            export_payload, branding_profile = self._apply_report_branding_to_payload(payload)
            logo_path = self._logo_path_for_pdf(branding_profile)
            candidate_dirs = [
                self._paths.exports_dir(),
                self._paths.data_dir() / "exports",
                self._paths.root / "outputs",
            ]
            filepath = ""
            last_error = None
            for export_dir in candidate_dirs:
                try:
                    export_dir.mkdir(parents=True, exist_ok=True)
                    filepath = generate_docket_pdf(export_payload, str(export_dir), str(logo_path))
                    if filepath:
                        break
                except Exception as exc:
                    last_error = exc
                    continue
            if not filepath:
                raise RuntimeError(f"PDF export failed for all output locations: {last_error}")
            filepath = os.path.abspath(filepath)
            if not os.path.exists(filepath):
                raise RuntimeError(f"PDF exporter returned a non-existent path: {filepath}")
            return {
                "ok": True,
                "path": filepath,
                "filename": os.path.basename(filepath),
                "message": f"PDF exported: {os.path.basename(filepath)} | Saved to: {os.path.dirname(filepath)}"
            }
        except Exception as exc:
            self._report_failure("Could not export PDF", context="report.docket_activity.export_pdf", exc=exc)
            logging.getLogger("cspm.pdf").exception("PDF export failed")
            return {"ok": False, "message": str(exc)}

    @Slot("QVariantMap", result=dict)
    def saveReportPdf(self, payload):
        payload_dict = dict(payload or {})
        report_id = str(payload_dict.get("reportId") or payload_dict.get("report_id") or "").strip().lower()
        if report_id in {"docket_activity", "docket_activity_report", ""}:
            export_payload = payload_dict.get("exportPayload")
            if not isinstance(export_payload, dict):
                export_payload = payload_dict
            return self.exportDocketActivityPdf(export_payload)
        if report_id in {"matter_time_ledger", "today_time_ledger", "time_ledger"}:
            try:
                from services.report_pdf_exporter import generate_matter_time_ledger_pdf

                export_payload = payload_dict.get("exportPayload")
                if not isinstance(export_payload, dict):
                    export_payload = payload_dict
                export_payload, branding_profile = self._apply_report_branding_to_payload(export_payload)
                logo_path = self._logo_path_for_pdf(branding_profile)
                candidate_dirs = [
                    self._paths.exports_dir(),
                    self._paths.data_dir() / "exports",
                    self._paths.root / "outputs",
                ]
                filepath = ""
                last_error = None
                for export_dir in candidate_dirs:
                    try:
                        export_dir.mkdir(parents=True, exist_ok=True)
                        filepath = generate_matter_time_ledger_pdf(export_payload, str(export_dir), str(logo_path))
                        if filepath:
                            break
                    except Exception as exc:
                        last_error = exc
                        continue
                if not filepath:
                    raise RuntimeError(f"PDF export failed for all output locations: {last_error}")
                filepath = os.path.abspath(filepath)
                if not os.path.exists(filepath):
                    raise RuntimeError(f"PDF exporter returned a non-existent path: {filepath}")
                return {
                    "ok": True,
                    "path": filepath,
                    "filename": os.path.basename(filepath),
                    "message": f"PDF exported: {os.path.basename(filepath)} | Saved to: {os.path.dirname(filepath)}",
                }
            except Exception as exc:
                self._report_failure(
                    "Could not export Matter Time Ledger PDF",
                    context="report.matter_time_ledger.export_pdf",
                    exc=exc,
                )
                logging.getLogger("cspm.pdf").exception("Matter Time Ledger PDF export failed")
                return {"ok": False, "message": str(exc), "path": "", "filename": ""}
        if report_id in {"productivity", "productivity_report"}:
            try:
                from services.report_pdf_exporter import generate_productivity_report_pdf

                export_payload = payload_dict.get("exportPayload")
                if not isinstance(export_payload, dict):
                    export_payload = payload_dict
                export_payload, branding_profile = self._apply_report_branding_to_payload(export_payload)
                logo_path = self._logo_path_for_pdf(branding_profile)
                candidate_dirs = [
                    self._paths.exports_dir(),
                    self._paths.data_dir() / "exports",
                    self._paths.root / "outputs",
                ]
                filepath = ""
                last_error = None
                for export_dir in candidate_dirs:
                    try:
                        export_dir.mkdir(parents=True, exist_ok=True)
                        filepath = generate_productivity_report_pdf(export_payload, str(export_dir), str(logo_path))
                        if filepath:
                            break
                    except Exception as exc:
                        last_error = exc
                        continue
                if not filepath:
                    raise RuntimeError(f"PDF export failed for all output locations: {last_error}")
                filepath = os.path.abspath(filepath)
                if not os.path.exists(filepath):
                    raise RuntimeError(f"PDF exporter returned a non-existent path: {filepath}")
                return {
                    "ok": True,
                    "path": filepath,
                    "filename": os.path.basename(filepath),
                    "message": f"PDF exported: {os.path.basename(filepath)} | Saved to: {os.path.dirname(filepath)}",
                }
            except Exception as exc:
                self._report_failure(
                    "Could not export Productivity Report PDF",
                    context="report.productivity.export_pdf",
                    exc=exc,
                )
                logging.getLogger("cspm.pdf").exception("Productivity Report PDF export failed")
                return {"ok": False, "message": str(exc), "path": "", "filename": ""}
        if report_id in {"ar_aging", "ar_aging_report", "accounts_receivable", "statement_of_account"} or report_id.startswith("ar_aging_"):
            try:
                from services.report_pdf_exporter import (
                    generate_generic_report_pdf,
                    generate_statement_of_account_pdf,
                )

                export_payload = payload_dict.get("exportPayload")
                if not isinstance(export_payload, dict):
                    export_payload = payload_dict
                export_payload, branding_profile = self._apply_report_branding_to_payload(export_payload)
                logo_path = self._logo_path_for_pdf(branding_profile)
                candidate_dirs = [
                    self._paths.exports_dir(),
                    self._paths.data_dir() / "exports",
                    self._paths.root / "outputs",
                ]
                filepath = ""
                last_error = None
                for export_dir in candidate_dirs:
                    try:
                        export_dir.mkdir(parents=True, exist_ok=True)
                        if report_id == "statement_of_account":
                            filepath = generate_statement_of_account_pdf(export_payload, str(export_dir), str(logo_path))
                        else:
                            filepath = generate_generic_report_pdf(export_payload, str(export_dir), str(logo_path))
                        if filepath:
                            break
                    except Exception as exc:
                        last_error = exc
                        continue
                if not filepath:
                    raise RuntimeError(f"PDF export failed for all output locations: {last_error}")
                filepath = os.path.abspath(filepath)
                if not os.path.exists(filepath):
                    raise RuntimeError(f"PDF exporter returned a non-existent path: {filepath}")
                return {
                    "ok": True,
                    "path": filepath,
                    "filename": os.path.basename(filepath),
                    "message": f"PDF exported: {os.path.basename(filepath)} | Saved to: {os.path.dirname(filepath)}",
                }
            except Exception as exc:
                report_name = "Statement of Account" if report_id == "statement_of_account" else "A/R aging"
                report_context = "report.statement_of_account.export_pdf" if report_id == "statement_of_account" else "report.ar_aging.export_pdf"
                self._report_failure(f"Could not export {report_name} PDF", context=report_context, exc=exc)
                logging.getLogger("cspm.pdf").exception("%s PDF export failed", report_name)
                return {"ok": False, "message": str(exc), "path": "", "filename": ""}
        return {
            "ok": False,
            "path": "",
            "filename": "",
            "message": f"PDF export is not available for report: {report_id}",
        }

    @Slot(str, result=bool)
    def copyTextToClipboard(self, text):
        try:
            clipboard = QGuiApplication.clipboard()
            if clipboard is None:
                return False
            clipboard.setText(str(text or ""))
            return True
        except Exception as exc:
            self._report_failure("Could not copy report text", context="report.copy", exc=exc)
            return False


    @Slot("QVariantMap", result=dict)
    def getStatementOfAccount(self, payload):
        try:
            req = payload.toVariant() if hasattr(payload, "toVariant") else payload
            return self._excel_repo.statement_of_account_report(req)
        except Exception as exc:
            self._report_failure(
                "Failed to generate Statement of Account",
                context="app.report.statement_of_account.failed",
                exc=exc,
            )
            return {"ok": False, "message": str(exc)}

    @Slot(result=list)
    def listStatementBillingClients(self):
        try:
            return self._excel_repo.list_statement_billing_clients()
        except Exception as exc:
            self._report_failure(
                "Failed to load statement billing clients",
                context="app.report.statement_of_account.billing_clients",
                exc=exc,
            )
            return []

    @Slot(str)
    def requestStatementBillingClients(self, request_id: str) -> None:
        """Load Statement bill-to choices without blocking the QML thread."""

        token = str(request_id or "")
        started = time.perf_counter()

        def _load() -> list:
            return list(self._excel_repo.list_statement_billing_clients() or [])

        def _ready(rows: Any) -> None:
            logging.getLogger("performance.statement").info(
                "statement billing-client choices completed in %.3fs",
                max(0.0, time.perf_counter() - started),
            )
            self.statementBillingClientsReady.emit(token, list(rows or []))

        def _failed(error_info: tuple) -> None:
            _type, exc, _traceback = error_info
            message = str(exc or "Could not load statement billing clients.")
            self._report_failure(
                "Failed to load statement billing clients",
                context="app.report.statement_of_account.billing_clients.async",
                exc=exc,
            )
            self.statementBillingClientsFailed.emit(token, message)

        self._start_background_worker(
            _load,
            name="statement_billing_clients",
            on_result=_ready,
            on_error=_failed,
        )

    @Slot(str, "QVariantMap")
    def requestStatementOfAccount(self, request_id: str, payload) -> None:
        """Prepare a Statement report off-thread and return it to QML by token."""

        token = str(request_id or "")
        source = payload.toVariant() if hasattr(payload, "toVariant") else payload
        request_payload = dict(source or {})
        started = time.perf_counter()

        def _load() -> Dict[str, Any]:
            return dict(self._excel_repo.statement_of_account_report(request_payload) or {})

        def _ready(result: Any) -> None:
            response = dict(result or {})
            logging.getLogger("performance.statement").info(
                "statement report completed in %.3fs client=%s ok=%s",
                max(0.0, time.perf_counter() - started),
                str(request_payload.get("billingClient") or request_payload.get("client") or ""),
                bool(response.get("ok")),
            )
            self.statementOfAccountReady.emit(token, response)

        def _failed(error_info: tuple) -> None:
            _type, exc, _traceback = error_info
            message = str(exc or "Could not prepare statement.")
            self._report_failure(
                "Failed to generate Statement of Account",
                context="app.report.statement_of_account.async",
                exc=exc,
            )
            self.statementOfAccountFailed.emit(token, message)

        self._start_background_worker(
            _load,
            name="statement_of_account",
            on_result=_ready,
            on_error=_failed,
        )

    @Slot(result=list)
    def getExcludedARInvoices(self) -> list:
        return self._settings_data.get("excludedARInvoices", [])

    @Slot("QVariantList", result=bool)
    def setExcludedARInvoices(self, payload) -> bool:
        try:
            val = list(payload) if payload else []
            self._settings_data["excludedARInvoices"] = val
            self._save_settings()
            return True
        except Exception:
            return False

    @Slot(str, result=bool)
    def stampPdfPageNumbers(self, filepath: str) -> bool:
        try:
            from backend.pdf_utils import add_page_numbers_to_pdf
            add_page_numbers_to_pdf(filepath)
            return True
        except Exception as exc:
            self._logger.exception("Failed to stamp PDF page numbers")
            return False

    @Slot(str, str)
    def recordTelemetry(self, action: str, details: str):
        if hasattr(self, "_telemetry") and self._telemetry:
            self._telemetry.record_activity(action, details=details)

    @Slot(str, int, str)
    def recordTelemetryDuration(self, action: str, duration_ms: int, details: str):
        if hasattr(self, "_telemetry") and self._telemetry:
            self._telemetry.record_activity(action, duration_ms=duration_ms, details=details)
