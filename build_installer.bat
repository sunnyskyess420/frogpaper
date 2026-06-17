@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Building FrogPaper Installer...
echo ==========================================

echo.
echo [1/2] Building EXE with PyInstaller...
call build_frogpaper_exe.bat
if errorlevel 1 (
    echo EXE build failed. Cannot continue with installer.
    pause
    exit /b 1
)

echo.
echo [2/2] Building installer with Inno Setup...
echo Using Inno Setup from: C:\Program Files (x86)\Inno Setup 6

echo Compiling installer script...

"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FrogPaperInstaller.iss
if errorlevel 1 (
    echo Installer compilation failed.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Installer created successfully!
echo ==========================================
echo.
echo Installer location: installer_output\FrogPaper-Setup-1.0.0.exe
echo.
echo You can now distribute this installer to users.
echo.
pause
exit /b 0
