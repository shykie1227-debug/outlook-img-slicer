# CHANGELOG

## V6.1.1 - 2026-07-09

### 架构整理

- 当前发布架构统一为 `PySide6 桌面界面 + Python 图像处理 + Outlook COM`。
- 清理旧 Electron / React / Node / sidecar 目录和构建配置，避免后续误走不可用架构。
- 将原稳定桌面代码从历史目录迁移到 `desktop/`，根目录 `build.py` 只作为发布入口转发。
- 构建产物统一为英文文件名：`OutlookImgSlicer-V6.1.1.exe`。

### 构建优化

- `vm_build.ps1` 改为仅构建桌面版 EXE，不再安装 Node 或执行前端构建。
- `build.ps1` / `build.bat` / GitHub Actions 同步指向 `desktop/dist/OutlookImgSlicer.exe`。
- PyInstaller spec 改为 `desktop/outlook_img_slicer.spec`，图标和版本信息从项目根/desktop 正确读取。

### 质量与回归

- 新增桌面发布入口测试，防止 Electron/sidecar 旧架构回流。
- 更新版本一致性测试，覆盖 `main.py`、`version_info.txt`、构建脚本和输出文件名。
- 保留 Outlook HTML 关键约束：普通长图走稳定 `<img>` 堆叠；热点区域独立切片，避免 Outlook 中错位或缝隙。

## V6.1.0 - 2026-07-08

- 回到稳定 Python 桌面架构，修复 Electron 方案下启动依赖、sidecar 未就绪、经典 Outlook 创建草稿不可用等问题。
- 恢复经典 Outlook COM 草稿路径：只调用 `mail.Display(False)`，不自动发送。
- 修复可点击按钮链接后长图不完整、复制 HTML 到 Outlook 不完整/错位的核心路径。

## V5.x

- 完整 PySide6 桌面工具。
- 支持长图切片、手动切图位置、热点链接、保存切图、经典 Outlook 草稿创建。
- 建立 Outlook Word 引擎兼容规则，重点避免图片间缝隙和链接热区错位。

## V4.x

- 早期桌面版和 Outlook HTML 兼容性探索版本。
