"""Recovery imports select the active pair without invoking restoration."""
import builtins
import runpy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src/python"))
from backend import native_candidate


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("explicit_selector", [False, True])
def test_recovery_entry_preserves_pair_state_and_backup_roots(
    tmp_path, monkeypatch, fallback, explicit_selector,
):
    profile = tmp_path / "profile"
    selected = tmp_path / "selected-practice"
    monkeypatch.setenv("CSPM_DATA_DIR", str(profile))
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(profile / "runtime"))
    monkeypatch.setattr(native_candidate, "_profile", None)
    if explicit_selector:
        monkeypatch.setenv("CSPM_RECOVERY_DATA_DIR", str(selected.resolve()))
    else:
        monkeypatch.delenv("CSPM_RECOVERY_DATA_DIR", raising=False)
    if fallback:
        real_import = builtins.__import__

        def fixture_import(name, *args, **kwargs):
            if name == "services.paths":
                raise ImportError("isolated packaged fallback fixture")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fixture_import)

    if fallback:
        # A broken installation must not silently select a different practice.
        with pytest.raises(ImportError, match="isolated packaged fallback fixture"):
            runpy.run_path(str(ROOT / "scripts/cspm_recovery.py"), run_name="recovery_selector_fixture")
        assert not profile.exists()
        assert not selected.exists()
        return

    module = runpy.run_path(str(ROOT / "scripts/cspm_recovery.py"), run_name="recovery_selector_fixture")
    paths = module["PATHS"]
    engine = module["RecoveryEngine"]()
    expected_data = selected if explicit_selector else profile / "data"

    assert paths.workbook_path() == expected_data / "CSPM.xlsm"
    assert paths.dockets_workbook_path() == expected_data / "Dockets.xlsm"
    assert paths.state_dir() == expected_data / "state"
    assert engine.data_dir == expected_data
    assert engine.journal_path == expected_data / "state/restore_journal.json"
    assert paths.backups_snapshots_dir() == profile / "backups/CSPM/snapshots"
    assert module["APPROVED_ROOTS"] == [
        str(expected_data), str(expected_data / "state"), str(profile / "backups/CSPM/snapshots"),
    ]
    assert not profile.exists()
    assert not selected.exists()
