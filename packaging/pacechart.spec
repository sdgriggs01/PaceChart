# PyInstaller spec for PaceChart (onedir build: faster startup and fewer
# antivirus false-positives than --onefile; onedir also builds straight
# into the platform-native install format -- Inno Setup on Windows, a
# .app bundle on macOS -- so it costs nothing on the distribution side).
#
# Build with: pyinstaller packaging/pacechart.spec
# Run on the target platform: this is not a cross-compiler. A Windows
# build must run on Windows, a macOS build on macOS, a Linux build on
# Linux -- see .github/workflows/build-installer.yml for the 3-way matrix.

import os
import sys

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))
src_dir = os.path.join(project_root, "src")

if sys.platform == "win32":
    icon_path = os.path.join(SPECPATH, "logo.ico")
elif sys.platform == "darwin":
    icon_path = os.path.join(SPECPATH, "logo.icns")
else:
    # No standard icon format for a raw Linux binary; the .desktop file
    # installed alongside it (packaging/linux/) points at logo.png instead.
    icon_path = None

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
    icon=icon_path,
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

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PaceChart.app",
        icon=icon_path,
        bundle_identifier="com.simongriggs.pacechart",
        info_plist={
            "CFBundleShortVersionString": os.environ.get("PACECHART_VERSION", "0.0.0"),
            "NSHighResolutionCapable": True,
        },
    )
