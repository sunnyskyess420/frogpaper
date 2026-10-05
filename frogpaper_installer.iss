[Setup]
AppName=FrogPaper
AppVersion=1.6.0
AppPublisher=FrogPaper
AppPublisherURL=https://github.com/sunnyskyess420/frogpaper
AppSupportURL=https://github.com/sunnyskyess420/frogpaper/issues
AppUpdatesURL=https://github.com/sunnyskyess420/frogpaper/releases
DefaultDirName={userpf}\FrogPaper
DefaultGroupName=FrogPaper
OutputBaseFilename=FrogPaper-Setup-1.6.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardImageFile=FrogPaperLogo.bmp
WizardSmallImageFile=FrogPaperSmall.bmp
SetupIconFile=frogpaper.ico
UninstallDisplayIcon={app}\frogpaper.ico
CreateAppDir=yes
OutputDir=installer_output
UsePreviousAppDir=no
DirExistsWarning=no
AppendDefaultDirName=no
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"
Name: "quicklaunchicon"; Description: "Create a Quick Launch icon"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "startup"; Description: "Run FrogPaper at Windows startup"; GroupDescription: "Startup options:"

[Files]
Source: "dist\FrogPaper.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "sounds\*"; DestDir: "{app}\sounds"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "frogpaper.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "FrogPaperLogo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "FrogPaperLogo.bmp"; DestDir: "{app}"; Flags: ignoreversion
Source: "FrogPaperSmall.bmp"; DestDir: "{app}"; Flags: ignoreversion
Source: "sidebar_logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.template.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist
Source: "keywords.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "presets.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "negative_presets.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "recipes.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "prompt_library.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "templates.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "user_thesaurus.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Dirs]
Name: "{app}\wallpapers"
Name: "{app}\logs"

[Icons]
Name: "{group}\FrogPaper"; Filename: "{app}\FrogPaper.exe"; IconFilename: "{app}\frogpaper.ico"
Name: "{group}\Uninstall FrogPaper"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FrogPaper"; Filename: "{app}\FrogPaper.exe"; IconFilename: "{app}\frogpaper.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\FrogPaper"; Filename: "{app}\FrogPaper.exe"; Tasks: quicklaunchicon

[Registry]
; Add to startup registry if selected
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FrogPaper"; ValueData: """{app}\FrogPaper.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\FrogPaper.exe"; Description: "Launch FrogPaper"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\wallpapers\manual"
Type: filesandordirs; Name: "{app}\wallpapers\generated"
Type: filesandordirs; Name: "{app}\wallpapers\styled"
Type: filesandordirs; Name: "{app}\wallpapers\favorites"
