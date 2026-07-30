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

### Step 2: Build the Installer
Then, create the installer:
```cmd
build_installer.bat
```

This will create `installer_output\FrogPaper-Setup-1.0.2.exe`

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

1. Run the installer: `installer_output\FrogPaper-Setup-1.0.2.exe`
2. Choose installation options (desktop icon, startup, etc.)
3. After installation, test the "Run on startup" setting in FrogPaper settings
4. Restart your computer to verify startup functionality
5. Test uninstall via Control Panel or Start Menu

## Website Integration

After building and testing the installer:

1. **Upload the installer** to GitHub releases:
   ```cmd
   gh release upload v1.0.2 installer_output\FrogPaper-Setup-1.0.2.exe --repo sunnyskyess420/frogpaper
   ```

2. **Update your website** download button to point to the installer:
   - Change the download link from `FrogPaper.exe` to `FrogPaper-Setup-1.0.2.exe`
   - Update the file size and description
   - Add a note about the installer providing automatic startup options

3. **Keep the EXE available** for advanced users who prefer portable installation

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