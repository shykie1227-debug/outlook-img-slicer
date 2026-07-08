/**
 * DropZone 组件（V6.1.0 — 豆包风格）
 *
 * 视觉规范：
 * - 虚线边框 2px，默认 #e7eaef
 * - hover/拖放态：边框 #0065fd + 背景 #e5e9ff
 * - 使用 icons/folder-color.svg 彩色文件夹图标
 */
import {
  useRef,
  useState,
  type DragEvent,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";
import { Icon } from "./icons";

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
        className="w-full max-w-2xl flex flex-col items-center justify-center gap-4 text-center opacity-50 cursor-not-allowed p-12"
        style={{
          border: "2px dashed var(--color-border)",
          borderRadius: "12px",
          background: "var(--color-card)",
        }}
      >
        <p style={{ color: "var(--color-text-weak)" }}>处理中…</p>
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

  // 豆包风格状态样式：虚线 2px，hover 变蓝 + 浅蓝底
  const stateStyle: Record<string, React.CSSProperties> = {
    idle: {
      borderColor: "var(--color-border)",
      background: "var(--color-card)",
    },
    hover: {
      borderColor: "var(--color-primary)",
      background: "#e5e9ff",
    },
    rejected: {
      borderColor: "var(--color-error)",
      background: "#fef2f2",
    },
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
      className="w-full max-w-2xl flex flex-col items-center justify-center gap-2.5 text-center cursor-pointer p-12 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2"
      style={{
        minHeight: "180px",
        border: "2px dashed var(--color-border)",
        borderRadius: "12px",
        ...stateStyle[state],
      }}
    >
      {/* 彩色文件夹图标 */}
      <img src={Icon.folderColor} alt="" className="w-11 h-11" />

      <div className="space-y-1">
        <p
          className="text-sm font-bold"
          style={{ color: "var(--color-text)" }}
        >
          {state === "rejected" ? "不支持的文件格式" : "拖拽图片到此处"}
        </p>
        <p
          data-testid="dropzone-formats"
          className="text-xs"
          style={{ color: "var(--color-text-secondary)" }}
        >
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
