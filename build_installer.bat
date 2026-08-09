@echo off
REM Build FrogPaper installer using Inno Setup
REM This creates a professional setup.exe installer for distribution

echo ========================================
echo FrogPaper - Building Installer
echo ========================================
echo.

REM Check if the executable exists
if not exist "dist\FrogPaper.exe" (
    echo ERROR: FrogPaper.exe not found in dist folder!
    echo Please run build_frogpaper_exe.bat first.
    pause
    exit /b 1
)

REM Check if Inno Setup compiler is installed
set "INNO_PATH=C:\Program Files\Inno Setup 7\ISCC.exe"
if exist "%INNO_PATH%" goto :found_inno
set "INNO_PATH=C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
if exist "%INNO_PATH%" goto :found_inno
where iscc >nul 2>&1
if not errorlevel 1 (
    set "INNO_PATH=iscc"
    goto :found_inno
)
echo Inno Setup compiler (iscc.exe) not found.
echo Please install Inno Setup from: https://jrsoftware.org/isdl.php
pause
exit /b 1

:found_inno

echo.
echo Creating installer...
echo.

REM Create output directory if it doesn't exist
if not exist "installer_output" mkdir "installer_output"


REM Create a comprehensive Inno Setup script
(
echo [Setup]
echo AppName=FrogPaper
echo AppVersion=1.1.1
echo AppPublisher=FrogPaper
echo AppPublisherURL=https://github.com/sunnyskyess420/frogpaper
echo AppSupportURL=https://github.com/sunnyskyess420/frogpaper/issues
echo AppUpdatesURL=https://github.com/sunnyskyess420/frogpaper/releases
echo DefaultDirName={userpf}\FrogPaper
echo DefaultGroupName=FrogPaper
echo OutputBaseFilename=FrogPaper-Setup-1.1.1
echo Compression=lzma2
echo SolidCompression=yes
echo WizardStyle=modern
echo WizardImageFile=FrogPaperLogo.bmp
echo WizardSmallImageFile=FrogPaperSmall.bmp
echo SetupIconFile=frogpaper.ico
echo UninstallDisplayIcon={app}\frogpaper.ico
echo CreateAppDir=yes
echo OutputDir=installer_output
echo UsePreviousAppDir=no
echo DirExistsWarning=no
echo AppendDefaultDirName=no
echo PrivilegesRequired=lowest
echo.
echo [Languages]
echo Name: "english"; MessagesFile: "compiler:Default.isl"
echo.
echo [Tasks]
echo Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"
echo Name: "quicklaunchicon"; Description: "Create a Quick Launch icon"; GroupDescription: "Additional icons:"; Flags: unchecked
echo Name: "startup"; Description: "Run FrogPaper at Windows startup"; GroupDescription: "Startup options:"
echo.
echo [Files]
echo Source: "dist\FrogPaper.exe"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "sounds\*"; DestDir: "{app}\sounds"; Flags: ignoreversion recursesubdirs createallsubdirs
echo Source: "frogpaper.ico"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "FrogPaperLogo.png"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "FrogPaperLogo.bmp"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "FrogPaperSmall.bmp"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "sidebar_logo.png"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "keywords.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "presets.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "presets.json.bak"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "gallery_tags.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "gallery_tags.json.bak"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "negative_presets.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "recipes.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "prompt_library.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "prompt_library.json.bak"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "templates.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "user_thesaurus.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "user_thesaurus.json.bak"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo Source: "keyword_expansion.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
echo.
echo [Dirs]
echo Name: "{app}\wallpapers"
echo Name: "{app}\logs"
echo.
echo [Icons]
echo Name: "{group}\FrogPaper"; Filename: "{app}\FrogPaper.exe"; IconFilename: "{app}\frogpaper.ico"
echo Name: "{group}\Uninstall FrogPaper"; Filename: "{uninstallexe}"
echo Name: "{autodesktop}\FrogPaper"; Filename: "{app}\FrogPaper.exe"; IconFilename: "{app}\frogpaper.ico"; Tasks: desktopicon
echo Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\FrogPaper"; Filename: "{app}\FrogPaper.exe"; Tasks: quicklaunchicon
echo.
echo [Registry]
echo ; Add to startup registry if selected
echo Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FrogPaper"; ValueData: """{app}\FrogPaper.exe"""; Tasks: startup; Flags: uninsdeletevalue
echo.
echo [Run]
echo Filename: "{app}\FrogPaper.exe"; Description: "Launch FrogPaper"; Flags: nowait postinstall skipifsilent
echo.
echo [UninstallDelete]
echo Type: filesandordirs; Name: "{app}\__pycache__"
echo Type: filesandordirs; Name: "{app}\wallpapers\manual"
echo Type: filesandordirs; Name: "{app}\wallpapers\generated"
echo Type: filesandordirs; Name: "{app}\wallpapers\styled"
echo Type: filesandordirs; Name: "{app}\wallpapers\favorites"
) > frogpaper_installer.iss

REM Compile the installer
"%INNO_PATH%" frogpaper_installer.iss

if errorlevel 1 (
    echo.
    echo ERROR: Installer build failed!
    if exist frogpaper_installer.iss del frogpaper_installer.iss
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

REM Clean up temporary script
if exist frogpaper_installer.iss del frogpaper_installer.iss

echo.
echo ========================================
echo Installer created successfully!
echo ========================================
echo.
echo Installer location: installer_output\FrogPaper-Setup-1.1.1.exe
echo.
echo Press any key to exit...
pause >nul
