# Outlook 长图助手

一个给经典 Outlook 使用的 Windows 桌面小工具：把长图、PDF、PPT、PSD 等内容转成适合 Outlook 邮件正文的图片切片，并支持手动调整切图位置、添加可点击按钮链接、复制 HTML 或创建 Outlook 草稿。

当前发布架构：`稳定 V6/PySide 桌面界面 + Python 图像处理 + Outlook COM`。

## 主要能力

- 支持 JPG / PNG / WebP / GIF / BMP / PDF / PPT / PPTX / PSD / PSB。
- 自动切图并尽量避开文字区域，默认单张切片最大高度 1200px。
- 可手动调整切图位置，带最小/最大切片高度防呆。
- 可在图片按钮区域添加 URL，发送到经典 Outlook 后区域可点击。
- 可创建 Outlook 草稿窗口，但绝不自动发送邮件。
- 可复制 HTML，适合需要手动粘贴的场景。
- 全程本地处理，exe 运行时不联网、不上传。

## 用户使用

1. 打开 `OutlookImgSlicer-V6.4.1.exe`。
2. 拖入图片、PDF、PPT 或 PSD 文件。
3. 按需调整邮件宽度、手动切线或添加可点击按钮。
4. 点击“在 Outlook 中创建邮件”，在 Outlook 草稿窗口中检查后手动发送。

## 开发运行

```bash
python3 -m pip install -r requirements.txt
python3 desktop/main.py
```

## 回归测试

Windows / macOS 双端同一套命令（界面用例依赖 `QT_QPA_PLATFORM=offscreen`）：

```bash
python3 -m pytest tests/ -q
python3 -m compileall -q build.py desktop tests image_slicer.py html_assembler.py \
  outlook_sender.py clipboard_html.py clickable_map.py hotspot_slicer.py \
  image_safety.py pdf_slicer.py ppt_slicer.py psd_slicer.py
```

当前基线：**181 passed**。升版本号时必须同步 `desktop/main.py` 的 `VERSION`、
`desktop/version_info.txt`、`desktop/ui-preview.html` 以及 4 个测试文件里的版本断言
（`test_release_consistency.py`、`test_documentation_release_contract.py`、
`test_v620_release_contract.py`、`test_code_agent_guide.py`）。

## Windows 构建

在 Windows 上双击：

```text
build.bat
```

或在 PowerShell 里运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

输出：

```text
dist/OutlookImgSlicer-V6.4.1.exe
```

本地 Parallels Windows VM 构建入口：

```powershell
\\Mac\Home\outlook-img-slicer\vm_start_build.ps1 -SourceGitSha <40位提交SHA>
```

上面的共享目录是本地 Parallels 示例；发布构建必须传入当前源码的完整提交 SHA，
构建清单会据此校验 EXE 与源码一致。

## 项目结构

```text
outlook-img-slicer/
├── desktop/                    # PySide6 桌面界面与 PyInstaller 配置
│   ├── main.py                 # 主窗口和完整工作流
│   ├── cut_editor.py           # 手动切图编辑器
│   ├── hotspot_editor.py       # 可点击按钮/热区编辑器
│   ├── export_dialog.py        # 图片导出设置
│   ├── export_worker.py        # 后台导出与持续进度
│   ├── ui_scaling.py           # 编辑弹窗统一响应式缩放
│   ├── build.py                # PyInstaller 构建脚本
│   └── outlook_img_slicer.spec # 单文件 EXE 打包配置
├── image_slicer.py             # 图片切片与智能切图
├── pdf_slicer.py               # PDF 渲染
├── ppt_slicer.py               # PPT/PPTX 渲染
├── psd_slicer.py               # PSD/PSB 合成
├── hotspot_slicer.py           # 热区物理切片
├── html_assembler.py           # Outlook HTML 生成
├── clickable_map.py            # 可点击热区数据模型与校验
├── clipboard_html.py           # Windows CF_HTML
├── outlook_sender.py           # Outlook COM 草稿创建
├── image_safety.py             # 邮件体积与安全检查
├── verify_source_snapshot.py   # 构建前校验源码与提交一致
├── requirements.txt            # 运行与打包依赖
├── tests/                      # Python 回归测试
├── build.py                    # 根构建入口，委托 desktop/build.py
├── build.ps1 / build.bat       # Windows 手动构建入口
├── vm_build.ps1                # 本地 Windows VM 构建主流程
└── vm_start_build.ps1          # VM 内以分离进程启动构建（避免 exec 断连）
```

## 安全原则

- exe 运行时不访问网络。
- exe 运行时不上传用户文件。
- Outlook 只调用 `Display()` 打开草稿，不调用 `Send()` 自动发送。
- 用户必须在 Outlook 草稿窗口中自行检查并手动发送。

## 已知限制

- **SVG 导入在无 libcairo 的环境下会失败**。`image_slicer._convert_svg_to_png`
  先尝试 `cairosvg`，但其 `except` 只捕获 `ImportError`；实测缺少 libcairo 时
  `import cairosvg` 抛的是 `OSError`，不会被捕获，因此不会回退到可用的 `svglib`。
  修复方向：把该处 `except ImportError` 放宽为 `except Exception`。
- **PPT 需要本机渲染器**：优先用 PowerPoint COM（Windows），其次 LibreOffice
  （`soffice`，macOS/Linux）。两者都没有时会停止导出并给出提示，不做低保真降级。
- **仅支持经典 Outlook**：新版 Outlook（WebView2 内核）不在支持范围内。
- **一次只处理一个文件**：多图拖入「切图模式」时只处理第一张。
- **测试进程中的偶发段错误**：若测试进程里「文件名排序最靠前的 Qt 模块」构造
  `HotspotEditorDialog`，整套用例会段错误。已确认与产品代码无关，
  已在新测试中规避，根因待定位。
