#!/usr/bin/env python3
"""Session Tracking, Persistence, and Old-School Batch Accounting Report Engine
for the CSPM Quick Expense App (v16).

Strictly complies with:
- Global Rule 9: NEVER use em-dashes (--) anywhere in email subjects, bodies, or reports.
- Global Rule 12: 100% headless execution, zero console window flashing.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cspm.quick_expense.session")

REPORT_WIDTH = 92
DOUBLE_RULE = "=" * REPORT_WIDTH
SINGLE_RULE = "-" * REPORT_WIDTH


def parse_client_device(user_agent: str) -> str:
    """Parse HTTP User-Agent string into friendly device / OS / client descriptor."""
    ua = (user_agent or "").strip()
    if not ua:
        return "Quick Expense Web Client"
    ua_lower = ua.lower()

    if "iphone" in ua_lower or "ipad" in ua_lower:
        if "crios" in ua_lower:
            return "iPhone (iOS) / Chrome"
        if "fxios" in ua_lower:
            return "iPhone (iOS) / Firefox"
        if "safari" in ua_lower or "applewebkit" in ua_lower:
            return "iPhone (iOS) / Safari PWA"
        return "iPhone (iOS) / Web App"

    if "android" in ua_lower:
        if "chrome" in ua_lower:
            return "Android / Chrome PWA"
        return "Android / Mobile Web"

    if "cros" in ua_lower:
        return "Chromebook / Chrome PWA"

    if "windows" in ua_lower:
        if "edg/" in ua_lower:
            return "Windows PC / Edge App"
        if "chrome/" in ua_lower:
            return "Windows PC / Chrome"
        if "firefox/" in ua_lower:
            return "Windows PC / Firefox"
        return "Windows PC / Desktop"

    if "macintosh" in ua_lower or "mac os x" in ua_lower:
        if "edg/" in ua_lower:
            return "Mac / Edge"
        if "chrome/" in ua_lower:
            return "Mac / Chrome"
        return "Mac / Safari"

    if "linux" in ua_lower:
        return "Linux Desktop / Chrome"

    return "Quick Expense Client"


def format_duration(start_epoch: float, end_epoch: float) -> str:
    """Format elapsed seconds into HHh MMm SSs."""
    diff = max(0, int(end_epoch - start_epoch))
    hours = diff // 3600
    minutes = (diff % 3600) // 60
    seconds = diff % 60
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


def format_now_timestamp(epoch: Optional[float] = None) -> str:
    """Format timestamp as YYYY-MM-DD HH:MM:SS TZ."""
    dt = datetime.fromtimestamp(epoch) if epoch is not None else datetime.now()
    tz_str = time.tzname[time.daylight] if time.daylight else time.tzname[0]
    tz_abbr = "".join(w[0] for w in tz_str.split()) if len(tz_str) > 4 else tz_str
    return dt.strftime("%Y-%m-%d %H:%M:%S") + f" {tz_abbr}"


def format_dot_leader(label: str, value: str, width: int = REPORT_WIDTH) -> str:
    """Format dot-leader line: Label .................. : Value (exactly width chars)."""
    val_width = width - 67
    clean_label = label.replace("—", "--")[:60]
    dots_count = max(2, 64 - len(clean_label))
    line = f"{clean_label}{'.' * dots_count} : {value:>{val_width}}"
    return line[:width].ljust(width)


def format_old_school_session_report(session: Dict[str, Any]) -> Tuple[str, str]:
    """Generate both a pure 92-column fixed-width ASCII report and a cream/green-bar HTML email wrapper.
    Rule 9 enforced: 0 em-dashes anywhere in text or HTML.
    """
    batch_id = str(session.get("batch_id") or "QE-00000000-000")
    user_id = str(session.get("user_id") or "operator")
    user_name = str(session.get("user_name") or user_id.upper()).replace("—", "--")
    operator_role = str(session.get("operator_role") or "CSPM Sub-Ledger Operator").replace("—", "--")
    device = str(session.get("device") or "Quick Expense Client").replace("—", "--")
    client_ip = str(session.get("client_ip") or "127.0.0.1")
    session_start = str(session.get("session_start") or "")
    session_end = str(session.get("session_end") or format_now_timestamp())
    session_length = str(session.get("session_length") or "00h 00m 00s")
    close_status = str(session.get("close_status") or "SESSION COMPLETED").replace("—", "--")
    reported_at = format_now_timestamp()

    txns_new = session.get("transactions_new", [])
    txns_amended = session.get("transactions_amended", [])
    all_txns = txns_new + txns_amended
    receipts_scanned = session.get("receipts_scanned", [])
    voice_commands = session.get("voice_commands", [])
    dockets = session.get("dockets_logged", [])
    invoice_actions = session.get("invoice_actions", [])
    actions = session.get("actions", [])

    # Totals computation
    count_new = len(txns_new)
    count_amended = len(txns_amended)
    filed_receipts = sum(1 for t in all_txns if t.get("receiptPath") or t.get("receiptFileName"))
    count_receipts = max(len(receipts_scanned), filed_receipts)
    count_voice = len(voice_commands)
    count_dockets = len(dockets)
    docket_hours = sum(float(d.get("hours") or 0.0) for d in dockets)

    gross_expenses = 0.0
    gross_income = 0.0
    transfers = 0.0
    total_hst = 0.0
    total_shl = 0.0
    journal_net = 0.0
    journal_hst = 0.0
    journal_gross = 0.0

    for t in all_txns:
        amt = float(t.get("amount") or 0.0)
        tax = float(t.get("taxAmount") or 0.0)
        net = round(amt - tax, 2)
        mode = str(t.get("mode") or "").strip().lower()
        ttype = str(t.get("type") or "").strip().lower()

        journal_net += net
        journal_hst += tax
        journal_gross += amt
        total_hst += tax

        if t.get("shlCredit") or "gifi 2781" in str(t.get("notes") or "").lower():
            total_shl += amt

        if mode == "income" or ttype == "income":
            gross_income += amt
        elif mode in ("transfer", "pay credit card") or ttype == "transfer":
            transfers += amt
        else:
            gross_expenses += amt

    # -------------------------------------------------------------------------
    # Build 92-Column Monospace ASCII Text
    # -------------------------------------------------------------------------
    lines: List[str] = []

    # BANNER & BATCH CONTROL HEADER
    lines.append(DOUBLE_RULE)
    lines.append("                   CORY SCHNEIDER LAW PC  //  CSPM FINANCIAL LEDGER".center(REPORT_WIDTH))
    lines.append("                  QUICK EXPENSE & SUB-LEDGER -- SESSION BATCH REPORT".center(REPORT_WIDTH))
    lines.append(DOUBLE_RULE)

    # 2-column metadata block (44 chars left, 48 chars right = 92)
    def meta_line(k1: str, v1: str, k2: str, v2: str) -> str:
        left = f"{k1:<15}: {v1[:27]:<27}"
        right = f"{k2:<15}: {v2[:31]:<31}"
        return (left + right)[:REPORT_WIDTH].ljust(REPORT_WIDTH)

    lines.append(meta_line("BATCH NO.", batch_id, "REPORTED AT", reported_at))
    lines.append(meta_line("OPERATOR", f"{user_name} (ID: {user_id})", "OPERATOR ROLE", operator_role))
    lines.append(meta_line("TERMINAL / DEV", device, "NETWORK IP", client_ip))
    lines.append(meta_line("SESSION START", session_start, "SESSION END", session_end))
    lines.append(meta_line("SESSION LENGTH", session_length, "CLOSE STATUS", close_status))
    lines.append(DOUBLE_RULE)

    # SECTION 1 -- EXECUTIVE BATCH CONTROL TOTALS
    lines.append("SECTION 1 -- EXECUTIVE BATCH CONTROL TOTALS")
    lines.append(SINGLE_RULE)
    lines.append(format_dot_leader("Total Transactions Posted (New)", str(count_new)))
    lines.append(format_dot_leader("Total Transactions Amended (Edited)", str(count_amended)))
    lines.append(format_dot_leader("Total Receipts Scanned (OCR) & Filed", str(count_receipts)))
    lines.append(format_dot_leader("Total Voice Dictation Commands Parsed", str(count_voice)))
    lines.append(format_dot_leader("Total Dockets Logged (Count / Hours)", f"{count_dockets} / {docket_hours:.1f} hrs"))
    lines.append(format_dot_leader("Gross Expenses & Outflows Posted", f"$ {gross_expenses:>10,.2f}"))
    lines.append(format_dot_leader("Gross Income & Client Receipts Posted", f"$ {gross_income:>10,.2f}"))
    lines.append(format_dot_leader("Credit Card Payments & Internal Transfers", f"$ {transfers:>10,.2f}"))
    lines.append(format_dot_leader("Total Input Tax Credits / HST Captured", f"$ {total_hst:>10,.2f}"))
    lines.append(format_dot_leader("Total PC Shareholder Loan (GIFI 2781) Credits", f"$ {total_shl:>10,.2f}"))
    lines.append(SINGLE_RULE)

    # SECTION 2 -- ITEMIZED TRANSACTION POSTING JOURNAL
    lines.append("SECTION 2 -- ITEMIZED TRANSACTION POSTING JOURNAL")
    lines.append(SINGLE_RULE)

    w_seq, w_time, w_date, w_mode, w_stream, w_payee, w_net, w_hst, w_gross = 3, 8, 10, 7, 15, 17, 8, 7, 9
    s2_hdr = f"{'SEQ':<{w_seq}} {'TIME':<{w_time}} {'TXN DATE':<{w_date}} {'MODE':<{w_mode}} {'STREAM/ENTITY':<{w_stream}} {'PAYEE/PARTICULARS':<{w_payee}} {'NET ($)':>{w_net}} {'HST ($)':>{w_hst}} {'GROSS ($)':>{w_gross}}"
    s2_div = f"{'-'*w_seq} {'-'*w_time} {'-'*w_date} {'-'*w_mode} {'-'*w_stream} {'-'*w_payee} {'-'*w_net} {'-'*w_hst} {'-'*w_gross}"
    lines.append(s2_hdr)
    lines.append(s2_div)

    if not all_txns:
        lines.append("  [No transactions recorded in this batch session]".ljust(REPORT_WIDTH))
    else:
        for idx, t in enumerate(all_txns, start=1):
            t_time = str(t.get("time") or t.get("createdAt", "")[-8:] or "00:00:00")[:8]
            t_date = str(t.get("txnDate") or t.get("date") or "")[:10]
            t_mode = str(t.get("mode") or t.get("type") or "Expense")[:7]
            raw_stream = str(t.get("streamLabel") or t.get("streamId") or "").replace("—", "-")
            # Friendly abbreviation for table column
            if "OT" in raw_stream and "Priv" in raw_stream:
                t_stream = "Deborah OT Priv"
            elif "OT" in raw_stream and "VHA" in raw_stream:
                t_stream = "Deborah OT VHA"
            elif "Sole" in raw_stream:
                t_stream = "Cory Sole Prop"
            elif "PC" in raw_stream:
                t_stream = "Cory PC Operat."
            elif "Family" in raw_stream or "Household" in raw_stream:
                t_stream = "Family Household"
            else:
                t_stream = raw_stream[:15]

            t_payee = str(t.get("payee") or t.get("party") or "Unknown")[:17]
            amt = float(t.get("amount") or 0.0)
            tax = float(t.get("taxAmount") or 0.0)
            net = round(amt - tax, 2)

            net_s = f"{net:,.2f}"[:8]
            tax_s = f"{tax:,.2f}"[:7]
            amt_s = f"{amt:,.2f}"[:9]

            row_line = f"{idx:03d} {t_time:<{w_time}} {t_date:<{w_date}} {t_mode:<{w_mode}} {t_stream:<{w_stream}} {t_payee:<{w_payee}} {net_s:>{w_net}} {tax_s:>{w_hst}} {amt_s:>{w_gross}}"
            lines.append(row_line)

            # Indented Voucher Detail Lines
            from_acc = str(t.get("fromAccountLabel") or t.get("fromAccount") or "N/A").replace("—", "-")
            to_acc = str(t.get("toAccountLabel") or t.get("toAccount") or "").replace("—", "-")
            cat_lbl = str(t.get("categoryLabel") or t.get("categoryName") or t.get("categoryCode") or "").replace("—", "-")
            cat_code = str(t.get("categoryCode") or "")
            acc_str = f"Account: {from_acc}" + (f" -> {to_acc}" if to_acc else "")
            if cat_lbl:
                acc_str += f" | GL Cat: {cat_lbl}" + (f" ({cat_code})" if cat_code and cat_code != cat_lbl else "")
            lines.append(f"     {acc_str[:85]}")

            # Payee detail if truncated in table
            full_payee = str(t.get("payee") or "").replace("—", "-")
            if len(full_payee) > 17:
                lines.append(f"     Payee  : {full_payee[:80]}")

            notes = str(t.get("notes") or t.get("expenseDetails") or "").replace("—", "-").strip()
            if notes:
                lines.append(f"     Notes  : {notes[:80]}")

            # Receipt Info
            rcpt_path = str(t.get("receiptPath") or t.get("receiptFileName") or "").replace("—", "-")
            if rcpt_path:
                lines.append(f"     Receipt: [FILED] {rcpt_path[:75]}")
            elif t.get("scannedReceipt"):
                lines.append("     Receipt: [OCR SCANNED]")
            else:
                lines.append("     Receipt: [NO RECEIPT ATTACHED]")

            # Tax / SHL / Client Rebill
            shl_tag = "Credited to Shareholder Loan (GIFI 2781)" if (t.get("shlCredit") or "gifi 2781" in notes.lower()) else ""
            matter_tag = f"Client Matter Rebill: {t['clientMatter']}" if t.get("clientMatter") else ""
            tags = " | ".join(filter(None, [shl_tag, matter_tag]))
            if tags:
                lines.append(f"     SHL/Tax: {tags[:80]}")

        # Section 2 Totals
        lines.append(DOUBLE_RULE)
        prefix_len = w_seq + 1 + w_time + 1 + w_date + 1 + w_mode + 1 + w_stream + 1 + w_payee
        tot_lbl = f"     BATCH JOURNAL TOTALS ({len(all_txns)} Items)"
        j_net_s = f"{journal_net:,.2f}"[:8]
        j_hst_s = f"{journal_hst:,.2f}"[:7]
        j_gross_s = f"{journal_gross:,.2f}"[:9]
        tot_row = f"{tot_lbl:<{prefix_len}} {j_net_s:>{w_net}} {j_hst_s:>{w_hst}} {j_gross_s:>{w_gross}}"
        lines.append(tot_row)
        lines.append(DOUBLE_RULE)

    # SECTION 3 -- DOCKETS & BILLING ACTIVITY (IF ANY IN SESSION)
    lines.append("SECTION 3 -- DOCKETS & BILLING ACTIVITY")
    lines.append(SINGLE_RULE)
    if not dockets and not invoice_actions:
        lines.append("  [No time dockets or invoice actions recorded in this batch]".ljust(REPORT_WIDTH))
    else:
        if dockets:
            w3_seq, w3_time, w3_date, w3_mat, w3_hrs, w3_rate, w3_fee, w3_narr = 3, 8, 10, 19, 6, 8, 11, 20
            s3_hdr = f"{'SEQ':<{w3_seq}} {'TIME':<{w3_time}} {'DATE':<{w3_date}} {'MATTER':<{w3_mat}} {'HOURS':>{w3_hrs}} {'RATE ($)':>{w3_rate}} {'FEE VAL ($)':>{w3_fee}} {'NARRATIVE':<{w3_narr}}"
            s3_div = f"{'-'*w3_seq} {'-'*w3_time} {'-'*w3_date} {'-'*w3_mat} {'-'*w3_hrs} {'-'*w3_rate} {'-'*w3_fee} {'-'*w3_narr}"
            lines.append(s3_hdr)
            lines.append(s3_div)
            tot_docket_fee = 0.0
            for d_idx, d in enumerate(dockets, start=1):
                d_time = str(d.get("time") or "00:00:00")[:8]
                d_date = str(d.get("date") or "")[:10]
                d_mat = str(d.get("matter") or d.get("matterId") or "")[:19]
                hrs = float(d.get("hours") or 0.0)
                rate = float(d.get("rate") or 475.0)
                fee = round(hrs * rate, 2)
                tot_docket_fee += fee
                narr = str(d.get("narrative") or "").replace("—", "-")[:20]
                row3 = f"{d_idx:03d} {d_time:<{w3_time}} {d_date:<{w3_date}} {d_mat:<{w3_mat}} {hrs:>{w3_hrs}.2f} {rate:>{w3_rate}.2f} {fee:>{w3_fee},.2f} {narr:<{w3_narr}}"
                lines.append(row3)
                if len(str(d.get("narrative") or "")) > 20:
                    lines.append(f"     Full Narrative: {str(d.get('narrative') or '').replace('—', '-')[:80]}")
            lines.append(DOUBLE_RULE)
            lines.append(f"     TOTAL DOCKET HOURS: {docket_hours:.2f} hrs  |  ESTIMATED FEES: ${tot_docket_fee:,.2f}".ljust(REPORT_WIDTH))

        if invoice_actions:
            lines.append("  -- Invoice & AR Actions:")
            for ia in invoice_actions:
                act = str(ia.get("action") or "INVOICE").replace("—", "-")
                num = str(ia.get("invoiceNumber") or ia.get("invoice") or "N/A")
                party = str(ia.get("client") or ia.get("party") or "").replace("—", "-")
                amt = float(ia.get("amount") or 0.0)
                lines.append(f"     * {act}: Inv #{num} | {party} | ${amt:,.2f}"[:88])

    lines.append(SINGLE_RULE)

    # SECTION 4 -- SUB-LEDGER BREAKDOWN BY ENTITY / STREAM
    lines.append("SECTION 4 -- SUB-LEDGER BREAKDOWN BY ENTITY / STREAM")
    lines.append(SINGLE_RULE)
    w4_ent, w4_items, w4_in, w4_out, w4_hst, w4_net = 26, 5, 14, 14, 14, 14
    s4_hdr = f"{'ENTITY / STREAM':<{w4_ent}} {'ITEMS':>{w4_items}} {'INFLOWS ($)':>{w4_in}} {'OUTFLOWS ($)':>{w4_out}} {'HST/ITC ($)':>{w4_hst}} {'NET FLOW ($)':>{w4_net}}"
    s4_div = f"{'-'*w4_ent} {'-'*w4_items} {'-'*w4_in} {'-'*w4_out} {'-'*w4_hst} {'-'*w4_net}"
    lines.append(s4_hdr)
    lines.append(s4_div)

    stream_buckets: Dict[str, Dict[str, Any]] = {}
    for t in all_txns:
        s_name = str(t.get("streamLabel") or t.get("streamId") or "FAMILY").replace("—", "-")
        amt = float(t.get("amount") or 0.0)
        tax = float(t.get("taxAmount") or 0.0)
        mode = str(t.get("mode") or t.get("type") or "").strip().lower()

        if s_name not in stream_buckets:
            stream_buckets[s_name] = {"count": 0, "inflows": 0.0, "outflows": 0.0, "hst": 0.0}
        stream_buckets[s_name]["count"] += 1
        stream_buckets[s_name]["hst"] += tax

        if mode == "income":
            stream_buckets[s_name]["inflows"] += amt
        else:
            stream_buckets[s_name]["outflows"] += amt

    tot_s4_in = sum(b["inflows"] for b in stream_buckets.values())
    tot_s4_out = sum(b["outflows"] for b in stream_buckets.values())
    tot_s4_hst = sum(b["hst"] for b in stream_buckets.values())
    tot_s4_net = tot_s4_in - tot_s4_out

    if not stream_buckets:
        lines.append("  [No stream movements recorded in this batch]".ljust(REPORT_WIDTH))
    else:
        for s_name, b in sorted(stream_buckets.items()):
            net_flow = b["inflows"] - b["outflows"]
            row4 = f"{s_name[:w4_ent]:<{w4_ent}} {b['count']:>{w4_items}} {b['inflows']:>{w4_in},.2f} {b['outflows']:>{w4_out},.2f} {b['hst']:>{w4_hst},.2f} {net_flow:>{w4_net},.2f}"
            lines.append(row4)
        lines.append(DOUBLE_RULE)
        tot4_row = f"{'TOTAL ENTITY NET FLOWS':<{w4_ent + 1 + w4_items}} {tot_s4_in:>{w4_in},.2f} {tot_s4_out:>{w4_out},.2f} {tot_s4_hst:>{w4_hst},.2f} {tot_s4_net:>{w4_net},.2f}"
        lines.append(tot4_row)

    lines.append(SINGLE_RULE)

    # SECTION 5 -- BANK & CREDIT ACCOUNT MOVEMENT SUMMARY
    lines.append("SECTION 5 -- BANK & CREDIT ACCOUNT MOVEMENT SUMMARY")
    lines.append(SINGLE_RULE)
    w5_acc, w5_items, w5_deb, w5_cred, w5_net = 28, 5, 17, 18, 20
    s5_hdr = f"{'ACCOUNT CODE & NAME':<{w5_acc}} {'ITEMS':>{w5_items}} {'DEBITS/IN ($)':>{w5_deb}} {'CREDITS/OUT ($)':>{w5_cred}} {'NET MOVEMENT ($)':>{w5_net}}"
    s5_div = f"{'-'*w5_acc} {'-'*w5_items} {'-'*w5_deb} {'-'*w5_cred} {'-'*w5_net}"
    lines.append(s5_hdr)
    lines.append(s5_div)

    acc_buckets: Dict[str, Dict[str, Any]] = {}
    for t in all_txns:
        from_acc = str(t.get("fromAccountLabel") or t.get("fromAccount") or "CASH").replace("—", "-")
        amt = float(t.get("amount") or 0.0)
        mode = str(t.get("mode") or t.get("type") or "").strip().lower()

        if from_acc not in acc_buckets:
            acc_buckets[from_acc] = {"count": 0, "debits": 0.0, "credits": 0.0}
        acc_buckets[from_acc]["count"] += 1
        if mode == "income":
            acc_buckets[from_acc]["debits"] += amt
        else:
            acc_buckets[from_acc]["credits"] += amt

        to_acc = str(t.get("toAccountLabel") or t.get("toAccount") or "").replace("—", "-")
        if to_acc:
            if to_acc not in acc_buckets:
                acc_buckets[to_acc] = {"count": 0, "debits": 0.0, "credits": 0.0}
            acc_buckets[to_acc]["count"] += 1
            acc_buckets[to_acc]["debits"] += amt

    tot_s5_deb = sum(b["debits"] for b in acc_buckets.values())
    tot_s5_cred = sum(b["credits"] for b in acc_buckets.values())
    tot_s5_net = tot_s5_deb - tot_s5_cred

    if not acc_buckets:
        lines.append("  [No account movements recorded in this batch]".ljust(REPORT_WIDTH))
    else:
        for acc_name, b in sorted(acc_buckets.items()):
            net_mov = b["debits"] - b["credits"]
            row5 = f"{acc_name[:w5_acc]:<{w5_acc}} {b['count']:>{w5_items}} {b['debits']:>{w5_deb},.2f} {b['credits']:>{w5_cred},.2f} {net_mov:>{w5_net},.2f}"
            lines.append(row5)
        lines.append(DOUBLE_RULE)
        tot5_row = f"{'TOTAL ACCOUNT MOVEMENTS':<{w5_acc + 1 + w5_items}} {tot_s5_deb:>{w5_deb},.2f} {tot_s5_cred:>{w5_cred},.2f} {tot_s5_net:>{w5_net},.2f}"
        lines.append(tot5_row)

    lines.append(SINGLE_RULE)

    # SECTION 6 -- CHRONOLOGICAL OPERATOR AUDIT TRAIL
    lines.append("SECTION 6 -- CHRONOLOGICAL OPERATOR AUDIT TRAIL")
    lines.append(SINGLE_RULE)
    w6_time, w6_code, w6_act = 8, 17, 63
    s6_hdr = f"{'TIME':<{w6_time}}  {'EVENT CODE':<{w6_code}}  {'ACTION / AUDIT DETAIL':<{w6_act}}"
    s6_div = f"{'-'*w6_time}  {'-'*w6_code}  {'-'*w6_act}"
    lines.append(s6_hdr)
    lines.append(s6_div)

    if not actions:
        lines.append("  [No audit events logged]".ljust(REPORT_WIDTH))
    else:
        for a in actions:
            raw_ts = str(a.get("timestamp") or "")
            a_time = raw_ts.split()[1][:8] if len(raw_ts.split()) >= 2 else raw_ts[:8]
            a_code = str(a.get("event_code") or "EVENT")[:w6_code]
            a_detail = str(a.get("detail") or a.get("action") or "").replace("—", "-")
            row6 = f"{a_time:<{w6_time}}  {a_code:<{w6_code}}  {a_detail[:w6_act]:<{w6_act}}"
            lines.append(row6)

    # END OF REPORT FOOTER
    lines.append(DOUBLE_RULE)
    lines.append("*** END OF SESSION BATCH REPORT -- VERIFIED BY CSPM LEDGER ENGINE (v16) ***".center(REPORT_WIDTH))
    lines.append("DELIVERED TO: cory@coryschneiderlaw.ca  |  STATUS: POSTED".center(REPORT_WIDTH))
    lines.append(DOUBLE_RULE)

    plain_text = "\n".join(lines).replace("—", "--")

    # -------------------------------------------------------------------------
    # Build Classic Green-Bar & Cream Ledger HTML Container
    # -------------------------------------------------------------------------
    escaped_text = html.escape(plain_text)
    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CSPM Quick Expense Session Report - {html.escape(batch_id)}</title>
</head>
<body style="margin: 0; padding: 24px 12px; background-color: #EDECE6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <div style="max-width: 920px; margin: 0 auto;">
    <!-- Classic 1980s/1990s Accounting Mainframe Ledger Paper Container -->
    <div style="font-family: 'Courier New', Consolas, 'Lucida Console', monospace; font-size: 12.5px; line-height: 1.38; background-color: #FDFCF7; color: #111111; border: 2px solid #222222; border-radius: 4px; padding: 20px 22px; box-shadow: 0 4px 16px rgba(0,0,0,0.15); overflow-x: auto;">
      <pre style="margin: 0; font-family: 'Courier New', Consolas, 'Lucida Console', monospace; font-size: 12.5px; line-height: 1.38; color: #111111; white-space: pre; overflow-x: auto;">{escaped_text}</pre>
    </div>
    <div style="margin-top: 14px; text-align: center; font-size: 11px; color: #666666; font-family: Consolas, monospace;">
      Automated Accounting Session Batch Report dispatched by CSPM Quick Expense Server (v16) to cory@coryschneiderlaw.ca
    </div>
  </div>
</body>
</html>
""".replace("—", "--")

    return plain_text, html_body


