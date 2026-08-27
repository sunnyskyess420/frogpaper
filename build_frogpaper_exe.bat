@echo off
REM Build FrogPaper executable using PyInstaller
REM This creates a standalone .exe file that can be distributed

echo ========================================
echo FrogPaper - Building Executable
echo ========================================
echo.

REM Clean up old build artifacts to prevent caching issues
echo Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
echo Cleanup complete.
echo.

REM Clean PyInstaller cache in temp directory
echo Cleaning PyInstaller cache...
for /d %%i in ("%TEMP%\PyInstaller\*") do rmdir /s /q "%%i" 2>nul
echo PyInstaller cache cleaned.
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    python -m pip install pyinstaller
)

echo.
echo ========================================
echo Pre-build security check
echo ========================================
echo Verifying config.json / config.template.json do not contain real
echo HuggingFace / Google / Dropbox / OneDrive secrets before packing...
python prebuild_check.py
if errorlevel 1 (
    echo.
    echo ERROR: Pre-build check failed. ABORTING build to prevent
    echo        secrets from being baked into FrogPaper.exe.
    echo.
    pause
    exit /b 2
)
echo Pre-build check passed.
echo.

echo.
echo Building FrogPaper.exe...
echo This may take a few minutes...
echo.

REM Build the executable using the spec file
REM NOTE: invoke through "python -m" so we always use the same Python that ran
REM the checks above -- avoids 'pyinstaller is not recognized' when the
REM Scripts folder is not on PATH.
python -m PyInstaller --clean FrogPaper.spec

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
