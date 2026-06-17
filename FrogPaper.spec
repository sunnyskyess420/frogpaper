# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

import os
datas = []
for f, target in [('config.json', '.'), ('keywords.json', '.'), ('negative_presets.json', '.'), ('presets.json', '.'), ('recipes.json', '.'), ('templates.json', '.'), ('prompt_library.json', '.'), ('logs', 'logs')]:
    if os.path.exists(f):
        datas.append((f, target))
# Note: wallpapers folder is not included in EXE - users will save their own images
binaries = []
hiddenimports = ['PIL', 'PIL.Image', 'huggingface_hub', 'sv_ttk', 'darkdetect', 'cv2', 'keyboard']
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('huggingface_hub')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sv_ttk')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cv2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


# Use current directory explicitly
import os
curr_dir = os.path.abspath(os.getcwd())

a = Analysis(
    ['main.py', 'app.py'], # Explicitly include app.py as a script
    pathex=[curr_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    icon='frogpaper.ico',
)
