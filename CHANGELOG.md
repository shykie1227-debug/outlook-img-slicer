# CHANGELOG

## 未发布（post-V6.4.0）- 2026-09-24

### 收尾整理（不含功能变更）
- **删除死代码**（AST 全量扫描确认零引用后删除，共 195 行）：
  `html_assembler._build_cell` / `_build_image_row`（旧多 `<tr>` 链路残留，
  本次才真正删掉 —— V6.4.0 说明里只删了 `_build_complex_inline_stack`）、
  `get_cid_map`、`cleanup_all_tracked_temp_slices`；
  `hotspot_slicer.HotspotCutError` / `compute_cut_lines` / `build_stripe_assignments`；
  `ppt_slicer._ensure_pptx`（连同仅它使用的 `_presentation`）/ `_emu_to_px`；
  `desktop/main._btn_size`。
- **清理随之失效的 import**：`desktop/main.py` 的 `time`、`QFontMetrics`、
  `FMT_PNG`/`FMT_JPG`；`hotspot_slicer.py` 的 `HotspotMap`；`ppt_slicer.py` 的 `io`。
  （保留了仍被引用的 `PPT_RENDERER_UNAVAILABLE_HINT`。）
- **README**：新增「回归测试」与「已知限制」两节，补全项目结构中遗漏的
  `clickable_map.py` / `image_safety.py` / `verify_source_snapshot.py` /
  `vm_start_build.ps1` 等条目。
- **requirements.txt**：补充 `pdf2image`（需系统 poppler，故不默认引入）与
  `dulwich`（仅构建校验用）的说明注释，未改动实际依赖列表。
- **注释**：修正 `html_assembler.py` 中「待删除」的过时措辞（已删）；
  在 `image_slicer._convert_svg_to_png` 处标注 SVG 兜底失效的真实原因与修复方向。
- 清理本地临时产物：空的 `build/` 目录、`build_step.log`、`tests/_artifacts` 下的
  pytest basetemp 与 `__pycache__`（保留 `dist/` 内已发布 EXE 与证据截图）。
- 回归：全量 **178 passed**，`compileall` 通过，主窗口冒烟正常。

## V6.4.0 - 2026-09-23

### 缺陷修复：可点击按钮导致的邮件缝隙（结构性根修）
- **根因确认**：加可点击按钮后，邮件正文从「单 `<td>` 内连续 `<img>`」切换为
  「外层 `<td>` 内嵌一张多 `<tr>` 网格表」。实测一封 3 按钮邮件有 **9 条 `<tr>`**；
  Outlook 的 Word 引擎在 `<tr>` 之间始终插入约 1px 间距（本模块 V4.9.0 已记载
  该行为，V4.9.0 正是靠单 `<tr>` 根修过一次），行数越多缝隙越多。
- **根修方式**：把网格**转置成列结构**——取所有视觉行 X 边界的并集作为列，
  每列一个 `<td>`，列内用 `display:block` 连续堆叠该列的竖向片段，可点击片段
  用 `<a>` 包裹。整封邮件从此只有 **1 张 `<table>`、1 条 `<tr>`**，无嵌套表格、
  无 `colgroup`/`colspan`，与普通长图（用户实测无缝）的写法完全一致。
- materialize 阶段直接按「列 × 行」网格产出最终 PNG，物理尺寸与 HTML 声明严格
  一致；新增 `SliceItem.grid_col/grid_row` 标记网格坐标。
- 保留几何硬校验：某行各段宽度之和、各列宽度之和 != 邮件显示宽度时直接抛
  `ValueError`，不再静默产出错位 HTML。
- `build_render_plan` 与 `assemble_html` 共用同一份列优先顺序（`_ordered_grid_cells`），
  保证 Outlook 附件 CID 与正文 `cid:` 引用一一对应、不漂移、不重复。
- **代价（有意取舍）**：图片片数从"每行若干竖条"增加为"列 × 行"网格单元数
  （3 按钮示例 13 → 35 片），每片更小，总体积基本不变。
- 验证：3 种按钮布局（单按钮 / 同排 3 按钮 / 上下错列 2 按钮）下，
  从生成的 HTML 解码全部图片并按表格几何拼回，与原图逐像素差异 **0**。

### 新功能：手动调整切线可新增 / 删除单条切线
- 切线编辑器顶部新增「＋ 新增切线」「－ 删除切线」。
  新增：选中某条线时插到它下方居中处，否则插到当前最宽的区间中间；
  两侧都不会低于 80px 最小切片高度，空间不足时按钮置灰并明确提示。
  删除：删除当前选中的那条切线，未选中时按钮置灰。
- 「恢复自动切线」现在会一并丢弃用户新增 / 删除过的切线并重建，
  不再只是把旧切线挪回原位（旧实现在增删后数量对不上）。
- 汇总条改为两行显示切线总数、各片高度与切线位置；新增/删除后即时刷新。

### 缺陷修复：热区编辑器画布偏移与白边
- `ImageCanvas` 旧实现用「请求宽度」计算缩放比例，但 `Qt.KeepAspectRatio`
  实际返回的位图更小（请求 800 → 实得 797/799），且 `setMinimumSize` 用的是
  请求尺寸；QLabel 默认 `AlignLeft | AlignVCenter` 又把位图垂直居中。
  三者叠加导致短切片（900x140）的位图原点比画布原点低 **16px**、右侧留 **49px** 白边，
  `paintEvent` 按 (0,0) 画热区、鼠标按 (0,0) 换算坐标，用户看到的按钮框与
  实际存储坐标对不上。
