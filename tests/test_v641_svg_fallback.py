"""
SVG 转换兜底回归（V6.4.1）。

缺陷现场：
  缺少 libcairo 时 `import cairosvg` 抛的是 **OSError**（cairocffi 找不到
  cairo-2 / libcairo-2），而不是 ImportError。旧实现只 `except ImportError`，
  异常直接冒泡，走不到下面不依赖系统库的 svglib 兜底 —— 在没有 libcairo 的
  机器上（含打包后的 EXE）SVG 导入会直接失败。

这两条用例用 monkeypatch 拦截 `builtins.__import__` 来模拟两种环境，
因此**不需要真的安装 cairosvg / svglib / libcairo**，
在 macOS、Windows 与 CI 上都能稳定执行。
"""
import builtins
import types
from pathlib import Path

import pytest

import image_slicer

_SVG_BODY = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
    '<rect width="40" height="20"/></svg>'
)


def _write_svg(tmp_path: Path) -> str:
    svg = tmp_path / "sample.svg"
    svg.write_text(_SVG_BODY, encoding="utf-8")
    return str(svg)


def test_svg_falls_back_to_svglib_when_cairo_is_missing(monkeypatch, tmp_path):
    """cairosvg 抛 OSError（缺 libcairo）时，必须回退到 svglib 并真的产出 PNG。"""
    svg_path = _write_svg(tmp_path)
    calls = []
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
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
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = image_slicer._convert_svg_to_png(svg_path)

    # 关键断言：没有抛出 OSError，而是落到了 svglib 兜底并写出文件
    assert calls == ["renderPM"], "缺 libcairo 时应回退到 svglib + reportlab"
    assert Path(result).suffix == ".png"
    assert Path(result).exists()


def test_svg_prefers_cairosvg_when_it_works(monkeypatch, tmp_path):
    """cairosvg 可用时优先使用它，不应落到 svglib。"""
    svg_path = _write_svg(tmp_path)
    calls = []
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cairosvg":
            module = types.ModuleType("cairosvg")

            def svg2png(url=None, write_to=None, **kwargs):
                calls.append("cairosvg")
                Path(write_to).write_bytes(b"\x89PNG\r\n\x1a\n")

            module.svg2png = svg2png
            return module
        if name.startswith("svglib") or name.startswith("reportlab"):
            raise AssertionError("cairosvg 可用时不应回退到 svglib")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = image_slicer._convert_svg_to_png(svg_path)

    assert calls == ["cairosvg"], "cairosvg 可用时应直接使用它"
    assert Path(result).exists()


def test_non_svg_path_is_returned_untouched(tmp_path):
    """非 .svg 后缀不应进入转换流程。"""
    png = tmp_path / "already.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert image_slicer._convert_svg_to_png(str(png)) == str(png)
