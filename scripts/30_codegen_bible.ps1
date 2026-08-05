# 30_codegen_bible.ps1
# Generates update_bible.py + basic docs scaffolding (safe overwrite w/ backups)

$BaseRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House"
$ProjectRoot = Join-Path $BaseRoot "__CSPM"

$Stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot ("archive\codegen_backups\" + $Stamp)

function Ensure-Dir($p) { if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }

function Backup-IfExists($filePath) {
  if (Test-Path -LiteralPath $filePath) {
    $rel = Resolve-Path -LiteralPath $filePath | ForEach-Object { $_.Path.Substring($ProjectRoot.Length).TrimStart("\") }
    $dest = Join-Path $BackupRoot $rel
    Ensure-Dir (Split-Path -Parent $dest)
    Copy-Item -LiteralPath $filePath -Destination $dest -Force
  }
}

function Write-File($relPath, $content) {
  $full = Join-Path $ProjectRoot $relPath
  Ensure-Dir (Split-Path -Parent $full)
  Backup-IfExists $full
  Set-Content -LiteralPath $full -Value $content -Encoding UTF8
  Write-Host ("WROTE: " + $relPath) -ForegroundColor Green
}

Ensure-Dir (Join-Path $ProjectRoot "scripts")
Ensure-Dir (Join-Path $ProjectRoot "docs")
Ensure-Dir (Join-Path $ProjectRoot "docs\DECISIONS")
Ensure-Dir (Join-Path $ProjectRoot "dumps\bible")

# Minimal docs placeholders (only if missing)
$roadmap = Join-Path $ProjectRoot "docs\ROADMAP.md"
if (-not (Test-Path -LiteralPath $roadmap)) {
  Set-Content -LiteralPath $roadmap -Encoding UTF8 -Value @"
# ROADMAP

## Phase 0 (Now)
- QML Main Menu console
- Excel schema bootstrap (blank workbook)
- Time entry MVP with Parent cut %

## Phase 1
- Clients + Matters CRUD
- Ticklers MVP
- Prebills + Invoices MVP

## Phase 2
- Reports: ledgers, statements, productivity
- HST rollups and remittance tracking
"@
}

$changelog = Join-Path $ProjectRoot "docs\CHANGELOG.md"
if (-not (Test-Path -LiteralPath $changelog)) {
  Set-Content -LiteralPath $changelog -Encoding UTF8 -Value @"
# CHANGELOG

- Initial scaffolding.
"@
}

# update_bible.py
Write-File "scripts\update_bible.py" @'
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
'@

Write-Host ""
Write-Host "Bible codegen complete." -ForegroundColor Cyan
Write-Host ("Backups (if any overwrites) in: " + $BackupRoot) -ForegroundColor Cyan
