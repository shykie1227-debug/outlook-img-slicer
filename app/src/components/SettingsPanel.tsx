/**
 * SettingsPanel 组件（V6.1.0 — 豆包风格）
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
  compressImage: boolean;
  compressQuality: number;
  compressFormat: "JPEG" | "PNG";
}

export const DEFAULT_SETTINGS: Settings = {
  emailWidth: 650,
  maxSliceHeight: 2000,
  outputFormat: "PNG",
  jpegQuality: 95,
  theme: "light",
  exportImage: false,
  avoidTextCut: true,
  compressImage: false,
  compressQuality: 80,
  compressFormat: "JPEG",
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

  const inputStyle: React.CSSProperties = {
    width: "100%",
    height: "34px",
    background: "var(--color-card)",
    border: "1px solid var(--color-border)",
    borderRadius: "8px",
    color: "var(--color-text)",
    fontSize: "12px",
    padding: "0 8px",
    outline: "none",
    fontFamily: "inherit",
  };

  return (
    <div
      data-testid="settings-panel"
      className="w-full max-w-md mx-auto p-4 space-y-4"
      style={{
        background: "#fff",
        border: "1px solid var(--color-border)",
        borderRadius: "12px",
      }}
    >
      <div className="flex items-center justify-between">
        <h3
          className="text-sm font-semibold"
          style={{ color: "var(--color-text)" }}
        >
          高级设置
        </h3>
        <button
          data-testid="reset-settings"
          onClick={reset}
          className="text-xs"
          style={{ color: "var(--color-text-weak)" }}
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
          style={inputStyle}
        />
      </Field>

      <Field label="输出格式">
        <select
          data-testid="setting-outputFormat"
          name="outputFormat"
          value={value.outputFormat}
          onChange={onFormat}
          style={inputStyle}
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
          style={{ ...inputStyle, opacity: value.outputFormat !== "JPEG" ? 0.5 : 1 }}
        />
      </Field>

      <Field label="主题">
        <select
          data-testid="setting-theme"
          name="theme"
          value={value.theme}
          onChange={onTheme}
          style={inputStyle}
        >
          <option value="light">浅色</option>
          <option value="dark">深色</option>
          <option value="system">跟随系统</option>
        </select>
      </Field>

      <label className="doubao-checkbox">
        <span className="text-xs font-medium">导出图片</span>
        <input
          type="checkbox"
          checked={value.exportImage}
          onChange={onExportImage}
        />
        <span className="doubao-checkbox-box">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
        </span>
      </label>

      <label className="doubao-checkbox">
        <span className="text-xs font-medium">避开文字切图（推荐）</span>
        <input
          type="checkbox"
          checked={value.avoidTextCut}
          onChange={onAvoidTextCut}
        />
        <span className="doubao-checkbox-box">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
        </span>
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
        <span style={{ color: "var(--color-text-secondary)" }}>{label}</span>
        {hint && <span style={{ color: "var(--color-text-weak)" }}>{hint}</span>}
      </div>
      {children}
    </label>
  );
}
