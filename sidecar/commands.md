# Sidecar IPC 协议契约（V6.0.0）

> **单一事实源（Single Source of Truth）**
> 本文档与 `electron/types.ts`、`electron/sidecar-manager.ts`、`sidecar/sidecar_server.py` 严格同步。
> 任何修改必须同时更新这三处，并在 PR 描述中说明。

---

## 一、传输协议

- **传输：** stdio JSON-RPC 风格
- **请求方向：** Electron 主进程 → Sidecar（stdin）
- **响应方向：** Sidecar → Electron 主进程（stdout）
- **心跳方向：** Sidecar → 主进程（stdout，每 3 秒）
- **行分隔：** `\n`（每行一个 JSON 对象）
- **Python 启动参数：** `-u`（强制无缓冲 stdout）

### 启动握手

Sidecar 进程启动后第一行 stdout 必须输出：

```json
{"ready": true}
```

### 心跳

Sidecar 每 3 秒输出一行：

```json
{"ping": 1700000000.123}
```

主进程 10 秒未收到心跳视为 Sidecar 死亡，触发 SIGKILL + 重启。

### 请求

```json
{"id": "<uuid>", "method": "<command>", "params": {...}}
```

### 响应

成功：
```json
{"id": "<uuid>", "ok": true, "result": {...}}
```

失败：
```json
{"id": "<uuid>", "ok": false, "error": "FileNotFoundError: /tmp/missing.png"}
```

---

## 二、命令清单（11 个）

> 命名约定：所有命令名使用 `camelCase` 或 `dot.case`，**不使用 snake_case**。
> IPC 通道名转换规则：`method.replace(/\./g, ":")`，例 `image.info` → `image:info`

### 1. `image.info`

获取图片基本信息。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | ✅ | 图片绝对路径 |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `width` | number | 像素宽度 |
| `height` | number | 像素高度 |
| `format` | string | `PNG` / `JPEG` / `BMP` / `WEBP` 等 |
| `mode` | string | `RGB` / `RGBA` / `L` 等 |
| `size_bytes` | number | 文件字节数 |

### 2. `image.safetyCheck`

检查图片是否安全（长宽比 / 像素总数）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | ✅ | 图片绝对路径 |
| `max_edge` | number | ❌ | 单边最大像素（默认 8000） |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `is_safe` | boolean | 是否安全 |
| `width` | number | 实际宽度 |
| `height` | number | 实际高度 |
| `reason` | string? | 不安全时说明原因 |

### 3. `image.slice`

把图片按最大高度切片。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | ✅ | 原图绝对路径 |
| `max_h` | number | ✅ | 单切片最大高度（像素） |
| `max_w` | number | ❌ | 单切片最大宽度（默认无限） |
| `mode` | `"fixed" \| "smart"` | ❌ | 切片模式（默认 `fixed`） |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `slices` | Array | 切片列表，每项含 `path` / `width` / `height` / `index` |

### 4. `pdf.toImages`

PDF 拆为图片。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | ✅ | PDF 绝对路径 |
| `dpi` | number | ❌ | 渲染 DPI（默认 150） |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `pages` | Array | 每页含 `path` / `width` / `height` / `index` |

### 5. `pptx.toImages`

PPTX 拆为图片（每页一张）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | ✅ | PPTX 绝对路径 |

**响应 result：** 同 `pdf.toImages`。

### 6. `psd.toImage`

PSD 展平为 PNG。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | ✅ | PSD 绝对路径 |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `image_path` | string | 展平后的 PNG 路径 |
| `width` | number | 像素宽度 |
| `height` | number | 像素高度 |

### 7. `html.assemble`

把切片拼装为 Outlook HTML（含热区）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `slices` | Array | ✅ | 切片列表，每项含 `path` / `width` / `height` / `href?` / `alt_text?` / `sort_key?` / `original_width?` |
| `width` | number | ✅ | 目标显示宽度（默认 650） |
| `hotspots` | Array | ❌ | 热区列表（V5 兼容格式） |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `html` | string | Outlook HTML 字符串 |
| `cid_files` | object | cid → 绝对路径 映射 |

### 8. `html.clipboard`

把 HTML 转为 CF_HTML 剪贴板格式。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `html` | string | ✅ | HTML 字符串 |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `cf_html` | string | CF_HTML 字节流 |
| `cf_html_size` | number | 字节数 |

### 9. `outlook.createDraft`（⚠️ 仅 Windows）

调用 pywin32 COM 创建 Outlook 草稿邮件（仅 `Display()`，绝不 `Send()`）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `html` | string | ✅ | 邮件 HTML 正文 |
| `subject` | string | ✅ | 邮件主题 |
| `cid_files` | object | ✅ | cid → 绝对路径 映射 |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `mail_id` | string | Outlook 内部 ID |
| `subject` | string | 实际主题 |
| `opened` | boolean | 草稿窗口是否成功弹出 |

**非 Windows 平台：** 返回 `{"ok": false, "error": "Outlook 仅支持 Windows 平台"}`。

### 10. `outlook.copyClipboard`（⚠️ 仅 Windows）

把 CF_HTML 写入系统剪贴板（Outlook 自动识别）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `cf_html` | string | ✅ | CF_HTML 字节流 |

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `ok` | true | 写入成功 |

**非 Windows 平台：** 返回 `{"ok": false, "error": "..."}`。

### 11. `sidecar.status`

查询 Sidecar 当前状态（**不调用 Python，由主进程 SidecarManager 直接返回**）。

**params：** `{}`（空对象）

**响应 result：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `pid` | number | Python 进程 PID（未启动为 0） |
| `platform` | string | 操作系统（`win32` / `darwin` / `linux`） |
| `uptime_seconds` | number | 启动后秒数（未启动为 0） |
| `last_ping` | number? | 最近心跳时间戳（ms），未收到过为 null |
| `is_alive` | boolean | 是否存活 |

---

## 三、错误约定

| 错误来源 | 抛出 | 示例 |
|---|---|---|
| `params` 字段类型错误 | `TypeError` | `TypeError: path must be str, not int` |
| 文件不存在 | `FileNotFoundError` | `FileNotFoundError: /tmp/missing.png` |
| 字段缺失 | `KeyError` | `KeyError: 'path'` |
| Outlook 失败（非 Windows） | `RuntimeError` | `RuntimeError: outlook.createDraft 仅支持 Windows` |

所有 Python 异常会被 Sidecar 捕获并转换为 `{"ok": false, "error": "<message>"}`。

---

## 四、临时目录清理

PDF / PPT / PSD 拆页产生的临时目录会被 Sidecar 记录在 `_sidecar_temp_dirs` 集合中。
Sidecar 主进程退出时（`main()` 收尾）会调用 `shutil.rmtree` 清理全部。
主进程 `stop()` 时会通过 SIGTERM 触发 Sidecar 退出 → 触发清理。
