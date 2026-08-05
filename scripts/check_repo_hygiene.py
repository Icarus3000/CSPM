from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SCAN_ROOTS = (
    PROJECT_ROOT,
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "scripts",
)
EXCLUDED_TOP_LEVEL = {
    ".venv",
    ".pytest_cache",
    ".pytest_tmp",
    ".pytest_tmp_live",
    ".pytest_tmp_runs",
    ".codex_tmp",
    "archive",
    "backups",
    "dumps",
    "dist",
    "outputs",
}
EXCLUDED_PREFIXES = (".venv_", ".pytest_tmp_", "tmp")
ROOT_FORBIDDEN_NAMES = {
    "append_tests.py",
    "extract_panels.py",
    "fix_grids.py",
    "fix_qml_lint.py",
    "fix_qml_lint_id.py",
    "fix_report.py",
    "fix_table_ref.py",
    "fix_table_ref_2.py",
    "my_test_runner.py",
    "test_handover.py",
    "test_handover.ps1",
    "test_run.ps1",
    "lint_summary.txt",
    "remaining_warnings.txt",
    "remaining_warnings_utf8.txt",
    "pytest_errors.log",
    "pytest_errors2.log",
    "tests_error.txt",
    "tests_output.txt",
    "tests_output_fixed.txt",
    "tests_output_fixed2.txt",
    "tests_output_utf8.txt",
    "test_out.txt",
    "test_out.log",
    "test_output.log",
    "run_out.txt",
    "out.txt",
    "debug.txt",
    "errors.txt",
    "err.log",
    "err8.log",
    "err_time.txt",
    "err_utf8.log",
    "tmp_startup_err.log",
    "tmp_startup_out.log",
    "migration_debug.txt",
    "qml_lint.log",
}
ROOT_FORBIDDEN_PATTERNS = (
    re.compile(r"^fix_.*\.py$", re.IGNORECASE),
    re.compile(r"^test_.*\.log$", re.IGNORECASE),
    re.compile(r"^startup_profile.*\.txt$", re.IGNORECASE),
    re.compile(r"^bad_(?:lines|strings)\.txt$", re.IGNORECASE),
)
QML_ARTIFACT_PATTERNS = (
    re.compile(r".*\.pre_[^\\/]+$", re.IGNORECASE),
    re.compile(r".*\.base_[^\\/]+$", re.IGNORECASE),
    re.compile(r".*\.copilot-broken$", re.IGNORECASE),
    re.compile(r".*_broken[^\\/]*$", re.IGNORECASE),
)


@dataclass(frozen=True)
class Finding:
    kind: str
    path: Path


def _is_excluded(path: Path) -> bool:
    try:
        rel = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return True
    if not rel.parts:
        return False
    top = rel.parts[0]
    if top in EXCLUDED_TOP_LEVEL:
        return True
    return any(top.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def _iter_paths(root: Path) -> list[Path]:
    items: list[Path] = []
    for path in root.rglob("*"):
        if _is_excluded(path):
            continue
        items.append(path)
    return items


def _check_root_path(path: Path) -> list[Finding]:
    rel = path.relative_to(PROJECT_ROOT)
    findings: list[Finding] = []
    if rel.parent != Path("."):
        return findings
    if path.is_dir():
        if path.name in {"__pycache__", ".codex_tmp", ".pytest_cache", ".pytest_tmp", ".pytest_tmp_live", ".pytest_tmp_runs"}:
            findings.append(Finding("forbidden_root_dir", rel))
        return findings
    if path.name in ROOT_FORBIDDEN_NAMES:
        findings.append(Finding("forbidden_root_file", rel))
    for pattern in ROOT_FORBIDDEN_PATTERNS:
        if pattern.match(path.name):
            findings.append(Finding("forbidden_root_file", rel))
            break
    if path.suffix.lower() in {".pyc", ".pyo"}:
        findings.append(Finding("bytecode_file", rel))
    return findings


def _check_active_path(path: Path) -> list[Finding]:
    rel = path.relative_to(PROJECT_ROOT)
    findings: list[Finding] = []
    if path.is_dir():
        if path.name == "__pycache__":
            findings.append(Finding("bytecode_dir", rel))
        return findings

    if path.suffix.lower() in {".pyc", ".pyo"}:
        findings.append(Finding("bytecode_file", rel))

    rel_text = str(rel).replace("\\", "/")
    if rel_text.startswith("src/"):
        for pattern in QML_ARTIFACT_PATTERNS:
            if pattern.match(rel_text):
                findings.append(Finding("qml_artifact", rel))
                break
    return findings


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []
    seen: set[Path] = set()
    for root in ACTIVE_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_paths(root):
            if path in seen:
                continue
            seen.add(path)
            if path.parent == PROJECT_ROOT or path == PROJECT_ROOT:
                findings.extend(_check_root_path(path))
            findings.extend(_check_active_path(path))
    findings.sort(key=lambda item: (str(item.path).lower(), item.kind))
    return findings


def main() -> int:
    findings = collect_findings()
    if not findings:
        print("[HYGIENE] PASS")
        return 0

    print(f"[HYGIENE] FAIL ({len(findings)} issues)")
    for finding in findings[:200]:
        print(f"{finding.kind}|{finding.path.as_posix()}")
    if len(findings) > 200:
        print(f"... and {len(findings) - 200} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
