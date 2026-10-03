"""Validate the index-only privacy guard without reading any real user data."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/diagnostics/scan_cleanroom_staged.py"
SPEC = importlib.util.spec_from_file_location("cleanroom_privacy_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize("path", [
    "logs/audit/report.json", "data/business.xlsm", "docs/profile/user_settings.json",
    ".env.local", ".venv_local/pyvenv.cfg", "bundle/review.zip",
])
def test_sensitive_artifact_paths_are_rejected_before_content_read(path):
    assert MODULE.private_path_rule(path)


def test_source_and_sanitized_report_paths_are_allowed():
    assert MODULE.private_path_rule("src/python/backend/transition_experiment.py") is None
    assert MODULE.private_path_rule("docs/CLEANROOM_RESULTS.json") is None
    assert MODULE.private_path_rule("src/qml/shaders/cleanroom_transition.frag.qsb") is None


def test_recognized_credential_finding_does_not_expose_matching_contents():
    credential = ("gh" + "p_" + "a" * 36).encode()
    findings = MODULE.inspect_blob(7, b"unrelated source\n" + credential)
    assert findings == [MODULE.Finding(7, "GitHub credential")]
    assert credential.decode() not in repr(findings)


def test_utf16_credentials_are_recognized():
    credential = "AK" + "IA" + "A" * 16
    assert MODULE.inspect_blob(1, credential.encode("utf-16")) == [MODULE.Finding(1, "AWS access identifier")]


def test_large_blob_requires_explicit_review():
    assert MODULE.inspect_blob(1, b"a" * (MODULE.MAX_BLOB_BYTES + 1)) == [
        MODULE.Finding(1, "staged blob exceeds bounded review size")
    ]


def test_index_guard_uses_staged_bytes_and_never_reads_ignored_runtime_data(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git("init", "--quiet")
    source = tmp_path / "source.py"
    source.write_text("ordinary staged text\n", encoding="utf-8")
    git("add", "--", "source.py")
    source.write_text("gh" + "p_" + "a" * 36, encoding="utf-8")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/private.log").write_text("gh" + "p_" + "b" * 36, encoding="utf-8")
    assert MODULE.staged_findings(tmp_path) == (1, [])
    git("add", "--", "source.py")
    assert MODULE.staged_findings(tmp_path) == (1, [MODULE.Finding(1, "GitHub credential")])


def test_private_path_classification_does_not_read_secret_content(tmp_path, monkeypatch):
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        assert command[:3] == ["git", "diff", "--cached"]
        return subprocess.CompletedProcess(command, 0, stdout=b"logs/person_record.json\0", stderr=b"")
    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    assert MODULE.staged_findings(tmp_path) == (1, [MODULE.Finding(1, "private/runtime artifact directory")])
    assert len(calls) == 1


def test_oversize_staged_blob_is_rejected_before_read(tmp_path, monkeypatch):
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:3] == ["git", "diff", "--cached"]:
            contents = b"docs/report.json\0"
        else:
            assert command[:3] == ["git", "cat-file", "-s"]
            contents = str(MODULE.MAX_BLOB_BYTES + 1).encode()
        return subprocess.CompletedProcess(command, 0, stdout=contents, stderr=b"")
    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    assert MODULE.staged_findings(tmp_path) == (1, [MODULE.Finding(1, "staged blob exceeds bounded review size")])
    assert len(calls) == 2
