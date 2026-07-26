@echo off
REM Build FrogPaper installer using Inno Setup
REM This creates a setup.exe installer for distribution

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
where iscc >nul 2>&1
if errorlevel 1 (
    echo Inno Setup compiler (iscc.exe) not found in PATH.
    echo Please install Inno Setup from: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo.
echo Creating installer...
echo.

REM Create a temporary Inno Setup script
(
echo [Setup]
echo AppName=FrogPaper
echo AppVersion=1.0
echo DefaultDirName={commonpf}\FrogPaper
echo DefaultGroupName=FrogPaper
echo OutputBaseFilename=FrogPaper-Setup
echo Compression=lzma
echo SolidCompression=yes
echo WizardStyle=modern
echo.
echo [Files]
echo Source: "dist\FrogPaper.exe"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "sounds\*"; DestDir: "{app}\sounds"; Flags: ignoreversion recursesubdirs createallsubdirs
echo Source: "frogpaper.ico"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "FrogPaperLogo.png"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "keywords.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "presets.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "gallery_tags.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "negative_presets.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "recipes.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "prompt_library.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "templates.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "user_thesaurus.json"; DestDir: "{app}"; Flags: ignoreversion
echo Source: "keyword_expansion.json"; DestDir: "{app}"; Flags: ignoreversion
echo.
echo [Icons]
echo Name: "{group}\FrogPaper"; Filename: "{app}\FrogPaper.exe"
echo Name: "{commondesktop}\FrogPaper"; Filename: "{app}\FrogPaper.exe"
echo.
echo [Run]
echo Filename: "{app}\FrogPaper.exe"; Description: "Launch FrogPaper"; Flags: nowait postinstall skipifsilent
) > frogpaper_installer.iss

REM Compile the installer
iscc frogpaper_installer.iss

if errorlevel 1 (
    echo.
    echo ERROR: Installer build failed!
    del frogpaper_installer.iss
    pause
    exit /b 1
)

REM Clean up temporary script
del frogpaper_installer.iss

echo.
echo ========================================
echo Installer created successfully!
echo ========================================
echo.
echo Installer location: Output\FrogPaper-Setup.exe
echo.
pause
