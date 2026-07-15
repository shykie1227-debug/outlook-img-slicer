# 测试计划 - Outlook 长图助手 V6.3.0

## 1. 目标与底线

本计划验证从导入、切片、热区编辑到 Outlook 草稿和 Windows EXE 的完整链路。
发布底线如下：

- 普通长图与热区长图必须保持顺序、居中和像素连续，不得出现可见缝隙。
- 单切片可添加多个互不重叠的有效链接，保存后可编辑和删除。
- Outlook 路径只创建并显示草稿；运行时代码不得包含 `mail.Send()`、联网、上传、遥测或自动更新。
- 构建清单、文件名、窗口版本和 Windows 文件属性必须一致为 V6.3.0。

## 2. 自动化范围

| 范围 | 重点 |
|------|------|
| 图片与文档输入 | JPG/PNG/BMP/WebP/GIF、PDF、PPT/PPTX、PSD/PSB 的解析与错误提示 |
| 切片 | 智能切线、手工切线、边缘像素连续、每片 80–1200px、临时目录隔离 |
| 热区 | 单/多链接、贴边、奇偶像素、越界、重叠、空链接、协议校验、再次编辑 |
| 邮件渲染 | 普通直接 `<img>` 路径、热区物理切片、CID 数量、链接映射、零间距表格 |
| Outlook 与剪贴板 | 草稿 `Display(False)`、CF_HTML 字节偏移、异常恢复、禁止自动发送 |
| 主界面 | 三步流程、按钮状态、620px 窄窗口、主窗口与编辑弹窗全局缩放、后台导出、压缩/品质、错误恢复 |
| 发布 | 版本同步、构建清单、SHA-256、ASCII 文件名、运行时本地安全契约 |

测试数据由 pytest fixture 或临时目录动态生成，不依赖用户文件，不保留隐私数据。

## 3. 本机回归门槛

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q
python3 -m compileall -q build.py desktop tests
git diff --check
```

重点回归文件包括：

- `tests/test_outlook_hotspot_layout.py`
- `tests/test_v486_no_gap_regression.py`
- `tests/test_v620_hotspot_preflight.py`
- `tests/test_v622_reliability_refactor.py`
- `tests/test_main_window_ux.py`
- `tests/test_responsive_dialogs.py`
- `tests/test_export_worker.py`
- `tests/test_runtime_safety_contract.py`
- `tests/test_release_consistency.py`
- `tests/test_documentation_release_contract.py`

当前发布不把覆盖率百分比作为阻断门槛；若生成覆盖率报告，结果仅用于发现缺口，
不能代替行为回归、Windows 启动或经典 Outlook 验收。

## 4. Windows VM 自动验收

1. 从共享目录复制源码到 Windows 本地目录，避免共享文件锁导致清理失败。
2. 运行全量 pytest，再执行 PyInstaller onefile 构建。
3. 校验 `build-manifest.json` 中的版本、产物类型、大小和 SHA-256。
4. 复制为 `dist/OutlookImgSlicer-V6.3.0.exe`。
5. 读取 PE `FileVersion` / `ProductVersion`，启动 EXE，等待主窗口进程稳定后关闭。
6. 检查运行期无网络请求，且 Outlook 自动化路径不存在 `mail.Send()`。

自动化通过只证明 EXE 可构建、版本正确且可启动，不等同于 Outlook Word 渲染验收。

## 5. 经典 Outlook 人工矩阵

| 场景 | 验收内容 |
|------|----------|
| 普通长图 | 草稿完整、居中、上下无缝、保存并重开后顺序不变 |
| 单热区 | 链接区域位置正确、可点击、目标 URL 正确 |
| 多热区 | 同片多个按钮均可点击，左右和上下错位场景不产生横纵缝隙 |
| 超长图/多源切片 | 邮件中连续拼接，无缺片、重复片或宽度漂移 |
| 显示缩放 | Windows 100%、125%、150%、175%、200% 下控件无截断、重叠或失效 |
| 实际发送 | 收件端重新打开后图片仍完整、链接仍可点击；发送动作始终由用户手动完成 |

任一 Outlook 无缝或链接用例失败时，不发布该版本。

## 6. 完成证据

发布记录必须包含：pytest 实际通过数、编译与差异检查结果、Windows 构建日志、
EXE 绝对路径、文件大小、SHA-256、PE 版本和启动冒烟结果。未执行的经典 Outlook
实际发送测试必须明确标记为“未验证”，不能用自动化结果替代。
