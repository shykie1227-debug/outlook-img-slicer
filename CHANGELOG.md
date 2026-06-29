# 更新日志（CHANGELOG）

记录 Outlook 长图助手的所有重要变更。

## V6.0.0 - 2026-06-30

### 重大变更
- **架构完全重写**：从 PySide6 (Qt6) 迁移到 Electron 30 + React 18 + Vite + TypeScript
- **三层架构**：Electron 主进程 + Vite/React 18 渲染进程 + Python Sidecar 子进程
- **Python Sidecar 通过 stdio JSON-RPC 通信**，V5 拆图/Outlook COM 能力 100% 复用
- **打包格式**：从单 .exe 改为 NSIS 安装器（~180MB，含 Chromium 运行时）

### 新增功能
- **safe-file 自定义协议**：`safe-file:///abs/path.png` 安全预览本地图片（白名单 8 种图片格式）
- **暗/亮主题切换**：ThemeSwitcher 组件，同步 `<html class="dark">`
- **Framer Motion 转场动画**：步骤切换 0.2s 淡入淡出
- **Zustand 全局状态管理**：替代散落的 10+ useState
- **DropZone 集成系统级文件对话框**：`window.api.openImage()` 调用 `dialog.showOpenDialog`
- **`webUtils.getPathForFile`** 安全方式获取 File 对象 OS 路径
- **ImagePreview 组件**：在主界面显示原图
- **保存 HTML 按钮**：拼装结果可保存为独立 .html 文件

### 修复
- 修复 V5.0.2 已知的小数 px → 1px 缝隙问题（V5 协议保持）
- 修复 Phase 1 协议 bug：Python 读 `type` 而 TS 发 `method`（在 sidecar-manager 加兼容层）
- 修复 EventEmitter 无 error 监听时同步抛异常的边角问题

### 内部改进
- **3 层测试体系**：Python 126 + Electron 42 + App 78 = 246 个测试
- **electron-builder NSIS 打包**：必须 Windows 构建，含 PyInstaller sidecar_server.exe
- 完整 TypeScript 严格模式（`noUncheckedIndexedAccess`）
- TDD 严格遵循（red-green-refactor）

### 升级提示
- V5 → V6 数据不兼容（V6 没用 PySide6 配置文件）
- 需重新在 Windows 上打包：见 [docs/v6-build-guide.md](docs/v6-build-guide.md)
- macOS / Linux 可开发但 Outlook 集成不可用

### 已知限制
- 未代码签名，Windows SmartScreen 会拦截（点"更多信息"放行）
- 仅支持 Windows 目标平台
- Electron 30 + jsdom 22 + vitest 1.6 测试栈有跨上下文问题，App.test.tsx 改为 helper 单元测试

## V5.0.3 - 2026-06-30

### 修复
- 修复 V5 窗口标题栏 + 任务栏无图标（V5 main.py 缺 `app.setWindowIcon()`）
- 修复 V6 electron-builder 打包后无窗口图标（`createMainWindow` 缺 `icon` 选项 + electron-builder.yml 缺 `icon.ico` extraResources）

## V5.0.2 - 2026-06-29

### 修复
- 修复长图嵌入 Outlook 后段间 1px 缝隙
- 修复长图嵌入 Outlook 后按钮与图片错位

## V5.0.0 - 2026-06-29

### 新增
- 完整 Outlook 长图助手（PySide6 UI）
- 支持 PNG/JPG/BMP/WebP/GIF/PDF/PPT/PSD
- 5 种邮件宽度预设
- Outlook COM 集成（仅 Windows）
- 拼装 HTML 算法（v3 协议）
- 单 .exe 打包（PyInstaller）

## V4.x

历史版本，见 `release-artifacts/v4.9.4-notes.md` 等。

---

## 版本管理

- 主版本：架构重大变更
- 次版本：新功能
- 修订号：Bug 修复

每次发布同步更新：
- `package.json` version
- `electron/package.json` version
- `app/package.json` version
- 本文件
- `test.md` 添加版本段
- `release-artifacts/` 添加 `v6.0.0-notes.md`
