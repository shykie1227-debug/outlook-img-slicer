# Outlook 长图助手 UI 优化说明

## 修改内容

### 1. `main.py`

- 精简并重构主界面布局。
- 优化主题色与按钮样式，界面风格更统一。
- 将拖拽区域改为可点击上传的 `DropZone`，提高可用性。
- 移除多余导入和冗余组件，简化代码结构。
- 重新整理输入框、预览区、进度条和操作按钮的布局。
- 统一状态提示样式，简化 `send` / `reset` 逻辑。

### 2. `html_assembler.py`

- 改用 `Path(path).absolute().as_uri()` 生成本地 `file://` URL，更兼容 Outlook。
- 精简 HTML 生成结构，采用表格布局以增强邮件客户端显示一致性。
- 使用默认宽度参数，并去除旧版多余函数。

## 目标效果

- 更简洁的应用界面
- 更少的代码冗余
- 更稳定的 Outlook HTML 生成方式
- 保持原有功能：图片/PDF 切片、预览、创建 Outlook 邮件

## 验证情况

- 已执行 `python3 -m py_compile main.py html_assembler.py image_slicer.py outlook_sender.py pdf_slicer.py`
- 所有文件通过语法检查

## 文件位置

- `main.py`
- `html_assembler.py`
- `image_slicer.py`
- `outlook_sender.py`
- `pdf_slicer.py`

## 备注

如果你希望，我还可以继续将此说明整理为 `README.md` 或 `CHANGELOG.md`。
