# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PathCUT (onedir, windowed)."""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ezdxf ships template DXF files and other data that must be bundled.
ezdxf_datas = collect_data_files("ezdxf")

a = Analysis(
    ["src/plate_nesting/gui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=ezdxf_datas + [("pathcut.ico", ".")],
    hiddenimports=collect_submodules("plate_nesting"),
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
    name="PathCUT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # windowed app — no terminal
    disable_windowed_traceback=False,
    icon="pathcut.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PathCUT",
)
