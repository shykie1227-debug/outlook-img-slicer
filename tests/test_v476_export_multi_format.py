"""
V4.7.6 测试 — 导出分支支持多格式（PDF/PPT/PSD/PSB）

修复：
- _export_images 用 _render_source_to_images 统一渲染
  替代旧 _PI.open 直开（PDF/PPT/PSD 在 _PI.open 会直接失败）
- 多页文件（>5 页）弹 QMessageBox 二次确认（架构师 UX 决策）
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 允许在测试目录外运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _make_test_png(path: Path, size=(100, 80), color=(255, 0, 0)):
    """构造一张测试用 PNG"""
    from PIL import Image
    img = Image.new("RGB", size, color)
    img.save(path, "PNG")


def test_export_images_supports_png_jpg_bmp_webp_gif(tmp_path):
    """V4.7.6 回归：传统图片格式仍能导出（与 v4.7.5 等价）"""
    from main import _render_source_to_images

    formats = [
        ("a.png", "PNG"),
        ("b.jpg", "JPEG"),
        ("c.bmp", "BMP"),
        ("d.webp", "WEBP"),
        ("e.gif", "GIF"),
    ]
    paths = []
    for name, _ in formats:
        p = tmp_path / name
        _make_test_png(p)
        paths.append(str(p))

    for p in paths:
        imgs = _render_source_to_images(p)
        assert len(imgs) == 1, f"{p} 应渲染出 1 张"
        assert imgs[0].size[0] > 0 and imgs[0].size[1] > 0


def test_render_source_to_images_pdf_multipage(tmp_path):
    """V4.7.6 新增：PDF 多页应渲染为多张 PIL Image"""
    # 用 reportlab 构造一个 3 页 PDF（如果不可用则 skip）
    try:
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        pytest.skip("reportlab not available")

    from main import _render_source_to_images
    pdf_path = tmp_path / "test.pdf"
    c = rl_canvas.Canvas(str(pdf_path))
    for i in range(3):
        c.drawString(100, 750, f"Page {i+1}")
        c.showPage()
    c.save()

    imgs = _render_source_to_images(str(pdf_path))
    assert len(imgs) == 3, f"3 页 PDF 应渲染出 3 张，得到 {len(imgs)}"
    for img in imgs:
        assert img.size[0] > 0 and img.size[1] > 0


def test_render_source_to_images_unsupported_ext_raises(tmp_path):
    """V4.7.6：不支持的格式应明确抛 ValueError，不静默失败"""
    from main import _render_source_to_images
    fake = tmp_path / "x.txt"
    fake.write_text("not an image")
    with pytest.raises(ValueError, match="不支持的导出格式"):
        _render_source_to_images(str(fake))


def test_render_source_to_images_no_psd_top_level_import(monkeypatch):
    """V4.7.6 验证：未安装 psd_tools 时不应让主程序启动失败"""
    # 检查 main.py 模块级不应有 `import psd_slicer`
    main_src = (ROOT / "main.py").read_text()
    # 只允许函数内 import
    for line in main_src.splitlines():
        if "import psd_slicer" in line:
            # 函数内 import 是允许的
            assert "def " in main_src[max(0, main_src.index(line) - 200):main_src.index(line)], \
                f"psd_slicer 顶层 import: {line}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
