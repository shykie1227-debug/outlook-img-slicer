# DESIGN.md - Outlook 长图助手界面与交互规范

当前版本使用稳定 `V6/PySide + Python` 原生桌面架构。界面目标不是“炫”，而是让非技术用户打开后按顺序完成：导入图片 → 检查切图 → 添加按钮链接 → 创建 Outlook 草稿或保存切图。

## 1. 产品定位

- 面向经典 Outlook 用户，优先保证长图邮件在 Outlook Word 引擎中稳定显示。
- 所有图片处理、HTML 生成、Outlook 草稿创建均在本地完成。
- 不自动发送邮件，只打开 Outlook 编辑窗口让用户二次检查。

## 2. 主流程

1. 拖入或选择图片/PDF/PPT/PSD 等源文件。
2. 工具自动解析尺寸并按邮件宽度生成预览。
3. 用户可手动调整切图位置，避免文字、按钮、二维码被切断。
4. 用户可在图片区域添加可点击按钮/热区链接。
5. 用户选择：
   - `在 Outlook 中创建邮件`：生成 CID 图片附件 + HTMLBody 草稿。
   - `复制图片（兼容方式）`：写入 Windows CF_HTML 剪贴板。
   - `保存切图`：导出切片图片，供手动检查或备用。

## 3. 视觉风格

- 背景：浅灰白，减少视觉压力。
- 主色：蓝色，表示主要动作和选中状态。
- 风格：现代 Windows 桌面工具，胶丸按钮、清晰留白、状态提示靠近操作区。
- 字体：优先 `Microsoft YaHei UI` / `Segoe UI`，中文清晰可读。

## 4. 交互原则

- 主按钮在没有图片或处理未完成时必须禁用，避免误操作。
- 错误提示使用用户能理解的语言，不暴露长堆栈。
- 对新版 Outlook 给出明确提示：新版 Outlook 不支持 COM 自动化，需要经典 Outlook。
- 创建邮件前不发送，创建后由用户在 Outlook 中检查和手动发送。
- 调整切图/添加链接属于高级操作，但入口应可见，并提供引导说明。

## 5. Outlook 渲染约束

Outlook 使用 Word 引擎渲染 HTML，和浏览器不同。当前实现必须遵守：

- 普通长图优先使用稳定的直接 `<img>` 堆叠路径。
- 普通长图路径不强写 HTML `height` 属性，减少 px/pt 换算产生的缝隙。
- 热区物理切片路径必须让 `<tr>`、`<td>` 与 `<img>` 的像素高度严格一致。
- 带链接热区的行独立处理，避免共享复杂 grid 导致错位。
- 生成 Outlook 草稿时使用 CID 附件，不依赖 base64 内联图片。
- 复制 HTML 路径使用 CF_HTML，以提升经典 Outlook 粘贴稳定性。

## 6. 防呆设计

- 输入宽度必须限制在合理范围，避免生成超宽邮件。
- 空文件、损坏文件、非 Windows Outlook 自动化环境必须给出可执行提示。
- 保存切图目录失败、附件添加失败、剪贴板写入失败都必须明确提示。
- 构建产物使用英文 ASCII 文件名，降低 Windows 脚本和共享目录乱码风险。

## 7. 当前资源约定

- 图标位于 `icons/`，彩色填充风格（24x24 viewBox，stroke-width: 2，stroke-linecap/linejoin: round）。
- 禁止 `currentColor`（Qt SVG 渲染不支持），禁止 `linearGradient`、`feDropShadow` 等滤镜。
- 每个图标使用独立主题色（fill 或 stroke），白色变体使用 `fill="#ffffff"` 或 `stroke="#ffffff"`。
- 禁止圆形底座——直接用彩色路径，避免缩放后拥挤。
- 白色变体用于 Primary 按钮（蓝底），命名 `*-white.svg`。
- 文件夹类图标（upload-cloud、folder-open）使用黄色拟物风格（`#f6c744` 主体 + `#e5a800` 翻盖）。
- 图标清单（13 个）：`upload-cloud`(folder)、`rotate-ccw`、`scissors`、`mouse-pointer-click`、`mail-white`、`arrow-down-to-line`、`clipboard-copy`、`image`、`check`、`check-white`、`arrow-down-to-line-white`、`palette`、`folder-open`。
- 桌面入口位于 `desktop/main.py`。
- 构建入口位于根目录 `build.py`，实际调用 `desktop/build.py`。
- Windows 文件版本信息位于 `desktop/version_info.txt`。

