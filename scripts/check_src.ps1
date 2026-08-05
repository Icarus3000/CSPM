$root='c:/Users/cschn/Documents/LIH (Personal)/OneDrive - Lawyers in House/__CSPM'
$srcDir=Join-Path $root 'src'
Write-Host "root: $root"
Write-Host "srcDir: $srcDir"
Write-Host "exists: $(Test-Path $srcDir)"
Get-ChildItem -LiteralPath $srcDir -File -Recurse -Force | Select-Object -First 5 | ForEach-Object { Write-Host $_.FullName }
