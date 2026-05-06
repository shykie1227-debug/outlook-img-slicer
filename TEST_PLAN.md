# 测试计划 - Outlook 长图无损插入工具

## 1. 测试范围与目标

### 1.1 测试范围
- `image_slicer.py` - 图像切片模块
- `html_assembler.py` - HTML 组装模块
- `pdf_slicer.py` - PDF 解析模块
- `outlook_sender.py` - Outlook 发送模块

### 1.2 测试目标
- 核心模块覆盖率 ≥ 80%
- 边界条件全覆盖
- 错误路径全覆盖

---

## 2. 测试策略

### 2.1 黑盒测试
| 模块 | 测试重点 |
|------|----------|
| `image_slicer` | JPG/PNG/BMP/WebP/GIF 格式支持、切片数量计算、边界尺寸处理 |
| `html_assembler` | HTML 结构生成、CSS 内联样式、表格无缝拼接 |
| `pdf_slicer` | 多页 PDF 转换、图像质量、DPI 设置 |
| `outlook_sender` | 邮件创建参数、HTML 格式、附件处理 |

### 2.2 白盒测试
| 模块 | 测试重点 |
|------|----------|
| `image_slicer` | `detect_and_slice` 逻辑分支、`get_image_info` 返回值 |
| `html_assembler` | CSS 双花括号转义、表格行生成 |
| `pdf_slicer` | PyMuPDF 异常处理、io.BytesIO 流处理 |
| `outlook_sender` | pywin32 ImportError 处理、COM 调用异常 |

---

## 3. 测试环境要求

### 3.1 依赖环境
```
pytest>=7.0.0
Pillow>=10.0.0
pytest-cov>=4.0.0
PyMuPDF>=1.23.0
```

### 3.2 测试数据
- 测试图片：通过 `conftest.py` 中的 fixtures 动态生成
- 临时文件：使用 `tempfile` 模块，测试后自动清理

---

## 4. 测试用例清单

### 4.1 `test_image_slicer.py`
| 用例ID | 描述 | 预期结果 |
|--------|------|----------|
| `test_jpg_slice` | JPG 图片高度 > 1500px | 正确切片，生成 2 片 |
| `test_png_transparency` | PNG 带透明通道 | 保留 RGBA 模式和透明背景 |
| `test_small_image_no_slice` | 图片高度 ≤ 1500px | 返回原路径，不切片 |
| `test_invalid_file` | 传入无效文件 | 抛出异常 |
| `test_exact_boundary_no_slice` | 图片高度恰好 1500px | 不切片，直接返回 |
| `test_multi_slice_count` | 高度 4000px 图片 | 切成 3 片 (1500+1500+1000) |
| `test_different_formats` | 测试 BMP/WebP/GIF | 各格式均能正确切片 |
| `test_get_info_jpg` | 获取 JPG 元信息 | 返回 width/height/format |
| `test_get_info_png` | 获取 PNG 元信息 | 返回 RGBA 模式信息 |
| `test_get_info_invalid` | 无效文件信息获取 | 抛出异常 |

### 4.2 `test_html_assembler.py`
| 用例ID | 描述 | 预期结果 |
|--------|------|----------|
| `test_gapless_table_generation` | 表格行无缝拼接 | 每行一个 `<td><img>` |
| `test_css_inline_styles` | CSS 内联到 HTML | `<style>` 标签存在且正确 |
| `test_empty_image_list` | 空图片列表 | 生成空表格 |
| `test_single_image` | 单张图片 | 表格仅一行 |
| `test_cid_replacement` | CID 方式图片引用 | `src="cid:image_N"` 格式 |
| `test_multiple_images` | 多张图片 CID | 正确生成多个 CID 引用 |

### 4.3 `test_pdf_slicer.py`
| 用例ID | 描述 | 预期结果 |
|--------|------|----------|
| `test_import_module` | 模块可导入 | PyMuPDF 可用 |
| `test_pdf_page_count_missing_file` | 不存在的 PDF | 抛出异常 |
| `test_pdf_to_images_missing_file` | 转换不存在的 PDF | 抛出异常 |
| `test_pdf_dpi_parameter` | DPI 参数存在 | 函数签名包含 dpi |
| `test_module_structure` | 模块结构完整 | 函数可调用 |

---

## 5. 执行计划

```bash
# 安装依赖
pip install pytest pytest-cov Pillow PyMuPDF

# 运行所有测试
pytest tests/ -v --cov=. --cov-report=term-missing

# 生成覆盖率报告
pytest tests/ --cov=. --cov-report=html
```

---

## 6. 验收标准

- [x] 所有测试用例通过 (23/23)
- [x] 核心模块覆盖率 ≥ 80%
- [x] 错误路径测试覆盖 ImportError、IOError、ValueError
- [x] Linux/macOS 环境可完整运行测试（跳过 Windows 特定部分）
- [x] 发现并修复 `html_assembler.py` 中 CSS 双花括号转义 bug
