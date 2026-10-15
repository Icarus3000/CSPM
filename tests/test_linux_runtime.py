from __future__ import annotations

from pathlib import Path
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src/python"
if str(SOURCE) not in sys.path:
    sys.path.append(str(SOURCE))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux desktop ownership")
def test_live_instance_cannot_be_replaced_and_releases_cleanly(tmp_path, monkeypatch):
    from backend.linux_instance import acquire_instance_lock
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    first = acquire_instance_lock()
    assert first is not None
    assert acquire_instance_lock() is None
    candidate = acquire_instance_lock(candidate=True)
    assert candidate is not None
    candidate.unlock()
    first.unlock()
    successor = acquire_instance_lock()
    assert successor is not None
    successor.unlock()


def test_restart_waits_for_parent_exit_before_launching(monkeypatch):
    from backend import restart_worker
    calls = []
    remaining = iter([True, True, False])
    def kill(pid, signal):
        assert pid == 321 and signal == 0
        if not next(remaining):
            raise ProcessLookupError
    monkeypatch.setattr(restart_worker.os, "kill", kill)
    monkeypatch.setattr(restart_worker.time, "sleep", lambda value: calls.append("wait"))
    monkeypatch.setattr(restart_worker.subprocess, "Popen", lambda args, **kwargs: calls.append(args))
    assert restart_worker.run_from_argv(["CSPM", "--restart-after-pid", "321", "--", "/a path/CSPM", "--tray-only"]) == 0
    assert calls == ["wait", "wait", ["/a path/CSPM", "--tray-only"]]


def test_linux_office_conversion_isolates_profile_and_system_libraries(tmp_path, monkeypatch):
    from services import supplier_document_service as module
    source = tmp_path / "Supplier invoice.docx"
    source.write_bytes(b"synthetic source")
    destination = tmp_path / "converted.pdf"
    monkeypatch.setattr(module.shutil, "which", lambda value: "/usr/bin/libreoffice")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/frozen/internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/system/libraries")
    def convert(command, **kwargs):
        assert command[-1] == str(source)
        assert kwargs["env"]["LD_LIBRARY_PATH"] == "/system/libraries"
        profile_uri = command[1].split("=", 1)[1]
        assert "MacroSecurityLevel" in (Path(profile_uri.removeprefix("file://")) / "registrymodifications.xcu").read_text()
        output_dir = Path(command[command.index("--outdir") + 1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4 synthetic")
    monkeypatch.setattr(module.subprocess, "run", convert)
    module.SupplierDocumentService._libreoffice_to_pdf(source, destination)
    assert destination.read_bytes().startswith(b"%PDF")
    assert source.read_bytes() == b"synthetic source"


@pytest.mark.parametrize("uri,expected", [
    ("file:///home/user/My%20File%23%25.pdf", "/home/user/My File#%.pdf"),
    ("file:///C:/My%20File.pdf", "C:/My File.pdf"),
    ("file://server/shared/My%20File.pdf", "//server/shared/My File.pdf"),
    ("/home/user/100% done.pdf", "/home/user/100% done.pdf"),
])
def test_backend_file_dialog_paths_preserve_native_roots(uri, expected):
    from backend.app_controller import AppController
    assert AppController._strip_file_uri(None, uri) == expected


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux startup desktop file")
def test_linux_autostart_can_be_enabled_and_disabled_without_registry(tmp_path, monkeypatch):
    from services.desktop import configure_linux_autostart
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    configure_linux_autostart(True)
    target = tmp_path / "autostart/cspm.desktop"
    assert "--tray-only" in target.read_text()
    assert "main.py" in target.read_text()
    configure_linux_autostart(False)
    assert not target.exists()
