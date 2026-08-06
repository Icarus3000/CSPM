import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_HALF_UP

from domain.money import calc_amounts
from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo

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

    def _entry_invoice_amounts(self, row: Dict[str, Any], *, normalize_fee: bool = False) -> tuple[Decimal, Decimal]:
        """Resolve the invoiceable net amount and HST for a docket row.

        Direct-fee rows have zero hours/rate by design.  Older rows can have a
        valid ``GrossToClient`` amount but a blank/zero ``AmountToYou`` and HST;
        treating those rows as zero silently produces a $0 invoice.  The direct
        fee's positive gross value is therefore the canonical recovery source.
        """
        net = self._money(row.get(sc.COL_TIME_NET))
        tax = self._money(row.get(sc.COL_TIME_HST))
        is_direct_fee = "entrytype:fee" in str(row.get(sc.COL_TIME_LOCK_AUDIT) or "").lower()

        if is_direct_fee:
            gross = self._money(row.get(sc.COL_TIME_GROSS))
            if net <= 0 and gross > 0:
                net = gross
            if net > 0 and tax <= 0:
                tax = (net * Decimal("0.13")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if normalize_fee and net > 0:
                row[sc.COL_TIME_NET] = str(net)
                row[sc.COL_TIME_HST] = str(tax)
                row[sc.COL_TIME_TOTAL] = str(net + tax)

        return net, tax

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

        # Docket rows already hold the lawyer's share in ``AmountToYou`` and
        # the corresponding HST.  Automatically applying a further 30% split
        # merely because LIHDC is the billing client therefore deducts that
        # share a second time.  A user may still explicitly apply an agency
        # split through ``apply_agency_split`` when it is genuinely required.
        agency_split_percent = "0.0"

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
        
        fees = Decimal('0.0')
        tax = Decimal('0.0') # Initial raw tax
        for r in time_entries:
            if str(r.get(sc.COL_TIME_INVOICE_REF) or "").strip() == draft_num:
                entry_net, entry_tax = self._entry_invoice_amounts(r)
                fees += entry_net
                tax += entry_tax
                
        disb_total = Decimal('0.0')
        for r in disb_entries:
            if str(r.get(sc.COL_DISB_INVOICE_REF) or "").strip() == draft_num:
                disb_total += Decimal(str(r.get(sc.COL_DISB_AMOUNT) or 0))
                
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                is_flat_fee = str(row.get(sc.COL_DRAFT_IS_FLAT_FEE) or "False").lower() == "true"
                flat_fee_amt = Decimal(str(row.get(sc.COL_DRAFT_FLAT_FEE_AMOUNT) or 0))
                fees_to_use = flat_fee_amt if is_flat_fee else fees
                row[sc.COL_DRAFT_TOTAL_FEES] = str(self._money(fees_to_use + disb_total))
                
                discount_type = str(row.get(sc.COL_DRAFT_DISCOUNT_TYPE) or "None")
                discount_value = Decimal(str(row.get(sc.COL_DRAFT_DISCOUNT_VALUE) or 0))
                agency_split_percent = Decimal(str(row.get(sc.COL_DRAFT_AGENCY_SPLIT_PERCENT) or 0))
                
                total_base = fees_to_use + disb_total
                
                # Standard discount calculation
                if discount_type == "Percentage":
                    discount_amt = total_base * (discount_value / Decimal('100.0'))
                elif discount_type == "Flat":
                    discount_amt = discount_value
                else:
                    discount_amt = Decimal('0.0')
                    
                subtotal = max(Decimal('0.0'), total_base - discount_amt)
                
                # Agency Split calculation
                agency_split_amt = subtotal * (agency_split_percent / Decimal('100.0'))
                new_fees = max(Decimal('0.0'), subtotal - agency_split_amt)
                
                # If there's an agency split, we recalculate tax based on the post-split subtotal 
                # (Assuming 13% HST, but we only apply it to fees, not disbursements? 
                # For simplicity, if there is an agency split, we just recalculate the total tax at 13% of the new fees,
                # minus whatever was originally tax, or just use 13%)
                # Let's match billing_controller logic:
                if is_flat_fee or agency_split_percent > 0:
                     final_tax = new_fees * Decimal("0.13")
                else:
                     final_tax = tax
                     
                final_tax = self._money(final_tax)
                row[sc.COL_DRAFT_TOTAL_TAX] = str(final_tax)
                row[sc.COL_DRAFT_TOTAL_DUE] = str(self._money(new_fees + final_tax))
                row[sc.COL_DRAFT_UPDATED_AT] = datetime.now().astimezone().isoformat()
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
                    break
        self.repo._write_table_rows(sc.TBL_TIME, time_entries)
        if draft_num:
            self.recalculate_draft_totals(draft_num)

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
        import os
        import shutil
        from decimal import Decimal
        
        draft = self.get_draft(draft_num)
        if not draft:
            raise ValueError(f"Draft {draft_num} not found")

        # Never finalize from stale draft totals.  This also recovers legacy
        # direct-fee rows that have GrossToClient populated but net/HST blank.
        self.recalculate_draft_totals(draft_num)
        draft = self.get_draft(draft_num)
        if not draft:
            raise ValueError(f"Draft {draft_num} disappeared during finalization")
        final_invoice_total = self._money(draft.get(sc.COL_DRAFT_TOTAL_DUE))
            
        now_str = datetime.now().astimezone().isoformat()
        date_str = draft.get(sc.COL_DRAFT_DATE) or now_str
        
        # 1. Update Time Entries
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
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

        self.repo._write_table_rows(sc.TBL_TIME, time_entries)
        
        # 2. Update Disbursements
        disb_entries = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        for row in disb_entries:
            if row.get(sc.COL_DISB_INVOICE_REF) == draft_num:
                row[sc.COL_DISB_INVOICE_REF] = final_invoice_num
        self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, disb_entries)
        
        # 3. Create Receivables entry
        receivables = self.repo._read_table_rows(sc.TBL_RECEIVABLES)
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
        self.repo._write_table_rows(sc.TBL_RECEIVABLES, receivables)
        
        # 4. Create Invoice Log entry
        invoice_log = self.repo._read_table_rows(sc.TBL_INVOICE_LOG)
        invoice_log.append({
            sc.COL_INV_INVOICE_NUM: final_invoice_num,
            sc.COL_INV_CLIENT_NAME: draft.get(sc.COL_DRAFT_CLIENT_NAME),
            sc.COL_INV_INVOICE_DATE: date_str,
            sc.COL_INV_TOTAL_FEES: draft.get(sc.COL_DRAFT_TOTAL_FEES),
            sc.COL_INV_TOTAL_TAX: draft.get(sc.COL_DRAFT_TOTAL_TAX),
            sc.COL_INV_AGGREGATE_BILLED: draft.get(sc.COL_DRAFT_TOTAL_DUE)
        })
        self.repo._write_table_rows(sc.TBL_INVOICE_LOG, invoice_log)
        
        # 4b. Create Ledger Entry for Revenue
        ledger = self.repo._read_table_rows(sc.TBL_LEDGER)
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
        self.repo._write_table_rows(sc.TBL_LEDGER, ledger)
        
        # 5. Remove Draft
        drafts = self.repo._read_table_rows(sc.TBL_DRAFT_INVOICES)
        drafts = [d for d in drafts if d.get(sc.COL_DRAFT_INVOICE_NUM) != draft_num]
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        
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

    def reverse_invoice(self, invoice_num: str, archive_dir: str):
        """
        Reverses a finalized invoice. Reverts WIP to unbilled, removes receivables,
        and moves associated files to the REVERSED folder.
        """
        import os
        import shutil
        
        # 1. Revert Time Entries
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        for row in time_entries:
            if row.get(sc.COL_TIME_INVOICE_REF) == invoice_num:
                row[sc.COL_TIME_INVOICE_REF] = ""
                row[sc.COL_TIME_INVOICE_STATUS] = "Unbilled"
                row[sc.COL_TIME_INVOICE_DATE] = ""
        self.repo._write_table_rows(sc.TBL_TIME, time_entries)
        
        # 2. Revert Disbursements
        disb_entries = self.repo._read_table_rows(sc.TBL_DISBURSEMENTS)
        for row in disb_entries:
            if row.get(sc.COL_DISB_INVOICE_REF) == invoice_num:
                row[sc.COL_DISB_INVOICE_REF] = ""
        self.repo._write_table_rows(sc.TBL_DISBURSEMENTS, disb_entries)
        
        # 3. Void Receivables
        receivables = self.repo._read_table_rows(sc.TBL_RECEIVABLES)
        for r in receivables:
            if r.get(sc.COL_RECV_INVOICE_NUM) == invoice_num:
                r[sc.COL_RECV_STATUS] = "Void"
        self.repo._write_table_rows(sc.TBL_RECEIVABLES, receivables)
        
        # 4. Void in Invoice Log (add -V reversal entry)
        invoice_log = self.repo._read_table_rows(sc.TBL_INVOICE_LOG)
        original_inv = next((i for i in invoice_log if i.get(sc.COL_INV_INVOICE_NUM) == invoice_num), None)
        if original_inv:
            void_inv = dict(original_inv)
            void_inv[sc.COL_INV_INVOICE_NUM] = f"{invoice_num}-V"
            for amount_col in [sc.COL_INV_TOTAL_FEES, sc.COL_INV_TOTAL_DISBURSEMENTS, sc.COL_INV_TOTAL_TAX, sc.COL_INV_AGGREGATE_BILLED]:
                val = void_inv.get(amount_col)
                if val:
                    try:
                        void_inv[amount_col] = -float(val)
                    except ValueError:
                        pass
            invoice_log.append(void_inv)
            self.repo._write_table_rows(sc.TBL_INVOICE_LOG, invoice_log)
        
        # 5. Move files to REVERSED
        reversed_dir = os.path.join(archive_dir, "REVERSED")
        os.makedirs(reversed_dir, exist_ok=True)
        
        receivable_dir = os.path.join(archive_dir, "Receivable")
        finalized_dir = os.path.join(archive_dir, "Finalized")
        
        for search_dir in [receivable_dir, finalized_dir]:
            if os.path.exists(search_dir):
                for f in os.listdir(search_dir):
                    if invoice_num in f:
                        shutil.move(os.path.join(search_dir, f), os.path.join(reversed_dir, f))
                        
        return True
