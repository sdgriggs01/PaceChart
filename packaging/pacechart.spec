# PyInstaller spec for PaceChart (onedir build: faster startup and fewer
# antivirus false-positives than --onefile; Inno Setup packages the whole
# output folder into one installer anyway, so onedir costs nothing on the
# distribution side).
#
# Build with: pyinstaller packaging/pacechart.spec

import os

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))
src_dir = os.path.join(project_root, "src")

a = Analysis(
    [os.path.join(SPECPATH, "entrypoint.py")],
    pathex=[src_dir],
    binaries=[],
    datas=[
        (os.path.join(src_dir, "pacechart", "assets"), os.path.join("pacechart", "assets")),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PaceChart",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(SPECPATH, "logo.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PaceChart",
)
