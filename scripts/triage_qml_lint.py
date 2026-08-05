"""
QML Lint Warning Triage Script

Reads qml_lint.log (or a path passed as argv[1]) and prints a ranked
summary grouped by warning category.

Usage:
    python scripts/triage_qml_lint.py
    python scripts/triage_qml_lint.py path/to/qml_lint.log
"""
import re
import sys
from collections import Counter
from pathlib import Path


def _extract_category(line: str) -> str:
    """
    Map a qmllint warning line to a short category label.

    qmllint lines look like one of:
      filename.qml:123:45: warning: message [category]
      Warning: message
      Note: ...
    """
    # Try bracketed category at end of line: [...category-name...]
    bracket = re.search(r"\[([a-zA-Z_\-]+)\]\s*$", line)
    if bracket:
        return bracket.group(1)

    # Classify by leading severity keyword
    lower = line.strip().lower()
    if lower.startswith("warning:") or ": warning:" in lower:
        return "warning (uncategorized)"
    if lower.startswith("error:") or ": error:" in lower:
        return "error"
    if lower.startswith("note:") or ": note:" in lower:
        return "note"
    if lower.startswith("info:"):
        return "info"
    return None


def triage(log_path: Path) -> None:
    if not log_path.exists():
        print(f"[triage_qml_lint] File not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    total_lines = len(lines)
    category_counts: Counter = Counter()
    category_examples: dict = {}

    for line in lines:
        cat = _extract_category(line)
        if cat is None:
            continue
        category_counts[cat] += 1
        if cat not in category_examples:
            # Store a trimmed example (max 120 chars)
            category_examples[cat] = line.strip()[:120]

    print(f"\nQML Lint Triage — {log_path.name}")
    print(f"Total lines: {total_lines:,}")
    print(f"Categorised warnings/errors: {sum(category_counts.values()):,}")
    print("-" * 72)
    print(f"{'Count':>7}  Category")
    print("-" * 72)
    for cat, count in category_counts.most_common():
        print(f"{count:>7}  {cat}")
        example = category_examples.get(cat, "")
        if example:
            print(f"           └─ e.g. {example}")
    print("-" * 72)
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        # Default: qml_lint.log in project root (two directories above scripts/)
        path = Path(__file__).resolve().parents[1] / "qml_lint.log"
    triage(path)
