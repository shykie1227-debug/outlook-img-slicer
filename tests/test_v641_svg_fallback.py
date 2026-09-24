"""
SVG 转换渲染链回归（V6.4.2）。

背景：
  在没有 libcairo 的机器上（**含打包后的 Windows EXE**），cairosvg 与
  svglib+reportlab 会**同时**失效：
    - `import cairosvg` 抛 OSError（cairocffi 找不到 cairo-2 / libcairo-2）；
    - svglib 路径能 import，但 `renderPM` 加载 rlPyCairo 后端时抛
      `RenderPMError: cannot import desired renderPM backend rlPyCairo`。
  所以仅把 `except ImportError` 放宽为 `except Exception`（V6.4.1）并不能让 SVG
  导入真正可用 —— 它只改变了失败时的异常类型。

  真正的解法是把 **PySide6 自带的 QtSvg** 提为首选：项目已依赖 PySide6，
  QtSvg 是其中的标准模块，不依赖任何系统库。

用例安排：
  第 1 条走真实 QtSvg 验证主路径；第 2、3 条用 monkeypatch 拦截
  `builtins.__import__` 模拟降级环境；第 4 条验证非 SVG 直通。
  因此本文件**不依赖真实的 cairosvg / svglib / libcairo**，
  在 macOS / Windows / CI 上都能稳定执行。
"""
import builtins
import types
from pathlib import Path

import image_slicer

_SVG_BODY = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60">'
    '<rect width="120" height="60" fill="#ff8c00"/>'
    "</svg>"
)


def _write_svg(tmp_path: Path, name: str = "sample.svg") -> str:
    svg = tmp_path / name
    svg.write_text(_SVG_BODY, encoding="utf-8")
    return str(svg)


def _patch_import(monkeypatch, handler):
    """用 handler 拦截 builtins.__import__，其余请求转交真实实现。"""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        result = handler(name, real_import, *args, **kwargs)
        if result is not None:
            return result
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_svg_renders_with_qtsvg_without_system_libraries(tmp_path):
    """主路径：QtSvg 直接渲染，不需要 cairosvg / svglib / libcairo。"""
    svg_path = _write_svg(tmp_path)

    result = image_slicer._convert_svg_to_png(svg_path)

    assert Path(result).suffix == ".png", "QtSvg 路径应产出同名 .png"
    assert Path(result).exists()
    assert Path(result).stat().st_size > 0


def test_svg_falls_back_to_cairosvg_when_qtsvg_unavailable(monkeypatch, tmp_path):
    """QtSvg 不可用时应降级到 cairosvg。"""
    svg_path = _write_svg(tmp_path)
    calls = []

    def handler(name, real_import, *args, **kwargs):
        if name == "PySide6.QtSvg":
            raise ImportError("blocked: PySide6.QtSvg")
        if name == "cairosvg":
            module = types.ModuleType("cairosvg")

            def svg2png(url=None, write_to=None, **kwargs):
                calls.append("cairosvg")
                Path(write_to).write_bytes(b"\x89PNG\r\n\x1a\n")

            module.svg2png = svg2png
            return module
        return None

    _patch_import(monkeypatch, handler)

    result = image_slicer._convert_svg_to_png(svg_path)

    assert calls == ["cairosvg"]
    assert Path(result).exists()


def test_svg_falls_back_to_svglib_when_qtsvg_and_cairo_unavailable(monkeypatch, tmp_path):
    """QtSvg 不可用 + 缺 libcairo（真实故障）时应降级到 svglib。"""
    svg_path = _write_svg(tmp_path)
    calls = []

    def handler(name, real_import, *args, **kwargs):
        if name == "PySide6.QtSvg":
            raise ImportError("blocked: PySide6.QtSvg")
        if name == "cairosvg":
            # 真实故障现场：cairocffi 找不到 libcairo
            raise OSError('no library called "cairo-2" was found')
        if name == "svglib.svglib":
            module = types.ModuleType("svglib.svglib")
            module.svg2rlg = lambda path: ("drawing", path)
            return module
        if name == "reportlab.graphics":
            package = types.ModuleType("reportlab.graphics")
            render_pm = types.ModuleType("reportlab.graphics.renderPM")

            def draw_to_file(drawing, path, fmt=None):
                calls.append("renderPM")
                Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")

            render_pm.drawToFile = draw_to_file
            package.renderPM = render_pm
            return package
        return None

    _patch_import(monkeypatch, handler)

    result = image_slicer._convert_svg_to_png(svg_path)

    # 关键：不能抛出 OSError，必须落到 svglib 兜底并写出文件
    assert calls == ["renderPM"]
    assert Path(result).suffix == ".png"
    assert Path(result).exists()


def test_non_svg_path_is_returned_untouched(tmp_path):
    """非 .svg 后缀不应进入转换流程。"""
    png = tmp_path / "already.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert image_slicer._convert_svg_to_png(str(png)) == str(png)


def test_pyinstaller_spec_declares_qtsvg_hidden_import():
    """
    打包配置必须显式声明 PySide6.QtSvg。

    image_slicer 是在函数体内 import QSvgRenderer 的，若 spec 里不显式列出，
    打包后的 EXE 里 QtSvg 可能被裁掉，SVG 转换会静默退回
    cairosvg/svglib —— 而这两条路径在没有 libcairo 的机器上都不可用。
    """
    spec = (
        Path(__file__).resolve().parents[1] / "desktop" / "outlook_img_slicer.spec"
    )
    content = spec.read_text(encoding="utf-8")

    assert '"PySide6.QtSvg"' in content, (
        "desktop/outlook_img_slicer.spec 的 hiddenimports 必须包含 PySide6.QtSvg"
    )