- 修复：缩放比例与画布几何一律按**实际位图尺寸**回填（新增
  `ImageCanvas.apply_scaled_pixmap`），对齐强制 `AlignLeft | AlignTop`，
  位图原点与画布原点重合；窗口缩放（`ResponsiveDialogMixin` 改写 minimumSize 后）
  也会重新收敛。

### 旧结构清理
- 删除已被取代的旧链路代码：`_build_complex_inline_stack`（单表多 `<tr>` 版本）、
  `_build_cell`、`_build_image_row`。

### 质量保障
- 新增切线增删回归（含顺序有序、最小高度约束、空间不足提示、
  重置还原数量、提交结果不含被删切线、最小窗口宽度不截断）。
- 新增画布原点对齐回归（短切片 / 长切片 / 宽度变化后 / 坐标换算往返 /
  对话框 resize 路径确实委托给 `apply_scaled_pixmap`）。
  该组用例在修复前代码上 **5 项全红**，失败信息即缺陷签名
  （`display_w=800 与实际位图宽 797 不一致`），可证是真回归而非摆设。
- 热区排版契约测试同步为单行列网格断言：`<table>` 2 → 1、`<tr>` 6 → 1、
  嵌套表格 / `colgroup` / `colspan` 均为 0，并校验列宽求和等于显示宽度、
  列内 `<img>` 高度求和等于该列高度、cid 集合与附件清单一致且不重复。
- 全量测试 **178 passed**（原 166，新增 7 项切线 + 5 项画布）；`compileall` 通过。
- 新增 `outlook-compare/` 目录：同一张 960x3600 原图、同样 3 个按钮的
  「改造前 / 改造后」两版自包含 `.htm`，供在真实 Outlook / Word（与 Outlook
  同一排版引擎）中对比缝隙，作为最终验收依据。

### 已知问题（非本次引入，已定位未根治）
- **测试进程段错误**：若测试进程里「文件名排序最靠前的 Qt 模块」构造
  `HotspotEditorDialog`，整套用例会在 `tests/test_v491_hotspot_disabled.py`
  段错误，崩点 `desktop/main.py:502` 的 `super().__init__()`。
  - **稳定复现**：清空 `__pycache__` 后连续 3 次全量运行 **3/3 段错误**，
    不是偶发。
  - **已确认与本次改动无关**：把 `desktop/hotspot_editor.py` 整体回退到 HEAD
    （`apply_scaled_pixmap` 不存在）后，同样稳定复现。
  - **可控边界（干净缓存下实测）**：
    - 该模块只造 `ImageCanvas` → 全量 178 passed，不崩；
    - 该模块只造 `QLabel` + `QPixmap` → 全量通过，不崩；
    - 该模块造 `HotspotEditorDialog` → 段错误；
    - 单次观察到：先造一次性 `QWidget`「暖机」再造对话框仍段错误；
      「探测模块 + v487 + v489 + v491」小组合则正常（35 passed），
      需累积到整套用例才崩（该两条为单次观察，未做多轮复验）。
  - 本机 `lldb` 无法 attach（macOS 拒绝附加权限），拿不到 C++ 栈，故未定位根因。
  - **当前规避**：`tests/test_canvas_origin_alignment.py` 刻意不构造
    `HotspotEditorDialog`，改用「未绑定方法 + 轻量 stub」调用
    `_refit_canvas_to_size`，对话框侧几何入口同样被覆盖；`qapp` 统一为
    `tests/conftest.py` 的会话级 fixture（避免 `QApplication` 被 GC 回收后
    构造 QWidget 段错误）。
  - **残留风险**：任何文件名排序落在 `test_v*` 之前、且构造该对话框的新测试
    文件都会重新触发。根治需可用的 C++ 调试器。
- **开发提醒（踩过一次）**：排查时反复用 `git checkout` / `cp` 热替换 `.py`
  再立刻跑 pytest，会读到陈旧 `__pycache__` 字节码，出现「同一文件时而 5 项
  断言失败、时而段错误、清缓存后全绿」的假故障。改文件后跑测试前，
  建议先 `find . -name __pycache__ -type d -exec rm -rf {} +`。

## V6.3.0 - 2026-07-15

### Outlook 几何与链接
- 热区邮件按整张源图计算唯一目标高度，再以 4px 单位分配所有行，消除多链接累计拉伸。
- 每个热区视觉行使用独立列网格，并由连续外表格锁定纵向高度，避免经典 Outlook 跨行协调列宽导致错位。
- 复制图片增加全宽居中上下文；Windows EXE 使用原生 CF_HTML 写入剪贴板。
- Windows 剪贴板通过系统动态注册 `HTML Format`，兼容不提供 `CF_HTML` 常量的 pywin32 版本。
- 普通无链接长图继续使用原始连续图片路径，不改变稳定渲染行为。

### 编辑与界面
- 切线可以在相邻切线之间自由移动；超长区间应用时自动均匀补充 Outlook 安全切线。
- 主窗口及切线、热区、导出弹窗统一缩放字体、图标、按钮高度、圆角、内边距和布局间距。
- Windows 字体优先使用 Microsoft YaHei UI，并显式启用抗锯齿与质量优先渲染。
- 按钮使用实际圆角半径和内边距，不再依赖 999px 伪圆角。
- 图片导出在后台完成渲染、合并和写盘，主界面保持响应并显示阶段进度。
- JPG 导出真实使用品质滑块设置，不再固定使用 95% 品质。

### 质量保障
- 新增自由切线、多热区整图比例、独立列网格、复制居中、原生 CF_HTML、全局缩放、抗锯齿、后台导出和 JPG 品质回归。

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
