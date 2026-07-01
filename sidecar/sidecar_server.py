"""
Sidecar Server (V6.0.0)

V5 Python 核心的 JSON-RPC 封装，作为 Electron 主进程调用的子进程运行。

协议：stdin/stdout JSON 行（每行一个 JSON 对象）
- 启动时第一行 stdout 输出 {"ready": true}
- 每 3 秒输出一行 {"ping": timestamp}
- 接收 stdin 上的命令，输出响应到 stdout

约束（继承自 LOCAL_RULES.md）：
- 纯本地运行
- 不联网 / 不上传
- Outlook 命令仅 Windows

设计原则（继承自用户工作规则）：
- 简单 > 炫技
- 100 行能解决不写 1000 行
- 一个文件能解决不拆 20 个
"""
import sys
import os
import json
import time
import shutil
import base64
import platform
import threading
import traceback
from pathlib import Path

# ─────────────────────────────────────
# Path Setup: 让 sidecar 能 import V5 模块
# ─────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────
# 临时目录追踪（PDF/PSD/PPT 拆页后清理）
# ─────────────────────────────────────
_sidecar_temp_dirs: set[str] = set()


def _track_temp_dir(path: str) -> str:
    """记录临时目录路径，Sidecar 退出时统一清理。"""
    _sidecar_temp_dirs.add(path)
    return path


def _cleanup_temp_dirs() -> None:
    """Sidecar 退出时清理所有追踪过的临时目录。"""
    for d in list(_sidecar_temp_dirs):
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass
        _sidecar_temp_dirs.discard(d)


