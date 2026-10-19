from __future__ import annotations

from copy import copy
from datetime import date, datetime, timedelta
from html import escape as xml_escape
import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4
import zipfile

import openpyxl
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.table import Table, TableStyleInfo

from domain import schema_constants as sc
from services.paths import AppPaths

logger = logging.getLogger(__name__)

LEGACY_DOCKETS_SHEET = "Dockets"
LEGACY_DOCKETS_TABLE = "Table1_1"
LEGACY_DOCKETS_HEADERS: tuple[str, ...] = (
    "Date",
    "Client",
    "Sub-Client2",
    "Description",
    "Time (in hrs)",
    "Hourly Rate/Flat Fee",
    "Percentage",
    "Amount to CS",
    "Total Inclusive of HST",
    "Invoice",
    "Matter_ID",
    "RawSeconds",
    "EntryType",
)
LEGACY_DOCKETS_COLUMNS = LEGACY_DOCKETS_HEADERS
LEGACY_DATE_NUMBER_FORMAT = "[$-409]mmmm\\ d\\,\\ yyyy;@"
LEGACY_PERCENT_NUMBER_FORMAT = "0%"
LEGACY_CURRENCY_NUMBER_FORMAT = "$#,##0.00"
EXCEL_EPOCH_DATE = date(1899, 12, 30)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "nan", "(blank)", "(none)"}:
        return ""
    return re.sub(r"\s+", " ", text)


def _norm_key(value: Any) -> str:
    return _clean_text(value).casefold()


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else default
    text = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
    if not text:
        return default
    try:
        parsed = float(text)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _parse_datetime_midnight(value: Any) -> datetime:
    if isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, 0, 0, 0)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, 0, 0, 0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20000 <= float(value) <= 100000:
            dt_d = EXCEL_EPOCH_DATE + timedelta(days=int(round(float(value))))
            return datetime(dt_d.year, dt_d.month, dt_d.day, 0, 0, 0)
    text = _clean_text(value)
    if text:
        if re.fullmatch(r"\d{5}(?:\.\d+)?", text):
            serial_val = float(text)
            if 20000 <= serial_val <= 100000:
                dt_d = EXCEL_EPOCH_DATE + timedelta(days=int(round(serial_val)))
                return datetime(dt_d.year, dt_d.month, dt_d.day, 0, 0, 0)
        for candidate in (text[:10], text):
            try:
                dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                return datetime(dt.year, dt.month, dt.day, 0, 0, 0)
            except ValueError:
                pass
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y"):
            try:
                dt = datetime.strptime(text, fmt)
                return datetime(dt.year, dt.month, dt.day, 0, 0, 0)
            except ValueError:
                pass
    today = date.today()
    return datetime(today.year, today.month, today.day, 0, 0, 0)


def _iso_date_str(value: Any) -> str:
    return _parse_datetime_midnight(value).strftime("%Y-%m-%d")


def _normalize_share_fraction(value: Any) -> int | float:
    raw = _parse_float(value, default=100.0)
    if raw <= 0:
        return 1
    if raw > 1.0:
        frac = round(raw / 100.0, 4)
    else:
        frac = round(raw, 4)
    if abs(frac - 1.0) < 1e-6:
        return 1
    return frac


def _format_rate_number(value: Any) -> int | float:
    rate = round(_parse_float(value, default=0.0), 2)
    if rate.is_integer():
        return int(rate)
    return rate


def _format_xml_number(value: Any) -> str:
    num = float(value or 0.0)
    if not math.isfinite(num):
        return "0"
    if num.is_integer():
        return str(int(num))
    return str(round(num, 6)).rstrip("0").rstrip(".")


