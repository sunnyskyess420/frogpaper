# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('sounds', 'sounds'),
        ('frogpaper.ico', '.'),
        ('FrogPaperLogo.png', '.'),
        ('config.json', '.'),
        ('keywords.json', '.'),
        ('presets.json', '.'),
        ('gallery_tags.json', '.'),
        ('negative_presets.json', '.'),
        ('recipes.json', '.'),
        ('prompt_library.json', '.'),
        ('templates.json', '.'),
        ('user_thesaurus.json', '.'),
        ('keyword_expansion.json', '.'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'nltk',
        'sentence_transformers',
        'huggingface_hub',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
