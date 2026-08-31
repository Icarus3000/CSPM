import uuid
import logging
import math
import re
import threading
import time
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_HALF_UP

from domain.money import calc_amounts
from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo


logger = logging.getLogger(__name__)


_DRAFT_LIFECYCLE_LOCK = threading.RLock()


CUSTOM_FEE_ORIGIN = "InvoiceDraft"

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

    @classmethod
    def _bill_to_snapshot_client_name(cls, raw_snapshot: Any) -> str:
        """Read the immutable bill-to identity without trusting live client data."""
        text = cls._text(raw_snapshot)
        if not text:
            return ""
        try:
            import json
            snapshot = json.loads(text)
        except (TypeError, ValueError):
            return ""
        return cls._text(snapshot.get("clientName")) if isinstance(snapshot, dict) else ""

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

    def _read_tables_once(self, tables: List[Any]) -> Dict[Any, List[Dict[str, Any]]]:
        """Read one coherent workbook snapshot when the repository supports it."""
        read_bulk = getattr(self.repo, "_read_table_rows_bulk", None)
        if callable(read_bulk):
            return read_bulk(tables)
        return {table: self.repo._read_table_rows(table) for table in tables}

    @classmethod
    def _audit_markers(cls, row: Dict[str, Any]) -> Dict[str, str]:
        markers: Dict[str, str] = {}
        raw = cls._text(row.get(sc.COL_TIME_LOCK_AUDIT))
        for part in raw.split("||"):
            token = part.strip()
            if not token or ":" not in token:
                continue
            key, value = token.split(":", 1)
            normalized_key = key.strip().casefold()
            if normalized_key and normalized_key not in markers:
                markers[normalized_key] = value.strip()
        return markers

    @classmethod
    def _is_draft_custom_fee(cls, row: Dict[str, Any]) -> bool:
        markers = cls._audit_markers(row)
        return (
            markers.get("entrytype", "").casefold() == "fee"
            and markers.get("feeorigin", "").casefold() == CUSTOM_FEE_ORIGIN.casefold()
        )

    @staticmethod
    def _validate_custom_fee_request_id(request_id: Any) -> str:
        value = str(request_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", value):
            raise ValueError(
                "The custom-fee request identifier is missing or invalid. Reopen Add Custom Fee and try again."
            )
        return value

    @staticmethod
    def _custom_fee_line_id(draft_id: str, request_id: str) -> str:
        stable = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"cspm:invoice-draft-custom-fee:{draft_id}:{request_id}",
        )
        return f"CF_{stable.hex[:20]}"

    @staticmethod
    def _custom_fee_lock_audit(
        *,
        draft_id: str,
        draft_num: str,
        request_id: str,
        line_id: str,
        state: str,
        final_invoice_num: str = "",
    ) -> str:
        parts = [
            "EntryType:Fee",
            f"FeeOrigin:{CUSTOM_FEE_ORIGIN}",
            f"DraftOwnerID:{draft_id}",
            f"DraftRef:{draft_num}",
            f"RequestID:{request_id}",
            f"CustomFeeLineID:{line_id}",
            f"CustomFeeState:{state}",
        ]
        if final_invoice_num:
            parts.append(f"FinalInvoice:{final_invoice_num}")
        return " || ".join(parts)

    @classmethod
    def _custom_fee_result(
        cls,
        row: Dict[str, Any],
        *,
        already_created: bool,
        recovered: bool = False,
        already_finalized: bool = False,
    ) -> Dict[str, Any]:
        markers = cls._audit_markers(row)
        return {
            "ok": True,
            "entryId": cls._text(row.get(sc.COL_TIME_ENTRY_ID)),
            "customFeeLineId": markers.get("customfeelineid", ""),
            "requestId": markers.get("requestid", ""),
            "draftId": markers.get("draftownerid", ""),
            "state": markers.get("customfeestate", "Draft") or "Draft",
            "alreadyCreated": bool(already_created),
            "alreadyFinalized": bool(already_finalized),
            "recovered": bool(recovered),
        }

    @classmethod
    def _matching_custom_fee_requests(
        cls,
        rows: List[Dict[str, Any]],
        request_id: str,
    ) -> List[Dict[str, Any]]:
        request_key = request_id.casefold()
        return [
            row
            for row in rows
            if cls._is_draft_custom_fee(row)
            and cls._audit_markers(row).get("requestid", "").casefold() == request_key
        ]

    @classmethod
    def _assert_custom_fee_owner(
        cls,
        row: Dict[str, Any],
        *,
        draft_id: str,
        draft_num: str,
    ) -> None:
        markers = cls._audit_markers(row)
        if markers.get("draftownerid", "").casefold() != draft_id.casefold():
            raise ValueError("The custom-fee request belongs to a different invoice draft.")
        if markers.get("draftref", "").casefold() != draft_num.casefold():
            raise ValueError("The custom-fee ownership reference does not match this draft.")

    @classmethod
    def _custom_fee_dependency_reasons(
        cls,
        row: Dict[str, Any],
        *,
        draft_num: str,
        financial_tables: Dict[Any, List[Dict[str, Any]]],
    ) -> List[str]:
        reasons: List[str] = []
        entry_id = cls._text(row.get(sc.COL_TIME_ENTRY_ID))
        invoice_ref = cls._text(row.get(sc.COL_TIME_INVOICE_REF))
        invoice_status = cls._text(row.get(sc.COL_TIME_INVOICE_STATUS)).casefold()
        status = cls._text(row.get(sc.COL_TIME_STATUS)).casefold()
        payment_status = cls._text(row.get(sc.COL_TIME_PAYMENT_STATUS)).casefold()

        if invoice_ref.casefold() != draft_num.casefold():
            reasons.append("invoice-reference")
        if invoice_status not in {"", "draft"}:
            reasons.append("invoice-status")
        if status not in {"", "draft", "unbilled"}:
            reasons.append("record-status")
        if payment_status:
            reasons.append("payment-status")
        if cls._text(row.get(sc.COL_TIME_REISSUE_INVOICE_NUM)):
            reasons.append("reissue-reservation")
        for column, label in (
            (sc.COL_TIME_INVOICE_TOTAL, "invoice-total"),
            (sc.COL_TIME_INVOICE_AMOUNT_PAID, "invoice-payment"),
            (sc.COL_TIME_INVOICE_BALANCE_DUE, "invoice-balance"),
        ):
            if cls._money(row.get(column)) != Decimal("0.00"):
                reasons.append(label)

        exact_tokens = {entry_id.casefold(), draft_num.casefold()} - {""}
        for table, table_rows in financial_tables.items():
            for candidate in table_rows:
                values = {cls._text(value).casefold() for value in candidate.values()}
                if exact_tokens.intersection(values):
                    reasons.append(f"financial-reference:{getattr(table, 'table', table)}")
                    break
        return sorted(set(reasons))

    @staticmethod
    def _normalize_discount_type(discount_type: Any) -> str:
        dtype = str(discount_type or "").strip().casefold()
        if dtype in ("percentage", "percent", "%"):
            return "Percentage"
        elif dtype in ("flat", "fixed", "flat amount", "amount", "$"):
            return "Flat"
        return "None"

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

        discount_type = self._normalize_discount_type(draft.get(sc.COL_DRAFT_DISCOUNT_TYPE))
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

        # If flat fee, agency split, or discount is applied, compute tax on final net fees
        if is_flat_fee or agency_split_percent > 0 or discount_amt > 0:
            final_tax = round(new_fees * Decimal("0.13"), 2)
            fees_billed = new_fees
        else:
            final_tax = tax
            fees_billed = fees_to_use + disb_total

        draft[sc.COL_DRAFT_TOTAL_FEES] = str(self._money(fees_billed))
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

        invoice_fee = net if net > 0 else gross

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

    def create_draft(
        self,
        client_id: str,
        client_name: str,
        time_entry_ids: List[str],
        disb_ids: List[str] = None,
        grouping_pref: str = "matter",
        billing_recipient: Optional[Dict[str, Any]] = None,
    ) -> str:
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

        bill_to_lookup = getattr(self.repo, "list_invoice_bill_to_options", None)
        bill_to_options = bill_to_lookup(time_entry_ids + disb_ids) if callable(bill_to_lookup) else []
        bill_to_snapshot = ""
        if bill_to_options:
            requested_client_id = self._text((billing_recipient or {}).get("clientId"))
            selected = next(
                (
                    option
                    for option in bill_to_options
                    if self._text(option.get("clientId")).casefold() == requested_client_id.casefold()
                ),
                None,
            )
            if selected is None:
                raise ValueError(
                    "Select a bill-to client for this joint matter before creating the invoice draft."
                )
            import json
            bill_to_snapshot = json.dumps(
                {
                    "clientId": self._text(selected.get("clientId")),
                    "clientName": self._text(selected.get("clientName")),
                    "fullAddress": self._text(selected.get("fullAddress")),
                    "primaryEmail": self._text(selected.get("primaryEmail")),
                    "billingEmail": self._text(selected.get("billingEmail")),
                    "selectedAt": datetime.now().astimezone().isoformat(),
                },
                separators=(",", ":"),
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
            sc.COL_DRAFT_BILL_TO_SNAPSHOT: bill_to_snapshot,
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
        norm_type = self._normalize_discount_type(discount_type)
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        now_str = datetime.now().astimezone().isoformat()
        
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                row[sc.COL_DRAFT_DISCOUNT_TYPE] = norm_type
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

    def update_line_item(
        self,
        draft_num: str,
        entry_id: Any = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with _DRAFT_LIFECYCLE_LOCK:
            # Compatibility for callers from before the draft number became an
            # explicit ownership boundary: update_line_item(entry_id, data).
            if data is None and isinstance(entry_id, dict):
                data = dict(entry_id)
                legacy_entry_id = self._text(draft_num)
                owner_matches = [
                    row
                    for row in self.repo._read_table_rows(sc.TBL_TIME)
                    if self._text(row.get(sc.COL_TIME_ENTRY_ID)).casefold()
                    == legacy_entry_id.casefold()
                ]
                if len(owner_matches) != 1:
                    raise ValueError("The selected draft line could not be resolved uniquely.")
                draft_num = self._text(owner_matches[0].get(sc.COL_TIME_INVOICE_REF))
                entry_id = legacy_entry_id
            draft_num = self._text(draft_num)
            entry_id = self._text(entry_id)
            tables = self._read_tables_once([
                sc.TBL_DRAFT_INVOICES,
                sc.TBL_TIME,
                sc.TBL_DISBURSEMENTS,
                sc.TBL_RECEIVABLES,
                sc.TBL_INVOICE_LOG,
                sc.TBL_LEDGER,
                sc.TBL_TRANSACTIONS_MASTER,
            ])
            drafts = tables[sc.TBL_DRAFT_INVOICES]
            draft = next(
                (
                    row
                    for row in drafts
                    if self._text(row.get(sc.COL_DRAFT_INVOICE_NUM)).casefold()
                    == draft_num.casefold()
                ),
                None,
            )
            if not draft:
                raise ValueError("The invoice draft no longer exists. Refresh Invoice Builder.")

            time_entries = tables[sc.TBL_TIME]
            matches = [
                row
                for row in time_entries
                if self._text(row.get(sc.COL_TIME_ENTRY_ID)).casefold() == entry_id.casefold()
            ]
            if len(matches) != 1:
                raise ValueError("The selected draft line could not be resolved uniquely.")
            row = matches[0]
            if self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold() != draft_num.casefold():
                raise ValueError("The selected line no longer belongs to this invoice draft.")

            changes = dict(data or {})
            if "date" in changes:
                date_text = self._text(changes.get("date"))
                try:
                    parsed_date = datetime.strptime(date_text, "%Y-%m-%d")
                except ValueError as exc:
                    raise ValueError("Enter the line date as YYYY-MM-DD.") from exc
                if parsed_date.strftime("%Y-%m-%d") != date_text:
                    raise ValueError("Enter a valid line date as YYYY-MM-DD.")
                row[sc.COL_TIME_DATE] = date_text
            if "description" in changes:
                description = self._text(changes.get("description"))
                if not description:
                    raise ValueError("Line description cannot be blank.")
                row[sc.COL_TIME_DESC] = description

            is_fee = "entrytype:fee" in self._text(row.get(sc.COL_TIME_LOCK_AUDIT)).casefold()
            if is_fee:
                if self._is_draft_custom_fee(row):
                    draft_id = self._text(draft.get(sc.COL_DRAFT_ID))
                    self._assert_custom_fee_owner(
                        row,
                        draft_id=draft_id,
                        draft_num=draft_num,
                    )
                    financial_tables = {
                        table: tables[table]
                        for table in (
                            sc.TBL_RECEIVABLES,
                            sc.TBL_INVOICE_LOG,
                            sc.TBL_LEDGER,
                            sc.TBL_TRANSACTIONS_MASTER,
                        )
                    }
                    reasons = self._custom_fee_dependency_reasons(
                        row,
                        draft_num=draft_num,
                        financial_tables=financial_tables,
                    )
                    if reasons:
                        raise ValueError(
                            "This custom fee has a financial dependency and cannot be edited. "
                            f"Run Support Diagnostics ({', '.join(reasons)})."
                        )
                if "amount" in changes:
                    try:
                        amount = Decimal(str(changes.get("amount"))).quantize(
                            Decimal("0.01"),
                            rounding=ROUND_HALF_UP,
                        )
                    except Exception as exc:
                        raise ValueError("Enter a valid fee amount.") from exc
                    if not amount.is_finite() or amount <= Decimal("0.00"):
                        raise ValueError("Fee amount must be greater than zero.")
                    hst = self._money(amount * Decimal("0.13"))
                    row[sc.COL_TIME_HOURS] = "0.0"
                    row[sc.COL_TIME_RATE] = "0.0"
                    row[sc.COL_TIME_GROSS] = str(amount)
                    row[sc.COL_TIME_NET] = str(amount)
                    row[sc.COL_TIME_HST] = str(hst)
                    row[sc.COL_TIME_TOTAL] = str(amount + hst)
            elif "hours" in changes or "rate" in changes:
                hrs = float(changes.get("hours", row.get(sc.COL_TIME_HOURS) or 0))
                rate = float(changes.get("rate", row.get(sc.COL_TIME_RATE) or 0))
                if not math.isfinite(hrs) or not math.isfinite(rate) or hrs < 0 or rate < 0:
                    raise ValueError("Hours and hourly rate cannot be negative or invalid.")
                net = self._money(Decimal(str(hrs)) * Decimal(str(rate)))
                hst = self._money(net * Decimal("0.13"))
                row[sc.COL_TIME_HOURS] = str(hrs)
                row[sc.COL_TIME_RATE] = str(rate)
                row[sc.COL_TIME_GROSS] = str(net)
                row[sc.COL_TIME_NET] = str(net)
                row[sc.COL_TIME_HST] = str(hst)
                row[sc.COL_TIME_TOTAL] = str(net + hst)

            self._recalculate_draft_totals_in_memory(
                draft,
                time_entries,
                tables[sc.TBL_DISBURSEMENTS],
            )
            self._write_tables_once({
                sc.TBL_TIME: time_entries,
                sc.TBL_DRAFT_INVOICES: drafts,
            })
            return {"ok": True, "entryId": entry_id, "draftNum": draft_num}

    def remove_line_item(
        self,
        draft_num: str,
        entry_id: Optional[str] = None,
        delete_completely: bool = False,
    ) -> Dict[str, Any]:
        with _DRAFT_LIFECYCLE_LOCK:
            # Compatibility for callers from before the draft number became an
            # explicit ownership boundary: remove_line_item(entry_id, ...).
            if entry_id is None:
                legacy_entry_id = self._text(draft_num)
                owner_matches = [
                    row
                    for row in self.repo._read_table_rows(sc.TBL_TIME)
                    if self._text(row.get(sc.COL_TIME_ENTRY_ID)).casefold()
                    == legacy_entry_id.casefold()
                ]
                if len(owner_matches) != 1:
                    raise ValueError("The selected draft line could not be resolved uniquely.")
                draft_num = self._text(owner_matches[0].get(sc.COL_TIME_INVOICE_REF))
                entry_id = legacy_entry_id
            draft_num = self._text(draft_num)
            entry_id = self._text(entry_id)
            tables = self._read_tables_once([
                sc.TBL_DRAFT_INVOICES,
                sc.TBL_TIME,
                sc.TBL_DISBURSEMENTS,
                sc.TBL_RECEIVABLES,
                sc.TBL_INVOICE_LOG,
                sc.TBL_LEDGER,
                sc.TBL_TRANSACTIONS_MASTER,
            ])
            drafts = tables[sc.TBL_DRAFT_INVOICES]
            draft = next(
                (
                    row
                    for row in drafts
                    if self._text(row.get(sc.COL_DRAFT_INVOICE_NUM)).casefold()
                    == draft_num.casefold()
                ),
                None,
            )
            if not draft:
                raise ValueError("The invoice draft no longer exists. Refresh Invoice Builder.")

            time_entries = tables[sc.TBL_TIME]
            matches = [
                row
                for row in time_entries
                if self._text(row.get(sc.COL_TIME_ENTRY_ID)).casefold() == entry_id.casefold()
            ]
            if len(matches) != 1:
                raise ValueError("The selected draft line could not be resolved uniquely.")
            row = matches[0]
            if self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold() != draft_num.casefold():
                raise ValueError("The selected line no longer belongs to this invoice draft.")

            removed_custom_fee = self._is_draft_custom_fee(row)
            if removed_custom_fee:
                draft_id = self._text(draft.get(sc.COL_DRAFT_ID))
                self._assert_custom_fee_owner(
                    row,
                    draft_id=draft_id,
                    draft_num=draft_num,
                )
                financial_tables = {
                    table: tables[table]
                    for table in (
                        sc.TBL_RECEIVABLES,
                        sc.TBL_INVOICE_LOG,
                        sc.TBL_LEDGER,
                        sc.TBL_TRANSACTIONS_MASTER,
                    )
                }
                reasons = self._custom_fee_dependency_reasons(
                    row,
                    draft_num=draft_num,
                    financial_tables=financial_tables,
                )
                if reasons:
                    raise ValueError(
                        "This custom fee has a financial dependency and cannot be removed. "
                        f"Run Support Diagnostics ({', '.join(reasons)})."
                    )
                time_entries.remove(row)
            else:
                if delete_completely:
                    raise ValueError(
                        "Only an exclusively draft-owned custom fee can be deleted. "
                        "Use Remove to return an ordinary docket to unbilled WIP."
                    )
                row[sc.COL_TIME_INVOICE_REF] = ""
                row[sc.COL_TIME_INVOICE_STATUS] = "Unbilled"
                row[sc.COL_TIME_STATUS] = "Unbilled"
                suggested_reissue_num = self._text(
                    draft.get(sc.COL_DRAFT_REISSUE_INVOICE_NUM)
                )
                if (
                    suggested_reissue_num
                    and self._text(row.get(sc.COL_TIME_REISSUE_INVOICE_NUM)).casefold()
                    == suggested_reissue_num.casefold()
                ):
                    row[sc.COL_TIME_REISSUE_INVOICE_NUM] = ""

            self._recalculate_draft_totals_in_memory(
                draft,
                time_entries,
                tables[sc.TBL_DISBURSEMENTS],
            )
            self._write_tables_once({
                sc.TBL_TIME: time_entries,
                sc.TBL_DRAFT_INVOICES: drafts,
            })
            return {
                "ok": True,
                "entryId": entry_id,
                "draftNum": draft_num,
                "removedCustomFee": removed_custom_fee,
                "releasedToWip": not removed_custom_fee,
            }

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

    def _recover_custom_fee_request(
        self,
        *,
        draft_id: str,
        draft_num: str,
        request_id: str,
    ) -> Optional[Dict[str, Any]]:
        matches = self._matching_custom_fee_requests(
            self.repo._read_table_rows(sc.TBL_TIME),
            request_id,
        )
        if len(matches) > 1:
            raise RuntimeError(
                "Custom-fee recovery found duplicate request records. Stop and run Support Diagnostics."
            )
        if not matches:
            return None
        self._assert_custom_fee_owner(
            matches[0],
            draft_id=draft_id,
            draft_num=draft_num,
        )
        markers = self._audit_markers(matches[0])
        if (
            markers.get("customfeestate", "").casefold() != "draft"
            or self._text(matches[0].get(sc.COL_TIME_INVOICE_REF)).casefold()
            != draft_num.casefold()
            or self._text(matches[0].get(sc.COL_TIME_INVOICE_STATUS)).casefold()
            != "draft"
            or self._text(matches[0].get(sc.COL_TIME_STATUS)).casefold() != "draft"
        ):
            raise RuntimeError(
                "Custom-fee recovery found a billed-and-draft state mismatch. "
                "Stop and run Support Diagnostics."
            )
        return self._custom_fee_result(
            matches[0],
            already_created=True,
            recovered=True,
        )

    def add_custom_fee_line(self, draft_num: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or recover one draft-owned custom fee for one logical request."""
        with _DRAFT_LIFECYCLE_LOCK:
            request = dict(data or {})
            request_id = self._validate_custom_fee_request_id(request.get("requestId"))
            draft_num = self._text(draft_num)
            if not draft_num:
                raise ValueError("Select an invoice draft before adding a custom fee.")

            tables = self._read_tables_once([
                sc.TBL_DRAFT_INVOICES,
                sc.TBL_TIME,
                sc.TBL_DISBURSEMENTS,
                sc.TBL_MATTERS,
            ])
            drafts = tables[sc.TBL_DRAFT_INVOICES]
            time_entries = tables[sc.TBL_TIME]
            disbursements = tables[sc.TBL_DISBURSEMENTS]
            matters = tables[sc.TBL_MATTERS]
            draft = next(
                (
                    row
                    for row in drafts
                    if self._text(row.get(sc.COL_DRAFT_INVOICE_NUM)).casefold()
                    == draft_num.casefold()
                ),
                None,
            )
            if not draft:
                raise ValueError("The selected invoice draft no longer exists. Refresh Invoice Builder.")

            draft_id = self._text(draft.get(sc.COL_DRAFT_ID))
            if not draft_id:
                raise ValueError("The selected invoice draft is missing its stable DraftID.")

            existing = self._matching_custom_fee_requests(time_entries, request_id)
            if len(existing) > 1:
                raise RuntimeError(
                    "This custom-fee request has duplicate records. Stop and run Support Diagnostics."
                )
            if existing:
                self._assert_custom_fee_owner(
                    existing[0],
                    draft_id=draft_id,
                    draft_num=draft_num,
                )
                state = self._audit_markers(existing[0]).get("customfeestate", "Draft")
                if (
                    state.casefold() != "draft"
                    or self._text(existing[0].get(sc.COL_TIME_INVOICE_REF)).casefold()
                    != draft_num.casefold()
                    or self._text(existing[0].get(sc.COL_TIME_INVOICE_STATUS)).casefold()
                    != "draft"
                    or self._text(existing[0].get(sc.COL_TIME_STATUS)).casefold() != "draft"
                ):
                    raise RuntimeError(
                        "This custom-fee request has an inconsistent billed-and-draft state. "
                        "Stop and run Support Diagnostics."
                    )
                logger.info(
                    "Custom fee request resolved idempotently draft_id=%s request_id=%s state=%s",
                    draft_id,
                    request_id,
                    state,
                )
                return self._custom_fee_result(
                    existing[0],
                    already_created=True,
                )

            date_text = self._text(request.get("date"))
            try:
                parsed_date = datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("Enter the custom-fee date as YYYY-MM-DD.") from exc
            if parsed_date.strftime("%Y-%m-%d") != date_text:
                raise ValueError("Enter a valid custom-fee date as YYYY-MM-DD.")

            description = self._text(request.get("description"))
            if not description:
                raise ValueError("Enter a description for the custom fee.")

            try:
                amount = Decimal(str(request.get("amount"))).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
            except Exception as exc:
                raise ValueError("Enter a valid custom-fee amount.") from exc
            if not amount.is_finite() or amount <= Decimal("0.00"):
                raise ValueError("Custom-fee amount must be greater than zero.")

            matter_id = self._text(request.get("matterId"))
            matter = next(
                (
                    row
                    for row in matters
                    if self._text(row.get(sc.COL_MATTER_ID)).casefold() == matter_id.casefold()
                ),
                None,
            )
            if not matter_id or not matter:
                raise ValueError("Select a valid matter for the custom fee.")

            draft_client_id = self._text(draft.get(sc.COL_DRAFT_CLIENT_ID))
            matter_client_id = self._text(matter.get(sc.COL_MATTER_CLIENT_ID))
            if not draft_client_id or matter_client_id.casefold() != draft_client_id.casefold():
                raise ValueError("The selected matter does not belong to this invoice draft's work client.")

            represented_matter_ids = {
                self._text(row.get(sc.COL_TIME_MATTER_ID)).casefold()
                for row in time_entries
                if self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold() == draft_num.casefold()
                and self._text(row.get(sc.COL_TIME_MATTER_ID))
            }
            represented_matter_ids.update(
                self._text(row.get(sc.COL_DISB_MATTER_ID)).casefold()
                for row in disbursements
                if self._text(row.get(sc.COL_DISB_INVOICE_REF)).casefold() == draft_num.casefold()
                and self._text(row.get(sc.COL_DISB_MATTER_ID))
            )
            if matter_id.casefold() not in represented_matter_ids:
                raise ValueError("Select a matter already represented by this invoice draft.")

            line_id = self._custom_fee_line_id(draft_id, request_id)
            line_id_matches = [
                row
                for row in time_entries
                if self._text(row.get(sc.COL_TIME_ENTRY_ID)).casefold() == line_id.casefold()
            ]
            if line_id_matches:
                raise RuntimeError(
                    "The stable custom-fee line identifier is already in use. Stop and run Support Diagnostics."
                )

            tax = self._money(amount * Decimal("0.13"))
            now_stamp = datetime.now().astimezone().isoformat()
            new_row = {
                sc.COL_TIME_ENTRY_ID: line_id,
                sc.COL_TIME_DATE: date_text,
                sc.COL_TIME_CLIENT_ID: matter_client_id,
                sc.COL_TIME_MATTER_ID: matter_id,
                sc.COL_TIME_PARENT_ID: self._text(matter.get(sc.COL_MATTER_PARENT_ID)),
                sc.COL_TIME_DESC: description,
                sc.COL_TIME_HOURS: "0.0",
                sc.COL_TIME_RATE: "0.0",
                sc.COL_TIME_SHARE_PCT: "100.0",
                sc.COL_TIME_GROSS: str(amount),
                sc.COL_TIME_NET: str(amount),
                sc.COL_TIME_HST: str(tax),
                sc.COL_TIME_TOTAL: str(amount + tax),
                sc.COL_TIME_SECONDS: "0",
                sc.COL_TIME_STATUS: "Draft",
                sc.COL_TIME_INVOICE_REF: draft_num,
                sc.COL_TIME_INVOICE_STATUS: "Draft",
                sc.COL_TIME_PAYMENT_STATUS: "",
                sc.COL_TIME_INVOICE_TOTAL: "0.00",
                sc.COL_TIME_INVOICE_AMOUNT_PAID: "0.00",
                sc.COL_TIME_INVOICE_BALANCE_DUE: "0.00",
                sc.COL_TIME_INVOICE_DATE: "",
                sc.COL_TIME_REISSUE_INVOICE_NUM: "",
                sc.COL_TIME_LOCK_AUDIT: self._custom_fee_lock_audit(
                    draft_id=draft_id,
                    draft_num=draft_num,
                    request_id=request_id,
                    line_id=line_id,
                    state="Draft",
                ),
                sc.COL_TIME_CREATED: now_stamp,
            }
            time_entries.append(new_row)
            self._recalculate_draft_totals_in_memory(draft, time_entries, disbursements)

            try:
                self._write_tables_once({
                    sc.TBL_TIME: time_entries,
                    sc.TBL_DRAFT_INVOICES: drafts,
                })
            except Exception as exc:
                logger.error(
                    "Custom fee write result uncertain draft_id=%s request_id=%s error_type=%s",
                    draft_id,
                    request_id,
                    type(exc).__name__,
                )
                recovered = self._recover_custom_fee_request(
                    draft_id=draft_id,
                    draft_num=draft_num,
                    request_id=request_id,
                )
                if recovered:
                    return recovered
                raise RuntimeError(
                    "The custom fee could not be verified after the workbook write. Retry this same request."
                ) from exc

            recovered = self._recover_custom_fee_request(
                draft_id=draft_id,
                draft_num=draft_num,
                request_id=request_id,
            )
            if not recovered:
                raise RuntimeError(
                    "The custom fee write completed but read-back verification failed. Retry this same request."
                )
            recovered["alreadyCreated"] = False
            recovered["recovered"] = False
            logger.info(
                "Custom fee created draft_id=%s request_id=%s line_id=%s",
                draft_id,
                request_id,
                line_id,
            )
            return recovered

    def add_line_item(self, draft_num: str, data: Dict[str, Any]):
        if bool((data or {}).get("isFee")):
            return self.add_custom_fee_line(draft_num, data)

        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        draft = self.get_draft(draft_num)
        if not draft:
            raise ValueError(f"Draft {draft_num} not found")
            
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
        return {"ok": True, "entryId": entry_id}

    def _recover_completed_custom_fee_finalization(
        self,
        draft_num: str,
        final_invoice_num: str,
    ) -> Optional[Dict[str, Any]]:
        """Recognize a completed custom-fee finalization after a lost response."""
        tables = self._read_tables_once([
            sc.TBL_DRAFT_INVOICES,
            sc.TBL_TIME,
            sc.TBL_RECEIVABLES,
            sc.TBL_INVOICE_LOG,
            sc.TBL_LEDGER,
        ])
        if any(
            self._text(row.get(sc.COL_DRAFT_INVOICE_NUM)).casefold()
            == self._text(draft_num).casefold()
            for row in tables[sc.TBL_DRAFT_INVOICES]
        ):
            return None

        candidates = [
            row
            for row in tables[sc.TBL_TIME]
            if self._is_draft_custom_fee(row)
            and self._audit_markers(row).get("draftref", "").casefold()
            == self._text(draft_num).casefold()
        ]
        if not candidates:
            return None

        requested_invoice = self._text(final_invoice_num)
        draft_ids = {
            self._audit_markers(row).get("draftownerid", "").casefold()
            for row in candidates
        } - {""}
        completed_invoices = {
            self._audit_markers(row).get("finalinvoice", "")
            or self._text(row.get(sc.COL_TIME_INVOICE_REF))
            for row in candidates
            if self._audit_markers(row).get("customfeestate", "").casefold()
            == "finalized"
        }
        if (
            len(draft_ids) != 1
            or len(completed_invoices) != 1
            or requested_invoice not in completed_invoices
            or any(
                self._audit_markers(row).get("customfeestate", "").casefold()
                != "finalized"
                or self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold()
                != requested_invoice.casefold()
                or self._text(row.get(sc.COL_TIME_INVOICE_STATUS)).casefold() != "billed"
                for row in candidates
            )
        ):
            raise RuntimeError(
                "The invoice draft is missing but its custom-fee completion footprint is inconsistent. "
                "Stop and run Support Diagnostics."
            )

        receivable_matches = [
            row
            for row in tables[sc.TBL_RECEIVABLES]
            if self._text(row.get(sc.COL_RECV_INVOICE_NUM)).casefold()
            == requested_invoice.casefold()
        ]
        invoice_log_matches = [
            row
            for row in tables[sc.TBL_INVOICE_LOG]
            if self._text(row.get(sc.COL_INV_INVOICE_NUM)).casefold()
            == requested_invoice.casefold()
        ]
        ledger_matches = [
            row
            for row in tables[sc.TBL_LEDGER]
            if self._text(row.get(sc.COL_LEDGER_REFERENCE)).casefold()
            == requested_invoice.casefold()
            and self._text(row.get(sc.COL_LEDGER_CATEGORY)).casefold() == "revenue"
        ]
        if not (
            len(receivable_matches) == 1
            and len(invoice_log_matches) == 1
            and len(ledger_matches) == 1
        ):
            raise RuntimeError(
                "The invoice draft is missing but its financial completion records are incomplete or duplicated. "
                "Stop and run Support Diagnostics."
            )

        draft_id = next(iter(draft_ids))
        logger.info(
            "Invoice finalization recovered idempotently draft_id=%s custom_fee_count=%d",
            draft_id,
            len(candidates),
        )
        return {
            "ok": True,
            "invoiceNum": requested_invoice,
            "draftId": draft_id,
            "alreadyFinalized": True,
            "customFeeCount": len(candidates),
        }

    def finalize_draft(self, draft_num: str, final_invoice_num: str, save_dir: str):
        with _DRAFT_LIFECYCLE_LOCK:
            return self._finalize_draft_locked(draft_num, final_invoice_num, save_dir)

    def _finalize_draft_locked(self, draft_num: str, final_invoice_num: str, save_dir: str):
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
            recovered = self._recover_completed_custom_fee_finalization(
                draft_num,
                final_invoice_num,
            )
            if recovered:
                return recovered
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
            sc.TBL_MATTERS,
            sc.TBL_TRANSACTIONS_MASTER,
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
        draft_id = self._text(draft.get(sc.COL_DRAFT_ID))
        custom_fee_rows = [
            row
            for row in time_entries
            if self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold()
            == self._text(draft_num).casefold()
            and self._is_draft_custom_fee(row)
        ]
        if custom_fee_rows and not draft_id:
            raise ValueError("The invoice draft is missing its stable DraftID.")

        matters_by_id = {
            self._text(row.get(sc.COL_MATTER_ID)).casefold(): row
            for row in table_rows[sc.TBL_MATTERS]
            if self._text(row.get(sc.COL_MATTER_ID))
        }
        request_ids = set()
        line_ids = set()
        financial_tables = {
            table: table_rows[table]
            for table in (
                sc.TBL_RECEIVABLES,
                sc.TBL_INVOICE_LOG,
                sc.TBL_LEDGER,
                sc.TBL_TRANSACTIONS_MASTER,
            )
        }
        for row in custom_fee_rows:
            self._assert_custom_fee_owner(row, draft_id=draft_id, draft_num=draft_num)
            markers = self._audit_markers(row)
            if markers.get("customfeestate", "").casefold() != "draft":
                raise ValueError(
                    "A custom fee is not in the expected Draft state. Run Support Diagnostics."
                )
            request_id = self._validate_custom_fee_request_id(markers.get("requestid"))
            entry_id = self._text(row.get(sc.COL_TIME_ENTRY_ID))
            marker_line_id = self._text(markers.get("customfeelineid"))
            if not entry_id or marker_line_id.casefold() != entry_id.casefold():
                raise ValueError(
                    "A custom fee has an invalid stable line identity. Run Support Diagnostics."
                )
            if request_id.casefold() in request_ids or entry_id.casefold() in line_ids:
                raise ValueError(
                    "A custom fee request or line identity is duplicated. Run Support Diagnostics."
                )
            request_ids.add(request_id.casefold())
            line_ids.add(entry_id.casefold())

            matter_id = self._text(row.get(sc.COL_TIME_MATTER_ID))
            matter = matters_by_id.get(matter_id.casefold())
            if not matter:
                raise ValueError(
                    "A custom fee no longer references a valid matter. Repair it before finalizing."
                )
            if (
                self._text(matter.get(sc.COL_MATTER_CLIENT_ID)).casefold()
                != self._text(draft.get(sc.COL_DRAFT_CLIENT_ID)).casefold()
            ):
                raise ValueError(
                    "A custom fee matter no longer belongs to the draft work client."
                )
            reasons = self._custom_fee_dependency_reasons(
                row,
                draft_num=draft_num,
                financial_tables=financial_tables,
            )
            if reasons:
                raise ValueError(
                    "A custom fee already has a financial dependency and cannot be finalized safely. "
                    f"Run Support Diagnostics ({', '.join(reasons)})."
                )

        self._recalculate_draft_totals_in_memory(draft, time_entries, disb_entries)
        final_invoice_total = self._money(draft.get(sc.COL_DRAFT_TOTAL_DUE))
            
        now_str = datetime.now().astimezone().isoformat()
        date_str = draft.get(sc.COL_DRAFT_DATE) or now_str
        
        # 1. Update Time Entries
        for row in time_entries:
            if row.get(sc.COL_TIME_INVOICE_REF) == draft_num:
                custom_fee_markers = self._audit_markers(row) if self._is_draft_custom_fee(row) else None
                self._entry_invoice_amounts(row, normalize_fee=True)
                row[sc.COL_TIME_INVOICE_REF] = final_invoice_num
                row[sc.COL_TIME_INVOICE_STATUS] = "Billed"
                row[sc.COL_TIME_STATUS] = "Billed"
                row[sc.COL_TIME_INVOICE_DATE] = date_str
                row[sc.COL_TIME_INVOICE_TOTAL] = str(final_invoice_total)
                row[sc.COL_TIME_INVOICE_AMOUNT_PAID] = "0.00"
                row[sc.COL_TIME_INVOICE_BALANCE_DUE] = str(final_invoice_total)
                row[sc.COL_TIME_REISSUE_INVOICE_NUM] = ""
                if custom_fee_markers is not None:
                    row[sc.COL_TIME_LOCK_AUDIT] = self._custom_fee_lock_audit(
                        draft_id=custom_fee_markers["draftownerid"],
                        draft_num=custom_fee_markers["draftref"],
                        request_id=custom_fee_markers["requestid"],
                        line_id=custom_fee_markers["customfeelineid"],
                        state="Finalized",
                        final_invoice_num=final_invoice_num,
                    )
                
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
                discount_val = Decimal(str(draft.get(sc.COL_DRAFT_DISCOUNT_VALUE) or 0))
                discount_type = self._normalize_discount_type(draft.get(sc.COL_DRAFT_DISCOUNT_TYPE))
                if discount_type != "None" and discount_val > 0:
                    wip_fees = sum(
                        Decimal(str(r.get(sc.COL_TIME_NET) or 0))
                        for r in time_entries
                        if r.get(sc.COL_TIME_INVOICE_REF) == final_invoice_num
                    )
                    if discount_type == "Percentage":
                        discount_amt = self._money(wip_fees * (discount_val / Decimal("100.0")))
                        desc = f"Courtesy Discount ({discount_val}% {discount_type})"
                    else:
                        discount_amt = self._money(discount_val)
                        desc = f"Courtesy Discount ({discount_type})"

                    discount_hst = self._money(discount_amt * Decimal("0.13"))
                    discount_total = discount_amt + discount_hst
                    time_entries.append({
                        sc.COL_TIME_ENTRY_ID: f"WIP_{uuid.uuid4().hex[:8]}",
                        sc.COL_TIME_DATE: date_str,
                        sc.COL_TIME_CLIENT_ID: draft.get(sc.COL_DRAFT_CLIENT_ID),
                        sc.COL_TIME_DESC: desc,
                        sc.COL_TIME_NET: str(-discount_amt),
                        sc.COL_TIME_HST: str(-discount_hst),
                        sc.COL_TIME_TOTAL: str(-discount_total),
                        sc.COL_TIME_INVOICE_REF: final_invoice_num,
                        sc.COL_TIME_INVOICE_STATUS: "Billed",
                        sc.COL_TIME_STATUS: "Billed",
                        sc.COL_TIME_INVOICE_DATE: date_str,
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
        
        bill_to_snapshot = self._text(draft.get(sc.COL_DRAFT_BILL_TO_SNAPSHOT))
        bill_to_client_name = self._bill_to_snapshot_client_name(bill_to_snapshot) or self._text(
            draft.get(sc.COL_DRAFT_CLIENT_NAME)
        )

        # 3. Create Receivables entry
        receivables = table_rows[sc.TBL_RECEIVABLES]
        receivables.append({
            sc.COL_RECV_INVOICE_NUM: final_invoice_num,
            sc.COL_RECV_DATE: date_str,
            sc.COL_RECV_CLIENT: bill_to_client_name,
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
            sc.COL_INV_CLIENT_NAME: bill_to_client_name,
            sc.COL_INV_INVOICE_DATE: date_str,
            sc.COL_INV_TOTAL_FEES: draft.get(sc.COL_DRAFT_TOTAL_FEES),
            sc.COL_INV_TOTAL_TAX: draft.get(sc.COL_DRAFT_TOTAL_TAX),
            sc.COL_INV_AGGREGATE_BILLED: draft.get(sc.COL_DRAFT_TOTAL_DUE),
            sc.COL_INV_BILL_TO_CLIENT: bill_to_client_name,
            sc.COL_INV_BILL_TO_SNAPSHOT: bill_to_snapshot,
        })
        # 4b. Create Ledger Entry for Revenue
        ledger = table_rows[sc.TBL_LEDGER]
        ledger.append({
            sc.COL_LEDGER_ID: self.repo._new_id("LED"),
            sc.COL_LEDGER_DATE: date_str,
            sc.COL_LEDGER_CLIENT_VENDOR: bill_to_client_name,
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
        try:
            self._write_tables_once({
                sc.TBL_TIME: time_entries,
                sc.TBL_DISBURSEMENTS: disb_entries,
                sc.TBL_RECEIVABLES: receivables,
                sc.TBL_INVOICE_LOG: invoice_log,
                sc.TBL_LEDGER: ledger,
                sc.TBL_DRAFT_INVOICES: drafts,
            })
        except Exception as exc:
            logger.error(
                "Invoice finalization write result uncertain draft_id=%s error_type=%s",
                draft_id,
                type(exc).__name__,
            )
            recovered = self._recover_completed_custom_fee_finalization(
                draft_num,
                final_invoice_num,
            )
            if recovered:
                return recovered
            raise RuntimeError(
                "Invoice finalization could not be verified after the workbook write. "
                "Retry with the same invoice number."
            ) from exc
        logger.info(
            "[PERF] Invoice finalization draft_id=%s completed in %.3fs with one workbook save.",
            draft_id,
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
        Delete one draft, destroying only its exclusively owned custom fees.

        Ordinary time and disbursement WIP is released.  A draft custom fee is
        never released as ordinary WIP because it has no independent source
        record outside the draft that created it.
        """
        with _DRAFT_LIFECYCLE_LOCK:
            draft_num = self._text(draft_num)
            tables = self._read_tables_once([
                sc.TBL_DRAFT_INVOICES,
                sc.TBL_TIME,
                sc.TBL_DISBURSEMENTS,
                sc.TBL_RECEIVABLES,
                sc.TBL_INVOICE_LOG,
                sc.TBL_LEDGER,
                sc.TBL_TRANSACTIONS_MASTER,
            ])
            drafts = tables[sc.TBL_DRAFT_INVOICES]
            draft = next(
                (
                    row
                    for row in drafts
                    if self._text(row.get(sc.COL_DRAFT_INVOICE_NUM)).casefold()
                    == draft_num.casefold()
                ),
                None,
            )
            if not draft:
                return False

            draft_id = self._text(draft.get(sc.COL_DRAFT_ID))
            time_entries = tables[sc.TBL_TIME]
            owned_time = [
                row
                for row in time_entries
                if self._text(row.get(sc.COL_TIME_INVOICE_REF)).casefold()
                == draft_num.casefold()
            ]
            custom_fees = [row for row in owned_time if self._is_draft_custom_fee(row)]
            if custom_fees and not draft_id:
                raise ValueError("The invoice draft is missing its stable DraftID.")

            financial_tables = {
                table: tables[table]
                for table in (
                    sc.TBL_RECEIVABLES,
                    sc.TBL_INVOICE_LOG,
                    sc.TBL_LEDGER,
                    sc.TBL_TRANSACTIONS_MASTER,
                )
            }
            for row in custom_fees:
                self._assert_custom_fee_owner(row, draft_id=draft_id, draft_num=draft_num)
                reasons = self._custom_fee_dependency_reasons(
                    row,
                    draft_num=draft_num,
                    financial_tables=financial_tables,
                )
                if reasons:
                    raise ValueError(
                        "A custom fee has a financial dependency, so this draft cannot be deleted. "
                        f"Run Support Diagnostics ({', '.join(reasons)})."
                    )

            custom_fee_objects = {id(row) for row in custom_fees}
            owned_time_objects = {id(row) for row in owned_time}
            retained_time = []
            for row in time_entries:
                if id(row) in custom_fee_objects:
                    continue
                if id(row) in owned_time_objects:
                    row[sc.COL_TIME_INVOICE_REF] = ""
                    row[sc.COL_TIME_INVOICE_STATUS] = "Unbilled"
                    row[sc.COL_TIME_STATUS] = "Unbilled"
                    row[sc.COL_TIME_REISSUE_INVOICE_NUM] = ""
                retained_time.append(row)

            disb_entries = tables[sc.TBL_DISBURSEMENTS]
            for row in disb_entries:
                if (
                    self._text(row.get(sc.COL_DISB_INVOICE_REF)).casefold()
                    == draft_num.casefold()
                ):
                    row[sc.COL_DISB_INVOICE_REF] = ""
                    row[sc.COL_DISB_REISSUE_INVOICE_NUM] = ""

            retained_drafts = [row for row in drafts if row is not draft]
            self._write_tables_once({
                sc.TBL_TIME: retained_time,
                sc.TBL_DISBURSEMENTS: disb_entries,
                sc.TBL_DRAFT_INVOICES: retained_drafts,
            })
            logger.info(
                "Invoice draft deleted draft_id=%s custom_fee_count=%d released_wip_count=%d",
                draft_id,
                len(custom_fees),
                len(owned_time) - len(custom_fees),
            )
            return True

    def delete_drafts(self, draft_nums: list) -> bool:
        """
        Batch deletes multiple drafts.
        """
        if not draft_nums:
            return False
        with _DRAFT_LIFECYCLE_LOCK:
            deleted_any = False
            for draft_num in draft_nums:
                deleted_any = self.delete_draft(str(draft_num)) or deleted_any
            return deleted_any

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
