# LOCAL_RULES.md - 本仓库运行原则

> **本文件仅适用于本仓库（outlook-img-slicer）**
> 用户（王萧铭）于 2026-06-01 明确声明：完全不联网，不上传，完全本地运行。

---

## 🔒 硬性约束

### 1. 不联网

- ❌ **禁止** 主动调用 `pip install` / `npm install` / `gh release download` / curl / wget 任何外网
- ❌ **禁止** 访问 GitHub API / PyPI / npm registry / 任何 HTTP(S) 外网地址
- ✅ **允许** 本地局域网内操作（如 Windows 共享盘 SMB、本地 PyPI 镜像）
- ✅ **允许** 使用本地已下载好的离线包 / wheel

### 2. 不上传

- ❌ **禁止** `git push` 到 origin 远程（即使有 GitHub remote）
- ❌ **禁止** 提交到任何云端代码托管平台
- ❌ **禁止** 上传 Release Asset / Issue / Wiki / Discussion
- ✅ **允许** 本地 Git 提交（`git commit`）
- ✅ **允许** 用户明确说「推送到 GitHub」时，**单次授权内** push 一次

### 3. 不外发

- ❌ **禁止** Outlook 邮件自动发送（即使配置了 outlook_sender）
- ❌ **禁止** 调用 create_email_with_images().Display() 后自动点「发送」
- ✅ **允许** 打开 Outlook 邮件窗口（mail.Display()）让用户手动检查后点发送
- ✅ **允许** 复制 HTML 到剪贴板

### 4. 不收集

- ❌ **禁止** 收集用户使用数据 / 埋点 / telemetry
- ❌ **禁止** Heartbeat 推送 / 飞书机器人外发（除非用户明确启用）
- ✅ **允许** 本地日志写入（log file / print）

---

## 📋 触发检查表（每次任务执行前自检）

每次接到本仓库的修改任务时，先自检：

```
□ 这个任务需要联网吗？（如自动下载依赖）→ 是 → 先停下，确认本地有离线包
□ 这个任务需要 push 远程吗？→ 是 → 先停下，等用户明确说「push」
□ 这个任务需要调用 outlook_sender 真实发送吗？→ 是 → 仅 Display() 不 Send()
□ 这个任务需要上传文件到任何云吗？→ 是 → 先停下
□ 都没勾 → 正常执行本地 git commit
```

---

## 🚨 误操作修复指引

如果 AI 不小心做了以下事情：
1. `git push` → 立刻告知用户，提供 `git reset --hard HEAD~N` 撤销指引
2. 联网下载 → 立刻告知用户下载内容
3. 真实发送邮件 → 立刻告知用户邮件内容
4. 上传文件 → 立刻告知用户上传位置

---

## 🛡 与 SOUL.md 的优先级关系

- SOUL.md 说「不轻易求助」「不需每步确认」「自主决策」是默认模式
- 本 LOCAL_RULES.md 的「联网/上传/外发」是**例外**——必须先确认
- 冲突时，**本规则优先**（保护用户数据 > 自动化效率）

---

## 📅 原则确立时间

- 2026-06-01 由用户（王萧铭）口头声明
- 已同步至 MEMORY.md（永久记录）
- 本规则永久生效，除非用户主动撤销
