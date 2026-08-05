# 26_patch_lazy_openpyxl.ps1
# Prevents startup hangs by lazy-importing openpyxl and removing schema bootstrap from AppController.__init__.

$BaseRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House"
$ProjectRoot = Join-Path $BaseRoot "__CSPM"

$Stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot ("archive\codegen_backups\" + $Stamp)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Ensure-Dir($p) { if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }

function Backup-IfExists($filePath) {
  if (Test-Path -LiteralPath $filePath) {
    $rel = Resolve-Path -LiteralPath $filePath | ForEach-Object { $_.Path.Substring($ProjectRoot.Length).TrimStart("\") }
    $dest = Join-Path $BackupRoot $rel
    Ensure-Dir (Split-Path -Parent $dest)
    Copy-Item -LiteralPath $filePath -Destination $dest -Force
  }
}

function Write-File($relPath, $content) {
  $full = Join-Path $ProjectRoot $relPath
  Ensure-Dir (Split-Path -Parent $full)
  Backup-IfExists $full
  [System.IO.File]::WriteAllText($full, $content, $utf8NoBom)
  Write-Host ("WROTE: " + $relPath) -ForegroundColor Green
}

# -----------------------------------------
# Patch: src/python/services/excel_service.py
# -----------------------------------------
Write-File "src\python\services\excel_service.py" @'
from __future__ import annotations

from typing import Dict, Any, Optional

from services.paths import AppPaths


HST_RATE = 0.13
HST_MULT = 1.0 + HST_RATE

SHEET_CLIENTS = "Clients"
SHEET_MATTERS = "Matters"
SHEET_PARENTS = "Parents"
SHEET_TIME = "TimeEntries"

TBL_CLIENTS = "tblClients"
TBL_MATTERS = "tblMatters"
TBL_PARENTS = "tblParents"
TBL_TIME = "tblTimeEntries"


class ExcelService:
    """
    NOTE: openpyxl is imported lazily inside methods to avoid startup hangs/crashes.
    """

    def __init__(self, paths: AppPaths):
        self.paths = paths

    def _import_openpyxl(self):
        # Lazy imports
        from openpyxl import Workbook, load_workbook
        from openpyxl.worksheet.table import Table, TableStyleInfo
        from openpyxl.utils.cell import get_column_letter, range_boundaries
        return Workbook, load_workbook, Table, TableStyleInfo, get_column_letter, range_boundaries

    def ensure_workbook(self) -> None:
        Workbook, load_workbook, Table, TableStyleInfo, get_column_letter, range_boundaries = self._import_openpyxl()

        path = self.paths.workbook_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            wb = Workbook()
            try:
                if "Sheet" in wb.sheetnames:
                    ws = wb["Sheet"]
                    wb.remove(ws)
                wb.save(path)
            finally:
                try:
                    wb.close()
                except Exception:
                    pass

    def ensure_schema(self) -> None:
        Workbook, load_workbook, Table, TableStyleInfo, get_column_letter, range_boundaries = self._import_openpyxl()

        self.ensure_workbook()
        path = self.paths.workbook_path()
        wb = None
        try:
            wb = load_workbook(path, keep_vba=True)

            self._ensure_table(
                wb, SHEET_PARENTS, TBL_PARENTS,
                ["ParentID", "ParentName", "DefaultCutPct", "DefaultClientRate", "Notes"],
                Table, TableStyleInfo, get_column_letter
            )
            self._ensure_table(
                wb, SHEET_CLIENTS, TBL_CLIENTS,
                ["ClientID", "ClientName", "Email", "Phone", "Status", "Notes"],
                Table, TableStyleInfo, get_column_letter
            )
            self._ensure_table(
                wb, SHEET_MATTERS, TBL_MATTERS,
                ["MatterID", "ClientID", "MatterName", "ParentID", "DefaultRate", "DefaultCutPct", "Status", "Notes"],
                Table, TableStyleInfo, get_column_letter
            )
            self._ensure_table(
                wb, SHEET_TIME, TBL_TIME,
                [
                    "EntryID", "Date", "ClientID", "MatterID", "ParentID",
                    "Description", "Hours", "ClientRate",
                    "CutPct", "AmountToClient", "AmountToCory",
                    "HST", "TotalInclHST",
                    "RawSeconds", "Status"
                ],
                Table, TableStyleInfo, get_column_letter
            )

            wb.save(path)
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass

    def append_time_entry(self, payload: Dict[str, Any]) -> None:
        Workbook, load_workbook, Table, TableStyleInfo, get_column_letter, range_boundaries = self._import_openpyxl()

        path = self.paths.workbook_path()
        wb = None
        try:
            wb = load_workbook(path, keep_vba=True)
            ws = wb[SHEET_TIME]
            tbl = ws.tables[TBL_TIME]

            headers = self._table_headers(ws, tbl, range_boundaries)
            next_row = self._next_table_row(tbl, range_boundaries)

            hours = float(self._parse_float(payload.get("Hours", 0)) or 0)
            rate = float(self._parse_float(payload.get("ClientRate", 0)) or 0)
            cut = float(self._parse_float(payload.get("CutPct", 0)) or 0)
            if cut > 1.0:
                cut = cut / 100.0

            amount_client = round(hours * rate, 2)
            amount_cory = round(amount_client * (1.0 - cut), 2)
            hst = round(amount_cory * HST_RATE, 2)
            total = round(amount_cory + hst, 2)

            payload2 = dict(payload)
            payload2["AmountToClient"] = amount_client
            payload2["AmountToCory"] = amount_cory
            payload2["HST"] = hst
            payload2["TotalInclHST"] = total
            payload2.setdefault("Status", "WIP")

            for col_ix, header in enumerate(headers, start=1):
                ws.cell(row=next_row, column=col_ix).value = payload2.get(header, "")

            # expand table
            min_col, min_row, max_col, max_row = range_boundaries(tbl.ref)
            new_ref = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{next_row}"
            tbl.ref = new_ref

            wb.save(path)
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass

    # ---- helpers ----
    def _parse_float(self, v: Any) -> Optional[float]:
        s = str(v or "").strip()
        if s == "":
            return None
        s = s.replace(",", "").replace("$", "").replace("%", "")
        try:
            return float(s)
        except Exception:
            return None

    def _ensure_table(self, wb, sheet_name: str, table_name: str, headers: list[str], Table, TableStyleInfo, get_column_letter) -> None:
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            ws = wb.create_sheet(sheet_name)

        # write headers in row 1
        for i, h in enumerate(headers, start=1):
            ws.cell(row=1, column=i).value = h

        if not hasattr(ws, "tables") or table_name not in ws.tables:
            for c in range(1, len(headers) + 1):
                ws.cell(row=2, column=c).value = None

            ref = f"{get_column_letter(1)}1:{get_column_letter(len(headers))}2"
            tbl = Table(displayName=table_name, ref=ref)
            tbl.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium9",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=False,
            )
            ws.add_table(tbl)

    def _table_headers(self, ws, tbl, range_boundaries) -> list[str]:
        min_col, min_row, max_col, max_row = range_boundaries(tbl.ref)
        headers = []
        for c in range(min_col, max_col + 1):
            headers.append(str(ws.cell(row=min_row, column=c).value or "").strip())
        return headers

    def _next_table_row(self, tbl, range_boundaries) -> int:
        min_col, min_row, max_col, max_row = range_boundaries(tbl.ref)
        return max_row + 1
'@

# -----------------------------------------
# Patch: src/python/backend/app_controller.py
# Remove ensure_schema() call from __init__, add ensureSchema() slot.
# -----------------------------------------
Write-File "src\python\backend\app_controller.py" @'
from __future__ import annotations

import time
from typing import Any, Dict, List

from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer

from services.paths import AppPaths
from services.theme_service import ThemeService
from services.state_service import StateService
from services.lists_service import ListsService
from services.excel_service import ExcelService
from services.backup_service import BackupService
from services.workspace_dump_service import WorkspaceDumpService
from utils.time_utils import seconds_to_hms


class AppController(QObject):
    toast = Signal(str)
    error = Signal(str)

    themeChanged = Signal()
    timerChanged = Signal()
    listsChanged = Signal()

    def __init__(self, paths: AppPaths):
        super().__init__()
        self.paths = paths

        self.theme_svc = ThemeService(paths)
        self.state_svc = StateService(paths)
        self.lists_svc = ListsService(paths)
        self.excel_svc = ExcelService(paths)
        self.backup_svc = BackupService(paths)
        self.dump_svc = WorkspaceDumpService(paths)

        self._lists = self.lists_svc.load()

        self._timer_running = False
        self._start_epoch = 0.0
        self._elapsed = 0.0

        self._qtimer = QTimer(self)
        self._qtimer.setInterval(50)
        self._qtimer.timeout.connect(self._tick)

        # IMPORTANT: Do not touch openpyxl on startup to avoid import-time hangs.
        # Schema can be ensured on demand via ensureSchema().
        self.toast.emit("App loaded. Excel schema will initialize on first save or when requested.")

    # ---- Theme ----
    @Property("QVariantMap", notify=themeChanged)
    def theme(self) -> Dict[str, Any]:
        return self.theme_svc.current_theme()

    @Property("QStringList", constant=True)
    def themeNames(self):
        return self.theme_svc.theme_names()

    @Slot(str)
    def setTheme(self, name: str) -> None:
        try:
            self.theme_svc.set_theme(name)
            self.themeChanged.emit()
        except Exception as e:
            self.error.emit(str(e))

    # ---- Lists ----
    @Property("QStringList", notify=listsChanged)
    def clients(self) -> List[str]:
        return list(self._lists.get("clients", []))

    @Property("QStringList", notify=listsChanged)
    def matters(self) -> List[str]:
        return list(self._lists.get("matters", []))

    @Property("QStringList", notify=listsChanged)
    def parents(self) -> List[str]:
        return list(self._lists.get("parents", []))

    @Slot(str)
    def addClient(self, value: str) -> None:
        self._lists = self.lists_svc.add_value("clients", value)
        self.listsChanged.emit()

    @Slot(str)
    def addMatter(self, value: str) -> None:
        self._lists = self.lists_svc.add_value("matters", value)
        self.listsChanged.emit()

    @Slot(str)
    def addParent(self, value: str) -> None:
        self._lists = self.lists_svc.add_value("parents", value)
        self.listsChanged.emit()

    # ---- Timer ----
    @Property(bool, notify=timerChanged)
    def timerRunning(self) -> bool:
        return self._timer_running

    @Property(float, notify=timerChanged)
    def elapsedSeconds(self) -> float:
        return float(self._elapsed)

    @Property(str, notify=timerChanged)
    def timerLabel(self) -> str:
        prefix = "Running" if self._timer_running else "Ready"
        return f"{prefix} ({seconds_to_hms(self._elapsed)})"

    @Slot()
    def toggleTimer(self) -> None:
        if not self._timer_running:
            self._timer_running = True
            self._start_epoch = time.time() - self._elapsed
            self._qtimer.start()
        else:
            self._timer_running = False
            self._qtimer.stop()
            self._elapsed = time.time() - self._start_epoch
        self.timerChanged.emit()

    def _tick(self) -> None:
        if not self._timer_running:
            return
        self._elapsed = time.time() - self._start_epoch
        self.timerChanged.emit()

    # ---- Excel schema on demand ----
    @Slot()
    def ensureSchema(self) -> None:
        try:
            self.excel_svc.ensure_schema()
            self.toast.emit("Excel schema ensured.")
        except Exception as e:
            self.error.emit(str(e))

    # ---- Actions ----
    @Slot()
    def backupWorkbook(self) -> None:
        try:
            out = self.backup_svc.backup_workbook_if_exists(force=True)
            if out:
                self.toast.emit(f"Backup created: {out.name}")
            else:
                self.toast.emit("No workbook found to back up.")
        except Exception as e:
            self.error.emit(str(e))

    @Slot()
    def dumpWorkspace(self) -> None:
        try:
            out = self.dump_svc.dump_workspace()
            self.toast.emit(f"Workspace dump saved: {out.name}")
        except Exception as e:
            self.error.emit(str(e))

    @Slot("QVariantMap")
    def saveTimeEntry(self, payload: Dict[str, Any]) -> None:
        try:
            # Ensure schema right before writing
            self.excel_svc.ensure_schema()

            self.backup_svc.backup_workbook_if_exists(force=True)
            self.excel_svc.append_time_entry(dict(payload))
            self.toast.emit("Time entry saved to Excel.")
        except PermissionError:
            self.error.emit("Workbook locked (likely open in Excel). Close it and try again.")
        except Exception as e:
            self.error.emit(str(e))
'@

Write-Host ""
Write-Host "Lazy-openpyxl patch complete. Backups stored at:" -ForegroundColor Cyan
Write-Host ("  " + $BackupRoot) -ForegroundColor Yellow