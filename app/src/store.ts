/**
 * App 全局状态（V6.0.0 Phase 4）
 *
 * 用 Zustand 集中管理 App.tsx 里散落的 10+ useState，
 * 避免 prop drilling，并让子组件可选择性订阅。
 *
 * 状态分组：
 * - 生命周期: step, error
 * - 源图: sourcePath, sourceInfo
 * - 切片: slices, cuts, selectedCutId
 * - 拼装: assembledHtml, assembledCids
 * - 进度: tasks
 * - UI: showSettings, settings
 * - Sidecar: status, sidecarError
 */
import { create } from "zustand";

import { DEFAULT_SETTINGS, type Settings } from "./components/SettingsPanel";
import type { ProgressTask } from "./components/ProgressBar";

export type Step = "idle" | "slicing" | "edit-cuts" | "assemble" | "done";
export type Theme = "dark" | "light";

export interface SourceInfo {
  width: number;
  height: number;
  format: string;
  mode: string;
  size_bytes: number;
}

export interface CutLine {
  id: string;
  y: number;
}

export interface SliceMeta {
  path: string;
  width: number;
  height: number;
  index: number;
}

export interface SidecarStatus {
  pid: number;
  platform: string;
  uptime_seconds: number;
  last_ping: number | null;
  is_alive: boolean;
}

export interface AppState {
  // 生命周期
  step: Step;
  error: string | null;

  // 源图
  sourcePath: string | null;
  sourceInfo: SourceInfo | null;

  // 切片
  slices: SliceMeta[];
  cuts: CutLine[];
  selectedCutId: string | null;

  // 拼装
  assembledHtml: string | null;
  assembledCids: Record<string, string>;

  // 进度
  tasks: ProgressTask[];

  // UI
  showSettings: boolean;
  settings: Settings;
  theme: Theme;

  // Sidecar
  status: SidecarStatus | null;
  sidecarError: string | null;

  // Actions
  setStep: (step: Step) => void;
  setError: (e: string | null) => void;
  setSourcePath: (p: string | null) => void;
  setSourceInfo: (i: SourceInfo | null) => void;
  setSlices: (s: SliceMeta[]) => void;
  setCuts: (c: CutLine[]) => void;
  setSelectedCutId: (id: string | null) => void;
  setAssembledHtml: (h: string | null) => void;
  setAssembledCids: (c: Record<string, string>) => void;
  setTasks: (t: ProgressTask[]) => void;
  patchTask: (id: string, patch: Partial<ProgressTask>) => void;
  setShowSettings: (s: boolean) => void;
  setSettings: (s: Settings) => void;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
  setStatus: (s: SidecarStatus | null) => void;
  setSidecarError: (e: string | null) => void;
  reset: () => void;
}

const INITIAL: Omit<AppState,
  | "setStep" | "setError" | "setSourcePath" | "setSourceInfo" | "setSlices"
  | "setCuts" | "setSelectedCutId" | "setAssembledHtml" | "setAssembledCids"
  | "setTasks" | "patchTask" | "setShowSettings" | "setSettings"
  | "setTheme" | "toggleTheme" | "setStatus" | "setSidecarError" | "reset"
> = {
  step: "idle",
  error: null,
  sourcePath: null,
  sourceInfo: null,
  slices: [],
  cuts: [],
  selectedCutId: null,
  assembledHtml: null,
  assembledCids: {},
  tasks: [],
  showSettings: false,
  settings: DEFAULT_SETTINGS,
  theme: "dark",
  status: null,
  sidecarError: null,
};

export const useAppStore = create<AppState>((set) => ({
  ...INITIAL,
  setStep: (step) => set({ step }),
  setError: (error) => set({ error }),
  setSourcePath: (sourcePath) => set({ sourcePath }),
  setSourceInfo: (sourceInfo) => set({ sourceInfo }),
  setSlices: (slices) => set({ slices }),
  setCuts: (cuts) => set({ cuts }),
  setSelectedCutId: (selectedCutId) => set({ selectedCutId }),
  setAssembledHtml: (assembledHtml) => set({ assembledHtml }),
  setAssembledCids: (assembledCids) => set({ assembledCids }),
  setTasks: (tasks) => set({ tasks }),
  patchTask: (id, patch) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...patch } : t)),
    })),
  setShowSettings: (showSettings) => set({ showSettings }),
  setSettings: (settings) => set({ settings }),
  setTheme: (theme) => set({ theme }),
  toggleTheme: () => set((s) => ({ theme: s.theme === "dark" ? "light" : "dark" })),
  setStatus: (status) => set({ status }),
  setSidecarError: (sidecarError) => set({ sidecarError }),
  reset: () => set({ ...INITIAL, settings: get().settings }),
}));

function get(): { settings: Settings } {
  return useAppStore.getState();
}
