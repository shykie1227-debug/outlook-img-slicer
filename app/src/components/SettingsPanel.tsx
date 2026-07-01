/**
 * SettingsPanel 组件（V6.0.0 Phase 3.6 简化版）
 *
 * 设置面板：
 * - 邮件默认宽度 [400, 1200]
 * - 切片最大高度 [500, 6000]
 * - 输出格式 PNG / JPEG
 * - JPEG 质量 [50, 100]
 * - 主题 浅色 / 深色 / 跟随系统
 *
 * 加载策略（I5 修复）：
 * - 父组件（App.tsx）在 useState lazy init 阶段从 localStorage 读取
 * - SettingsPanel 只负责显示和回写，不做反向 setState（避免重复渲染）
 */
import { type ChangeEvent } from "react";

export interface Settings {
  emailWidth: number;
  maxSliceHeight: number;
  outputFormat: "PNG" | "JPEG";
  jpegQuality: number;
  theme: "light" | "dark" | "system";
}

export const DEFAULT_SETTINGS: Settings = {
  emailWidth: 960,
  maxSliceHeight: 2000,
  outputFormat: "PNG",
  jpegQuality: 95,
  theme: "dark",
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

  const onEmailWidth = (e: ChangeEvent<HTMLInputElement>): void => {
    const v = clamp(parseInt(e.target.value, 10) || 0, 400, 1200);
    patch({ emailWidth: v });
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

  const reset = (): void => {
    onChange(DEFAULT_SETTINGS);
    if (persist) saveToStorage(DEFAULT_SETTINGS);
  };

  return (
    <div
      data-testid="settings-panel"
      className="w-full max-w-md mx-auto p-4 rounded-lg border border-slate-800 bg-slate-900/60 space-y-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">设置</h3>
        <button
          data-testid="reset-settings"
          onClick={reset}
          className="text-xs text-slate-500 hover:text-rose-400"
        >
          恢复默认
        </button>
      </div>

      <Field label="邮件宽度（px）" hint="[400, 1200]">
        <input
          data-testid="setting-emailWidth"
          type="number"
          name="emailWidth"
          inputMode="numeric"
          autoComplete="off"
          min={400}
          max={1200}
          value={value.emailWidth}
          onChange={onEmailWidth}
          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        />
      </Field>

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
          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        />
      </Field>

      <Field label="输出格式">
        <select
          data-testid="setting-outputFormat"
          name="outputFormat"
          value={value.outputFormat}
          onChange={onFormat}
          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
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
          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        />
      </Field>

      <Field label="主题">
        <select
          data-testid="setting-theme"
          name="theme"
          value={value.theme}
          onChange={onTheme}
          className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        >
          <option value="light">浅色</option>
          <option value="dark">深色</option>
          <option value="system">跟随系统</option>
        </select>
      </Field>
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
        <span className="text-slate-400">{label}</span>
        {hint && <span className="text-slate-600">{hint}</span>}
      </div>
      {children}
    </label>
  );
}
