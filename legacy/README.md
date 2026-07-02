# 遗留代码目录

本目录存放 V5 及更早版本的遗留代码，仅供参考，不再维护。

## 目录结构

```
legacy/
└── v5-python-ui/          # V5 PySide6 单文件版本的 UI 代码
    ├── main.py            # V5 主程序入口（PySide6）
    ├── cut_editor.py      # 切线编辑器对话框
    ├── hotspot_editor.py  # 热区编辑器对话框
    ├── export_dialog.py   # 导出格式对话框
    ├── build.py           # V5 构建脚本
    ├── outlook_img_slicer.spec  # PyInstaller 配置
    ├── ui-preview.html    # 旧版 UI 预览
    └── version_info.txt   # 旧版版本信息
```

## V5 → V6 架构变化

V6 使用 Electron + React 重构，原 V5 的 Python 核心算法保留在项目根目录，通过 Sidecar 方式被 Electron 调用。

保留的核心模块（在项目根目录）：
- `image_slicer.py` - 图片切片核心算法
- `image_safety.py` - 图片安全检查
- `html_assembler.py` - HTML 组装
- `clipboard_html.py` - Windows 剪贴板 HTML
- `outlook_sender.py` - Outlook COM 集成
- `pdf_slicer.py` - PDF 处理
- `ppt_slicer.py` - PPT 处理
- `psd_slicer.py` - PSD 处理
- `hotspot_slicer.py` - 热区切片算法
- `clickable_map.py` - 热区数据结构
