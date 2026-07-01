/**
 * DropZone 组件（V6.0.0 Phase 3.1）
 *
 * 拖拽上传区，4 状态：idle / hover / rejected / disabled
 * 支持格式：PNG / JPG / JPEG / BMP / WebP / GIF / PDF / PPT / PPTX / PSD
 *
 * Phase 5 接入 Framer Motion 后会替换 CSS 过渡为弹性动效。
 */
import {
  useRef,
  useState,
  type DragEvent,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";

const SUPPORTED_EXTS = [
  "png", "jpg", "jpeg", "bmp", "webp", "gif", "svg",
  "pdf", "ppt", "pptx", "psd",
];

const FORMAT_LABELS = "PNG · JPG · BMP · WebP · GIF · SVG · PDF · PPT · PSD";

export interface DropZoneProps {
  /** 合法文件被放下时调用 */
  onFile: (file: File) => void;
  /** 禁用状态（处理中） */
  disabled?: boolean;
  /**
   * 可选：点击后调用系统级文件对话框（window.api.openImage）。
   * 不传则不渲染"选择文件"按钮。
   */
  onPick?: () => void;
}

function getExt(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}

function isSupported(file: File): boolean {
  const ext = getExt(file.name);
  return SUPPORTED_EXTS.includes(ext);
}

export function DropZone({ onFile, disabled = false, onPick }: DropZoneProps): JSX.Element {
  const [state, setState] = useState<"idle" | "hover" | "rejected">("idle");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const dragCounter = useRef(0);

  if (disabled) {
    return (
      <div
        data-testid="dropzone"
        data-state="disabled"
        className="w-full max-w-2xl aspect-[3/4] rounded-2xl border-2 border-dashed border-slate-800 bg-slate-900/60 flex flex-col items-center justify-center gap-4 text-center opacity-50 cursor-not-allowed"
      >
        <p className="text-slate-500">处理中…</p>
      </div>
    );
  }

  const onDragEnter = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    const types = e.dataTransfer?.types;
    if (types && types.includes("Files")) {
      setState("hover");
    }
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    const types = e.dataTransfer?.types;
    if (types && types.includes("Files")) {
      e.dataTransfer.dropEffect = "copy";
      setState("hover");
    }
  };

  const onDragLeave = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setState("idle");
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    const file = e.dataTransfer?.files?.[0];
    if (!file) {
      setState("idle");
      return;
    }
    if (isSupported(file)) {
      onFile(file);
      setState("idle");
    } else {
      setState("rejected");
      setTimeout(() => setState("idle"), 2000);
    }
  };

  const onClick = (): void => {
    // 优先用 onPick（系统级对话框），否则回退到 HTML input
    if (onPick) {
      onPick();
      return;
    }
    inputRef.current?.click();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  const onInputChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (isSupported(file)) {
      onFile(file);
    } else {
      setState("rejected");
      setTimeout(() => setState("idle"), 2000);
    }
    // 清空 input，允许同文件再次选择
    e.target.value = "";
  };

  const stateClasses: Record<string, string> = {
    idle: "border-slate-700 bg-slate-800/40 hover:border-sky-500/50",
    hover: "border-sky-400 bg-sky-500/10 scale-[1.01]",
    rejected: "border-rose-500 bg-rose-500/10",
  };

  return (
    <div
      data-testid="dropzone"
      data-state={state}
      onClick={onClick}
      onKeyDown={onKeyDown}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      role="button"
      tabIndex={0}
      aria-label="拖拽或选择长图文件"
      className={`w-full max-w-2xl aspect-[3/4] rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-4 text-center cursor-pointer transition-[border-color,background-color,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${stateClasses[state] ?? stateClasses.idle}`}
    >
      <div aria-hidden="true" className="w-16 h-16 rounded-full bg-sky-500/10 flex items-center justify-center text-3xl">
        📥
      </div>
      <div className="space-y-1">
        <p className="text-lg font-medium">
          {state === "rejected" ? "不支持的文件格式" : "拖拽图片到此处"}
        </p>
        <p data-testid="dropzone-formats" className="text-sm text-slate-400">
          支持 {FORMAT_LABELS}
        </p>
      </div>
      <p className="text-xs text-slate-500 mt-4">
        也可点击此处选择文件
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={SUPPORTED_EXTS.map((e) => `.${e}`).join(",")}
        data-testid="dropzone-input"
        className="hidden"
        onChange={onInputChange}
        aria-label="选择长图文件"
      />
    </div>
  );
}
