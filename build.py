#!/usr/bin/env python3
"""
Outlook 长图插入工具 — 一键打包脚本
用法: python build.py

依赖:
    pip install pyinstaller

输出:
    dist/Outlook长图插入工具.exe  (单文件)
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

# 当前脚本所在目录
SCRIPT_DIR = Path(__file__).parent.resolve()
DIST_DIR = SCRIPT_DIR / "dist"
BUILD_DIR = SCRIPT_DIR / "build"
SPEC_FILE = SCRIPT_DIR / "outlook_img_slicer.spec"
EXE_NAME = "Outlook长图插入工具"


def log(msg: str):
    print(f"[build] {msg}")


def clean():
    """清理旧的构建产物"""
    log("清理旧构建产物...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            log(f"  已删除: {d}")


def build():
    """执行 PyInstaller 打包"""
    log("开始打包...")
    log(f"  使用 spec: {SPEC_FILE.name}")
    log("  模式: --onefile (单文件)")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--noconsole",   # Windows GUI 程序，隐藏控制台
        "--onefile",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(SCRIPT_DIR),
        str(SPEC_FILE),
    ]

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        log(f"❌ 打包失败 (exit {result.returncode})")
        sys.exit(result.returncode)

    # 定位 EXE
    exe_files = list(DIST_DIR.glob("*.exe"))
    if not exe_files:
        log("❌ 未找到 EXE 文件，打包可能失败")
        sys.exit(1)

    exe_path = exe_files[0]
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    log(f"✅ 打包完成!")
    log(f"   文件: {exe_path}")
    log(f"   大小: {size_mb:.1f} MB")
    log(f"\n📦 交付文件: {exe_path}")
    log("   双击即可运行，无需安装任何依赖!")

    return exe_path


if __name__ == "__main__":
    if not SPEC_FILE.exists():
        log(f"❌ 找不到 spec 文件: {SPEC_FILE}")
        log("请确认在项目根目录运行此脚本")
        sys.exit(1)

    clean()
    exe_path = build()
    print(f"\n{'='*50}")
    print(f"🎉 构建成功!")
    print(f"   {exe_path}")
    print(f"{'='*50}")
