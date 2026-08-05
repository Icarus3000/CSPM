from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SRC = REPO_ROOT / "src" / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from services.paths import AppPaths
from services.workbook_integrity_service import WorkbookIntegrityIssue, WorkbookIntegrityService


def _format_issue(issue: WorkbookIntegrityIssue) -> str:
    parts = [f"[{issue.severity.upper()}]", issue.code]
    location = []
    if issue.sheet:
        location.append(issue.sheet)
    if issue.table:
        location.append(issue.table)
    if issue.row is not None:
        location.append(f"row {issue.row}")
    if issue.column:
        location.append(issue.column)
    if location:
        parts.append("(" + " / ".join(location) + ")")
    parts.append(issue.message)
    if issue.value:
        parts.append(f"value={issue.value}")
    return " ".join(parts)


def _format_text_report(report: object) -> str:
    payload = report.as_dict()
    summary = payload["summary"]
    lines = [
        "CSPM active workbook integrity check",
        f"Status: {'PASS' if report.ok else 'FAIL'}",
        f"Workbook: {payload['workbookPath']}",
        f"Schema: {payload['schemaPath']}",
        f"SHA-256: {payload['workbookSha256'] or 'unavailable'}",
        (
            "Summary: "
            f"{summary['tablesChecked']} tables, "
            f"{summary['rowsChecked']} data rows, "
            f"{summary['errorCount']} errors, "
            f"{summary['warningCount']} warnings"
        ),
    ]
    totals = summary.get("financialTotals") or {}
    if totals:
        lines.append(
            "Financial totals: "
            f"time gross={totals.get('timeGrossToClient', 0):.2f}, "
            f"time amount={totals.get('timeAmountToYou', 0):.2f}, "
            f"transactions={totals.get('transactionsAmount', 0):.2f}"
        )
    if report.issues:
        lines.append("")
        lines.append("Issues:")
        lines.extend(_format_issue(issue) for issue in report.issues)
    else:
        lines.append("")
        lines.append("No integrity issues found.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check CSPM active workbook integrity.")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="CSPM project root.")
    parser.add_argument("--workbook", default="", help="Workbook path. Defaults to data/CSPM.xlsm.")
    parser.add_argument("--schema", default="", help="Schema path. Defaults to schema/workbook_schema.yml.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", default="", help="Optional path to write the JSON report.")
    parser.add_argument(
        "--warn-as-error",
        action="store_true",
        help="Return exit code 1 when warnings are present.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    project_root = Path(args.project_root).resolve()
    workbook = Path(args.workbook).resolve() if args.workbook else None
    schema = Path(args.schema).resolve() if args.schema else None

    service = WorkbookIntegrityService(AppPaths(project_root))
    report = service.check(workbook_path=workbook, schema_path=schema)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.to_json() + "\n", encoding="utf-8")

    if args.json:
        print(report.to_json())
    else:
        print(_format_text_report(report))

    if report.error_count > 0:
        return 1
    if args.warn_as_error and report.warning_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