class SessionTracker:
    """Manages active operator sessions, records sub-ledger events, persists audit state,
    dispatches aligned batch reports via Outlook MAPI, and archives copies to disk."""

    def __init__(self, paths: Any):
        self.paths = paths
        self._lock = threading.RLock()
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._completed_sessions: List[Dict[str, Any]] = []
        self._load_audit()

    # -------------------------------------------------------------------------
    # Audit Persistence Paths
    # -------------------------------------------------------------------------
    def _audit_file_candidates(self) -> List[Path]:
        candidates: List[Path] = []
        try:
            m_dir = getattr(self.paths, "master_data_dir", None)
            master = m_dir() if callable(m_dir) else None
            if master and Path(master).exists():
                sync_dir = Path(master) / "QuickExpense_Sync"
                sync_dir.mkdir(parents=True, exist_ok=True)
                candidates.append(sync_dir / "session_audit.json")
        except Exception:
            pass
        try:
            l_dir = getattr(self.paths, "data_dir", None)
            local = l_dir() if callable(l_dir) else None
            if local:
                sync_dir = Path(local) / "QuickExpense_Sync"
                sync_dir.mkdir(parents=True, exist_ok=True)
                cand = sync_dir / "session_audit.json"
                if cand not in candidates:
                    candidates.append(cand)
        except Exception:
            pass
        try:
            for od in sorted(Path.home().glob("OneDrive*")):
                cand = od / "CSPM_Shared_Data"
                if cand.is_dir():
                    audit_p = cand / "QuickExpense_Sync" / "session_audit.json"
                    audit_p.parent.mkdir(parents=True, exist_ok=True)
                    if audit_p not in candidates:
                        candidates.append(audit_p)
                    break
        except Exception:
            pass
        return candidates

    def _reports_dir_candidates(self) -> List[Path]:
        candidates: List[Path] = []
        try:
            m_dir = getattr(self.paths, "master_data_dir", None)
            master = m_dir() if callable(m_dir) else None
            if master and Path(master).exists():
                rep_dir = Path(master) / "QuickExpense_Sync" / "Session_Reports"
                rep_dir.mkdir(parents=True, exist_ok=True)
                candidates.append(rep_dir)
        except Exception:
            pass
        try:
            l_dir = getattr(self.paths, "data_dir", None)
            local = l_dir() if callable(l_dir) else None
            if local:
                rep_dir = Path(local) / "QuickExpense_Sync" / "Session_Reports"
                rep_dir.mkdir(parents=True, exist_ok=True)
                if rep_dir not in candidates:
                    candidates.append(rep_dir)
        except Exception:
            pass
        try:
            for od in sorted(Path.home().glob("OneDrive*")):
                cand = od / "CSPM_Shared_Data"
                if cand.is_dir():
                    rep_dir = cand / "QuickExpense_Sync" / "Session_Reports"
                    rep_dir.mkdir(parents=True, exist_ok=True)
                    if rep_dir not in candidates:
                        candidates.append(rep_dir)
                    break
        except Exception:
            pass
        return candidates

    def _load_audit(self) -> None:
        for p in self._audit_file_candidates():
            if p.is_file():
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                    self._active_sessions = raw.get("active_sessions", {}) or {}
                    self._completed_sessions = raw.get("completed_sessions", []) or []
                    logger.debug("Loaded session audit from %s (%d active, %d completed)", p, len(self._active_sessions), len(self._completed_sessions))
                    return
                except Exception as exc:
                    logger.warning("Could not read session audit %s: %s", p, exc)

    def _save_audit(self) -> None:
        payload = {
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active_sessions": self._active_sessions,
            "completed_sessions": self._completed_sessions[-250:],
        }
        data = json.dumps(payload, indent=2, ensure_ascii=False)
        for p in self._audit_file_candidates():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(data, encoding="utf-8")
            except Exception as exc:
                logger.warning("Could not persist session audit to %s: %s", p, exc)

    # -------------------------------------------------------------------------
    # Active Session Management
    # -------------------------------------------------------------------------
    def _next_batch_id(self) -> str:
        today_str = datetime.now().strftime("%Y%m%d")
        prefix = f"QE-{today_str}-"
        seq = 1
        with self._lock:
            all_batches = [s.get("batch_id", "") for s in self._completed_sessions]
            all_batches += [s.get("batch_id", "") for s in self._active_sessions.values()]
            for b in all_batches:
                if b.startswith(prefix):
                    try:
                        num = int(b.split("-")[-1])
                        seq = max(seq, num + 1)
                    except Exception:
                        pass
        return f"{prefix}{seq:03d}"

    def get_or_create_active_session(
        self, user_id: str, client_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        uid = (user_id or "deborah").strip().lower()
        now_epoch = time.time()
        now_str = format_now_timestamp(now_epoch)

        with self._lock:
            session = self._active_sessions.get(uid)
            if session is None:
                batch_id = self._next_batch_id()
                is_cory = uid == "cory"
                is_deb = uid == "deborah"
                user_name = "CORY SCHNEIDER" if is_cory else ("DEBORAH" if is_deb else uid.upper())
                role = "Managing Lawyer & Partner" if is_cory else ("Family, OT & Legal Entry" if is_deb else "CSPM Sub-Ledger Operator")

                meta = client_meta or {}
                session = {
                    "batch_id": batch_id,
                    "user_id": uid,
                    "user_name": user_name,
                    "operator_role": role,
                    "device": meta.get("device") or "Quick Expense Client",
                    "client_ip": meta.get("client_ip") or "127.0.0.1",
                    "session_start": now_str,
                    "session_start_epoch": now_epoch,
                    "last_activity": now_str,
                    "last_activity_epoch": now_epoch,
                    "session_end": None,
                    "session_end_epoch": None,
                    "session_length": "00h 00m 00s",
                    "close_status": "ACTIVE",
                    "actions": [],
                    "transactions_new": [],
                    "transactions_amended": [],
                    "receipts_scanned": [],
                    "voice_commands": [],
                    "dockets_logged": [],
                    "invoice_actions": [],
                    "reports_viewed": [],
                }
                self._active_sessions[uid] = session
                self._save_audit()
            else:
                if client_meta:
                    if client_meta.get("device") and session.get("device") in ("Quick Expense Client", "Quick Expense Web Client"):
                        session["device"] = client_meta["device"]
                    if client_meta.get("client_ip"):
                        session["client_ip"] = client_meta["client_ip"]
            return session

    def record_event(
        self,
        user_id: str,
        event_code: str,
        detail: str,
        item_data: Optional[Dict[str, Any]] = None,
        client_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an action inside the active session for user_id with timestamps."""
        session = self.get_or_create_active_session(user_id, client_meta)
        now_epoch = time.time()
        now_str = format_now_timestamp(now_epoch)

        with self._lock:
            session["last_activity"] = now_str
            session["last_activity_epoch"] = now_epoch
            if client_meta:
                if client_meta.get("device"):
                    session["device"] = client_meta["device"]
                if client_meta.get("client_ip"):
                    session["client_ip"] = client_meta["client_ip"]

            clean_detail = detail.replace("—", "--")
            clean_code = event_code.replace("—", "--")
            session["actions"].append(
                {
                    "timestamp": now_str,
                    "event_code": clean_code,
                    "detail": clean_detail,
                }
            )

            # Route item data into specific bucket
            if item_data:
                clean_item = {
                    k: (str(v).replace("—", "--") if isinstance(v, str) else v)
                    for k, v in item_data.items()
                }
                if "time" not in clean_item:
                    clean_item["time"] = now_str.split()[1] if len(now_str.split()) >= 2 else now_str

                if event_code == "TXN_POST_NEW":
                    session["transactions_new"].append(clean_item)
                elif event_code == "TXN_AMEND":
                    session["transactions_amended"].append(clean_item)
                elif event_code == "RECEIPT_OCR_SCAN":
                    session["receipts_scanned"].append(clean_item)
                elif event_code == "VOICE_COMMAND":
                    session["voice_commands"].append(clean_item)
                elif event_code == "DOCKET_POST":
                    session["dockets_logged"].append(clean_item)
                elif event_code == "INVOICE_ACTION":
                    session["invoice_actions"].append(clean_item)
                elif event_code == "REPORT_VIEW":
                    session["reports_viewed"].append(clean_item)

            self._save_audit()

    def has_meaningful_activity(self, session: Dict[str, Any]) -> bool:
        """Return True if session had at least 1 saved/amended entry, receipt, voice command, docket, or invoice action."""
        return bool(
            session.get("transactions_new")
            or session.get("transactions_amended")
            or session.get("receipts_scanned")
            or session.get("voice_commands")
            or session.get("dockets_logged")
            or session.get("invoice_actions")
        )

    # -------------------------------------------------------------------------
    # Archival Report Disk Storage
    # -------------------------------------------------------------------------
    def _save_archival_reports(self, batch_id: str, plain_text: str, html_body: str) -> List[Path]:
        saved_paths: List[Path] = []
        for rep_dir in self._reports_dir_candidates():
            try:
                rep_dir.mkdir(parents=True, exist_ok=True)
                txt_p = rep_dir / f"{batch_id}_report.txt"
                html_p = rep_dir / f"{batch_id}_report.html"
                txt_p.write_text(plain_text, encoding="utf-8")
                html_p.write_text(html_body, encoding="utf-8")
                saved_paths.extend([txt_p, html_p])
            except Exception as exc:
                logger.warning("Failed saving archival report to %s: %s", rep_dir, exc)
        return saved_paths

    # -------------------------------------------------------------------------
    # Email Dispatcher via Outlook MAPI
    # -------------------------------------------------------------------------
    def _dispatch_email(self, subject: str, plain_text: str, html_body: str) -> bool:
        """Send email to cory@coryschneiderlaw.ca via Classic Outlook MAPI.
        Complies strictly with Rule 9 (no em-dashes) and Rule 12 (headless)."""
        clean_subj = subject.replace("—", "--")
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            logger.warning("win32com / pythoncom not installed; cannot send Outlook email.")
            return False

        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            mail.To = "cory@coryschneiderlaw.ca"
            mail.Subject = clean_subj
            mail.Body = plain_text
            mail.HTMLBody = html_body

            # Match account preference: cory@coryschneiderlaw.ca > cory@levipn.com
            preferred_account = None
            try:
                for acc in outlook.Session.Accounts:
                    addr = str(getattr(acc, "SmtpAddress", "") or "").lower()
                    if "cory@coryschneiderlaw.ca" in addr:
                        preferred_account = acc
                        break
                if not preferred_account:
                    for acc in outlook.Session.Accounts:
                        addr = str(getattr(acc, "SmtpAddress", "") or "").lower()
                        if "cory@levipn.com" in addr:
                            preferred_account = acc
                            break
                if preferred_account:
                    mail.SendUsingAccount = preferred_account
            except Exception as acc_exc:
                logger.debug("Outlook account enumeration note: %s", acc_exc)

            mail.Send()
            logger.info("Session batch email dispatched to cory@coryschneiderlaw.ca: %s", clean_subj)
            return True
        except Exception as exc:
            logger.warning("Outlook MAPI email dispatch warning: %s", exc)
            return False
        finally:
            pythoncom.CoUninitialize()

    # -------------------------------------------------------------------------
    # Session Finalization & Completion
    # -------------------------------------------------------------------------
    def complete_session(
        self,
        user_id: str,
        reason: str = "Operator Finished Session",
        force_send: bool = False,
        client_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Finalize an operator session, generate the batch report, send the email report if activity exists,
        archive to session_audit.json, and reset active session buffer."""
        uid = (user_id or "deborah").strip().lower()

        with self._lock:
            session = self._active_sessions.get(uid)
            if session is None:
                return {
                    "ok": True,
                    "emailed": False,
                    "batchId": None,
                    "message": "No active session in progress.",
                }

            has_act = self.has_meaningful_activity(session)
            if not has_act and not force_send:
                # Closed without activity: prune active session silently
                del self._active_sessions[uid]
                self._save_audit()
                return {
                    "ok": True,
                    "emailed": False,
                    "batchId": session.get("batch_id"),
                    "message": "Session closed (no activity to report).",
                }

            # Finalize session timing and status
            now_epoch = time.time()
            now_str = format_now_timestamp(now_epoch)
            session["session_end"] = now_str
            session["session_end_epoch"] = now_epoch
            start_epoch = float(session.get("session_start_epoch") or now_epoch)
            session["session_length"] = format_duration(start_epoch, now_epoch)
            session["close_status"] = reason.upper().replace("—", "--")

            # Record final close event
            session["actions"].append(
                {
                    "timestamp": now_str,
                    "event_code": "SESSION_CLOSE",
                    "detail": f"{reason} (Total Duration: {session['session_length']})",
                }
            )

            # Generate batch reports
            plain_text, html_body = format_old_school_session_report(session)

            # Save disk archives
            batch_id = str(session.get("batch_id"))
            self._save_archival_reports(batch_id, plain_text, html_body)

            # Build subject: [CSPM Batch #QE-YYYYMMDD-NNN] Quick Expense Session Report - <Operator> (<N> items, $<Total>)
            all_txns = session.get("transactions_new", []) + session.get("transactions_amended", [])
            item_count = len(all_txns)
            total_gross = sum(float(t.get("amount") or 0.0) for t in all_txns)
            op_name = session.get("user_name", uid.upper())
            subject = f"[CSPM Batch #{batch_id}] Quick Expense Session Report - {op_name} ({item_count} items, ${total_gross:,.2f})".replace("—", "--")

            # Dispatch email
            emailed = self._dispatch_email(subject, plain_text, html_body)

            # Archive completed session and reset active buffer
            self._completed_sessions.append(session)
            del self._active_sessions[uid]
            self._save_audit()

            return {
                "ok": True,
                "emailed": emailed,
                "batchId": batch_id,
                "itemCount": item_count,
                "totalGross": total_gross,
                "message": f"Session #{batch_id} completed! Batch report emailed to cory@coryschneiderlaw.ca" if emailed else f"Session #{batch_id} completed (Archived to disk).",
            }

    # -------------------------------------------------------------------------
    # Idle Watchdog (10 Minutes Inactivity After Entry)
    # -------------------------------------------------------------------------
    def check_and_complete_idle_sessions(self, idle_seconds: int = 600) -> List[Dict[str, Any]]:
        """Check all active sessions: if meaningful activity took place and session
        has been idle for >= idle_seconds, automatically complete and dispatch report."""
        now_epoch = time.time()
        to_finalize: List[str] = []

        with self._lock:
            for uid, s in list(self._active_sessions.items()):
                if self.has_meaningful_activity(s):
                    last_act_epoch = float(s.get("last_activity_epoch") or s.get("session_start_epoch") or now_epoch)
                    idle_time = now_epoch - last_act_epoch
                    if idle_time >= idle_seconds:
                        to_finalize.append(uid)

        results: List[Dict[str, Any]] = []
        for uid in to_finalize:
            logger.info("Auto-completing idle session for user '%s' after %d+ seconds of inactivity.", uid, idle_seconds)
            res = self.complete_session(
                user_id=uid,
                reason="Auto-Completed (10m Inactivity After Entry)",
                force_send=True,
            )
            results.append(res)
        return results
