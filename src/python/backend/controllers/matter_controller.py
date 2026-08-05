import logging
from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from backend.workers import Worker
from domain.matter_validation import validate_matter_payload

class MatterController(QObject):
    matterDataChanged = Signal()
    matterSaveFinished = Signal(dict)
    reassignFinished = Signal(dict)
    error = Signal(str)
    toast = Signal(str)

    def __init__(self, excel_repo):
        super().__init__()
        self._excel_repo = excel_repo
        self._threadpool = QThreadPool.globalInstance()

    @Slot(result=list)
    def listMatterNames(self):
        try:
            return self._excel_repo.list_matter_names()
        except Exception as exc:
            self.error.emit(f"Could not list matters: {exc}")
            return []

    @Slot(result=list)
    def listMatterDirectory(self):
        try:
            return self._excel_repo.list_matter_directory()
        except Exception as exc:
            self.error.emit(f"Could not build matter directory: {exc}")
            return []

    @Slot(str, result=dict)
    def getMatterProfile(self, matter_key):
        try:
            return dict(self._excel_repo.get_matter_profile(str(matter_key or "")))
        except Exception as exc:
            self.error.emit(f"Could not load matter profile: {exc}")
            return {"ok": False, "message": str(exc), "matter": {}}

    @Slot(str, str, str, str, result=str)
    def previewMatterNumber(self, client_name, matter_type, date_opened, existing_matter_id):
        try:
            return str(
                self._excel_repo.preview_matter_number(
                    client_name=str(client_name or ""),
                    matter_type=str(matter_type or ""),
                    date_opened=str(date_opened or ""),
                    existing_matter_id=str(existing_matter_id or ""),
                )
                or ""
            )
        except Exception:
            return ""

    @Slot(result=list)
    def listActiveMatterNames(self):
        try:
            return self._excel_repo.list_active_matter_names()
        except Exception as exc:
            self.error.emit(f"Could not list active matters: {exc}")
            return []

    @Slot(result=list)
    def listActiveMatterDirectory(self):
        try:
            return self._excel_repo.list_active_matter_directory()
        except Exception as exc:
            self.error.emit(f"Could not build matter directory: {exc}")
            return []

    @Slot("QVariantMap")
    def saveMatterProfile(self, payload):
        # 1. Domain Validation
        payload_dict = dict(payload or {})
        issues = validate_matter_payload(payload_dict)
        if issues:
            self.matterSaveFinished.emit({
                "ok": False,
                "matterId": "",
                "message": "\\n".join(f"- {issue}" for issue in issues)
            })
            return

        # 2. Async Execution
        worker = Worker(self._excel_repo.save_matter_profile, payload_dict)
        worker.signals.result.connect(self._on_matter_saved)
        worker.signals.error.connect(self._on_matter_save_error)
        self._threadpool.start(worker)

    def _on_matter_saved(self, result):
        res_dict = dict(result or {})
        if res_dict.get("ok"):
            self.toast.emit(f"Matter saved: {res_dict.get('matterId', '')}")
            self.matterDataChanged.emit()
            self.matterSaveFinished.emit(res_dict)
        else:
            self.matterSaveFinished.emit(res_dict)
            self.error.emit(res_dict.get("message", "Matter profile verification failed."))

    def _on_matter_save_error(self, err_tuple):
        exctype, value, tb_str = err_tuple
        self.error.emit(f"Could not save matter profile: {value}")
        self.matterSaveFinished.emit({
            "ok": False,
            "matterId": "",
            "message": str(value)
        })

    @Slot("QVariantMap")
    def reassignMatter(self, payload):
        worker = Worker(self._excel_repo.reassign_matter, dict(payload or {}))
        worker.signals.result.connect(self._on_reassign_finished)
        worker.signals.error.connect(self._on_reassign_error)
        self._threadpool.start(worker)

    def _on_reassign_finished(self, result):
        res_dict = dict(result or {})
        if res_dict.get("ok"):
            if res_dict.get("changed"):
                matter_label = str(res_dict.get("matterName") or res_dict.get("matterId") or "").strip()
                self.toast.emit(
                    f"Matter reassigned: {matter_label}" if matter_label else "Matter reassignment saved."
                )
                self.matterDataChanged.emit()
            else:
                self.toast.emit(str(res_dict.get("message", "Matter reassignment checked.")))
        else:
            message = str(res_dict.get("message", "") or "").strip()
            if message:
                self.error.emit(message)
        self.reassignFinished.emit(res_dict)

    def _on_reassign_error(self, err_tuple):
        exctype, value, tb_str = err_tuple
        self.error.emit(f"Could not reassign matter: {value}")
        self.reassignFinished.emit({
            "ok": False,
            "changed": False,
            "message": str(value)
        })
