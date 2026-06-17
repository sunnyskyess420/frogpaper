; FrogPaper Installer Script
; Requires Inno Setup (https://jrsoftware.org/isdl.php)

#define MyAppName "FrogPaper"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "FrogPaper"
#define MyAppURL "https://github.com/yourusername/frogpaper"
#define MyAppExeName "FrogPaper.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\FrogPaper
DefaultGroupName=FrogPaper
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=FrogPaper-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesAssociations=yes
PrivilegesRequired=lowest
SetupIconFile=frogpaper.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"
Name: "quicklaunchicon"; Description: "Create a Quick Launch icon"; GroupDescription: "Additional icons:"

[Files]
; Main executable
Source: "dist\FrogPaper.exe"; DestDir: "{app}"; Flags: ignoreversion
; Icon files (removed due to bitmap error - app uses internal icons)
; Configuration files
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "keywords.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "negative_presets.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "presets.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "recipes.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "templates.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "prompt_library.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "gallery_tags.json"; DestDir: "{app}"; Flags: ignoreversion
; Documentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; Directories (create empty folders for user data)
; Note: wallpapers folder structure is created for user images
Source: "logs\*"; DestDir: "{app}\logs"; Flags: ignoreversion recursesubdirs createallsubdirs

; Create wallpapers subdirectories
[Dirs]
Name: "{app}\wallpapers"
Name: "{app}\wallpapers\manual"
Name: "{app}\wallpapers\generated"
Name: "{app}\wallpapers\styled"
Name: "{app}\wallpapers\favorites"

[Icons]
Name: "{group}\FrogPaper"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall FrogPaper"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FrogPaper"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\FrogPaper"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FrogPaper"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\wallpapers"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}"

[Code]
procedure InitializeWizard;
begin
  // No custom wizard images - using default Inno Setup wizard
end;