# ─────────────────────────────────────
# JSON IO
# ─────────────────────────────────────
def _write_json(obj: dict) -> None:
    """写一行 JSON 到 stdout，立即 flush。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _log_stderr(msg: str) -> None:
    """写一行日志到 stderr（不污染 stdout 的 JSON 协议）。"""
    sys.stderr.write(f"[sidecar] {msg}\n")
    sys.stderr.flush()


# ─────────────────────────────────────
# 心跳线程
# ─────────────────────────────────────
_heartbeat_stop = threading.Event()


def _heartbeat_loop() -> None:
    """每 3 秒输出一行 ping。"""
    while not _heartbeat_stop.wait(3.0):
        try:
            _write_json({"ping": time.time()})  # float 精度，毫秒级
        except Exception as exc:
            _log_stderr(f"心跳发送失败: {exc}")
            break


# ─────────────────────────────────────
# 输入校验
# ─────────────────────────────────────
def _require_path(params: dict) -> str:
    """校验 params['path'] 必须是字符串且文件存在。"""
    p = params.get("path")
    if not isinstance(p, str):
        raise TypeError(f"path 必须是字符串，得到 {type(p).__name__}")
    if not os.path.isfile(p):
        raise FileNotFoundError(f"文件不存在: {p}")
    return p


# ─────────────────────────────────────
# 平台守卫
# ─────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"


def _require_windows() -> dict | None:
    """非 Windows 平台返回错误响应 dict，否则返回 None。"""
    if not IS_WINDOWS:
        return {"ok": False, "error": "Outlook 集成仅支持 Windows 平台"}
    return None


# ─────────────────────────────────────
# 命令分派
# ─────────────────────────────────────
def _dispatch(req: dict) -> dict:
    """
    根据 req['method']（或向后兼容的 req['type']）调用对应命令，返回响应 dict（不含 id，由调用方填）。

    协议：JSON-RPC 风格 — 优先使用 'method' 字段（与 commands.md / electron/types.ts 一致），
    旧实现用 'type'，保留兼容。
    """
    cmd = req.get("method") or req.get("type", "")
    params = req.get("params", {}) or {}

    try:
        # ── 健康检查 ──
        if cmd == "sidecar.status":
            return {
                "ok": True,
                "result": {
                    "ready": True,
                    "pid": os.getpid(),
                    "platform": platform.system(),
                },
            }

        # ── 图片信息 ──
        if cmd == "image.info":
            from image_slicer import get_image_info
            p = _require_path(params)
            return {"ok": True, "result": get_image_info(p)}

        if cmd == "image.safetyCheck":
            from image_safety import check_image_safety, estimate_email_size_mb
            p = _require_path(params)  # 不存在文件直接抛错
            size_mb = estimate_email_size_mb([p])
            warnings = []
            is_safe = True
            try:
                check_image_safety(p)
            except Exception as exc:
                is_safe = False
                warnings.append(str(exc))
            return {
                "ok": True,
                "result": {"size_mb": size_mb, "is_safe": is_safe, "warnings": warnings},
            }

        # ── 图片切片 ──
        if cmd == "image.slice":
            from image_slicer import detect_and_slice
            from PIL import Image
            p = _require_path(params)
            paths = detect_and_slice(
                p,
                max_height=int(params.get("max_height", 1200)),
                smart=bool(params.get("smart", False)),
                target_width=int(params.get("target_width", 0)) or None,
            )
            slices = []
            for i, p2 in enumerate(paths, start=1):
                with Image.open(p2) as img:
                    w, h = img.size
                slices.append({
                    "path": p2,
                    "width": w,
                    "height": h,
                    "source_index": i,
                })
            return {"ok": True, "result": {"slices": slices}}

        # ── PDF 拆页 ──
        if cmd == "pdf.toImages":
            from pdf_slicer import pdf_to_images
            p = _require_path(params)
            import tempfile
            work_dir = Path(_track_temp_dir(tempfile.mkdtemp(prefix="sidecar_pdf_")))
            pages = pdf_to_images(p)
            out = []
            for i, img in enumerate(pages, start=1):
                fp = str(work_dir / f"page_{i:03d}.png")
                img.save(fp)
                out.append({"path": fp, "width": img.width, "height": img.height, "source_index": i})
            return {"ok": True, "result": {"pages": out}}

        # ── PPT 拆页 ──
        if cmd == "pptx.toImages":
            from ppt_slicer import pptx_to_images
            p = _require_path(params)
            import tempfile
            work_dir = Path(_track_temp_dir(tempfile.mkdtemp(prefix="sidecar_pptx_")))
            pages = pptx_to_images(p)
            out = []
            for i, img in enumerate(pages, start=1):
                fp = str(work_dir / f"page_{i:03d}.png")
                img.save(fp)
                out.append({"path": fp, "width": img.width, "height": img.height, "source_index": i})
            return {"ok": True, "result": {"pages": out}}

        # ── PSD 展平 ──
        if cmd == "psd.toImage":
            from psd_slicer import psd_to_images
            p = _require_path(params)
            import tempfile
            work_dir = Path(_track_temp_dir(tempfile.mkdtemp(prefix="sidecar_psd_")))
            imgs = psd_to_images(p)
            out = []
            for i, img in enumerate(imgs, start=1):
                fp = str(work_dir / f"psd_{i:03d}.png")
                img.save(fp)
                out.append({"path": fp, "width": img.width, "height": img.height, "source_index": i})
            return {"ok": True, "result": {"pages": out}}

        # ── HTML 组装（V5 验证算法） ──
        if cmd == "html.assemble":
            from html_assembler import SliceItem, generate_plain_html
            display_w = int(params.get("display_w", 960))
            items = [
                SliceItem(
                    path=s["path"],
                    href=s.get("href"),
                    alt_text=s.get("alt_text", ""),
                    sort_key=float(s.get("sort_key", i + 1)),
                    original_width=int(s.get("original_width", 0)),
                )
                for i, s in enumerate(params.get("slices", []))
            ]
            html = generate_plain_html(items, display_w=display_w)
            return {"ok": True, "result": {"html": html, "cid_files": {}}}

        # ── CF_HTML 字节（剪贴板） ──
        if cmd == "html.clipboard":
            from clipboard_html import build_windows_clipboard_html
            raw = build_windows_clipboard_html(params["html"])
            return {"ok": True, "result": {"cf_html_b64": base64.b64encode(raw).decode("ascii")}}

        # ── Outlook 邮件草稿（仅 Windows） ──
        if cmd == "outlook.createDraft":
            guard = _require_windows()
            if guard is not None:
                return guard
            from outlook_sender import create_email_with_images
            mail = create_email_with_images(
                html_content=params["html"],
                subject=params.get("subject", ""),
                to=params.get("to", ""),
                cid_files=params.get("cid_files"),
            )
            return {"ok": True, "result": {"mail_id": str(mail), "subject": params.get("subject", "")}}

        if cmd == "outlook.copyClipboard":
            guard = _require_windows()
            if guard is not None:
                return guard
            from outlook_sender import copy_cf_html_to_clipboard
            raw = base64.b64decode(params["cf_html_b64"])
            copy_cf_html_to_clipboard(raw)
            return {"ok": True, "result": {"ok": True}}

        return {"ok": False, "error": f"未知命令: {cmd}"}

    except KeyError as exc:
        return {"ok": False, "error": f"缺少必填参数: {exc}"}
    except FileNotFoundError as exc:
        return {"ok": False, "error": f"文件不存在: {exc}"}
    except TypeError as exc:
        _log_stderr(f"TypeError in {cmd}: {traceback.format_exc()}")
        return {"ok": False, "error": f"参数类型错误: {exc}"}
    except Exception as exc:
        _log_stderr(f"命令 {cmd} 执行异常:\n{traceback.format_exc()}")
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ─────────────────────────────────────
# 主循环
# ─────────────────────────────────────
def main() -> int:
    # 启动心跳线程
    hb = threading.Thread(target=_heartbeat_loop, daemon=True)
    hb.start()

    # 启动握手
    _write_json({"ready": True})

    # 读取 stdin
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            # 尝试解析为 JSON，保留 id（如有）以便错误响应匹配
            req_id = None
            try:
                req = json.loads(line)
                req_id = req.get("id")
            except json.JSONDecodeError as exc:
                resp = {"ok": False, "error": f"JSON 解析失败: {exc}"}
                if req_id is not None:
                    resp["id"] = req_id
                _write_json(resp)
                continue

            resp = _dispatch(req)
            if req_id is not None:
                resp["id"] = req_id
            _write_json(resp)
    except (EOFError, KeyboardInterrupt):
        _log_stderr("Sidecar 收到退出信号")
    finally:
        _heartbeat_stop.set()
        _cleanup_temp_dirs()  # 清理所有临时目录
    return 0


if __name__ == "__main__":
    sys.exit(main())
