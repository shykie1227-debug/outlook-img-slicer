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
    """
    检查并自动安装缺失依赖。

    离线模式触发条件（任一）：
    - 环境变量 OUTLOOK_SLICER_OFFLINE=1
    - 命令行参数 --offline
    - 环境变量 PIP_NO_INDEX=1 （用户本身就是离线 pip 环境）

    离线模式：检测到缺失依赖则直接报错退出，不尝试 pip install。
    """
    # 检查是否处于离线模式
    offline = (
        os.environ.get("OUTLOOK_SLICER_OFFLINE") == "1"
        or os.environ.get("PIP_NO_INDEX") == "1"
        or "--offline" in sys.argv
    )

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

    if not missing:
        print("[OK] 所有依赖已安装")
        return

    if missing:
        # ── 离线模式：拒绝联网，直接报错退出 ──
        if offline:
            print("\n" + "=" * 60)
            print("  [离线模式] 检测到缺失依赖，但已禁止联网安装。")
            print("=" * 60)
            print(f"\n缺失依赖：{', '.join(missing)}\n")
            print("请在「联网环境」下执行以下命令后重新打包：\n")
            print(f"  pip install {' '.join(missing)} pywin32==306\n")
            print("或者：\n")
            print("  1. 在有网环境下载 wheel 包到本地")
            print("  2. pip install --no-index --find-links=/path/to/wheels ...\n")
            input("按回车键退出...")
            sys.exit(2)  # 2 = 环境错误，与 build 错误区分

        # ── 在线模式：但需警告用户（按原则默认还是不要联网） ──
        print(f"\n⚠️  [警告] 检测到缺失依赖: {', '.join(missing)}")
        print("⚠️  准备调用 pip install —— 这会联网到 PyPI。")
        print("⚠️  如果你遵循「完全不联网」原则，请按 Ctrl+C 取消，")
        print("⚠️  改为手动: pip install " + " ".join(missing) + " pywin32==306")
        print("⚠️  或设置 OUTLOOK_SLICER_OFFLINE=1 走离线模式\n")

        try:
            input("按回车继续安装依赖（或 Ctrl+C 取消）...")
        except KeyboardInterrupt:
            print("\n[取消] 依赖未安装，退出。")
            sys.exit(2)

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