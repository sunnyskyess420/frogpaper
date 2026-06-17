@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Building FrogPaper EXE with PyInstaller...
echo ==========================================

echo.
echo [1/5] Installing build tools...
py -m pip install --upgrade pip pyinstaller huggingface_hub Pillow sv_ttk darkdetect opencv-python keyboard
if errorlevel 1 goto :fail

echo.
echo [2/5] Cleaning old build folders and preparing assets...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Clear PyInstaller system cache to prevent bundling old versions
if exist "%APPDATA%\pyinstaller" (
    echo Clearing PyInstaller system cache...
    rmdir /s /q "%APPDATA%\pyinstaller"
)

:: Clear __pycache__ folders
echo Clearing Python bytecode cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
if not exist config.json echo {} > config.json
if not exist keywords.json echo [] > keywords.json
if not exist negative_presets.json echo [] > negative_presets.json
if not exist presets.json echo [] > presets.json
if not exist recipes.json echo [] > recipes.json
if not exist templates.json echo [] > templates.json
if not exist prompt_library.json echo [] > prompt_library.json
if not exist wallpapers mkdir wallpapers
if not exist logs mkdir logs

echo.
echo [3/5] Building EXE...
echo Note: Using FrogPaper.spec for build configuration.
py -m PyInstaller --noconfirm --clean FrogPaper.spec
if errorlevel 1 goto :fail

echo.
echo [4/5] Build complete.
echo EXE created at:
echo dist\FrogPaper.exe

echo.
echo [5/5] First-run note:
echo Run the new EXE from the dist folder first to test it.
echo If your token changes later, keep config.json beside the EXE or rebuild.

echo.
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1