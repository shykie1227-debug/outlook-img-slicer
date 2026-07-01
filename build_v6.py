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

NPM_CMD = "npm"
NODE_CMD = "node"


def pause_before_exit():
    if sys.stdin is not None and sys.stdin.isatty():
        input("\n按回车键退出...")


def find_npm():
    global NPM_CMD, NODE_CMD
    
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            NODE_CMD = "node"
            node_version = result.stdout.strip()
            print(f"[OK] Node.js: {node_version}")
        else:
            raise Exception("node not found")
    except Exception:
        print("[INFO] 尝试查找 Node.js 安装路径...")
        common_paths = [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "nodejs", "node.exe"),
            os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", "node", "bin", "node.exe"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                NODE_CMD = path
                result = subprocess.run([path, "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"[OK] Node.js: {result.stdout.strip()} ({path})")
                    break
        else:
            print("[ERROR] 未找到 Node.js，请先安装 Node.js 18+")
            print("        下载地址: https://nodejs.org/")
            return False
    
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            NPM_CMD = "npm"
            npm_version = result.stdout.strip()
            print(f"[OK] npm: {npm_version}")
            return True
    except Exception:
        pass
    
    print("[INFO] npm 命令找不到，尝试通过 node 调用 npm-cli.js...")
    node_dir = os.path.dirname(NODE_CMD) if os.path.isfile(NODE_CMD) else ""
    
    npm_cli_paths = [
        os.path.join(node_dir, "node_modules", "npm", "bin", "npm-cli.js"),
        os.path.join(os.path.dirname(sys.executable), "node_modules", "npm", "bin", "npm-cli.js"),
    ]
    
    for npm_cli in npm_cli_paths:
        if os.path.exists(npm_cli):
            NPM_CMD = f'"{NODE_CMD}" "{npm_cli}"'
            result = subprocess.run(f'{NODE_CMD} "{npm_cli}" --version', capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                npm_version = result.stdout.strip()
                print(f"[OK] npm: {npm_version} (via node + npm-cli.js)")
                return True
    
    print("[ERROR] 未找到 npm，请检查 Node.js 安装")
    return False


def run(cmd: list, cwd=None, **kwargs):
    if cwd is None:
        cwd = PROJECT_ROOT
    
    use_shell = False
    if isinstance(cmd, str):
        full_cmd = cmd
        use_shell = True
    else:
        full_cmd = " ".join(str(c) for c in cmd)
    
    print(f"\n>>> {full_cmd}")
    
    if use_shell:
        result = subprocess.run(full_cmd, cwd=cwd, shell=True, **kwargs)
    else:
        result = subprocess.run(cmd, cwd=cwd, **kwargs)
    
    if result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}")
        if result.stdout:
            print("STDOUT:", str(result.stdout)[-2000:])
        if result.stderr:
            print("STDERR:", str(result.stderr)[-2000:])
        pause_before_exit()
        sys.exit(result.returncode)
    return result


def run_with_output(cmd: list, cwd=None):
    if cwd is None:
        cwd = PROJECT_ROOT
    
    use_shell = False
    if isinstance(cmd, str):
        full_cmd = cmd
        use_shell = True
    else:
        full_cmd = " ".join(str(c) for c in cmd)
    
    print(f"\n>>> {full_cmd}")
    
    if use_shell:
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


def install_node_deps():
    print("\n=== 安装 Node.js 依赖 ===")
    if "npm-cli.js" in NPM_CMD:
        run(f'{NPM_CMD} install')
    else:
        run([NPM_CMD, "install"])


def build_renderer():
    print("\n=== 构建 React 渲染进程 ===")
    if "npm-cli.js" in NPM_CMD:
        run(f'{NPM_CMD} run build:renderer')
    else:
        run([NPM_CMD, "run", "build:renderer"])


def build_main():
    print("\n=== 构建 Electron 主进程 ===")
    if "npm-cli.js" in NPM_CMD:
        run(f'{NPM_CMD} run build:main')
    else:
        run([NPM_CMD, "run", "build:main"])


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


def build_electron():
    print("\n=== 使用 electron-builder 打包 ===")
    if "npm-cli.js" in NPM_CMD:
        run(f'{NPM_CMD} run dist:win')
    else:
        run([NPM_CMD, "run", "dist:win"])


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

    if not find_npm():
        sys.exit(1)
    
    if not check_python_version():
        sys.exit(1)

    install_node_deps()
    install_python_deps()
    
    build_renderer()
    build_main()
    build_sidecar()
    build_electron()
    
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
