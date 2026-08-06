from __future__ import annotations

from functools import partial
import json
import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from backend.workers import Worker
from repositories.ap_workbook_repository import APWorkbookRepository
from services.ap_orchestration_service import APOrchestrationService


logger = logging.getLogger("cspm.ap.controller")


class APController(QObject):
    """QML-facing Accounts Payable controller.

    The existing ExcelRepo remains the Transactions Master and matter-linked
    Disbursements gateway. APWorkbookRepository owns APBills and APPayments.
    All operations retain the existing asynchronous Worker pattern.
    """

    apLoaded = Signal(list)
    apSaveFinished = Signal(dict)
    apPaymentFinished = Signal(dict)
    apPaymentReversed = Signal(dict)
    apBillDetailsLoaded = Signal(dict)
    apDeleteFinished = Signal(dict)
    operationFinished = Signal(dict)
    error = Signal(str)
    toast = Signal(str)

    def __init__(
        self,
        excel_repo: Any,
        ap_repository: APWorkbookRepository | None = None,
        orchestration_service: APOrchestrationService | None = None,
        worker_factory: Callable[..., Any] = Worker,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = excel_repo
        self._worker_factory = worker_factory
        self._workers: set[Any] = set()
        if orchestration_service is not None:
            self._orchestrator = orchestration_service
            self._ap_repository = orchestration_service.ap_repository
        else:
            self._ap_repository = ap_repository or APWorkbookRepository(
                self._resolve_workbook_path(excel_repo)
            )
            self._orchestrator = APOrchestrationService(
                self._ap_repository,
                excel_repo,
            )
        # Column config persistence file (data/state/ap_table_columns.json)
        try:
            wb_path = self._resolve_workbook_path(excel_repo)
            self._column_config_path = wb_path.parent / "state" / "ap_table_columns.json"
        except Exception:
            self._column_config_path = Path("data/state/ap_table_columns.json")

    # ── Column config persistence ─────────────────────────────────────
    @Slot(str)
    def saveAPColumnConfig(self, config_json: str) -> None:
        try:
            self._column_config_path.parent.mkdir(parents=True, exist_ok=True)
            self._column_config_path.write_text(config_json, encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save AP column config: %s", exc)

    @Slot(result=str)
    def loadAPColumnConfig(self) -> str:
        try:
            if self._column_config_path.is_file():
                return self._column_config_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to load AP column config: %s", exc)
        return ""

    @staticmethod
    def _resolve_workbook_path(excel_repo: Any) -> Path:
        candidates = (
            "workbook_path",
            "path",
            "file_path",
            "filepath",
            "_workbook_path",
            "_path",
            "_file_path",
        )
        for name in candidates:
            value = getattr(excel_repo, name, None)
            if value:
                path = Path(value)
                if path.is_file():
                    return path
        workbook = getattr(excel_repo, "_wb", None)
        archive = getattr(workbook, "vba_archive", None) if workbook is not None else None
        filename = getattr(archive, "filename", None)
        if filename:
            path = Path(filename)
            if path.is_file():
                return path
        raise RuntimeError(
            "APController could not determine the active workbook path. "
            "Pass ap_repository or orchestration_service explicitly."
        )

    @staticmethod
    def _result_payload(
        *,
        ok: bool,
        operation: str,
        message: str = "",
        payload: Any = None,
        error: str = "",
    ) -> dict[str, Any]:
        return {
            "ok": bool(ok),
            "operation": operation,
            "message": str(message or ""),
            "payload": payload,
            "error": str(error or ""),
        }

    def _start_worker(
        self,
        function: Callable[..., Any],
        operation: str,
        success_signal: Signal,
        *args: Any,
    ) -> None:
        worker = self._worker_factory(function, *args)
        self._workers.add(worker)
        worker.signals.result.connect(
            partial(self._on_success, worker, operation, success_signal)
        )
        worker.signals.error.connect(
            partial(self._on_error, worker, operation, success_signal)
        )
        finished = getattr(worker.signals, "finished", None)
        if finished is not None:
            finished.connect(partial(self._release_worker, worker))
        QThreadPool.globalInstance().start(worker)

    def _release_worker(self, worker: Any, *_: Any) -> None:
        self._workers.discard(worker)
        delete_later = getattr(worker, "deleteLater", None)
        if callable(delete_later):
            delete_later()

    def _on_success(
        self,
        worker: Any,
        operation: str,
        success_signal: Signal,
        result: Any,
    ) -> None:
        if operation == "load":
            rows = list(result or [])
            success_signal.emit(rows)
            envelope = self._result_payload(
                ok=True,
                operation=operation,
                message=f"Loaded {len(rows)} AP bill(s).",
                payload=rows,
            )
        else:
            payload = self._serialize_result(result)
            success_signal.emit(payload)
            envelope = self._result_payload(
                ok=True,
                operation=operation,
                message=str(payload.get("message") or self._success_message(operation)),
                payload=payload,
            )
        self.operationFinished.emit(envelope)
        logger.info(
            "AP operation completed operation=%s ok=true message=%s",
            operation,
            envelope["message"],
        )
        if envelope["message"]:
            self.toast.emit(envelope["message"])
        self._release_worker(worker)

    def _on_error(
        self,
        worker: Any,
        operation: str,
        success_signal: Signal,
        error_value: Any,
    ) -> None:
        message = self._error_text(error_value)
        failure = self._result_payload(
            ok=False,
            operation=operation,
            message=message,
            error=message,
        )
        if operation == "load":
            success_signal.emit([])
        else:
            success_signal.emit(failure)
        self.operationFinished.emit(failure)
        logger.error("AP operation failed operation=%s error=%s", operation, message)
        self.error.emit(message)
        self._release_worker(worker)

    @staticmethod
    def _error_text(error_value: Any) -> str:
        # Worker.error emits ``(exception type, exception value, traceback)``.
        # The traceback is useful in the log, but it is neither actionable nor
        # readable in the A/P form.  Prefer the exception's user-facing value.
        if isinstance(error_value, tuple) and error_value:
            if len(error_value) >= 2 and error_value[1]:
                return str(error_value[1])
            for value in reversed(error_value):
                if value:
                    return str(value)
        return str(error_value or "Accounts Payable operation failed.")

    @staticmethod
    def _success_message(operation: str) -> str:
        return {
            "create_bill": "AP bill saved.",
            "update_bill": "AP bill updated.",
            "load_details": "AP bill details loaded.",
            "delete_bill": "AP bill deleted.",
            "record_payment": "AP payment recorded.",
            "reverse_payment": "AP payment reversed.",
        }.get(operation, "Accounts Payable operation completed.")

    @staticmethod
    def _serialize_result(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return dict(result)
        if hasattr(result, "__dict__"):
            payload = dict(result.__dict__)
            payload.setdefault("ok", True)
            return payload
        return {"ok": True, "result": result}

    def _load_bills(self) -> list[dict[str, Any]]:
        from domain.ap_lifecycle import clean_text
        bills = self._ap_repository.list_bills()
        for bill in bills:
            if not bill.get("ExpenseTreatment") or not bill.get("CategoryName") or not bill.get("SourceAccount"):
                txn_id = clean_text(bill.get("ExpenseTransactionID"))
                if txn_id and hasattr(self._orchestrator, "_transaction_for_id"):
                    try:
                        txn = self._orchestrator._transaction_for_id(txn_id)
                        if txn:
                            if not bill.get("ExpenseTreatment"):
                                matter = clean_text(txn.get("matter") or txn.get("Matter"))
                                bill["ExpenseTreatment"] = "matter" if matter else "office"
                            if not bill.get("CategoryCode"):
                                bill["CategoryCode"] = clean_text(txn.get("categoryCode") or txn.get("CategoryCode"))
                            if not bill.get("CategoryName"):
                                bill["CategoryName"] = clean_text(txn.get("categoryName") or txn.get("CategoryName"))
                            if not bill.get("SourceAccount"):
                                bill["SourceAccount"] = clean_text(txn.get("fromAccount") or txn.get("FromAccount"))
                    except Exception as exc:
                        logger.warning("Failed to enrich bill %s from transaction: %s", bill.get("APBillID"), exc)
        return bills

    @Slot()
    def loadAPInvoices(self) -> None:
        # Small local read: complete deterministically; writes remain asynchronous.
        try:
            logger.info("AP reload requested")
            bills = list(self._load_bills() or [])
            self.apLoaded.emit(bills)
            logger.info("AP reload completed rows=%s", len(bills))
            self.operationFinished.emit(self._result_payload(
                ok=True, operation="load",
                message="Accounts Payable bills loaded.",
                payload={"count": len(bills)},
            ))
        except Exception as exc:
            message = self._error_text(exc)
            self.error.emit(message)
            self.operationFinished.emit(self._result_payload(
                ok=False, operation="load",
                message="Accounts Payable bills could not be loaded.",
                error=message,
            ))

    @Slot("QVariantMap")
    def saveAPInvoice(self, payload: dict[str, Any]) -> None:
        logger.info("AP save requested bill_id=%s", dict(payload or {}).get("APBillID", ""))
        self._start_worker(
            self._orchestrator.create_bill,
            "create_bill",
            self.apSaveFinished,
            dict(payload or {}),
        )

    @Slot("QVariantMap")
    def updateAPInvoice(self, payload: dict[str, Any]) -> None:
        logger.info("AP update requested bill_id=%s", dict(payload or {}).get("APBillID", ""))
        self._start_worker(
            self._orchestrator.update_bill,
            "update_bill",
            self.apSaveFinished,
            dict(payload or {}),
        )

    @Slot(str)
    def loadAPBillDetails(self, bill_id: str) -> None:
        logger.info("AP detail load requested bill_id=%s", bill_id)
        self._start_worker(
            self._orchestrator.bill_details,
            "load_details",
            self.apBillDetailsLoaded,
            bill_id,
        )

    @Slot(str)
    def deleteAPInvoice(self, bill_id: str) -> None:
        logger.info("AP delete requested bill_id=%s", bill_id)
        self._start_worker(
            self._orchestrator.delete_bill,
            "delete_bill",
            self.apDeleteFinished,
            bill_id,
        )

    @Slot("QVariantMap")
    def recordAPPayment(self, payload: dict[str, Any]) -> None:
        self._start_worker(
            self._orchestrator.record_payment,
            "record_payment",
            self.apPaymentFinished,
            dict(payload or {}),
        )

    @Slot("QVariantMap")
    def recordAPSetoff(self, payload: dict[str, Any]) -> None:
        self._start_worker(
            self._orchestrator.record_setoff,
            "record_setoff",
            self.apPaymentFinished,
            dict(payload or {}),
        )

    @Slot(str, str, str)
    def reverseAPPayment(
        self,
        payment_id: str,
        reversal_id: str,
        reason: str,
    ) -> None:
        self._start_worker(
            self._orchestrator.reverse_payment,
            "reverse_payment",
            self.apPaymentReversed,
            payment_id,
            reversal_id,
            reason,
        )

    @Slot(str, str, str)
    def reverseAPSetoff(self, payment_id: str, reversal_id: str, reason: str) -> None:
        self._start_worker(
            self._orchestrator.reverse_setoff,
            "reverse_setoff",
            self.apPaymentReversed,
            payment_id,
            reversal_id,
            reason,
        )
