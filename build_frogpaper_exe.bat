@echo off
REM Build FrogPaper executable using PyInstaller
REM This creates a standalone .exe file that can be distributed

echo ========================================
echo FrogPaper - Building Executable
echo ========================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo.
echo Building FrogPaper.exe...
echo This may take a few minutes...
echo.

REM Build the executable
pyinstaller --onefile --windowed --name FrogPaper --icon=frogpaper.ico --add-data "sounds;sounds" --add-data "frogpaper.ico;." --add-data "FrogPaperLogo.png;." --hidden-import=PIL._tkinter_finder app.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Executable location: dist\FrogPaper.exe
echo.
echo To test the executable:
echo   cd dist
echo   FrogPaper.exe
echo.
pause
