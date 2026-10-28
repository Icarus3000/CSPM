import logging
from functools import partial

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from backend.workers import Worker

class DocketingController(QObject):
    transactionDataChanged = Signal()
    transactionLookupDataChanged = Signal()
    transactionSaveFinished = Signal(dict)
    paymentSaveFinished = Signal(dict)
    billingClientReceiptSaveFinished = Signal(dict)
    timeSaveFinished = Signal(dict)
    trademarkSaveFinished = Signal(dict)
    docketActivityReportFinished = Signal(dict)
    clientLedgerReportFinished = Signal(dict)
    timeDocketAggregateFinished = Signal(dict)
    bulkDocketMovePreviewFinished = Signal(dict)
    bulkDocketMoveFinished = Signal(dict)
    xeroReconciliationFinished = Signal(dict)
    invoiceLogEntryUpdated = Signal(dict)
    error = Signal(str)
    toast = Signal(str)

    def __init__(self, excel_repo):
        super().__init__()
        self._excel_repo = excel_repo
        self._threadpool = QThreadPool.globalInstance()
        self._active_workers = set()

    def _start_worker(self, worker):
        self._active_workers.add(worker)
        self._threadpool.start(worker)

    def _release_worker(self, worker):
        self._active_workers.discard(worker)

    @Slot(result=list)
    def listDeadlines(self):
        try:
            return self._excel_repo.list_deadline_entries()
        except Exception as exc:
            self.error.emit(f"Could not list deadlines: {exc}")
            return []

    @Slot("QVariantMap", result=dict)
    def createDeadline(self, payload):
        try:
            return self._excel_repo.create_deadline_entry(dict(payload))
        except Exception as exc:
            self.error.emit(f"Failed to create deadline: {exc}")
            return {"ok": False, "message": str(exc)}

    @Slot(str, "QVariantMap", result=dict)
    def updateDeadline(self, entry_id, changes):
        try:
            updated = self._excel_repo.update_deadline_entry(str(entry_id), dict(changes))
            if updated is None:
                return {"ok": False, "message": "Deadline not found"}
            return updated
        except Exception as exc:
            self.error.emit(f"Failed to update deadline: {exc}")
            return {"ok": False, "message": str(exc)}

    @Slot(str, result=bool)
    def deleteDeadline(self, entry_id):
        try:
            return self._excel_repo.delete_deadline_entry(str(entry_id))
        except Exception as exc:
            self.error.emit(f"Failed to delete deadline: {exc}")
            return False

    @Slot("QVariantMap")
    def saveTransaction(self, payload):
        worker = Worker(
            self._excel_repo.save_transaction,
            dict(payload or {}),
            name="saveTransaction",
        )
        worker.signals.result.connect(partial(self._on_transaction_saved, worker))
        worker.signals.error.connect(partial(self._on_transaction_error, worker))
        self._start_worker(worker)

    def _on_transaction_saved(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("ok"):
                self.toast.emit(f"Transaction saved: {res_dict.get('transactionId', '')}")
                self.transactionDataChanged.emit()
                self.transactionSaveFinished.emit(res_dict)
            else:
                self.transactionSaveFinished.emit(res_dict)
                self.error.emit(res_dict.get("message", "Transaction verification failed."))
        finally:
            self._release_worker(worker)

    def _on_transaction_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not save transaction: {value}")
            self.transactionSaveFinished.emit({
                "ok": False,
                "message": str(value)
            })
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def postPayment(self, payload):
        worker = Worker(
            self._excel_repo.post_invoice_payment,
            dict(payload or {}),
            name="postPayment",
        )
        worker.signals.result.connect(partial(self._on_payment_saved, worker))
        worker.signals.error.connect(partial(self._on_payment_error, worker))
        self._start_worker(worker)

    @Slot(str, result=dict)
    def getPaymentEntry(self, payment_id):
        try:
            return self._excel_repo.get_invoice_payment_entry(str(payment_id or ""))
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @Slot("QVariantMap")
    def updatePayment(self, payload):
        worker = Worker(
            self._excel_repo.update_invoice_payment,
            dict(payload or {}),
            name="updatePayment",
        )
        worker.signals.result.connect(partial(self._on_payment_saved, worker))
        worker.signals.error.connect(partial(self._on_payment_error, worker))
        self._start_worker(worker)

    @Slot("QVariantMap")
    def postBillingClientReceipt(self, payload):
        worker = Worker(
            self._excel_repo.post_billing_client_receipt,
            dict(payload or {}),
            name="postBillingClientReceipt",
        )
        worker.signals.result.connect(partial(self._on_billing_client_receipt_saved, worker))
        worker.signals.error.connect(partial(self._on_billing_client_receipt_error, worker))
        self._start_worker(worker)

    def _on_billing_client_receipt_saved(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("ok"):
                self.toast.emit(res_dict.get("message", "Billing-client receipt posted."))
                self.transactionDataChanged.emit()
            else:
                self.error.emit(res_dict.get("message", "Billing-client receipt posting failed."))
            self.billingClientReceiptSaveFinished.emit(res_dict)
        finally:
            self._release_worker(worker)

    def _on_billing_client_receipt_error(self, worker, err_tuple):
        try:
            _, value, _ = err_tuple
            self.error.emit(f"Could not post billing-client receipt: {value}")
            payload = {
                "ok": False,
                "message": str(value),
            }
            error_code = str(getattr(value, "error_code", "") or "").strip()
            if error_code:
                payload["errorCode"] = error_code
            conflicts = getattr(value, "conflicts", None)
            if isinstance(conflicts, list):
                payload["billingClientConflicts"] = [dict(item or {}) for item in conflicts]
            expected = str(getattr(value, "expected_billing_client", "") or "").strip()
            if expected:
                payload["expectedBillingClient"] = expected
            self.billingClientReceiptSaveFinished.emit(payload)
        finally:
            self._release_worker(worker)

    def _on_payment_saved(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("ok"):
                self.toast.emit(res_dict.get("message", "Payment posted."))
                self.transactionDataChanged.emit()
                self.paymentSaveFinished.emit(res_dict)
            else:
                self.paymentSaveFinished.emit(res_dict)
                self.error.emit(res_dict.get("message", "Payment posting failed."))
        finally:
            self._release_worker(worker)

    def _on_payment_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not post payment: {value}")
            self.paymentSaveFinished.emit({
                "ok": False,
                "message": str(value)
            })
        finally:
            self._release_worker(worker)

    unlinkBilledDocketFinished = Signal(dict)

    @Slot(str)
    def unlinkBilledDocket(self, entry_id):
        worker = Worker(
            self._excel_repo.unlink_billed_docket,
            str(entry_id),
            name="unlinkBilledDocket",
        )
        worker.signals.result.connect(partial(self._on_unlink_billed_docket_finished, worker))
        worker.signals.error.connect(partial(self._on_unlink_billed_docket_error, worker))
        self._start_worker(worker)

    def _on_unlink_billed_docket_finished(self, worker, result):
        try:
            res = dict(result or {})
            if res.get("ok"):
                self.toast.emit(res.get("message", "Invoice unlinked and docket unlocked."))
            else:
                self.error.emit(res.get("message", "Failed to unlink invoice."))
            self.unlinkBilledDocketFinished.emit(res)
        finally:
            self._release_worker(worker)

    def _on_unlink_billed_docket_error(self, worker, err_tuple):
        try:
            _, value, _ = err_tuple
            self.error.emit(f"Could not unlink invoice: {value}")
            self.unlinkBilledDocketFinished.emit({"ok": False, "message": str(value)})
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def saveTimeDocketEntry(self, payload):
        worker = Worker(
            self._excel_repo.add_time_entry,
            dict(payload or {}),
            name="saveTimeDocketEntry",
        )
        worker.signals.result.connect(partial(self._on_time_entry_saved, worker))
        worker.signals.error.connect(partial(self._on_time_entry_error, worker))
        self._start_worker(worker)

    def _on_time_entry_saved(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("ok"):
                self.toast.emit(f"Time entry saved: {res_dict.get('entryId', '')}")
                self.timeSaveFinished.emit(res_dict)
            else:
                self.timeSaveFinished.emit(res_dict)
                self.error.emit(res_dict.get("message", "Time entry verification failed."))
        finally:
            self._release_worker(worker)

    def _on_time_entry_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not save time entry: {value}")
            self.timeSaveFinished.emit({
                "ok": False,
                "message": str(value)
            })
        finally:
            self._release_worker(worker)

    @Slot(str, "QVariantMap")
    def updateTimeDocketEntry(self, entry_id, changes):
        worker = Worker(
            self._excel_repo.update_time_entry,
            str(entry_id),
            dict(changes or {}),
            name="updateTimeDocketEntry",
        )
        worker.signals.result.connect(partial(self._on_time_entry_updated, worker))
        worker.signals.error.connect(partial(self._on_time_entry_error, worker))
        self._start_worker(worker)

    def _on_time_entry_updated(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("ok"):
                self.toast.emit("Time entry updated.")
                self.timeSaveFinished.emit(res_dict)
            else:
                self.timeSaveFinished.emit(res_dict)
                self.error.emit(res_dict.get("message", "Time entry update failed."))
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def saveTrademarkFiling(self, payload):
        worker = Worker(
            self._excel_repo.save_trademark_filing,
            dict(payload or {}),
            name="saveTrademarkFiling",
        )
        worker.signals.result.connect(partial(self._on_trademark_saved, worker))
        worker.signals.error.connect(partial(self._on_trademark_error, worker))
        self._start_worker(worker)

    def _on_trademark_saved(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("ok"):
                self.toast.emit(f"Trademark filing saved: {res_dict.get('trademarkId', '')}")
                self.trademarkSaveFinished.emit(res_dict)
            else:
                self.trademarkSaveFinished.emit(res_dict)
                self.error.emit(res_dict.get("message", "Trademark verification failed."))
        finally:
            self._release_worker(worker)

    def _on_trademark_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not save trademark: {value}")
            self.trademarkSaveFinished.emit({
                "ok": False,
                "message": str(value)
            })
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def loadDocketActivityReport(self, payload):
        payload_dict = dict(payload or {})
        request_token = str(payload_dict.pop("_requestToken", "") or "")
        worker = Worker(
            self._excel_repo.get_docket_activity_report,
            payload_dict,
            name="loadDocketActivityReport",
        )
        worker.signals.result.connect(partial(self._on_docket_report_loaded, worker, request_token))
        worker.signals.error.connect(partial(self._on_docket_report_error, worker, request_token))
        self._start_worker(worker)

    def _on_docket_report_loaded(self, worker, request_token, result):
        try:
            res_dict = dict(result or {})
            if request_token:
                res_dict["_requestToken"] = request_token
            self.docketActivityReportFinished.emit(res_dict)
        finally:
            self._release_worker(worker)

    def _on_docket_report_error(self, worker, request_token, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not load docket report: {value}")
            result = {
                "ok": False,
                "message": str(value),
            }
            if request_token:
                result["_requestToken"] = request_token
            self.docketActivityReportFinished.emit(result)
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def loadClientLedgerReport(self, payload):
        payload_dict = dict(payload or {})
        request_token = str(payload_dict.pop("_requestToken", "") or "")
        worker = Worker(
            self._excel_repo.get_client_ledger_report,
            payload_dict,
            name="loadClientLedgerReport",
        )
        worker.signals.result.connect(partial(self._on_client_ledger_loaded, worker, request_token))
        worker.signals.error.connect(partial(self._on_client_ledger_error, worker, request_token))
        self._start_worker(worker)

    def _on_client_ledger_loaded(self, worker, request_token, result):
        try:
            res_dict = dict(result or {})
            if request_token:
                res_dict["_requestToken"] = request_token
            
            entries = res_dict.get("entries", [])
            if isinstance(entries, list) and len(entries) > 500:
                import json
                from datetime import datetime, date
                from decimal import Decimal

                def json_serial(obj):
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    if isinstance(obj, Decimal):
                        return float(obj)
                    return str(obj)

                self.clientLedgerReportFinished.emit({
                    "_requestToken": request_token,
                    "_jsonPayload": json.dumps(res_dict, default=json_serial)
                })
            else:
                self.clientLedgerReportFinished.emit(res_dict)
        finally:
            self._release_worker(worker)

    def _on_client_ledger_error(self, worker, request_token, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not load client ledger: {value}")
            result = {
                "ok": False,
                "message": str(value),
            }
            if request_token:
                result["_requestToken"] = request_token
            self.clientLedgerReportFinished.emit(result)
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def loadTimeDocketAggregate(self, payload):

        worker = Worker(
            self._excel_repo.get_time_docket_aggregate,
            dict(payload or {}),
            name="loadTimeDocketAggregate",
        )
        worker.signals.result.connect(partial(self._on_time_aggregate_loaded, worker))
        worker.signals.error.connect(partial(self._on_time_aggregate_error, worker))
        self._start_worker(worker)

    def _on_time_aggregate_loaded(self, worker, result):
        try:
            res_dict = dict(result or {})
            self.timeDocketAggregateFinished.emit(res_dict)
        finally:
            self._release_worker(worker)

    def _on_time_aggregate_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not load time aggregate: {value}")
            self.timeDocketAggregateFinished.emit({
                "ok": False,
                "message": str(value)
            })
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def previewBulkDocketMove(self, payload):
        worker = Worker(
            self._excel_repo.preview_bulk_docket_move,
            dict(payload or {}),
            name="previewBulkDocketMove",
        )
        worker.signals.result.connect(partial(self._on_bulk_docket_move_previewed, worker))
        worker.signals.error.connect(partial(self._on_bulk_docket_move_preview_error, worker))
        self._start_worker(worker)

    def _on_bulk_docket_move_previewed(self, worker, result):
        try:
            self.bulkDocketMovePreviewFinished.emit(dict(result or {}))
        finally:
            self._release_worker(worker)

    def _on_bulk_docket_move_preview_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            message = str(value)
            self.error.emit(f"Could not find movable dockets: {message}")
            self.bulkDocketMovePreviewFinished.emit({"ok": False, "message": message})
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def moveDocketsToMatter(self, payload):
        worker = Worker(
            self._excel_repo.move_dockets_to_matter,
            dict(payload or {}),
            name="moveDocketsToMatter",
        )
        worker.signals.result.connect(partial(self._on_dockets_moved, worker))
        worker.signals.error.connect(partial(self._on_dockets_move_error, worker))
        self._start_worker(worker)

    def _on_dockets_moved(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("ok"):
                count = int(res_dict.get("movedCount") or 0)
                self.toast.emit(f"Moved {count} docket{'s' if count != 1 else ''} to the destination matter.")
            else:
                self.error.emit(res_dict.get("message", "Docket move verification failed."))
            self.bulkDocketMoveFinished.emit(res_dict)
        finally:
            self._release_worker(worker)

    def _on_dockets_move_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            message = str(value)
            self.error.emit(f"Could not move dockets: {message}")
            self.bulkDocketMoveFinished.emit({"ok": False, "message": message})
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap", result=dict)
    def getTimeDocketAggregateSync(self, payload):
        try:
            result = self._excel_repo.get_time_docket_aggregate(dict(payload or {}))
            return dict(result or {})
        except Exception as exc:
            self.error.emit(f"Could not load aggregate synchronously: {exc}")
            return {"ok": False, "exists": False, "message": str(exc)}

    @Slot("QVariantMap", result=str)
    def getDocketEntriesSync(self, payload):
        try:
            import json
            res = self._excel_repo.get_docket_activity_report(dict(payload or {}))
            return json.dumps(res.get("rows", []))
        except Exception as exc:
            self.error.emit(f"Could not load entries synchronously: {exc}")
            return "[]"

    @Slot(result=bool)
    def notifyTransactionLookupDataChanged(self):
        try:
            self.transactionLookupDataChanged.emit()
            return True
        except Exception:
            return False

    @Slot(result=list)
    def listTransactionAccounts(self): return self._excel_repo.list_transaction_accounts(include_inactive=False)

    @Slot(bool, result=list)
    def listTransactionAccountsAll(self, include_inactive): return self._excel_repo.list_transaction_accounts(include_inactive=bool(include_inactive))

    @Slot(str, str, bool, result=list)
    def listTransactionCategories(self, txn_type, txn_class, include_inactive): return self._excel_repo.list_transaction_categories(txn_type=str(txn_type or ""), txn_class=str(txn_class or ""), include_inactive=bool(include_inactive))

    @Slot(result=list)
    def listTransactionBusinessUnits(self): return self._excel_repo.list_transaction_business_units(include_inactive=False)

    @Slot(bool, result=list)
    def listTransactionBusinessUnitsAll(self, include_inactive): return self._excel_repo.list_transaction_business_units(include_inactive=bool(include_inactive))

    @Slot(result=list)
    def listTransactionPayees(self): return self._excel_repo.list_transaction_payees(include_inactive=False)

    @Slot(bool, result=list)
    def listTransactionPayeesAll(self, include_inactive): return self._excel_repo.list_transaction_payees(include_inactive=bool(include_inactive))

    @Slot("QVariantMap", result=list)
    def listTransactions(self, filters): return self._excel_repo.list_transactions(dict(filters or {}))

    @Slot(result=list)
    def listAllTransactions(self): return self._excel_repo.list_transactions({})

    @Slot(str, result=list)
    def listTrademarkDirectory(self, query): return self._excel_repo.list_trademark_directory(str(query or ""))

    @Slot("QVariantMap")
    def updateInvoiceLogEntry(self, payload):
        """Update an invoice log entry (fees, tax, etc.) and emit the result."""
        payload_dict = dict(payload or {})
        worker = Worker(
            self._excel_repo.save_invoice_log,
            payload_dict,
            name="updateInvoiceLogEntry",
        )
        worker.signals.result.connect(partial(self._on_invoice_log_updated, worker))
        worker.signals.error.connect(partial(self._on_invoice_log_update_error, worker))
        self._start_worker(worker)

    def _on_invoice_log_updated(self, worker, result):
        try:
            res_dict = dict(result or {})
            self.invoiceLogEntryUpdated.emit(res_dict)
        finally:
            self._release_worker(worker)

    def _on_invoice_log_update_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            self.error.emit(f"Could not update invoice: {value}")
            self.invoiceLogEntryUpdated.emit({"ok": False, "message": str(value)})
        finally:
            self._release_worker(worker)

    @Slot("QVariantMap")
    def reverseAndReissueInvoice(self, payload):
        """Perform the strict audit reverse and reissue flow."""
        payload_dict = dict(payload or {})
        worker = Worker(
            self._excel_repo.reverse_and_reissue_invoice,
            payload_dict,
            name="reverseAndReissueInvoice",
        )
        worker.signals.result.connect(partial(self._on_invoice_log_updated, worker))
        worker.signals.error.connect(partial(self._on_invoice_log_update_error, worker))
        self._start_worker(worker)

    @property
    def sqlite_repo(self):
        if hasattr(self._excel_repo, "_get_sqlite_repo"):
            return self._excel_repo._get_sqlite_repo()
        return None

    @Slot("QVariantMap", result=dict)
    def upsertLiveDocketHeartbeat(self, payload):
        """Persist a real-time timer or draft docket heartbeat to SQLite cspm.db (WAL mode)."""
        try:
            if hasattr(self._excel_repo, "upsert_sqlite_docket_heartbeat"):
                return dict(self._excel_repo.upsert_sqlite_docket_heartbeat(dict(payload or {})) or {})
            sq = self.sqlite_repo
            if sq is not None:
                return dict(sq.upsert_live_docket_heartbeat(dict(payload or {})) or {})
            return {"ok": False, "message": "SQLite repository unavailable"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @Slot(result=dict)
    def reconcileUnsyncedDocketsOnStartup(self):
        """Reconcile PENDING_SYNC and PENDING_CRASH_RECOVERY SQLite dockets on startup."""
        try:
            if hasattr(self._excel_repo, "reconcile_unsynced_dockets_on_startup"):
                return dict(self._excel_repo.reconcile_unsynced_dockets_on_startup() or {})
            return {"ok": True, "syncedEntries": [], "conflicts": [], "crashRecoveryDockets": []}
        except Exception as exc:
            return {"ok": False, "message": str(exc), "syncedEntries": [], "conflicts": [], "crashRecoveryDockets": []}

    @Slot(str, str, str, result=dict)
    def resolveCrashRecoveryDocket(self, entry_id, action, time_option="heartbeat"):
        """Resolve a crash-recovered docket ('save_and_sync', 'sync_and_keep_paused', or 'discard')."""
        try:
            if hasattr(self._excel_repo, "resolve_crash_recovery_docket"):
                return dict(
                    self._excel_repo.resolve_crash_recovery_docket(
                        str(entry_id or ""),
                        str(action or ""),
                        time_option=str(time_option or "heartbeat"),
                    )
                    or {}
                )
            return {"ok": False, "message": "Crash recovery resolution unavailable"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @Slot(str, result="QVariantMap")
    @Slot(str, bool, result="QVariantMap")
    def cancelOrDeleteDocketTab(self, tab_or_entry_id: str, remove_from_legacy_dockets: bool = True) -> dict:
        """Cancel a running/paused timer or delete a docket entry from active tabs, SQLite, CSPM.xlsm, timer_recovery.json, and Dockets.xlsm."""
        try:
            tray = getattr(self, "_tray_controller", None)
            if tray is not None and hasattr(tray, "cancelOrDeleteDocketTab"):
                res = dict(tray.cancelOrDeleteDocketTab(str(tab_or_entry_id or ""), bool(remove_from_legacy_dockets)) or {})
                self.transactionDataChanged.emit()
                return res
            if hasattr(self._excel_repo, "cancel_or_delete_docket_entry"):
                res = dict(
                    self._excel_repo.cancel_or_delete_docket_entry(
                        str(tab_or_entry_id or ""),
                        remove_from_legacy_dockets=bool(remove_from_legacy_dockets),
                    )
                    or {}
                )
                self.transactionDataChanged.emit()
                return res
            if hasattr(self._excel_repo, "delete_time_entry"):
                res = dict(self._excel_repo.delete_time_entry(str(tab_or_entry_id or "")) or {})
                self.transactionDataChanged.emit()
                return res
            return {"ok": False, "message": "Docket delete unavailable"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @Slot("QVariantMap")
    def runXeroReconciliation(self, payload):
        """Run 4-way LIH Xero Projects reconciliation (and optional sync/report export) in a background worker."""
        req = dict(payload or {})
        worker = Worker(
            self._execute_xero_reconciliation,
            req,
            name="runXeroReconciliation",
        )
        worker.signals.result.connect(partial(self._on_xero_reconciliation_finished, worker))
        worker.signals.error.connect(partial(self._on_xero_reconciliation_error, worker))
        self._start_worker(worker)

    def _execute_xero_reconciliation(self, req: dict) -> dict:
        import datetime as _dt
        import pathlib as _pl
        from services.xero_sync_service import get_reconciliation_data, resolve_xero_runtime_paths

        today = _dt.date.today()
        start_date = str(req.get("startDate") or today.strftime("%Y-%m-01")).strip()
        end_date = str(req.get("endDate") or today.strftime("%Y-%m-%d")).strip()
        period_label = str(req.get("periodLabel") or f"{start_date} to {end_date}").strip()
        do_sync = bool(req.get("doSync", False))
        update_mismatches = bool(req.get("updateMismatches", False))
        export_report = bool(req.get("exportReport", False))
        app_paths = getattr(self._excel_repo, "paths", None)
        report_out = None
        if export_report:
            rt_paths = resolve_xero_runtime_paths(app_paths)
            shared_dir = _pl.Path(rt_paths["shared_dir"])
            report_out = shared_dir / f"LIH_Xero_Reconciliation_{start_date}_to_{end_date}.md"
        return get_reconciliation_data(
            start_date=start_date,
            end_date=end_date,
            period_label=period_label,
            do_sync=do_sync,
            update_mismatches=update_mismatches,
            report_out=report_out,
            app_paths=app_paths,
        )

    def _on_xero_reconciliation_finished(self, worker, result):
        try:
            res_dict = dict(result or {})
            if res_dict.get("saved_report_path"):
                self.toast.emit(f"Exported Xero reconciliation report: {res_dict['saved_report_path']}")
            elif res_dict.get("synced_count") or res_dict.get("updated_count"):
                self.toast.emit(
                    f"Xero Sync Complete: {res_dict.get('synced_count', 0)} created, {res_dict.get('updated_count', 0)} updated."
                )
            self.xeroReconciliationFinished.emit(res_dict)
        finally:
            self._release_worker(worker)

    def _on_xero_reconciliation_error(self, worker, err_tuple):
        try:
            exctype, value, tb_str = err_tuple
            msg = str(value)
            self.error.emit(f"Xero reconciliation failed: {msg}")
            self.xeroReconciliationFinished.emit({"ok": False, "message": msg})
        finally:
            self._release_worker(worker)

    @Slot()
    def openXeroLoginWindow(self):
        """Launch interactive Edge CDP login window if the 30-day Xero cookie ever expires."""
        def _run_login():
            import importlib.util
            import pathlib as _pl
            from services.xero_sync_service import resolve_xero_runtime_paths
            rt_paths = resolve_xero_runtime_paths(getattr(self._excel_repo, "paths", None))
            shared_state = _pl.Path(rt_paths["shared_state_dir"])
            skill_script = shared_state.parent / "skills" / "xero-sync" / "scripts" / "xero_sync.py"
            if skill_script.is_file():
                spec = importlib.util.spec_from_file_location("xero_sync_login", str(skill_script))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    mod.interactive_cdp_login(shared_state)
                    return {"ok": True}
            return {"ok": False, "message": "xero_sync.py not found"}

        worker = Worker(_run_login, name="openXeroLoginWindow")
        worker.signals.result.connect(lambda _res: self._release_worker(worker))
        worker.signals.error.connect(lambda _err: self._release_worker(worker))
        self._start_worker(worker)

    @Slot(str, result="QVariantMap")
    def resetDocketTimer(self, tab_or_entry_id: str) -> dict:
        """Stop the timer if running, reset raw_seconds to 0, clear auto-shutdown placeholder text, and keep the matter tab open."""
        try:
            tray = getattr(self, "_tray_controller", None)
            if tray is not None and hasattr(tray, "resetDocketTimer"):
                res = dict(tray.resetDocketTimer(str(tab_or_entry_id or "")) or {})
                self.transactionDataChanged.emit()
                return res
            if hasattr(self._excel_repo, "reset_docket_timer"):
                res = dict(self._excel_repo.reset_docket_timer(str(tab_or_entry_id or "")) or {})
                self.transactionDataChanged.emit()
                return res
            return {"ok": False, "message": "Docket timer reset unavailable"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}


