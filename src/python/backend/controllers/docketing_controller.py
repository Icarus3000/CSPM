import logging
from functools import partial

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from backend.workers import Worker

class DocketingController(QObject):
    transactionDataChanged = Signal()
    transactionLookupDataChanged = Signal()
    transactionSaveFinished = Signal(dict)
    paymentSaveFinished = Signal(dict)
    timeSaveFinished = Signal(dict)
    trademarkSaveFinished = Signal(dict)
    docketActivityReportFinished = Signal(dict)
    clientLedgerReportFinished = Signal(dict)
    timeDocketAggregateFinished = Signal(dict)
    bulkDocketMovePreviewFinished = Signal(dict)
    bulkDocketMoveFinished = Signal(dict)
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
