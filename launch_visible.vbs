Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pwsh.exe -File .\launch.ps1", 1, false
