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

    def resource_root(self) -> Path:
        """Locate shipped resources independently of the writable profile.

        Frozen callers may use ``root`` for a per-user runtime directory. The
        immutable package remains under PyInstaller's resource directory.
        Development callers retain their explicitly supplied fixture/source root.
        """
        import sys
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return self.project_root()
        return self.root

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
        from backend.native_candidate import profile
        if profile() is not None:
            return None
        if self.override_master_dir and str(self.override_master_dir).strip():
            return self.override_master_dir
        from services.data_locations import environment_data_path
        return environment_data_path("CSPM_MASTER_DATA_DIR")

    def data_dir(self) -> Path:
        from backend.native_candidate import profile
        candidate = profile()
        if candidate is not None:
            return candidate / "working" / "data"
        if self.override_data_dir and str(self.override_data_dir).strip():
            return self.override_data_dir
        from services.data_locations import environment_data_path
        selected = environment_data_path("CSPM_LOCAL_DATA_DIR")
        if selected is not None:
            return selected
        return self._persistent_data_root() / "data"

    def workbook_path(self) -> Path:
        return self.data_dir() / "CSPM.xlsm"

    def dockets_workbook_path(self) -> Path:
        return self.data_dir() / "Dockets.xlsm"

    def sqlite_db_path(self) -> Path:
        """Resolve SQLite database path (%LOCALAPPDATA%/CSPM/data/cspm.db or test/dev data_dir/cspm.db)."""
        env_override = os.environ.get("CSPM_SQLITE_DB_PATH", "").strip()
        if env_override:
            return Path(os.path.expandvars(env_override)).expanduser()
        return self.data_dir() / "cspm.db"

    def _is_isolated_test_root(self) -> bool:
        if os.environ.get("PYTEST_CURRENT_TEST", "").strip():
            return True
        try:
            root_resolved = self.root.resolve()
            proj_resolved = self.project_root().resolve()
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            app_data_root = (Path(local_app_data) / "CSPM").resolve() if local_app_data else None
            if root_resolved != proj_resolved and (app_data_root is None or root_resolved != app_data_root):
                return True
            if self.override_data_dir is not None and str(self.override_data_dir).strip():
                od_resolved = Path(self.override_data_dir).resolve()
                proj_data = (proj_resolved / "data").resolve()
                app_data_dir = (app_data_root / "data").resolve() if app_data_root is not None else None
                if od_resolved != proj_data and (app_data_dir is None or od_resolved != app_data_dir):
                    return True
        except OSError:
            return True
        return False

    def legacy_onedrive_dockets_workbook_path(self) -> Path | None:
        """Resolve %OneDrive%/__Invoices (1)/Dockets.xlsm dynamically via environment/PathService.

        In isolated test fixtures (tmp_path or override_data_dir), only explicit
        test overrides or a fixture-local __Invoices (1)/Dockets.xlsm are returned
        so tests never touch the live user OneDrive workbook.
        """
        explicit_override = os.environ.get("CSPM_LEGACY_DOCKETS_XLSM", "").strip()
        if explicit_override:
            return Path(os.path.expandvars(explicit_override)).expanduser()

        fixture_candidate = self.root / "__Invoices (1)" / "Dockets.xlsm"
        if fixture_candidate.exists():
            return fixture_candidate

        if self._is_isolated_test_root():
            return None

        candidate_roots: list[Path] = []
        for env_key in ("OneDriveCommercial", "OneDrive", "OneDriveConsumer"):
            env_val = os.environ.get(env_key, "").strip()
            if env_val:
                expanded = Path(os.path.expandvars(env_val)).expanduser()
                if expanded not in candidate_roots:
                    candidate_roots.append(expanded)

        try:
            for match in sorted(Path.home().glob("OneDrive*")):
                if match.is_dir() and match not in candidate_roots:
                    candidate_roots.append(match)
        except OSError:
            pass

        for od_root in candidate_roots:
            candidate = od_root / "__Invoices (1)" / "Dockets.xlsm"
            if candidate.is_file():
                return candidate

        for od_root in candidate_roots:
            inv_dir = od_root / "__Invoices (1)"
            if inv_dir.is_dir():
                return inv_dir / "Dockets.xlsm"

        return None

    def legacy_dockets_sync_targets(self) -> list[Path]:
        """Return existing Dockets.xlsm paths (OneDrive __Invoices (1)/Dockets.xlsm + local data mirror)."""
        targets: list[Path] = []
        seen: set[str] = set()

        def _add_if_exists(candidate: Path | None) -> None:
            if candidate is None:
                return
            try:
                if candidate.is_file():
                    resolved_key = str(candidate.resolve()).casefold()
                    if resolved_key not in seen:
                        seen.add(resolved_key)
                        targets.append(candidate)
            except OSError:
                return

        _add_if_exists(self.legacy_onedrive_dockets_workbook_path())
        _add_if_exists(self.dockets_workbook_path())
        if not self._is_isolated_test_root():
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                _add_if_exists(Path(local_app_data) / "CSPM" / "data" / "Dockets.xlsm")
            try:
                _add_if_exists(self.shared_vault_dir().parent / "Dockets.xlsm")
            except Exception:
                pass
        if self._is_isolated_test_root():
            _add_if_exists(self.root / "Dockets.xlsm")
        return targets

    def local_vault_dir(self) -> Path:
        """Resolve <data_dir>/Vault (e.g. %LOCALAPPDATA%/CSPM/data/Vault)."""
        return self.data_dir() / "Vault"

    def shared_vault_dir(self) -> Path:
        """Resolve <masterDataDir>/Vault (e.g. %OneDrive%/CSPM_Shared_Data/Vault)."""
        master = self.master_data_dir()
        if master is not None:
            return master / "Vault"

        # Check user_settings.json if masterDataDir is configured there
        try:
            import json
            settings_file = self.user_settings_path()
            if settings_file.is_file():
                payload = json.loads(settings_file.read_text(encoding="utf-8"))
                master_setting = str(payload.get("masterDataDir", "") or "").strip()
                if master_setting:
                    expanded = Path(os.path.expandvars(master_setting)).expanduser()
                    if expanded.is_absolute():
                        return expanded / "Vault"
        except Exception:
            pass

        # Discover %OneDriveCommercial% / %OneDrive% / ~/OneDrive* CSPM_Shared_Data
        for env_key in ("OneDriveCommercial", "OneDrive", "OneDriveConsumer"):
            env_val = os.environ.get(env_key, "").strip()
            if env_val:
                od_shared = Path(os.path.expandvars(env_val)).expanduser() / "CSPM_Shared_Data"
                if od_shared.exists():
                    return od_shared / "Vault"

        try:
            for match in sorted(Path.home().glob("OneDrive*")):
                if match.is_dir() and (match / "CSPM_Shared_Data").exists():
                    return match / "CSPM_Shared_Data" / "Vault"
        except OSError:
            pass

        for env_key in ("OneDriveCommercial", "OneDrive", "OneDriveConsumer"):
            env_val = os.environ.get(env_key, "").strip()
            if env_val:
                return Path(os.path.expandvars(env_val)).expanduser() / "CSPM_Shared_Data" / "Vault"

        return self.local_vault_dir()

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
        return self.resource_root() / "docs"

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
        return self.resource_root() / "schema"

    def workbook_schema_path(self) -> Path:
        return self.schema_dir() / "workbook_schema.yml"

    # qml
    def themes_json_path(self) -> Path:
        return self.resource_root() / "src" / "qml" / "themes" / "themes.json"
