from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass()
class AppPaths:
    root: Path
    override_data_dir: Path | None = None
    override_master_dir: Path | None = None

    @staticmethod
    def project_root() -> Path:
        import sys
        # For bundled assets (e.g. src/qml, docs), PyInstaller provides sys._MEIPASS.
        # In PyInstaller 6+ one-dir mode, this points to the _internal directory.
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        
        # Fallback to dev mode: src/python/services/paths.py -> services -> python -> src -> __CSPM
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def executable_root() -> Path:
        import sys
        env_override = os.environ.get("CSPM_EXECUTABLE_ROOT", "").strip()
        if env_override:
            return Path(env_override)
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS)
        return AppPaths.project_root()

    # persistent data root
    def _persistent_data_root(self) -> Path:
        env_override = os.environ.get("CSPM_DATA_DIR", "").strip()
        if env_override:
            return Path(env_override)
        import sys
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                return Path(local_app_data) / "CSPM"
            return Path.home() / ".cspm_data"
        # Dev mode uses project root
        return self.root

    # data
    def master_data_dir(self) -> Path | None:
        if self.override_master_dir and str(self.override_master_dir).strip():
            return self.override_master_dir
        return None

    def data_dir(self) -> Path:
        if self.override_data_dir and str(self.override_data_dir).strip():
            return self.override_data_dir
        return self._persistent_data_root() / "data"

    def workbook_path(self) -> Path:
        return self.data_dir() / "CSPM.xlsm"

    def dockets_workbook_path(self) -> Path:
        return self.data_dir() / "Dockets.xlsm"

    def state_dir(self) -> Path:
        return self.data_dir() / "state"

    def prefs_path(self) -> Path:
        return self.state_dir() / "prefs.json"

    def last_entry_path(self) -> Path:
        return self.state_dir() / "last_entry.json"

    def excel_metadata_cache_path(self) -> Path:
        return self.state_dir() / "excel_table_metadata_cache.json"

    # backups/dumps
    def backups_dir(self) -> Path:
        return self._persistent_data_root() / "backups" / "CSPM"

    def backups_snapshots_dir(self) -> Path:
        return self.backups_dir() / "snapshots"

    # user runtime (outside repo ACLs, when possible)
    def runtime_dir(self) -> Path:
        env_override = os.environ.get("CSPM_RUNTIME_DIR", "").strip()
        if env_override:
            return Path(env_override)
        return self._persistent_data_root()

    def user_settings_path(self) -> Path:
        env_override = os.environ.get("CSPM_RUNTIME_DIR", "").strip()
        if env_override:
            return Path(env_override) / "user_settings.json"
        
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data) / "CSPM" / "user_settings.json"
        return Path.home() / ".cspm_data" / "user_settings.json"

    def exports_dir(self) -> Path:
        env_override = os.environ.get("CSPM_EXPORT_DIR", "").strip()
        if env_override:
            return Path(env_override)
        return self.runtime_dir() / "exports"

    def dumps_dir(self) -> Path:
        return self._persistent_data_root() / "dumps"

    def dumps_workspace_dir(self) -> Path:
        return self.dumps_dir() / "workspace"

    def dumps_bible_dir(self) -> Path:
        return self.root / "dumps" / "bible"

    # docs/schema
    def docs_dir(self) -> Path:
        return self.root / "docs"

    def bible_md_path(self) -> Path:
        return self.docs_dir() / "BIBLE.md"

    def roadmap_md_path(self) -> Path:
        return self.docs_dir() / "ROADMAP.md"

    def changelog_md_path(self) -> Path:
        return self.docs_dir() / "CHANGELOG.md"

    def spec_dir(self) -> Path:
        return self.docs_dir() / "spec"

    def decisions_dir(self) -> Path:
        return self.docs_dir() / "DECISIONS"

    def schema_dir(self) -> Path:
        return self.root / "schema"

    def workbook_schema_path(self) -> Path:
        return self.schema_dir() / "workbook_schema.yml"

    # qml
    def themes_json_path(self) -> Path:
        return self.root / "src" / "qml" / "themes" / "themes.json"
