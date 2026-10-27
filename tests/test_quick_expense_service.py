from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1] / "src" / "python"
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from repositories.excel_repo import ExcelRepo
from services.paths import AppPaths
from services.quick_expense_service import QuickExpenseService


def _make_service(tmp_path: Path) -> QuickExpenseService:
    paths = AppPaths(
        root=AppPaths.project_root(),
        override_data_dir=tmp_path,
        override_master_dir=tmp_path / "shared",
    )
    repo = ExcelRepo(paths)
    return QuickExpenseService(paths=paths, repo=repo)


def test_authentication_and_deborah_account_firewall(tmp_path: Path):
    svc = _make_service(tmp_path)

    # 1. Deborah PIN sign-in (4867)
    bad_deb = svc.authenticate("deborah", pin="0000")
    assert bad_deb["ok"] is False

    deb_auth = svc.authenticate("deborah", pin="4867")
    assert deb_auth["ok"] is True
    assert deb_auth["user"]["userId"] == "deborah"

    # 2. Cory PIN sign-in
    bad_cory = svc.authenticate("cory", pin="0000")
    assert bad_cory["ok"] is False

    good_cory = svc.authenticate("cory", pin="1977")
    assert good_cory["ok"] is True
    assert good_cory["user"]["userId"] == "cory"

    # 3. Bootstrap account visibility firewall
    deb_boot = svc.get_bootstrap_data("deborah")
    cory_boot = svc.get_bootstrap_data("cory")

    deb_codes = {a["accountCode"] for a in deb_boot["accounts"]}
    cory_codes = {a["accountCode"] for a in cory_boot["accounts"]}

    # Restricted accounts MUST NEVER appear for Deborah
    for restricted in ("KOHO", "WEALTHSIMPLE", "EQ_ACCOUNT", "EQ_CARD", "CIBC_LOC"):
        assert restricted not in deb_codes, f"{restricted} leaked to Deborah!"
        assert restricted in cory_codes, f"{restricted} missing for Cory!"

    # Required accounts MUST appear for Deborah
    for expected in (
        "SIMPLII_VISA",
        "TRIANGLE_MASTERCARD",
        "CIBC_CHEQUING",
        "CIBC_SAVINGS",
        "SIMPLII_CHEQUING",
        "CIBC_PC_GENERAL",
        "CIBC_PC_TRUST",
    ):
        assert expected in deb_codes

    # Verify CIBC Personal Chequing label distinction
    deb_by_code = {a["accountCode"]: a for a in deb_boot["accounts"]}
    assert deb_by_code["CIBC_CHEQUING"]["accountName"] == "CIBC Personal Chequing"
    assert deb_by_code["CIBC_SAVINGS"]["accountName"] == "CIBC PC Savings"
    assert deb_by_code["CIBC_PC_GENERAL"]["accountName"] == "CIBC PC General"
    assert deb_by_code["CIBC_PC_TRUST"]["shortName"] == "CIBC PC Trust"
    assert "Client Money In / Out to General Only" in deb_by_code["CIBC_PC_TRUST"]["accountName"]
    assert deb_by_code["CIBC_PC_TRUST"]["isTrust"] is True

    # Verify separate CIBC Mortgage and Home Trust Mortgage categories exist
    cat_codes = {c["categoryCode"]: c for c in deb_boot["categories"]}
    assert "EXP_MORTGAGE_CIBC" in cat_codes
    assert "EXP_MORTGAGE_HOME_TRUST" in cat_codes
    assert cat_codes["EXP_MORTGAGE_CIBC"]["categoryName"] == "CIBC Mortgage"
    assert cat_codes["EXP_MORTGAGE_HOME_TRUST"]["categoryName"] == "Home Trust Mortgage"


