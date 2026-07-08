/**
 * SettingsPanel 组件（V6.0.3 — V5 浅色还原版）
 *
 * Settings 接口新增 exportImage / avoidTextCut 字段。
 * 默认 emailWidth=650（匹配 V5/图一）。
 */
import { type ChangeEvent } from "react";

export interface Settings {
  emailWidth: number;
  maxSliceHeight: number;
  outputFormat: "PNG" | "JPEG";
  jpegQuality: number;
  theme: "light" | "dark" | "system";
  exportImage: boolean;
  avoidTextCut: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  emailWidth: 650,
  maxSliceHeight: 2000,
  outputFormat: "PNG",
  jpegQuality: 95,
  theme: "light",
  exportImage: false,
  avoidTextCut: true,
};

const STORAGE_KEY = "outlook-img-slicer-settings";

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

export interface SettingsPanelProps {
  value: Settings;
  onChange: (s: Settings) => void;
  persist?: boolean;
}

function saveToStorage(s: Settings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

export function SettingsPanel({
  value,
  onChange,
  persist = false,
}: SettingsPanelProps): JSX.Element {
  const patch = (p: Partial<Settings>): void => {
    const next = { ...value, ...p };
    onChange(next);
    if (persist) saveToStorage(next);
  };

  const onMaxHeight = (e: ChangeEvent<HTMLInputElement>): void => {
    const v = clamp(parseInt(e.target.value, 10) || 0, 500, 6000);
    patch({ maxSliceHeight: v });
  };

  const onJpegQuality = (e: ChangeEvent<HTMLInputElement>): void => {
    const v = clamp(parseInt(e.target.value, 10) || 0, 50, 100);
    patch({ jpegQuality: v });
  };

  const onFormat = (e: ChangeEvent<HTMLSelectElement>): void => {
    patch({ outputFormat: e.target.value as "PNG" | "JPEG" });
  };

  const onTheme = (e: ChangeEvent<HTMLSelectElement>): void => {
    patch({ theme: e.target.value as "light" | "dark" | "system" });
  };

  const onExportImage = (e: ChangeEvent<HTMLInputElement>): void => {
    patch({ exportImage: e.target.checked });
  };

  const onAvoidTextCut = (e: ChangeEvent<HTMLInputElement>): void => {
    patch({ avoidTextCut: e.target.checked });
  };

  const reset = (): void => {
    onChange(DEFAULT_SETTINGS);
    if (persist) saveToStorage(DEFAULT_SETTINGS);
  };

  return (
    <div
      data-testid="settings-panel"
      className="w-full max-w-md mx-auto p-4 rounded-lg border border-slate-200 bg-white space-y-4 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">高级设置</h3>
        <button
          data-testid="reset-settings"
          onClick={reset}
          className="text-xs text-slate-400 hover:text-rose-500"
        >
          恢复默认
        </button>
      </div>

      <Field label="切片最大高度（px）" hint="[500, 6000]">
        <input
          data-testid="setting-maxSliceHeight"
          type="number"
          name="maxSliceHeight"
          inputMode="numeric"
          autoComplete="off"
          min={500}
          max={6000}
          value={value.maxSliceHeight}
          onChange={onMaxHeight}
          className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
        />
      </Field>

      <Field label="输出格式">
        <select
          data-testid="setting-outputFormat"
          name="outputFormat"
          value={value.outputFormat}
          onChange={onFormat}
          className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1.5 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
        >
          <option value="PNG">PNG（无损 / 文件大）</option>
          <option value="JPEG">JPEG（有损 / 文件小）</option>
        </select>
      </Field>

      <Field label="JPEG 质量" hint="[50, 100]">
        <input
          data-testid="setting-jpegQuality"
          type="number"
          name="jpegQuality"
          inputMode="numeric"
          autoComplete="off"
          min={50}
          max={100}
          value={value.jpegQuality}
          onChange={onJpegQuality}
          disabled={value.outputFormat !== "JPEG"}
          className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1.5 text-sm disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
        />
      </Field>

      <Field label="主题">
        <select
          data-testid="setting-theme"
          name="theme"
          value={value.theme}
          onChange={onTheme}
          className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1.5 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
        >
          <option value="light">浅色</option>
          <option value="dark">深色</option>
          <option value="system">跟随系统</option>
        </select>
      </Field>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={value.exportImage}
          onChange={onExportImage}
          className="w-4 h-4 accent-sky-600"
        />
        <span className="text-sm text-slate-700">导出图片</span>
      </label>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={value.avoidTextCut}
          onChange={onAvoidTextCut}
          className="w-4 h-4 accent-sky-600"
        />
        <span className="text-sm text-slate-700">避开文字切图（推荐）</span>
      </label>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <label className="block space-y-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        {hint && <span className="text-slate-400">{hint}</span>}
      </div>
      {children}
    </label>
  );
}
