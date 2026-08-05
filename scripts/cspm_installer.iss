[Setup]
AppName=CSPM
AppVersion=2.4.0
AppPublisher=Icarus3000
AppId={{D37F21F6-427E-4FBD-A7DF-28A07A3B7E6F}
DefaultDirName={localappdata}\Programs\CSPM
DefaultGroupName=CSPM
UninstallDisplayIcon={app}\CSPM.exe
Compression=lzma2
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=CSPM-Setup-2.4.0
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
SetupIconFile=compiler:SetupClassicIcon.ico

[Files]
Source: "..\dist\CSPM\*"; DestDir: "{app}"; Excludes: "data\*,backups\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\src\templates\CSPM.xlsm"; DestDir: "{localappdata}\CSPM\data"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall
Source: "..\src\templates\Dockets.xlsm"; DestDir: "{localappdata}\CSPM\data"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall

[UninstallDelete]
; Clean up compiled python files or logs created during runtime, 
; but strictly avoid touching \data or \backups so user records are preserved.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Icons]
Name: "{group}\CSPM"; Filename: "{app}\CSPM.exe"
Name: "{group}\CSPM Recovery Utility"; Filename: "{app}\CSPM_Recovery.exe"
Name: "{autodesktop}\CSPM"; Filename: "{app}\CSPM.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\CSPM.exe"; Description: "Launch CSPM"; Flags: nowait postinstall skipifsilent
