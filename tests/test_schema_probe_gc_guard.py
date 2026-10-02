"""Schema probing follows the same worker/GC guard as other workbook reads."""
import gc
from pathlib import Path
import sys
from threading import Thread
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
from repositories import excel_repo
from services.paths import AppPaths


@pytest.mark.parametrize("initially_enabled", [True, False])
def test_worker_schema_probe_suppresses_collection_and_restores_original_gc_state(
        tmp_path, monkeypatch, initially_enabled):
    workbook = tmp_path / "CSPM.xlsm"
    workbook.touch()
    repo = excel_repo.ExcelRepo(AppPaths(ROOT, tmp_path))
    monkeypatch.setattr(repo, "_get_cached_schema_requires_migration", lambda _: None)
    monkeypatch.setattr(repo, "_set_cached_schema_requires_migration", lambda *_: None)
    monkeypatch.setattr(repo, "_persist_table_meta_cache", lambda: None)
    monkeypatch.setattr(excel_repo, "_lazy_load_heavy_libs", lambda: None)
    observed = []

    def load(*args, **kwargs):
        observed.append(gc.isenabled())
        raise RuntimeError("exercise parser failure cleanup")

    monkeypatch.setattr(excel_repo, "load_workbook", load, raising=False)
    original = gc.isenabled()
    try:
        (gc.enable if initially_enabled else gc.disable)()
        result = []
        worker = Thread(target=lambda: result.append(repo.schema_requires_migration()))
        worker.start()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert result == [True]
        assert observed == [False]
        assert gc.isenabled() is initially_enabled
    finally:
        (gc.enable if original else gc.disable)()
