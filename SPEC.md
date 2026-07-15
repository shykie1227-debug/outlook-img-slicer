# SPEC.md - Outlook 长图助手产品与技术规格

> 当前版本：V6.3.0
> 当前架构：稳定 V6/PySide 桌面应用 + Python 图像处理 + 经典 Outlook COM
> 目标平台：Windows / 经典 Outlook

## 1. 产品目标

用户把长图、PDF、PPT 或 PSD 拖入工具后，可以本地生成适合经典 Outlook 的邮件内容，避免长图被 Outlook 截断、压缩、错位或出现切片缝隙。

核心原则：

- 打开即可用，不要求用户理解 HTML 或 Outlook 限制。
- 运行时完全本地处理，不上传用户文件。
- 只创建 Outlook 草稿，不自动发送邮件。
- 优先保证经典 Outlook 渲染稳定，而不是追求浏览器式复杂布局。

## 2. 用户主流程

1. 用户拖入或选择源文件。
2. 工具读取文件信息并生成预览。
3. 用户可设置邮件宽度，默认宽度由界面配置提供。
4. 用户可手动调整切图位置，避免文字、二维码、按钮被切断。
5. 用户可添加可点击按钮/热区链接。
6. 用户选择输出方式：
   - `在 Outlook 中创建邮件`：生成 CID 附件和 HTMLBody，并调用 `mail.Display(False)` 打开草稿。
   - `复制图片（兼容方式）`：写入 Windows CF_HTML 剪贴板，链接可靠性低于 CID 草稿路径。
   - `保存切图`：导出切片图片到本地。

## 3. 功能规格

### F1 文件导入

支持：

- JPG / JPEG / PNG / BMP / WebP / GIF
- PDF
- PPT / PPTX
- PSD / PSB

边界要求：

- 空文件、损坏文件、未知格式必须给出中文错误提示。
- 同名文件、多实例处理不得互相覆盖。
- 临时文件必须在独立工作区生成。

### F2 自动切图

- 根据邮件宽度等比计算展示尺寸。
- 对过高图片自动切片。
- 尽量避开明显文字区域。
- 每片高度必须限制在安全范围内，避免 Outlook 显示异常。
- 支持后续通过 `desktop/cut_editor.py` 手动调整切线。

### F3 手动调整切图位置

- 用户可以进入切图编辑器查看当前切线。
- 支持拖动切线。
- 必须防止切片过小、过大、重叠或越界。
- 保存后重新生成切片和预览。

### F4 可点击按钮/热区

- 用户可以在图片上框选区域并填写链接。
- 热区通过 `clickable_map.py` 建模。
- `hotspot_slicer.py` 根据热区做最小必要切片。
- Outlook HTML 不能使用一个共享全局 grid，以免出现错位和缝隙。

### F5 Outlook 草稿创建

- 仅支持经典 Outlook COM 自动化。
- `outlook_sender.py` 使用 `Outlook.Application` 创建邮件。
- 图片通过 CID 附件引用。
- 只允许 `mail.Display(False)`，禁止 `mail.Send()`。
- 新版 Outlook 不支持 COM 时，必须提示用户切回经典 Outlook，或使用复制/保存路径。

### F6 复制 HTML

- `clipboard_html.py` 生成 Windows CF_HTML。
- 中文内容的 offset 必须按 UTF-8 字节计算。
- 复制路径可以使用 base64 自包含图片，方便网页邮箱或手动粘贴。

### F7 保存切图

- 允许用户选择保存目录和格式。
- 保存失败要说明目录权限、磁盘空间或文件占用等可能原因。
- 保存切图不触发 Outlook，也不发送邮件。

## 4. 当前模块结构

```
outlook-img-slicer/
├── desktop/main.py                 # 主窗口、用户流程、状态管理
├── desktop/cut_editor.py           # 手动切图位置编辑
├── desktop/hotspot_editor.py       # 热区/按钮链接编辑
├── desktop/export_dialog.py        # 保存切图格式选择
├── desktop/build.py                # PyInstaller 构建
├── desktop/outlook_img_slicer.spec # PyInstaller 配置
├── desktop/version_info.txt        # Windows 文件版本
├── icon.ico                        # Windows 窗口/EXE 图标
├── image_slicer.py                 # 图片检测、切片、临时工作区
├── html_assembler.py               # Outlook HTML / 复制 HTML 生成
├── hotspot_slicer.py               # 热区最小切片
├── clickable_map.py                # 热点数据结构
├── clipboard_html.py               # CF_HTML 生成
├── outlook_sender.py               # Outlook COM 草稿创建
├── image_safety.py                 # 邮件体积/安全检查
├── pdf_slicer.py                   # PDF 转图片
├── ppt_slicer.py                   # PPT/PPTX 转图片
├── psd_slicer.py                   # PSD/PSB 转图片
└── tests/                          # 自动化测试
```

## 5. Outlook HTML 兼容规则

Outlook 使用 Word 引擎，不等同于浏览器。必须遵守：

- 普通长图使用稳定的连续 `<img>` 堆叠。
- 不给普通切片强写 HTML `height` 属性。
- 带链接热区的横向段使用最小局部结构。
- 不把所有按钮边界扩散为全局网格。
- 不依赖外链图片、远程 CSS、远程字体。
- CID 草稿路径优先保证经典 Outlook 可见。

## 6. 构建规格

- 根入口：`build.py`
- 实际构建：`desktop/build.py`
- spec：`desktop/outlook_img_slicer.spec`
- VM 构建入口：`vm_start_build.ps1`
- VM 构建脚本：`vm_build.ps1`
- 输出文件名：`OutlookImgSlicer-V6.3.0.exe`
- 每次构建生成 `build-manifest.json`，包装脚本必须校验其中的产物路径与 SHA-256。
- EXE 内部文件名：`OutlookImgSlicer.exe`
- 图标来源：根目录 `icon.ico`，界面 SVG 来源为 `icons/`

构建产物必须使用英文 ASCII 文件名，避免共享目录和 Windows 系统编码导致乱码。

## 7. 验收范围

自动化验收：

- `python3 -m pytest tests/ -q`
- `python3 -m py_compile build.py desktop/*.py image_slicer.py html_assembler.py outlook_sender.py clipboard_html.py clickable_map.py hotspot_slicer.py image_safety.py pdf_slicer.py ppt_slicer.py psd_slicer.py`
- `git diff --check`

人工验收：

- 打开 EXE。
- 上传一张普通长图。
- 调整邮件宽度。
- 手动移动切图线。
- 添加一个可点击按钮链接。
- 复制 HTML 到经典 Outlook。
- 在经典 Outlook 中创建草稿。
- 保存切图到本地目录。

## 8. 红线

- 禁止运行时联网、上传、遥测、自动更新。
- 禁止自动发送邮件。
- 禁止恢复旧不可用架构。
- 禁止为了界面美观破坏 Outlook 渲染稳定性。
