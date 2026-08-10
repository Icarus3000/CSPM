import re

import logging

from decimal import Decimal

from functools import partial

from typing import Dict, List, Any, Optional

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot, Property

from backend.workers import Worker

from domain import schema_constants as sc

def clean_desc(text):

    import re

    text = text.replace("discusion", "discussion")

    text = text.replace("Discusion", "Discussion")

    text = text.replace("T2060s", "T2060 forms")

    text = re.sub(r'(?i)\bre\b', 'regarding', text)

    text = re.sub(r'(?i)\bemail to\b', 'correspondence with', text)

    text = re.sub(r'(?i)\bemails to\b', 'correspondence with', text)

    text = re.sub(r'(?i)\breview research memos\b', 'review of research memoranda', text)

    text = re.sub(r'(?i)\breview research memo\b', 'review of research memorandum', text)

    

    if text:

        text = text[0].upper() + text[1:]

    

    # Ensure it ends with a period if it doesn't already

    if text and not text.endswith(('.', ';', ':')):

        text += '.'

        

    return text

logger = logging.getLogger(__name__)

class BillingController(QObject):

    """

    QML-facing controller for billing workflows:

      - Loading unbilled WIP

      - Creating / managing draft invoices

      - Finalising invoices and generating documents

    """

    # ── Signals ──────────────────────────────────────────────────────────────

    wipDataLoaded = Signal('QVariantList')

    draftCreated = Signal('QVariantMap')

    draftUpdated = Signal('QVariantMap')

    draftDeleted = Signal('QVariantMap')

    draftsDeleted = Signal('QVariantMap')

    draftFinalized = Signal('QVariantMap')

    draftReversed = Signal('QVariantMap')

    invoiceHtmlReady = Signal(str)

    pdfExportFinished = Signal(str, bool)

    error = Signal(str)

    toast = Signal(str)
    
    customInvoiceDirChanged = Signal()

    @Property(str, notify=customInvoiceDirChanged)
    def customInvoiceDir(self):
        from PySide6.QtCore import QSettings
        return str(QSettings("DigitalShovel", "CSPM").value("custom_invoice_dir", ""))

    @Slot()
    def promptCustomInvoiceDir(self):
        from PySide6.QtWidgets import QFileDialog, QApplication
        from PySide6.QtCore import QSettings
        import os

        parent = QApplication.activeWindow()
        current_dir = self.customInvoiceDir
        if not current_dir or not os.path.isdir(current_dir):
            current_dir = os.path.expanduser("~")

        selected_dir = QFileDialog.getExistingDirectory(parent, "Select Invoice Root Folder", current_dir)
        
        if selected_dir:
            settings = QSettings("DigitalShovel", "CSPM")
            settings.setValue("custom_invoice_dir", selected_dir)
            settings.sync()
            self.customInvoiceDirChanged.emit()

    def __init__(self, excel_repo, invoice_draft_service, invoice_document_service):

        super().__init__()

        self._excel_repo = excel_repo

        self._draft_svc = invoice_draft_service

        self._doc_svc = invoice_document_service

        self._threadpool = QThreadPool.globalInstance()
        self._active_workers = set()
        self._payload_cache = {}

    # ── Worker helpers ───────────────────────────────────────────────────────

    def _start_worker(self, worker):

        self._active_workers.add(worker)

        self._threadpool.start(worker)

    def _release_worker(self, worker):

        self._active_workers.discard(worker)

    # ── WIP Loading ──────────────────────────────────────────────────────────

    @Slot()

    def loadUnbilledWip(self):

        """Load all unbilled WIP time entries, grouped by client."""

        worker = Worker(self._load_unbilled_wip_impl, name="loadUnbilledWip")

        worker.signals.result.connect(partial(self._on_wip_loaded, worker))

        worker.signals.error.connect(partial(self._on_wip_error, worker))

        self._start_worker(worker)

    def _load_unbilled_wip_impl(self):

        from repositories.excel_repo import TBL_TIME, TBL_CLIENTS, TBL_MATTERS

        

        # Build lookups for Client and Matter names

        clients = self._excel_repo._read_table_rows(TBL_CLIENTS)

        profiles = self._excel_repo._read_table_rows(sc.TBL_CLIENT_PROFILES)

        client_map = {}

        client_parent_map = {}

        for c in clients:

            c_id = str(c.get(sc.COL_CLIENT_ID) or c.get("Client ID") or "").strip()
            c_name = str(c.get(sc.COL_CLIENT_NAME) or c.get("Client Name") or "").strip()

            if c_id:

                client_map[c_id] = c_name or c_id

        for p in profiles:

            c_id = str(p.get(sc.COL_PROFILE_CLIENT_ID) or "").strip()

            p_id = str(p.get(sc.COL_PROFILE_PARENT_ID) or "").strip()

            if c_id and p_id:

                client_parent_map[c_id] = p_id

        parents = self._excel_repo._read_table_rows(sc.TBL_PARENTS)

        parent_map = {}

        for p in parents:

            p_id = str(p.get(sc.COL_PARENT_ID) or p.get("Parent ID") or "").strip()
            p_name = str(p.get(sc.COL_PARENT_NAME) or p.get("Parent Name") or "").strip()

            if p_id:

                parent_map[p_id] = p_name or p_id

        matters = self._excel_repo._read_table_rows(TBL_MATTERS)

        matter_map = {}

        for m in matters:

            m_id = str(m.get(sc.COL_MATTER_ID) or "").strip()

            m_name = str(m.get(sc.COL_MATTER_NAME) or "").strip()

            m_desc = str(m.get(sc.COL_MATTER_DESCRIPTION) or "").strip()

            m_type = str(m.get(sc.COL_MATTER_TYPE) or "").strip()

            m_name = str(m.get(sc.COL_MATTER_NAME) or "").strip()

            m_number = str(m.get(sc.COL_MATTER_NUMBER) or "").strip()

            display = m_desc if m_desc else (m_type if m_type else m_name)

            if not display:

                display = str(m.get(sc.COL_MATTER_DISPLAY_NAME) or "").strip()

            

            if display.startswith("Legacy Matter "):

                display = display.replace("Legacy Matter ", "").strip()

            import re

            m_match = re.search(r'(\d{2}-\d{4})$', m_number)

            short_num = m_match.group(1) if m_match else m_number

            if short_num:

                if display and not display.endswith(short_num):

                    display = f"{display} - {short_num}"

                elif not display:

                    display = short_num

            if m_id:

                matter_map[m_id] = display or m_id

        rows = self._excel_repo._read_table_rows(TBL_TIME)

        wip_rows = []

        for row in rows:

            invoice_ref = str(row.get(sc.COL_TIME_INVOICE_REF) or "").strip()

            status = str(row.get(sc.COL_TIME_STATUS) or "").strip().lower()

            invoice_status = str(row.get(sc.COL_TIME_INVOICE_STATUS) or "").strip().lower()

            # WIP = not already billed

            # Note: We now INCLUDE items that have an invoice_ref (i.e. in Draft)

            # but we still exclude them if they are actually finalized/billed.

            if invoice_status in ("billed", "finalized"):

                continue

            if status == "billed":

                continue

            try:

                net = float(row.get(sc.COL_TIME_NET) or 0)

            except (ValueError, TypeError):

                net = 0.0

            try:

                hours = float(row.get(sc.COL_TIME_HOURS) or 0)

            except (ValueError, TypeError):

                hours = 0.0

            try:

                hst = float(row.get(sc.COL_TIME_HST) or 0)

            except (ValueError, TypeError):

                hst = 0.0

            client_id_raw = str(row.get(sc.COL_TIME_CLIENT_ID) or "")

            client_id = client_id_raw.split(',')[0].strip() if ',' in client_id_raw else client_id_raw.strip()

            matter_id_raw = str(row.get(sc.COL_TIME_MATTER_ID) or "")

            matter_id = matter_id_raw.split(',')[0].strip() if ',' in matter_id_raw else matter_id_raw.strip()

            time_parent_id_raw = str(row.get(sc.COL_TIME_PARENT_ID) or "").strip()

            time_parent_id = time_parent_id_raw.split(',')[0].strip() if ',' in time_parent_id_raw else time_parent_id_raw.strip()

            # The Client Profile's ParentClientID is the source of truth for the billing client.

            # If not set in the profile, fall back to the time entry's ParentID, or the client_id itself.

            profile_parent = client_parent_map.get(client_id)

            parent_id = profile_parent if profile_parent else (time_parent_id if time_parent_id else client_id)

            

            if parent_id in parent_map:

                parent_name = parent_map[parent_id]

            else:

                parent_name = client_map.get(parent_id, parent_id)

            wip_rows.append({

                "entryId": str(row.get(sc.COL_TIME_ENTRY_ID) or ""),

                "date": str(row.get(sc.COL_TIME_DATE) or ""),

                "clientId": client_id,

                "clientName": client_map.get(client_id, client_id),

                "matterId": matter_id,

                "matterName": matter_map.get(matter_id, matter_id),

                "parentId": parent_id,

                "parentName": parent_name,

                "description": clean_desc(str(row.get(sc.COL_TIME_DESC) or "")),

                "hours": round(hours, 2),

                "rate": float(row.get(sc.COL_TIME_RATE) or 0),

                "net": round(net, 2),

                "hst": round(hst, 2),

                "invoiceRef": invoice_ref,

                "invoiceStatus": str(row.get(sc.COL_TIME_INVOICE_STATUS) or ""),
                
                "status": status.title() if status else "Draft",
                
                "sharePct": float(self._excel_repo._parse_float(row.get(sc.COL_TIME_SHARE_PCT)) or 100.0) if self._excel_repo._parse_float(row.get(sc.COL_TIME_SHARE_PCT)) is not None else 100.0,
                
                "grossToClient": float(self._excel_repo._parse_float(row.get(sc.COL_TIME_GROSS)) or 0.0),
                
                "rawSeconds": int(self._excel_repo._parse_float(row.get(sc.COL_TIME_SECONDS)) or 0),

            })

        # Sort by client, then date

        wip_rows.sort(key=lambda r: (r["clientName"], r["date"]))

        return wip_rows

    def _on_wip_loaded(self, worker, result):

        try:

            self.wipDataLoaded.emit(list(result or []))

        finally:

            self._release_worker(worker)

    def _on_wip_error(self, worker, err_tuple):

        try:

            exctype, value, tb_str = err_tuple

            self.error.emit(f"Could not load WIP data: {value}")

            self.wipDataLoaded.emit([])

        finally:

            self._release_worker(worker)

    # ── Draft Creation ───────────────────────────────────────────────────────

    @Slot(str, str, list)

    def createDraft(self, client_id, client_name, time_entry_ids):
        """Create a draft invoice from the selected WIP entry IDs."""
        py_time_ids = [str(x) for x in time_entry_ids]
        if not py_time_ids:
            message = "Select at least one time docket, fee entry, or disbursement before creating a draft invoice."
            self.toast.emit(message)
            self.draftCreated.emit({"ok": False, "message": message})
            return
        worker = Worker(
            self._draft_svc.create_draft,
            str(client_id),
            str(client_name),
            py_time_ids,
            None,
            "matter", # Default grouping
            name="createDraft",
        )

        worker.signals.result.connect(partial(self._on_draft_created, worker))

        worker.signals.error.connect(partial(self._on_draft_error, worker))

        self._start_worker(worker)

    @Slot(str, str, 'QVariantList', str)

    def createDraftWithGrouping(self, client_id, client_name, time_entry_ids, grouping_pref):
        """Create a draft invoice from the selected WIP entry IDs with a specific grouping preference."""
        py_all_ids = [str(x) for x in time_entry_ids]
        if not py_all_ids:
            message = "Select at least one time docket, fee entry, or disbursement before creating a draft invoice."
            self.toast.emit(message)
            self.draftCreated.emit({"ok": False, "message": message})
            return
        
        from domain import schema_constants as sc
        disb_rows = self._excel_repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        disb_ids = [str(r.get(sc.COL_DISB_ID) or "") for r in disb_rows]
        
        time_ids = []
        actual_disb_ids = []
        for d in py_all_ids:
            if d in disb_ids:
                actual_disb_ids.append(d)
            else:
                time_ids.append(d)

        worker = Worker(
            self._draft_svc.create_draft,
            str(client_id),
            str(client_name),
            time_ids,
            actual_disb_ids,
            str(grouping_pref),
            name="createDraft",
        )

        worker.signals.result.connect(partial(self._on_draft_created, worker))
        worker.signals.error.connect(partial(self._on_draft_error, worker))
        self._start_worker(worker)

    def _on_draft_created(self, worker, result):

        try:

            draft_num = str(result or "")

            if draft_num:

                self.toast.emit(f"Draft invoice created: {draft_num}")

                self.draftCreated.emit({"draftNum": draft_num})

        except Exception as e:

            self.error.emit(f"Failed to process draft result: {str(e)}")

            self.draftCreated.emit({"ok": False})

        finally:

            self._release_worker(worker)

    def _on_draft_error(self, worker, err_tuple):

        try:

            exctype, value, tb_str = err_tuple

            self.error.emit(f"Could not create draft: {value}")

            self.draftCreated.emit({"ok": False, "message": str(value)})

        finally:

            self._release_worker(worker)

    # ── Draft Details ────────────────────────────────────────────────────────

    @Slot(str, result='QVariantMap')

    def getDraft(self, draft_num):

        """Get a specific draft invoice's details."""

        try:

            draft = self._draft_svc.get_draft(str(draft_num))

            if draft:

                return dict(draft)

            return {"ok": False, "message": f"Draft {draft_num} not found"}

        except Exception as exc:

            self.error.emit(f"Could not load draft: {exc}")

            return {"ok": False, "message": str(exc)}

    @Slot(str, result='QVariantList')

    def getDraftLineItems(self, draft_num):

        """Get the time entries associated with a draft invoice."""

        try:

            from repositories.excel_repo import TBL_TIME

            rows = self._excel_repo._read_table_rows(TBL_TIME)

            items = []

            for row in rows:

                if str(row.get(sc.COL_TIME_INVOICE_REF) or "") == str(draft_num):

                    try:
                        net = float(row.get(sc.COL_TIME_GROSS) or row.get(sc.COL_TIME_NET) or 0)

                    except (ValueError, TypeError):

                        net = 0.0

                    try:

                        hours = float(row.get(sc.COL_TIME_HOURS) or 0)

                    except (ValueError, TypeError):

                        hours = 0.0

                    items.append({

                        "entryId": str(row.get(sc.COL_TIME_ENTRY_ID) or ""),

                        "date": str(row.get(sc.COL_TIME_DATE) or ""),

                        "description": clean_desc(str(row.get(sc.COL_TIME_DESC) or "")),

                        "hours": round(hours, 2),

                        "rate": float(row.get(sc.COL_TIME_RATE) or 0),

                        "amount": round(net, 2),

                        "isFee": "entrytype:fee" in str(row.get(sc.COL_TIME_LOCK_AUDIT) or "").lower(),

                        "matterId": str(row.get(sc.COL_TIME_MATTER_ID) or ""),

                    })

            draft_sort_order = []
            drafts = self._excel_repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
            for d in drafts:
                if str(d.get(sc.COL_DRAFT_INVOICE_NUM) or "") == str(draft_num):
                    order_str = str(d.get(sc.COL_DRAFT_CUSTOM_SORT_ORDER) or "")
                    if order_str:
                        draft_sort_order = [x.strip() for x in order_str.split(",")]
                    break

            if draft_sort_order:
                # Create a map for fast lookup
                order_map = {entry_id: i for i, entry_id in enumerate(draft_sort_order)}
                items.sort(key=lambda r: order_map.get(r["entryId"], 999999))
            else:
                items.sort(key=lambda r: r["date"])

            return items

        except Exception as exc:

            self.error.emit(f"Could not load draft line items: {exc}")

            return []

    @Slot(str, str, 'QVariantMap')

    def updateDraftLineItem(self, draft_num, entry_id, data):
        self._payload_cache.pop(f"{draft_num}_True_None", None)

        try:

            self._draft_svc.update_line_item(str(entry_id), data)

            self.draftUpdated.emit({})

            self.previewInvoiceHtml(str(draft_num), "Concept_A2")

            self.toast.emit("Docket updated")

        except Exception as exc:

            self.error.emit(f"Could not update docket: {exc}")

    @Slot(str, str, bool)

    def removeDraftLineItem(self, draft_num, entry_id, delete_completely):
        self._payload_cache.pop(f"{draft_num}_True_None", None)

        try:

            self._draft_svc.remove_line_item(str(entry_id), delete_completely)

            self.draftUpdated.emit({})

            self.previewInvoiceHtml(str(draft_num), "Concept_A2")

            self.toast.emit("Docket removed")

        except Exception as exc:

            self.error.emit(f"Could not remove docket: {exc}")

    @Slot(str, 'QVariantMap')

    def addDraftLineItem(self, draft_num, data):
        self._payload_cache.pop(f"{draft_num}_True_None", None)

        try:

            self._draft_svc.add_line_item(str(draft_num), data)

            self.draftUpdated.emit({})

            self.previewInvoiceHtml(str(draft_num), "Concept_A2")

            self.toast.emit("Docket added")

        except Exception as exc:

            self.error.emit(f"Could not add docket: {exc}")

    # ── Discount ─────────────────────────────────────────────────────────────

    @Slot(str, str)

    def updateDraftDate(self, draft_num, new_date_str):

        """Update the issue date of a draft invoice."""

        try:

            from datetime import date

            normalized_date = str(new_date_str or "").strip()
            if not normalized_date:
                raise ValueError("Invoice date is required.")
            parsed_date = date.fromisoformat(normalized_date)
            if parsed_date.isoformat() != normalized_date:
                raise ValueError("Use YYYY-MM-DD for the invoice date.")

            drafts = self._excel_repo._read_table_rows(sc.TBL_DRAFT_INVOICES)

            updated = False

            for d in drafts:

                if str(d.get(sc.COL_DRAFT_INVOICE_NUM) or "") == str(draft_num):

                    d[sc.COL_DRAFT_DATE] = normalized_date + "T00:00:00"

                    updated = True

                    break

            if updated:

                self._excel_repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)

                self._payload_cache.clear()

                draft = self._draft_svc.get_draft(str(draft_num))

                self.toast.emit(f"Draft date updated to {normalized_date}")

                self.draftUpdated.emit(dict(draft) if draft else {})

                self.previewInvoiceHtml(str(draft_num), "Concept_A2")

            else:

                self.error.emit(f"Draft {draft_num} was not found.")

        except (TypeError, ValueError) as exc:
            self.error.emit(f"Could not update invoice date: {exc}")
        except Exception as exc:
            logger.exception("Could not update invoice date for draft %s", draft_num)
            self.error.emit(f"Could not update invoice date: {exc}")

    @Slot(str, str)
    def updateDraftGrouping(self, draft_num, grouping_pref):
        self._payload_cache.pop(f"{draft_num}_True_None", None)
        """Update the grouping preference of a draft invoice."""
        try:
            drafts = self._excel_repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
            updated = False
            for d in drafts:
                if str(d.get(sc.COL_DRAFT_INVOICE_NUM) or "") == str(draft_num):
                    d[sc.COL_DRAFT_GROUPING_PREF] = grouping_pref
                    updated = True
                    break
            if updated:
                self._excel_repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
                draft = self._draft_svc.get_draft(str(draft_num))
                self.toast.emit(f"Draft grouping updated to {grouping_pref}")
                self.draftUpdated.emit(dict(draft) if draft else {})
                self.previewInvoiceHtml(str(draft_num), "Concept_A2")
        except Exception as e:
            self.toast.emit(f"Failed to update grouping: {str(e)}")

    @staticmethod
    def _normalize_reconciliation_mode(mode: Any) -> str:
        """Map current and legacy draft values onto the two supported choices."""
        normalized = str(mode or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")
        if normalized in {"discount", "discountline"}:
            return "discount_line"
        return "hidden_adjustment"

    @Slot(str, str)
    def updateDraftReconciliationMode(self, draft_num, mode):
        """Persist the custom-fee reconciliation preference for a draft."""
        self._payload_cache.clear()
        try:
            drafts = self._excel_repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
            normalized_mode = self._normalize_reconciliation_mode(mode)
            updated = False
            for draft in drafts:
                if str(draft.get(sc.COL_DRAFT_INVOICE_NUM) or "") == str(draft_num):
                    draft[sc.COL_DRAFT_RECONCILIATION_MODE] = normalized_mode
                    updated = True
                    break

            if not updated:
                self.error.emit(f"Draft {draft_num} was not found.")
                return

            self._excel_repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
            refreshed_draft = self._draft_svc.get_draft(str(draft_num))
            self.draftUpdated.emit(dict(refreshed_draft) if refreshed_draft else {})
            self.previewInvoiceHtml(str(draft_num), "Concept_A2")
        except (KeyError, TypeError, ValueError) as exc:
            self.error.emit(f"Could not save reconciliation mode: {exc}")
        except Exception as exc:
            logger.exception("Could not save reconciliation mode for draft %s", draft_num)
            self.error.emit(f"Could not save reconciliation mode: {exc}")

    @Slot(str, str)
    def updateDraftDocketDisplayMode(self, draft_num, mode):
        """Persist how time dockets appear beside a custom flat fee."""
        self._payload_cache.clear()
        try:
            normalized_mode = str(mode or "show").strip().lower()
            if normalized_mode not in {"show", "hide", "tasks"}:
                normalized_mode = "show"

            drafts = self._excel_repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
            updated = False
            for draft in drafts:
                if str(draft.get(sc.COL_DRAFT_INVOICE_NUM) or "") == str(draft_num):
                    draft["DocketDisplayMode"] = normalized_mode
                    updated = True
                    break

            if not updated:
                self.error.emit(f"Draft {draft_num} was not found.")
                return

            self._excel_repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
            refreshed_draft = self._draft_svc.get_draft(str(draft_num))
            self.draftUpdated.emit(dict(refreshed_draft) if refreshed_draft else {})
            self.previewInvoiceHtml(str(draft_num), "Concept_A2")
        except (KeyError, TypeError, ValueError) as exc:
            self.error.emit(f"Could not save docket display mode: {exc}")
        except Exception as exc:
            logger.exception("Could not save docket display mode for draft %s", draft_num)
            self.error.emit(f"Could not save docket display mode: {exc}")

    @Slot(str, list)
    def updateDraftSortOrder(self, draft_num, entry_ids):
        self._payload_cache.pop(f"{draft_num}_True_None", None)
        try:
            drafts = self._excel_repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
            updated = False
            for d in drafts:
                if str(d.get(sc.COL_DRAFT_INVOICE_NUM) or "") == str(draft_num):
                    d[sc.COL_DRAFT_CUSTOM_SORT_ORDER] = ",".join([str(x) for x in entry_ids])
                    updated = True
                    break
            if updated:
                self._excel_repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
                self.draftUpdated.emit({})
                self.previewInvoiceHtml(str(draft_num), "Concept_A2")
        except Exception as e:
            self.error.emit(f"Failed to update sort order: {str(e)}")

    @Slot(str, dict)
    def updateDraftMeta(self, draft_num, meta_changes):
        self._payload_cache.clear()
        try:
            drafts = self._excel_repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
            updated = False
            for d in drafts:
                if str(d.get(sc.COL_DRAFT_INVOICE_NUM) or "") == str(draft_num):
                    if "isFlatFee" in meta_changes:
                        d[sc.COL_DRAFT_IS_FLAT_FEE] = "True" if meta_changes["isFlatFee"] else "False"
                    if "showTotalHours" in meta_changes:
                        d[sc.COL_DRAFT_SHOW_TOTAL_HOURS] = "True" if meta_changes["showTotalHours"] else "False"
                    if "flatFeeAmount" in meta_changes:
                        try:
                            d[sc.COL_DRAFT_FLAT_FEE_AMOUNT] = float(meta_changes["flatFeeAmount"] or 0.0)
                        except (KeyError, TypeError, ValueError):
                            d[sc.COL_DRAFT_FLAT_FEE_AMOUNT] = 0.0
                    if "flatFeeDesc" in meta_changes:
                        d[sc.COL_DRAFT_FLAT_FEE_DESC] = str(meta_changes["flatFeeDesc"])
                    if "reconciliationMode" in meta_changes:
                        d[sc.COL_DRAFT_RECONCILIATION_MODE] = self._normalize_reconciliation_mode(
                            meta_changes["reconciliationMode"]
                        )
                    if "docketDisplayMode" in meta_changes:
                        d["DocketDisplayMode"] = str(meta_changes["docketDisplayMode"])
                    updated = True
                    break
            if updated:
                self._excel_repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
                self.draftUpdated.emit({})
                self.previewInvoiceHtml(str(draft_num), "Concept_A2")
        except (KeyError, TypeError, ValueError) as e:
            self.error.emit(f"Failed to update draft metadata: {e}")
        except Exception as e:
            logger.exception(f"Failed to update draft meta: {e}")

    @Slot(str, str, float)

    def applyDiscount(self, draft_num, discount_type, discount_value):

        """Apply a discount to a draft invoice."""

        try:

            self._payload_cache.pop(f"{draft_num}_True_None", None)
            self._draft_svc.apply_discount(

                str(draft_num),

                str(discount_type),

                Decimal(str(discount_value)),

            )

            draft = self._draft_svc.get_draft(str(draft_num))

            self.toast.emit(f"Discount applied to {draft_num}")

            self.draftUpdated.emit(dict(draft) if draft else {})

        except Exception as exc:

            self.error.emit(f"Could not apply discount: {exc}")

    @Slot(str, float)

    def applyAgencySplit(self, draft_num, percent):

        """Apply an agency split to a draft invoice."""

        try:

            self._payload_cache.pop(f"{draft_num}_True_None", None)
            self._draft_svc.apply_agency_split(

                str(draft_num),

                Decimal(str(percent)),

            )

            draft = self._draft_svc.get_draft(str(draft_num))

            self.toast.emit(f"Agency split applied to {draft_num}")

            self.draftUpdated.emit(dict(draft) if draft else {})

        except Exception as exc:

            self.error.emit(f"Could not apply agency split: {exc}")

    # ── Finalize & Delete ───────────────────────────────────────────────────

    @Slot(str, result='QVariantMap')
    def deleteDraft(self, draft_num):
        self._payload_cache.pop(f"{draft_num}_True_None", None)
        """Delete a single draft invoice and revert its WIP."""
        try:
            success = self._draft_svc.delete_draft(str(draft_num))
            if success:
                message = f"Draft {draft_num} deleted"
                self.toast.emit(message)
                self.draftUpdated.emit({})  # Trigger refresh
                return {"ok": True, "message": message}
            else:
                self.error.emit(f"Failed to delete draft {draft_num}")
                return {"ok": False, "message": "Backend deletion failed"}
        except Exception as exc:
            self.error.emit(f"Could not delete draft: {exc}")
            return {"ok": False, "message": str(exc)}

    @Slot('QVariantList', result='QVariantMap')
    def deleteDrafts(self, draft_nums):
        """Delete multiple drafts."""
        try:
            for num in draft_nums:
                self._draft_svc.delete_draft(str(num))
            message = f"Deleted {len(draft_nums)} drafts"
            self.toast.emit(message)
            self.draftUpdated.emit({})
            return {"ok": True, "message": message}
        except Exception as exc:
            self.error.emit(f"Could not delete drafts: {exc}")
            return {"ok": False, "message": str(exc)}

    @Slot(str, result='QVariantMap')
    def deleteLedgerEntry(self, ledger_id):
        """Hard delete a finalized ledger entry (for manual correction)."""
        try:
            result = self._repo.delete_ledger_entry(ledger_id)
            if result.get("ok"):
                self.toast.emit(result["message"])
            else:
                self.error.emit(result.get("message", "Failed to delete ledger entry"))
            return result
        except Exception as exc:
            self.error.emit(f"Could not delete ledger entry: {exc}")
            return {"ok": False, "message": str(exc)}

    @Slot(str, str, str)

    def finalizeDraft(self, draft_num, final_invoice_num, save_dir):

        """Finalize a draft into a real invoice."""

        worker = Worker(

            self._draft_svc.finalize_draft,

            str(draft_num),

            str(final_invoice_num),

            str(save_dir),

            name="finalizeDraft",

        )

        worker.signals.result.connect(partial(self._on_draft_finalized, worker, final_invoice_num))

        worker.signals.error.connect(partial(self._on_finalize_error, worker))

        self._start_worker(worker)

    def _on_draft_finalized(self, worker, invoice_num, result):

        try:

            self.toast.emit(f"Invoice {invoice_num} finalized successfully!")

            self.draftFinalized.emit({"ok": True, "invoiceNum": invoice_num})

        finally:

            self._release_worker(worker)

    def _on_finalize_error(self, worker, err_tuple):

        try:

            exctype, value, tb_str = err_tuple

            self.error.emit(f"Could not finalize invoice: {value}")

            self.draftFinalized.emit({"ok": False, "message": str(value)})

        finally:

            self._release_worker(worker)

    @Slot(str)
    def openInvoicePdf(self, invoice_num):
        """Open the finalized invoice PDF."""
        try:
            import os
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            from PySide6.QtCore import QStandardPaths

            invoice_log = self._draft_svc.repo._read_table_rows(sc.TBL_INVOICE_LOG)
            client_name = ""
            file_path = ""
            for row in invoice_log:
                if str(row.get(sc.COL_INV_INVOICE_NUM) or "").strip() == str(invoice_num):
                    file_path = str(row.get(sc.COL_INV_FILE_PATH) or "").strip()
                    client_name = str(row.get(sc.COL_INV_CLIENT_NAME) or "").strip()
                    break

            if file_path and os.path.exists(file_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
                self.toast.emit("Opening PDF...")
                return

            # Smart Fallback
            from PySide6.QtCore import QSettings
            from PySide6.QtWidgets import QFileDialog
            
            docs_paths = QStandardPaths.standardLocations(QStandardPaths.DocumentsLocation)
            desktop_paths = QStandardPaths.standardLocations(QStandardPaths.DesktopLocation)
            
            search_paths = []
            settings = QSettings("DigitalShovel", "CSPM")
            custom_dir = settings.value("custom_invoice_dir", "")
            if custom_dir and os.path.exists(custom_dir):
                search_paths.append(custom_dir)
                
            search_paths.extend(docs_paths + desktop_paths)
            
            found_path = None
            inv_marker = f"INV {invoice_num}"
            for base_dir in search_paths:
                if found_path: break
                for root_dir, dirs, files in os.walk(base_dir):
                    if root_dir.count(os.sep) - base_dir.count(os.sep) > 3:
                        del dirs[:]
                        continue
                    for f in files:
                        if f.endswith(".pdf") and inv_marker in f:
                            # It's highly likely to be the file if the invoice number matches
                            found_path = os.path.join(root_dir, f)
                            break
                    if found_path:
                        break

            if found_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(found_path))
                self.toast.emit("Found and opened PDF.")
            else:
                # Prompt the user to manually select the root folder
                self.toast.emit("Could not locate PDF automatically. Please select your invoice root folder.")
                selected_dir = QFileDialog.getExistingDirectory(
                    None,
                    "Select Root Folder for Invoices",
                    "",
                    QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
                )
                if selected_dir and os.path.exists(selected_dir):
                    # Save this directory to QSettings to make future searches smarter
                    settings.setValue("custom_invoice_dir", selected_dir)
                    self.customInvoiceDirChanged.emit()
                    self.toast.emit(f"Remembered invoice root folder. Searching...")
                    
                    # Search again in the newly selected directory
                    found_path_retry = None
                    for root_dir, dirs, files in os.walk(selected_dir):
                        if root_dir.count(os.sep) - selected_dir.count(os.sep) > 3:
                            del dirs[:]
                            continue
                        for f in files:
                            if f.endswith(".pdf") and inv_marker in f:
                                found_path_retry = os.path.join(root_dir, f)
                                break
                        if found_path_retry:
                            break
                            
                    if found_path_retry:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(found_path_retry))
                        self.toast.emit("Found and opened PDF.")
                    else:
                        self.error.emit(f"Could not locate PDF for {invoice_num} even in selected folder.")
                else:
                    self.error.emit(f"Could not locate PDF for {invoice_num}")
                
        except Exception as e:
            self.error.emit(f"Error opening PDF: {str(e)}")

    # ── Reverse ──────────────────────────────────────────────────────────────

    @Slot(str, str, str, str)
    def reverseInvoice(self, invoice_num, source_pdf_path, pdf_action, target_dir):
        """Reverse a finalized invoice."""
        try:
            self._draft_svc.reverse_invoice(str(invoice_num), str(source_pdf_path), str(pdf_action), str(target_dir))
            self.toast.emit(f"Invoice {invoice_num} reversed.")

            self.draftReversed.emit({"ok": True, "invoiceNum": invoice_num})

        except Exception as exc:

            self.error.emit(f"Could not reverse invoice: {exc}")
            self.draftReversed.emit({"ok": False, "message": str(exc)})

    @Slot(str, str, str, str)
    def reverseAndEditInvoice(self, invoice_num, source_pdf_path, pdf_action, target_dir):
        """Reverse a finalized invoice and create a draft for editing."""
        try:
            new_draft_num = self._draft_svc.reverse_and_edit_invoice(str(invoice_num), str(source_pdf_path), str(pdf_action), str(target_dir))
            self.toast.emit(f"Invoice {invoice_num} reversed and loaded into builder.")
            self.draftReversed.emit({"ok": True, "invoiceNum": invoice_num, "newDraftNum": new_draft_num})
        except Exception as exc:
            self.error.emit(f"Could not reverse and edit invoice: {exc}")
            self.draftReversed.emit({"ok": False, "message": str(exc)})

    # ── HTML Preview ─────────────────────────────────────────────────────────

    _last_preview_html = ""
    _last_preview_draft_num = ""

    @Slot(str, result=str)
    def getCachedPreviewHtml(self, draft_num):
        """Return the last generated preview HTML if it matches the requested draft, else empty string."""
        if self._last_preview_draft_num == str(draft_num) and self._last_preview_html:
            return self._last_preview_html
        return ""

    @Slot(str, str)

    def previewInvoiceHtml(self, draft_num, template_name):

        """Generate an HTML preview of the draft invoice."""

        self._last_preview_draft_num = str(draft_num)

        worker = Worker(

            self._generate_preview_impl,

            str(draft_num),

            str(template_name) or "Concept_A2",

            name="previewInvoiceHtml",

        )

        worker.signals.result.connect(partial(self._on_preview_ready, worker))

        worker.signals.error.connect(partial(self._on_preview_error, worker))

        self._start_worker(worker)

    def _build_invoice_payload(self, draft_num, is_draft=True, final_invoice_num=None):

        cache_key = f"{draft_num}_{is_draft}_{final_invoice_num}"
        if cache_key in self._payload_cache:
            payload = self._payload_cache[cache_key]
            # Refresh draft metadata (like discount/totals) but keep heavy line items cached
            fresh_draft = self._draft_svc.get_draft(draft_num)
            if fresh_draft:
                payload["invoice"] = dict(fresh_draft)
            self._payload_cache[cache_key] = payload
            return payload

        draft = self._draft_svc.get_draft(draft_num)

        if not draft:

            raise ValueError(f"Draft {draft_num} not found")

        from repositories.excel_repo import TBL_TIME

        rows = self._excel_repo._read_table_rows(TBL_TIME)

        matters_map = {}
        service_client_names = []
        service_matter_names = []
        service_client_cache = {}
        service_matter_cache = {}
        has_third_party_service_matter = False

        def append_unique(values, value):
            value = str(value or "").strip()
            if value and value.casefold() not in {item.casefold() for item in values}:
                values.append(value)

        def service_client_name(client_key):
            """Resolve the client receiving the services, not merely the bill-to client."""
            lookup = str(client_key or "").strip()
            if not lookup:
                return ""

            cache_key = lookup.casefold()
            if cache_key not in service_client_cache:
                if cache_key == client_id.casefold():
                    profile = client_profile
                elif cache_key == str(billing_client_id or "").casefold():
                    profile = billing_profile
                else:
                    result = self._excel_repo.get_client_profile(lookup)
                    profile = result.get("client", {}) if result.get("ok") else {}
                service_client_cache[cache_key] = (
                    profile.get("displayName") or profile.get("clientName") or lookup
                )
            return service_client_cache[cache_key]

        def service_matter_name(matter_key, service_client_id=""):
            """Resolve a human-readable matter label for the invoice service context."""
            nonlocal has_third_party_service_matter
            lookup = str(matter_key or "").strip()
            if not lookup:
                return ""

            cache_key = lookup.casefold()
            if cache_key not in service_matter_cache:
                result = self._excel_repo.get_matter_profile(lookup)
                matter = result.get("matter", {}) if result.get("ok") else {}
                matter_number = str(matter.get("matterNumber") or "").strip()
                matter_name = str(
                    matter.get("displayName") or matter.get("matterName") or matter.get("description") or lookup
                ).strip()
                matter_client_id = str(matter.get("clientId") or service_client_id or "").strip()
                is_third_party_billing = bool(
                    matter_client_id
                    and str(billing_client_id or "").strip()
                    and matter_client_id.casefold() != str(billing_client_id).strip().casefold()
                )
                if is_third_party_billing:
                    has_third_party_service_matter = True
                    plain_description = str(
                        matter.get("description") or matter.get("matterName") or matter_name or lookup
                    ).strip()
                    # A display name is occasionally the matter number plus its
                    # description.  Do not leak that internal code onto a
                    # third-party invoice when it is the only available fallback.
                    if matter_number and plain_description.casefold().startswith(matter_number.casefold()):
                        plain_description = plain_description[len(matter_number):].lstrip(" \t-—–:")
                    service_matter_cache[cache_key] = plain_description or "Matter description not provided"
                else:
                    service_matter_cache[cache_key] = (
                        f"{matter_number} — {matter_name}"
                        if matter_number and matter_name and matter_number.casefold() != matter_name.casefold()
                        else matter_name or matter_number or lookup
                    )
            return service_matter_cache[cache_key]

        total_fees = 0.0

        total_tax = 0.0

        total_hours = 0.0

        

        # Fetch client profiles to resolve billing parent

        client_id_raw = str(draft.get(sc.COL_DRAFT_CLIENT_ID) or "")

        client_id = client_id_raw.split(',')[0].strip() if ',' in client_id_raw else client_id_raw.strip()

        client_profile_res = self._excel_repo.get_client_profile(client_id)

        client_profile = client_profile_res.get("client", {}) if client_profile_res.get("ok") else {}

        billing_client_id = client_profile.get("parentClientId") or client_id

        

        if billing_client_id != client_id:

            billing_profile_res = self._excel_repo.get_client_profile(billing_client_id)

            billing_profile = billing_profile_res.get("client", {}) if billing_profile_res.get("ok") else client_profile

        else:

            billing_profile = client_profile

        city = billing_profile.get('city', '')

        state = billing_profile.get('stateProvince', '')

        postal = billing_profile.get('postalCode', '')

        

        city_state_zip = ""

        if city and state:

            city_state_zip = f"{city}, {state} {postal}".strip()

        else:

            city_state_zip = " ".join(filter(None, [city, state, postal])).replace("  ", " ")

            

        addr_lines = [

            billing_profile.get("addressLine1"),

            billing_profile.get("addressLine2"),

            city_state_zip,

            billing_profile.get("country")

        ]

        addr_lines = [x for x in addr_lines if x]

        discount_type = str(draft.get(sc.COL_DRAFT_DISCOUNT_TYPE) or "None")

        try:

            discount_value = float(draft.get(sc.COL_DRAFT_DISCOUNT_VALUE) or 0)

        except (ValueError, TypeError):

            discount_value = 0.0

            

        try:

            agency_split_percent = float(draft.get(sc.COL_DRAFT_AGENCY_SPLIT_PERCENT) or 0)

        except (ValueError, TypeError):

            agency_split_percent = 0.0

        grouping_pref = str(draft.get(sc.COL_DRAFT_GROUPING_PREF) or "matter").lower()

        for row in rows:

            if str(row.get(sc.COL_TIME_INVOICE_REF) or "") != draft_num:

                continue

            # The billing profile can be a parent or other third party.  Preserve
            # the actual client and matter attached to the billed work so the
            # rendered invoice is unambiguous, including flat-fee-only invoices.
            append_unique(
                service_client_names,
                service_client_name(row.get(sc.COL_TIME_CLIENT_ID)),
            )
            append_unique(
                service_matter_names,
                service_matter_name(
                    row.get(sc.COL_TIME_MATTER_ID),
                    row.get(sc.COL_TIME_CLIENT_ID),
                ),
            )

                

            if grouping_pref == "client":
                group_id = str(row.get(sc.COL_TIME_CLIENT_ID) or "General")
                group_res = self._excel_repo.get_client_profile(group_id)
                group_data = group_res.get("client", {}) if group_res.get("ok") else {}
                cname = group_data.get("displayName") or group_data.get("clientName") or group_id
                display_name = f"RE: {cname}"

            elif grouping_pref == "combined":
                group_id = "General"
                display_name = "Services Rendered"

            else: # "matter"
                group_id = str(row.get(sc.COL_TIME_MATTER_ID) or "General")
                group_res = self._excel_repo.get_matter_profile(group_id)
                group_data = group_res.get("matter", {}) if group_res.get("ok") else {}
                mname = group_data.get("displayName") or group_data.get("description") or group_id
                
                # Check if third-party billing
                c_id_for_matter = str(row.get(sc.COL_TIME_CLIENT_ID) or "")
                if str(billing_client_id or "").casefold() != c_id_for_matter.casefold():
                    mname = service_matter_name(group_id, c_id_for_matter)
                    # Fetch client name to append
                    c_res = self._excel_repo.get_client_profile(c_id_for_matter)
                    c_data = c_res.get("client", {}) if c_res.get("ok") else {}
                    cname = c_data.get("displayName") or c_data.get("clientName") or c_id_for_matter
                    display_name = f"RE: {cname} - {mname}"
                else:
                    display_name = f"RE: {mname}"

            if group_id not in matters_map:

                matters_map[group_id] = {

                    "name": group_id,

                    "display_name": display_name,

                    "line_items": [],

                    "total_fees": 0.0,

                    "total_tax": 0.0,
                    
                    "total_hours": 0.0,

                }

            try:
                net = float(row.get(sc.COL_TIME_GROSS) or row.get(sc.COL_TIME_NET) or 0)

            except (ValueError, TypeError):

                net = 0.0

            try:

                hst = float(row.get(sc.COL_TIME_HST) or 0)

            except (ValueError, TypeError):

                hst = 0.0

            try:

                hours = float(row.get(sc.COL_TIME_HOURS) or 0)

            except (ValueError, TypeError):

                hours = 0.0

            try:

                rate = float(row.get(sc.COL_TIME_RATE) or 0)

            except (ValueError, TypeError):

                rate = 0.0

            matters_map[group_id]["line_items"].append({
                "entryId": str(row.get(sc.COL_TIME_ENTRY_ID) or ""),
                "date": str(row.get(sc.COL_TIME_DATE) or ""),
                "description": clean_desc(str(row.get(sc.COL_TIME_DESC) or "")),
                "hours": hours,
                "rate": rate,
                "is_custom_fee": hours == 0 and rate == 0 and net > 0,
                "amount": net,
                "amount_client": net,
                "amount_firm": net * (1.0 - (agency_split_percent / 100.0)) if agency_split_percent > 0 else net,
            })

            matters_map[group_id]["total_fees"] += net

            matters_map[group_id]["total_tax"] += hst
            
            matters_map[group_id]["total_hours"] += hours

            total_fees += net

            total_tax += hst
            
            total_hours += hours

        # A custom fee is a zero-hour/zero-rate positive line deliberately added
        # by the invoice builder.  Its amount replaces the docketed fee total.
        time_based_total = 0.0
        custom_fee_total = 0.0
        flat_fees_list = []
        for matter in matters_map.values():
            for item in matter["line_items"]:
                if item.get("is_custom_fee"):
                    custom_fee_total += float(item.get("amount") or 0)
                    flat_fees_list.append({
                        "date": item.get("date", ""),
                        "description": item.get("description", "Custom Fee"),
                        "amount": float(item.get("amount") or 0),
                    })
                else:
                    time_based_total += float(item.get("amount") or 0)

        is_flat_fee = (
            str(draft.get(sc.COL_DRAFT_IS_FLAT_FEE) or "False").lower() == "true"
            or bool(flat_fees_list)
        )
        try:
            stored_flat_fee_amount = float(draft.get(sc.COL_DRAFT_FLAT_FEE_AMOUNT) or 0)
        except (KeyError, TypeError, ValueError):
            stored_flat_fee_amount = 0.0
        flat_fee_amount = custom_fee_total if flat_fees_list else stored_flat_fee_amount
        flat_fee_desc = str(draft.get(sc.COL_DRAFT_FLAT_FEE_DESC) or "")
        reconciliation_mode = self._normalize_reconciliation_mode(
            draft.get(sc.COL_DRAFT_RECONCILIATION_MODE)
        )
        flat_fee_courtesy_discount = 0.0
        # Keep the stored custom-fee lines intact for data consumers.  The
        # invoice-facing display can differ when a visible courtesy discount
        # is requested: the invoice must first show the original docketed
        # service value and then show the reduction that produces the agreed
        # flat fee.  Rendering the flat fee as the service line while using
        # the docketed total in the totals block makes the document internally
        # inconsistent.
        flat_fee_display_lines = list(flat_fees_list)
        flat_fee_section_label = "Flat Fee"

        if is_flat_fee:
            # A lower custom fee can be expressed as a visible courtesy discount.
            # Equal, higher, and explicitly hidden reconciliations use only the
            # adjusted subtotal, so no synthetic discount is printed.
            if (
                flat_fee_amount < time_based_total
                and reconciliation_mode == "discount_line"
            ):
                total_fees = time_based_total
                flat_fee_courtesy_discount = time_based_total - flat_fee_amount
                discount_amount = flat_fee_courtesy_discount
                display_source = flat_fees_list[0] if flat_fees_list else {}
                flat_fee_display_lines = [{
                    "date": display_source.get("date", ""),
                    "description": (
                        display_source.get("description")
                        or flat_fee_desc
                        or "Legal Services Rendered"
                    ),
                    "amount": time_based_total,
                }]
                flat_fee_section_label = "Services Rendered"
            else:
                total_fees = flat_fee_amount
                discount_amount = 0.0

            # The flat-fee invoice template owns the visible fee line; docket
            # subtotals must not be rendered as an additional charge.
            for matter in matters_map.values():
                matter["total_fees"] = 0.0
                matter["total_tax"] = 0.0
        elif discount_type == "Percentage":
            discount_amount = total_fees * (discount_value / 100.0)
        elif discount_type == "Flat":
            discount_amount = discount_value
        else:
            discount_amount = 0.0

        subtotal_after_discount = max(0.0, total_fees - discount_amount)

        agency_split_amount = subtotal_after_discount * (agency_split_percent / 100.0)

        final_fees = max(0.0, subtotal_after_discount - agency_split_amount)

        # Always calculate total_tax based on final_fees to avoid line-item accumulation rounding errors
        total_tax = round(final_fees * 0.13, 2)

        if not is_flat_fee:
            for m in matters_map.values():
                m_sub = max(0.0, m["total_fees"] - (m["total_fees"] * (discount_value / 100.0) if discount_type == "Percentage" else 0))
                if discount_type == "Flat" and total_fees > 0:
                    m_sub = max(0.0, m["total_fees"] - (discount_value * (m["total_fees"] / total_fees)))
                m["total_tax"] = round((m_sub - (m_sub * (agency_split_percent / 100.0))) * 0.13, 2)

        total_due = final_fees + total_tax

        

        from datetime import datetime

        date_str = str(draft.get(sc.COL_DRAFT_DATE) or "")

        try:

            date_formatted = datetime.fromisoformat(date_str).strftime("%B %d, %Y").replace(" 0", " ")

        except ValueError:

            date_formatted = date_str

        # Format descriptive "work for"

        if billing_client_id == client_id:

            # If there's one matter, use it, else combine them

            matters_list = list(matters_map.values())

            if len(matters_list) == 1:

                work_for = matters_list[0].get("display_name")

            elif len(matters_list) > 1:

                work_for = ", ".join(m.get("display_name") for m in matters_list)

            else:

                work_for = ""

        else:

            work_for = client_profile.get("displayName") or client_profile.get("clientName") or ""

        billing_client_name = billing_profile.get("displayName") or billing_profile.get("clientName") or str(draft.get(sc.COL_DRAFT_CLIENT_NAME) or "")

        agency_short_name = billing_client_name.split()[0] if billing_client_name else "Agency"

        if agency_short_name == "LIHDC":

            agency_short_name = "LIH"

        draft_sort_order = []
        order_str = str(draft.get(sc.COL_DRAFT_CUSTOM_SORT_ORDER) or "")
        if order_str:
            draft_sort_order = [x.strip() for x in order_str.split(",")]

        if draft_sort_order:
            order_map = {entry_id: i for i, entry_id in enumerate(draft_sort_order)}
            for m in matters_map.values():
                m["line_items"].sort(key=lambda item: order_map.get(item.get("entryId"), 999999))
        else:
            for m in matters_map.values():
                m["line_items"].sort(key=lambda item: item.get("date", ""))

        docket_display_mode = str(draft.get("DocketDisplayMode") or "show").lower()
        
        # If we have a flat fee (via Fee Entries or Draft Meta), apply the display mode filter
        if is_flat_fee:
            for m in matters_map.values():
                new_line_items = []
                for item in m["line_items"]:
                    is_fee = bool(item.get("is_custom_fee"))
                    if is_fee:
                        new_line_items.append(item)
                    else:
                        if docket_display_mode == "tasks":
                            item["amount"] = 0
                            item["amount_client"] = 0
                            item["amount_firm"] = 0
                            new_line_items.append(item)
                        elif docket_display_mode == "hide":
                            pass # skip it
                        else:
                            new_line_items.append(item) # default behavior if missing
                m["line_items"] = new_line_items

        # A draft can be created from a legacy row with no attached work items.
        # Still identify the selected client rather than leaving the recipient
        # guessing whether "Bill To" is also the service client.
        if not service_client_names:
            append_unique(
                service_client_names,
                client_profile.get("displayName")
                or client_profile.get("clientName")
                or str(draft.get(sc.COL_DRAFT_CLIENT_NAME) or "")
                or billing_client_name,
            )

        service_client_display = ", ".join(service_client_names)
        service_matter_display = ", ".join(service_matter_names)

        payload = {
            "is_draft": is_draft,
            "invoice_number_raw": final_invoice_num if final_invoice_num else self.nextInvoiceNumber(),
            "invoice_number": final_invoice_num if final_invoice_num else draft_num,
            "client_name": str(draft.get(sc.COL_DRAFT_CLIENT_NAME) or ""),
            "billing_client_name": billing_client_name,
            "agency_short_name": agency_short_name,
            "billing_client_principal": billing_profile.get("principalName") or "",
            "billing_client_address_lines": addr_lines,
            "service_client_label": "Client" if len(service_client_names) == 1 else "Clients",
            "service_client_name": service_client_display,
            "service_matter_label": "Matter" if has_third_party_service_matter else (
                "Matter" if len(service_matter_names) == 1 else "Matters"
            ),
            "service_matter_name": service_matter_display,
            "is_third_party_service_context": has_third_party_service_matter,
            "work_for": work_for,
            "grouping_pref": grouping_pref,
            "date": date_formatted,
            "matters": list(matters_map.values()),
            "total_fees": total_fees,
            "total_tax": total_tax,
            "discount_amount": discount_amount,
            "agency_split_amount": agency_split_amount,
            "agency_split_percent": agency_split_percent,
            "total_due": total_due,
            "total_hours": total_hours,
            "discount_type": discount_type,
            "signature_path": "",
            "is_flat_fee": is_flat_fee,
            "flat_fee_desc": flat_fee_desc,
            "flat_fee_amount": flat_fee_amount if is_flat_fee else 0.0,
            "flat_fees_list": flat_fees_list,
            "flat_fee_display_lines": flat_fee_display_lines,
            "flat_fee_section_label": flat_fee_section_label,
            "time_based_total": time_based_total,
            "flat_fee_courtesy_discount": flat_fee_courtesy_discount,
            "reconciliation_mode": reconciliation_mode,
            "show_total_hours": str(draft.get(sc.COL_DRAFT_SHOW_TOTAL_HOURS) or "True").lower() == "true",
        }

        

        self._payload_cache[cache_key] = payload
        return payload

    def _generate_preview_impl(self, draft_num, template_name):

        payload = self._build_invoice_payload(draft_num)

        html = self._doc_svc.generate_html(template_name, payload)

        return html

    @Slot(str, str, result=str)
    def getFinalizedHtml(self, draft_num, final_invoice_num):
        cache_key = f"{draft_num}_True_None"
        if cache_key in self._payload_cache:
            import copy
            payload = copy.deepcopy(self._payload_cache[cache_key])
            payload["is_draft"] = False
            payload["invoice_number_raw"] = final_invoice_num
            payload["invoice_number"] = final_invoice_num
            return self._doc_svc.generate_html("Concept_A2", payload)
            
        try:
            payload = self._build_invoice_payload(draft_num, is_draft=False, final_invoice_num=final_invoice_num)
            return self._doc_svc.generate_html("Concept_A2", payload)
        except Exception as e:
            self._logger.error(f"Could not rebuild payload for finalized HTML: {e}")
            return ""

    @Slot(str, str, str)

    def exportDraftToWord(self, draft_num, template_name, output_path):

        """Export draft invoice to DOCX."""

        worker = Worker(

            self._export_draft_word_impl,

            str(draft_num),

            str(template_name) or "Concept_A2",

            str(output_path),

            name="exportDraftToWord",

        )

        worker.signals.result.connect(partial(self._on_export_ready, worker, output_path))

        worker.signals.error.connect(partial(self._on_export_error, worker))

        self._start_worker(worker)

    def _export_draft_word_impl(self, draft_num, template_name, output_path):

        payload = self._build_invoice_payload(draft_num)

        self._doc_svc.generate_docx(template_name, payload, output_path)

        return output_path

    def _on_export_ready(self, worker, output_path, result):

        try:

            self.toast.emit(f"Exported to {output_path}")

            import os

            try:

                os.startfile(output_path)

            except Exception as e:

                self.error.emit(f"Could not open file: {e}")

        finally:

            self._release_worker(worker)

    def _on_export_error(self, worker, err_tuple):

        try:

            exctype, value, tb_str = err_tuple

            self.error.emit(f"Could not export: {value}")

        finally:

            self._release_worker(worker)

    def _on_preview_ready(self, worker, result):

        try:

            html = str(result or "")
            self._last_preview_html = html
            self.invoiceHtmlReady.emit(html)

        finally:

            self._release_worker(worker)

    def _on_preview_error(self, worker, err_tuple):

        try:

            exctype, value, tb_str = err_tuple

            self.error.emit(f"Could not generate preview: {value}")

        finally:

            self._release_worker(worker)

    @Slot(str, str)
    def exportHtmlToPdf(self, html_content: str, output_path: str):
        """Generates a PDF explicitly sized as Letter."""
        try:
            from PySide6.QtWebEngineCore import QWebEnginePage
            from PySide6.QtGui import QPageLayout, QPageSize
            from PySide6.QtCore import QMarginsF
            import tempfile
            import os
            
            temp_dir = tempfile.gettempdir()
            pass1_path = os.path.join(temp_dir, "pass1.pdf")
            
            self.pdf_page = QWebEnginePage()
            
            layout = QPageLayout(
                QPageSize(QPageSize.Letter),
                QPageLayout.Portrait,
                QMarginsF(0, 0, 0, 0)
            )
            
            def finalize_merge():
                try:
                    from pypdf import PdfReader, PdfWriter
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter
                    from reportlab.lib.colors import Color
                    import re
                    
                    reader = PdfReader(pass1_path)
                    writer = PdfWriter()
                    total_pages = len(reader.pages)
                    
                    # Extract metadata
                    client_match = re.search(r'data-client="([^"]+)"', html_content)
                    invoice_match = re.search(r'data-invoice="([^"]+)"', html_content)
                    date_match = re.search(r'data-date="([^"]+)"', html_content)
                    
                    client_name = client_match.group(1).upper() if client_match else ""
                    invoice_num = invoice_match.group(1).upper() if invoice_match else ""
                    date_str = date_match.group(1).upper() if date_match else ""
                    
                    color_gray = Color(148/255.0, 163/255.0, 184/255.0)
                    color_navy = Color(15/255.0, 23/255.0, 42/255.0)
                    
                    for i in range(total_pages):
                        page = reader.pages[i]
                        temp_pdf_path = os.path.join(temp_dir, f"temp_page_{i}.pdf")
                        
                        c = canvas.Canvas(temp_pdf_path, pagesize=letter)
                        
                        # Draw Page Numbers (all pages)
                        text = f"PAGE {i+1} OF {total_pages}"
                        c.setFont("Helvetica", 8)
                        tw = c.stringWidth(text, "Helvetica", 8)
                        
                        c.setFillColor(color_gray)
                        # fitz y=758 from top -> reportlab y = 792 - 758 = 34 from bottom
                        c.drawString(554.4 - tw, 34, text)
                        
                        # Draw Continuation Header (pages 2+)
                        if i > 0:
                            left_text_1 = "CORY SCHNEIDER LAW OFFICE   "
                            left_text_2 = f"{client_name}"
                            right_text = f"INVOICE {invoice_num} \u2022 {date_str}"
                            
                            y_pos = 792 - 36  # fitz y=36 from top -> 756 from bottom
                            x_left = 57.6
                            
                            c.setFont("Helvetica-Bold", 8.5)
                            c.setFillColor(color_navy)
                            c.drawString(x_left, y_pos, left_text_1)
                            tw_1 = c.stringWidth(left_text_1, "Helvetica-Bold", 8.5)
                            
                            c.setFillColor(color_gray)
                            c.drawString(x_left + tw_1, y_pos, left_text_2)
                            
                            tw_r = c.stringWidth(right_text, "Helvetica-Bold", 8.5)
                            c.drawString(554.4 - tw_r, y_pos, right_text)
                            
                        c.save()
                        
                        overlay_reader = PdfReader(temp_pdf_path)
                        page.merge_page(overlay_reader.pages[0])
                        writer.add_page(page)
                        
                        os.remove(temp_pdf_path)
                        
                    with open(output_path, "wb") as f:
                        writer.write(f)
                    
                    self.toast.emit(f"Exported to {output_path}")
                    
                    self.pdfExportFinished.emit(output_path, True)

                    # Auto-open the PDF
                    try:
                        os.startfile(os.path.normpath(output_path))
                    except Exception as e:
                        self.error.emit(f"Could not open PDF: {e}")
                except Exception as e:
                    self.error.emit(f"Failed to save PDF: {e}")
                    self.pdfExportFinished.emit(output_path, False)
                finally:
                    if os.path.exists(pass1_path):
                        try: os.remove(pass1_path)
                        except: pass

            def on_pdf1_printed(filepath, success):
                if success:
                    finalize_merge()
                else:
                    self.error.emit("Failed to generate PDF")
                    self.pdfExportFinished.emit(output_path, False)
                    
            def on_load1_finished(ok):
                if ok: 
                    self.pdf_page.printToPdf(pass1_path, layout)
                else: 
                    self.error.emit("Failed to load HTML for PDF")
                    
            self.pdf_page.pdfPrintingFinished.connect(on_pdf1_printed)
            self.pdf_page.loadFinished.connect(on_load1_finished)
            self.pdf_page.setHtml(html_content)
            
        except Exception as exc:
            self.error.emit(f"Could not initialize PDF export: {exc}")

    # ── List Drafts ──────────────────────────────────────────────────────────

    @Slot(result='QVariantList')

    def listDrafts(self):

        """List all current draft invoices."""

        try:

            from repositories.excel_repo import TBL_DRAFT_INVOICES

            rows = self._excel_repo._read_table_rows(TBL_DRAFT_INVOICES)

            return [dict(r) for r in rows]

        except Exception as exc:
            self.error.emit(f"Could not list drafts: {exc}")
            return []

    @Slot(result='QVariantList')
    def listFinalizedInvoices(self):
        """List all finalized invoices from the invoice log."""
        try:
            from repositories.excel_repo import TBL_INVOICE_LOG
            rows = self._excel_repo._read_table_rows(TBL_INVOICE_LOG)
            # Make sure we map standard fields for generic list UI if needed
            return [dict(r) for r in rows]
        except Exception as exc:
            self.error.emit(f"Could not list finalized invoices: {exc}")
            return []

    @Slot(str, result='QVariantMap')
    def getInvoiceSummary(self, invoiceNum):
        """Fetch a full 360 summary for a specific invoice including matters and receivables."""
        try:
            from repositories.excel_repo import (
                TBL_DISBURSEMENTS,
                TBL_INVOICE_LOG,
                TBL_MATTERS,
                TBL_RECEIVABLES,
                TBL_TIME,
                TBL_TRANSACTIONS_MASTER,
            )
            from domain import schema_constants as sc
            invoice_log = self._excel_repo._read_table_rows(TBL_INVOICE_LOG)
            receivables = self._excel_repo._read_table_rows(TBL_RECEIVABLES)
            times = self._excel_repo._read_table_rows(TBL_TIME)
            disbursements = self._excel_repo._read_table_rows(TBL_DISBURSEMENTS)
            transactions = self._excel_repo._read_table_rows(TBL_TRANSACTIONS_MASTER)
            matters = self._excel_repo._read_table_rows(TBL_MATTERS)
            
            inv_row = {}
            for r in invoice_log:
                if str(r.get(sc.COL_INV_INVOICE_NUM) or "").strip() == invoiceNum:
                    inv_row = dict(r)
                    break
            
            if not inv_row:
                return {}
                
            for r in receivables:
                if str(r.get(sc.COL_RECV_INVOICE_NUM) or "").strip() == invoiceNum:
                    inv_row["AmountPaid"] = r.get(sc.COL_RECV_AMOUNT_PAID)
                    inv_row["BalanceDue"] = r.get(sc.COL_RECV_BALANCE_DUE)
                    inv_row["Status"] = r.get(sc.COL_RECV_STATUS)
                    break
            
            matter_ids = set()
            for t in times:
                if str(t.get(sc.COL_TIME_INVOICE_REF) or "").strip() == invoiceNum:
                    m_id = str(t.get(sc.COL_TIME_MATTER_ID) or "").strip()
                    if m_id:
                        matter_ids.add(m_id)

            for disbursement in disbursements:
                if str(disbursement.get(sc.COL_DISB_INVOICE_REF) or "").strip() == invoiceNum:
                    m_id = str(disbursement.get(sc.COL_DISB_MATTER_ID) or "").strip()
                    if m_id:
                        matter_ids.add(m_id)

            # Some imported legacy records contain the matter identifier in
            # Transactions Master rather than the time or disbursement tables.
            matter_lookup_values = set(matter_ids)
            for transaction in transactions:
                if str(transaction.get(sc.COL_TXN_INVOICE_REF) or "").strip() == invoiceNum:
                    matter_value = str(transaction.get(sc.COL_TXN_MATTER) or "").strip()
                    if matter_value:
                        matter_lookup_values.add(matter_value)
            
            matter_details = []
            for m in matters:
                m_id = str(m.get(sc.COL_MATTER_ID) or "").strip()
                m_number = str(m.get(sc.COL_MATTER_NUMBER) or "").strip()
                m_name = str(m.get(sc.COL_MATTER_NAME) or "").strip()
                m_display = str(m.get(sc.COL_MATTER_DISPLAY_NAME) or "").strip()
                if m_id in matter_lookup_values or m_number in matter_lookup_values or m_name in matter_lookup_values or m_display in matter_lookup_values:
                    description = str(
                        m.get(sc.COL_MATTER_DESCRIPTION)
                        or m_name
                        or m_display
                        or m_number
                        or m_id
                    ).strip()
                    if description:
                        matter_details.append(
                            {
                                "description": description,
                                "matterNumber": m_number,
                                "inferred": False,
                            }
                        )

            # Historic invoices were sometimes imported without their time
            # rows.  When exactly one substantive matter belongs to the invoice
            # client and predates the invoice, show its plain-English
            # description rather than presenting a made-up matter reference.
            if not matter_details:
                invoice_client = str(
                    inv_row.get(sc.COL_INV_SUB_CLIENT)
                    or inv_row.get(sc.COL_INV_CLIENT_NAME)
                    or inv_row.get("BillToClient")
                    or ""
                ).strip().lower()
                invoice_date = str(inv_row.get(sc.COL_INV_INVOICE_DATE) or "").strip()[:10]
                candidates = []
                for m in matters:
                    if not invoice_client or str(m.get(sc.COL_MATTER_CLIENT_NAME) or "").strip().lower() != invoice_client:
                        continue
                    description = str(
                        m.get(sc.COL_MATTER_DESCRIPTION)
                        or m.get(sc.COL_MATTER_NAME)
                        or m.get(sc.COL_MATTER_DISPLAY_NAME)
                        or ""
                    ).strip()
                    if not description or description.lower().startswith("legacy matter "):
                        continue
                    opened = str(m.get(sc.COL_MATTER_OPEN_DATE) or "").strip()[:10]
                    if invoice_date and opened and opened > invoice_date:
                        continue
                    candidates.append((description, str(m.get(sc.COL_MATTER_NUMBER) or "").strip()))
                if len(candidates) == 1:
                    description, matter_number = candidates[0]
                    matter_details.append(
                        {
                            "description": description,
                            "matterNumber": matter_number,
                            "inferred": True,
                        }
                    )
            
            # Keep the original string array for older QML callers, while the
            # directory gets structured descriptions and may show multiple
            # linked matters cleanly.
            inv_row["Matters"] = [detail["description"] for detail in matter_details]
            inv_row["MatterDetails"] = matter_details
            return inv_row
            
        except Exception as exc:
            self.error.emit(f"Could not get invoice summary: {exc}")
            return {}

    @Slot(str, result='QVariantMap')
    def repairFinalizedInvoiceAmounts(self, invoice_num):
        """Repair one finalized invoice from its linked billed WIP entries."""
        try:
            result = self._draft_svc.repair_finalized_invoice_amounts(str(invoice_num))
            self.toast.emit(
                f"Invoice {result['invoiceNum']} financials repaired: ${result['total']:,.2f} billed."
            )
            return {"ok": True, **result}
        except Exception as exc:
            self.error.emit(f"Could not repair invoice financials: {exc}")
            return {"ok": False, "message": str(exc)}

    # ── Next Invoice Number ──────────────────────────────────────────────────

    @Slot(result=str)

    def nextInvoiceNumber(self):

        """Suggest the next invoice number based on existing invoices."""

        try:

            from repositories.excel_repo import TBL_INVOICE_LOG

            rows = self._excel_repo._read_table_rows(TBL_INVOICE_LOG)

            max_num = 0

            import re

            from datetime import datetime

            current_year_prefix = str(datetime.now().year)[-2:]

            for row in rows:

                inv = str(row.get(sc.COL_INV_INVOICE_NUM) or "").strip()

                match = re.search(f'^{current_year_prefix}-(\\d+)$', inv)

                if match:

                    num = int(match.group(1))

                    if num > max_num:

                        max_num = num

            # Also check time entries for legacy invoice refs

            from repositories.excel_repo import TBL_TIME

            time_rows = self._excel_repo._read_table_rows(TBL_TIME)

            for row in time_rows:

                inv = str(row.get(sc.COL_TIME_INVOICE_REF) or "").strip()

                match = re.search(f'^{current_year_prefix}-(\\d+)$', inv)

                if match:

                    num = int(match.group(1))

                    if num > max_num:

                        max_num = num

            next_num = max_num + 1

            return f"{current_year_prefix}-{next_num:04d}"

        except Exception as exc:

            logger.error("nextInvoiceNumber error: %s", exc, exc_info=True)

            return "26-0001"

    @Slot(str, result=bool)

    def isInvoiceNumberUsed(self, invoice_num):

        """Check if an invoice number is already issued."""

        try:

            from repositories.excel_repo import TBL_INVOICE_LOG, TBL_TIME

            inv_clean = str(invoice_num).strip().lower()

            

            # Check invoice log

            rows = self._excel_repo._read_table_rows(TBL_INVOICE_LOG)

            for row in rows:

                inv = str(row.get(sc.COL_INV_INVOICE_NUM) or "").strip().lower()

                if inv == inv_clean:

                    return True

                    

            # Check time entries

            time_rows = self._excel_repo._read_table_rows(TBL_TIME)

            for row in time_rows:

                inv = str(row.get(sc.COL_TIME_INVOICE_REF) or "").strip().lower()

                if inv == inv_clean:

                    return True

                    

            return False

        except Exception as exc:

            logger.error("isInvoiceNumberUsed error: %s", exc, exc_info=True)

            return False
