#!/usr/bin/env python3
"""
build.py - Outlook 长图插入工具 V3 一键打包脚本
用法: python build.py
依赖: pip install pyinstaller Pillow PyMuPDF PySide6 pywin32==306
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"


def run(cmd: list, **kwargs):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}")
        sys.exit(result.returncode)
    return result


def check_and_install_deps():
    """检查并自动安装缺失依赖"""
    import_to_pip = {
        "PyInstaller": "pyinstaller",
        "PIL": "Pillow",
        "fitz": "PyMuPDF",
        "pymupdf": "PyMuPDF",
        "PySide6": "PySide6",
    }
    required = list(import_to_pip.keys())
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(import_to_pip[pkg])

    if missing:
        print(f"[INFO] 检测到缺失依赖: {', '.join(missing)}")
        print("[INFO] 正在自动安装...")
        pip_pkgs = missing + ["pywin32==306"]
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + pip_pkgs,
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[ERROR] 自动安装失败，请手动运行：")
            print(f"  pip install {' '.join(pip_pkgs)}")
            sys.exit(1)
        print("[INFO] 依赖安装完成！")


def build_spec(spec_file: str):
    """用 PyInstaller 分析 spec 文件并构建"""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_file),
    ]
    run(cmd, cwd=PROJECT_ROOT)


def create_onedir_fallback():
    """
    如果 --onefile 打包失败（dll 依赖问题），切换到 --onedir
    """
    print("\n[FALLBACK] 切换到 --onedir 模式...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir",
        "--name=Outlook长图插入工具",
        "--add-binary=.;.",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=shiboken6",
        "--hidden-import=win32com.client",
        "--hidden-import=win32api",
        "--hidden-import=win32con",
        "--hidden-import=win32gui",
        "--hidden-import=pywintypes",
        "--hidden-import=pythoncom",
        "--icon=icon.ico",
        "--console=False",
        "main.py",
    ]
    run(cmd, cwd=PROJECT_ROOT)


def main():
    print("=== Outlook 长图插入工具 V3 打包脚本 ===")
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"Python: {sys.version}")

    check_and_install_deps()

    # 清理旧构建
    build_dir = PROJECT_ROOT / "build"
    dist_dir = PROJECT_ROOT / "dist"
    for d in [build_dir, dist_dir]:
        if d.exists():
            print(f"\n清理旧构建: {d}")
            shutil.rmtree(d)

    spec_file = PROJECT_ROOT / "outlook_img_slicer.spec"
    if not spec_file.exists():
        print(f"[ERROR] spec 文件不存在: {spec_file}")
        sys.exit(1)

    print("\n开始构建（--onefile 模式）...")
    build_spec(spec_file)

    # 检查产物
    exe_path = dist_dir / "Outlook长图插入工具.exe"
    onedir_exe = dist_dir / "Outlook长图插入工具" / "Outlook长图插入工具.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ 单文件 EXE 生成成功: {exe_path}")
        print(f"   文件大小: {size_mb:.1f} MB")
    elif onedir_exe.exists():
        print(f"\n✅ ONEDIR EXE 生成成功: {onedir_exe.parent}")
    else:
        print("\n⚠️ 未找到 EXE，尝试 --onedir 模式...")
        create_onedir_fallback()

    print("\n打包完成！")
    print(f"产物目录: {dist_dir}")


if __name__ == "__main__":
    main()
