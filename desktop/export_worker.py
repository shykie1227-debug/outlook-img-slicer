"""Background image export pipeline used by the desktop UI."""

from __future__ import annotations

import os
import time
import traceback
from pathlib import Path
from typing import Callable, List

from PIL import Image as PILImage
from PySide6.QtCore import QThread, Signal


class ExportWorker(QThread):
    progress = Signal(int, str)
    succeeded = Signal(dict)
    failed = Signal(str, str)

    def __init__(
        self,
        paths: List[str],
        save_dir: str,
        fmt: str,
        keep_alpha: bool,
        jpg_quality: int,
        renderer: Callable[[str], List[PILImage.Image]],
        parent=None,
    ):
        super().__init__(parent)
        self.paths = list(paths)
        self.save_dir = save_dir
        self.fmt = fmt
        self.keep_alpha = keep_alpha
        self.jpg_quality = max(10, min(100, int(jpg_quality)))
        self.renderer = renderer

    def run(self):
        try:
            images = []
            for path_index, path in enumerate(self.paths):
                if self.isInterruptionRequested():
                    return
                progress = 10 + round(45 * path_index / max(1, len(self.paths)))
                self.progress.emit(progress, f"正在渲染 {Path(path).name}...")
                for image in self.renderer(path):
                    images.append(self._normalize_image(image))

            if not images:
                raise RuntimeError("没有可导出的图片页。")
            if self.isInterruptionRequested():
                return

            self.progress.emit(60, "正在合并图片...")
            merged = self._merge_images(images)
            self.progress.emit(78, "正在准备写入文件...")

            ext = "png" if self.fmt == "png" else "jpg"
            suffix = f"_{int(time.time())}_{os.getpid()}" if len(images) > 1 else ""
            base_name = "merged" if len(images) > 1 else Path(self.paths[0]).stem
            destination = os.path.join(self.save_dir, f"{base_name}{suffix}.{ext}")

            self.progress.emit(88, "正在写入导出文件...")
            if self.fmt == "jpg":
                if merged.mode != "RGB":
                    merged = self._flatten_to_rgb(merged)
                merged.save(destination, "JPEG", quality=self.jpg_quality)
            else:
                merged.save(destination, "PNG")

            if not os.path.isfile(destination) or os.path.getsize(destination) <= 0:
                if os.path.exists(destination):
                    os.remove(destination)
                raise RuntimeError(f"导出文件为空或未生成：{destination}")

            self.progress.emit(100, "导出完成，正在校验文件...")
            self.succeeded.emit({
                "path": destination,
                "size_bytes": os.path.getsize(destination),
                "page_count": len(images),
                "format": ext,
                "keep_alpha": self.fmt == "png" and self.keep_alpha,
                "jpg_quality": self.jpg_quality,
            })
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())

    def _normalize_image(self, image: PILImage.Image) -> PILImage.Image:
        if self.fmt == "png" and self.keep_alpha:
            return image if image.mode == "RGBA" else image.convert("RGBA")
        return self._flatten_to_rgb(image)

    @staticmethod
    def _flatten_to_rgb(image: PILImage.Image) -> PILImage.Image:
        if image.mode == "RGB":
            return image
        if image.mode in ("RGBA", "LA"):
            background = PILImage.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            return background
        return image.convert("RGB")

    @staticmethod
    def _merge_images(images: List[PILImage.Image]) -> PILImage.Image:
        if len(images) == 1:
            return images[0]
        canvas_width = max(image.width for image in images)
        canvas_height = sum(image.height for image in images)
        mode = "RGBA" if images[0].mode == "RGBA" else "RGB"
        background = (0, 0, 0, 0) if mode == "RGBA" else (255, 255, 255)
        canvas = PILImage.new(mode, (canvas_width, canvas_height), background)
        y = 0
        for image in images:
            x = (canvas_width - image.width) // 2
            if image.mode == "RGBA" and canvas.mode == "RGBA":
                canvas.alpha_composite(image, (x, y))
            else:
                canvas.paste(image, (x, y))
            y += image.height
        return canvas
