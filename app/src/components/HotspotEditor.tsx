/**
 * HotspotEditor 组件（V6.0.0 Phase 3.4）
 *
 * 热区编辑器：
 * - SVG 切片预览 + 热区矩形叠加
 * - 属性编辑面板（x / y / w / h / href）
 * - 添加 / 删除 / 选中
 * - 边界裁剪 + 最小尺寸约束
 */
import { type ChangeEvent } from "react";

export interface Hotspot {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  href: string;
}

export interface HotspotOptions {
  minSizePx: number;
}

export interface HotspotEditorProps {
  slice: { width: number; height: number };
  hotspots: Hotspot[];
  selectedId?: string | null;
  options: HotspotOptions;
  onChange: (hotspots: Hotspot[]) => void;
  onSelect?: (id: string | null) => void;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

export function HotspotEditor({
  slice,
  hotspots,
  selectedId = null,
  options,
  onChange,
  onSelect,
}: HotspotEditorProps): JSX.Element {
  const selected = hotspots.find((h) => h.id === selectedId) ?? null;

  const addHotspot = (): void => {
    const w = 100;
    const h = 50;
    const x = Math.floor((slice.width - w) / 2);
    const y = Math.floor((slice.height - h) / 2);
    const id = `h${Date.now()}`;
    onChange([...hotspots, { id, x, y, w, h, href: "" }]);
    onSelect?.(id);
  };

  const removeHotspot = (): void => {
    if (!selectedId) return;
    onChange(hotspots.filter((h) => h.id !== selectedId));
    onSelect?.(null);
  };

  const updateSelected = (patch: Partial<Hotspot>): void => {
    if (!selectedId) return;
    onChange(
      hotspots.map((h) => {
        if (h.id !== selectedId) return h;
        const merged = { ...h, ...patch };
        merged.w = Math.max(options.minSizePx, merged.w);
        merged.h = Math.max(options.minSizePx, merged.h);
        merged.x = clamp(merged.x, 0, slice.width - merged.w);
        merged.y = clamp(merged.y, 0, slice.height - merged.h);
        return merged;
      })
    );
  };

  const onNumberChange = (key: "x" | "y" | "w" | "h") => (e: ChangeEvent<HTMLInputElement>): void => {
    const v = Number(e.target.value);
    if (Number.isFinite(v)) updateSelected({ [key]: v });
  };

  return (
    <div className="flex flex-col md:flex-row gap-4 w-full">
      {/* SVG 切片预览 + 热区 */}
      <div className="flex-1 min-w-0">
        <svg
          viewBox={`0 0 ${slice.width} ${slice.height}`}
          preserveAspectRatio="xMidYMid meet"
          className="w-full bg-slate-900 rounded-lg border border-slate-800"
          onClick={() => onSelect?.(null)}
        >
          <rect x={0} y={0} width={slice.width} height={slice.height} fill="#1e293b" />
          {hotspots.map((h) => {
            const isSel = h.id === selectedId;
            return (
              <g key={h.id}>
                <rect
                  data-hotspot={h.id}
                  data-selected={isSel ? "true" : "false"}
                  x={h.x}
                  y={h.y}
                  width={h.w}
                  height={h.h}
                  fill={isSel ? "rgba(14,165,233,0.2)" : "rgba(244,114,182,0.15)"}
                  stroke={isSel ? "#0ea5e9" : "#f472b6"}
                  strokeWidth={isSel ? 3 : 2}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect?.(h.id);
                  }}
                  style={{ cursor: "pointer" }}
                />
                {isSel && (
                  <>
                    <rect x={h.x - 4} y={h.y - 4} width={8} height={8} fill="#0ea5e9" />
                    <rect
                      x={h.x + h.w - 4}
                      y={h.y + h.h - 4}
                      width={8}
                      height={8}
                      fill="#0ea5e9"
                      style={{ cursor: "nwse-resize" }}
                    />
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* 属性面板 */}
      <div className="w-full md:w-72 space-y-3">
        <div className="flex gap-2">
          <button
            data-testid="add-hotspot"
            onClick={addHotspot}
            className="flex-1 px-3 py-1.5 text-sm rounded-md bg-sky-600 hover:bg-sky-500 text-white"
          >
            + 添加热区
          </button>
          <button
            data-testid="remove-hotspot"
            onClick={removeHotspot}
            disabled={!selected}
            className="px-3 py-1.5 text-sm rounded-md bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            删除
          </button>
        </div>

        {hotspots.length === 0 && (
          <div data-testid="hotspot-empty" className="text-sm text-slate-500 p-3 border border-dashed border-slate-800 rounded-md text-center">
            暂无热区，点击上方按钮添加
          </div>
        )}

        {hotspots.map((h) => (
          <div
            key={h.id}
            data-testid="hotspot-row"
            data-selected={h.id === selectedId ? "true" : "false"}
            onClick={() => onSelect?.(h.id)}
            className={`p-2 rounded-md cursor-pointer border ${
              h.id === selectedId
                ? "border-sky-500 bg-sky-500/10"
                : "border-slate-800 hover:border-slate-600"
            }`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 truncate">{h.href || "未设置链接"}</span>
              <span className="text-slate-500">
                {h.w}×{h.h}
              </span>
            </div>
            {h.id === selectedId && (
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <label className="flex flex-col">
                  <span className="text-slate-500">x</span>
                  <input
                    data-testid="hotspot-x"
                    type="number"
                    value={h.x}
                    onChange={onNumberChange("x")}
                    className="bg-slate-800 border border-slate-700 rounded px-1.5 py-1"
                  />
                </label>
                <label className="flex flex-col">
                  <span className="text-slate-500">y</span>
                  <input
                    data-testid="hotspot-y"
                    type="number"
                    value={h.y}
                    onChange={onNumberChange("y")}
                    className="bg-slate-800 border border-slate-700 rounded px-1.5 py-1"
                  />
                </label>
                <label className="flex flex-col">
                  <span className="text-slate-500">w</span>
                  <input
                    data-testid="hotspot-w"
                    type="number"
                    value={h.w}
                    onChange={onNumberChange("w")}
                    className="bg-slate-800 border border-slate-700 rounded px-1.5 py-1"
                  />
                </label>
                <label className="flex flex-col">
                  <span className="text-slate-500">h</span>
                  <input
                    data-testid="hotspot-h"
                    type="number"
                    value={h.h}
                    onChange={onNumberChange("h")}
                    className="bg-slate-800 border border-slate-700 rounded px-1.5 py-1"
                  />
                </label>
                <label className="flex flex-col col-span-2">
                  <span className="text-slate-500">链接 URL</span>
                  <input
                    data-testid="hotspot-url"
                    type="url"
                    value={h.href}
                    onChange={(e) => updateSelected({ href: e.target.value })}
                    placeholder="https://..."
                    className="bg-slate-800 border border-slate-700 rounded px-1.5 py-1"
                  />
                </label>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
