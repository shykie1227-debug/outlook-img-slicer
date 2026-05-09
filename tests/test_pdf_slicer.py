"""
测试 pdf_slicer 模块
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_slicer import pdf_to_images


class TestPdfSlicer:
    """测试 pdf_slicer 模块"""

    def test_import_module(self):
        """测试模块可导入"""
        import pdf_slicer
        assert hasattr(pdf_slicer, "pdf_to_images")

    def test_pdf_to_images_missing_file(self):
        """测试转换不存在的 PDF"""
        with pytest.raises(Exception):
            pdf_to_images("/nonexistent/file.pdf")

    def test_dpi_parameter(self):
        """测试 DPI 参数存在且有默认值"""
        import inspect
        sig = inspect.signature(pdf_to_images)
        assert "dpi" in sig.parameters
        assert sig.parameters["dpi"].default == 150

    def test_module_structure(self):
        """测试模块结构完整"""
        import pdf_slicer
        assert callable(pdf_slicer.pdf_to_images)
