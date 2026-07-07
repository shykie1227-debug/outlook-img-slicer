# 更新日志（CHANGELOG）

记录 Outlook 长图助手的所有重要变更。

## V6.0.3 - 2026-07-06

### 修复（EXE 启动失败）
- **sidecar_server.exe 未打包**：上次构建绕过了 PyInstaller 步骤，导致 EXE 内缺少 Python Sidecar，应用启动后无法连接后端。改用 vm_build.ps1 完整流程（Step 6 先构建 sidecar，Step 7 再打包 electron）。
- **preload 文件名不匹配**：main.ts 引用 `preload.mjs` 但 TypeScript 编译产物是 `preload.js`。导致 Electron 找不到 preload 脚本，渲染进程无法调用任何 API（白屏）。修正为 `preload.js`。
- **ES Module 冲突**：根 package.json 的 `"type": "module"` 导致 Electron 以 ES module 模式加载 CommonJS 编译的 main.js，引发 `exports is not defined` 错误。在 electron-builder.yml 的 `extraMetadata` 中覆盖为 `"type": "commonjs"`。

### 新增
- **vm_build.ps1 Node.js 自动安装**：VM 中缺少 Node.js 时自动下载 v20.18.0 LTS（华为云镜像）并静默安装。
- **vm_build.ps1 pip 中国镜像**：Python 依赖安装直接使用清华镜像，避免默认源下载超时。
- **vm_start_build.ps1 独立进程**：通过 Start-Process 启动构建脚本为独立进程，避免 prlctl exec 长时间运行断开。

## V6.0.2 - 2026-07-03

### 修复（关键 Bug）
- **长图发送 Outlook 错位**：`_build_v3_plain_image_stack` 移除 `height` HTML 属性。Outlook Word 引擎 px→pt 转换 (1px=0.75pt)，非 4 倍数高度产生小数 pt，Word 四舍五入后导致图片间 1px 错位，多片累积为可见偏移。回滚至 V3.0 验证过的稳定方案：只写 width，让 Outlook 按宽高比自动计算 height。
- **按钮切片发送 Outlook 破碎**：`_build_inline_segment` 从 V6.0.1 的 `<td>` + `display: block` 回滚为 `<span style="display: inline-block">` + `<a style="display: inline-block">`。V6.0.1 的 td 结构破坏了横向按钮布局。
- **按钮行间缝隙**：`_build_complex_inline_stack` 从 V6.0.1 的多 `<table><tr>` 结构回滚为单 `<div>` 容器。V6.0.1 每行独立 table 违反"单 <tr> + 单 <td>"约束，多 table 之间在 Outlook Word 引擎中产生 1px 缝隙。
- **Outlook 草稿图片不显示**：sidecar 新增 CID 模式 (`mode: "cid"`)。Outlook Word 引擎不支持 base64 内联图片，必须用 CID 附件。`onCreateDraft` 现在始终生成 CID 模式 HTML。
- **剪贴板字段名不匹配**：`html.clipboard` 返回 `cf_html_b64` 但 TypeScript 类型定义为 `cf_html`，导致 `outlook.copyClipboard` 接收不到数据。统一为 `cf_html`。
- **outlook.createDraft 参数错误**：sidecar 传 `cid_files` 给 `create_email_with_images`，但该函数不接受此参数。改为将 `cid_files` 字典转换为排序的 `image_paths` 列表。
- **App.tsx 数据流断裂**：4 处 `htmlAssemble` 调用未传 `sort_key` / `original_width`，导致 Python 端排序和宽度比例计算错误。

### 优化
- **构建脚本精简**：删除冗余的 `build_v6.py`、`build_v6.ps1`、`一键打包.bat`、`一键打包.ps1`、`一键打包说明.md`。仅保留 `build.bat` + `build.ps1`（一键构建，含国内镜像加速）。
- **输出目录统一**：electron-builder 输出从 `release-artifacts/electron/` 改为 `dist/`。构建后自动清理 dist 目录，仅保留 portable EXE。
- **types.ts 接口修正**：`AssembleParams.width` 改为 `display_w`（与实际运行时参数名一致），新增 `mode` 参数。

## V6.0.1 - 2026-06-30

### 修复
- **Web Interface Guidelines 合规**：装饰性 emoji 全部加 `aria-hidden="true"`（✂、V6.0.0 徽章、状态点、加载占位）
- **prefers-reduced-motion 支持**：App.tsx 加 `MotionConfig reducedMotion="user"`，Step 转场在用户启用系统级"减少动效"时自动降级
- **ImagePreview CLS 修复**：补 `width` / `height` 显式属性 + `aspectRatio` 占位 + `fetchpriority="high"`（above-the-fold 关键图）
- **焦点环**：所有按钮加 `focus-visible:ring-2 focus-visible:ring-sky-500`
- **键盘可达性**：DropZone 加 `onKeyDown` 处理 Enter/Space
- **ProgressBar ARIA**：加 `role="progressbar"` + `aria-valuenow/min/max/label`
- **SettingsPanel 表单**：补 `name` / `inputMode="numeric"` / `autoComplete="off"`
- **Windows 深色模式**：index.css 加 `color-scheme: light dark` / `html.dark { color-scheme: dark }`，select 元素显式 `text-slate-100`
- **transition-all 反模式**：ProgressBar / DropZone 改为 `transition-[width]` / `transition-[border-color,background-color,transform]`
- **aria-live 异步消息**：错误条、Sidecar 状态徽章加 `role="status" aria-live="polite"`
- **aria-expanded**：设置按钮加 `aria-expanded={showSettings}`
- **icon.ico 升级**：从 5 尺寸（16/32/64/128/256）扩展到 6 尺寸（+ 48），HiDPI 任务栏更清晰

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
