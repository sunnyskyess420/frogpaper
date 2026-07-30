# -*- mode: python ; coding: utf-8 -*-
import sys
import os

# Add current directory to path so modules can be found
sys.path.insert(0, os.getcwd())

# Collect all local .py modules to ensure they're included
import glob
py_files = [(f, '.') for f in glob.glob('*.py') if f != 'app.py']

a = Analysis(
    ['app.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[('sounds', 'sounds'), ('frogpaper.ico', '.'), ('FrogPaperLogo.png', '.'), ('sidebar_logo.png', '.'), ('config.json', '.'), ('keywords.json', '.'), ('presets.json', '.'), ('gallery_tags.json', '.'), ('negative_presets.json', '.'), ('recipes.json', '.'), ('prompt_library.json', '.'), ('templates.json', '.'), ('user_thesaurus.json', '.'), ('keyword_expansion.json', '.')] + py_files,
    hiddenimports=['PIL._tkinter_finder', 'theme_mixer', 'prompt_builder', 'slideshow', 'keyword_expander', 'gallery_manager', 'preset_manager', 'utils', 'setup_scheduler', 'session_manager', 'tray_manager', 'settings_tab', 'prompt_tab', 'gallery_tab', 'set_wallpaper', 'database', 'icons', 'negative_manager', 'prompt_validator', 'style_transfer', 'wallpaper_generator', 'ui_effects', 'nltk', 'sentence_transformers', 'huggingface_hub', 'torch', 'transformers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FrogPaper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['frogpaper.ico'],
)