def test_cibc_pc_trust_strict_guardrails(tmp_path: Path):
    svc = _make_service(tmp_path)

    # 1. Blocked for Expense
    res_exp = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-11-05",
            "mode": "Expense",
            "streamId": "CORY_PC",
            "fromAccount": "CIBC_PC_TRUST",
            "categoryCode": "EXP_SOFTWARE_SAAS",
            "payee": "Clio",
            "amount": 113.00,
        },
    )
    assert res_exp["ok"] is False
    assert "Trust" in res_exp["message"]

    # 2. Blocked for Credit Card Payment
    res_cc = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-11-05",
            "mode": "Pay Credit Card",
            "streamId": "CORY_PC",
            "fromAccount": "CIBC_PC_TRUST",
            "toAccount": "SIMPLII_VISA",
            "amount": 250.00,
        },
    )
    assert res_cc["ok"] is False
    assert "Trust" in res_cc["message"]

    # 3. Blocked for Transfer to Personal Chequing
    res_bad_xfer = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-11-05",
            "mode": "Transfer",
            "streamId": "CORY_PC",
            "fromAccount": "CIBC_PC_TRUST",
            "toAccount": "CIBC_CHEQUING",
            "amount": 500.00,
        },
    )
    assert res_bad_xfer["ok"] is False
    assert "CIBC PC General" in res_bad_xfer["message"]

    # 4. ALLOWED for Money In from Clients (Income under Cory PC)
    res_trust_in = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-11-05",
            "mode": "Income",
            "streamId": "CORY_PC",
            "toAccount": "CIBC_PC_TRUST",
            "categoryCode": "INC_RETAINER_RECEIPTS",
            "payee": "Acme Corp Client Retainer",
            "amount": 2500.00,
            "notes": "Client retainer deposit into trust",
        },
    )
    assert res_trust_in["ok"] is True, res_trust_in

    # 5. ALLOWED for Money Out to General (Transfer CIBC_PC_TRUST -> CIBC_PC_GENERAL)
    res_trust_out = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-11-06",
            "mode": "Transfer",
            "streamId": "CORY_PC",
            "fromAccount": "CIBC_PC_TRUST",
            "toAccount": "CIBC_PC_GENERAL",
            "amount": 1130.00,
            "notes": "Transfer trust funds to PC general for Invoice 26-0043-PC",
        },
    )
    assert res_trust_out["ok"] is True, res_trust_out


def test_entry_visibility_firewall_and_shareholder_loan_sync(tmp_path: Path):
    svc = _make_service(tmp_path)

    # 1. Deborah logs a Family CIBC Mortgage payment
    r1 = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-11-02",
            "mode": "Expense",
            "streamId": "FAMILY",
            "member": "Joint",
            "fromAccount": "CIBC_CHEQUING",
            "categoryCode": "EXP_MORTGAGE_CIBC",
            "payee": "CIBC Mortgages",
            "amount": 2100.00,
            "notes": "Monthly CIBC mortgage",
        },
    )
    assert r1["ok"] is True

    # 2. Deborah logs a PC business expense paid on Simplii Visa -> auto-credits GIFI 2781
    r2 = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-11-03",
            "mode": "Expense",
            "streamId": "CORY_PC",
            "fromAccount": "SIMPLII_VISA",
            "categoryCode": "EXP_OFFICE_SUPPLIES",
            "payee": "Staples",
            "amount": 113.00,
            "taxAmount": 13.00,
            "notes": "Printer paper for PC",
        },
    )
    assert r2["ok"] is True
    shl_rows = svc.repo.list_shareholder_loan_entries(biller_entity="PC")
    linked_shl = [r for r in shl_rows if r.get("linkedTransactionId") == r2["transactionId"]]
    assert len(linked_shl) == 1
    assert float(linked_shl[0]["grossAmount"]) == 113.00

    # 3. Cory logs a restricted KOHO expense and a non-restricted CIBC_PC_GENERAL expense
    r3_restricted = svc.save_entry(
        "cory",
        {
            "txnDate": "2026-11-03",
            "mode": "Expense",
            "streamId": "FAMILY",
            "member": "Cory",
            "fromAccount": "KOHO",
            "categoryCode": "EXP_DINING",
            "payee": "Private Cafe",
            "amount": 45.00,
        },
    )
    assert r3_restricted["ok"] is True

    r4_shared = svc.save_entry(
        "cory",
        {
            "txnDate": "2026-11-04",
            "mode": "Expense",
            "streamId": "CORY_PC",
            "fromAccount": "CIBC_PC_GENERAL",
            "categoryCode": "EXP_SOFTWARE_SAAS",
            "payee": "Microsoft 365",
            "amount": 56.50,
            "taxAmount": 6.50,
        },
    )
    assert r4_shared["ok"] is True

    # 4. Verify Deborah's report includes r1, r2, and r4_shared, but NEVER r3_restricted (KOHO)
    deb_report = svc.build_report("deborah", period="all")
    deb_txn_ids = {e["transactionId"] for e in deb_report["entries"]}
    assert r1["transactionId"] in deb_txn_ids
    assert r2["transactionId"] in deb_txn_ids
    assert r4_shared["transactionId"] in deb_txn_ids
    assert r3_restricted["transactionId"] not in deb_txn_ids

    # 5. Verify Cory's report includes all 4
    cory_report = svc.build_report("cory", period="all")
    cory_txn_ids = {e["transactionId"] for e in cory_report["entries"]}
    assert r3_restricted["transactionId"] in cory_txn_ids
    assert len(cory_txn_ids) >= 4

    # 6. Verify editing in-place and deleting
    r1_edit = svc.save_entry(
        "deborah",
        {
            "transactionId": r1["transactionId"],
            "txnDate": "2026-11-02",
            "mode": "Expense",
            "streamId": "FAMILY",
            "member": "Joint",
            "fromAccount": "CIBC_CHEQUING",
            "categoryCode": "EXP_MORTGAGE_HOME_TRUST",
            "payee": "Home Trust",
            "amount": 1850.00,
        },
    )
    assert r1_edit["ok"] is True
    assert r1_edit["entry"]["categoryCode"] == "EXP_MORTGAGE_HOME_TRUST"
    assert r1_edit["entry"]["amount"] == 1850.00

    # Deborah cannot delete Cory's restricted entry
    del_restricted = svc.delete_entry("deborah", r3_restricted["transactionId"])
    assert del_restricted["ok"] is False

    # Deborah can delete her own entry
    del_ok = svc.delete_entry("deborah", r2["transactionId"])
    assert del_ok["ok"] is True
    # Linked shareholder loan entry should also be removed
    shl_after = [
        r
        for r in svc.repo.list_shareholder_loan_entries(biller_entity="PC")
        if r.get("linkedTransactionId") == r2["transactionId"]
    ]
    assert len(shl_after) == 0


