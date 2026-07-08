/**
 * DropZone 组件（V6.0.3 — V5 浅色还原版）
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

const FORMAT_LABELS = "JPG · PNG · PDF · PPT · PSD/PSB";

export interface DropZoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
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
        className="w-full max-w-2xl rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 flex flex-col items-center justify-center gap-4 text-center opacity-50 cursor-not-allowed p-12"
      >
        <p className="text-slate-400">处理中…</p>
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
    e.target.value = "";
  };

  const stateClasses: Record<string, string> = {
    idle: "border-slate-300 bg-white hover:border-sky-400 hover:bg-sky-50/50",
    hover: "border-sky-500 bg-sky-50 scale-[1.01]",
    rejected: "border-rose-400 bg-rose-50",
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
      className={`w-full max-w-2xl rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-3 text-center cursor-pointer transition-[border-color,background-color,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 p-12 ${stateClasses[state] ?? stateClasses.idle}`}
    >
      {/* 黄色文件夹图标 */}
      <div aria-hidden="true" className="w-20 h-20 flex items-center justify-center mb-2">
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M8 16C8 13.7909 9.79086 12 12 12H24L30 18H52C54.2091 18 56 19.7909 56 22V46C56 48.2091 54.2091 50 52 50H12C9.79086 50 8 48.2091 8 46V16Z" fill="#FFD75E"/>
          <path d="M8 22C8 19.7909 9.79086 18 12 18H52C54.2091 18 56 19.7909 56 22V46C56 48.2091 54.2091 50 52 50H12C9.79086 50 8 48.2091 8 46V22Z" fill="#FFC331"/>
        </svg>
      </div>
      <div className="space-y-1">
        <p className="text-lg font-bold text-slate-700">
          {state === "rejected" ? "不支持的文件格式" : "拖拽图片到此处"}
        </p>
        <p data-testid="dropzone-formats" className="text-sm text-slate-400">
          支持 {FORMAT_LABELS}，点击上传
        </p>
      </div>
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
