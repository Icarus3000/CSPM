# 05_FixJsonBOM.ps1
# Converts JSON files to UTF-8 WITHOUT BOM (safe, in-place).

$BaseRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House"
$ProjectRoot = Join-Path $BaseRoot "__CSPM"

$Targets = @(
  (Join-Path $ProjectRoot "src\qml\themes"),
  (Join-Path $ProjectRoot "data\state")
)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Fix-OneFile($path) {
  try {
    $bytes = [System.IO.File]::ReadAllBytes($path)

    # UTF-8 BOM bytes: EF BB BF
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
      $text = [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
      [System.IO.File]::WriteAllText($path, $text, $utf8NoBom)
      Write-Host "FIXED BOM: $path" -ForegroundColor Green
    } else {
      # Ensure it's still saved as UTF-8 no BOM (normalizing)
      $text = [System.IO.File]::ReadAllText($path)
      [System.IO.File]::WriteAllText($path, $text, $utf8NoBom)
      Write-Host "NORMALIZED: $path" -ForegroundColor DarkGray
    }
  } catch {
    Write-Host "ERROR: $path  $($_.Exception.Message)" -ForegroundColor Red
  }
}

foreach ($dir in $Targets) {
  if (Test-Path -LiteralPath $dir) {
    Get-ChildItem -LiteralPath $dir -Filter "*.json" -File -Recurse | ForEach-Object {
      Fix-OneFile $_.FullName
    }
  }
}

Write-Host "`nDone." -ForegroundColor Cyan