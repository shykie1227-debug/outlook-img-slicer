# CHANGELOG

## V6.2.2 - 2026-07-14

### UI 布局重构
- 设置行从 QGridLayout 改为 QHBoxLayout，"导出图片"和"避开文字切图"紧挨在一起。
- 6 个按钮全部去掉前导空格，用 QSS padding + QHBoxLayout spacing 替代。
- _apply_responsive_layout 移除 settings grid 重建逻辑（QHBoxLayout 天然单行）。
- "合并导出长图"文案统一改为"导出图片"（main.py + ui-preview.html + 状态提示）。
- 勾选"导出图片"时弹出预览说明弹窗，告知操作流程和注意事项。
- 文档中"复制到 Outlook"统一改为"复制图片（兼容方式）"。

### 图标与尺寸统一
- 全部 13 个图标统一为 24x24 viewBox 彩色填充风格，去掉圆形底座避免缩放拥挤。
- 拖放区文件夹图标改为黄色拟物打开文件夹造型，渲染尺寸 56px。
- 重置按钮图标改为逆时针旋转箭头（teal），路径用贝塞尔曲线确保 Qt 渲染方向正确。
- 导出图片复选框添加 image 图标（16px）。
- Ghost 按钮图标统一 16px，Primary 按钮图标统一 18px。
- Ghost 按钮高度 34→32px，字号 12→11px；Primary 按钮高度 44→42px，字号 14→13px。
- DropZone 图标在 __init__/set_compact/_reset_drop_zone/_start_processing 四处全部从 44px 改为 56px。

### 交互优化
- 新增 Ctrl+Enter 快捷键创建 Outlook 邮件。
- 重置按钮在有切片时弹确认对话框，防止误操作丢失工作。
- ui-preview.html 全面重写，删除死的滑杆 CSS/JS，尺寸与 main.py 完全同步。

### 文档与规范
- DESIGN.md 新增第 8 节"精确尺寸规范"（按钮/图标/复选框/输入框/窗口尺寸表 + 布局结构图）。
- CODE-AGENT-GUIDE.md 新增第 8 节"布局结构"+快捷键表+复选框表+ui-preview.html 同步规则。
- 版本号同步检查项增加 ui-preview.html（main.py + version_info.txt + ui-preview.html 三处）。

### 功能改进
- 带链接切片按源图完整重组后一次缩放再切回，减少 Outlook 行边界重采样缝隙。
- 热区编辑改为事务式保存，取消或关闭窗口不会误改正式数据。
- 异步切图增加任务代际隔离与协作取消，不再强制终止线程或让旧结果覆盖新文件。
- 主界面补充发送图片质量选项、兼容复制说明、Windows UIA 标识和高 DPI 窗口约束。
- 构建生成带 SHA-256 的产物清单，Windows 脚本不再从可能残留的 dist 目录猜测 EXE。

## V6.2.1 - 2026-07-11

- 恢复 V6 顶部标题、引导与紧凑工具栏的视觉层级。
- “导出图片、避开文字切图”固定在邮件宽度右侧，不再掉到第二行。
- 编辑与输出按钮在窗口缩放时只调整宽度，始终保持单行。

## V6.2.0 - 2026-07-11

- 主界面整理为“放入文件、编辑切片与链接、检查并输出”单页三步流程。
- 工具设置在窄窗口下自动重排，保留 Qt 6 的 Windows Per-Monitor DPI 适配。
- 新增统一邮件渲染计划，锁定切片物理尺寸、显示尺寸、顺序、链接和 CID。
- Outlook HTML 声明 96 PPI，并继续保留普通长图连续图片稳定路径。
- 构建产物升级为 `OutlookImgSlicer-V6.2.0.exe`。

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
