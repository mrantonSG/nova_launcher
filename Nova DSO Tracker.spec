# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['nova_manager.py'],
    pathex=[],
    binaries=[],
    datas=[('nova_logo.png', '.')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='Nova DSO Tracker',
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
    icon=['nova_logo.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Nova DSO Tracker',
)
app = BUNDLE(
    coll,
    name='Nova DSO Tracker.app',
    icon='nova_logo.icns',
    bundle_identifier='com.mrantonsg.nova-dso-tracker',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1',
        'NSHighResolutionCapable': 'True',
        'NSHumanReadableCopyright': 'Copyright © 2026 mrantonsg. https://nova-tracker.com'
    },
)
