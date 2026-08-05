from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _canonical_file(path_text: str, workspace: Path) -> str:
    try:
        resolved = Path(path_text).resolve()
    except Exception:
        return path_text.replace("\\", "/")

    root = workspace.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return str(resolved).replace("\\", "/")
    return "<WORKSPACE>/" + str(rel).replace("\\", "/")


def _normalize_message(message: str) -> str:
    return " ".join(message.split())


def _canonical_issue(diag: dict[str, object], workspace: Path) -> str:
    file_path = _canonical_file(str(diag.get("file", "")), workspace)
    severity = str(diag.get("severity", "unknown")).lower()
    rule = str(diag.get("rule", "") or "")
    message = _normalize_message(str(diag.get("message", "")))
    return f"{severity}|{file_path}|{rule}|{message}"


def _load_json(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    # If pyright output contains non-JSON prefixes, recover from first JSON object.
    start = text.find("{")
    if start > 0:
        text = text[start:]
    return json.loads(text)


def load_issues(json_path: Path, workspace: Path) -> list[str]:
    payload = _load_json(json_path)
    diagnostics = payload.get("generalDiagnostics", [])
    if not isinstance(diagnostics, list):
        return []
    issues = []
    for item in diagnostics:
        if isinstance(item, dict):
            issues.append(_canonical_issue(item, workspace))
    return sorted(set(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce pyright no-new-issues policy.")
    parser.add_argument("--json", required=True, help="Path to pyright --outputjson log file.")
    parser.add_argument(
        "--baseline",
        default="docs/quality/pyright_issue_baseline.txt",
        help="Baseline issue file path.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite baseline with current pyright issue set.",
    )
    args = parser.parse_args()

    workspace = Path.cwd()
    json_path = (workspace / args.json).resolve()
    baseline_path = (workspace / args.baseline).resolve()
    current = load_issues(json_path, workspace)

    if args.update_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text("\n".join(current) + ("\n" if current else ""), encoding="utf-8")
        print(f"[PYRIGHT-GATE] Baseline updated: {baseline_path} ({len(current)} issues)")
        return 0

    if not baseline_path.exists():
        print(
            "[PYRIGHT-GATE] Baseline missing. "
            "Run with --update-baseline after confirming current pyright issues.",
            file=sys.stderr,
        )
        return 2

    baseline = {
        line.strip()
        for line in baseline_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    }
    current_set = set(current)
    new_issues = sorted(current_set - baseline)

    print(f"[PYRIGHT-GATE] Baseline issues: {len(baseline)}")
    print(f"[PYRIGHT-GATE] Current issues: {len(current_set)}")
    if not new_issues:
        print("[PYRIGHT-GATE] PASS (no new issues)")
        return 0

    print(f"[PYRIGHT-GATE] FAIL ({len(new_issues)} new issues)")
    for line in new_issues[:50]:
        print(line)
    if len(new_issues) > 50:
        print(f"... and {len(new_issues) - 50} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
