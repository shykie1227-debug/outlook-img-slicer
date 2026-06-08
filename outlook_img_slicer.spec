# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 - outlook-img-slicer V4.0.20260513
真正的单文件模式（--onefile），优化体积
"""
import sys
import os

block_cipher = None
UPX_LEVEL = 9

hiddenimports = [
    "PIL._tkinter_finder",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
    "win32com.client",
    "win32api",
    "win32con",
    "win32gui",
    "pywintypes",
    "pythoncom",
    "PIL",
    "fitz",
    # PPT/PPTX 支持（PyMuPDF 原生支持 PPTX，无需额外依赖）
    "ppt_slicer",
    # python-pptx（PPT 渲染备用，无 office 环境也能提取嵌入图片）
    "pptx",
    "lxml",
    # V4 新增模块
    "image_safety",
    "html_assembler",
    # V4.6 新增：PSD 支持（psd-tools 依赖 numpy）
    "psd_slicer",
    "psd_tools",
    "psd_tools.api.psd_image",
    "psd_tools.api.pil_io",
    "psd_tools.api.layers",
    "numpy",
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
        "scipy",
        "pandas",
        "jupyter",
        "test",
        "unittest",
        "IPython",
        "notebook",
        "jax",
        "torch",
        "tensorflow",
        # numpy 不再排除：psd-tools 内部依赖
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 单文件 EXE：所有依赖打包进一个 exe
# Windows 环境默认没有类 Unix strip 工具；开启会产生大量 FileNotFoundError 警告。
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    exclude_binaries=False,
    name="Outlook长图插入工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=UPX_LEVEL > 0,
    upx_args=["--best"] if UPX_LEVEL > 0 else [],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)
