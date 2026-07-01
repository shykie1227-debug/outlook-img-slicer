#!/usr/bin/env python3
"""
build_v6.py - Outlook 长图助手 V6 一键打包脚本（Windows）
用法: python build_v6.py
依赖:
  1. Node.js 18+ (npm)
  2. Python 3.10+ (pip)
  3. PyInstaller (pip install pyinstaller)

构建流程:
  1. 安装 Node.js 依赖
  2. 构建 React 渲染进程 (app/dist)
  3. 构建 Electron 主进程 (electron/dist-electron)
  4. 使用 PyInstaller 打包 Python Sidecar (sidecar/dist)
  5. 使用 electron-builder 打包为 Windows EXE (release-artifacts/electron)

输出:
  release-artifacts/electron/Outlook 长图助手-V6.0.0-Setup.exe
"""
import subprocess
import sys
import os
import shutil
import json
import stat
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def pause_before_exit():
    if sys.stdin is not None and sys.stdin.isatty():
        input("\n按回车键退出...")


def find_executable(name):
    if sys.platform == "win32":
        name = name + ".exe"
    for path in os.environ["PATH"].split(os.pathsep):
        full_path = os.path.join(path, name)
        if os.path.exists(full_path):
            return full_path
    return None


def find_node_and_npm():
    node_path = None
    npm_path = None

    common_node_paths = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "nodejs", "node.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", "node", "bin", "node.exe"),
    ]

    for path in common_node_paths:
        if os.path.exists(path):
            node_path = path
            break

    if not node_path:
        node_path = find_executable("node")

    if not node_path:
        print("[ERROR] 未找到 Node.js，请先安装 Node.js 18+")
        print("        下载地址: https://nodejs.org/")
        print("        安装时请勾选 'Add to PATH'")
        return None, None

    try:
        result = subprocess.run([node_path, "--version"], capture_output=True, text=True)
        print(f"[OK] Node.js: {result.stdout.strip()} ({node_path})")
    except Exception as e:
        print(f"[ERROR] 无法执行 Node.js: {e}")
        return None, None

    npm_path = find_executable("npm")

    if not npm_path:
        node_dir = os.path.dirname(node_path)
        npm_candidates = [
            os.path.join(node_dir, "npm.cmd"),
            os.path.join(node_dir, "npm"),
        ]
        for candidate in npm_candidates:
            if os.path.exists(candidate):
                npm_path = candidate
                break

    if npm_path:
        try:
            result = subprocess.run([npm_path, "--version"], capture_output=True, text=True)
            print(f"[OK] npm: {result.stdout.strip()} ({npm_path})")
            return node_path, npm_path
        except Exception:
            pass

    print("[INFO] 尝试通过 node 调用 npm-cli.js...")
    node_dir = os.path.dirname(node_path)
    npm_cli = os.path.join(node_dir, "node_modules", "npm", "bin", "npm-cli.js")

    if os.path.exists(npm_cli):
        try:
            result = subprocess.run([node_path, npm_cli, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[OK] npm: {result.stdout.strip()} (via node + npm-cli.js)")
                return node_path, (node_path, npm_cli)
        except Exception:
            pass

    print("[ERROR] 未找到 npm，请检查 Node.js 安装")
    return None, None


def run(cmd, cwd=None, shell=False):
    if cwd is None:
        cwd = PROJECT_ROOT

    if isinstance(cmd, (list, tuple)):
        full_cmd = " ".join(str(c) for c in cmd)
    else:
        full_cmd = cmd
        shell = True

    print(f"\n>>> {full_cmd}")

    if shell:
        result = subprocess.run(full_cmd, cwd=cwd, shell=True, text=True, encoding='utf-8', errors='replace')
    else:
        result = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace')

    if result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}")
        if result.stdout:
            print("STDOUT:", result.stdout[-2000:])
        if result.stderr:
            print("STDERR:", result.stderr[-2000:])
        pause_before_exit()
        sys.exit(result.returncode)
    return result


def run_with_output(cmd, cwd=None, shell=False):
    if cwd is None:
        cwd = PROJECT_ROOT

    if isinstance(cmd, (list, tuple)):
        full_cmd = " ".join(str(c) for c in cmd)
    else:
        full_cmd = cmd
        shell = True

    print(f"\n>>> {full_cmd}")

    if shell:
        result = subprocess.run(full_cmd, cwd=cwd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    else:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')

    if result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}")
        if result.stdout:
            print("STDOUT:", result.stdout[-2000:])
        if result.stderr:
            print("STDERR:", result.stderr[-2000:])
        pause_before_exit()
        sys.exit(result.returncode)
    return result


def check_python_version():
    try:
        result = run_with_output([sys.executable, "--version"])
        version = result.stdout.strip()
        print(f"[OK] Python: {version}")
        return True
    except Exception as e:
        print(f"[ERROR] 未找到 Python")
        return False


def run_npm(npm_path, args):
    if isinstance(npm_path, tuple):
        node_path, npm_cli = npm_path
        cmd = f'"{node_path}" "{npm_cli}" {args}'
    else:
        cmd = f'"{npm_path}" {args}'
    run(cmd, shell=True)


def install_node_deps(npm_path):
    print("\n=== 安装 Node.js 依赖 ===")
    run_npm(npm_path, "install")


def build_renderer(npm_path):
    print("\n=== 构建 React 渲染进程 ===")
    run_npm(npm_path, "run build:renderer")


def build_main(npm_path):
    print("\n=== 构建 Electron 主进程 ===")
    run_npm(npm_path, "run build:main")


def install_python_deps():
    print("\n=== 安装 Python 依赖 ===")
    req_file = PROJECT_ROOT / "requirements.txt"
    if req_file.exists():
        run([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
    else:
        print("[WARNING] requirements.txt 不存在，跳过 Python 依赖安装")


def build_sidecar():
    print("\n=== 打包 Python Sidecar ===")
    sidecar_dir = PROJECT_ROOT / "sidecar"
    dist_dir = sidecar_dir / "dist"

    if dist_dir.exists():
        print("清理旧的 Sidecar 构建...")
        shutil.rmtree(dist_dir, ignore_errors=True)

    run([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "sidecar_server",
        "--distpath", str(dist_dir),
        "--workpath", str(sidecar_dir / "build"),
        "--specpath", str(sidecar_dir),
        "--noconfirm",
        "--clean",
        str(sidecar_dir / "sidecar_server.py")
    ])

    exe_path = dist_dir / "sidecar_server.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"[OK] Sidecar 打包成功: {exe_path} ({size_mb:.1f} MB)")
    else:
        print("[ERROR] Sidecar 打包失败")
        sys.exit(1)


def build_electron(npm_path):
    print("\n=== 使用 electron-builder 打包 ===")
    run_npm(npm_path, "run dist:win")


def verify_build():
    print("\n=== 验证构建结果 ===")
    artifact_dir = PROJECT_ROOT / "release-artifacts" / "electron"
    if not artifact_dir.exists():
        print(f"[ERROR] 构建产物目录不存在: {artifact_dir}")
        return False

    setup_exe = None
    for file in artifact_dir.iterdir():
        if file.suffix == ".exe" and "Setup" in file.name:
            setup_exe = file
            break

    if setup_exe:
        size_mb = setup_exe.stat().st_size / (1024 * 1024)
        print(f"[OK] 构建成功！")
        print(f"[OK] 输出文件: {setup_exe}")
        print(f"[OK] 文件大小: {size_mb:.1f} MB")
        return True
    else:
        print("[ERROR] 未找到 Setup.exe 文件")
        return False


def main():
    print("=" * 60)
    print("  Outlook 长图助手 V6 一键打包脚本")
    print("=" * 60)
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"Python: {sys.version}")
    print("=" * 60)

    node_path, npm_path = find_node_and_npm()
    if not node_path or not npm_path:
        sys.exit(1)

    node_dir = os.path.dirname(node_path)
    if node_dir not in os.environ["PATH"]:
        print(f"[INFO] 将 Node.js 目录加入 PATH: {node_dir}")
        os.environ["PATH"] = node_dir + os.pathsep + os.environ["PATH"]

    if not check_python_version():
        sys.exit(1)

    install_node_deps(npm_path)
    install_python_deps()

    build_renderer(npm_path)
    build_main(npm_path)
    build_sidecar()
    build_electron(npm_path)

    if verify_build():
        print("\n" + "=" * 60)
        print("✅ 所有构建步骤完成！")
        print("=" * 60)
    else:
        print("\n[ERROR] 构建验证失败")
        sys.exit(1)

    pause_before_exit()


if __name__ == "__main__":
    main()
