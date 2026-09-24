
import pytest
from backend.controllers.ap_controller import APController
from repositories.finance_repo import FinanceRepo

class DummyDB:
    TXN_CURRENCY_OPTIONS = ["CAD", "USD"]
    TXN_DEBT_DEST_ACCOUNT_KINDS = []
    
    def _pick_float(self, payload, keys):
        for k in keys:
            if k in payload: return payload[k]
        return None
        
    def _pick_text(self, payload, keys):
        for k in keys:
            if k in payload: return payload[k]
        return ""
        
    def _to_bool_int(self, val, default=0):
        if str(val).lower() in ("true", "1", "yes"): return 1
        return default
        
    def _pick_value(self, payload, keys):
        for k in keys:
            if k in payload: return payload[k]
        return None

    def _transaction_category_lookup_maps(self):
        return {"c1": {"categoryCode": "C1", "categoryName": "Cat 1"}}, {"cat 1": {"categoryCode": "C1", "categoryName": "Cat 1"}}
        
    def get_matter_profile(self, matter):
        if matter == "m_valid":
            return {"ok": True, "matter": {"clientId": "c1", "clientName": "Client 1", "parentId": "p1", "parentName": "Parent 1"}}
        return {"ok": False, "matter": {}}
        
    def _transaction_account_kind_lookup(self):
        return {}

def test_ap_validation_repair_valid():
    db = DummyDB()
    repo = FinanceRepo(db)
    payload = {
        "type": "expense",
        "amount": "100.0",
        "categoryCode": "C1",
        "categoryName": "Cat 1",
        "billClaimPct": "100",
        "matter": "m_valid",
        "client": "c1",
        "parent": "p1"
    }
    # Should not raise any ValueError about client/matter
    try:
        repo.save_txn("dummy_id", "2026-09-23", "Business", "BU", payload, "Open")
    except ValueError as e:
        assert "Select a client and matter" not in str(e)
        assert "incomplete and cannot be billed" not in str(e)

def test_ap_validation_repair_missing():
    db = DummyDB()
    repo = FinanceRepo(db)
    payload = {
        "type": "expense",
        "amount": "100.0",
        "categoryCode": "C1",
        "categoryName": "Cat 1",
        "billClaimPct": "100",
        "matter": "",
        "client": "",
        "parent": ""
    }
    with pytest.raises(ValueError, match="Select a client and matter before saving a recoverable expense"):
        repo.save_txn("dummy_id", "2026-09-23", "Business", "BU", payload, "Open")

def test_ap_validation_repair_mismatch():
    db = DummyDB()
    repo = FinanceRepo(db)
    payload = {
        "type": "expense",
        "amount": "100.0",
        "categoryCode": "C1",
        "categoryName": "Cat 1",
        "billClaimPct": "100",
        "matter": "m_valid",
        "client": "wrong_client",
        "parent": "p1"
    }
    with pytest.raises(ValueError, match="The selected matter could not be linked to its client"):
        repo.save_txn("dummy_id", "2026-09-23", "Business", "BU", payload, "Open")

