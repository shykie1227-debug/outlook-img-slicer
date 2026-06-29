# V6.0.0 Windows 打包指南

本文档说明如何在 **Windows** 环境下把 V6.0.0 Electron + Python Sidecar 应用打包成单一 NSIS 安装包。

> ⚠️ **必须在 Windows 上构建**
> 跨平台打包（macOS 打包 Windows exe）需要 Wine 等额外配置，强烈建议直接在 Windows 上构建。
> macOS / Linux 仅做开发与单元测试。

## 1. 前置条件

| 工具 | 版本 | 用途 |
|------|------|------|
| Node.js | ≥ 20 | Vite / electron-builder |
| Python | 3.10 | Sidecar 运行时 + PyInstaller |
| PyInstaller | ≥ 6.0 | 打包 Sidecar |
| Windows 10/11 | x64 | 目标平台 |

## 2. 一次性安装

```cmd
# 在项目根目录
npm install
pip install -r requirements.txt
pip install pyinstaller
```

## 3. 打包 Sidecar（关键步骤）

```cmd
npm run build:sidecar
```

产物：`sidecar/dist/sidecar_server/sidecar_server.exe`（约 30-50MB）

> PyInstaller --onefile 会把 Python 解释器和所有依赖打成一个单文件。
> 第一次构建较慢（2-5 分钟），后续增量较快。

## 4. 打包 Electron 渲染层 + 主进程

```cmd
npm run build
```

产物：
- `app/dist/index.html` + assets（前端）
- `electron/dist-electron/main.js` 等（主进程）

## 5. 打包安装程序

```cmd
npm run dist:win
```

electron-builder 会：
1. 把 `app/dist/` 放到 `resources/app/`
2. 把 `sidecar/dist/sidecar_server/sidecar_server.exe` 放到 `resources/sidecar/`
3. 把 `electron/dist-electron/*` 作为主程序
4. 生成 NSIS 安装器

产物：`release-artifacts/electron/Outlook 长图助手-V6.0.0-Setup.exe`

## 6. 验证

1. 双击安装 → 选目录 → 完成
2. 启动 "Outlook 长图助手" 桌面快捷方式
3. 验证 Sidecar PID 显示正常
4. 拖一张长图测试完整流程

## 7. 常见问题

**Q: 安装时 Windows Defender 报警？**
A: 未签名 exe 会被 SmartScreen 拦截。点"更多信息 → 仍要运行"。

**Q: 启动后 Sidecar 状态一直 "连接中..."？**
A: 检查 `resources/sidecar/sidecar_server.exe` 是否存在；
   检查 Python 依赖（pywin32、pyperclip、Pillow）是否完整打包。

**Q: 打包后体积超过 200MB？**
A: 正常。Vite bundle ~5MB + Python runtime ~30MB + Chromium ~150MB = ~185MB。
   如需瘦身：PyInstaller --exclude-module 排除未用模块。

**Q: macOS / Linux 用户能用吗？**
A: V6.0.0 仅支持 Windows。Outlook COM 仅 Windows 平台。
   macOS / Linux 可装但 Outlook.createDraft 会失败。

## 8. 文件清单

```
electron-builder.yml        # 打包配置
electron/main.ts             # 处理开发/打包路径切换
sidecar/dist/                # PyInstaller 产物（gitignore）
release-artifacts/electron/  # electron-builder 产物（gitignore）
```
