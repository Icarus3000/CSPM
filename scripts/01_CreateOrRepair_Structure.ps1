# 01_CreateOrRepair_Structure.ps1
# Creates/repairs the full __CSPM future-proof structure (safe; no deletes).

$BaseRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House"
$ProjectRoot = Join-Path $BaseRoot "__CSPM"

$Today = Get-Date -Format "yyyy-MM-dd"
$LegacyFolder = Join-Path "archive" ("legacy_" + $Today)

$Folders = @(
  # data
  "data",
  "data\state",

  # backups
  "backups",
  "backups\CSPM",

  # dumps
  "dumps",
  "dumps\workspace",
  "dumps\bible",

  # outputs
  "outputs",
  "outputs\invoices",
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

  # templates
  "templates",
  "templates\invoices",
  "templates\reports",

  # assets
  "assets",
  "assets\images",
  "assets\excel",

  # schema governance
  "schema",
  "schema\migrations",

  # docs (Bible + roadmap + decisions)
  "docs",
  "docs\DECISIONS",

  # src
  "src",
  "src\python",
  "src\qml",
  "src\qml\components",
  "src\qml\themes",

  # scripts
  "scripts",

  # archive
  "archive",
  $LegacyFolder
)

$Files = @(
  "README.md",
  "requirements.txt",
  "docs\BIBLE.md",
  "docs\ROADMAP.md",
  "docs\CHANGELOG.md",
  "schema\workbook_schema.yml"
)

Write-Host "Creating/repairing under:" -ForegroundColor Cyan
Write-Host "  $ProjectRoot" -ForegroundColor Yellow

# Create project root
New-Item -ItemType Directory -Force -Path $ProjectRoot | Out-Null

# Create folders
foreach ($rel in $Folders) {
  $full = Join-Path $ProjectRoot $rel
  New-Item -ItemType Directory -Force -Path $full | Out-Null
}

# Create placeholder files if missing
foreach ($rel in $Files) {
  $full = Join-Path $ProjectRoot $rel
  if (-not (Test-Path -LiteralPath $full)) {
    $dir = Split-Path -Parent $full
    if (-not (Test-Path -LiteralPath $dir)) {
      New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    "# Placeholder - created $(Get-Date -Format s)" | Set-Content -LiteralPath $full -Encoding UTF8
  }
}

Write-Host "`nDone. Structure created/repaired." -ForegroundColor Green
Write-Host "Legacy parking folder:" -ForegroundColor Green
Write-Host "  $(Join-Path $ProjectRoot $LegacyFolder)" -ForegroundColor Green
