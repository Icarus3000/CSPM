# 41_diag_openpyxl_import.ps1
$ProjectRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House\__CSPM"
Set-Location $ProjectRoot

Write-Host "Python executable / version:" -ForegroundColor Cyan
python -c "import sys; print(sys.executable); print(sys.version)"

Write-Host "`nTiming openpyxl import (with faulthandler)..." -ForegroundColor Cyan
$code = @"
import time, faulthandler, threading, sys
faulthandler.enable()
def dump():
    import faulthandler
    faulthandler.dump_traceback()
t = threading.Timer(8.0, dump)  # dump stack if import takes >8s
t.start()
t0 = time.time()
import openpyxl
dt = time.time() - t0
t.cancel()
print('openpyxl imported OK in', round(dt, 3), 'seconds')
"@

python -X faulthandler -c $code