# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('config.yaml', '.'), ('src', 'src')],
    hiddenimports=['PIL', 'yaml', 'click', 'rich', 'jinja2', 'zhipuai', 'openai'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_cv2fix.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MaterialReview',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MaterialReview',
)
app = BUNDLE(
    coll,
    name='MaterialReview.app',
    icon=None,
    bundle_identifier=None,
)
