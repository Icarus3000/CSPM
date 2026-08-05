# 02_Validate_Structure.ps1
# Validates the expected __CSPM structure and prints a report.

$BaseRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House"
$ProjectRoot = Join-Path $BaseRoot "__CSPM"

$RequiredFolders = @(
  "data",
  "data\state",
  "backups\CSPM",
  "dumps\workspace",
  "dumps\bible",
  "outputs\invoices\paid\docx",
  "outputs\invoices\paid\pdf",
  "outputs\invoices\receivable\docx",
  "outputs\invoices\receivable\pdf",
  "outputs\invoices\write_off\docx",
  "outputs\invoices\write_off\pdf",
  "outputs\invoices\reversed\docx",
  "outputs\invoices\reversed\pdf",
  "outputs\ledgers",
  "outputs\productivity_reports",
  "outputs\statements_of_account",
  "outputs\hst",
  "templates\invoices",
  "templates\reports",
  "assets\images",
  "assets\excel",
  "schema\migrations",
  "docs\DECISIONS",
  "src\python",
  "src\qml\components",
  "src\qml\themes",
  "scripts",
  "archive"
)

$RequiredFiles = @(
  "README.md",
  "requirements.txt",
  "docs\BIBLE.md",
  "docs\ROADMAP.md",
  "docs\CHANGELOG.md",
  "schema\workbook_schema.yml"
)

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
  throw "ProjectRoot not found: $ProjectRoot"
}

Write-Host "Validating __CSPM structure at:" -ForegroundColor Cyan
Write-Host "  $ProjectRoot" -ForegroundColor Yellow
Write-Host ""

$MissingFolders = @()
foreach ($rel in $RequiredFolders) {
  $full = Join-Path $ProjectRoot $rel
  if (-not (Test-Path -LiteralPath $full)) {
    $MissingFolders += $rel
  }
}

$MissingFiles = @()
foreach ($rel in $RequiredFiles) {
  $full = Join-Path $ProjectRoot $rel
  if (-not (Test-Path -LiteralPath $full)) {
    $MissingFiles += $rel
  }
}

Write-Host "=== SUMMARY ===" -ForegroundColor Cyan
Write-Host ("Required folders: {0}" -f $RequiredFolders.Count)
Write-Host ("Missing folders:  {0}" -f $MissingFolders.Count)
Write-Host ("Required files:   {0}" -f $RequiredFiles.Count)
Write-Host ("Missing files:    {0}" -f $MissingFiles.Count)
Write-Host ""

if ($MissingFolders.Count -gt 0) {
  Write-Host "MISSING FOLDERS:" -ForegroundColor Red
  $MissingFolders | ForEach-Object { Write-Host ("  - " + $_) }
  Write-Host ""
} else {
  Write-Host "Folders OK." -ForegroundColor Green
  Write-Host ""
}

if ($MissingFiles.Count -gt 0) {
  Write-Host "MISSING FILES:" -ForegroundColor Red
  $MissingFiles | ForEach-Object { Write-Host ("  - " + $_) }
  Write-Host ""
} else {
  Write-Host "Files OK." -ForegroundColor Green
  Write-Host ""
}

# Optional: show "extra" top-level items (doesn't mark as failure)
$TopLevel = Get-ChildItem -LiteralPath $ProjectRoot -Force | Select-Object -ExpandProperty Name
Write-Host "TOP-LEVEL ITEMS:" -ForegroundColor Cyan
$TopLevel | Sort-Object | ForEach-Object { Write-Host ("  - " + $_) }
Write-Host ""

# Output a compact folder tree (depth 3) for quick human verification
Write-Host "TREE (depth 3):" -ForegroundColor Cyan
$depth = 3
function Show-Tree([string]$path, [int]$level) {
  if ($level -gt $depth) { return }
  Get-ChildItem -LiteralPath $path -Directory -Force | Sort-Object Name | ForEach-Object {
    $indent = ("  " * $level)
    Write-Host ("{0}- {1}" -f $indent, $_.Name)
    Show-Tree $_.FullName ($level + 1)
  }
}
Write-Host ("- " + (Split-Path -Leaf $ProjectRoot))
Show-Tree $ProjectRoot 1