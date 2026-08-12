import uuid
import logging
import time
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_HALF_UP

from domain.money import calc_amounts
from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo


logger = logging.getLogger(__name__)

class InvoiceDraftService:
    def __init__(self, repo: ExcelRepo):
        self.repo = repo

    @staticmethod
    def _money(value: Any) -> Decimal:
        """Return a safe two-decimal monetary value without float drift."""
        try:
            return Decimal(str(value if value not in (None, "") else 0)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except Exception:
            return Decimal("0.00")

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    def _write_tables_once(self, table_rows: Dict[Any, List[Dict[str, Any]]]) -> None:
        """Commit one financial command as one workbook replacement.

        Older lightweight test repositories intentionally only implement the
        single-table writer, so keep that compatible fallback.  The production
        Excel repository implements ``_write_table_rows_bulk`` and persists
        every supplied table through one atomic macro-workbook save.
        """
        write_bulk = getattr(self.repo, "_write_table_rows_bulk", None)
        if callable(write_bulk):
            write_bulk(table_rows)
            return
        for table, rows in table_rows.items():
            self.repo._write_table_rows(table, rows)

    def _recalculate_draft_totals_in_memory(
        self,
        draft: Dict[str, Any],
        time_entries: List[Dict[str, Any]],
        disb_entries: List[Dict[str, Any]],
    ) -> None:
        """Refresh a draft's totals without forcing an intermediate save."""
        draft_num = self._text(draft.get(sc.COL_DRAFT_INVOICE_NUM))
        fees = Decimal("0.0")
        tax = Decimal("0.0")
        for row in time_entries:
            if self._text(row.get(sc.COL_TIME_INVOICE_REF)) == draft_num:
                entry_net, entry_tax = self._entry_invoice_amounts(row)
                fees += entry_net
                tax += entry_tax

        disb_total = Decimal("0.0")
        for row in disb_entries:
            if self._text(row.get(sc.COL_DISB_INVOICE_REF)) == draft_num:
                disb_total += Decimal(str(row.get(sc.COL_DISB_AMOUNT) or 0))

        is_flat_fee = self._text(draft.get(sc.COL_DRAFT_IS_FLAT_FEE)).lower() == "true"
        flat_fee_amt = Decimal(str(draft.get(sc.COL_DRAFT_FLAT_FEE_AMOUNT) or 0))
        fees_to_use = flat_fee_amt if is_flat_fee else fees
        draft[sc.COL_DRAFT_TOTAL_FEES] = str(self._money(fees_to_use + disb_total))

        discount_type = self._text(draft.get(sc.COL_DRAFT_DISCOUNT_TYPE)) or "None"
        discount_value = Decimal(str(draft.get(sc.COL_DRAFT_DISCOUNT_VALUE) or 0))
        agency_split_percent = Decimal(str(draft.get(sc.COL_DRAFT_AGENCY_SPLIT_PERCENT) or 0))
        total_base = fees_to_use + disb_total
        if discount_type == "Percentage":
            discount_amt = total_base * (discount_value / Decimal("100.0"))
        elif discount_type == "Flat":
            discount_amt = discount_value
        else:
            discount_amt = Decimal("0.0")

        subtotal = max(Decimal("0.0"), total_base - discount_amt)
        agency_split_amt = subtotal * (agency_split_percent / Decimal("100.0"))
        new_fees = max(Decimal("0.0"), subtotal - agency_split_amt)
        final_tax = new_fees * Decimal("0.13") if (is_flat_fee or agency_split_percent > 0) else tax
        draft[sc.COL_DRAFT_TOTAL_TAX] = str(self._money(final_tax))
        draft[sc.COL_DRAFT_TOTAL_DUE] = str(self._money(new_fees + final_tax))
        draft[sc.COL_DRAFT_UPDATED_AT] = datetime.now().astimezone().isoformat()

    def _assert_invoice_number_available(self, invoice_num: str) -> None:
        """Reject a final number already used by a live financial record.

        The UI performs the same check for quick feedback, but finalization is
        the authoritative write boundary.  This also makes a correction draft
        safe to finalize after an app restart.
        """
        target = self._text(invoice_num).casefold()
        if not target:
            raise ValueError("A final invoice number is required.")

        checks = (
            (sc.TBL_INVOICE_LOG, sc.COL_INV_INVOICE_NUM, "Invoice Log"),
            (sc.TBL_RECEIVABLES, sc.COL_RECV_INVOICE_NUM, "Receivables"),
            (sc.TBL_TIME, sc.COL_TIME_INVOICE_REF, "Time Entries"),
            (sc.TBL_DISBURSEMENTS, sc.COL_DISB_INVOICE_REF, "Disbursements"),
        )
        for table, column, label in checks:
            for row in self.repo._read_table_rows(table):
                if self._text(row.get(column)).casefold() == target:
                    raise ValueError(
                        f"Invoice number {invoice_num} is already in use in {label}."
                    )

    def invoice_number_reuse_status(self, invoice_num: str) -> Dict[str, Any]:
        """Describe whether a final invoice number can safely be used.

        A previously reversed *unpaid* invoice is a special, safe case.  Its
        number can be reused for the corrected replacement once the original
        rows are moved to their internal ``-SUPERSEDED`` audit references.  A
        paid/credited or otherwise active number is never made reusable by
        this convenience path.
        """
        invoice_num = self._text(invoice_num)
        invoice_key = invoice_num.casefold()
        if not invoice_num:
            return {
                "state": "invalid",
                "canUse": False,
                "message": "Invoice number cannot be empty.",
            }

        invoice_rows = [
            row for row in self.repo._read_table_rows(sc.TBL_INVOICE_LOG)
            if self._text(row.get(sc.COL_INV_INVOICE_NUM)).casefold() == invoice_key
        ]
        receivable_rows = [
            row for row in self.repo._read_table_rows(sc.TBL_RECEIVABLES)
            if self._text(row.get(sc.COL_RECV_INVOICE_NUM)).casefold() == invoice_key
        ]
        linked_time = [
            row for row in self.repo._read_table_rows(sc.TBL_TIME)
            if self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold() == invoice_key
        ]
        linked_disbursements = [
            row for row in self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
            if self._text(row.get(sc.COL_DISB_INVOICE_REF)).casefold() == invoice_key
        ]

        if not invoice_rows and not receivable_rows and not linked_time and not linked_disbursements:
            return {
                "state": "available",
                "canUse": True,
                "message": "This invoice number is available.",
            }

        void_statuses = {"void", "voided", "reversed", "cancelled", "canceled"}
        is_voided = bool(receivable_rows) and all(
            self._text(row.get(sc.COL_RECV_STATUS)).casefold() in void_statuses
            for row in receivable_rows
        )
        has_money = any(
            self._money(row.get(sc.COL_RECV_AMOUNT_PAID)) != Decimal("0.00")
            or self._money(row.get(sc.COL_RECV_CREDITS_ADJ)) != Decimal("0.00")
            for row in receivable_rows
        )

        if invoice_rows and is_voided and not has_money and not linked_time and not linked_disbursements:
            return {
                "state": "reclaimable_void",
                "canUse": True,
                "message": (
                    f"{invoice_num} was previously voided with no payment or credit. "
                    "Confirm will preserve its internal audit record and reissue this number."
                ),
            }

        if has_money:
            message = (
                f"Invoice number {invoice_num} belongs to a paid or credited invoice and cannot be reused."
            )
        elif linked_time or linked_disbursements:
            message = (
                f"Invoice number {invoice_num} is still linked to billed work. "
                "Use Correct & Reissue from the original invoice first."
            )
        else:
            message = f"Invoice number {invoice_num} has already been used."
        return {"state": "used", "canUse": False, "message": message}

    def _entry_invoice_amounts(self, row: Dict[str, Any], *, normalize_fee: bool = False) -> tuple[Decimal, Decimal]:
        """Resolve the invoiceable net amount and HST for a docket row.

        Direct-fee rows have zero hours/rate by design.  Older rows can have a
        valid ``GrossToClient`` amount but a blank/zero ``AmountToYou`` and HST;
        treating those rows as zero silently produces a $0 invoice.  The direct
        fee's positive gross value is therefore the canonical recovery source.
        """
        gross = self._money(row.get(sc.COL_TIME_GROSS))
        net = self._money(row.get(sc.COL_TIME_NET))
        tax = self._money(row.get(sc.COL_TIME_HST))
        is_direct_fee = "entrytype:fee" in str(row.get(sc.COL_TIME_LOCK_AUDIT) or "").lower()

        # The draft invoice total must use the gross docket amount as the base.
        # This matches the HTML invoice display, and correctly handles agency 
        # split calculations without double-deducting the lawyer's share.
        invoice_fee = gross if gross > 0 else net

        if is_direct_fee:
            if net <= 0 and gross > 0:
                net = gross
                invoice_fee = gross
            if invoice_fee > 0 and tax <= 0:
                tax = (invoice_fee * Decimal("0.13")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if normalize_fee and net > 0:
                row[sc.COL_TIME_NET] = str(net)
                row[sc.COL_TIME_HST] = str(tax)
                row[sc.COL_TIME_TOTAL] = str(net + tax)

        return invoice_fee, tax

    def create_draft(self, client_id: str, client_name: str, time_entry_ids: List[str], disb_ids: List[str] = None, grouping_pref: str = "matter") -> str:
        """
        Creates a new draft invoice aggregating the specified time entries and disbursements.
        Assigns a temporary DRAFT-xxx invoice reference to them.
        """
        time_entry_ids = [str(item) for item in (time_entry_ids or []) if str(item).strip()]
        disb_ids = [str(item) for item in (disb_ids or []) if str(item).strip()]
        if not time_entry_ids and not disb_ids:
            raise ValueError(
                "Select at least one time docket, fee entry, or disbursement before creating a draft invoice."
            )

        draft_id = str(uuid.uuid4())
        
        # Format: CLIENTNAME-YYYYMMDD-DRAFTID
        # Clean client name: remove spaces/special chars and uppercase
        import re
        clean_name = re.sub(r'[^A-Za-z0-9]', '', str(client_name)).upper()
        if not clean_name:
            clean_name = str(client_id).upper()
        # Take first 10 chars of client name
        clean_name = clean_name[:10]
        
        date_str = datetime.now().astimezone().strftime("%Y%m%d")
        draft_num = f"{clean_name}-{date_str}-{draft_id[:4].upper()}-D"
        
        now_str = datetime.now().astimezone().isoformat()
        import logging
        logger = logging.getLogger("InvoiceDraftService")
        logger.info(f"[CREATE DRAFT] Client: {client_id}, {client_name}")
        logger.info(f"[CREATE DRAFT] Time Entry IDs: {time_entry_ids}")
        logger.info(f"[CREATE DRAFT] Disb IDs: {disb_ids}")
        
        # 1. Update Time Entries
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        updated_time = False
        fees_total = Decimal('0.0')
        tax_total = Decimal('0.0')
        latest_date = None
        
        time_entry_ids_str = [str(i) for i in time_entry_ids]
        
        # Keep track of old drafts that had items pulled out of them
        affected_old_drafts = set()

        # A correction reservation follows returned WIP, not a transient UI
        # session.  A replacement invoice must be built from that correction
        # WIP alone; mixing it with ordinary WIP would make the reissued number
        # ambiguous and could silently add unrelated work to a corrected bill.
        reissue_numbers = set()
        selected_unreserved_entries = False
        for row in time_entries:
            if self._text(row.get(sc.COL_TIME_ENTRY_ID)) not in time_entry_ids_str:
                continue
            reserved = self._text(row.get(sc.COL_TIME_REISSUE_INVOICE_NUM))
            if reserved:
                reissue_numbers.add(reserved.casefold())
            else:
                selected_unreserved_entries = True
        
        for row in time_entries:
            if str(row.get(sc.COL_TIME_ENTRY_ID) or "").strip() in time_entry_ids_str:
                old_ref = str(row.get(sc.COL_TIME_INVOICE_REF) or "").strip()
                if old_ref and old_ref != draft_num:
                    affected_old_drafts.add(old_ref)
                    
                row[sc.COL_TIME_INVOICE_REF] = draft_num
                row[sc.COL_TIME_INVOICE_STATUS] = "Draft"
                updated_time = True
                
                net, tax = self._entry_invoice_amounts(row, normalize_fee=True)
                fees_total += net
                tax_total += tax
                
                row_date = str(row.get(sc.COL_TIME_DATE) or "").strip()
                if row_date:
                    if not latest_date or row_date > latest_date:
                        latest_date = row_date

        import calendar
        if latest_date:
            try:
                dt = datetime.strptime(latest_date[:10], "%Y-%m-%d")
                last_day = calendar.monthrange(dt.year, dt.month)[1]
                draft_date = dt.replace(day=last_day).strftime("%Y-%m-%dT12:00:00Z")
            except Exception:
                draft_date = now_str
        else:
            draft_date = now_str

        if updated_time:
            self.repo._write_table_rows(sc.TBL_TIME, time_entries)

        # 2. Update Disbursements
        disb_entries = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        updated_disb = False
        disb_total = Decimal('0.0')
        
        disb_ids_str = [str(i) for i in disb_ids]

        for row in disb_entries:
            if self._text(row.get(sc.COL_DISB_ID)) not in disb_ids_str:
                continue
            reserved = self._text(row.get(sc.COL_DISB_REISSUE_INVOICE_NUM))
            if reserved:
                reissue_numbers.add(reserved.casefold())
            else:
                selected_unreserved_entries = True

        if len(reissue_numbers) > 1 or (reissue_numbers and selected_unreserved_entries):
            raise ValueError(
                "Create the corrected invoice from its returned WIP only. "
                "Do not mix it with other unbilled entries."
            )
        reissue_invoice_num = next(iter(reissue_numbers), "")
        
        for row in disb_entries:
            if str(row.get(sc.COL_DISB_ID) or "").strip() in disb_ids_str:
                old_ref = str(row.get(sc.COL_DISB_INVOICE_REF) or "").strip()
                if old_ref and old_ref != draft_num:
                    affected_old_drafts.add(old_ref)
                    
                row[sc.COL_DISB_INVOICE_REF] = draft_num
                updated_disb = True
                amt = Decimal(str(row.get(sc.COL_DISB_AMOUNT) or 0))
                disb_total += amt

        if updated_disb:
            self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, disb_entries)

        # Apply 30% agency split for LIHDC. Because _entry_invoice_amounts
        # now uses GrossToClient as the draft's fee base, this accurately
        # matches the HTML preview and correctly reduces the backend total
        # to the net AmountToYou without double-deduction.
        agency_split_percent = "0.0"
        try:
            cid = str(client_id).split(',')[0].strip()
            client_profile_res = self.repo.get_client_profile(cid)
            client_profile = client_profile_res.get("client", {}) if client_profile_res.get("ok") else {}
            billing_client_id = client_profile.get("parentClientId") or cid
            if billing_client_id != cid:
                billing_profile_res = self.repo.get_client_profile(billing_client_id)
                billing_profile = billing_profile_res.get("client", {}) if billing_profile_res.get("ok") else client_profile
            else:
                billing_profile = client_profile
            
            billing_client_name = billing_profile.get("clientName", "") or billing_profile.get("displayName", "")
            if "LIHDC" in str(billing_client_name).upper() or "LIHDC" in str(client_name).upper():
                agency_split_percent = "30.0"
        except Exception:
            pass

        # 3. Create Draft Record
        draft_record = {
            sc.COL_DRAFT_ID: draft_id,
            sc.COL_DRAFT_INVOICE_NUM: draft_num,
            sc.COL_DRAFT_CLIENT_ID: client_id,
            sc.COL_DRAFT_CLIENT_NAME: client_name,
            sc.COL_DRAFT_DATE: draft_date,
            sc.COL_DRAFT_DISCOUNT_TYPE: "None",
            sc.COL_DRAFT_DISCOUNT_VALUE: "0.0",
            sc.COL_DRAFT_AGENCY_SPLIT_PERCENT: agency_split_percent,
            sc.COL_DRAFT_TOTAL_FEES: str(fees_total + disb_total),
            sc.COL_DRAFT_TOTAL_TAX: str(tax_total),
            sc.COL_DRAFT_TOTAL_DUE: str(fees_total + disb_total + tax_total),
            sc.COL_DRAFT_GROUPING_PREF: grouping_pref,
            sc.COL_DRAFT_IS_FLAT_FEE: "False",
            sc.COL_DRAFT_FLAT_FEE_DESC: "",
            sc.COL_DRAFT_FLAT_FEE_AMOUNT: "0.0",
            sc.COL_DRAFT_RECONCILIATION_MODE: "backend_adjustment",
            sc.COL_DRAFT_SHOW_TOTAL_HOURS: "True",
            sc.COL_DRAFT_REISSUE_INVOICE_NUM: reissue_invoice_num,
            sc.COL_DRAFT_CREATED_AT: now_str,
            sc.COL_DRAFT_UPDATED_AT: now_str,
        }
        
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        
        # 4. Clean up affected old drafts
        if affected_old_drafts:
            drafts_to_keep = []
            for d in drafts:
                old_num = str(d.get(sc.COL_DRAFT_INVOICE_NUM) or "")
                if old_num in affected_old_drafts:
                    remaining_time = [r for r in time_entries if str(r.get(sc.COL_TIME_INVOICE_REF) or "") == old_num]
                    remaining_disb = [r for r in disb_entries if str(r.get(sc.COL_DISB_INVOICE_REF) or "") == old_num]
                    
                    if not remaining_time and not remaining_disb:
                        logger.info(f"Auto-deleting orphan draft {old_num}")
                        continue
                    else:
                        old_fees = sum((self._entry_invoice_amounts(r)[0] for r in remaining_time), Decimal("0.00"))
                        old_tax = sum((self._entry_invoice_amounts(r)[1] for r in remaining_time), Decimal("0.00"))
                        old_disb_total = sum(Decimal(str(r.get(sc.COL_DISB_AMOUNT) or 0)) for r in remaining_disb)
                        
                        d[sc.COL_DRAFT_TOTAL_FEES] = str(old_fees + old_disb_total)
                        d[sc.COL_DRAFT_TOTAL_TAX] = str(old_tax)
                        d[sc.COL_DRAFT_TOTAL_DUE] = str(old_fees + old_disb_total + old_tax)
                        d[sc.COL_DRAFT_UPDATED_AT] = now_str
                drafts_to_keep.append(d)
            drafts = drafts_to_keep
            
        drafts.append(draft_record)
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        
        # If there's an agency split, recalculate immediately to ensure math is correct
        if float(agency_split_percent) > 0:
            self.recalculate_draft_totals(draft_num)
            
        logger.info(f"[CREATE DRAFT] Success. Draft {draft_num} created.")
        return draft_num

    def apply_discount(self, draft_num: str, discount_type: str, discount_value: Decimal):
        """
        Applies a percentage or flat discount to the draft.
        """
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        now_str = datetime.now().astimezone().isoformat()
        
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                row[sc.COL_DRAFT_DISCOUNT_TYPE] = discount_type
                row[sc.COL_DRAFT_DISCOUNT_VALUE] = str(discount_value)
                row[sc.COL_DRAFT_UPDATED_AT] = now_str
                break
                
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        self.recalculate_draft_totals(draft_num)
        
    def apply_agency_split(self, draft_num: str, agency_split_percent: Decimal):
        """
        Applies an agency split to the draft.
        """
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        now_str = datetime.now().astimezone().isoformat()
        
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                row[sc.COL_DRAFT_AGENCY_SPLIT_PERCENT] = str(agency_split_percent)
                row[sc.COL_DRAFT_UPDATED_AT] = now_str
                break
                
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        self.recalculate_draft_totals(draft_num)

    def update_draft_meta(self, draft_num: str, meta: Dict[str, Any]):
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        now_str = datetime.now().astimezone().isoformat()
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                if "isFlatFee" in meta:
                    row[sc.COL_DRAFT_IS_FLAT_FEE] = str(meta["isFlatFee"])
                if "flatFeeDesc" in meta:
                    row[sc.COL_DRAFT_FLAT_FEE_DESC] = str(meta["flatFeeDesc"])
                if "flatFeeAmount" in meta:
                    row[sc.COL_DRAFT_FLAT_FEE_AMOUNT] = str(meta["flatFeeAmount"])
                if "reconciliationMode" in meta:
                    row[sc.COL_DRAFT_RECONCILIATION_MODE] = str(meta["reconciliationMode"])
                if "showTotalHours" in meta:
                    row[sc.COL_DRAFT_SHOW_TOTAL_HOURS] = str(meta["showTotalHours"])
                row[sc.COL_DRAFT_UPDATED_AT] = now_str
                break
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        self.recalculate_draft_totals(draft_num)

    def get_draft(self, draft_num: str) -> Optional[Dict[str, Any]]:
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                return row
        return None

    def recalculate_draft_totals(self, draft_num: str):
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        disb_entries = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                self._recalculate_draft_totals_in_memory(row, time_entries, disb_entries)
                break
                
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)

    def update_line_item(self, entry_id: str, data: Dict[str, Any]):
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        draft_num = None
        for row in time_entries:
            if str(row.get(sc.COL_TIME_ENTRY_ID) or "") == entry_id:
                if "date" in data:
                    row[sc.COL_TIME_DATE] = data["date"]
                if "description" in data:
                    row[sc.COL_TIME_DESC] = data["description"]
                is_fee = "entrytype:fee" in str(row.get(sc.COL_TIME_LOCK_AUDIT) or "").lower()
                if is_fee:
                    if "amount" in data:
                        amount = float(data["amount"])
                        if amount < 0:
                            raise ValueError("Fee amount cannot be negative.")
                        row[sc.COL_TIME_HOURS] = "0.0"
                        row[sc.COL_TIME_RATE] = "0.0"
                        hst = round(amount * 0.13, 2)
                        row[sc.COL_TIME_GROSS] = str(round(amount, 2))
                        row[sc.COL_TIME_NET] = str(round(amount, 2))
                        row[sc.COL_TIME_HST] = str(hst)
                        row[sc.COL_TIME_TOTAL] = str(round(amount + hst, 2))
                elif "hours" in data or "rate" in data:
                    hrs = float(data.get("hours", row.get(sc.COL_TIME_HOURS) or 0))
                    rate = float(data.get("rate", row.get(sc.COL_TIME_RATE) or 0))
                    if hrs < 0 or rate < 0:
                        raise ValueError("Hours and hourly rate cannot be negative.")
                    net = round(hrs * rate, 2)
                    hst = round(net * 0.13, 2)
                    row[sc.COL_TIME_HOURS] = str(hrs)
                    row[sc.COL_TIME_RATE] = str(rate)
                    row[sc.COL_TIME_GROSS] = str(net)
                    row[sc.COL_TIME_NET] = str(net)
                    row[sc.COL_TIME_HST] = str(hst)
                    row[sc.COL_TIME_TOTAL] = str(round(net + hst, 2))
                draft_num = str(row.get(sc.COL_TIME_INVOICE_REF) or "")
                break
        self.repo._write_table_rows(sc.TBL_TIME, time_entries)
        if draft_num:
            self.recalculate_draft_totals(draft_num)

    def remove_line_item(self, entry_id: str, delete_completely: bool):
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        draft_num = None
        if delete_completely:
            to_remove = None
            for row in time_entries:
                if str(row.get(sc.COL_TIME_ENTRY_ID) or "") == entry_id:
                    draft_num = str(row.get(sc.COL_TIME_INVOICE_REF) or "")
                    to_remove = row
                    break
            if to_remove:
                time_entries.remove(to_remove)
        else:
            for row in time_entries:
                if str(row.get(sc.COL_TIME_ENTRY_ID) or "") == entry_id:
                    draft_num = str(row.get(sc.COL_TIME_INVOICE_REF) or "")
                    row[sc.COL_TIME_INVOICE_REF] = ""
                    row[sc.COL_TIME_INVOICE_STATUS] = "Unbilled"
                    # A returned docket can be deliberately removed from a
                    # correction draft so it can be billed separately. Once
                    # it leaves that draft it must not keep the old invoice
                    # number as a replacement suggestion.
                    draft = next(
                        (
                            item
                            for item in drafts
                            if self._text(item.get(sc.COL_DRAFT_INVOICE_NUM))
                            == self._text(draft_num)
                        ),
                        {},
                    )
                    suggested_reissue_num = self._text(
                        draft.get(sc.COL_DRAFT_REISSUE_INVOICE_NUM)
                    )
                    if (
                        suggested_reissue_num
                        and self._text(row.get(sc.COL_TIME_REISSUE_INVOICE_NUM)).casefold()
                        == suggested_reissue_num.casefold()
                    ):
                        row[sc.COL_TIME_REISSUE_INVOICE_NUM] = ""
                    break
        self.repo._write_table_rows(sc.TBL_TIME, time_entries)
        if draft_num:
            self.recalculate_draft_totals(draft_num)

    def release_draft_reissue_suggestion(self, draft_num: str) -> Dict[str, Any]:
        """Turn a separate correction-derived draft back into ordinary WIP.

        This covers a split correction: the draft and its WIP remain intact,
        but the stale old invoice-number suggestion is removed so it can be
        finalized under its own unused invoice number.
        """
        draft_num = self._text(draft_num)
        draft = self.get_draft(draft_num)
        if not draft:
            raise ValueError(f"Draft {draft_num} not found")
        suggested_num = self._text(draft.get(sc.COL_DRAFT_REISSUE_INVOICE_NUM))
        if not suggested_num:
            return {
                "ok": True,
                "released": False,
                "message": "Draft has no correction number suggestion.",
            }

        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        released_time = 0
        for row in time_entries:
            if (
                self._text(row.get(sc.COL_TIME_INVOICE_REF)) == draft_num
                and self._text(row.get(sc.COL_TIME_REISSUE_INVOICE_NUM)).casefold()
                == suggested_num.casefold()
            ):
                row[sc.COL_TIME_REISSUE_INVOICE_NUM] = ""
                released_time += 1
        self.repo._write_table_rows(sc.TBL_TIME, time_entries)

        disbursements = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        released_disbursements = 0
        for row in disbursements:
            if (
                self._text(row.get(sc.COL_DISB_INVOICE_REF)) == draft_num
                and self._text(row.get(sc.COL_DISB_REISSUE_INVOICE_NUM)).casefold()
                == suggested_num.casefold()
            ):
                row[sc.COL_DISB_REISSUE_INVOICE_NUM] = ""
                released_disbursements += 1
        self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, disbursements)

        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        for item in drafts:
            if self._text(item.get(sc.COL_DRAFT_INVOICE_NUM)) == draft_num:
                item[sc.COL_DRAFT_REISSUE_INVOICE_NUM] = ""
                break
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        self.recalculate_draft_totals(draft_num)
        return {
            "ok": True,
            "released": True,
            "draftNum": draft_num,
            "suggestedInvoiceNum": suggested_num,
            "timeEntryCount": released_time,
            "disbursementCount": released_disbursements,
        }

    def add_line_item(self, draft_num: str, data: Dict[str, Any]):
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        draft = self.get_draft(draft_num)
        if not draft:
            return
            
        import uuid
        entry_id = f"T_{uuid.uuid4().hex[:10]}"

        is_fee = data.get("isFee", False)
        if is_fee:
            hrs = 0.0
            rate = 0.0
            net = float(data.get("amount") or 0.0)
        else:
            hrs = float(data.get("hours") or 0.0)
            rate = float(data.get("rate") or 0.0)
            net = hrs * rate
        
        new_row = {
            sc.COL_TIME_ENTRY_ID: entry_id,
            sc.COL_TIME_MATTER_ID: data.get("matterId") or "",
            sc.COL_TIME_CLIENT_ID: draft.get(sc.COL_DRAFT_CLIENT_ID),
            sc.COL_TIME_DATE: data.get("date") or datetime.now().strftime("%Y-%m-%d"),
            sc.COL_TIME_DESC: data.get("description") or ("Fee Entry" if is_fee else "New Time Entry"),
            sc.COL_TIME_HOURS: str(hrs),
            sc.COL_TIME_RATE: str(rate),
            sc.COL_TIME_NET: str(net),
            sc.COL_TIME_GROSS: str(net),
            sc.COL_TIME_HST: str(net * 0.13),
            sc.COL_TIME_INVOICE_STATUS: "Draft",
            sc.COL_TIME_INVOICE_REF: draft_num
        }
        time_entries.append(new_row)
        self.repo._write_table_rows(sc.TBL_TIME, time_entries)
        self.recalculate_draft_totals(draft_num)

    def finalize_draft(self, draft_num: str, final_invoice_num: str, save_dir: str):
        """
        Finalizes the draft into a real invoice.
        Locks the draft, updates docket statuses, creates Receivable and InvoiceLog rows.
        Moves generated PDFs into the sorted directories.
        """
        started = time.perf_counter()
        import os
        import shutil
        from decimal import Decimal
        
        draft = self.get_draft(draft_num)
        if not draft:
            raise ValueError(f"Draft {draft_num} not found")

        final_invoice_num = self._text(final_invoice_num)
        suggested_reissue_num = self._text(draft.get(sc.COL_DRAFT_REISSUE_INVOICE_NUM))
        number_status = self.invoice_number_reuse_status(final_invoice_num)
        if number_status.get("state") == "reclaimable_void":
            # This is the in-app completion path for an invoice that was
            # reversed before its replacement draft was created.  It is safe
            # only because invoice_number_reuse_status has proved there are no
            # payment/credit entries or still-billed docket rows.
            self._archive_voided_invoice_number_for_reissue(final_invoice_num)
        elif not number_status.get("canUse"):
            raise ValueError(str(number_status.get("message") or "Invoice number is unavailable."))
        else:
            self._assert_invoice_number_available(final_invoice_num)

        # Read every table that finalization changes from one snapshot.  The
        # prior implementation re-opened the macro workbook for each table,
        # recalculated the draft with an intermediate save, then saved six
        # more times.  Work from this single snapshot and persist it once.
        finalization_tables = [
            sc.TBL_DRAFT_INVOICES,
            sc.TBL_TIME,
            sc.TBL_DISBURSEMENTS,
            sc.TBL_RECEIVABLES,
            sc.TBL_INVOICE_LOG,
            sc.TBL_LEDGER,
        ]
        read_bulk = getattr(self.repo, "_read_table_rows_bulk", None)
        if callable(read_bulk):
            table_rows = read_bulk(finalization_tables)
        else:
            table_rows = {
                table: self.repo._read_table_rows(table)
                for table in finalization_tables
            }

        drafts = table_rows[sc.TBL_DRAFT_INVOICES]
        draft = next(
            (
                row
                for row in drafts
                if self._text(row.get(sc.COL_DRAFT_INVOICE_NUM)) == self._text(draft_num)
            ),
            None,
        )
        if not draft:
            raise ValueError(f"Draft {draft_num} disappeared during finalization")

        # Never finalize from stale draft totals.  This also recovers legacy
        # direct-fee rows that have GrossToClient populated but net/HST blank,
        # without saving a transient draft state first.
        time_entries = table_rows[sc.TBL_TIME]
        disb_entries = table_rows[sc.TBL_DISBURSEMENTS]
        self._recalculate_draft_totals_in_memory(draft, time_entries, disb_entries)
        final_invoice_total = self._money(draft.get(sc.COL_DRAFT_TOTAL_DUE))
            
        now_str = datetime.now().astimezone().isoformat()
        date_str = draft.get(sc.COL_DRAFT_DATE) or now_str
        
        # 1. Update Time Entries
        for row in time_entries:
            if row.get(sc.COL_TIME_INVOICE_REF) == draft_num:
                self._entry_invoice_amounts(row, normalize_fee=True)
                row[sc.COL_TIME_INVOICE_REF] = final_invoice_num
                row[sc.COL_TIME_INVOICE_STATUS] = "Billed"
                row[sc.COL_TIME_STATUS] = "Billed"
                row[sc.COL_TIME_INVOICE_DATE] = date_str
                row[sc.COL_TIME_INVOICE_TOTAL] = str(final_invoice_total)
                row[sc.COL_TIME_INVOICE_AMOUNT_PAID] = "0.00"
                row[sc.COL_TIME_INVOICE_BALANCE_DUE] = str(final_invoice_total)
                row[sc.COL_TIME_REISSUE_INVOICE_NUM] = ""
                
        # 1b. Handle WIP Adjustments for Flat Fees or Discounts
        try:
            import uuid
            is_flat_fee = str(draft.get(sc.COL_DRAFT_IS_FLAT_FEE) or "False").lower() == "true"
            if is_flat_fee:
                wip_fees = sum(Decimal(str(r.get(sc.COL_TIME_NET) or 0)) for r in time_entries if r.get(sc.COL_TIME_INVOICE_REF) == final_invoice_num)
                flat_fee_amt = Decimal(str(draft.get(sc.COL_DRAFT_FLAT_FEE_AMOUNT) or 0))
                recon_mode = str(draft.get(sc.COL_DRAFT_RECONCILIATION_MODE) or "backend_adjustment")
                diff = flat_fee_amt - wip_fees
                if diff != 0:
                    desc = f"Courtesy Discount ({draft.get(sc.COL_DRAFT_FLAT_FEE_DESC) or 'Flat Fee'})" if diff < 0 and recon_mode == "discount_line" else ("Flat Fee Adjustment (Write-Up)" if diff > 0 else "Flat Fee Adjustment (Write-Down)")
                    time_entries.append({
                        sc.COL_TIME_ENTRY_ID: f"WIP_{uuid.uuid4().hex[:8]}",
                        sc.COL_TIME_DATE: date_str,
                        sc.COL_TIME_CLIENT_ID: draft.get(sc.COL_DRAFT_CLIENT_ID),
                        sc.COL_TIME_DESC: desc,
                        sc.COL_TIME_NET: str(diff),
                        sc.COL_TIME_HST: str(diff * Decimal('0.13')),
                        sc.COL_TIME_TOTAL: str(diff * Decimal('1.13')),
                        sc.COL_TIME_INVOICE_REF: final_invoice_num,
                        sc.COL_TIME_INVOICE_STATUS: "Billed",
                        sc.COL_TIME_STATUS: "Billed",
                        sc.COL_TIME_INVOICE_DATE: date_str
                    })
            else:
                discount_val = draft.get(sc.COL_DRAFT_DISCOUNT_VALUE)
                if discount_val and Decimal(str(discount_val)) > 0:
                    time_entries.append({
                        sc.COL_TIME_ENTRY_ID: f"WIP_{uuid.uuid4().hex[:8]}",
                        sc.COL_TIME_DATE: date_str,
                        sc.COL_TIME_CLIENT_ID: draft.get(sc.COL_DRAFT_CLIENT_ID),
                        sc.COL_TIME_DESC: f"Courtesy Discount ({draft.get(sc.COL_DRAFT_DISCOUNT_TYPE)})",
                        sc.COL_TIME_NET: str(-Decimal(str(discount_val))),
                        sc.COL_TIME_HST: "0.00",
                        sc.COL_TIME_TOTAL: str(-Decimal(str(discount_val))),
                        sc.COL_TIME_INVOICE_REF: final_invoice_num,
                        sc.COL_TIME_INVOICE_STATUS: "Billed",
                        sc.COL_TIME_STATUS: "Billed",
                        sc.COL_TIME_INVOICE_DATE: date_str
                    })
        except Exception as e:
            print("Failed to apply WIP adjustment:", e)

        # 2. Update Disbursements
        for row in disb_entries:
            if row.get(sc.COL_DISB_INVOICE_REF) == draft_num:
                row[sc.COL_DISB_INVOICE_REF] = final_invoice_num
                row[sc.COL_DISB_REISSUE_INVOICE_NUM] = ""
        # A correction can be split deliberately.  Work moved into another
        # draft must become ordinary WIP once this correction is finalized;
        # it is not part of the replacement and must not keep its old-number
        # suggestion.
        if suggested_reissue_num:
            for row in time_entries:
                if (
                    self._text(row.get(sc.COL_TIME_REISSUE_INVOICE_NUM)).casefold()
                    == suggested_reissue_num.casefold()
                    and self._text(row.get(sc.COL_TIME_INVOICE_REF)) != final_invoice_num
                ):
                    row[sc.COL_TIME_REISSUE_INVOICE_NUM] = ""
            for row in disb_entries:
                if (
                    self._text(row.get(sc.COL_DISB_REISSUE_INVOICE_NUM)).casefold()
                    == suggested_reissue_num.casefold()
                    and self._text(row.get(sc.COL_DISB_INVOICE_REF)) != final_invoice_num
                ):
                    row[sc.COL_DISB_REISSUE_INVOICE_NUM] = ""
            for item in drafts:
                if (
                    self._text(item.get(sc.COL_DRAFT_INVOICE_NUM)) != draft_num
                    and self._text(item.get(sc.COL_DRAFT_REISSUE_INVOICE_NUM)).casefold()
                    == suggested_reissue_num.casefold()
                ):
                    item[sc.COL_DRAFT_REISSUE_INVOICE_NUM] = ""
        
        # 3. Create Receivables entry
        receivables = table_rows[sc.TBL_RECEIVABLES]
        receivables.append({
            sc.COL_RECV_INVOICE_NUM: final_invoice_num,
            sc.COL_RECV_DATE: date_str,
            sc.COL_RECV_CLIENT: draft.get(sc.COL_DRAFT_CLIENT_NAME),
            sc.COL_RECV_TOTAL_INVOICED: draft.get(sc.COL_DRAFT_TOTAL_DUE),
            sc.COL_RECV_AMOUNT_PAID: "0",
            sc.COL_RECV_CREDITS_ADJ: "0",
            sc.COL_RECV_BALANCE_DUE: draft.get(sc.COL_DRAFT_TOTAL_DUE),
            sc.COL_RECV_STATUS: "Unpaid"
        })
        # 4. Create Invoice Log entry
        invoice_log = table_rows[sc.TBL_INVOICE_LOG]
        invoice_log.append({
            sc.COL_INV_INVOICE_NUM: final_invoice_num,
            sc.COL_INV_CLIENT_NAME: draft.get(sc.COL_DRAFT_CLIENT_NAME),
            sc.COL_INV_INVOICE_DATE: date_str,
            sc.COL_INV_TOTAL_FEES: draft.get(sc.COL_DRAFT_TOTAL_FEES),
            sc.COL_INV_TOTAL_TAX: draft.get(sc.COL_DRAFT_TOTAL_TAX),
            sc.COL_INV_AGGREGATE_BILLED: draft.get(sc.COL_DRAFT_TOTAL_DUE)
        })
        # 4b. Create Ledger Entry for Revenue
        ledger = table_rows[sc.TBL_LEDGER]
        ledger.append({
            sc.COL_LEDGER_ID: self.repo._new_id("LED"),
            sc.COL_LEDGER_DATE: date_str,
            sc.COL_LEDGER_CLIENT_VENDOR: draft.get(sc.COL_DRAFT_CLIENT_NAME),
            sc.COL_LEDGER_DESCRIPTION: f"Invoice {final_invoice_num}",
            sc.COL_LEDGER_CATEGORY: "Revenue",
            sc.COL_LEDGER_REFERENCE: final_invoice_num,
            sc.COL_LEDGER_BILLINGS_EXCL_HST: draft.get(sc.COL_DRAFT_TOTAL_FEES),
            sc.COL_LEDGER_HST_COLLECTED: draft.get(sc.COL_DRAFT_TOTAL_TAX),
            sc.COL_LEDGER_RECEIVABLE: draft.get(sc.COL_DRAFT_TOTAL_DUE),
            sc.COL_LEDGER_CREATED_AT: now_str
        })
        # 5. Remove Draft
        drafts = [d for d in drafts if d.get(sc.COL_DRAFT_INVOICE_NUM) != draft_num]
        self._write_tables_once({
            sc.TBL_TIME: time_entries,
            sc.TBL_DISBURSEMENTS: disb_entries,
            sc.TBL_RECEIVABLES: receivables,
            sc.TBL_INVOICE_LOG: invoice_log,
            sc.TBL_LEDGER: ledger,
            sc.TBL_DRAFT_INVOICES: drafts,
        })
        logger.info(
            "[PERF] Invoice finalization %s from %s completed in %.3fs with one workbook save.",
            final_invoice_num,
            draft_num,
            time.perf_counter() - started,
        )
        
        return True

    def repair_finalized_invoice_amounts(self, invoice_num: str) -> Dict[str, Any]:
        """Rebuild one finalized invoice's monetary records from linked WIP.

        This is a targeted integrity repair for historical invoices created by
        the direct-fee zero-total defect.  It deliberately leaves payment and
        credit figures intact while synchronizing the Invoice Log, Receivables,
        Revenue ledger row, and linked time-entry invoice fields.
        """
        invoice_num = str(invoice_num or "").strip()
        if not invoice_num:
            raise ValueError("Invoice number is required.")

        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        linked_time = [
            row for row in time_entries
            if str(row.get(sc.COL_TIME_INVOICE_REF) or "").strip() == invoice_num
        ]
        if not linked_time:
            raise ValueError(f"No billed time or fee entries are linked to {invoice_num}.")

        fees = Decimal("0.00")
        tax = Decimal("0.00")
        for row in linked_time:
            entry_net, entry_tax = self._entry_invoice_amounts(row, normalize_fee=True)
            fees += entry_net
            tax += entry_tax

        disbursements = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        disbursement_total = sum(
            (
                self._money(row.get(sc.COL_DISB_AMOUNT))
                for row in disbursements
                if str(row.get(sc.COL_DISB_INVOICE_REF) or "").strip() == invoice_num
            ),
            Decimal("0.00"),
        )
        total_due = fees + tax + disbursement_total

        invoice_log = self.repo._read_table_rows(sc.TBL_INVOICE_LOG)
        invoice_rows = [
            row for row in invoice_log
            if str(row.get(sc.COL_INV_INVOICE_NUM) or "").strip() == invoice_num
        ]
        if not invoice_rows:
            raise ValueError(f"Invoice Log entry {invoice_num} was not found.")
        for row in invoice_rows:
            row[sc.COL_INV_TOTAL_FEES] = str(fees)
            row[sc.COL_INV_TOTAL_DISBURSEMENTS] = str(disbursement_total)
            row[sc.COL_INV_TOTAL_TAX] = str(tax)
            row[sc.COL_INV_AGGREGATE_BILLED] = str(total_due)

        receivables = self.repo._read_table_rows(sc.TBL_RECEIVABLES)
        receivable_rows = [
            row for row in receivables
            if str(row.get(sc.COL_RECV_INVOICE_NUM) or "").strip() == invoice_num
        ]
        if not receivable_rows:
            raise ValueError(f"Receivables entry {invoice_num} was not found.")
        paid = Decimal("0.00")
        credits = Decimal("0.00")
        for row in receivable_rows:
            paid = self._money(row.get(sc.COL_RECV_AMOUNT_PAID))
            credits = self._money(row.get(sc.COL_RECV_CREDITS_ADJ))
            balance_due = total_due - paid - credits
            if abs(balance_due) < Decimal("0.01"):
                balance_due = Decimal("0.00")
            row[sc.COL_RECV_TOTAL_INVOICED] = str(total_due)
            row[sc.COL_RECV_BALANCE_DUE] = str(balance_due)

        invoice_date = invoice_rows[0].get(sc.COL_INV_INVOICE_DATE, "")
        balance_due = total_due - paid - credits
        if abs(balance_due) < Decimal("0.01"):
            balance_due = Decimal("0.00")
        for row in linked_time:
            row[sc.COL_TIME_INVOICE_TOTAL] = str(total_due)
            row[sc.COL_TIME_INVOICE_AMOUNT_PAID] = str(paid)
            row[sc.COL_TIME_INVOICE_BALANCE_DUE] = str(balance_due)
            if invoice_date:
                row[sc.COL_TIME_INVOICE_DATE] = invoice_date

        ledger = self.repo._read_table_rows(sc.TBL_LEDGER)
        ledger_rows = [
            row for row in ledger
            if str(row.get(sc.COL_LEDGER_REFERENCE) or "").strip() == invoice_num
            and str(row.get(sc.COL_LEDGER_CATEGORY) or "").strip().lower() == "revenue"
        ]
        for row in ledger_rows:
            row[sc.COL_LEDGER_BILLINGS_EXCL_HST] = str(fees + disbursement_total)
            row[sc.COL_LEDGER_HST_COLLECTED] = str(tax)
            row[sc.COL_LEDGER_RECEIVABLE] = str(balance_due)

        self.repo._write_table_rows(sc.TBL_TIME, time_entries)
        self.repo._write_table_rows(sc.TBL_INVOICE_LOG, invoice_log)
        self.repo._write_table_rows(sc.TBL_RECEIVABLES, receivables)
        if ledger_rows:
            self.repo._write_table_rows(sc.TBL_LEDGER, ledger)

        return {
            "invoiceNum": invoice_num,
            "fees": float(fees),
            "disbursements": float(disbursement_total),
            "tax": float(tax),
            "total": float(total_due),
            "balanceDue": float(balance_due),
            "linkedTimeEntries": len(linked_time),
            "ledgerRowsUpdated": len(ledger_rows),
        }

    def delete_draft(self, draft_num: str) -> bool:
        """
        Deletes a draft invoice and releases associated time and disbursement entries
        back to an 'Unbilled' state.
        """
        draft = self.get_draft(draft_num)
        if not draft:
            return False

        # 1. Revert Time Entries
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        modified_time = False
        for row in time_entries:
            if row.get(sc.COL_TIME_INVOICE_REF) == draft_num:
                row[sc.COL_TIME_INVOICE_REF] = ""
                row[sc.COL_TIME_INVOICE_STATUS] = ""
                row["Status"] = "Unbilled"
                modified_time = True
        if modified_time:
            self.repo._write_table_rows(sc.TBL_TIME, time_entries)

        # 2. Revert Disbursements
        disb_entries = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        modified_disb = False
        for row in disb_entries:
            if row.get(sc.COL_DISB_INVOICE_REF) == draft_num:
                row[sc.COL_DISB_INVOICE_REF] = ""
                modified_disb = True
        if modified_disb:
            self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, disb_entries)

        # 3. Remove Draft
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        drafts = [d for d in drafts if d.get(sc.COL_DRAFT_INVOICE_NUM) != draft_num]
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        
        return True

    def delete_drafts(self, draft_nums: list) -> bool:
        """
        Batch deletes multiple drafts.
        """
        if not draft_nums:
            return False
            
        draft_nums_set = set(draft_nums)

        # 1. Revert Time Entries
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        modified_time = False
        for row in time_entries:
            if row.get(sc.COL_TIME_INVOICE_REF) in draft_nums_set:
                row[sc.COL_TIME_INVOICE_REF] = ""
                row[sc.COL_TIME_INVOICE_STATUS] = ""
                row["Status"] = "Unbilled"
                modified_time = True
        if modified_time:
            self.repo._write_table_rows(sc.TBL_TIME, time_entries)

        # 2. Revert Disbursements
        disb_entries = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        modified_disb = False
        for row in disb_entries:
            if row.get(sc.COL_DISB_INVOICE_REF) in draft_nums_set:
                row[sc.COL_DISB_INVOICE_REF] = ""
                modified_disb = True
        if modified_disb:
            self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, disb_entries)

        # 3. Remove Drafts
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        drafts = [d for d in drafts if d.get(sc.COL_DRAFT_INVOICE_NUM) not in draft_nums_set]
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        
        return True

    def reverse_invoice(
        self,
        invoice_num: str,
        source_pdf_path: str = "",
        pdf_action: str = "keep",
        target_dir: str = "",
    ) -> bool:
        """Reverse one unpaid finalized invoice without losing its audit trail.

        A reversal returns only the invoice's linked WIP to the unbilled state;
        it does not alter another docket on the same client or matter.  The
        original invoice evidence remains in the workbook, paired with a
        ``-V`` audit row, while all operational views treat the invoice as
        void.  This signature deliberately matches the Invoice Reversal UI.
        """
        from pathlib import Path
        import shutil

        invoice_num = str(invoice_num or "").strip()
        if not invoice_num:
            raise ValueError("An invoice number is required for reversal.")
        invoice_key = invoice_num.casefold()
        reversal_num = f"{invoice_num}-V"

        receivables = self.repo._read_table_rows(sc.TBL_RECEIVABLES)
        matched_receivables = [
            row
            for row in receivables
            if str(row.get(sc.COL_RECV_INVOICE_NUM) or "").strip().casefold() == invoice_key
        ]
        if not matched_receivables:
            raise ValueError(f"Invoice {invoice_num} was not found in Receivables.")

        invoice_log = self.repo._read_table_rows(sc.TBL_INVOICE_LOG)
        original_inv = next(
            (
                row
                for row in invoice_log
                if str(row.get(sc.COL_INV_INVOICE_NUM) or "").strip().casefold() == invoice_key
            ),
            None,
        )
        if original_inv is None:
            raise ValueError(f"Invoice Log entry {invoice_num} was not found.")
        reversal_exists = any(
            str(row.get(sc.COL_INV_INVOICE_NUM) or "").strip().casefold() == reversal_num.casefold()
            for row in invoice_log
        )
        already_void = reversal_exists and all(
            str(row.get(sc.COL_RECV_STATUS) or "").strip().casefold()
            in {"void", "voided", "reversed", "cancelled", "canceled"}
            for row in matched_receivables
        )

        for row in matched_receivables:
            paid = self._money(row.get(sc.COL_RECV_AMOUNT_PAID))
            credits = self._money(row.get(sc.COL_RECV_CREDITS_ADJ))
            if paid != Decimal("0.00") or credits != Decimal("0.00"):
                raise ValueError(
                    f"Invoice {invoice_num} has recorded payments or credits and cannot be reversed here. "
                    "Reverse those allocations first."
                )

        # Validate an explicitly requested PDF action *before* changing any
        # financial records.  Keeping the PDF is the normal/default path and
        # deliberately needs no file selection.
        pdf_action_key = str(pdf_action or "keep").strip().casefold()
        pdf_path = None
        archive_dir = None
        archived_pdf = None
        if pdf_action_key in {"move", "delete"}:
            pdf_path = Path(str(source_pdf_path or "").strip())
            if not pdf_path.is_file():
                raise ValueError(
                    "Select the existing invoice PDF before asking CSPM to move or delete it."
                )
            if pdf_action_key == "move":
                archive_dir = (
                    Path(str(target_dir or "").strip())
                    if str(target_dir or "").strip()
                    else pdf_path.parent / "REVERSED"
                )
                archived_pdf = archive_dir / pdf_path.name
                if archived_pdf.exists():
                    raise FileExistsError(
                        f"Refusing to overwrite an existing archived PDF: {archived_pdf}"
                    )

        # 1. Return only the linked time entries to unbilled WIP.
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        for row in time_entries:
            if str(row.get(sc.COL_TIME_INVOICE_REF) or "").strip().casefold() != invoice_key:
                continue
            row[sc.COL_TIME_INVOICE_REF] = ""
            row[sc.COL_TIME_INVOICE_STATUS] = "Unbilled"
            # ``Draft`` is the canonical stored state for unbilled WIP.  The
            # client-ledger view presents it as a WIP/time entry, rather than
            # as an invoice.
            row[sc.COL_TIME_STATUS] = "Draft"
            row[sc.COL_TIME_INVOICE_DATE] = ""
            row[sc.COL_TIME_INVOICE_TOTAL] = "0.00"
            row[sc.COL_TIME_INVOICE_AMOUNT_PAID] = "0.00"
            row[sc.COL_TIME_INVOICE_BALANCE_DUE] = "0.00"
            row[sc.COL_TIME_PAYMENT_STATUS] = ""
        self.repo._write_table_rows(sc.TBL_TIME, time_entries)

        # 2. Unlink only the invoice's linked disbursements.
        disb_entries = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        for row in disb_entries:
            if str(row.get(sc.COL_DISB_INVOICE_REF) or "").strip().casefold() == invoice_key:
                row[sc.COL_DISB_INVOICE_REF] = ""
        self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, disb_entries)

        # 3. Preserve the receivable as an auditable void, with nothing due.
        for row in matched_receivables:
            row[sc.COL_RECV_BALANCE_DUE] = "0.00"
            row[sc.COL_RECV_STATUS] = "Void"
        self.repo._write_table_rows(sc.TBL_RECEIVABLES, receivables)

        # 4. Add exactly one negative invoice-log audit row.  The dashboard,
        # statements, and client ledger all exclude voided invoices.
        if not reversal_exists:
            void_inv = dict(original_inv)
            void_inv[sc.COL_INV_INVOICE_NUM] = reversal_num
            for amount_col in (
                sc.COL_INV_TOTAL_FEES,
                sc.COL_INV_TOTAL_DISBURSEMENTS,
                sc.COL_INV_TOTAL_TAX,
                sc.COL_INV_AGGREGATE_BILLED,
            ):
                void_inv[amount_col] = str(-self._money(void_inv.get(amount_col)))
            invoice_log.append(void_inv)
            self.repo._write_table_rows(sc.TBL_INVOICE_LOG, invoice_log)

        # 5. Post matching contra rows to the canonical ledger / transaction
        # tables.  We never erase the original invoice evidence; paired rows
        # keep the accounting trail intact while returning the net effect to
        # zero.  This is skipped for an already-complete reversal so repeated
        # clicks are harmless.
        if not already_void:
            now_str = datetime.now().astimezone().isoformat()
            reversal_fees = self._money(original_inv.get(sc.COL_INV_TOTAL_FEES))
            reversal_disb = self._money(original_inv.get(sc.COL_INV_TOTAL_DISBURSEMENTS))
            reversal_tax = self._money(original_inv.get(sc.COL_INV_TOTAL_TAX))
            reversal_total = self._money(original_inv.get(sc.COL_INV_AGGREGATE_BILLED))
            if reversal_total == Decimal("0.00"):
                reversal_total = reversal_fees + reversal_disb + reversal_tax

            ledger = self.repo._read_table_rows(sc.TBL_LEDGER)
            has_ledger_reversal = any(
                str(row.get(sc.COL_LEDGER_REFERENCE) or "").strip().casefold() == reversal_num.casefold()
                for row in ledger
            )
            if not has_ledger_reversal:
                ledger.append({
                    sc.COL_LEDGER_ID: self.repo._new_id("LED"),
                    sc.COL_LEDGER_DATE: now_str[:10],
                    sc.COL_LEDGER_CLIENT_VENDOR: (
                        original_inv.get(sc.COL_INV_BILL_TO_CLIENT)
                        or original_inv.get(sc.COL_INV_CLIENT_NAME)
                        or ""
                    ),
                    sc.COL_LEDGER_DESCRIPTION: f"Reversal of invoice {invoice_num}",
                    sc.COL_LEDGER_CATEGORY: "Invoice Reversal",
                    sc.COL_LEDGER_REFERENCE: reversal_num,
                    sc.COL_LEDGER_BILLINGS_EXCL_HST: str(-(reversal_fees + reversal_disb)),
                    sc.COL_LEDGER_HST_COLLECTED: str(-reversal_tax),
                    sc.COL_LEDGER_RECEIVABLE: str(-reversal_total),
                    sc.COL_LEDGER_CREATED_AT: now_str,
                })
                self.repo._write_table_rows(sc.TBL_LEDGER, ledger)

            transactions = self.repo._read_table_rows(sc.TBL_TRANSACTIONS_MASTER)
            has_transaction_reversal = any(
                str(row.get(sc.COL_TXN_INVOICE_REF) or "").strip().casefold() == reversal_num.casefold()
                for row in transactions
            )
            if not has_transaction_reversal:
                transactions.append({
                    sc.COL_TXN_ID: self.repo._new_id("TXN"),
                    sc.COL_TXN_DATE: now_str[:10],
                    sc.COL_TXN_CLASS: "Business",
                    sc.COL_TXN_TYPE: "Income",
                    sc.COL_TXN_CLIENT: (
                        original_inv.get(sc.COL_INV_BILL_TO_CLIENT)
                        or original_inv.get(sc.COL_INV_CLIENT_NAME)
                        or ""
                    ),
                    sc.COL_TXN_CATEGORY_CODE: "INC_LEGAL_FEES",
                    sc.COL_TXN_CATEGORY_NAME: "Invoice Reversal",
                    sc.COL_TXN_AMOUNT: str(-reversal_fees - reversal_disb),
                    sc.COL_TXN_TAX_AMOUNT: str(-reversal_tax),
                    sc.COL_TXN_INVOICE_REF: reversal_num,
                    sc.COL_TXN_NOTES: f"Reversal of invoice {invoice_num}",
                    sc.COL_TXN_STATUS: "Cleared",
                    sc.COL_TXN_CURRENCY: "CAD",
                    sc.COL_TXN_CREATED_AT: now_str,
                    sc.COL_TXN_UPDATED_AT: now_str,
                })
                self.repo._write_table_rows(sc.TBL_TRANSACTIONS_MASTER, transactions)

        # An external PDF is optional.  When the user explicitly selects a
        # disposition, however, require an existing file and never overwrite
        # an archive item with the same name.
        if pdf_action_key == "delete" and pdf_path is not None:
            pdf_path.unlink()
        elif pdf_action_key == "move" and pdf_path is not None:
            assert archive_dir is not None
            assert archived_pdf is not None
            archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf_path), str(archived_pdf))

        return True

    def _archive_voided_invoice_number_for_reissue(self, invoice_num: str) -> None:
        """Free a voided number while retaining an internal audit trail.

        The original row and its negative ``-V`` contra remain in the workbook,
        but the original row is internally marked ``-SUPERSEDED``.  The exact
        invoice number is therefore available for the corrected replacement,
        while client-facing reports continue to expose only the replacement.
        """
        invoice_num = self._text(invoice_num)
        invoice_key = invoice_num.casefold()
        superseded_num = f"{invoice_num}-SUPERSEDED"

        invoice_log = self.repo._read_table_rows(sc.TBL_INVOICE_LOG)
        if any(
            self._text(row.get(sc.COL_INV_INVOICE_NUM)).casefold()
            == superseded_num.casefold()
            for row in invoice_log
        ):
            raise ValueError(
                f"Invoice {invoice_num} is already reserved for a correction draft."
            )
        if not any(
            self._text(row.get(sc.COL_INV_INVOICE_NUM)).casefold() == invoice_key
            for row in invoice_log
        ):
            raise ValueError(f"Invoice Log entry {invoice_num} was not found.")

        receivables = self.repo._read_table_rows(sc.TBL_RECEIVABLES)
        matching_receivables = [
            row
            for row in receivables
            if self._text(row.get(sc.COL_RECV_INVOICE_NUM)).casefold() == invoice_key
        ]
        if not matching_receivables:
            raise ValueError(f"Receivables entry {invoice_num} was not found.")
        if any(
            self._text(row.get(sc.COL_RECV_STATUS)).casefold()
            not in {"void", "voided", "reversed", "cancelled", "canceled"}
            for row in matching_receivables
        ):
            raise ValueError(
                f"Invoice {invoice_num} must be voided before it can be reissued."
            )

        for row in invoice_log:
            if self._text(row.get(sc.COL_INV_INVOICE_NUM)).casefold() == invoice_key:
                row[sc.COL_INV_INVOICE_NUM] = superseded_num
        for row in receivables:
            if self._text(row.get(sc.COL_RECV_INVOICE_NUM)).casefold() == invoice_key:
                row[sc.COL_RECV_INVOICE_NUM] = superseded_num
                row[sc.COL_RECV_STATUS] = "Superseded"

        ledger = self.repo._read_table_rows(sc.TBL_LEDGER)
        for row in ledger:
            if self._text(row.get(sc.COL_LEDGER_REFERENCE)).casefold() == invoice_key:
                row[sc.COL_LEDGER_REFERENCE] = superseded_num
                description = self._text(row.get(sc.COL_LEDGER_DESCRIPTION))
                if "superseded" not in description.casefold():
                    row[sc.COL_LEDGER_DESCRIPTION] = (
                        f"{description} (superseded before reissue)".strip()
                    )

        transactions = self.repo._read_table_rows(sc.TBL_TRANSACTIONS_MASTER)
        for row in transactions:
            if self._text(row.get(sc.COL_TXN_INVOICE_REF)).casefold() == invoice_key:
                row[sc.COL_TXN_INVOICE_REF] = superseded_num
                notes = self._text(row.get(sc.COL_TXN_NOTES))
                if "superseded" not in notes.casefold():
                    row[sc.COL_TXN_NOTES] = (
                        f"{notes} Superseded before reissue.".strip()
                    )

        self._write_tables_once({
            sc.TBL_INVOICE_LOG: invoice_log,
            sc.TBL_RECEIVABLES: receivables,
            sc.TBL_LEDGER: ledger,
            sc.TBL_TRANSACTIONS_MASTER: transactions,
        })

    def correct_invoice_for_reissue(
        self,
        invoice_num: str,
        source_pdf_path: str = "",
        pdf_action: str = "keep",
        target_dir: str = "",
    ) -> Dict[str, Any]:
        """Return an unpaid erroneous invoice to WIP and suggest its number.

        Unlike a simple reversal, the returned dockets can now be reassigned to
        the correct client/matter before billing.  When that WIP is drafted by
        itself, CSPM carries the original number forward as a suggestion. The
        user may still issue the replacement with another unused number.
        """
        invoice_num = self._text(invoice_num)
        if not invoice_num:
            raise ValueError("An invoice number is required for correction.")
        invoice_key = invoice_num.casefold()

        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        disbursements = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        linked_time = [
            row for row in time_entries
            if self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold() == invoice_key
        ]
        linked_disbursements = [
            row for row in disbursements
            if self._text(row.get(sc.COL_DISB_INVOICE_REF)).casefold() == invoice_key
        ]
        if not linked_time and not linked_disbursements:
            raise ValueError(f"No invoiceable entries are linked to {invoice_num}.")
        if any(
            self._text(row.get(sc.COL_TIME_REISSUE_INVOICE_NUM)).casefold() == invoice_key
            for row in time_entries
        ) or any(
            self._text(row.get(sc.COL_DISB_REISSUE_INVOICE_NUM)).casefold() == invoice_key
            for row in disbursements
        ):
            raise ValueError(
                f"Invoice {invoice_num} is already reserved for a correction draft."
            )

        linked_time_ids = {
            self._text(row.get(sc.COL_TIME_ENTRY_ID)) for row in linked_time
        }
        linked_disb_ids = {
            self._text(row.get(sc.COL_DISB_ID)) for row in linked_disbursements
        }

        self.reverse_invoice(invoice_num, source_pdf_path, pdf_action, target_dir)
        self._archive_voided_invoice_number_for_reissue(invoice_num)

        returned_time = self.repo._read_table_rows(sc.TBL_TIME)
        for row in returned_time:
            if self._text(row.get(sc.COL_TIME_ENTRY_ID)) in linked_time_ids:
                row[sc.COL_TIME_REISSUE_INVOICE_NUM] = invoice_num
        self.repo._write_table_rows(sc.TBL_TIME, returned_time)

        returned_disbursements = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        for row in returned_disbursements:
            if self._text(row.get(sc.COL_DISB_ID)) in linked_disb_ids:
                row[sc.COL_DISB_REISSUE_INVOICE_NUM] = invoice_num
        self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, returned_disbursements)

        client_ids = {
            self._text(row.get(sc.COL_TIME_CLIENT_ID))
            for row in linked_time
            if self._text(row.get(sc.COL_TIME_CLIENT_ID))
        }
        matter_ids = {
            self._text(row.get(sc.COL_TIME_MATTER_ID))
            for row in linked_time
            if self._text(row.get(sc.COL_TIME_MATTER_ID))
        }
        return {
            "invoiceNum": invoice_num,
            "timeEntryCount": len(linked_time),
            "disbursementCount": len(linked_disbursements),
            "clientId": next(iter(client_ids), "") if len(client_ids) == 1 else "",
            "matterId": next(iter(matter_ids), "") if len(matter_ids) == 1 else "",
        }

    def reverse_and_edit_invoice(
        self,
        invoice_num: str,
        source_pdf_path: str = "",
        pdf_action: str = "keep",
        target_dir: str = "",
    ) -> str:
        """Reverse an unpaid invoice and immediately recreate its draft WIP."""
        invoice_num = str(invoice_num or "").strip()
        invoice_key = invoice_num.casefold()
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        disbursements = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        linked_time = [
            row for row in time_entries
            if str(row.get(sc.COL_TIME_INVOICE_REF) or "").strip().casefold() == invoice_key
        ]
        linked_disbursements = [
            row for row in disbursements
            if str(row.get(sc.COL_DISB_INVOICE_REF) or "").strip().casefold() == invoice_key
        ]
        if not linked_time and not linked_disbursements:
            raise ValueError(f"No invoiceable entries are linked to {invoice_num}.")

        invoice_log = self.repo._read_table_rows(sc.TBL_INVOICE_LOG)
        original_inv = next(
            (
                row for row in invoice_log
                if str(row.get(sc.COL_INV_INVOICE_NUM) or "").strip().casefold() == invoice_key
            ),
            {},
        )
        client_id = str(linked_time[0].get(sc.COL_TIME_CLIENT_ID) or "").strip() if linked_time else ""
        client_name = str(
            original_inv.get(sc.COL_INV_CLIENT_NAME)
            or original_inv.get(sc.COL_INV_BILL_TO_CLIENT)
            or client_id
        ).strip()

        self.reverse_invoice(invoice_num, source_pdf_path, pdf_action, target_dir)
        return self.create_draft(
            client_id,
            client_name,
            [str(row.get(sc.COL_TIME_ENTRY_ID) or "") for row in linked_time],
            [str(row.get(sc.COL_DISB_ID) or "") for row in linked_disbursements],
        )
