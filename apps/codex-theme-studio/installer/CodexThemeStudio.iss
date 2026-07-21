#ifndef AppVersion
  #define AppVersion "2.5.1"
#endif
#ifndef SourceExe
  #error SourceExe must point to the compiled CodexThemeStudio.exe
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef SetupIcon
  #error SetupIcon must point to the generated studio.ico
#endif

[Setup]
AppId={{9A418EF1-29CB-49A8-9A32-BCECE1B944A6}
AppName=Codex Theme Studio
AppVersion={#AppVersion}
AppVerName=Codex Theme Studio {#AppVersion}
AppPublisher=Codex Theme Studio
UninstallDisplayName=Codex Theme Studio
DefaultDirName={localappdata}\Programs\Codex Theme Studio
DefaultGroupName=Codex Theme Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=Codex-Theme-Studio-Setup-{#AppVersion}
SetupIconFile={#SetupIcon}
UninstallDisplayIcon={app}\CodexThemeStudio.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
LicenseFile=..\LICENSE
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany=Codex Theme Studio
VersionInfoDescription=Codex Theme Studio Windows Installer
VersionInfoProductName=Codex Theme Studio
VersionInfoProductVersion={#AppVersion}
VersionInfoCopyright=Copyright (c) 2026
MinVersion=10.0.17763

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: checkedonce

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "CodexThemeStudio.exe"; Flags: ignoreversion

[InstallDelete]
; Remove the legacy PowerShell launcher created before the native client split.
Type: files; Name: "{userprograms}\Codex Theme Studio.lnk"

[Icons]
Name: "{group}\Codex Theme Studio"; Filename: "{app}\CodexThemeStudio.exe"; WorkingDir: "{app}"
Name: "{group}\卸载 Codex Theme Studio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Codex Theme Studio"; Filename: "{app}\CodexThemeStudio.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\CodexThemeStudio.exe"; Description: "启动 Codex Theme Studio"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\CodexThemeStudio.exe"; Parameters: "--prepare-uninstall --no-ui"; Flags: runhidden waituntilterminated; RunOnceId: "PrepareThemeStudioUninstall"

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\CodexThemeStudio\engine"
Type: dirifempty; Name: "{localappdata}\CodexThemeStudio"
