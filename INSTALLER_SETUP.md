# FrogPaper Installer Setup Guide

## Prerequisites

### 1. Install Inno Setup
Download and install Inno Setup from: https://jrsoftware.org/isdl.php

- Download the "QuickStart Pack" for the easiest installation
- During installation, make sure to add Inno Setup to your system PATH
- After installation, restart your command prompt/terminal

### 2. Verify Installation
Open a command prompt and run:
```cmd
iscc
```
You should see the Inno Setup compiler help output.

## Building the Installer

### Step 1: Build the EXE
First, build the main FrogPaper executable:
```cmd
build_frogpaper_exe.bat
```

This will create `dist\FrogPaper.exe` using PyInstaller.

> **Note**: `build_frogpaper_exe.bat` automatically runs `prebuild_check.py`
> before packing the EXE. If any non-empty API token or OAuth secret is found
> in `config.json` or `config.template.json`, the build aborts with exit code 2.
> See `SECURITY_NOTES.md` for details.

### Step 2: Build the Installer
Then, create the installer:
```cmd
build_installer.bat
```

This will create `installer_output\FrogPaper-Setup-1.7.0.exe`

## Installer Features

The new installer includes:

- **Professional installation wizard** with FrogPaper branding
- **Program Files installation** to `C:\Program Files\FrogPaper`
- **Desktop shortcut** (optional)
- **Quick Launch shortcut** (optional)
- **Windows startup option** (optional) - adds FrogPaper to startup registry
- **Start Menu shortcuts** with uninstaller
- **Automatic data file preservation** - won't overwrite existing config files
- **Clean uninstall** - removes app but preserves user data in separate folders

## Windows Startup Fix

The Windows startup functionality has been improved:

1. **Better path handling** - Uses absolute paths with quotes for spaces
2. **Improved logging** - Shows exactly what path is being registered
3. **Status feedback** - Clear messages when enabling/disabling startup
4. **Registry management** - Properly handles updates and removals

## Testing the Installer

1. Run the installer: `installer_output\FrogPaper-Setup-1.7.0.exe`
2. Choose installation options (desktop icon, startup, etc.)
3. After installation, test the "Run on startup" setting in FrogPaper settings
4. Restart your computer to verify startup functionality
5. Test uninstall via Control Panel or Start Menu

## Website Integration

After building and testing the installer:

1. **Upload the installer** to GitHub releases:
   ```cmd
   gh release upload v1.7.0 installer_output\FrogPaper-Setup-1.7.0.exe --repo sunnyskyess420/frogpaper
   ```

2. **Update your website** download button to point to the installer:
   - Change the download link from `FrogPaper.exe` to `FrogPaper-Setup-1.7.0.exe`
   - Update the file size and description
   - Add a note about the installer providing automatic startup options

3. **Keep the EXE available** for advanced users who prefer portable installation

## In-App One-Click Updates

The update popup no longer just opens a browser. When a newer release is
found, clicking **Install Update** makes FrogPaper:

1. Stream the installer `.exe` straight from the GitHub release (with a themed,
   cancellable progress window).
2. Ask to close FrogPaper and hand off to the installer.
3. Launch the installer *after* FrogPaper exits — so it can replace the running
   `FrogPaper.exe` cleanly without a "file in use" prompt.

If the release has no direct installer asset, or the download fails, FrogPaper
warns the user and falls back to opening the download page.

### Requirements for one-click updates to work

- **Attach the installer as a release asset named with `Setup`** (e.g.
  `FrogPaper-Setup-1.7.0.exe`). This matches the same file the website links to.
  Do **not** zip it — the asset must be the raw `.exe`.
- **Bump `APP_VERSION` in `app.py`, `AppVersion` in `build_installer.bat`,
  `OutputBaseFilename`, and the GitHub release tag to the same version.** The
  automatic popup only appears when the release tag is strictly newer than
  `APP_VERSION`.

> Note: automatic install is offered only for the packaged EXE. Running from
> source (`python app.py`) opens the download page instead, since installing the
> EXE wouldn't update the source tree.

## Troubleshooting

### Inno Setup not found
- Make sure Inno Setup is installed
- Add it to your PATH or use the full path to `iscc.exe`
- Restart your command prompt after installation

### Build fails
- Ensure `dist\FrogPaper.exe` exists first
- Check that all required files (icons, images, JSON files) are present
- Review the error message for specific issues

### Startup not working
- Check Windows Task Manager > Startup tab
- Verify the registry entry: `regedit` > `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
- Check FrogPaper logs for startup-related errors
- Ensure the installed path is correct

## Files Modified

- `app.py` - Improved Windows startup registry handling
- `build_installer.bat` - Enhanced installer script with more options
- `FrogPaper.spec` - Added backup JSON files to the build
- `.gitignore` - Ensured database files are excluded from git