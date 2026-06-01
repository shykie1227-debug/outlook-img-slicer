#!/usr/bin/env python3
"""
build.py - Outlook 长图插入工具 V3 一键打包脚本
用法: python build.py
依赖: pip install pyinstaller Pillow PyMuPDF PySide6 pywin32==306 python-pptx lxml
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
        if result.stdout:
            print("STDOUT:", result.stdout[-2000:])
        if result.stderr:
            print("STDERR:", result.stderr[-2000:])
        input("\n按回车键退出...")
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
        "pptx": "python-pptx",
        "psd_tools": "psd-tools",
        "numpy": "numpy",
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
            print(f"[ERROR] 自动安装失败:")
            print(result.stdout[-2000:])
            print(result.stderr[-2000:])
            input("\n按回车键退出...")
            sys.exit(1)
        print("[INFO] 依赖安装完成！")
    else:
        print("[OK] 所有依赖已安装")


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
    """如果 --onefile 打包失败，切换到 --onedir"""
    print("\n[FALLBACK] 切换到 --onedir 模式...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir",
        "--name=Outlook长图插入工具",
        "--icon=icon.ico",
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
        input("\n按回车键退出...")
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
    input("\n按回车键退出...")


if __name__ == "__main__":
    main()