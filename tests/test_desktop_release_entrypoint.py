from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = ROOT / "desktop"


def test_root_build_py_delegates_to_desktop_builder():
    """Release builds should use the stable desktop/PySide architecture, not Electron."""
    build_py = ROOT / "build.py"

    assert build_py.exists(), "根目录 build.py 必须存在，供 GitHub/VM/手动构建统一入口调用"
    source = build_py.read_text(encoding="utf-8")

    assert "desktop/build.py" in source.replace("\\", "/")
    assert "electron-builder" not in source
    assert "sidecar" not in source.lower()


def test_vm_build_script_builds_desktop_pyside_exe_without_electron():
    """The local Windows VM build must not produce the broken Electron shell."""
    source = (ROOT / "vm_build.ps1").read_text(encoding="utf-8")
    lowered = source.lower()

    assert "desktop" in source.replace("\\", "/")
    assert "electron-builder" not in lowered
    assert "npm install" not in lowered
    assert "build:renderer" not in lowered
    assert "sidecar_server" not in lowered


def test_vm_build_rejects_locked_or_stale_output():
    source = (ROOT / "vm_build.ps1").read_text(encoding="utf-8")

    assert 'Get-Process -Name "OutlookImgSlicer"' in source
    assert 'Fail "Unable to clean local build directory' in source
    assert "$buildStartedAt" in source
    assert "LastWriteTimeUtc -lt $buildStartedAt" in source
    assert 'Join-Path $SharedRoot "build-manifest.json"' in source


def test_manual_windows_build_script_uses_same_desktop_entrypoint():
    """Double-click/manual Windows builds should match the VM/release target."""
    source = (ROOT / "build.ps1").read_text(encoding="utf-8")
    lowered = source.lower()

    assert "build.py" in lowered
    assert "electron-builder" not in lowered
    assert "npm install" not in lowered
    assert "sidecar_server" not in lowered


def test_desktop_pyinstaller_spec_can_package_from_desktop_subdir():
    """After moving the desktop app under desktop/, PyInstaller must see root modules/resources."""
    source = (DESKTOP_ROOT / "outlook_img_slicer.spec").read_text(encoding="utf-8")
    normalized = source.replace("\\", "/")

    assert re.search(r"ROOT_DIR\s*=", source), "spec 应定义仓库根目录"
    assert "__file__" not in source, "PyInstaller spec 执行环境不保证提供 __file__"
    assert "SPECPATH" in source, "spec 应使用 PyInstaller 提供的 SPECPATH 定位自身目录"
    assert "pathex=[ROOT_DIR" in normalized
    assert '"icons"' in source or "'icons'" in source
    assert 'icon=os.path.join(ROOT_DIR, "icon.ico")' in source
    assert 'name="OutlookImgSlicer"' in source


def test_desktop_build_script_is_safe_for_vm_noninteractive_ascii_output():
    """VM builds run as SYSTEM, so output names and pauses must be automation-safe."""
    source = (DESKTOP_ROOT / "build.py").read_text(encoding="utf-8")

    assert "OUTLOOK_IMG_SLICER_NO_PAUSE" in source
    assert "OutlookImgSlicer.exe" in source


def test_repository_no_longer_contains_electron_or_sidecar_release_tree():
    """The repo should be a single desktop/PySide product tree after cleanup."""
    assert DESKTOP_ROOT.exists()

    removed_paths = [
        "app",
        "electron",
        "sidecar",
        "scripts/dev.ts",
        "package.json",
        "package-lock.json",
        "electron-builder.yml",
        "docs/v6-build-guide.md",
        "release-artifacts/v6.0.0-notes.md",
        "legacy",
    ]
    for rel in removed_paths:
        assert not (ROOT / rel).exists(), f"旧架构残留未清理: {rel}"


def test_github_workflow_uses_verified_build_manifest():
    """CI must consume the exact hashed artifact, not guess from a stale dist path."""
    source = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    assert "build-manifest.json" in source
    assert "Get-FileHash -Algorithm SHA256" in source
    assert "manifest.artifact_path" in source
    assert "python -m pytest tests/ -q" in source
