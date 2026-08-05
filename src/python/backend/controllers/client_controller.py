import logging
from PySide6.QtCore import QObject, QThreadPool, Signal, Slot, Property

from backend.workers import Worker
from domain.client_validation import validate_client_payload

class ClientController(QObject):
    clientDataChanged = Signal()
    clientSaveFinished = Signal(dict)
    error = Signal(str)
    toast = Signal(str)

    def __init__(self, excel_repo):
        super().__init__()
        self._excel_repo = excel_repo
        self._threadpool = QThreadPool.globalInstance()

    @Slot(result=list)
    def listClientNames(self):
        try:
            return self._excel_repo.list_client_names()
        except Exception as exc:
            self.error.emit(f"Could not list clients: {exc}")
            return []

    @Slot(result=list)
    def listActiveClientNames(self):
        try:
            return self._excel_repo.list_active_client_names()
        except Exception as exc:
            self.error.emit(f"Could not list active clients: {exc}")
            return []

    @Slot(result=list)
    def listClientDirectory(self):
        try:
            return self._excel_repo.list_client_directory()
        except Exception as exc:
            self.error.emit(f"Could not build client directory: {exc}")
            return []

    @Slot(str, result=dict)
    def getClientProfile(self, client_key):
        try:
            return dict(self._excel_repo.get_client_profile(str(client_key or "")))
        except Exception as exc:
            self.error.emit(f"Could not load client profile: {exc}")
            return {"ok": False, "message": str(exc), "client": {}}

    @Slot(str, str, result=str)
    def previewLegacyClientCode(self, name, entity_type=""):
        try:
            from repositories.client_repo import _legacy_raw_client_code
            return _legacy_raw_client_code(name, entity_type)
        except Exception:
            return ""

    @Slot("QVariantMap")
    def saveClientProfile(self, payload):
        # 1. Domain Validation
        payload_dict = dict(payload or {})
        issues = validate_client_payload(payload_dict)
        if issues:
            # Emits failure immediately without blocking
            self.clientSaveFinished.emit({
                "ok": False,
                "clientId": "",
                "message": "\n".join(f"- {issue}" for issue in issues)
            })
            return

        # 2. Async Execution via QRunnable
        worker = Worker(self._excel_repo.save_client_profile, payload_dict)
        worker.signals.result.connect(self._on_client_saved)
        worker.signals.error.connect(self._on_client_save_error)
        self._threadpool.start(worker)

    def _on_client_saved(self, result):
        res_dict = dict(result)
        if res_dict.get("ok"):
            self.toast.emit(f"Client saved: {res_dict.get('clientId', '')}")
            self.clientDataChanged.emit()
            self.clientSaveFinished.emit(res_dict)
        else:
            self.clientSaveFinished.emit(res_dict)
            self.error.emit(res_dict.get("message", "Client profile validation failed."))

    def _on_client_save_error(self, err_tuple):
        exctype, value, tb_str = err_tuple
        self.error.emit(f"Could not save client profile: {value}")
        self.clientSaveFinished.emit({
            "ok": False,
            "clientId": "",
            "message": str(value)
        })

    @Slot("QVariantMap")
    def runConflictCheck(self, payload):
        worker = Worker(self._excel_repo.run_conflict_check, dict(payload or {}))
        worker.signals.result.connect(self._on_conflict_check_finished)
        worker.signals.error.connect(self._on_conflict_check_error)
        self._threadpool.start(worker)

    # Note: we need a Signal for conflict checks so QML can get the result back
    conflictCheckFinished = Signal(dict)

    def _on_conflict_check_finished(self, result):
        res_dict = dict(result or {})
        if res_dict.get("ok"):
            total = int(res_dict.get("totalMatches", 0) or 0)
            risk = str(res_dict.get("riskLevel", "") or "").strip().lower()
            note = f"Conflict check complete: {total} match(es)"
            if risk:
                note = f"{note} [{risk}]"
            self.toast.emit(note)
        else:
            message = str(res_dict.get("message", "") or "").strip()
            if message:
                self.error.emit(message)
        self.conflictCheckFinished.emit(res_dict)

    def _on_conflict_check_error(self, err_tuple):
        exctype, value, tb_str = err_tuple
        self.error.emit(f"Could not run conflict check: {value}")
        self.conflictCheckFinished.emit({
            "ok": False,
            "message": str(value),
            "riskLevel": "none",
            "termsUsed": [],
            "matches": [],
            "totalMatches": 0,
            "summary": {"client": 0, "matter": 0, "parent": 0},
            "checkedAtUtc": "",
        })

    @Slot("QVariantMap")
    def mergeDuplicateEntities(self, payload):
        worker = Worker(self._excel_repo.merge_duplicate_entities, dict(payload or {}))
        worker.signals.result.connect(self._on_merge_duplicates_finished)
        worker.signals.error.connect(self._on_merge_error)
        self._threadpool.start(worker)

    mergeFinished = Signal(dict)

    def _on_merge_duplicates_finished(self, result):
        res_dict = dict(result or {})
        if res_dict.get("ok"):
            if res_dict.get("changed"):
                merge_type = str(res_dict.get("mergeType", "entity") or "entity").strip()
                source_name = str(res_dict.get("sourceName", "") or "").strip()
                target_name = str(res_dict.get("targetName", "") or "").strip()
                label = f"{source_name} -> {target_name}".strip(" ->")
                if label:
                    self.toast.emit(f"{merge_type.title()} merge saved: {label}")
                else:
                    self.toast.emit(f"{merge_type.title()} merge saved.")
                self.clientDataChanged.emit()
            else:
                self.toast.emit(str(res_dict.get("message", "Merge request checked.")))
        else:
            message = str(res_dict.get("message", "") or "").strip()
            if message:
                self.error.emit(message)
        self.mergeFinished.emit(res_dict)
        
    def _on_merge_error(self, err_tuple):
        exctype, value, tb_str = err_tuple
        self.error.emit(f"Could not merge duplicate entities: {value}")
        self.mergeFinished.emit({
            "ok": False,
            "changed": False,
            "message": str(value)
        })
