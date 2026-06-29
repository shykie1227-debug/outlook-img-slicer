/**
 * CutEditor 组件（V6.0.0 Phase 3.3 重构版）
 *
 * 切线编辑器：
 * - SVG 渲染原图占位 + N 条切线 + 段遮罩
 * - 鼠标拖动切线 / 键盘微调 / Shift+方向 10px
 * - 磁吸最近 10 的倍数（±5px）
 * - 约束：minSegmentPx / maxSegmentPx / 边界
 *
 * 重构点：
 * - I3: 合并 draftCuts/cuts 双重状态，统一使用 props.cuts
 * - I4: keydown effect 用 useRef 缓存最新 cuts/options，避免每次 state 变化重绑
 * - I6: 使用 crypto.randomUUID() 生成 id
 */
import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

export interface CutLine {
  id: string;
  y: number;
}

export interface CutOptions {
  minSegmentPx: number;
  maxSegmentPx: number;
  snapThresholdPx: number;
}

export interface CutEditorProps {
  image: { width: number; height: number };
  cuts: CutLine[];
  selectedId?: string | null;
  options: CutOptions;
  onChange: (cuts: CutLine[]) => void;
  onSelect?: (id: string | null) => void;
}

function snap(y: number, threshold: number): number {
  const mod = y % 10;
  if (mod <= threshold) return y - mod;
  if (mod >= 10 - threshold) return y + (10 - mod);
  return y;
}

function isValidY(
  y: number,
  cuts: CutLine[],
  selfId: string,
  options: CutOptions,
  imageHeight: number
): boolean {
  if (y < options.minSegmentPx || y > imageHeight - options.minSegmentPx) return false;
  for (const c of cuts) {
    if (c.id === selfId) continue;
    const dist = Math.abs(y - c.y);
    if (dist < options.minSegmentPx || dist > options.maxSegmentPx) return false;
  }
  return true;
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `l${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function CutEditor({
  image,
  cuts,
  selectedId = null,
  options,
  onChange,
  onSelect,
}: CutEditorProps): JSX.Element {
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  // I4: 用 ref 缓存最新 cuts/options，keydown handler 不再随 state 变化重绑
  const stateRef = useRef({ cuts, options, imageHeight: image.height, selectedId });
  stateRef.current = { cuts, options, imageHeight: image.height, selectedId };

  // 拖动
  useEffect(() => {
    if (!draggingId) return;
    const onMove = (e: MouseEvent): void => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const ratio = image.height / rect.height;
      const y = Math.round((e.clientY - rect.top) * ratio);
      updateLine(draggingId, y);
    };
    const onUp = (): void => {
      setDraggingId(null);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [draggingId, image.height]);

  // I4: 键盘只绑定一次
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      let delta = 0;
      if (e.key === "ArrowUp") delta = e.shiftKey ? -10 : -1;
      else if (e.key === "ArrowDown") delta = e.shiftKey ? 10 : 1;
      else return;
      e.preventDefault();
      const { cuts: currentCuts, options: opts, imageHeight, selectedId: selId } = stateRef.current;
      if (!selId) return;
      const line = currentCuts.find((c) => c.id === selId);
      if (!line) return;
      let newY = line.y + delta;
      newY = snap(newY, opts.snapThresholdPx);
      if (!isValidY(newY, currentCuts, selId, opts, imageHeight)) {
        newY = line.y + (delta > 0 ? 1 : -1);
        newY = snap(newY, opts.snapThresholdPx);
        if (!isValidY(newY, currentCuts, selId, opts, imageHeight)) return;
      }
      updateLine(selId, newY);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const updateLine = (id: string, y: number): void => {
    const { cuts: currentCuts, imageHeight } = stateRef.current;
    const clamped = Math.max(0, Math.min(imageHeight, y));
    const newCuts = currentCuts.map((c) => (c.id === id ? { ...c, y: clamped } : c));
    onChange(newCuts);
  };

  const onLineMouseDown = (id: string) => (e: ReactMouseEvent<SVGLineElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    setDraggingId(id);
    onSelect?.(id);
  };

  const segments: { y0: number; y1: number; key: string }[] = [];
  const sortedY = [0, ...cuts.map((c) => c.y), image.height].sort((a, b) => a - b);
  for (let i = 0; i < sortedY.length - 1; i++) {
    segments.push({ y0: sortedY[i]!, y1: sortedY[i + 1]!, key: `seg-${i}` });
  }

  const addCut = (): void => {
    let bestY = image.height / 2;
    let bestSize = 0;
    for (const seg of segments) {
      if (seg.y1 - seg.y0 > bestSize) {
        bestSize = seg.y1 - seg.y0;
        bestY = Math.floor((seg.y0 + seg.y1) / 2);
      }
    }
    const id = newId();
    const newCuts = [...cuts, { id, y: bestY }].sort((a, b) => a.y - b.y);
    onChange(newCuts);
    onSelect?.(id);
  };

  const removeCut = (): void => {
    if (!selectedId) return;
    const newCuts = cuts.filter((c) => c.id !== selectedId);
    onChange(newCuts);
  };

  return (
    <div className="flex flex-col gap-3 w-full">
      <div className="flex items-center gap-2">
        <button
          data-testid="add-cut"
          onClick={addCut}
          className="px-3 py-1.5 text-sm rounded-md bg-sky-600 hover:bg-sky-500 text-white"
        >
          + 添加切线
        </button>
        <button
          data-testid="remove-cut"
          onClick={removeCut}
          disabled={!selectedId}
          className="px-3 py-1.5 text-sm rounded-md bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          - 删除切线
        </button>
        <span className="text-xs text-slate-500 ml-auto">
          {cuts.length} 条切线 / 段高 {options.minSegmentPx}~{options.maxSegmentPx}px
        </span>
      </div>

      <svg
        ref={svgRef}
        data-testid="cut-canvas"
        viewBox={`0 0 ${image.width} ${image.height}`}
        preserveAspectRatio="xMidYMin meet"
        className="w-full max-h-[60vh] bg-slate-900 rounded-lg border border-slate-800"
        onClick={() => onSelect?.(null)}
      >
        <rect x={0} y={0} width={image.width} height={image.height} fill="#1e293b" />
        <text
          x={image.width / 2}
          y={image.height / 2}
          fill="#475569"
          textAnchor="middle"
          fontSize="48"
        >
          原图 {image.width}×{image.height}
        </text>

        {segments.map((seg) => (
          <rect
            key={seg.key}
            data-testid="cut-mask"
            x={0}
            y={seg.y0}
            width={image.width}
            height={seg.y1 - seg.y0}
            fill="rgba(14, 165, 233, 0.04)"
          />
        ))}

        {cuts.map((c) => {
          const selected = c.id === selectedId;
          return (
            <g key={c.id}>
              <line
                data-testid="cut-line"
                x1={0}
                x2={image.width}
                y1={c.y}
                y2={c.y}
                stroke={selected ? "#0ea5e9" : "#64748b"}
                strokeWidth={selected ? 4 : 2}
                onMouseDown={onLineMouseDown(c.id)}
                style={{ cursor: "ns-resize" }}
              />
              <text
                x={10}
                y={c.y - 8}
                fill={selected ? "#0ea5e9" : "#94a3b8"}
                fontSize="20"
              >
                y={c.y}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
