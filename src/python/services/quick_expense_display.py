"""Human-friendly display consolidation & clear summary math for CSPM Quick Expense.

Preserves 100% of underlying accrual double-entry rows in `cspm.db` and `CSPM.xlsm` untouched,
while consolidating paired A/P Bill (`TXN-AP-*` / `AP_PAYABLE` Expense) + immediate A/P Payment
(`TXN-APP-*` / Card-to-`AP_PAYABLE` Transfer) legs into a single clear Expense entry for UI display
and ensuring top-level summaries never sum Expenses + Transfers + Income into an inflated figure.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_AP_PAYEE_RE = re.compile(r"AP\s+Payment\s*\([^)]+\)\s*to\s+([^:]+):\s*(.*)", re.IGNORECASE)


def _is_ap_bill_leg(row: Dict[str, Any]) -> bool:
    tid = str(row.get("transactionId") or "")
    from_acct = str(row.get("fromAccount") or row.get("account") or "").strip().upper()
    mode = str(row.get("mode") or row.get("type") or "").strip().lower()
    return mode == "expense" and (from_acct == "AP_PAYABLE" or tid.upper().startswith("TXN-AP-"))


def _is_ap_payment_leg(row: Dict[str, Any]) -> bool:
    tid = str(row.get("transactionId") or "")
    to_acct = str(row.get("toAccount") or row.get("to_account") or "").strip().upper()
    mode = str(row.get("mode") or row.get("type") or "").strip().lower()
    return mode in ("transfer", "pay credit card") and (to_acct == "AP_PAYABLE" or tid.upper().startswith("TXN-APP-"))


def _extract_ap_payee_and_desc(ap_row: Dict[str, Any], app_row: Dict[str, Any]) -> Tuple[str, str]:
    payee = str(ap_row.get("payee") or app_row.get("payee") or "").strip()
    ap_det = str(ap_row.get("expenseDetails") or ap_row.get("description") or "").strip()
    app_det = str(app_row.get("expenseDetails") or app_row.get("description") or "").strip()

    extracted_desc = ap_det
    for det in (app_det, ap_det):
        m = _AP_PAYEE_RE.match(det)
        if m:
            if not payee:
                payee = m.group(1).strip()
            if not extracted_desc and m.group(2).strip():
                extracted_desc = m.group(2).strip()

    if not payee and extracted_desc:
        low_desc = extracted_desc.lower()
        if "ontario business registry" in low_desc or "obr" in low_desc:
            payee = "ServiceOntario (OBR)"
        elif "cipo" in low_desc or "intellectual property" in low_desc:
            payee = "CIPO"
        else:
            payee = extracted_desc[:48]
    return payee, extracted_desc


def consolidate_ap_entries_for_display(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pair 1-to-1 matched A/P Bill (Expense) + A/P Payment (Transfer to AP_PAYABLE) legs
    on the same date & amount into a single clear Expense showing the real payment card/bank."""
    if not entries:
        return []

    ap_indices = [i for i, r in enumerate(entries) if _is_ap_bill_leg(r)]
    app_indices = [i for i, r in enumerate(entries) if _is_ap_payment_leg(r)]
    if not ap_indices or not app_indices:
        return list(entries)

    used_app: set[int] = set()
    ap_to_app: Dict[int, int] = {}

    for i_ap in ap_indices:
        ap = entries[i_ap]
        ap_date = str(ap.get("txnDate") or ap.get("date") or "")
        ap_amt = round(float(ap.get("amount") or 0.0), 2)
        ap_notes = str(ap.get("notes") or "").strip().lower()
        ap_det = str(ap.get("expenseDetails") or "").strip().lower()
        ap_created = str(ap.get("createdAt") or "")[:19]

        best_j = None
        best_score = -1
        for j_app in app_indices:
            if j_app in used_app:
                continue
            app = entries[j_app]
            app_date = str(app.get("txnDate") or app.get("date") or "")
            app_amt = round(float(app.get("amount") or 0.0), 2)
            if ap_date != app_date or abs(ap_amt - app_amt) >= 0.005:
                continue
            score = 1
            app_notes = str(app.get("notes") or "").strip().lower()
            app_det = str(app.get("expenseDetails") or "").strip().lower()
            app_created = str(app.get("createdAt") or "")[:19]
            if ap_notes and ap_notes == app_notes:
                score += 10
            if ap_det and ap_det in app_det:
                score += 8
            if ap_created and ap_created == app_created:
                score += 4
            if score > best_score:
                best_score = score
                best_j = j_app

        if best_j is not None:
            used_app.add(best_j)
            ap_to_app[i_ap] = best_j

    if not ap_to_app:
        return list(entries)

    consolidated: List[Dict[str, Any]] = []
    for idx, row in enumerate(entries):
        if idx in used_app:
            # Skip duplicate A/P transfer settlement row; folded into its Expense row
            continue
        if idx in ap_to_app:
            app_row = entries[ap_to_app[idx]]
            merged = dict(row)
            payee, clean_desc = _extract_ap_payee_and_desc(row, app_row)
            if payee:
                merged["payee"] = payee
            if clean_desc:
                merged["expenseDetails"] = clean_desc
            if not str(merged.get("categoryName") or "").strip():
                low = (clean_desc + " " + str(merged.get("notes") or "")).lower()
                if (
                    "filing fee" in low
                    or "statutory" in low
                    or "registry" in low
                    or "incorporation" in low
                    or "amendment" in low
                    or "trademark" in low
                    or "cipo" in low
                ):
                    merged["categoryName"] = "Government & Statutory Filing Fees"
                    merged["categoryIcon"] = "🏛️"
                else:
                    merged["categoryName"] = "Business Expense"
                    merged["categoryIcon"] = merged.get("categoryIcon") or "🧾"
            # Show the actual card/bank account used to pay the A/P bill
            real_from = str(app_row.get("fromAccount") or "").strip()
            if real_from and real_from.upper() != "AP_PAYABLE":
                merged["fromAccount"] = real_from
                if app_row.get("fromAccountLabel"):
                    merged["fromAccountLabel"] = app_row["fromAccountLabel"]
                if app_row.get("fromAccountIcon"):
                    merged["fromAccountIcon"] = app_row["fromAccountIcon"]
            merged["toAccount"] = ""
            merged["toAccountLabel"] = ""
            merged["toAccountIcon"] = ""
            merged["paidViaAp"] = True
            merged["apSettlementTransactionId"] = str(app_row.get("transactionId") or "")
            if not str(merged.get("notes") or "").strip() and app_row.get("notes"):
                merged["notes"] = app_row["notes"]
            consolidated.append(merged)
        else:
            consolidated.append(row)
    return consolidated