def test_onedrive_inbox_queue_and_flush(tmp_path: Path):
    svc = _make_service(tmp_path)
    queued_item = {
        "transactionId": "TXN_QUEUE_TEST1",
        "txnDate": "2026-11-07",
        "class": "Business",
        "businessUnit": "Deborah OT - Private",
        "type": "Expense",
        "fromAccount": "SIMPLII_VISA",
        "toAccount": "",
        "payee": "Therapy Shoppe",
        "categoryCode": "EXP_CLINICAL_SUPPLIES",
        "categoryName": "Therapy & Clinical Supplies",
        "member": "Deborah",
        "amount": 88.25,
        "taxAmount": 0.0,
        "taxFlag": "Business Deductible",
        "hstExempt": 1,
        "generalOfficeExpense": 1,
        "expenseDetails": "Sensory tools",
        "notes": "Sensory tools [Entered by Deborah]",
        "status": "Cleared",
        "currency": "CAD",
        "billerEntity": "DEBORAH_OT",
    }
    svc._write_queued_entries([queued_item])
    assert len(svc._read_queued_entries()) == 1

    flushed = svc.flush_pending_inbox()
    assert flushed["ok"] is True
    assert flushed["flushedCount"] == 1
    assert flushed["remainingCount"] == 0

    entries = svc.list_entries("deborah", period="all")
    assert any(e["payee"] == "Therapy Shoppe" and e["streamId"] == "DEBORAH_OT_PRIVATE" for e in entries)