class LegacyDocketsSyncService:
    """Auto-sync saved/updated CSPM time entries to legacy Dockets.xlsm (Dockets -> Table1_1)."""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def _sync_map_path(self) -> Path:
        return self.paths.state_dir() / "legacy_dockets_sync_map.json"

    def _pending_queue_path(self) -> Path:
        return self.paths.state_dir() / "legacy_dockets_pending_sync.json"

    def _pending_conflicts_path(self) -> Path:
        return self.paths.state_dir() / "legacy_dockets_pending_conflicts.json"

    def _load_json_state(self, path: Path) -> dict[str, Any]:
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.debug("[legacy_dockets_sync] Could not load %s: %s", path, exc)
        return {}

    def _save_json_state(self, path: Path, payload: Mapping[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            os.replace(str(tmp_path), str(path))
        except Exception as exc:
            logger.debug("[legacy_dockets_sync] Could not persist %s: %s", path, exc)

    @staticmethod
    def _close_workbook(workbook: Any) -> None:
        if workbook is None:
            return
        for attr in ("vba_archive", "_archive"):
            try:
                archive = getattr(workbook, attr, None)
                if archive is not None:
                    fp = getattr(archive, "fp", None)
                    if fp is not None and not getattr(fp, "closed", False):
                        archive.close()
                    archive.fp = None
                    setattr(workbook, attr, None)
            except Exception:
                pass
        try:
            workbook.close()
        except Exception:
            pass

    @staticmethod
    def _normalize_xlsm_content_types(saved_path: Path, target_path: Path) -> None:
        if target_path.suffix.lower() != ".xlsm":
            return
        if not saved_path.exists() or not zipfile.is_zipfile(saved_path):
            return
        macro_content_type = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
        workbook_part = 'PartName="/xl/workbook.xml"'
        temp_zip_path = saved_path.with_name(saved_path.name + ".ziptmp")
        changed = False
        try:
            with zipfile.ZipFile(saved_path, "r") as src, zipfile.ZipFile(
                temp_zip_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as dst:
                for info in src.infolist():
                    data = src.read(info.filename)
                    if info.filename == "[Content_Types].xml":
                        text = data.decode("utf-8")
                        next_text = re.sub(
                            rf'({re.escape(workbook_part)}\s+ContentType=")[^"]+(")',
                            rf"\1{macro_content_type}\2",
                            text,
                            count=1,
                        )
                        if next_text != text:
                            data = next_text.encode("utf-8")
                            changed = True
                    dst.writestr(info, data)
            if changed:
                os.replace(str(temp_zip_path), str(saved_path))
            else:
                temp_zip_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("[legacy_dockets_sync] ContentType normalization warning: %s", exc)
            temp_zip_path.unlink(missing_ok=True)

    @staticmethod
    def _is_excel_lock_present(target_path: Path) -> bool:
        lock_file = target_path.parent / f"~${target_path.name}"
        return lock_file.exists()

    @staticmethod
    def build_legacy_row_payload(
        entry_row: Mapping[str, Any],
        *,
        client_name: str = "",
        parent_name: str = "",
        sub_client_name: str = "",
        matter_number: str = "",
        is_fee_entry: bool = False,
    ) -> dict[str, Any]:
        """Build normalized 13-column representation for Table1_1."""
        clean_client = _clean_text(client_name)
        clean_parent = _clean_text(parent_name)
        clean_sub = _clean_text(sub_client_name)

        is_leviathan_parent = "leviathan" in clean_parent.casefold()
        if clean_parent and not is_leviathan_parent and _norm_key(clean_parent) != _norm_key(clean_client):
            legacy_client = clean_parent
            legacy_sub_client = clean_sub or clean_client
        else:
            legacy_client = clean_client or clean_parent
            legacy_sub_client = clean_sub if (clean_sub and _norm_key(clean_sub) != _norm_key(legacy_client)) else ""

        raw_seconds = int(round(_parse_float(entry_row.get(sc.COL_TIME_SECONDS), 0.0)))
        hours_val = round(_parse_float(entry_row.get(sc.COL_TIME_HOURS), 0.0), 2)
        if hours_val <= 0.0 and raw_seconds > 0 and not is_fee_entry:
            hours_val = round(math.ceil(((raw_seconds / 3600.0) * 10.0) - 1e-9) / 10.0, 2)
        if raw_seconds <= 0 and hours_val > 0:
            raw_seconds = int(round(hours_val * 3600.0))

        rate_val = _parse_float(entry_row.get(sc.COL_TIME_RATE), 0.0)
        net_val = round(_parse_float(entry_row.get(sc.COL_TIME_NET), 0.0), 2)
        total_val = round(_parse_float(entry_row.get(sc.COL_TIME_TOTAL), 0.0), 2)
        gross_val = round(_parse_float(entry_row.get(sc.COL_TIME_GROSS), 0.0), 2)

        lock_audit = _clean_text(entry_row.get(sc.COL_TIME_LOCK_AUDIT))
        flat_fee = bool(
            is_fee_entry
            or "entrytype:fee" in lock_audit.casefold()
            or "flat" in lock_audit.casefold()
            or (hours_val == 0.0 and (net_val != 0.0 or gross_val != 0.0))
        )
        if flat_fee and rate_val == 0.0:
            rate_val = gross_val if gross_val != 0.0 else net_val

        pct_val = _normalize_share_fraction(entry_row.get(sc.COL_TIME_SHARE_PCT, 100.0))
        if net_val == 0.0 and hours_val > 0.0 and rate_val > 0.0:
            net_val = round(hours_val * rate_val * float(pct_val), 2)
        if total_val == 0.0 and net_val != 0.0:
            hst_val = round(_parse_float(entry_row.get(sc.COL_TIME_HST), net_val * 0.13), 2)
            total_val = round(net_val + hst_val, 2)

        inv_ref = _clean_text(entry_row.get(sc.COL_TIME_INVOICE_REF))
        resolved_matter_num = _clean_text(matter_number) or _clean_text(entry_row.get(sc.COL_TIME_MATTER_ID))
        desc_text = _clean_text(entry_row.get(sc.COL_TIME_DESC))

        return {
            "entryId": _clean_text(entry_row.get(sc.COL_TIME_ENTRY_ID)),
            "Date": _iso_date_str(entry_row.get(sc.COL_TIME_DATE)),
            "Client": legacy_client,
            "Sub-Client2": legacy_sub_client if legacy_sub_client else None,
            "Description": desc_text,
            "Time (in hrs)": hours_val,
            "Hourly Rate/Flat Fee": _format_rate_number(rate_val),
            "Percentage": pct_val,
            "Amount to CS": net_val,
            "Total Inclusive of HST": total_val,
            "Invoice": inv_ref if inv_ref else None,
            "Matter_ID": resolved_matter_num,
            "RawSeconds": int(raw_seconds),
            "EntryType": "Flat Fee" if flat_fee else "Hourly",
        }

    @staticmethod
    def _signature_from_payload(payload: Mapping[str, Any]) -> tuple[str, str, int, str, float]:
        return (
            _norm_key(payload.get("Matter_ID")),
            _iso_date_str(payload.get("Date")),
            int(round(_parse_float(payload.get("RawSeconds"), 0.0))),
            _norm_key(payload.get("Description")),
            round(_parse_float(payload.get("Time (in hrs)"), 0.0), 2),
        )

    @staticmethod
    def _ensure_table1_1(ws: Any) -> tuple[Any, int, int, int, int]:
        table = ws.tables.get(LEGACY_DOCKETS_TABLE)
        if table is None and len(ws.tables) == 1:
            # Fallback if a single table exists on Dockets sheet under another name
            only_name = next(iter(ws.tables.keys()))
            if only_name == LEGACY_DOCKETS_TABLE:
                table = ws.tables[only_name]

        if table is None:
            # Initialize headers on row 1 if empty
            first_row_vals = [ws.cell(1, col_idx).value for col_idx in range(1, len(LEGACY_DOCKETS_HEADERS) + 1)]
            if not any(_clean_text(v) for v in first_row_vals):
                for col_idx, header in enumerate(LEGACY_DOCKETS_HEADERS, start=1):
                    ws.cell(1, col_idx).value = header
            max_r = max(2, ws.max_row)
            ref = f"A1:{get_column_letter(len(LEGACY_DOCKETS_HEADERS))}{max_r}"
            table = Table(displayName=LEGACY_DOCKETS_TABLE, ref=ref)
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=False,
            )
            ws.add_table(table)

        min_col, min_row, max_col, max_row = range_boundaries(table.ref)
        return table, int(min_col), int(min_row), int(max_col), int(max_row)

    @staticmethod
    def _row_is_blank(ws: Any, row_idx: int, min_col: int, max_col: int) -> bool:
        for col_idx in range(min_col, max_col + 1):
            val = ws.cell(row_idx, col_idx).value
            if val is not None and _clean_text(val) != "":
                return False
        return True

    @classmethod
    def _find_matching_row(
        cls,
        ws: Any,
        min_col: int,
        header_row: int,
        max_row: int,
        col_map: Mapping[str, int],
        target_sig: tuple[str, str, int, str, float],
        preferred_row_idx: int | None = None,
    ) -> int | None:
        t_matter, t_date, t_seconds, t_desc, t_hours = target_sig
        if not t_matter and not t_desc:
            return None

        col_date = col_map.get("date", min_col)
        col_desc = col_map.get("description", min_col + 3)
        col_hours = col_map.get("time (in hrs)", min_col + 4)
        col_matter = col_map.get("matter_id", min_col + 10)
        col_seconds = col_map.get("rawseconds", min_col + 11)

        def _row_matches(r_idx: int) -> bool:
            if r_idx <= header_row or r_idx > max_row:
                return False
            r_matter = _norm_key(ws.cell(r_idx, col_matter).value)
            if r_matter != t_matter:
                return False
            raw_date = ws.cell(r_idx, col_date).value
            if raw_date is None or _clean_text(raw_date) == "":
                return False
            r_date = _iso_date_str(raw_date)
            if r_date != t_date:
                return False
            r_desc = _norm_key(ws.cell(r_idx, col_desc).value)
            if r_desc != t_desc:
                return False
            r_sec_val = ws.cell(r_idx, col_seconds).value
            r_sec = int(round(_parse_float(r_sec_val, -1.0))) if r_sec_val not in (None, "") else -1
            if r_sec >= 0 and t_seconds >= 0 and r_sec == t_seconds:
                return True
            r_hrs = round(_parse_float(ws.cell(r_idx, col_hours).value, -1.0), 2)
            return abs(r_hrs - t_hours) < 0.011

        if preferred_row_idx is not None and _row_matches(preferred_row_idx):
            return preferred_row_idx

        # Scan bottom-up since recent dockets are at the bottom of Table1_1
        for r_idx in range(max_row, header_row, -1):
            if _row_matches(r_idx):
                return r_idx
        return None

    @classmethod
    def _find_rows_by_date_and_matter(
        cls,
        ws: Any,
        min_col: int,
        header_row: int,
        max_row: int,
        col_map: Mapping[str, int],
        matter_id: Any,
        date_val: Any,
    ) -> list[int]:
        t_matter = _norm_key(matter_id)
        t_date = _iso_date_str(date_val) if _clean_text(date_val) else ""
        if not t_matter or not t_date:
            return []
        col_date = col_map.get("date", min_col)
        col_matter = col_map.get("matter_id", min_col + 10)
        matches: list[int] = []
        for r_idx in range(header_row + 1, max_row + 1):
            r_matter = _norm_key(ws.cell(r_idx, col_matter).value)
            if r_matter != t_matter:
                continue
            raw_date = ws.cell(r_idx, col_date).value
            if raw_date is None or _clean_text(raw_date) == "":
                continue
            if _iso_date_str(raw_date) == t_date:
                matches.append(int(r_idx))
        return matches

    @classmethod
    def _extract_row_details(
        cls,
        ws: Any,
        row_idx: int,
        min_col: int,
        col_map: Mapping[str, int],
    ) -> dict[str, Any]:
        c_date = col_map.get("date", min_col)
        c_client = col_map.get("client", min_col + 1)
        c_sub = col_map.get("sub-client2") or col_map.get("sub-client") or (min_col + 2)
        c_desc = col_map.get("description", min_col + 3)
        c_hours = col_map.get("time (in hrs)", min_col + 4)
        c_rate = col_map.get("hourly rate/flat fee", min_col + 5)
        c_pct = col_map.get("percentage", min_col + 6)
        c_amt = col_map.get("amount to cs", min_col + 7)
        c_total = col_map.get("total inclusive of hst", min_col + 8)
        c_inv = col_map.get("invoice", min_col + 9)
        c_matter = col_map.get("matter_id", min_col + 10)
        c_sec = col_map.get("rawseconds", min_col + 11)
        c_type = col_map.get("entrytype", min_col + 12)

        raw_date = ws.cell(row_idx, c_date).value
        date_str = _iso_date_str(raw_date) if (raw_date is not None and _clean_text(raw_date) != "") else ""
        hours_val = round(_parse_float(ws.cell(row_idx, c_hours).value, 0.0), 2)
        raw_sec_val = ws.cell(row_idx, c_sec).value
        raw_seconds = int(round(_parse_float(raw_sec_val, 0.0)))
        if raw_seconds <= 0 and hours_val > 0:
            raw_seconds = int(round(hours_val * 3600.0))
        inv_text = _clean_text(ws.cell(row_idx, c_inv).value)

        return {
            "row": int(row_idx),
            "rowNumber": int(row_idx),
            "Date": date_str,
            "Client": _clean_text(ws.cell(row_idx, c_client).value),
            "Sub-Client2": _clean_text(ws.cell(row_idx, c_sub).value),
            "Description": _clean_text(ws.cell(row_idx, c_desc).value),
            "Time (in hrs)": hours_val,
            "Hourly Rate/Flat Fee": _format_rate_number(ws.cell(row_idx, c_rate).value),
            "Percentage": _normalize_share_fraction(ws.cell(row_idx, c_pct).value),
            "Amount to CS": round(_parse_float(ws.cell(row_idx, c_amt).value, 0.0), 2),
            "Total Inclusive of HST": round(_parse_float(ws.cell(row_idx, c_total).value, 0.0), 2),
            "Invoice": inv_text,
            "isBilled": bool(inv_text),
            "Matter_ID": _clean_text(ws.cell(row_idx, c_matter).value),
            "RawSeconds": int(raw_seconds),
            "EntryType": _clean_text(ws.cell(row_idx, c_type).value) or "Hourly",
        }

    @classmethod
    def _find_unique_matter_date_row(
        cls,
        ws: Any,
        min_col: int,
        header_row: int,
        max_row: int,
        col_map: Mapping[str, int],
        matter_id: Any,
        date_val: Any,
    ) -> int | None:
        matches = cls._find_rows_by_date_and_matter(
            ws, min_col, header_row, max_row, col_map, matter_id, date_val
        )
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _copy_row_styles(ws: Any, src_row: int, dst_row: int, min_col: int, max_col: int) -> None:
        if src_row == dst_row or src_row < 1:
            return
        for col_idx in range(min_col, max_col + 1):
            src_cell = ws.cell(src_row, col_idx)
            dst_cell = ws.cell(dst_row, col_idx)
            if src_cell.has_style:
                dst_cell.font = copy(src_cell.font)
                dst_cell.fill = copy(src_cell.fill)
                dst_cell.border = copy(src_cell.border)
                dst_cell.alignment = copy(src_cell.alignment)
                dst_cell.number_format = src_cell.number_format

    @staticmethod
    def _resolve_formula_or_value(
        ws: Any,
        template_row: int | None,
        target_row: int,
        col_idx: int,
        numeric_value: float,
        is_flat_fee: bool,
    ) -> Any:
        existing_val = ws.cell(target_row, col_idx).value
        if isinstance(existing_val, str) and existing_val.startswith("=") and not is_flat_fee:
            return existing_val

        if template_row is not None and template_row >= 2 and template_row != target_row and not is_flat_fee:
            tmpl_val = ws.cell(template_row, col_idx).value
            if isinstance(tmpl_val, str) and tmpl_val.startswith("="):
                if "[@" in tmpl_val:
                    return tmpl_val
                col_letter = get_column_letter(col_idx)
                try:
                    return Translator(
                        tmpl_val, origin=f"{col_letter}{template_row}"
                    ).translate_formula(f"{col_letter}{target_row}")
                except Exception:
                    return round(float(numeric_value), 2)

        return round(float(numeric_value), 2)

    @staticmethod
    def _normalize_resolution_mode(resolution_mode: str | None) -> str | None:
        if not resolution_mode:
            return None
        key = _clean_text(resolution_mode).casefold().replace("-", "_").replace(" ", "_")
        if key in {"overwrite", "overwrite_existing", "overwrite_existing_row", "replace"}:
            return "overwrite"
        if key in {"append", "append_new", "append_as_separate_new_row", "separate"}:
            return "append"
        if key in {"combine", "add_time", "combine_add_time", "combine_existing", "merge"}:
            return "combine"
        if key in {"skip", "skip_dockets", "save_in_cspm_only", "cspm_only", "ignore"}:
            return "skip"
        raise ValueError(f"Unsupported Dockets.xlsm conflict resolution mode: {resolution_mode}")

    def _apply_upsert_to_workbook(
        self,
        workbook_path: Path,
        current_payload: Mapping[str, Any],
        previous_payload: Mapping[str, Any] | None,
        is_update: bool,
        sync_map: dict[str, Any],
        *,
        resolution_mode: str | None = None,
        target_row: int | None = None,
        confirm_billed_overwrite: bool = True,
    ) -> dict[str, Any]:
        normalized_mode = self._normalize_resolution_mode(resolution_mode)
        if normalized_mode == "skip":
            return {
                "ok": True,
                "status": "SKIPPED",
                "conflict": False,
                "action": "skipped",
                "resolutionMode": "skip",
                "workbookPath": str(workbook_path),
            }

        if self._is_excel_lock_present(workbook_path):
            raise PermissionError(f"Excel lock file ~${workbook_path.name} is present.")

        wb = None
        temp_path = workbook_path.with_name(f".{workbook_path.name}.{uuid4().hex}.tmp")
        try:
            keep_vba = workbook_path.suffix.lower() == ".xlsm"
            wb = openpyxl.load_workbook(str(workbook_path), keep_vba=keep_vba)
            if LEGACY_DOCKETS_SHEET not in wb.sheetnames:
                ws = wb.create_sheet(LEGACY_DOCKETS_SHEET)
            else:
                ws = wb[LEGACY_DOCKETS_SHEET]

            table, min_col, header_row, max_col, max_row = self._ensure_table1_1(ws)
            if max_col - min_col + 1 < len(LEGACY_DOCKETS_HEADERS):
                max_col = min_col + len(LEGACY_DOCKETS_HEADERS) - 1

            col_map: dict[str, int] = {}
            for col_idx in range(min_col, max_col + 1):
                header_text = _clean_text(ws.cell(header_row, col_idx).value)
                if header_text:
                    col_map[header_text.casefold()] = col_idx
            for offset, default_header in enumerate(LEGACY_DOCKETS_HEADERS):
                col_idx = min_col + offset
                if default_header.casefold() not in col_map:
                    col_map[default_header.casefold()] = col_idx
                if not _clean_text(ws.cell(header_row, col_idx).value):
                    ws.cell(header_row, col_idx).value = default_header

            c_date = col_map["date"]
            c_client = col_map["client"]
            c_sub = col_map.get("sub-client2") or col_map.get("sub-client") or (min_col + 2)
            c_desc = col_map["description"]
            c_hours = col_map["time (in hrs)"]
            c_rate = col_map["hourly rate/flat fee"]
            c_pct = col_map["percentage"]
            c_amt = col_map["amount to cs"]
            c_total = col_map["total inclusive of hst"]
            c_inv = col_map["invoice"]
            c_matter = col_map["matter_id"]
            c_sec = col_map["rawseconds"]
            c_type = col_map["entrytype"]

            wb_key = str(workbook_path.resolve()).casefold()
            wb_entries = sync_map.setdefault(wb_key, {})
            entry_id = _clean_text(current_payload.get("entryId"))
            mapped_info = wb_entries.get(entry_id) if (entry_id and isinstance(wb_entries, dict)) else None
            preferred_row = int(mapped_info["row"]) if isinstance(mapped_info, dict) and mapped_info.get("row") else None

            date_matter_rows = self._find_rows_by_date_and_matter(
                ws,
                min_col,
                header_row,
                max_row,
                col_map,
                current_payload.get("Matter_ID"),
                current_payload.get("Date"),
            )

            prior_matched_row: int | None = None
            prior_snapshot_modified_externally = False
            if (
                preferred_row is not None
                and header_row < preferred_row <= max_row
                and not self._row_is_blank(ws, preferred_row, min_col, max_col)
            ):
                matches_saved = False
                if isinstance(mapped_info, dict) and mapped_info.get("signature"):
                    saved_sig = tuple(mapped_info["signature"])
                    if len(saved_sig) == 5:
                        matches_saved = (
                            self._find_matching_row(
                                ws,
                                min_col,
                                header_row,
                                max_row,
                                col_map,
                                saved_sig,
                                preferred_row_idx=preferred_row,
                            )
                            == preferred_row
                        )
                matches_prev = False
                if previous_payload is not None:
                    prev_sig = self._signature_from_payload(previous_payload)
                    matches_prev = (
                        self._find_matching_row(
                            ws,
                            min_col,
                            header_row,
                            max_row,
                            col_map,
                            prev_sig,
                            preferred_row_idx=preferred_row,
                        )
                        == preferred_row
                    )
                matches_curr = (
                    self._find_matching_row(
                        ws,
                        min_col,
                        header_row,
                        max_row,
                        col_map,
                        self._signature_from_payload(current_payload),
                        preferred_row_idx=preferred_row,
                    )
                    == preferred_row
                )
                prior_matched_row = preferred_row
                if not (matches_saved or matches_prev or matches_curr):
                    prior_snapshot_modified_externally = True
            elif previous_payload is not None:
                prev_sig = self._signature_from_payload(previous_payload)
                prior_matched_row = self._find_matching_row(
                    ws, min_col, header_row, max_row, col_map, prev_sig, preferred_row_idx=preferred_row
                )

            candidate_rows: list[int] = []
            if prior_matched_row is not None and header_row < prior_matched_row <= max_row:
                candidate_rows.append(int(prior_matched_row))
            for r_idx in date_matter_rows:
                if r_idx not in candidate_rows:
                    candidate_rows.append(int(r_idx))
            if previous_payload is not None:
                for r_idx in self._find_rows_by_date_and_matter(
                    ws,
                    min_col,
                    header_row,
                    max_row,
                    col_map,
                    previous_payload.get("Matter_ID"),
                    previous_payload.get("Date"),
                ):
                    if r_idx not in candidate_rows:
                        candidate_rows.append(int(r_idx))

            existing_rows_details = [
                self._extract_row_details(ws, r_idx, min_col, col_map) for r_idx in candidate_rows
            ]
            any_billed = any(bool(item.get("isBilled")) for item in existing_rows_details)

            effective_payload: dict[str, Any] = dict(current_payload)
            target_row_idx: int | None = None

            if normalized_mode is None:
                if not candidate_rows:
                    # Case A — No Conflict (Zero Matching Rows on (Date, Matter_ID)) -> Quietly append
                    target_row_idx = None
                elif (
                    is_update
                    and isinstance(mapped_info, dict)
                    and len(candidate_rows) == 1
                    and not prior_snapshot_modified_externally
                    and not any_billed
                ):
                    # Unambiguous in-place update of an entry synced by CSPM with no external edits or billing lock
                    target_row_idx = int(candidate_rows[0])
                else:
                    # Case B — Potential Conflict Detected -> Do NOT overwrite or append silently
                    if any_billed:
                        conflict_reason = "ALREADY_BILLED"
                    elif prior_snapshot_modified_externally:
                        conflict_reason = "EXTERNAL_MODIFICATION"
                    elif len(candidate_rows) > 1:
                        conflict_reason = "MULTIPLE_MATCHING_ROWS"
                    else:
                        conflict_reason = "EXISTING_DATE_MATTER_ROW"
                    return {
                        "ok": True,
                        "status": "CONFLICT",
                        "conflict": True,
                        "action": "conflict",
                        "conflictReason": conflict_reason,
                        "workbookPath": str(workbook_path),
                        "incomingEntry": dict(current_payload),
                        "existingRows": existing_rows_details,
                        "selectedTargetRow": int(candidate_rows[0]),
                    }
            elif normalized_mode == "append":
                target_row_idx = None
            elif normalized_mode == "overwrite":
                if target_row is not None and header_row < int(target_row) <= max_row:
                    target_row_idx = int(target_row)
                elif candidate_rows:
                    target_row_idx = int(candidate_rows[0])
                else:
                    target_row_idx = None

                if target_row_idx is not None:
                    existing_inv_on_target = _clean_text(ws.cell(target_row_idx, c_inv).value)
                    if existing_inv_on_target and not confirm_billed_overwrite:
                        return {
                            "ok": False,
                            "status": "CONFLICT",
                            "conflict": True,
                            "requiresBilledConfirmation": True,
                            "existingInvoice": existing_inv_on_target,
                            "row": int(target_row_idx),
                            "workbookPath": str(workbook_path),
                            "incomingEntry": dict(current_payload),
                            "existingRows": existing_rows_details,
                            "message": (
                                f"Row {target_row_idx} in Dockets.xlsm is already billed "
                                f"(Invoice {existing_inv_on_target}). Please confirm before overwriting."
                            ),
                        }
            elif normalized_mode == "combine":
                if target_row is not None and header_row < int(target_row) <= max_row:
                    target_row_idx = int(target_row)
                elif candidate_rows:
                    target_row_idx = int(candidate_rows[0])
                else:
                    target_row_idx = None

                if target_row_idx is not None:
                    existing_details = self._extract_row_details(ws, target_row_idx, min_col, col_map)
                    existing_sec = int(existing_details.get("RawSeconds") or 0)
                    existing_hrs = float(existing_details.get("Time (in hrs)") or 0.0)
                    existing_desc = _clean_text(existing_details.get("Description"))
                    existing_inv = _clean_text(existing_details.get("Invoice"))
                    existing_rate = _parse_float(existing_details.get("Hourly Rate/Flat Fee"), 0.0)
                    existing_pct = _normalize_share_fraction(existing_details.get("Percentage", 1))

                    incoming_sec = int(round(_parse_float(current_payload.get("RawSeconds"), 0.0)))
                    incoming_hrs = round(_parse_float(current_payload.get("Time (in hrs)"), 0.0), 2)
                    if incoming_sec <= 0 and incoming_hrs > 0:
                        incoming_sec = int(round(incoming_hrs * 3600.0))
                    if incoming_hrs <= 0 and incoming_sec > 0:
                        incoming_hrs = round(math.ceil(((incoming_sec / 3600.0) * 10.0) - 1e-9) / 10.0, 2)
                    incoming_desc = _clean_text(current_payload.get("Description"))

                    combined_sec = int(existing_sec + incoming_sec)
                    combined_hrs = round(existing_hrs + incoming_hrs, 2)
                    if combined_hrs <= 0 and combined_sec > 0:
                        combined_hrs = round(math.ceil(((combined_sec / 3600.0) * 10.0) - 1e-9) / 10.0, 2)

                    if existing_desc and incoming_desc:
                        if _norm_key(existing_desc) == _norm_key(incoming_desc):
                            merged_desc = existing_desc
                        else:
                            merged_desc = f"{existing_desc}; {incoming_desc}"
                    else:
                        merged_desc = existing_desc or incoming_desc

                    rate_num = _parse_float(current_payload.get("Hourly Rate/Flat Fee"), existing_rate) or existing_rate
                    pct_num = float(_normalize_share_fraction(current_payload.get("Percentage", existing_pct)))
                    amt_combined = round(combined_hrs * rate_num * pct_num, 2)
                    total_combined = round(amt_combined * 1.13, 2)

                    effective_payload["Description"] = merged_desc
                    effective_payload["Time (in hrs)"] = combined_hrs
                    effective_payload["RawSeconds"] = combined_sec
                    effective_payload["Hourly Rate/Flat Fee"] = _format_rate_number(rate_num)
                    effective_payload["Percentage"] = pct_num
                    effective_payload["Amount to CS"] = amt_combined
                    effective_payload["Total Inclusive of HST"] = total_combined
                    if not _clean_text(effective_payload.get("Invoice")) and existing_inv:
                        effective_payload["Invoice"] = existing_inv

            action = "updated"
            template_row_idx: int | None = None
            preserve_existing_client = False
            existing_client_val = None
            existing_sub_val = None
            if target_row_idx is None:
                action = "added"
                incoming_matter_val = _norm_key(effective_payload.get("Matter_ID"))
                if incoming_matter_val and max_row > header_row:
                    for prior_r in range(max_row, header_row, -1):
                        if _norm_key(ws.cell(prior_r, c_matter).value) == incoming_matter_val:
                            cand_client = _clean_text(ws.cell(prior_r, c_client).value)
                            if cand_client:
                                existing_client_val = cand_client
                                existing_sub_val = ws.cell(prior_r, c_sub).value
                                preserve_existing_client = True
                                break
                if max_row == header_row + 1 and self._row_is_blank(ws, max_row, min_col, max_col):
                    target_row_idx = max_row
                    template_row_idx = None
                else:
                    template_row_idx = max_row if max_row > header_row else None
                    target_row_idx = max_row + 1
                    max_row = target_row_idx
            else:
                if normalized_mode == "combine":
                    action = "combined"
                elif normalized_mode == "overwrite":
                    action = "overwritten"
                existing_matter_val = _norm_key(ws.cell(target_row_idx, c_matter).value)
                incoming_matter_val = _norm_key(effective_payload.get("Matter_ID"))
                existing_client_val = _clean_text(ws.cell(target_row_idx, c_client).value)
                existing_sub_val = ws.cell(target_row_idx, c_sub).value
                if existing_client_val and existing_matter_val and existing_matter_val == incoming_matter_val:
                    preserve_existing_client = True
                template_row_idx = target_row_idx - 1 if target_row_idx > header_row + 1 else (
                    target_row_idx + 1 if target_row_idx < max_row else None
                )

            if template_row_idx is not None and template_row_idx > header_row:
                self._copy_row_styles(ws, template_row_idx, target_row_idx, min_col, max_col)

            is_flat_fee = _clean_text(effective_payload.get("EntryType")).casefold() == "flat fee"

            cell_date = ws.cell(target_row_idx, c_date)
            cell_date.value = _parse_datetime_midnight(effective_payload.get("Date"))
            cell_date.number_format = LEGACY_DATE_NUMBER_FORMAT

            if preserve_existing_client:
                ws.cell(target_row_idx, c_client).value = existing_client_val
                ws.cell(target_row_idx, c_sub).value = existing_sub_val
            else:
                ws.cell(target_row_idx, c_client).value = _clean_text(effective_payload.get("Client")) or None
                sub_val = _clean_text(effective_payload.get("Sub-Client2"))
                ws.cell(target_row_idx, c_sub).value = sub_val if sub_val else None
            ws.cell(target_row_idx, c_desc).value = _clean_text(effective_payload.get("Description"))

            cell_hours = ws.cell(target_row_idx, c_hours)
            cell_hours.value = round(_parse_float(effective_payload.get("Time (in hrs)"), 0.0), 2)

            cell_rate = ws.cell(target_row_idx, c_rate)
            cell_rate.value = _format_rate_number(effective_payload.get("Hourly Rate/Flat Fee"))

            cell_pct = ws.cell(target_row_idx, c_pct)
            cell_pct.value = _normalize_share_fraction(effective_payload.get("Percentage", 1))
            cell_pct.number_format = LEGACY_PERCENT_NUMBER_FORMAT

            amt_numeric = round(_parse_float(effective_payload.get("Amount to CS"), 0.0), 2)
            cell_amt = ws.cell(target_row_idx, c_amt)
            cell_amt.value = self._resolve_formula_or_value(
                ws,
                template_row_idx,
                target_row_idx,
                c_amt,
                amt_numeric,
                is_flat_fee,
            )
            if not cell_amt.number_format or cell_amt.number_format == "General":
                cell_amt.number_format = LEGACY_CURRENCY_NUMBER_FORMAT

            total_numeric = round(_parse_float(effective_payload.get("Total Inclusive of HST"), 0.0), 2)
            cell_total = ws.cell(target_row_idx, c_total)
            cell_total.value = self._resolve_formula_or_value(
                ws,
                template_row_idx,
                target_row_idx,
                c_total,
                total_numeric,
                is_flat_fee,
            )
            if not cell_total.number_format or cell_total.number_format == "General":
                cell_total.number_format = LEGACY_CURRENCY_NUMBER_FORMAT

            inv_val = _clean_text(effective_payload.get("Invoice"))
            ws.cell(target_row_idx, c_inv).value = inv_val if inv_val else None
            ws.cell(target_row_idx, c_matter).value = _clean_text(effective_payload.get("Matter_ID")) or None
            ws.cell(target_row_idx, c_sec).value = int(round(_parse_float(effective_payload.get("RawSeconds"), 0.0)))
            ws.cell(target_row_idx, c_type).value = _clean_text(effective_payload.get("EntryType")) or "Hourly"

            # Update Table1_1.ref and autoFilter.ref if expanded
            new_ref = f"{get_column_letter(min_col)}{header_row}:{get_column_letter(max_col)}{max_row}"
            table.ref = new_ref
            if getattr(table, "autoFilter", None) is not None:
                table.autoFilter.ref = new_ref
            if getattr(ws, "auto_filter", None) is not None and getattr(ws.auto_filter, "ref", None):
                ws.auto_filter.ref = new_ref

            row_cell_values: dict[int, Any] = {
                col_idx: ws.cell(target_row_idx, col_idx).value
                for col_idx in range(min_col, max_col + 1)
            }
            formula_cached_values: dict[int, float] = {
                c_amt: amt_numeric,
                c_total: total_numeric,
            }

            patched_surgically = self._surgically_patch_workbook_zip(
                workbook_path=workbook_path,
                temp_path=temp_path,
                target_row_idx=int(target_row_idx),
                template_row_idx=int(template_row_idx) if template_row_idx is not None else None,
                header_row=int(header_row),
                min_col=int(min_col),
                max_col=int(max_col),
                max_row=int(max_row),
                new_ref=new_ref,
                row_cell_values=row_cell_values,
                formula_cached_values=formula_cached_values,
            )
            if not patched_surgically:
                wb.save(str(temp_path))
                self._normalize_xlsm_content_types(temp_path, workbook_path)
            self._close_workbook(wb)
            wb = None

            os.replace(str(temp_path), str(workbook_path))

            row_sig_dict = {
                "date": _iso_date_str(effective_payload.get("Date")),
                "matter_id": _clean_text(effective_payload.get("Matter_ID")),
                "raw_seconds": int(round(_parse_float(effective_payload.get("RawSeconds"), 0.0))),
                "time_hrs": round(_parse_float(effective_payload.get("Time (in hrs)"), 0.0), 2),
                "description": _clean_text(effective_payload.get("Description")),
            }
            if entry_id and isinstance(wb_entries, dict):
                wb_entries[entry_id] = {
                    "row": int(target_row_idx),
                    "signature": list(self._signature_from_payload(effective_payload)),
                    "rowSignature": row_sig_dict,
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                }

            status_code = "APPENDED" if action == "added" else "SYNCED"
            return {
                "ok": True,
                "status": status_code,
                "conflict": False,
                "action": action,
                "resolutionMode": normalized_mode or ("append" if action == "added" else "update"),
                "row": int(target_row_idx),
                "tableRef": new_ref,
                "workbookPath": str(workbook_path),
                "entryId": entry_id,
                "rowSignature": row_sig_dict,
            }
        finally:
            self._close_workbook(wb)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    @classmethod
    def _surgically_patch_workbook_zip(
        cls,
        *,
        workbook_path: Path,
        temp_path: Path,
        target_row_idx: int,
        template_row_idx: int | None,
        header_row: int,
        min_col: int,
        max_col: int,
        max_row: int,
        new_ref: str,
        row_cell_values: Mapping[int, Any],
        formula_cached_values: Mapping[int, float],
    ) -> bool:
        """Update only the Dockets sheet XML, Table1_1 XML, and ExternalData_1 definedName in the ZIP archive.

        This preserves customUI/*, _rels/.rels (ui/extensibility), xl/queryTables/*, xl/connections.xml,
        xl/comments*, xl/drawings/*, xl/vbaProject.bin, and all other workbook parts byte-for-byte.
        """
        if not workbook_path.is_file() or not zipfile.is_zipfile(workbook_path):
            return False

        try:
            with zipfile.ZipFile(workbook_path, "r") as zin:
                names = set(zin.namelist())
                if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
                    return False

                wb_xml = zin.read("xl/workbook.xml").decode("utf-8")
                wb_rels_xml = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")

                sheet_rid = None
                for m_sheet in re.finditer(r"<sheet\b[^>]*>", wb_xml):
                    tag = m_sheet.group(0)
                    m_name = re.search(r'\bname="([^"]+)"', tag)
                    if m_name and m_name.group(1) == LEGACY_DOCKETS_SHEET:
                        m_rid = re.search(r'\br:id="([^"]+)"', tag)
                        if m_rid:
                            sheet_rid = m_rid.group(1)
                        break
                if not sheet_rid:
                    return False

                sheet_part_name = None
                for m_rel in re.finditer(r"<Relationship\b[^>]*>", wb_rels_xml):
                    tag = m_rel.group(0)
                    m_id = re.search(r'\bId="([^"]+)"', tag)
                    m_target = re.search(r'\bTarget="([^"]+)"', tag)
                    if m_id and m_target and m_id.group(1) == sheet_rid:
                        raw_target = m_target.group(1).lstrip("/")
                        if not raw_target.startswith("xl/"):
                            raw_target = f"xl/{raw_target}"
                        sheet_part_name = raw_target
                        break
                if not sheet_part_name or sheet_part_name not in names:
                    return False

                table_part_name = None
                for candidate in sorted(n for n in names if n.startswith("xl/tables/") and n.endswith(".xml")):
                    t_xml = zin.read(candidate).decode("utf-8", errors="ignore")
                    m_tbl = re.search(r"<table\b[^>]*>", t_xml)
                    if not m_tbl:
                        continue
                    tbl_tag = m_tbl.group(0)
                    if (
                        f'name="{LEGACY_DOCKETS_TABLE}"' in tbl_tag
                        or f'displayName="{LEGACY_DOCKETS_TABLE}"' in tbl_tag
                    ):
                        table_part_name = candidate
                        break
                if not table_part_name or table_part_name not in names:
                    return False

                sheet_xml = zin.read(sheet_part_name).decode("utf-8")
                table_xml = zin.read(table_part_name).decode("utf-8")

                # Extract cell styles (s="...") from template row and/or existing target row
                style_by_col: dict[str, str] = {}
                candidate_style_rows: list[int] = []
                if template_row_idx is not None and template_row_idx > header_row:
                    candidate_style_rows.append(template_row_idx)
                if target_row_idx > header_row:
                    candidate_style_rows.append(target_row_idx)

                def _harvest_row_styles(row_block: str, overwrite: bool = True) -> None:
                    for m_c in re.finditer(r'<c\b[^>]*\br="([A-Z]+)\d+"[^>]*>', row_block):
                        col_let = m_c.group(1)
                        m_s = re.search(r'\bs="(\d+)"', m_c.group(0))
                        if m_s and (overwrite or col_let not in style_by_col):
                            style_by_col[col_let] = m_s.group(1)

                for r_idx in candidate_style_rows:
                    m_r = re.search(
                        rf'<row\b[^>]*\br="{r_idx}"[^>]*>(?:.*?</row>|/>)',
                        sheet_xml,
                        re.DOTALL,
                    )
                    if m_r:
                        _harvest_row_styles(m_r.group(0), overwrite=True)

                if not style_by_col:
                    all_rows = list(re.finditer(r'<row\b[^>]*\br="(\d+)"[^>]*>.*?</row>', sheet_xml, re.DOTALL))
                    for m_r in reversed(all_rows):
                        if int(m_r.group(1)) > header_row:
                            _harvest_row_styles(m_r.group(0), overwrite=False)
                            if style_by_col:
                                break

                existing_target_match = re.search(
                    rf'<row\b([^>]*\br="{target_row_idx}"[^>]*)>(?:.*?</row>|/>)',
                    sheet_xml,
                    re.DOTALL,
                )
                row_attrs_str = f'r="{target_row_idx}" spans="{min_col}:{max_col}"'
                if existing_target_match:
                    raw_attrs = existing_target_match.group(1)
                    m_ht = re.search(r'\bht="([^"]+)"', raw_attrs)
                    if m_ht:
                        row_attrs_str += f' ht="{m_ht.group(1)}"'
                elif template_row_idx is not None:
                    m_tmpl = re.search(rf'<row\b([^>]*\br="{template_row_idx}"[^>]*)>', sheet_xml)
                    if m_tmpl:
                        m_ht = re.search(r'\bht="([^"]+)"', m_tmpl.group(1))
                        if m_ht:
                            row_attrs_str += f' ht="{m_ht.group(1)}"'

                cells_xml: list[str] = []
                for col_idx in range(min_col, max_col + 1):
                    col_letter = get_column_letter(col_idx)
                    coord = f"{col_letter}{target_row_idx}"
                    s_val = style_by_col.get(col_letter)
                    s_attr = f' s="{s_val}"' if s_val is not None else ""
                    val = row_cell_values.get(col_idx)

                    if val is None or (isinstance(val, str) and val == ""):
                        if s_attr:
                            cells_xml.append(f'<c r="{coord}"{s_attr}/>')
                        continue

                    if isinstance(val, (datetime, date)):
                        d_val = val.date() if isinstance(val, datetime) else val
                        serial_days = (d_val - EXCEL_EPOCH_DATE).days
                        cells_xml.append(f'<c r="{coord}"{s_attr}><v>{serial_days}</v></c>')
                        continue

                    if isinstance(val, str) and val.startswith("="):
                        f_body = xml_escape(val[1:], quote=False)
                        cached_num = formula_cached_values.get(col_idx, 0.0)
                        v_str = _format_xml_number(cached_num)
                        cells_xml.append(f'<c r="{coord}"{s_attr}><f>{f_body}</f><v>{v_str}</v></c>')
                        continue

                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        v_str = _format_xml_number(val)
                        cells_xml.append(f'<c r="{coord}"{s_attr}><v>{v_str}</v></c>')
                        continue

                    text_str = str(val)
                    escaped_text = xml_escape(text_str, quote=False)
                    space_attr = (
                        ' xml:space="preserve"'
                        if (text_str[:1].isspace() or text_str[-1:].isspace() or "\n" in text_str)
                        else ""
                    )
                    cells_xml.append(
                        f'<c r="{coord}"{s_attr} t="inlineStr"><is><t{space_attr}>{escaped_text}</t></is></c>'
                    )

                new_row_xml = f"<row {row_attrs_str}>{''.join(cells_xml)}</row>"

                if existing_target_match:
                    start_pos, end_pos = existing_target_match.span()
                    sheet_xml = sheet_xml[:start_pos] + new_row_xml + sheet_xml[end_pos:]
                else:
                    close_tag = "</sheetData>"
                    idx_close = sheet_xml.rfind(close_tag)
                    if idx_close < 0:
                        return False
                    sheet_xml = sheet_xml[:idx_close] + new_row_xml + sheet_xml[idx_close:]

                # Expand <dimension ref="A1:Z879"/> if max_row exceeds previous dimension end row
                def _bump_dimension(m_dim: re.Match[str]) -> str:
                    prefix, end_col, end_row_str, suffix = (
                        m_dim.group(1),
                        m_dim.group(2),
                        m_dim.group(3),
                        m_dim.group(4),
                    )
                    new_end_row = max(int(end_row_str), int(max_row))
                    return f"{prefix}{end_col}{new_end_row}{suffix}"

                sheet_xml = re.sub(
                    r'(<dimension\b[^>]*\bref="[A-Z]+\d+:)([A-Z]+)(\d+)("[^>]*/>)',
                    _bump_dimension,
                    sheet_xml,
                    count=1,
                )

                # Update ref="A1:M..." on <table ...> and <autoFilter ...> in table1.xml
                table_xml = re.sub(
                    r'(<table\b[^>]*\bref=")[^"]+(")',
                    rf"\g<1>{new_ref}\g<2>",
                    table_xml,
                    count=1,
                )
                table_xml = re.sub(
                    r'(<autoFilter\b[^>]*\bref=")[^"]+(")',
                    rf"\g<1>{new_ref}\g<2>",
                    table_xml,
                    count=1,
                )

                # Synchronize ExternalData_1 definedName in xl/workbook.xml if present for Dockets queryTable
                wb_xml = re.sub(
                    r'(<definedName\b[^>]*\bname="ExternalData_1"[^>]*>\s*(?:\'Dockets\'|Dockets)!\$[A-Z]+\$\d+:\$[A-Z]+\$)\d+(\s*</definedName>)',
                    rf"\g<1>{max_row}\g<2>",
                    wb_xml,
                )

                with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                    for name in zin.namelist():
                        if name == sheet_part_name:
                            zout.writestr(name, sheet_xml.encode("utf-8"))
                        elif name == table_part_name:
                            zout.writestr(name, table_xml.encode("utf-8"))
                        elif name == "xl/workbook.xml":
                            zout.writestr(name, wb_xml.encode("utf-8"))
                        else:
                            zout.writestr(name, zin.read(name))
                return True
        except Exception as exc:
            logger.debug("[legacy_dockets_sync] Surgical ZIP patch fallback to openpyxl: %s", exc)
            return False

    def _queue_pending_sync(
        self,
        workbook_path: Path,
        current_payload: Mapping[str, Any],
        previous_payload: Mapping[str, Any] | None,
        is_update: bool,
        reason: str,
    ) -> None:
        queue_file = self._pending_queue_path()
        state = self._load_json_state(queue_file)
        items = state.setdefault("pending", [])
        if not isinstance(items, list):
            items = []
            state["pending"] = items

        wb_str = str(workbook_path)
        entry_id = _clean_text(current_payload.get("entryId"))
        if entry_id:
            for existing in items:
                if (
                    isinstance(existing, dict)
                    and _clean_text(existing.get("entryId")) == entry_id
                    and str(existing.get("workbookPath", "")).casefold() == wb_str.casefold()
                ):
                    # Keep the original previousPayload so the initial row in Table1_1 is still matched
                    existing["currentPayload"] = dict(current_payload)
                    existing["isUpdate"] = bool(is_update or existing.get("isUpdate"))
                    existing["reason"] = reason
                    existing["queuedAt"] = datetime.now().isoformat(timespec="seconds")
                    self._save_json_state(queue_file, state)
                    return

        items.append(
            {
                "workbookPath": wb_str,
                "entryId": entry_id,
                "currentPayload": dict(current_payload),
                "previousPayload": dict(previous_payload) if previous_payload is not None else None,
                "isUpdate": bool(is_update),
                "reason": reason,
                "queuedAt": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self._save_json_state(queue_file, state)

    def flush_pending_syncs(self, sync_map: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        queue_file = self._pending_queue_path()
        state = self._load_json_state(queue_file)
        pending = state.get("pending", [])
        if not isinstance(pending, list) or not pending:
            return []

        own_map = sync_map is None
        if sync_map is None:
            sync_map = self._load_json_state(self._sync_map_path())

        remaining: list[dict[str, Any]] = []
        flushed: list[dict[str, Any]] = []
        for item in pending:
            if not isinstance(item, dict):
                continue
            wb_path = Path(str(item.get("workbookPath", "")))
            if not wb_path.is_file():
                continue
            try:
                res = self._apply_upsert_to_workbook(
                    wb_path,
                    item.get("currentPayload") or {},
                    item.get("previousPayload"),
                    bool(item.get("isUpdate")),
                    sync_map,
                )
                flushed.append(res)
            except (PermissionError, OSError) as exc:
                item["reason"] = str(exc)
                remaining.append(item)
            except Exception as exc:
                logger.warning("[legacy_dockets_sync] Pending sync item failed for %s: %s", wb_path, exc)

        state["pending"] = remaining
        self._save_json_state(queue_file, state)
        if own_map and flushed:
            self._save_json_state(self._sync_map_path(), sync_map)
        return flushed

    def _save_pending_conflict(self, conflict_record: Mapping[str, Any]) -> None:
        conflict_file = self._pending_conflicts_path()
        state = self._load_json_state(conflict_file)
        conflicts = state.setdefault("conflicts", {})
        if not isinstance(conflicts, dict):
            conflicts = {}
            state["conflicts"] = conflicts
        conflict_id = _clean_text(conflict_record.get("conflictId"))
        if conflict_id:
            conflicts[conflict_id] = dict(conflict_record)
            state["latestConflictId"] = conflict_id
            self._save_json_state(conflict_file, state)

    def _remove_pending_conflict(self, conflict_id: str) -> None:
        clean_id = _clean_text(conflict_id)
        if not clean_id:
            return
        conflict_file = self._pending_conflicts_path()
        state = self._load_json_state(conflict_file)
        conflicts = state.get("conflicts")
        if isinstance(conflicts, dict) and clean_id in conflicts:
            conflicts.pop(clean_id, None)
            if state.get("latestConflictId") == clean_id:
                remaining_ids = list(conflicts.keys())
                state["latestConflictId"] = remaining_ids[-1] if remaining_ids else ""
            self._save_json_state(conflict_file, state)

    def get_pending_conflicts(self) -> list[dict[str, Any]]:
        state = self._load_json_state(self._pending_conflicts_path())
        conflicts = state.get("conflicts")
        if isinstance(conflicts, dict):
            return [dict(v) for v in conflicts.values() if isinstance(v, dict)]
        return []

    def sync_docket_entry(
        self,
        current_payload: Mapping[str, Any],
        *,
        previous_payload: Mapping[str, Any] | None = None,
        is_update: bool = False,
        target_paths: Sequence[Path] | None = None,
        resolution_mode: str | None = None,
        target_row: int | None = None,
        confirm_billed_overwrite: bool = True,
    ) -> dict[str, Any]:
        targets = list(target_paths) if target_paths is not None else self.paths.legacy_dockets_sync_targets()
        if not targets:
            return {
                "ok": True,
                "status": "NO_TARGETS",
                "conflict": False,
                "syncedCount": 0,
                "queuedCount": 0,
                "results": [],
            }

        sync_map = self._load_json_state(self._sync_map_path())
        self.flush_pending_syncs(sync_map=sync_map)

        results: list[dict[str, Any]] = []
        synced_count = 0
        queued_count = 0
        warnings: list[str] = []
        conflict_results: list[dict[str, Any]] = []

        for wb_path in targets:
            if not wb_path.is_file():
                continue
            try:
                res = self._apply_upsert_to_workbook(
                    wb_path,
                    current_payload,
                    previous_payload,
                    is_update,
                    sync_map,
                    resolution_mode=resolution_mode,
                    target_row=target_row,
                    confirm_billed_overwrite=confirm_billed_overwrite,
                )
                results.append(res)
                if res.get("conflict") or res.get("status") == "CONFLICT":
                    conflict_results.append(res)
                elif res.get("ok"):
                    synced_count += 1
            except (PermissionError, OSError) as exc:
                warn_msg = (
                    f"Dockets.xlsm ({wb_path.name}) is currently locked by Excel; "
                    "docket sync was queued for automatic retry."
                )
                logger.warning("[legacy_dockets_sync] %s (%s)", warn_msg, exc)
                self._queue_pending_sync(wb_path, current_payload, previous_payload, is_update, str(exc))
                queued_count += 1
                warnings.append(warn_msg)
                results.append(
                    {
                        "ok": True,
                        "queued": True,
                        "workbookPath": str(wb_path),
                        "warning": warn_msg,
                    }
                )
            except Exception as exc:
                warn_msg = f"Could not sync docket to {wb_path.name}: {exc}"
                logger.warning("[legacy_dockets_sync] %s", warn_msg)
                warnings.append(warn_msg)
                results.append(
                    {
                        "ok": False,
                        "queued": False,
                        "workbookPath": str(wb_path),
                        "warning": warn_msg,
                    }
                )

        self._save_json_state(self._sync_map_path(), sync_map)

        if conflict_results:
            primary_conflict = conflict_results[0]
            conflict_id = f"CONF-{uuid4().hex[:10].upper()}"
            existing_rows = list(primary_conflict.get("existingRows") or [])
            incoming_entry = dict(primary_conflict.get("incomingEntry") or current_payload)
            conflict_reason = str(primary_conflict.get("conflictReason") or "EXISTING_DATE_MATTER_ROW")
            selected_row = int(
                primary_conflict.get("selectedTargetRow")
                or (existing_rows[0]["row"] if existing_rows else 0)
            )
            conflict_record = {
                "conflictId": conflict_id,
                "status": "CONFLICT",
                "conflict": True,
                "conflictReason": conflict_reason,
                "requiresBilledConfirmation": bool(primary_conflict.get("requiresBilledConfirmation")),
                "existingInvoice": str(primary_conflict.get("existingInvoice") or ""),
                "incomingEntry": incoming_entry,
                "previousPayload": dict(previous_payload) if previous_payload is not None else None,
                "isUpdate": bool(is_update),
                "existingRows": existing_rows,
                "selectedTargetRow": selected_row,
                "targetPaths": [str(p) for p in targets if p.is_file()],
                "workbookPath": str(primary_conflict.get("workbookPath") or ""),
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            }
            self._save_pending_conflict(conflict_record)
            return {
                "ok": bool(primary_conflict.get("ok", True)),
                "status": "CONFLICT",
                "conflict": True,
                "conflictId": conflict_id,
                "conflictReason": conflict_reason,
                "requiresBilledConfirmation": bool(primary_conflict.get("requiresBilledConfirmation")),
                "existingInvoice": str(primary_conflict.get("existingInvoice") or ""),
                "incomingEntry": incoming_entry,
                "existingRows": existing_rows,
                "selectedTargetRow": selected_row,
                "workbookPath": str(primary_conflict.get("workbookPath") or ""),
                "syncedCount": synced_count,
                "queuedCount": queued_count,
                "warnings": warnings,
                "results": results,
                "message": str(
                    primary_conflict.get("message")
                    or "Potential conflict detected in legacy Dockets.xlsm."
                ),
            }

        normalized_mode = self._normalize_resolution_mode(resolution_mode)
        if normalized_mode == "skip":
            top_status = "SKIPPED"
            toast_msg = "Saved in CSPM only (skipped Dockets.xlsm)"
        elif synced_count > 0:
            top_status = "APPENDED" if any(r.get("action") == "added" for r in results) else "SYNCED"
            toast_msg = "Saved & synced to Dockets.xlsm"
        elif queued_count > 0:
            top_status = "QUEUED"
            toast_msg = ""
        else:
            top_status = "IDLE"
            toast_msg = ""

        first_sig = next(
            (r.get("rowSignature") for r in results if isinstance(r.get("rowSignature"), dict)),
            {
                "date": _iso_date_str(current_payload.get("Date")),
                "matter_id": _clean_text(current_payload.get("Matter_ID")),
                "raw_seconds": int(round(_parse_float(current_payload.get("RawSeconds"), 0.0))),
                "time_hrs": round(_parse_float(current_payload.get("Time (in hrs)"), 0.0), 2),
                "description": _clean_text(current_payload.get("Description")),
            },
        )
        return {
            "ok": True,
            "status": top_status,
            "conflict": False,
            "resolutionMode": normalized_mode or "",
            "toastMessage": toast_msg,
            "entryId": _clean_text(current_payload.get("entryId")),
            "rowSignature": first_sig,
            "syncedCount": synced_count,
            "queuedCount": queued_count,
            "warnings": warnings,
            "results": results,
        }

    def resolve_conflict(
        self,
        conflict_or_id: str | Mapping[str, Any] | None,
        resolution_mode: str,
        *,
        target_row: int | None = None,
        confirm_billed_overwrite: bool = True,
        target_paths: Sequence[Path] | None = None,
    ) -> dict[str, Any]:
        """Execute one of the 4 user conflict resolution actions: overwrite, append, combine, or skip."""
        normalized_mode = self._normalize_resolution_mode(resolution_mode)
        if not normalized_mode:
            raise ValueError("resolution_mode is required ('overwrite', 'append', 'combine', or 'skip').")

        conflict_id = ""
        conflict_record: dict[str, Any] = {}
        state = self._load_json_state(self._pending_conflicts_path())
        stored_conflicts = state.get("conflicts") if isinstance(state.get("conflicts"), dict) else {}

        if isinstance(conflict_or_id, str):
            conflict_id = _clean_text(conflict_or_id)
            if conflict_id and conflict_id in stored_conflicts:
                conflict_record = dict(stored_conflicts[conflict_id])
        elif isinstance(conflict_or_id, Mapping):
            nested = conflict_or_id.get("legacyDocketsSync")
            source_map = nested if isinstance(nested, Mapping) else conflict_or_id
            conflict_id = _clean_text(source_map.get("conflictId"))
            if conflict_id and conflict_id in stored_conflicts:
                conflict_record = dict(stored_conflicts[conflict_id])
            else:
                conflict_record = dict(source_map)

        if not conflict_record and state.get("latestConflictId"):
            latest_id = _clean_text(state.get("latestConflictId"))
            if latest_id and latest_id in stored_conflicts:
                conflict_id = latest_id
                conflict_record = dict(stored_conflicts[latest_id])

        incoming_entry = conflict_record.get("incomingEntry")
        if not isinstance(incoming_entry, Mapping):
            if isinstance(conflict_or_id, Mapping) and "Date" in conflict_or_id and "Matter_ID" in conflict_or_id:
                incoming_entry = conflict_or_id
            else:
                return {
                    "ok": False,
                    "status": "ERROR",
                    "conflict": False,
                    "message": f"Conflict record {conflict_id or ''} not found.",
                }

        resolved_target_row = target_row
        if resolved_target_row is None and conflict_record.get("selectedTargetRow"):
            try:
                resolved_target_row = int(conflict_record["selectedTargetRow"])
            except (TypeError, ValueError):
                resolved_target_row = None

        resolved_paths: list[Path] | None = None
        if target_paths is not None:
            resolved_paths = list(target_paths)
        elif isinstance(conflict_record.get("targetPaths"), list) and conflict_record.get("targetPaths"):
            resolved_paths = [Path(str(p)) for p in conflict_record["targetPaths"]]

        res = self.sync_docket_entry(
            incoming_entry,
            previous_payload=conflict_record.get("previousPayload"),
            is_update=bool(conflict_record.get("isUpdate")),
            target_paths=resolved_paths,
            resolution_mode=normalized_mode,
            target_row=resolved_target_row,
            confirm_billed_overwrite=confirm_billed_overwrite,
        )
        if not res.get("conflict") and conflict_id:
            self._remove_pending_conflict(conflict_id)
        return res

    @classmethod
    def _surgically_delete_row_in_workbook_zip(
        cls,
        *,
        workbook_path: Path,
        temp_path: Path,
        target_row_idx: int,
        header_row: int,
        min_col: int,
        max_col: int,
        new_max_row: int,
        new_ref: str,
        clear_only: bool = False,
    ) -> bool:
        if not workbook_path.is_file() or not zipfile.is_zipfile(workbook_path):
            return False

        if clear_only:
            empty_values = {col_idx: None for col_idx in range(min_col, max_col + 1)}
            return cls._surgically_patch_workbook_zip(
                workbook_path=workbook_path,
                temp_path=temp_path,
                target_row_idx=target_row_idx,
                template_row_idx=None,
                header_row=header_row,
                min_col=min_col,
                max_col=max_col,
                max_row=new_max_row,
                new_ref=new_ref,
                row_cell_values=empty_values,
                formula_cached_values={},
            )

        try:
            with zipfile.ZipFile(workbook_path, "r") as zin:
                names = set(zin.namelist())
                if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
                    return False

                wb_xml = zin.read("xl/workbook.xml").decode("utf-8")
                wb_rels_xml = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")

                sheet_rid = None
                for m_sheet in re.finditer(r"<sheet\b[^>]*>", wb_xml):
                    tag = m_sheet.group(0)
                    m_name = re.search(r'\bname="([^"]+)"', tag)
                    if m_name and m_name.group(1) == LEGACY_DOCKETS_SHEET:
                        m_rid = re.search(r'\br:id="([^"]+)"', tag)
                        if m_rid:
                            sheet_rid = m_rid.group(1)
                        break
                if not sheet_rid:
                    return False

                sheet_part_name = None
                for m_rel in re.finditer(r"<Relationship\b[^>]*>", wb_rels_xml):
                    tag = m_rel.group(0)
                    m_id = re.search(r'\bId="([^"]+)"', tag)
                    m_target = re.search(r'\bTarget="([^"]+)"', tag)
                    if m_id and m_target and m_id.group(1) == sheet_rid:
                        raw_target = m_target.group(1).lstrip("/")
                        if not raw_target.startswith("xl/"):
                            raw_target = f"xl/{raw_target}"
                        sheet_part_name = raw_target
                        break
                if not sheet_part_name or sheet_part_name not in names:
                    return False

                table_part_name = None
                for candidate in sorted(n for n in names if n.startswith("xl/tables/") and n.endswith(".xml")):
                    t_xml = zin.read(candidate).decode("utf-8", errors="ignore")
                    m_tbl = re.search(r"<table\b[^>]*>", t_xml)
                    if not m_tbl:
                        continue
                    tbl_tag = m_tbl.group(0)
                    if (
                        f'name="{LEGACY_DOCKETS_TABLE}"' in tbl_tag
                        or f'displayName="{LEGACY_DOCKETS_TABLE}"' in tbl_tag
                    ):
                        table_part_name = candidate
                        break
                if not table_part_name or table_part_name not in names:
                    return False

                sheet_xml = zin.read(sheet_part_name).decode("utf-8")
                table_xml = zin.read(table_part_name).decode("utf-8")

                row_pattern = re.compile(
                    r'<row\b([^>]*\br="(\d+)"[^>]*)(?:>(.*?)</row>|/>)',
                    re.DOTALL,
                )
                found_deleted = False

                def _replace_row(m_row: re.Match[str]) -> str:
                    nonlocal found_deleted
                    attrs = m_row.group(1)
                    r_num = int(m_row.group(2))
                    body = m_row.group(3)
                    if r_num == target_row_idx:
                        found_deleted = True
                        return ""
                    if r_num > target_row_idx:
                        next_r = r_num - 1
                        new_attrs = re.sub(r'\br="\d+"', f'r="{next_r}"', attrs, count=1)
                        if body is None:
                            return f"<row{new_attrs}/>"
                        new_body = re.sub(
                            r'(<c\b[^>]*\br="[A-Z]+)\d+(")',
                            rf"\g<1>{next_r}\g<2>",
                            body,
                        )
                        return f"<row{new_attrs}>{new_body}</row>"
                    return m_row.group(0)

                sheet_xml = row_pattern.sub(_replace_row, sheet_xml)
                if not found_deleted:
                    return False

                sheet_xml = re.sub(
                    r'(<dimension\b[^>]*\bref="[A-Z]+\d+:)([A-Z]+)(\d+)("[^>]*/>)',
                    lambda m_dim: f"{m_dim.group(1)}{m_dim.group(2)}{new_max_row}{m_dim.group(4)}",
                    sheet_xml,
                    count=1,
                )

                table_xml = re.sub(
                    r'(<table\b[^>]*\bref=")[^"]+(")',
                    rf"\g<1>{new_ref}\g<2>",
                    table_xml,
                    count=1,
                )
                table_xml = re.sub(
                    r'(<autoFilter\b[^>]*\bref=")[^"]+(")',
                    rf"\g<1>{new_ref}\g<2>",
                    table_xml,
                    count=1,
                )

                wb_xml = re.sub(
                    r'(<definedName\b[^>]*\bname="ExternalData_1"[^>]*>\s*(?:\'Dockets\'|Dockets)!\$[A-Z]+\$\d+:\$[A-Z]+\$)\d+(\s*</definedName>)',
                    rf"\g<1>{new_max_row}\g<2>",
                    wb_xml,
                )

                with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                    for name in zin.namelist():
                        if name == sheet_part_name:
                            zout.writestr(name, sheet_xml.encode("utf-8"))
                        elif name == table_part_name:
                            zout.writestr(name, table_xml.encode("utf-8"))
                        elif name == "xl/workbook.xml":
                            zout.writestr(name, wb_xml.encode("utf-8"))
                        else:
                            zout.writestr(name, zin.read(name))
                return True
        except Exception as exc:
            logger.debug("[legacy_dockets_sync] Surgical ZIP delete fallback to openpyxl: %s", exc)
            return False

    def _apply_delete_to_workbook(
        self,
        workbook_path: Path,
        entry_id: str,
        entry_payload: Mapping[str, Any] | None,
        sync_map: dict[str, Any],
    ) -> dict[str, Any]:
        if self._is_excel_lock_present(workbook_path):
            raise PermissionError(f"Excel lock file ~${workbook_path.name} is present.")

        wb = None
        temp_path = workbook_path.with_name(f".{workbook_path.name}.{uuid4().hex}.tmp")
        try:
            keep_vba = workbook_path.suffix.lower() == ".xlsm"
            wb = openpyxl.load_workbook(str(workbook_path), keep_vba=keep_vba)
            if LEGACY_DOCKETS_SHEET not in wb.sheetnames:
                return {
                    "ok": True,
                    "status": "NOT_FOUND",
                    "deleted": False,
                    "billedLocked": False,
                    "billedInvoice": "",
                    "workbookPath": str(workbook_path),
                    "entryId": entry_id,
                }
            ws = wb[LEGACY_DOCKETS_SHEET]
            table, min_col, header_row, max_col, max_row = self._ensure_table1_1(ws)
            if max_col - min_col + 1 < len(LEGACY_DOCKETS_HEADERS):
                max_col = min_col + len(LEGACY_DOCKETS_HEADERS) - 1

            col_map: dict[str, int] = {}
            for col_idx in range(min_col, max_col + 1):
                header_text = _clean_text(ws.cell(header_row, col_idx).value)
                if header_text:
                    col_map[header_text.casefold()] = col_idx
            for offset, default_header in enumerate(LEGACY_DOCKETS_HEADERS):
                col_idx = min_col + offset
                if default_header.casefold() not in col_map:
                    col_map[default_header.casefold()] = col_idx

            c_inv = col_map["invoice"]
            c_date = col_map["date"]
            c_matter = col_map["matter_id"]

            wb_key = str(workbook_path.resolve()).casefold()
            wb_entries = sync_map.setdefault(wb_key, {})
            clean_eid = _clean_text(entry_id)
            mapped_info = wb_entries.get(clean_eid) if (clean_eid and isinstance(wb_entries, dict)) else None
            preferred_row = (
                int(mapped_info["row"])
                if isinstance(mapped_info, dict) and mapped_info.get("row")
                else None
            )
            saved_sig: tuple[str, str, int, str, float] | None = None
            if isinstance(mapped_info, dict) and isinstance(mapped_info.get("signature"), (list, tuple)):
                raw_sig = list(mapped_info["signature"])
                if len(raw_sig) == 5:
                    saved_sig = (
                        str(raw_sig[0]),
                        str(raw_sig[1]),
                        int(round(_parse_float(raw_sig[2], 0.0))),
                        str(raw_sig[3]),
                        round(_parse_float(raw_sig[4], 0.0), 2),
                    )

            target_row_idx: int | None = None
            if (
                preferred_row is not None
                and header_row < preferred_row <= max_row
                and not self._row_is_blank(ws, preferred_row, min_col, max_col)
            ):
                row_date_str = _iso_date_str(ws.cell(preferred_row, c_date).value)
                row_matter_key = _norm_key(ws.cell(preferred_row, c_matter).value)
                expected_matter = (
                    saved_sig[0]
                    if saved_sig is not None
                    else (_norm_key(entry_payload.get("Matter_ID")) if entry_payload else "")
                )
                expected_date = (
                    saved_sig[1]
                    if saved_sig is not None
                    else (_iso_date_str(entry_payload.get("Date")) if entry_payload else "")
                )
                if (
                    (expected_date and row_date_str == expected_date)
                    and (not expected_matter or row_matter_key == expected_matter)
                ):
                    target_row_idx = int(preferred_row)

            if target_row_idx is None and saved_sig is not None:
                target_row_idx = self._find_matching_row(
                    ws,
                    min_col,
                    header_row,
                    max_row,
                    col_map,
                    saved_sig,
                    preferred_row_idx=preferred_row,
                )

            if target_row_idx is None and entry_payload is not None:
                payload_sig = self._signature_from_payload(entry_payload)
                if payload_sig[0] and payload_sig[1]:
                    target_row_idx = self._find_matching_row(
                        ws,
                        min_col,
                        header_row,
                        max_row,
                        col_map,
                        payload_sig,
                        preferred_row_idx=preferred_row,
                    )
                    if target_row_idx is None:
                        dm_rows = self._find_rows_by_date_and_matter(
                            ws,
                            min_col,
                            header_row,
                            max_row,
                            col_map,
                            entry_payload.get("Matter_ID"),
                            entry_payload.get("Date"),
                        )
                        if len(dm_rows) == 1:
                            target_row_idx = int(dm_rows[0])

            if target_row_idx is None:
                if clean_eid and isinstance(wb_entries, dict):
                    wb_entries.pop(clean_eid, None)
                return {
                    "ok": True,
                    "status": "NOT_FOUND",
                    "deleted": False,
                    "billedLocked": False,
                    "billedInvoice": "",
                    "workbookPath": str(workbook_path),
                    "entryId": clean_eid,
                }

            existing_inv = _clean_text(ws.cell(target_row_idx, c_inv).value)
            if existing_inv:
                warn_msg = (
                    f"Row {target_row_idx} in Dockets.xlsm is already billed on Invoice {existing_inv} "
                    "and was not deleted from Dockets.xlsm."
                )
                return {
                    "ok": False,
                    "status": "BILLED_LOCKED",
                    "deleted": False,
                    "billedLocked": True,
                    "billedInvoice": existing_inv,
                    "row": int(target_row_idx),
                    "workbookPath": str(workbook_path),
                    "entryId": clean_eid,
                    "warning": warn_msg,
                }

            clear_only = max_row <= (header_row + 1)
            if clear_only:
                for col_idx in range(min_col, max_col + 1):
                    ws.cell(target_row_idx, col_idx).value = None
                new_max_row = header_row + 1
            else:
                ws.delete_rows(target_row_idx, 1)
                new_max_row = max_row - 1

            new_ref = f"{get_column_letter(min_col)}{header_row}:{get_column_letter(max_col)}{new_max_row}"
            table.ref = new_ref
            if getattr(table, "autoFilter", None) is not None:
                table.autoFilter.ref = new_ref
            if getattr(ws, "auto_filter", None) is not None and getattr(ws.auto_filter, "ref", None):
                ws.auto_filter.ref = new_ref

            patched_surgically = self._surgically_delete_row_in_workbook_zip(
                workbook_path=workbook_path,
                temp_path=temp_path,
                target_row_idx=int(target_row_idx),
                header_row=int(header_row),
                min_col=int(min_col),
                max_col=int(max_col),
                new_max_row=int(new_max_row),
                new_ref=new_ref,
                clear_only=clear_only,
            )
            if not patched_surgically:
                wb.save(str(temp_path))
                self._normalize_xlsm_content_types(temp_path, workbook_path)
            self._close_workbook(wb)
            wb = None

            os.replace(str(temp_path), str(workbook_path))

            if isinstance(wb_entries, dict):
                if clean_eid:
                    wb_entries.pop(clean_eid, None)
                if not clear_only:
                    to_remove_keys: list[str] = []
                    for k, info in wb_entries.items():
                        if not isinstance(info, dict):
                            continue
                        r_val = info.get("row")
                        if isinstance(r_val, int):
                            if r_val == target_row_idx:
                                to_remove_keys.append(k)
                            elif r_val > target_row_idx:
                                info["row"] = r_val - 1
                    for k in to_remove_keys:
                        wb_entries.pop(k, None)

            return {
                "ok": True,
                "status": "DELETED",
                "deleted": True,
                "billedLocked": False,
                "billedInvoice": "",
                "row": int(target_row_idx),
                "tableRef": new_ref,
                "workbookPath": str(workbook_path),
                "entryId": clean_eid,
            }
        finally:
            self._close_workbook(wb)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def delete_docket_entry(
        self,
        entry_id: str,
        entry_payload: Mapping[str, Any] | None = None,
        *,
        target_paths: Sequence[Path] | None = None,
    ) -> dict[str, Any]:
        """Delete an unbilled synced row from Dockets.xlsm (Table1_1) and update Table1_1.ref."""
        clean_eid = _clean_text(entry_id)

        # Remove any pending queue items or pending conflicts for this entry_id
        if clean_eid:
            try:
                queue_file = self._pending_queue_path()
                q_state = self._load_json_state(queue_file)
                pending = q_state.get("pending")
                if isinstance(pending, list):
                    filtered = [
                        item
                        for item in pending
                        if not (isinstance(item, dict) and _clean_text(item.get("entryId")) == clean_eid)
                    ]
                    if len(filtered) != len(pending):
                        q_state["pending"] = filtered
                        self._save_json_state(queue_file, q_state)
            except Exception:
                pass
            try:
                conflict_file = self._pending_conflicts_path()
                c_state = self._load_json_state(conflict_file)
                conflicts = c_state.get("conflicts")
                if isinstance(conflicts, dict):
                    to_del = [
                        cid
                        for cid, cval in conflicts.items()
                        if isinstance(cval, dict)
                        and _clean_text((cval.get("incomingEntry") or {}).get("entryId")) == clean_eid
                    ]
                    for cid in to_del:
                        conflicts.pop(cid, None)
                    if to_del:
                        self._save_json_state(conflict_file, c_state)
            except Exception:
                pass

        targets = list(target_paths) if target_paths is not None else self.paths.legacy_dockets_sync_targets()
        if not targets:
            return {
                "ok": True,
                "status": "NO_TARGETS",
                "deleted": False,
                "deletedCount": 0,
                "billedLocked": False,
                "billedInvoice": "",
                "warnings": [],
                "results": [],
            }

        sync_map = self._load_json_state(self._sync_map_path())
        results: list[dict[str, Any]] = []
        deleted_count = 0
        billed_locked = False
        billed_invoice = ""
        warnings: list[str] = []

        for wb_path in targets:
            if not wb_path.is_file():
                continue
            try:
                res = self._apply_delete_to_workbook(wb_path, clean_eid, entry_payload, sync_map)
                results.append(res)
                if res.get("deleted"):
                    deleted_count += 1
                if res.get("billedLocked"):
                    billed_locked = True
                    billed_invoice = str(res.get("billedInvoice") or billed_invoice)
                    if res.get("warning"):
                        warnings.append(str(res["warning"]))
            except Exception as exc:
                warn_msg = f"Could not delete docket from {wb_path.name}: {exc}"
                logger.warning("[legacy_dockets_sync] %s", warn_msg)
                warnings.append(warn_msg)
                results.append(
                    {
                        "ok": False,
                        "deleted": False,
                        "workbookPath": str(wb_path),
                        "warning": warn_msg,
                    }
                )

        self._save_json_state(self._sync_map_path(), sync_map)
        return {
            "ok": not billed_locked,
            "status": "BILLED_LOCKED" if billed_locked else ("DELETED" if deleted_count > 0 else "NOT_FOUND"),
            "deleted": deleted_count > 0,
            "deletedCount": deleted_count,
            "billedLocked": billed_locked,
            "billedInvoice": billed_invoice,
            "warning": warnings[0] if warnings else "",
            "warnings": warnings,
            "results": results,
            "entryId": clean_eid,
        }


