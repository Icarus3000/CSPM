import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from decimal import Decimal

from domain.money import calc_amounts
from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo

class InvoiceDraftService:
    def __init__(self, repo: ExcelRepo):
        self.repo = repo

    def create_draft(self, client_id: str, client_name: str, time_entry_ids: List[str], disb_ids: List[str] = None, grouping_pref: str = "matter") -> str:
        """
        Creates a new draft invoice aggregating the specified time entries and disbursements.
        Assigns a temporary DRAFT-xxx invoice reference to them.
        """
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
        
        if disb_ids is None:
            disb_ids = []

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
                
                net = Decimal(str(row.get(sc.COL_TIME_NET) or 0))
                tax = Decimal(str(row.get(sc.COL_TIME_HST) or 0))
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

        # Determine if LIHDC is the billing client
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
                        old_fees = sum(Decimal(str(r.get(sc.COL_TIME_NET) or 0)) for r in remaining_time)
                        old_tax = sum(Decimal(str(r.get(sc.COL_TIME_HST) or 0)) for r in remaining_time)
                        old_disb_total = sum(Decimal(str(r.get(sc.COL_DISB_AMOUNT) or 0)) for r in remaining_disb)
                        
                        d[sc.COL_DRAFT_TOTAL_FEES] = str(old_fees + old_disb_total)
                        d[sc.COL_DRAFT_TOTAL_TAX] = str(old_tax)
                        d[sc.COL_DRAFT_TOTAL_DUE] = str(old_fees + old_disb_total + old_tax)
                        d[sc.COL_DRAFT_UPDATED_AT] = now_str
                drafts_to_keep.append(d)
            drafts = drafts_to_keep
            
        drafts.append(draft_record)
        self.repo._write_table_rows(sc.TBL_DRAFT_INVOICES, drafts)
        
        # If there's a default agency split, recalculate immediately to ensure math is correct
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
                fees += Decimal(str(r.get(sc.COL_TIME_NET) or 0))
                tax += Decimal(str(r.get(sc.COL_TIME_HST) or 0))
                
        disb_total = Decimal('0.0')
        for r in disb_entries:
            if str(r.get(sc.COL_DISB_INVOICE_REF) or "").strip() == draft_num:
                disb_total += Decimal(str(r.get(sc.COL_DISB_AMOUNT) or 0))
                
        for row in drafts:
            if row.get(sc.COL_DRAFT_INVOICE_NUM) == draft_num:
                row[sc.COL_DRAFT_TOTAL_FEES] = str(fees + disb_total)
                
                discount_type = str(row.get(sc.COL_DRAFT_DISCOUNT_TYPE) or "None")
                discount_value = Decimal(str(row.get(sc.COL_DRAFT_DISCOUNT_VALUE) or 0))
                agency_split_percent = Decimal(str(row.get(sc.COL_DRAFT_AGENCY_SPLIT_PERCENT) or 0))
                
                total_base = fees + disb_total
                
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
                if agency_split_percent > 0:
                     final_tax = new_fees * Decimal("0.13")
                else:
                     final_tax = tax
                     
                row[sc.COL_DRAFT_TOTAL_TAX] = str(final_tax)
                row[sc.COL_DRAFT_TOTAL_DUE] = str(new_fees + final_tax)
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
                if "hours" in data:
                    hrs = float(data["hours"])
                    row[sc.COL_TIME_HOURS] = str(hrs)
                    rate = float(row.get(sc.COL_TIME_RATE) or 0)
                    net = hrs * rate
                    row[sc.COL_TIME_NET] = str(net)
                    row[sc.COL_TIME_HST] = str(net * 0.13) # Assume 13% for now, consistent with create_draft
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
        hrs = float(data.get("hours") or 0)
        rate = float(data.get("rate") or 0)
        net = hrs * rate
        
        new_row = {
            sc.COL_TIME_ENTRY_ID: entry_id,
            sc.COL_TIME_MATTER_ID: data.get("matterId") or "",
            sc.COL_TIME_CLIENT_ID: draft.get(sc.COL_DRAFT_CLIENT_ID),
            sc.COL_TIME_DATE: data.get("date") or datetime.now().strftime("%Y-%m-%d"),
            sc.COL_TIME_DESC: data.get("description") or "New Time Entry",
            sc.COL_TIME_HOURS: str(hrs),
            sc.COL_TIME_RATE: str(rate),
            sc.COL_TIME_NET: str(net),
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
            
        now_str = datetime.now().astimezone().isoformat()
        date_str = draft.get(sc.COL_DRAFT_DATE) or now_str
        
        # 1. Update Time Entries
        time_entries = self.repo._read_table_rows(sc.TBL_TIME)
        for row in time_entries:
            if row.get(sc.COL_TIME_INVOICE_REF) == draft_num:
                row[sc.COL_TIME_INVOICE_REF] = final_invoice_num
                row[sc.COL_TIME_INVOICE_STATUS] = "Billed"
                row[sc.COL_TIME_STATUS] = "Billed"
                row[sc.COL_TIME_INVOICE_DATE] = date_str
                
        # 1b. Handle WIP Adjustments for Discounts
        discount_val = draft.get(sc.COL_DRAFT_DISCOUNT_VALUE)
        try:
            if discount_val and Decimal(str(discount_val)) > 0:
                time_entries.append({
                    sc.COL_TIME_ID: self.repo._new_id("WIP"),
                    sc.COL_TIME_DATE: date_str,
                    sc.COL_TIME_CLIENT: draft.get(sc.COL_DRAFT_CLIENT_NAME),
                    sc.COL_TIME_WORK_CLIENT: draft.get(sc.COL_DRAFT_CLIENT_NAME),
                    sc.COL_TIME_TK: "SYSTEM",
                    sc.COL_TIME_DESCRIPTION: f"Courtesy Discount ({draft.get(sc.COL_DRAFT_DISCOUNT_TYPE)})",
                    sc.COL_TIME_NET: str(-Decimal(str(discount_val))),
                    sc.COL_TIME_HST: "0.00",
                    sc.COL_TIME_TOTAL: str(-Decimal(str(discount_val))),
                    sc.COL_TIME_INVOICE_REF: final_invoice_num,
                    sc.COL_TIME_INVOICE_STATUS: "Billed",
                    sc.COL_TIME_STATUS: "Billed",
                    sc.COL_TIME_INVOICE_DATE: date_str
                })
        except Exception as e:
            print("Failed to apply discount WIP adjustment:", e)

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
