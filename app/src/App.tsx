/**
 * App 根组件（V6.0.3 Phase 5）
 *
 * 工作流：
 * 1. idle → 点击 DropZone 触发 window.api.openImage() 真实选择图片
 * 2. slicing → 调用 image.info / image.slice（带进度）
 * 3. edit-cuts → 切线编辑器（CutEditor）+ 实时 safe-file 预览
 * 4. assemble → 调用 html.assemble
 * 5. done → 复制 / 创建草稿 / 保存 HTML
 *
 * 状态管理：useAppStore（Zustand）
 * 主题：ThemeSwitcher 同步 <html> class="dark"
 * 动画：Framer Motion AnimatePresence 切换 step
 */
import { useEffect } from "react";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";

import { DropZone } from "./components/DropZone";
import { CutEditor, type CutLine } from "./components/CutEditor";
import { ProgressBar, type ProgressTask } from "./components/ProgressBar";
import { SettingsPanel, type Settings } from "./components/SettingsPanel";
import { ImagePreview } from "./components/ImagePreview";
import { ThemeSwitcher } from "./components/ThemeSwitcher";

import { useAppStore, type Step, type SidecarStatus } from "./store";

export type { Step };

/** 错误信息归一化（export 用于 App.test.tsx） */
export function getErrorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (e === null) return "null";
  if (e === undefined) return "undefined";
  return String(e);
}

const DEFAULT_CUT_OPTIONS = {
  minSegmentPx: 80,
  maxSegmentPx: 1200,
  snapThresholdPx: 5,
};

/** 步骤转场动画配置：reducedMotion 时退化为 0 持续 */
const STEP_TRANSITION = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.2 },
};

