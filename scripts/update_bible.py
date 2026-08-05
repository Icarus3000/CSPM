from __future__ import annotations

from datetime import datetime
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(p: Path) -> str:
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def list_tree(root: Path, max_depth: int = 3) -> str:
    lines = []
    base = root.resolve()

    def walk(cur: Path, depth: int):
        if depth > max_depth:
            return
        for child in sorted(cur.iterdir(), key=lambda x: x.name.lower()):
            if child.name.startswith("."):
                continue
            rel = child.relative_to(base)
            indent = "  " * depth
            if child.is_dir():
                lines.append(f"{indent}- {rel}/")
                walk(child, depth + 1)
            else:
                lines.append(f"{indent}- {rel}")
    lines.append(f"- {base.name}/")
    walk(base, 1)
    return "\n".join(lines)


def build_bible(root: Path) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    structure = list_tree(root, max_depth=3)

    roadmap = read_text(root / "docs" / "ROADMAP.md")
    changelog = read_text(root / "docs" / "CHANGELOG.md")
    schema = read_text(root / "schema" / "workbook_schema.yml")
    drag_plan = read_text(root / "docs" / "DECISIONS" / "DRAG_PIPELINE_OPTION3.md")

    content = []
    content.append("# CSPM PROJECT BIBLE")
    content.append("")
    content.append(f"Generated: {now}")
    content.append("")
    content.append("## Purpose")
    content.append(
        "A QML-first, Excel-backed practice management system for a sole practitioner lawyer: "
        "clients, matters, time, disbursements, expenses, prebills, invoices, payments, reporting, ticklers, HST/tax."
    )
    content.append("")
    content.append("## Key Design Decisions (current)")
    content.append("- Data store: Excel workbook (CSPM.xlsm) with schema bootstrap; SQL migration later via repository layer.")
    content.append("- 'Parent' is a payor/referrer firm/lawyer, not a parent matter; supports cut percentage mechanics.")
    content.append("- UI: consistent glass/bubble QML style; main menu console landing screen.")
    content.append("")
    content.append("## Current Folder Structure (depth 3)")
    content.append("```")
    content.append(structure)
    content.append("```")
    content.append("")
    content.append("## Roadmap")
    content.append(roadmap.strip() or "_(missing docs/ROADMAP.md)_")
    content.append("")
    content.append("## Drag Pipeline (Option 3)")
    content.append(drag_plan.strip() or "_(missing docs/DECISIONS/DRAG_PIPELINE_OPTION3.md)_")
    content.append("")
    content.append("## Changelog")
    content.append(changelog.strip() or "_(missing docs/CHANGELOG.md)_")
    content.append("")
    content.append("## Workbook Schema (YAML)")
    content.append("```yaml")
    content.append(schema.strip() or "missing schema/workbook_schema.yml")
    content.append("```")
    content.append("")
    content.append("## Next Steps")
    content.append("- Implement Clients/Matters CRUD (IDs, links to Parent).")
    content.append("- Expand Time Entry to choose Client/Matter via real IDs (not names).")
    content.append("- Implement Ticklers table + UI.")
    content.append("- Implement Prebill and Invoice generation pipeline.")
    return "\n".join(content) + "\n"


def main() -> int:
    root = project_root()
    bible = build_bible(root)

    docs_bible = root / "docs" / "BIBLE.md"
    docs_bible.write_text(bible, encoding="utf-8")

    dump_dir = root / "dumps" / "bible"
    dump_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dump_path = dump_dir / f"BIBLE_{ts}.md"
    dump_path.write_text(bible, encoding="utf-8")

    print(f"Wrote: {docs_bible}")
    print(f"Wrote: {dump_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