def test_docket_cory_only_and_payment_multi_field_search(tmp_path: Path):
    svc = _make_service(tmp_path)

    # 1. Docketing is restricted to Cory only
    assert svc.list_docket_matters("deborah")["ok"] is False
    assert svc.save_docket_entry("deborah", {"matter": "M-1", "hours": 1.0, "description": "test"})["ok"] is False

    cory_matters = svc.list_docket_matters("cory")
    assert cory_matters["ok"] is True

    d_res = svc.save_docket_entry(
        "cory",
        {
            "matterId": "M_ACME_01",
            "clientName": "Acme Corp",
            "date": "2026-11-05",
            "hours": 1.5,
            "rate": 475.0,
            "description": "review correspondence from James; draft and revise memorandum",
        },
    )
    assert d_res["ok"] is True
    assert d_res["syncedLegacyDockets"] is True
    entry_id = d_res["entryId"]

    # Verify matter-filtered recentDockets returns this docket
    by_matter = svc.list_docket_matters("cory", matter_id="M_ACME_01")
    assert by_matter["ok"] is True
    assert any(d["entryId"] == entry_id and d["hours"] == 1.5 for d in by_matter["recentDockets"])

    # Edit docket in place
    edit_res = svc.save_docket_entry(
        "cory",
        {
            "entryId": entry_id,
            "matterId": "M_ACME_01",
            "clientName": "Acme Corp",
            "date": "2026-11-06",
            "hours": 2.0,
            "rate": 475.0,
            "description": "review correspondence from James; finalize memorandum",
        },
    )
    assert edit_res["ok"] is True
    assert edit_res["updated"] is True
    by_matter_after_edit = svc.list_docket_matters("cory", matter_id="M_ACME_01")
    assert any(
        d["entryId"] == entry_id and d["hours"] == 2.0 and "finalize memorandum" in d["description"]
        for d in by_matter_after_edit["recentDockets"]
    )

    # Delete docket (restricted for Deborah, allowed for Cory)
    assert svc.delete_docket_entry("deborah", {"entryId": entry_id})["ok"] is False
    del_docket = svc.delete_docket_entry("cory", {"entryId": entry_id})
    assert del_docket["ok"] is True
    by_matter_after_del = svc.list_docket_matters("cory", matter_id="M_ACME_01")
    assert not any(d["entryId"] == entry_id for d in by_matter_after_del["recentDockets"])

    # 2. Seed an open invoice in Receivables and test 4-way Payment Search (Amount, Client, Billing Client, Invoice #)
    svc.repo.save_receivable(
        {
            "invoiceNum": "26-0042-PC",
            "date": "2026-10-20",
            "client": "Apex Holdings Inc.",
            "workClient": "Acme Operating Ltd.",
            "billingClient": "Apex Holdings Inc.",
            "totalInvoiced": 1695.00,
            "amountPaid": 0.00,
            "creditsAdj": 0.00,
            "balanceDue": 1695.00,
            "status": "Open",
        }
    )

    # Search by Invoice Number
    by_inv = svc.search_payment_invoices("deborah", query="26-0042-PC", force_refresh=True)
    assert by_inv["ok"] is True
    assert any(i["invoice"] == "26-0042-PC" for i in by_inv["invoices"])

    # Search by Dollar Amount (±5% tolerance)
    by_amt = svc.search_payment_invoices("deborah", query="1695")
    assert any(i["invoice"] == "26-0042-PC" for i in by_amt["invoices"])

    # Search by Work Client & Billing Client
    by_wc = svc.search_payment_invoices("deborah", query="Acme Operating")
    assert any(i["invoice"] == "26-0042-PC" for i in by_wc["invoices"])

    by_bc = svc.search_payment_invoices("deborah", query="Apex Holdings")
    assert any(i["invoice"] == "26-0042-PC" for i in by_bc["invoices"])

    # Post payment as Deborah
    pay_res = svc.post_payment_entry(
        "deborah",
        {
            "invoice": "26-0042-PC",
            "date": "2026-11-06",
            "amount": 1695.00,
            "depositAccount": "CIBC_PC_GENERAL",
            "method": "e-Transfer",
            "reference": "ETR-9912",
        },
    )
    assert pay_res["ok"] is True

    # After full payment, open-only search should exclude it, while include_paid=True includes it
    open_only = svc.search_payment_invoices("deborah", query="26-0042-PC", include_paid=False, force_refresh=True)
    assert not any(i["invoice"] == "26-0042-PC" for i in open_only["invoices"])

    with_paid = svc.search_payment_invoices("deborah", query="26-0042-PC", include_paid=True)
    assert any(i["invoice"] == "26-0042-PC" and i["status"] == "Paid" for i in with_paid["invoices"])