def build_clear_today_summary(today_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute non-misleading Today summary where Expenses, Income, and standalone Transfers
    are never lumped together into an inflated total."""
    clean_rows = consolidate_ap_entries_for_display(today_rows)
    exp_rows = [r for r in clean_rows if str(r.get("mode") or r.get("type") or "").strip().lower() == "expense"]
    inc_rows = [r for r in clean_rows if str(r.get("mode") or r.get("type") or "").strip().lower() == "income"]
    xfer_rows = [
        r for r in clean_rows
        if str(r.get("mode") or r.get("type") or "").strip().lower() not in ("expense", "income")
    ]

    exp_total = round(sum(float(r.get("amount") or 0.0) for r in exp_rows), 2)
    inc_total = round(sum(float(r.get("amount") or 0.0) for r in inc_rows), 2)
    xfer_total = round(sum(float(r.get("amount") or 0.0) for r in xfer_rows), 2)

    exp_fmt = f"${exp_total:,.2f}"
    inc_fmt = f"${inc_total:,.2f}"
    xfer_fmt = f"${xfer_total:,.2f}"

    parts: List[str] = []
    if exp_rows:
        noun = "expense" if len(exp_rows) == 1 else "expenses"
        parts.append(f"{len(exp_rows)} {noun} · {exp_fmt}")
    if inc_rows:
        parts.append(f"+{inc_fmt} income")
    if xfer_rows:
        xnoun = "transfer" if len(xfer_rows) == 1 else "transfers"
        parts.append(f"{len(xfer_rows)} {xnoun} ({xfer_fmt})")

    if not parts:
        label = "Today: $0.00 spent"
    else:
        label = "Today: " + " · ".join(parts)

    return {
        "count": len(clean_rows),
        "expenseCount": len(exp_rows),
        "expenseTotal": exp_total,
        "expenseFormatted": exp_fmt,
        "incomeCount": len(inc_rows),
        "incomeTotal": inc_total,
        "incomeFormatted": inc_fmt,
        "transferCount": len(xfer_rows),
        "transferTotal": xfer_total,
        "transferFormatted": xfer_fmt,
        # Keep totalAmount/totalFormatted equal to actual expenses (never expenses + transfers!)
        "totalAmount": exp_total if exp_rows or not clean_rows else (inc_total or xfer_total),
        "totalFormatted": exp_fmt if exp_rows or not clean_rows else (inc_fmt if inc_rows else xfer_fmt),
        "summaryLabel": label,
    }


def normalize_api_payload_for_display(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure /api/bootstrap, /api/entries, and /api/report responses (whether local or
    federated from OFFICENEW) always apply A/P double-entry consolidation and clear summary math."""
    if not isinstance(payload, dict) or not payload.get("ok"):
        return payload

    if path == "/api/entries" and isinstance(payload.get("entries"), list):
        out = dict(payload)
        out["entries"] = consolidate_ap_entries_for_display(payload["entries"])
        return out

    if path == "/api/report" and isinstance(payload.get("entries"), list):
        out = dict(payload)
        clean_entries = consolidate_ap_entries_for_display(payload["entries"])
        out["entries"] = clean_entries
        out["entryCount"] = len(clean_entries)
        exp_cnt = sum(1 for e in clean_entries if str(e.get("mode") or e.get("type") or "").lower() == "expense")
        inc_cnt = sum(1 for e in clean_entries if str(e.get("mode") or e.get("type") or "").lower() == "income")
        xfer_cnt = len(clean_entries) - exp_cnt - inc_cnt
        out["expenseCount"] = exp_cnt
        out["incomeCount"] = inc_cnt
        out["transferCount"] = xfer_cnt
        # Recompute transferTotal excluding folded A/P payment legs
        xfer_tot = round(
            sum(
                float(e.get("amount") or 0.0)
                for e in clean_entries
                if str(e.get("mode") or e.get("type") or "").lower() not in ("expense", "income")
            ),
            2,
        )
        out["transferTotal"] = xfer_tot
        out["transferFormatted"] = f"${xfer_tot:,.2f}"
        # Fix per-stream entry counts after folding A/P legs
        if isinstance(out.get("byStream"), list):
            counts_by_stream: Dict[str, int] = {}
            for e in clean_entries:
                sid = str(e.get("streamId") or "")
                counts_by_stream[sid] = counts_by_stream.get(sid, 0) + 1
            new_streams = []
            for s in out["byStream"]:
                ns = dict(s)
                sid = str(ns.get("streamId") or "")
                if sid in counts_by_stream or ns.get("count", 0) > 0:
                    ns["count"] = counts_by_stream.get(sid, 0)
                new_streams.append(ns)
            out["byStream"] = new_streams
        return out

    return payload
