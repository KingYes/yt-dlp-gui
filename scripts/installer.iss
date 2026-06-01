; Inno Setup script for the Windows online installer (per-user, no admin).

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#ifndef ManifestUrl
  #define ManifestUrl "https://github.com/KingYes/yt-dlp-gui/releases/latest/download/update-manifest.json"
#endif

#define MyAppName "yt-dlp GUI"
#define MyAppPublisher "KingYes"
#define MyAppURL "https://github.com/KingYes/yt-dlp-gui"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\yt-dlp-gui
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release-windows
OutputBaseFilename=yt-dlp-gui-setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\launcher.exe
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\launcher.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\install-runtime.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\update-helper.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\launcher.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\launcher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\install-runtime.exe"; Parameters: "--manifest ""{#ManifestUrl}"" --dest ""{app}"""; WorkingDir: "{app}"; StatusMsg: "Downloading application components..."; Flags: waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