def test_v12_receipts_voice_charts_and_tax_snapshot(tmp_path: Path):
    import base64

    svc = _make_service(tmp_path)

    # 1. Receipt OCR text parser (Costco mixed-HST receipt)
    ocr_sample = """
    COSTCO WHOLESALE
    14110 Yonge St, Aurora ON
    Date: 2026-10-24
    SUBTOTAL 210.36
    HST 13% 8.14
    TOTAL 218.50
    MASTERCARD 218.50
    """
    parsed = svc._parse_receipt_ocr_text(ocr_sample, user_id="deborah")
    assert parsed["payee"] == "Costco Wholesale"
    assert parsed["txnDate"] == "2026-10-24"
    assert parsed["amount"] == 218.50
    assert parsed["taxAmount"] == 8.14
    assert parsed["hstMode"] == "custom"
    assert parsed["fromAccount"] == "TRIANGLE_MASTERCARD"
    assert parsed["categoryCode"] == "EXP_GROCERIES"

    # 2. Scan & stage receipt + auto-file into Tax-Ready folder on save
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    scan_res = svc.scan_and_stage_receipt(
        "deborah",
        {
            "fileName": "dental_receipt.png",
            "mimeType": "image/png",
            "dataBase64": base64.b64encode(tiny_png).decode("ascii"),
        },
    )
    assert scan_res["ok"] is True
    assert scan_res["receiptToken"].startswith("RCPT_")

    saved_med = svc.save_entry(
        "deborah",
        {
            "txnDate": "2026-10-25",
            "mode": "Expense",
            "streamId": "FAMILY",
            "member": "Maya",
            "fromAccount": "SIMPLII_VISA",
            "categoryCode": "EXP_DENTAL",
            "payee": "Thornhill Dental",
            "amount": 245.00,
            "taxAmount": 0.00,
            "receiptToken": scan_res["receiptToken"],
        },
    )
    assert saved_med["ok"] is True
    assert saved_med["entry"]["hasReceipt"] is True
    assert "Medical_Dental_Pharmacy" in saved_med["entry"]["receiptRelativePath"]

    # 3. Universal Voice Command parser (Expense, CRA-Safe Docket, Timer, Report)
    v_exp = svc.parse_voice_command(
        "deborah",
        "Costco 184.50 with 6.50 HST on Triangle Mastercard yesterday",
    )
    assert v_exp["ok"] is True
    assert v_exp["intent"] == "EXPENSE"
    assert v_exp["prefill"]["payee"] == "Costco Wholesale"
    assert v_exp["prefill"]["amount"] == 184.50
    assert v_exp["prefill"]["taxAmount"] == 6.50
    assert v_exp["prefill"]["hstMode"] == "custom"
    assert v_exp["prefill"]["fromAccount"] == "TRIANGLE_MASTERCARD"

    v_doc = svc.parse_voice_command(
        "cory",
        "Docket 24 minutes called James Hutchinson and reviewed and revised partnership agreement",
    )
    assert v_doc["ok"] is True
    assert v_doc["intent"] == "DOCKET"
    assert v_doc["hours"] == 0.4
    assert "telephone call with James" in v_doc["description"]
    assert "Hutchinson" not in v_doc["description"]
    assert "; review and revise partnership agreement" in v_doc["description"]

    v_tmr = svc.parse_voice_command("cory", "Start call timer")
    assert v_tmr["ok"] is True
    assert v_tmr["intent"] == "TIMER"
    assert v_tmr["timerAction"] == "start"

    # 4. Graphical Budget & Cash-Flow Charts in build_report
    rep = svc.build_report("cory", period="all", stream_id="ALL")
    assert rep["ok"] is True
    assert "charts" in rep
    assert len(rep["charts"]["expensePieByCategory"]) >= 1
    assert len(rep["charts"]["cashFlowBarByStream"]) >= 1

    # 5. Live Tax, HST & Shareholder Loan (GIFI 2781) Snapshot
    tax_snap = svc.get_tax_and_shl_snapshot("cory")
    assert tax_snap["ok"] is True
    assert tax_snap["shareholderLoan"]["gifiCode"] == "2781"
    assert tax_snap["shareholderLoan"]["closingBalance"] >= 794.45
    assert "SOLE_PROP" in tax_snap["hst"]
    assert "PC" in tax_snap["hst"]


