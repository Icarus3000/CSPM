"""
CRUD facade delegates for AppController.

Extracted from app_controller.py to reduce monolith size.
Each method wraps a repo call with error handling, returning safe defaults on failure.
"""
import logging
from typing import Any, Callable, Dict, Optional


class CrudFacade:
    """Thin delegate that forwards CRUD calls to the Excel repo.

    Parameters:
        repo: LazyRepoFacade (or compatible) with the data layer methods.
        report_failure: callable(user_message, *, context, exc, emit_signal)
        is_booted: callable() -> bool to check if the backend has finished booting.
    """

    def __init__(
        self,
        repo,
        report_failure: Callable[..., None],
        is_booted: Callable[[], bool],
    ) -> None:
        self._repo = repo
        self._report_failure = report_failure
        self._is_booted = is_booted

    # ── Clients ────────────────────────────────────────────────────────────────

    def list_client_names(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_client_names()
        except Exception as exc:
            self._report_failure("Could not list clients", context="repo.client.list_names", exc=exc)
            return []

    def list_active_client_names(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_active_client_names()
        except Exception as exc:
            self._report_failure("Could not list active clients", context="repo.client.list_active_names", exc=exc)
            return []

    def list_client_directory(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_client_directory()
        except Exception as exc:
            self._report_failure("Could not build client directory", context="repo.client.list_directory", exc=exc)
            return []

    def get_client_profile(self, client_key: str) -> dict:
        if not self._is_booted():
            return {"ok": False, "message": "Backend is still loading.", "client": {}}
        try:
            return dict(self._repo.get_client_profile(str(client_key or "")))
        except Exception as exc:
            self._report_failure("Could not load client profile", context="repo.client.get_profile", exc=exc)
            return {"ok": False, "message": str(exc), "client": {}}

    # ── Global Search ──────────────────────────────────────────────────────────

    def get_receivable(self, invoice_num: str) -> dict:
        try:
            return self._repo.get_receivable(invoice_num)
        except Exception as e:
            return _error(e, f"Failed to get receivable {invoice_num}.")

    def update_receivable(self, invoice_num: str, changes: dict) -> dict:
        try:
            payload = self._repo.update_receivable(invoice_num, changes)
            if payload.get("ok"):
                self.sync_search_index()
            return payload
        except Exception as e:
            return _error(e, f"Failed to update receivable {invoice_num}.")

    def search_global_entities(self, query: str, mode: str) -> dict:
        not_booted_result = {
            "ok": False,
            "query": str(query or ""),
            "mode": str(mode or "any"),
            "results": [],
            "facets": {},
            "total": 0,
            "returnedCount": 0,
        }
        if not self._is_booted():
            not_booted_result["message"] = "Backend is still loading."
            return not_booted_result
        try:
            payload = self._repo.search_global_entities(
                query=str(query or ""),
                mode=str(mode or "any"),
                limit=350,
            )
            if isinstance(payload, dict):
                return payload
            return not_booted_result
        except Exception as exc:
            self._report_failure("Global search failed", context="repo.search.global", exc=exc)
            not_booted_result["message"] = str(exc)
            return not_booted_result

    # ── Deadlines ──────────────────────────────────────────────────────────────

    def list_deadlines(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_deadline_entries()
        except Exception as exc:
            self._report_failure("Could not list deadlines", context="repo.deadline.list", exc=exc)
            return []

    def create_deadline(self, payload: dict) -> dict:
        if not self._is_booted():
            return {"ok": False, "message": "Backend is still loading."}
        try:
            return self._repo.create_deadline_entry(dict(payload))
        except Exception as exc:
            self._report_failure("Failed to create deadline", context="repo.deadline.create", exc=exc)
            return {"ok": False, "message": str(exc)}

    def update_deadline(self, entry_id: str, changes: dict) -> dict:
        if not self._is_booted():
            return {"ok": False, "message": "Backend is still loading."}
        try:
            updated = self._repo.update_deadline_entry(str(entry_id), dict(changes))
            if updated is None:
                return {"ok": False, "message": "Deadline not found"}
            return updated
        except Exception as exc:
            self._report_failure("Failed to update deadline", context="repo.deadline.update", exc=exc)
            return {"ok": False, "message": str(exc)}

    def delete_deadline(self, entry_id: str) -> bool:
        if not self._is_booted():
            return False
        try:
            return self._repo.delete_deadline_entry(str(entry_id))
        except Exception as exc:
            self._report_failure("Failed to delete deadline", context="repo.deadline.delete", exc=exc)
            return False

    # ── Matters ────────────────────────────────────────────────────────────────

    def list_matter_names(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_matter_names()
        except Exception as exc:
            self._report_failure("Could not list matters", context="repo.matter.list_names", exc=exc)
            return []

    def list_matter_directory(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_matter_directory()
        except Exception as exc:
            self._report_failure("Could not build matter directory", context="repo.matter.list_directory", exc=exc)
            return []

    def get_matter_profile(self, matter_key: str) -> dict:
        if not self._is_booted():
            return {"ok": False, "message": "Backend is still loading.", "matter": {}}
        try:
            return dict(self._repo.get_matter_profile(str(matter_key or "")))
        except Exception as exc:
            self._report_failure("Could not load matter profile", context="repo.matter.get_profile", exc=exc)
            return {"ok": False, "message": str(exc), "matter": {}}

    def preview_matter_number(
        self, client_name: str, matter_type: str, date_opened: str, existing_matter_id: str
    ) -> str:
        if not self._is_booted():
            return ""
        try:
            return str(
                self._repo.preview_matter_number(
                    client_name=str(client_name or ""),
                    matter_type=str(matter_type or ""),
                    date_opened=str(date_opened or ""),
                    existing_matter_id=str(existing_matter_id or ""),
                )
                or ""
            )
        except Exception as exc:
            self._report_failure(
                "Could not preview matter number",
                context="repo.matter.preview_number",
                exc=exc,
                emit_signal=False,
            )
            return ""

    def list_parent_names(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_parent_names()
        except Exception as exc:
            self._report_failure("Could not list parents", context="repo.parent.list_names", exc=exc)
            return []

    def list_active_matter_names(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_active_matter_names()
        except Exception as exc:
            self._report_failure("Could not list active matters", context="repo.matter.list_active_names", exc=exc)
            return []

    def list_active_matter_directory(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_active_matter_directory()
        except Exception as exc:
            self._report_failure("Could not build active matter directory", context="repo.matter.list_active_directory", exc=exc)
            return []

    def list_trademark_directory(self, query: str) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_trademark_directory(str(query or ""))
        except Exception as exc:
            self._report_failure("Could not build trademark directory", context="repo.trademark.list_directory", exc=exc)
            return []

    # ── Transactions ───────────────────────────────────────────────────────────

    def list_transaction_accounts(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transaction_accounts(include_inactive=False)
        except Exception as exc:
            self._report_failure("Could not list transaction accounts", context="repo.txn.list_accounts", exc=exc)
            return []

    def list_transaction_accounts_all(self, include_inactive: bool) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transaction_accounts(include_inactive=bool(include_inactive))
        except Exception as exc:
            self._report_failure("Could not list transaction accounts", context="repo.txn.list_accounts_all", exc=exc)
            return []

    def list_transaction_categories(self, txn_type: str, txn_class: str, include_inactive: bool) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transaction_categories(
                txn_type=str(txn_type or ""),
                txn_class=str(txn_class or ""),
                include_inactive=bool(include_inactive),
            )
        except Exception as exc:
            self._report_failure("Could not list transaction categories", context="repo.txn.list_categories", exc=exc)
            return []

    def list_transaction_business_units(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transaction_business_units(include_inactive=False)
        except Exception as exc:
            self._report_failure("Could not list transaction business units", context="repo.txn.list_business_units", exc=exc)
            return []

    def list_transaction_business_units_all(self, include_inactive: bool) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transaction_business_units(include_inactive=bool(include_inactive))
        except Exception as exc:
            self._report_failure("Could not list transaction business units", context="repo.txn.list_business_units_all", exc=exc)
            return []

    def list_transaction_payees(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transaction_payees(include_inactive=False)
        except Exception as exc:
            self._report_failure("Could not list transaction payees", context="repo.txn.list_payees", exc=exc)
            return []

    def list_transaction_payees_all(self, include_inactive: bool) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transaction_payees(include_inactive=bool(include_inactive))
        except Exception as exc:
            self._report_failure("Could not list transaction payees", context="repo.txn.list_payees_all", exc=exc)
            return []

    def list_transactions(self, filters: dict) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transactions(dict(filters or {}))
        except Exception as exc:
            self._report_failure("Could not list transactions", context="repo.txn.list_filtered", exc=exc)
            return []

    def list_all_transactions(self) -> list:
        if not self._is_booted():
            return []
        try:
            return self._repo.list_transactions({})
        except Exception as exc:
            self._report_failure("Could not list transactions", context="repo.txn.list_all", exc=exc)
            return []

    # ── Operations ─────────────────────────────────────────────────────────────

    def run_conflict_check(self, payload: dict) -> dict:
        """Run conflict check. Returns result dict with toast/error message strings.

        The caller is responsible for emitting toast/error signals based on the
        returned dict's "ok", "message", "totalMatches" and "riskLevel" fields.
        """
        try:
            return dict(self._repo.run_conflict_check(dict(payload or {})) or {})
        except Exception as exc:
            self._report_failure("Could not run conflict check", context="repo.conflict_check.run", exc=exc)
            return {
                "ok": False,
                "message": str(exc),
                "riskLevel": "none",
                "termsUsed": [],
                "matches": [],
                "totalMatches": 0,
                "summary": {"client": 0, "matter": 0, "parent": 0},
                "checkedAtUtc": "",
            }

    def reassign_matter(self, payload: dict) -> dict:
        """Reassign a matter. Returns result dict.

        The caller is responsible for emitting toast/error/clientDataChanged signals.
        """
        try:
            return dict(self._repo.reassign_matter(dict(payload or {})) or {})
        except Exception as exc:
            self._report_failure("Could not reassign matter", context="repo.matter.reassign", exc=exc)
            return {
                "ok": False,
                "changed": False,
                "message": str(exc),
            }

    def merge_duplicate_entities(self, payload: dict) -> dict:
        """Merge duplicate entities. Returns result dict.

        The caller is responsible for emitting toast/error/clientDataChanged signals.
        """
        try:
            return dict(self._repo.merge_duplicate_entities(dict(payload or {})) or {})
        except Exception as exc:
            self._report_failure("Could not merge duplicate entities", context="repo.entity.merge_duplicate", exc=exc)
            return {
                "ok": False,
                "changed": False,
                "message": str(exc),
            }
