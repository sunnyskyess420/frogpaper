@echo off
REM Build FrogPaper executable using PyInstaller
REM
REM SECURITY RELEASE NOTE (v1.7.6): This script now builds FrogPaper.exe from
REM a clean, manifest-driven virtual environment instead of whatever Python
REM packages happen to be installed on the developer's machine. This closes
REM the "build env differs from requirements.txt" gap that previously allowed
REM a vulnerable Pillow to ship in the EXE even after requirements.txt was
REM pinned to a patched version.
REM
REM Behaviour:
REM   1. Verifies the developer's Python is 3.11+ (Pillow 13 requires it).
REM   2. Creates a clean .venv-build in the repo root (reused on subsequent
REM      runs unless --recreate-venv is passed or the venv is missing).
REM   3. Installs requirements.txt into the venv with --upgrade-pip.
REM   4. Runs prebuild_check.py to verify no real secrets are baked in.
REM   5. Invokes PyInstaller via `python -m PyInstaller --clean FrogPaper.spec`
REM      so the same venv's Python that installed deps also drives the build.
REM
REM Usage:
REM   build_frogpaper_exe.bat                  Standard build
REM   build_frogpaper_exe.bat --recreate-venv  Throw away .venv-build first
REM
REM Exit codes:
REM   0  build succeeded
REM   1  PyInstaller build failed
REM   2  pre-build security check failed (secrets present)
REM   3  Python not found or wrong version

setlocal enableDelayedExpansion

echo ========================================
echo FrogPaper - Building Executable
echo ========================================
echo.

REM --- Parse args ---
set "RECREATE_VENV=0"
if /i "%~1"=="--recreate-venv" set "RECREATE_VENV=1"

REM --- Locate a usable Python (3.11+) ---
REM Prefer "python", fall back to "py -3.12", then "py -3.11".
set "PY_CMD=python"
where %PY_CMD% >nul 2>&1
if errorlevel 1 (
    set "PY_CMD=py -3.12"
    where py >nul 2>&1
    if errorlevel 1 (
        set "PY_CMD=py -3.11"
    )
)

echo Verifying Python version (3.11+ required)...
%PY_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.11 or newer is required. Pillow 13 dropped
    echo        Python 3.10 support, so the build cannot proceed.
    echo        Install Python 3.11+ from https://www.python.org/downloads/
    echo        and make sure it is on PATH.
    pause
    exit /b 3
)
echo Python version OK.
echo.

REM --- Clean up old PyInstaller build artifacts (NOT the venv) ---
echo Cleaning old build outputs...
if exist build rmdir /s /q build
REM Never delete dist itself: an older EXE kept user data beside it
REM (config.json with API keys, wallpapers, logs, frogpaper.db) and
REM rmdir /s destroyed all of it. Remove only the previous build.
if exist "dist\FrogPaper.exe" del /q "dist\FrogPaper.exe"
if exist "dist\_internal" rmdir /s /q "dist\_internal"
if exist __pycache__ rmdir /s /q __pycache__
for /d %%i in ("%TEMP%\PyInstaller\*") do rmdir /s /q "%%i" 2>nul
echo Cleanup complete.
echo.

REM --- Create or recreate the build venv ---
set "VENV_DIR=.venv-build"
if "%RECREATE_VENV%"=="1" (
    echo Recreating .venv-build as requested...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
)
if not exist "%VENV_DIR%" (
    echo Creating clean build venv at %VENV_DIR%...
    %PY_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo ERROR: venv creation failed.
        pause
        exit /b 3
    )
)
echo.

REM --- Install requirements.txt into the venv ---
echo Installing requirements.txt into the build venv...
echo This may take a few minutes the first time (Pillow 13 + sentence-transformers
echo pulls torch ~2-3 GB if you let it; CI skips sentence-transformers via a lean
echo install, but the EXE needs the full set for hiddenimports to resolve).
echo.
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo ERROR: pip self-upgrade failed.
    pause
    exit /b 3
)
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: requirements.txt installation failed. Cannot continue.
    echo        Fix the install errors above before re-running this script.
    pause
    exit /b 3
)
echo.

REM --- Sanity-check the venv has the security-pinned versions ---
echo Verifying venv dependency versions match the security pins...
"%VENV_DIR%\Scripts\python.exe" -c "import sys, pkg_resources; data=[(d.project_name, d.version) for d in pkg_resources.working_set if d.project_name.lower() in ('pillow','nltk','opencv-python','pyinstaller')]; [print(f'{n}=={v}') for n,v in sorted(data)]; pillow_ver=[v for n,v in data if n.lower()=='pillow'][0]; sys.exit(0 if pillow_ver=='13.0.0' else 1)"
if errorlevel 1 (
    echo.
    echo ERROR: Pillow in the build venv is NOT 13.0.0.
    echo        The build is unsafe to ship. Aborting.
    echo        Check requirements.txt and re-run with --recreate-venv.
    pause
    exit /b 3
)
echo.

REM --- Pre-build security check (no real secrets baked in) ---
echo ========================================
echo Pre-build security check
echo ========================================
echo Verifying config.json / config.template.json do not contain real
echo HuggingFace / Google / Dropbox / OneDrive secrets before packing...
"%VENV_DIR%\Scripts\python.exe" prebuild_check.py
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

REM --- Build the EXE using the venv's Python so the bundled deps match
REM     requirements.txt exactly. ---
echo ========================================
echo Building FrogPaper.exe with PyInstaller
echo ========================================
echo This may take a few minutes...
echo.
"%VENV_DIR%\Scripts\python.exe" -m PyInstaller --clean FrogPaper.spec
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
echo VERIFY before shipping (recommended):
echo   1. Run dist\FrogPaper.exe once and confirm it starts cleanly.
echo   2. Confirm the bundled Pillow version is 13.0.0:
echo      "%VENV_DIR%\Scripts\python.exe" -c "import sys, pkgutil; print('Pillow', pkgutil.get_loader('PIL').get_filename() if hasattr(pkgutil.get_loader('PIL'), 'get_filename') else 'n/a')"
echo      Or extract the EXE with pyinstxtractor and inspect the
echo      Pillow-13.0.0.dist-info folder inside _internal.
echo.
pause
