# PyInstaller spec: onedir app bundle without PySide6 (runtime installed separately on Windows).
# PySide6 must be installed in the build venv for import analysis, but is excluded from COLLECT output.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

project_root = Path(SPECPATH)

datas = [
    (str(project_root / "locales"), "locales"),
    (str(project_root / "assets"), "assets"),
]

# PySide6 is loaded from an external runtime directory at launch (see src/runtime_paths.py).
_pyside6_excludes = [
    "PySide6",
    "shiboken6",
    "PySide6_Essentials",
    "PySide6_Addons",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("src") + collect_submodules("yt_dlp"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_pyside6_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_icon = project_root / "assets" / "icon.ico"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yt-dlp-gui",
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
    icon=str(_icon) if _icon.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="yt-dlp-gui",
)
