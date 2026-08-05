from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


WARNING_PREFIX = "Warning:"
IGNORED_RUNTIME_PREFIXES = (
    "WARNING: [QMLLINT] Skipping non-runnable tool",
    "WARNING: [QMLLINT] Tool probe failed",
)
WARNING_PATTERN = re.compile(
    r"^Warning:\s+(?P<path>.+?):\d+:\d+:\s+(?P<message>.+?)\s+\[(?P<code>[^\]]+)\]\s*$"
)


def canonicalize(line: str, workspace: Path) -> str:
    text = line.strip()
    root = str(workspace.resolve())
    text = text.replace(root + os.sep, "<WORKSPACE>/")
    text = text.replace(root + "\\", "<WORKSPACE>/")
    text = text.replace(root + "/", "<WORKSPACE>/")
    match = WARNING_PATTERN.match(text)
    if not match:
        return " ".join(text.split())

    path = match.group("path").replace("\\", "/")
    message = " ".join(match.group("message").split())
    code = match.group("code").strip()
    return f"Warning: {path}: {message} [{code}]"


def _decode_log_bytes(raw: bytes) -> str:
    for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_warning_lines(log_path: Path, workspace: Path) -> list[str]:
    warnings: list[str] = []
    content = _decode_log_bytes(log_path.read_bytes())
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(IGNORED_RUNTIME_PREFIXES):
            continue
        if line.startswith(WARNING_PREFIX):
            warnings.append(canonicalize(line, workspace))
    return sorted(set(warnings))


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce qmllint no-new-warnings policy.")
    parser.add_argument("--log", required=True, help="Path to qmllint log file.")
    parser.add_argument(
        "--baseline",
        default="docs/quality/qmllint_warning_baseline.txt",
        help="Baseline warning file path.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite baseline with current warnings.",
    )
    args = parser.parse_args()

    workspace = Path.cwd()
    log_path = (workspace / args.log).resolve()
    baseline_path = (workspace / args.baseline).resolve()
    current = load_warning_lines(log_path, workspace)

    if args.update_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text("\n".join(current) + ("\n" if current else ""), encoding="utf-8")
        print(f"[QMLLINT-GATE] Baseline updated: {baseline_path} ({len(current)} warnings)")
        return 0

    if not baseline_path.exists():
        print(
            "[QMLLINT-GATE] Baseline missing. "
            "Run with --update-baseline after confirming current warning set.",
            file=sys.stderr,
        )
        return 2

    baseline = {
        line.strip()
        for line in baseline_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    }
    current_set = set(current)
    new_warnings = sorted(current_set - baseline)

    print(f"[QMLLINT-GATE] Baseline warnings: {len(baseline)}")
    print(f"[QMLLINT-GATE] Current warnings: {len(current_set)}")
    if not new_warnings:
        print("[QMLLINT-GATE] PASS (no new warnings)")
        return 0

    print(f"[QMLLINT-GATE] FAIL ({len(new_warnings)} new warnings)")
    for line in new_warnings[:50]:
        print(line)
    if len(new_warnings) > 50:
        print(f"... and {len(new_warnings) - 50} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
