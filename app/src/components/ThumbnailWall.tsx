/**
 * ThumbnailWall 组件（V6.0.0 Phase 3.2）
 *
 * 切片缩略图墙：网格布局 + 键盘导航 + 删除按钮
 *
 * Phase 5 优化：
 * - 引入 react-window 虚拟列表（> 20 张时）
 * - Framer Motion AnimatePresence stagger 进入
 */
import { type KeyboardEvent } from "react";

export interface ThumbnailItem {
  id: string;
  name: string;
  width: number;
  height: number;
  /** 可选：缩略图路径或 dataURL（Phase 4 用 base64 dataURL） */
  path?: string;
  thumbnail?: string;
}

export interface ThumbnailWallProps {
  items: ThumbnailItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
}

export function ThumbnailWall({
  items,
  selectedId,
  onSelect,
  onRemove,
}: ThumbnailWallProps): JSX.Element {
  if (items.length === 0) {
    return (
      <div
        data-testid="thumbnail-wall"
        className="w-full max-w-4xl mx-auto p-6 text-center text-slate-500 border border-dashed border-slate-800 rounded-2xl"
      >
        暂无切片
      </div>
    );
  }

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    const idx = items.findIndex((it) => it.id === selectedId);
    if (idx < 0) return;
    if (e.key === "ArrowRight" && idx < items.length - 1) {
      e.preventDefault();
      onSelect(items[idx + 1]!.id);
    } else if (e.key === "ArrowLeft" && idx > 0) {
      e.preventDefault();
      onSelect(items[idx - 1]!.id);
    } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      // 边界：保持在原位
      e.preventDefault();
      onSelect(items[idx]!.id);
    }
  };

  return (
    <div
      data-testid="thumbnail-wall"
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="w-full max-w-4xl mx-auto grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 outline-none"
    >
      {items.map((item, idx) => {
        const selected = item.id === selectedId;
        return (
          <div
            key={item.id}
            data-testid="thumb"
            aria-selected={selected}
            onClick={() => onSelect(item.id)}
            className={`group relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all duration-150 ${
              selected
                ? "border-sky-400 ring-2 ring-sky-400/50"
                : "border-slate-800 hover:border-slate-600"
            }`}
          >
            <div className="aspect-[3/4] bg-slate-900 flex items-center justify-center overflow-hidden">
              {item.thumbnail ? (
                <img
                  src={item.thumbnail}
                  alt={item.name}
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="text-slate-600 text-xs">无预览</div>
              )}
            </div>
            <div className="p-2 bg-slate-800/60">
              <div className="flex items-center justify-between text-xs">
                <span className="px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300">
                  {idx + 1}
                </span>
                <button
                  data-testid="thumb-remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(item.id);
                  }}
                  className="text-slate-500 hover:text-rose-400 transition-colors"
                  aria-label={`删除 ${item.name}`}
                >
                  ✕
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-300 truncate">{item.name}</p>
              <p className="text-xs text-slate-500">
                {item.width}×{item.height}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
