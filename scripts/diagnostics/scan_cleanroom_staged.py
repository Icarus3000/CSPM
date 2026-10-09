"""Read-only privacy guard for the exact Git index prepared for review.

The guard never searches the working tree, runtime logs, or user profile. It
reports rule names and ordinal item numbers, never matching contents or paths.
Passing is a bounded automated check; review the sanitized report separately.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess


MAX_BLOB_BYTES = 4 * 1024 * 1024
PRIVATE_DIRECTORIES = frozenset((
    "logs", "data", "backups", "backup", "attachments", "disposable_profile",
    "local_profile", "private",
))
PRIVATE_FILENAMES = frozenset(("machine_id.json", "user_settings.json"))
PRIVATE_SUFFIXES = frozenset((
    ".log", ".csv", ".xls", ".xlsx", ".xlsm", ".db", ".db3", ".sqlite",
    ".sqlite3", ".pem", ".key", ".p12", ".pfx", ".har", ".pcap", ".dmp",
    ".dll", ".exe", ".obj", ".pdb", ".zip", ".7z",
))
SECRET_PATTERNS = (
    ("private-key material", re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")),
    ("GitHub credential", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    ("OpenAI credential", re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    ("AWS access identifier", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Slack credential", re.compile(rb"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
)


@dataclass(frozen=True)
class Finding:
    item: int
    rule: str


def private_path_rule(path: str) -> str | None:
    """Classify paths before reading any staged artifact contents."""
    normalized = PurePosixPath(path.replace("\\", "/"))
    parts = tuple(part.lower() for part in normalized.parts)
    if any(part in PRIVATE_DIRECTORIES or part.startswith(".venv") for part in parts[:-1]):
        return "private/runtime artifact directory"
    name = normalized.name.lower()
    if name in PRIVATE_FILENAMES or name.startswith(".env"):
        return "local configuration or credentials"
    if normalized.suffix.lower() in PRIVATE_SUFFIXES:
        return "data, capture, credential, or generated package artifact"
    return None


def inspect_blob(item: int, contents: bytes) -> list[Finding]:
    if len(contents) > MAX_BLOB_BYTES:
        return [Finding(item, "staged blob exceeds bounded review size")]
    if contents.startswith((b"\xff\xfe", b"\xfe\xff")):
        contents = contents.decode("utf-16", errors="replace").encode("utf-8")
    return [Finding(item, label) for label, pattern in SECRET_PATTERNS if pattern.search(contents)]


def staged_findings(root: Path) -> tuple[int, list[Finding]]:
    """Read names and bytes from the index, ignoring unstaged copies/deletions."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    names = [name.decode("utf-8", errors="surrogateescape") for name in result.stdout.split(b"\0") if name]
    findings = []
    for item, name in enumerate(names, start=1):
        rule = private_path_rule(name)
        if rule:
            findings.append(Finding(item, rule))
            continue
        size = int(subprocess.run(
            ["git", "cat-file", "-s", ":" + name], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout)
        if size > MAX_BLOB_BYTES:
            findings.append(Finding(item, "staged blob exceeds bounded review size"))
            continue
        contents = subprocess.run(
            ["git", "show", ":" + name], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout
        findings.extend(inspect_blob(item, contents))
    return len(names), findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        count, findings = staged_findings(args.root)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("FAIL: unable to read the Git index; no captured command output was printed")
        return 2
    if not count:
        print("UNMEASURED: no staged additions or modifications to inspect")
        return 2
    for finding in findings:
        print(f"FAIL: staged item #{finding.item}: {finding.rule}")
    if findings:
        print(f"FAIL: {len(findings)} privacy guard finding(s) across {count} staged item(s)")
        return 1
    print(f"PASS: {count} staged item(s); no prohibited artifact paths or recognized credential patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
