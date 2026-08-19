; Inno Setup script for PaceChart.
;
; Installs per-user (no admin prompt) into %LocalAppData%\Programs\PaceChart
; -- the same pattern VS Code's "User Installer" uses. Expects the
; PyInstaller onedir build to already exist at ..\build\dist\PaceChart
; (see pacechart.spec) and MyAppVersion to be passed on the command line:
;
;   ISCC.exe /DMyAppVersion=1.2.3 installer.iss

#define MyAppName "PaceChart"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppExeName "PaceChart.exe"
#define MyAppPublisher "Green Hope Cross Country"

[Setup]
; Fixed AppId so future versions upgrade in place instead of installing
; side-by-side. Do not change this.
AppId={{14437947-761D-478E-B4EE-88F898D095C2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; No admin rights required or requested -- installs entirely into the
; current user's own profile.
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=PaceChartSetup
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\build\dist\PaceChart\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
