#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_v6.py - Outlook 长图助手 V6 一键打包脚本（Windows）
用法: python build_v6.py [--skip-npm-install] [--skip-pip-install] [--mirror]

选项:
  --skip-npm-install    跳过 npm install
  --skip-pip-install    跳过 pip install
  --mirror              使用国内镜像加速下载（推荐）

构建流程:
  1. 环境检查（Node.js / Python / 必要文件）
  2. 安装 Node.js 依赖（可跳过）
  3. 安装 Python 依赖（可跳过）
  4. 构建 React 渲染进程 (app/dist)
  5. 构建 Electron 主进程 (electron/dist-electron)
  6. 使用 PyInstaller 打包 Python Sidecar (sidecar/dist)
  7. 使用 electron-builder 打包为 Windows 绿色免安装版

输出:
  release-artifacts/electron/Outlook 长图助手-V6.0.0-portable-x64.exe
"""
import subprocess
import sys
import os
import shutil
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"


def print_ok(msg):
    print(f"{COLOR_GREEN}[OK]{COLOR_RESET} {msg}")


def print_err(msg):
    print(f"{COLOR_RED}[ERROR]{COLOR_RESET} {msg}")


def print_warn(msg):
    print(f"{COLOR_YELLOW}[WARN]{COLOR_RESET} {msg}")


def print_info(msg):
    print(f"{COLOR_CYAN}[INFO]{COLOR_RESET} {msg}")


def print_step(title):
    print(f"\n{COLOR_CYAN}{'=' * 60}{COLOR_RESET}")
    print(f"{COLOR_CYAN}  {title}{COLOR_RESET}")
    print(f"{COLOR_CYAN}{'=' * 60}{COLOR_RESET}")


def pause_before_exit():
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input(f"\n{COLOR_CYAN}按回车键退出...{COLOR_RESET}")
        except EOFError:
            pass


def find_executable(name):
    if sys.platform == "win32":
        name = name + ".exe"
    for path in os.environ["PATH"].split(os.pathsep):
        full_path = os.path.join(path, name)
        if os.path.exists(full_path):
            return full_path
    return None


def find_node_and_npm():
    """
    查找 Node.js 和 npm。
    返回 (node_path, npm_runner)
    npm_runner 是一个 callable，接受 args 列表并执行 npm 命令
    """
    node_path = None
    npm_info = None

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
        print_err("未找到 Node.js，请先安装 Node.js 18+")
        print("        下载地址: https://nodejs.org/")
        print("        安装时请勾选 'Add to PATH'")
        return None, None

    try:
        result = subprocess.run(
            [node_path, "--version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        version = result.stdout.strip()
        print_ok(f"Node.js: {version} ({node_path})")

        major = int(version.lstrip("v").split(".")[0])
        if major < 18:
            print_warn(f"Node.js 版本 {version} 低于推荐的 18+，可能存在兼容性问题")
    except Exception as e:
        print_err(f"无法执行 Node.js: {e}")
        return None, None

    node_dir = os.path.dirname(node_path)

    npm_cli = os.path.join(node_dir, "node_modules", "npm", "bin", "npm-cli.js")
    if os.path.exists(npm_cli):
        try:
            result = subprocess.run(
                [node_path, npm_cli, "--version"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if result.returncode == 0:
                npm_version = result.stdout.strip()
                print_ok(f"npm: {npm_version} (via node + npm-cli.js)")
                return node_path, ("node_cli", node_path, npm_cli)
        except Exception:
            pass

    for npm_cmd_name in ["npm.cmd", "npm"]:
        npm_path = os.path.join(node_dir, npm_cmd_name)
        if os.path.exists(npm_path):
            try:
                result = subprocess.run(
                    [npm_path, "--version"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                if result.returncode == 0:
                    print_ok(f"npm: {result.stdout.strip()} ({npm_path})")
                    return node_path, ("direct", npm_path)
            except Exception:
                pass

    npm_in_path = find_executable("npm")
    if npm_in_path:
        try:
            result = subprocess.run(
                [npm_in_path, "--version"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if result.returncode == 0:
                print_ok(f"npm: {result.stdout.strip()} ({npm_in_path})")
                return node_path, ("direct", npm_in_path)
        except Exception:
            pass

    print_err("未找到 npm，请检查 Node.js 安装")
    print_info("尝试重新安装 Node.js，并确保勾选 'Add to PATH'")
    return None, None


def run_npm(npm_info, args, cwd=None):
    if cwd is None:
        cwd = str(PROJECT_ROOT)

    mode = npm_info[0]
    if mode == "node_cli":
        _, node_path, npm_cli = npm_info
        cmd = f'"{node_path}" "{npm_cli}" {args}'
    else:
        _, npm_path = npm_info
        cmd = f'"{npm_path}" {args}'

    print_info(f"npm {args}")

    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:
        print_err(f"npm 命令失败，退出码: {result.returncode}")
        print_err(f"命令: npm {args}")
        if result.stdout:
            print(f"\n--- STDOUT (最后30行) ---\n")
            lines = result.stdout.strip().splitlines()
            print("\n".join(lines[-30:]))
        if result.stderr:
            print(f"\n--- STDERR (最后30行) ---\n")
            lines = result.stderr.strip().splitlines()
            print("\n".join(lines[-30:]))
        print_err("\n构建失败，请检查上方错误信息")
        print_info("常见问题排查：")
        print_info("  1. 网络问题：使用 --mirror 参数启用国内镜像")
        print_info("  2. 权限问题：以管理员身份运行")
        print_info("  3. 依赖冲突：删除 node_modules 后重试")
        pause_before_exit()
        sys.exit(result.returncode)

    return result


def run_python(args, cwd=None):
    if cwd is None:
        cwd = str(PROJECT_ROOT)

    cmd = [sys.executable] + args
    print_info(f"python {' '.join(args)}")

    result = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:
        print_err(f"Python 命令失败，退出码: {result.returncode}")
        print_err(f"命令: python {' '.join(args)}")
        if result.stdout:
            print(f"\n--- STDOUT (最后30行) ---\n")
            lines = result.stdout.strip().splitlines()
            print("\n".join(lines[-30:]))
        if result.stderr:
            print(f"\n--- STDERR (最后30行) ---\n")
            lines = result.stderr.strip().splitlines()
            print("\n".join(lines[-30:]))
        print_err("\n构建失败，请检查上方错误信息")
        pause_before_exit()
        sys.exit(result.returncode)

    return result


def check_python_version():
    try:
        version = sys.version.split()[0]
        print_ok(f"Python: {version} ({sys.executable})")

        major, minor = sys.version_info[:2]
        if major < 3 or (major == 3 and minor < 10):
            print_warn(f"Python 版本 {version} 低于推荐的 3.10+，可能存在兼容性问题")
        return True
    except Exception as e:
        print_err(f"未找到 Python: {e}")
        return False


def check_project_files():
    print_step("检查项目文件")

    required_files = [
        "package.json",
        "electron-builder.yml",
        "app/package.json",
        "electron/package.json",
        "sidecar/sidecar_server.py",
        "requirements.txt",
        "icon.ico",
    ]

    all_ok = True
    for f in required_files:
        path = PROJECT_ROOT / f
        if path.exists():
            print_ok(f"存在: {f}")
        else:
            print_err(f"缺失: {f}")
            all_ok = False

    if not all_ok:
        print_err("项目文件不完整，请检查项目目录")
        return False

    return True


def setup_mirror(npm_info):
    print_step("配置国内镜像加速")

    print_info("设置 npm 镜像为 npmmirror.com...")
    run_npm(npm_info, "config set registry https://registry.npmmirror.com/")

    print_info("设置 Electron 二进制下载镜像...")
    run_npm(npm_info, "config set electron_mirror https://npmmirror.com/mirrors/electron/")

    print_info("设置 electron-builder 二进制下载镜像...")
    run_npm(npm_info, "config set electron-builder-binaries_mirror https://npmmirror.com/mirrors/electron-builder-binaries/")

    os.environ["ELECTRON_MIRROR"] = "https://npmmirror.com/mirrors/electron/"
    os.environ["ELECTRON_BUILDER_BINARIES_MIRROR"] = "https://npmmirror.com/mirrors/electron-builder-binaries/"

    print_ok("国内镜像配置完成")


def install_node_deps(npm_info):
    print_step("安装 Node.js 依赖")

    node_modules = PROJECT_ROOT / "node_modules"
    if node_modules.exists():
        print_info("node_modules 已存在，如需重新安装请先删除该目录")

    run_npm(npm_info, "install")
    print_ok("Node.js 依赖安装完成")


def install_python_deps():
    print_step("安装 Python 依赖")

    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        print_warn("requirements.txt 不存在，跳过 Python 依赖安装")
        return

    run_python(["-m", "pip", "install", "-r", str(req_file)])
    print_ok("Python 依赖安装完成")


def build_renderer(npm_info):
    print_step("构建 React 渲染进程")

    dist_dir = PROJECT_ROOT / "app" / "dist"
    if dist_dir.exists():
        print_info("清理旧的构建产物...")
        shutil.rmtree(dist_dir, ignore_errors=True)

    run_npm(npm_info, "run build:renderer")

    index_html = dist_dir / "index.html"
    if index_html.exists():
        print_ok("渲染进程构建完成")
        return True
    else:
        print_err("渲染进程构建失败，未找到 index.html")
        return False


def build_main(npm_info):
    print_step("构建 Electron 主进程")

    dist_dir = PROJECT_ROOT / "electron" / "dist-electron"
    if dist_dir.exists():
        print_info("清理旧的构建产物...")
        shutil.rmtree(dist_dir, ignore_errors=True)

    run_npm(npm_info, "run build:main")

    main_js = dist_dir / "main.js"
    if main_js.exists():
        print_ok("主进程构建完成")
        return True
    else:
        print_err("主进程构建失败，未找到 main.js")
        return False


def build_sidecar():
    print_step("打包 Python Sidecar")

    sidecar_dir = PROJECT_ROOT / "sidecar"
    dist_dir = sidecar_dir / "dist"
    build_dir = sidecar_dir / "build"

    if dist_dir.exists():
        print_info("清理旧的 Sidecar 构建...")
        shutil.rmtree(dist_dir, ignore_errors=True)
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    spec_file = sidecar_dir / "sidecar_server.spec"
    if spec_file.exists():
        spec_file.unlink()

    start_time = time.time()

    run_python([
        "-m", "PyInstaller",
        "--onefile",
        "--name", "sidecar_server",
        "--distpath", str(dist_dir),
        "--workpath", str(build_dir),
        "--specpath", str(sidecar_dir),
        "--noconfirm",
        "--clean",
        "--collect-all", "PIL",
        "--collect-all", "fitz",
        "--collect-all", "win32com",
        str(sidecar_dir / "sidecar_server.py")
    ])

    elapsed = time.time() - start_time

    exe_path = dist_dir / "sidecar_server.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print_ok(f"Sidecar 打包成功: {exe_path} ({size_mb:.1f} MB, 耗时 {elapsed:.0f}s)")
        return True
    else:
        print_err("Sidecar 打包失败，未找到 sidecar_server.exe")
        return False


def build_electron(npm_info):
    print_step("使用 electron-builder 打包（绿色免安装版）")

    output_dir = PROJECT_ROOT / "release-artifacts" / "electron"
    if output_dir.exists():
        print_info("清理旧的构建产物...")
        shutil.rmtree(output_dir, ignore_errors=True)

    start_time = time.time()

    run_npm(npm_info, "run dist:win")

    elapsed = time.time() - start_time
    print_info(f"electron-builder 完成，耗时 {elapsed:.0f}s")


def verify_build():
    print_step("验证构建结果")

    artifact_dir = PROJECT_ROOT / "release-artifacts" / "electron"
    if not artifact_dir.exists():
        print_err(f"构建产物目录不存在: {artifact_dir}")
        return None

    exe_files = list(artifact_dir.glob("*.exe"))
    if not exe_files:
        print_err("未找到任何 .exe 文件")
        return None

    portable_exe = None
    setup_exe = None
    for f in exe_files:
        if "portable" in f.name.lower():
            portable_exe = f
        elif "setup" in f.name.lower():
            setup_exe = f

    target_exe = portable_exe or setup_exe or exe_files[0]

    size_mb = target_exe.stat().st_size / (1024 * 1024)
    print_ok(f"找到构建产物: {target_exe.name}")
    print_ok(f"文件大小: {size_mb:.1f} MB")
    print_ok(f"完整路径: {target_exe}")

    other_files = [f.name for f in artifact_dir.iterdir() if f != target_exe]
    if other_files:
        print_info(f"其他产物: {', '.join(other_files)}")

    return target_exe


def main():
    parser = argparse.ArgumentParser(description="Outlook 长图助手 V6 打包脚本")
    parser.add_argument("--skip-npm-install", action="store_true", help="跳过 npm install")
    parser.add_argument("--skip-pip-install", action="store_true", help="跳过 pip install")
    parser.add_argument("--mirror", action="store_true", help="使用国内镜像加速下载")
    args = parser.parse_args()

    print(f"\n{COLOR_CYAN}{'=' * 60}{COLOR_RESET}")
    print(f"{COLOR_CYAN}  Outlook 长图助手 V6 一键打包脚本{COLOR_RESET}")
    print(f"{COLOR_CYAN}{'=' * 60}{COLOR_RESET}")
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"平台: {sys.platform}")
    if args.mirror:
        print(f"{COLOR_YELLOW}模式: 国内镜像加速{COLOR_RESET}")
    print(f"{COLOR_CYAN}{'=' * 60}{COLOR_RESET}")

    if not check_project_files():
        pause_before_exit()
        sys.exit(1)

    node_path, npm_info = find_node_and_npm()
    if not node_path or not npm_info:
        pause_before_exit()
        sys.exit(1)

    node_dir = os.path.dirname(node_path)
    if node_dir not in os.environ["PATH"]:
        print_info(f"将 Node.js 目录加入 PATH: {node_dir}")
        os.environ["PATH"] = node_dir + os.pathsep + os.environ["PATH"]

    if not check_python_version():
        pause_before_exit()
        sys.exit(1)

    if args.mirror:
        setup_mirror(npm_info)

    if not args.skip_npm_install:
        install_node_deps(npm_info)
    else:
        print_info("跳过 npm install（--skip-npm-install）")

    if not args.skip_pip_install:
        install_python_deps()
    else:
        print_info("跳过 pip install（--skip-pip-install）")

    if not build_renderer(npm_info):
        pause_before_exit()
        sys.exit(1)

    if not build_main(npm_info):
        pause_before_exit()
        sys.exit(1)

    if not build_sidecar():
        pause_before_exit()
        sys.exit(1)

    build_electron(npm_info)

    result_exe = verify_build()
    if result_exe:
        print(f"\n{COLOR_GREEN}{'=' * 60}{COLOR_RESET}")
        print(f"{COLOR_GREEN}  ✅ 所有构建步骤完成！{COLOR_RESET}")
        print(f"{COLOR_GREEN}{'=' * 60}{COLOR_RESET}")
        print(f"{COLOR_GREEN}  输出文件: {result_exe}{COLOR_RESET}")
        print(f"{COLOR_GREEN}  文件大小: {result_exe.stat().st_size / (1024*1024):.1f} MB{COLOR_RESET}")
        print(f"{COLOR_GREEN}{'=' * 60}{COLOR_RESET}")
    else:
        print_err("构建验证失败")
        pause_before_exit()
        sys.exit(1)

    pause_before_exit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warn("\n用户中断构建")
        sys.exit(130)
    except Exception as e:
        print_err(f"构建脚本发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)
