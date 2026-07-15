# LOCAL_RULES.md - 本仓库运行原则

> **本文件仅适用于本仓库（outlook-img-slicer）**
> 用户于 2026-06-01 明确声明：**构建成功的 exe 在其他电脑运行时** 完全不联网、不上传、完全本地。
> **开发期 / 构建期 / 本机测试期 允许联网**（pip install / git push / 下载依赖等都正常进行）。

---

## 版本号规则

- 当前版本从 `4.8` 开始。
- 小改动按 `4.81`、`4.82`、`4.83` 递增。
- 大改动直接升到 `4.9`、`5.0`、`5.1`、`5.2`。
- 修改版本号时同步更新 `main.py` 的 `VERSION` 和 `version_info.txt` 的 Windows 文件版本信息。

---

## 🔒 硬性约束（仅针对 exe 在其他电脑运行时）

### 1. exe 运行时不联网

- ❌ **打包后 exe 运行时** 禁止 访问任何 HTTP(S) / WebSocket / FTP / SMTP
- ❌ **exe 运行时** 禁止 检查更新 / 报告使用数据 / 任何 telemetry
- ❌ **exe 运行时** 禁止 自动从 CDN 下载字体/图标/图片/JS bundle
- ❌ **exe 运行时** 禁止 调用任何云端 API / 云服务
- ✅ **开发/构建/测试期** 允许联网（pip install / curl / wget / 任何下载都正常）

### 2. exe 运行时不上传

- ❌ **exe 运行时** 禁止 上传任何用户文件/数据到云
- ❌ **exe 运行时** 禁止 同步到云盘 / 云存储 / iCloud
- ✅ **开发/构建/测试期** 允许上传（git push / Release Asset / gh release 等都正常）

### 3. exe 运行时不外发

- ❌ **exe 运行时** 禁止 Outlook 邮件自动发送
- ❌ **exe 运行时** 禁止 调用 `mail.Send()` —— 只用 `mail.Display(False)` 打开邮件窗口
- ❌ **exe 运行时** 禁止 静默发送 / 定时发送 / 批量外发
- ✅ **开发/构建/测试期** 允许发送（如开发本机手动发邮件测试）

### 4. exe 运行时无外联（V4.6.1 承诺清单）

打包后的 Outlook.exe 在其他电脑运行时：
- ✅ Outlook 邮件：仅 `Display()`，不 `Send()`
- ✅ 无任何云端 API 调用代码
- ✅ 无任何 telemetry / 埋点代码
- ✅ 无任何自动更新 / 版本检查代码
- ✅ 所有图标、字体、图片内嵌在 exe 内
- ✅ 所有依赖打包在 exe 内（无运行时下载）

### 🔍 代码审计检查清单（确保打包后无外联）

- ❌ 源码中不能 import `requests` / `httpx` / `aiohttp` 等联网库
- ❌ 不能 import `socket` / `urllib.request` / `http.client` 等网络原语
- ❌ 不能 import `smtplib` / `ftplib` 等发送协议
- ❌ 不能调用 `webbrowser.open(外网URL)`
- ❌ 不能 `PIL.Image.open(url)` 远程图片
- ❌ 不能 `subprocess` 调用 `curl` / `wget` 等下载命令
- ❌ 不能有 `mail.Send()`（仅允许 `mail.Display()`）
- ✅ 所有用户可见资源（icon / 字体 / 模板）必须本地文件

### ✅ 开发/构建/测试期允许的操作

- ✅ `pip install` 安装依赖（联网拉 PyPI 包正常）
- ✅ `git push` 推送代码到 GitHub（构建后 release 也正常）
- ✅ 如检查历史版本，允许读取旧前端资料；当前发布架构不再依赖 Node/npm
- ✅ `curl` / `wget` 下载构建工具（Node.js / Rust / 7zip 等）
- ✅ 开发本机手动运行 exe 调试（仅测试）
- ✅ Outlook 本地测试发邮件（开发者本机操作）

---

## 🚨 误操作修复指引

如果 AI 不小心做了以下事情：
1. **在 exe 运行时引入了联网代码** → 立刻告知用户，提供 git revert 指引
2. **打包了含 `requests` / `socket` 等的代码到 exe** → 立刻告知用户，重新打包
3. **在 exe 中调用了 `mail.Send()`** → 立刻告知用户
4. **在 exe 中加入了 telemetry 埋点** → 立刻告知用户

---

## 🛡 与 SOUL.md 的优先级关系

- SOUL.md 说「不轻易求助」「不需每步确认」「自主决策」是默认模式
- 本 LOCAL_RULES.md 的「exe 运行时禁止联网」是**例外**——必须先确认
- 冲突时，**本规则优先**（保护用户数据 > 自动化效率）

---

## 📅 原则确立与修正记录

- 2026-06-01 16:00 确立：4 层面全禁（过度收紧）
- 2026-06-01 16:35 用户反馈校正：**仅 exe 在其他电脑运行时禁联网**，开发/构建期允许
- 已同步至 MEMORY.md（永久记录）
- 本规则永久生效，除非用户主动撤销
