/**
 * ImagePreview 组件（V6.0.0 Phase 4）
 *
 * 用 safe-file:// 自定义协议显示本地图片。
 * - 仅显示已批准的图片扩展名
 * - 限定最大高度，避免超大图撑爆 UI
 * - 支持点击放大查看（Phase 5+）
 */
import { useState } from "react";

export interface ImagePreviewProps {
  /** 绝对路径 */
  path: string;
  /** 最大高度（px） */
  maxHeight?: number;
  /** alt 文本 */
  alt?: string;
  /** 原图宽度（用于防 CLS） */
  width?: number;
  /** 原图高度（用于防 CLS） */
  height?: number;
}

/** 把绝对路径转成 safe-file:// URL */
export function toSafeFileUrl(absPath: string): string {
  // 简单 percent-encode 空格和特殊字符
  const encoded = absPath
    .split("/")
    .map((seg) => encodeURIComponent(seg))
    .join("/");
  return `safe-file://${encoded.startsWith("/") ? "" : "/"}${encoded}`;
}

export function ImagePreview({
  path,
  maxHeight = 400,
  alt = "原图预览",
  width,
  height,
}: ImagePreviewProps): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const url = toSafeFileUrl(path);

  if (error) {
    return (
      <div
        data-testid="image-preview-error"
        role="alert"
        className="w-full rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-rose-300 text-sm"
      >
        图片加载失败：{error}
      </div>
    );
  }

  return (
    <div
      data-testid="image-preview"
      className="relative w-full rounded-lg border border-slate-700 bg-slate-800/40 overflow-hidden"
      style={{ maxHeight, aspectRatio: width && height ? `${width} / ${height}` : undefined }}
    >
      <img
        src={url}
        alt={alt}
        width={width}
        height={height}
        // React 18.2 用 lowercase attribute
        // V6.0.0: above-the-fold 关键图片，高优先级
        {...({ fetchpriority: "high" } as Record<string, string>)}
        onLoad={() => setLoaded(true)}
        onError={() => setError("safe-file 协议拒绝或文件不可读")}
        className={`w-full h-auto object-contain transition-opacity duration-200 ${loaded ? "opacity-100" : "opacity-0"}`}
        style={{ maxHeight }}
        draggable={false}
      />
      {!loaded && (
        <div
          aria-hidden="true"
          className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm"
        >
          加载中…
        </div>
      )}
    </div>
  );
}
