"""
测试 pdf_slicer 模块
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPdfSlicer:
    """测试 pdf_slicer 模块"""

    def test_import_module(self):
        """测试模块可导入（PyMuPDF 依赖）"""
        try:
            import fitz
            assert True
        except ImportError:
            pytest.skip("PyMuPDF (fitz) 未安装，跳过 PDF 测试")

    def test_pdf_page_count_missing_file(self):
        """测试获取不存在的 PDF 页数"""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF (fitz) 未安装，跳过 PDF 测试")

        from pdf_slicer import pdf_page_count

        with pytest.raises(Exception):
            pdf_page_count("/nonexistent/file.pdf")

    def test_pdf_to_images_missing_file(self):
        """测试转换不存在的 PDF"""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF (fitz) 未安装，跳过 PDF 测试")

        from pdf_slicer import pdf_to_images

        with pytest.raises(Exception):
            pdf_to_images("/nonexistent/file.pdf")

    def test_pdf_dpi_parameter(self):
        """测试 DPI 参数文档化（代码中已定义）"""
        # 验证函数签名包含 dpi 参数
        try:
            import fitz
            from pdf_slicer import pdf_to_images
            import inspect
            sig = inspect.signature(pdf_to_images)
            assert "dpi" in sig.parameters
        except ImportError:
            pytest.skip("PyMuPDF (fitz) 未安装，跳过 PDF 测试")


class TestPdfSlicerIntegration:
    """PDF 解析集成测试（需要实际 PDF 文件）"""

    def test_module_structure(self):
        """测试模块结构完整性"""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF (fitz) 未安装，跳过 PDF 测试")

        # 验证函数存在
        from pdf_slicer import pdf_to_images, pdf_page_count
        assert callable(pdf_to_images)
        assert callable(pdf_page_count)