export function App(): JSX.Element {
  const {
    step,
    error,
    sourcePath,
    sourceInfo,
    slices,
    cuts,
    selectedCutId,
    tasks,
    showSettings,
    settings,
    assembledHtml,
    status,
    sidecarError,
    setStep,
    setError,
    setSourcePath,
    setSourceInfo,
    setSlices,
    setCuts,
    setSelectedCutId,
    setTasks,
    patchTask,
    setShowSettings,
    setSettings,
    setStatus,
    setSidecarError,
    setAssembledHtml,
    setAssembledCids,
    reset,
  } = useAppStore((s) => ({
    step: s.step,
    error: s.error,
    sourcePath: s.sourcePath,
    sourceInfo: s.sourceInfo,
    slices: s.slices,
    cuts: s.cuts,
    selectedCutId: s.selectedCutId,
    tasks: s.tasks,
    showSettings: s.showSettings,
    settings: s.settings,
    assembledHtml: s.assembledHtml,
    status: s.status,
    sidecarError: s.sidecarError,
    setStep: s.setStep,
    setError: s.setError,
    setSourcePath: s.setSourcePath,
    setSourceInfo: s.setSourceInfo,
    setSlices: s.setSlices,
    setCuts: s.setCuts,
    setSelectedCutId: s.setSelectedCutId,
    setTasks: s.setTasks,
    patchTask: s.patchTask,
    setShowSettings: s.setShowSettings,
    setSettings: s.setSettings,
    setStatus: s.setStatus,
    setSidecarError: s.setSidecarError,
    setAssembledHtml: s.setAssembledHtml,
    setAssembledCids: s.setAssembledCids,
    reset: s.reset,
  }));

  // ─────────────────────────────────────
  // Sidecar 状态订阅
  // ─────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    void window.api.sidecarStatus().then((s: SidecarStatus) => {
      if (!cancelled) setStatus(s);
    });
    const offReady = window.api.onSidecarReady(() => {
      void window.api.sidecarStatus().then((s: SidecarStatus) => setStatus(s));
    });
    const offExit = window.api.onSidecarExit(() => {
      void window.api.sidecarStatus().then((s: SidecarStatus) => setStatus(s));
    });
    const offRestart = window.api.onSidecarRestart(() => {
      void window.api.sidecarStatus().then((s: SidecarStatus) => setStatus(s));
    });
    const offError = window.api.onSidecarError((msg: string) => {
      setSidecarError(msg);
    });
    return () => {
      cancelled = true;
      offReady();
      offExit();
      offRestart();
      offError();
    };
  }, [setStatus, setSidecarError]);

  // 持久化 settings
  useEffect(() => {
    try {
      localStorage.setItem(
        "outlook-img-slicer-settings",
        JSON.stringify(settings)
      );
    } catch {
      /* ignore */
    }
  }, [settings]);

  // 初始从 localStorage 恢复 settings
  useEffect(() => {
    try {
      const raw = localStorage.getItem("outlook-img-slicer-settings");
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<Settings>;
        setSettings({ ...settings, ...parsed });
      }
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─────────────────────────────────────
  // 文件处理工作流
  // ─────────────────────────────────────
  const onPickFile = async (): Promise<void> => {
    setError(null);
    const r = await window.api.openImage();
    if (!r.path) return; // 用户取消
    void onPathReady(r.path);
  };

  /** DropZone 拖拽时也能用（拿 File 对象） */
  const onDropFile = async (file: File): Promise<void> => {
    setError(null);
    let filePath = "";
    try {
      filePath = window.api.getPathForFile(file);
    } catch {
      filePath = `/tmp/${file.name}`;
    }
    void onPathReady(filePath);
  };

  const onPathReady = async (filePath: string): Promise<void> => {
    setSourcePath(filePath);
    setStep("slicing");
    setTasks([{ id: "info", name: "读取图片信息", progress: 0 }]);
    try {
      const info = await window.api.imageInfo({ path: filePath });
      setSourceInfo(info);
      const nextTasks: ProgressTask[] = [
        ...useAppStore.getState().tasks.map((x) =>
          x.id === "info" ? { ...x, progress: 1, done: true } : x
        ),
        { id: "slice", name: "切片", progress: 0 },
      ];
      setTasks(nextTasks);
      const sliceRes = await window.api.imageSlice({
        path: filePath,
        max_h: settings.maxSliceHeight,
      });
      setSlices(sliceRes.slices);
      const finalTasks = useAppStore.getState().tasks.map((x) =>
        x.id === "slice" ? { ...x, progress: 1, done: true } : x
      );
      setTasks(finalTasks);
      setStep("edit-cuts");
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      patchTask("info", { error: msg });
      setStep("idle");
    }
  };

  const onCutsChange = (newCuts: CutLine[]): void => {
    setCuts(newCuts);
  };

  const onAssemble = async (): Promise<void> => {
    setStep("assemble");
    setTasks([{ id: "assemble", name: "拼装 HTML", progress: 0.2 }]);
    try {
      const r = await window.api.htmlAssemble({
        slices: slices.map((s) => ({
          path: s.path,
          width: s.width,
          height: s.height,
          sort_key: s.index + 1,
          original_width: sourceInfo?.width ?? 0,
        })),
        display_w: settings.emailWidth,
      });
      setAssembledHtml(r.html);
      setAssembledCids(r.cid_files);
      const finalTasks: ProgressTask[] = useAppStore
        .getState()
        .tasks.map((x) =>
          x.id === "assemble" ? { ...x, progress: 1, done: true } : x
        );
      setTasks(finalTasks);
      setStep("done");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onCopyClipboard = async (): Promise<void> => {
    try {
      let html = assembledHtml;
      if (!html) {
        const r = await window.api.htmlAssemble({
          slices: slices.map((s) => ({
            path: s.path,
            width: s.width,
            height: s.height,
            sort_key: s.index + 1,
            original_width: sourceInfo?.width ?? 0,
          })),
          display_w: settings.emailWidth,
        });
        html = r.html;
        setAssembledHtml(html);
        setAssembledCids(r.cid_files);
      }
      const clip = await window.api.htmlClipboard({ html });
      await window.api.outlookCopyClipboard({ cf_html: clip.cf_html });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onCreateDraft = async (): Promise<void> => {
    try {
      // Outlook Word 引擎不支持 base64 图片，必须用 CID 附件模式
      // 不复用 assembledHtml 缓存（那是 base64 模式），始终重新生成 CID 模式
      const r = await window.api.htmlAssemble({
        slices: slices.map((s) => ({
          path: s.path,
          width: s.width,
          height: s.height,
          sort_key: s.index + 1,
          original_width: sourceInfo?.width ?? 0,
        })),
        display_w: settings.emailWidth,
        mode: "cid",
      });
      await window.api.outlookCreateDraft({
        html: r.html,
        subject: sourceInfo ? `${sourceInfo.width}×${sourceInfo.height} 长图` : "长图",
        cid_files: r.cid_files,
      });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onSaveHtml = async (): Promise<void> => {
    try {
      let html: string = assembledHtml ?? "";
      if (!html) {
        const r = await window.api.htmlAssemble({
          slices: slices.map((s) => ({
            path: s.path,
            width: s.width,
            height: s.height,
            sort_key: s.index + 1,
            original_width: sourceInfo?.width ?? 0,
          })),
          display_w: settings.emailWidth,
        });
        html = r.html;
        setAssembledHtml(html);
        setAssembledCids(r.cid_files);
      }
      const r = await window.api.saveHtml({ defaultPath: "long-image.html" });
      if (!r.path) return;
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = r.path.split(/[/\\]/).pop() ?? "long-image.html";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onReset = (): void => {
    reset();
  };

  // ─────────────────────────────────────
  // 渲染
  // ─────────────────────────────────────
  return (
    <MotionConfig reducedMotion="user">
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-900 dark:text-slate-100 flex flex-col transition-colors duration-200">
      <header className="border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            aria-hidden="true"
            className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-white font-bold"
          >
            ✂
          </div>
          <h1 className="text-xl font-semibold">Outlook 长图助手</h1>
          <span
            aria-hidden="true"
            className="px-2 py-0.5 text-xs rounded-full bg-sky-500/20 text-sky-700 dark:text-sky-300 border border-sky-500/30"
          >
            V6.0.3
          </span>
        </div>
        <div className="flex items-center gap-2">
          {sourceInfo && (
            <button
              onClick={onReset}
              className="px-3 py-1.5 text-sm rounded-md text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              重新开始
            </button>
          )}
          <button
            data-testid="open-settings"
            onClick={() => setShowSettings(!showSettings)}
            aria-expanded={showSettings}
            className="px-3 py-1.5 text-sm rounded-md text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            <span aria-hidden="true" className="mr-1">⚙</span>
            设置
          </button>
          <ThemeSwitcher />
          <SidecarStatusBadge status={status} error={sidecarError} />
        </div>
      </header>

      <main className="flex-1 overflow-auto p-6 space-y-4">
        <AnimatePresence mode="wait">
          {error && (
            <motion.div
              key="error"
              {...STEP_TRANSITION}
              role="status"
              aria-live="polite"
              className="max-w-2xl mx-auto p-3 rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-sm"
            >
              错误：{error}
            </motion.div>
          )}

          {showSettings && (
            <motion.div key="settings" {...STEP_TRANSITION}>
              <SettingsPanel value={settings} onChange={setSettings} />
            </motion.div>
          )}

          {tasks.length > 0 && (
            <motion.div key="progress" {...STEP_TRANSITION}>
              <ProgressBar visible tasks={tasks} />
            </motion.div>
          )}

          {step === "idle" && (
            <motion.div
              key="idle"
              {...STEP_TRANSITION}
              className="flex items-center justify-center min-h-[60vh]"
            >
              <DropZone onFile={onDropFile} onPick={onPickFile} />
            </motion.div>
          )}

          {step !== "idle" && sourceInfo && sourcePath && (
            <motion.div
              key="edit"
              {...STEP_TRANSITION}
              className="max-w-4xl mx-auto space-y-4"
            >
              <div className="flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
                <span>
                  原图 {sourceInfo.width}×{sourceInfo.height} · {sourceInfo.format} ·{" "}
                  {(sourceInfo.size_bytes / 1024).toFixed(1)} KB
                </span>
                <span>{slices.length} 个切片</span>
              </div>

              <ImagePreview
                path={sourcePath}
                width={sourceInfo.width}
                height={sourceInfo.height}
                maxHeight={400}
              />

              <CutEditor
                image={{ width: sourceInfo.width, height: sourceInfo.height }}
                cuts={cuts}
                selectedId={selectedCutId}
                options={DEFAULT_CUT_OPTIONS}
                onChange={onCutsChange}
                onSelect={setSelectedCutId}
              />

              {step === "edit-cuts" && (
                <div className="flex justify-end gap-2">
                  <button
                    data-testid="assemble-html"
                    onClick={onAssemble}
                    className="px-4 py-2 rounded-md bg-sky-600 hover:bg-sky-500 text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
                  >
                    拼装 HTML <span aria-hidden="true">→</span>
                  </button>
                </div>
              )}

              {(step === "edit-cuts" || step === "done") && (
                <div className="flex flex-wrap justify-end gap-2 p-4 rounded-md border border-emerald-500/30 bg-emerald-500/10">
                  <button
                    data-testid="save-html"
                    onClick={onSaveHtml}
                    className="px-4 py-2 rounded-md bg-slate-700 hover:bg-slate-600 text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                  >
                    <span aria-hidden="true" className="mr-1">💾</span>
                    保存 HTML
                  </button>
                  <button
                    data-testid="copy-clipboard"
                    onClick={onCopyClipboard}
                    title="复制为自包含 HTML，适用于 Gmail / 网页邮箱；Outlook 桌面版不支持 base64 图片，请改用『创建 Outlook 草稿』"
                    className="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
                  >
                    <span aria-hidden="true" className="mr-1">📋</span>
                    复制到剪贴板
                  </button>
                  <button
                    data-testid="create-draft"
                    onClick={onCreateDraft}
                    className="px-4 py-2 rounded-md bg-sky-600 hover:bg-sky-500 text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
                  >
                    <span aria-hidden="true" className="mr-1">✉</span>
                    创建 Outlook 草稿
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <footer className="border-t border-slate-200 dark:border-slate-800 px-6 py-3 text-xs text-slate-500 flex justify-between">
        <span>
          Outlook 长图助手 V6.0.3 · Electron {window.api.versions.electron} · Chrome {window.api.versions.chrome} · Node{" "}
          {window.api.versions.node}
        </span>
        <span>本地运行 · 不联网 · 不上传</span>
      </footer>
    </div>
    </MotionConfig>
  );
}

function SidecarStatusBadge({
  status,
  error,
}: {
  status: { pid: number; platform: string } | null;
  error: string | null;
}): JSX.Element {
  if (error) {
    return (
      <div
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm"
        data-testid="sidecar-error"
        role="status"
        aria-live="polite"
      >
        <span aria-hidden="true" className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />
        Sidecar 异常：{error}
      </div>
    );
  }
  if (!status) {
    return (
      <div
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-800 text-slate-400 text-sm"
        role="status"
        aria-live="polite"
      >
        <span aria-hidden="true" className="w-2 h-2 rounded-full bg-slate-500 animate-pulse" />
        Sidecar 连接中…
      </div>
    );
  }
  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm"
      role="status"
    >
      <span aria-hidden="true" className="w-2 h-2 rounded-full bg-emerald-400" />
      <span data-testid="sidecar-status-text">在线</span>
      <span aria-hidden="true" className="text-slate-400">·</span>
      <span data-testid="sidecar-pid">PID {status.pid}</span>
      <span aria-hidden="true" className="text-slate-400">·</span>
      <span>{status.platform}</span>
    </div>
  );
}
