# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 - outlook-img-slicer"""

import sys
import os

block_cipher = None

UPX_LEVEL = 9  # 最大压缩率

# 收集所有数据文件
datas = []

# hidden imports（PyInstaller 静态分析漏掉的模块）
hiddenimports = [
    "PIL._tkinter_finder",
    "win32com.client",
    "win32api",
    "win32con",
    "win32gui",
    "pywintypes",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
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
        # PyMuPDF 大体积库，如不需要 PDF 功能可取消注释下一行
        # "PyMuPDF",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 单文件模式，Windows 控制台窗口隐藏
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Outlook长图插入工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX 压缩交由 COLLECT 统一处理
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",         # 图标文件
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["PySide6", "PyMuPDF"],  # 避免 Qt/PyMuPDF 被 UPX 压坏
    name="Outlook长图插入工具",
)