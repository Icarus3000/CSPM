# 43_create_venv_py314.ps1
$ProjectRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House\__CSPM"
$Py = "C:\Users\cschn\AppData\Local\Programs\Python\Python314\python.exe"

if (-not (Test-Path -LiteralPath $Py)) {
  throw "Python 3.14 not found at: $Py"
}

Set-Location $ProjectRoot

# Create venv if missing
if (-not (Test-Path -LiteralPath ".venv")) {
  & $Py -m venv .venv
}

# Use venv python from here on
$Vpy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

& $Vpy -m pip install --upgrade pip
& $Vpy -m pip install -r ".\requirements.txt"

Write-Host ""
Write-Host "Interpreter to use:" -ForegroundColor Green
Write-Host "  $Vpy" -ForegroundColor Green
Write-Host ""
Write-Host "Run the app with:" -ForegroundColor Cyan
Write-Host "  $Vpy .\src\python\main.py" -ForegroundColor Cyan