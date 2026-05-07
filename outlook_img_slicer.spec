# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 - outlook-img-slicer
V3: 单文件模式 (--onefile)
"""
import sys
import os

block_cipher = None

# hidden imports（PyInstaller 静态分析漏掉的模块）
hiddenimports = [
    "PIL._tkinter_finder",
    "win32com.client",
    "win32com.util",
    "win32api",
    "win32con",
    "win32gui",
    "win32print",
    "pywintypes",
    "pythoncom",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "jupyter",
        "test",
        "tests",
        "unittest",
        "doctest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ============================================================
# 单文件模式 (--onefile)：所有依赖打包进一个 EXE
# ============================================================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Outlook长图插入工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=["PySide6"],   # Qt 库不推荐 UPX 压缩
    console=False,             # 隐藏控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)