## 8. 精确尺寸规范（main.py ↔ ui-preview.html 统一）

以下尺寸为 main.py 代码与 ui-preview.html 预览的共同标准，修改时两边必须同步。

### 按钮

| 类型 | 高度 | 字号 | 图标尺寸 | 字重 | 圆角 |
|------|------|------|----------|------|------|
| Primary | 42px | 13px | 18px | 700 | 999px |
| Secondary | 42px | 12px | 16px | 500 | 999px |
| Ghost | 32px | 11px | 16px | 400 | 999px |

### 图标

| 用途 | SVG viewBox | Qt 渲染尺寸 | HTML 显示尺寸 |
|------|-------------|-------------|---------------|
| 拖放区文件夹 | 24x24 | 56x56 px | 56px |
| Ghost 按钮图标 | 24x24 | 16x16 px | 16px |
| Primary 按钮图标 | 24x24 | 18x18 px | 18px |
| Secondary 按钮图标 | 24x24 | 16x16 px | 16px |
| 复选框图标 | 24x24 | 16x16 px | 16px |

### 复选框

- 指示器尺寸：16x16 px，圆角 4px
- 选中态背景：`#0065fd`，白色对勾
- 未选中背景：`#f9f9fa`，边框 `#e7eaef`

### 输入框

| 类型 | 高度 | 字号 | 圆角 |
|------|------|------|------|
| 邮件宽度输入 | 32px | 11px | 8px |
| 邮件标题输入 | 36px | 12px | 8px |

### 窗口

- 默认宽度：760px；窗口可缩放，最小宽度由响应式布局约束
- 主窗口、切线编辑器、热区编辑器和导出弹窗统一缩放字体、图标、控件、圆角、内边距与间距（0.82–1.35）
- 标题栏高度：40px
- 内容内边距：20px 左右，14px 下，16px 上
- 组件间距：8px

### 布局结构（3 步分区）

```
[标题栏 40px]
[应用标题 + 副标题]
[引导药丸：1 放入文件 → 2 调整切线/添加链接 → 3 创建邮件]

[Step 1: 放入文件]
  ├─ 拖放区（56px 文件夹图标 + 标题 + 提示）
  └─ 工具栏行：重置 | 邮件宽度输入 px │ 导出图片 │ 避开文字切图

[Step 2: 编辑切片与链接]
  └─ 工具栏行：复制图片（兼容方式） | 调整切图位置 | 添加可点击按钮

[Step 3: 检查并输出]
  ├─ 邮件标题输入框
  ├─ 邮件品质下拉
  ├─ 状态提示
  └─ 底部按钮行：在 Outlook 中创建邮件（Primary）| 保存切图（Secondary）

[版本号 V6.3.0 + 作者]
```

### Ghost disabled 态

- 只用 `opacity: 0.4`（HTML）/ `opacity: 0.5`（Qt QSS）
- 不改文字颜色，不改背景色

### 版本号同步

版本源和可执行文件属性必须同时更新：
1. `desktop/main.py` → `VERSION = "x.y.z"`
2. `desktop/version_info.txt` → `FileVersion` / `ProductVersion`
3. `desktop/ui-preview.html` → `<title>` 和 `.app-title`

随后运行发布一致性测试，核对 README、SPEC、HANDOFF、TEST_PLAN、CHANGELOG、
构建清单和最终发布文件名，不能只依赖上述三个版本源文件。
