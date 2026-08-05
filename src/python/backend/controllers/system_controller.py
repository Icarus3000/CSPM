import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, Property

class SystemController(QObject):
    themeChanged = Signal()
    error = Signal(str)
    toast = Signal(str)

    def __init__(self, app_controller, snapshot_service, settings_path, themes_data):
        super().__init__()
        self._app = app_controller
        self._snapshot_service = snapshot_service
        self._settings_path = settings_path
        self._themes_data = themes_data
        
        self.load_settings()

    @Property(dict, notify=themeChanged)
    def theme(self):
        return self._themes_data.get(self._app._theme_name, self._themes_data.get("Dark", {}))

    @Property(list, constant=True)
    def themeNames(self):
        order = ["White", "Gray", "Dark", "Blue", "Red", "Green", "Purple"]
        return [name for name in order if name in self._themes_data]

    @Slot(str)
    def setTheme(self, name):
        if name in self._themes_data:
            self._app._theme_name = name
            self.save_settings()
            self._app.themeChanged.emit()
            self.themeChanged.emit()

    @Slot(str, result=dict)
    def getThemeByName(self, name):
        if isinstance(name, str) and name in self._themes_data:
            return dict(self._themes_data[name])
        return {}

    def load_settings(self):
        if self._settings_path.exists():
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "theme" in data and data["theme"] in self._themes_data:
                    self._app._theme_name = data["theme"]
            except Exception:
                pass

    def save_settings(self):
        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump({"theme": self._app._theme_name}, f)
        except Exception:
            pass

    @Slot(str, result=bool)
    def createProjectSnapshot(self, reason):
        return self._app._create_project_snapshot(reason or "manual", emit_toast=True)

    @Slot(int, result=list)
    def listProjectSnapshots(self, limit):
        try:
            return self._snapshot_service.list_snapshots(limit=max(1, int(limit or 1)))
        except Exception as exc:
            self.error.emit(f"Could not list snapshots: {exc}")
            return []

    @Slot(str, result=bool)
    def restoreProjectSnapshot(self, snapshot_id):
        try:
            ok = self._snapshot_service.restore_snapshot(snapshot_id)
            if ok:
                self.toast.emit(f"Project snapshot restored: {snapshot_id}")
                return True
            self.error.emit(f"Snapshot not found: {snapshot_id}")
            return False
        except Exception as exc:
            self.error.emit(f"Snapshot restore failed: {exc}")
            return False

