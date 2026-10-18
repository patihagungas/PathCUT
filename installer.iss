; Inno Setup 6 script for PathCUT
; Compile with: ISCC.exe installer.iss

[Setup]
AppName=PathCUT
AppVersion=0.1.0
AppPublisher=PathCUT
DefaultDirName={autopf}\PathCUT
DefaultGroupName=PathCUT
OutputDir=Output
OutputBaseFilename=PathCUT-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Files]
Source: "dist\PathCUT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PathCUT"; Filename: "{app}\PathCUT.exe"
Name: "{group}\Uninstall PathCUT"; Filename: "{uninstallexe}"
Name: "{commondesktop}\PathCUT"; Filename: "{app}\PathCUT.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\PathCUT.exe"; Description: "Launch PathCUT"; Flags: nowait postinstall skipifsilent
