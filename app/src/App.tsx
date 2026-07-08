/**
 * App 根组件（V6.0.3 — V5 浅色还原版）
 *
 * 还原 V5 浅色完整布局：
 * 标题 + 副标题 → 步骤条 → DropZone → 设置行 → 操作按钮 → 邮件标题 → 提示 → 底部按钮 → 页脚
 *
 * 业务逻辑不变：onCopyClipboard / onCreateDraft / onAssemble / onSaveHtml / CutEditor / HotspotEditor
 */
import { useEffect, useState } from "react";

import { DropZone } from "./components/DropZone";
import { CutEditor, type CutLine } from "./components/CutEditor";
import { HotspotEditor, type Hotspot } from "./components/HotspotEditor";
import { ProgressBar, type ProgressTask } from "./components/ProgressBar";
import { SettingsPanel, type Settings } from "./components/SettingsPanel";
import { ImagePreview } from "./components/ImagePreview";

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

const DEFAULT_HOTSPOT_OPTIONS = {
  minSizePx: 20,
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

  // V5 本地 UI 状态
  const [showCutEditor, setShowCutEditor] = useState(false);
  const [showHotspotEditor, setShowHotspotEditor] = useState(false);
  const [emailSubject, setEmailSubject] = useState("");
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [selectedHotspotId, setSelectedHotspotId] = useState<string | null>(null);

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
    if (!r.path) return;
    void onPathReady(r.path);
  };

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
        subject: emailSubject || (sourceInfo ? `${sourceInfo.width}×${sourceInfo.height} 长图` : "长图"),
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
    setShowCutEditor(false);
    setShowHotspotEditor(false);
    setEmailSubject("");
    setHotspots([]);
    setSelectedHotspotId(null);
  };

  // ─────────────────────────────────────
  // 渲染
  // ─────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#F8F9FA", color: "#24292E" }}>
      {/* 顶部标题区 */}
      <header className="text-center pt-8 pb-4">
        <h1 className="text-2xl font-bold" style={{ color: "#24292E" }}>
          Outlook 长图助手 V6.0.3
        </h1>
        <p className="text-sm mt-1" style={{ color: "#586069" }}>
          长图/PDF/PPT切片后插入Outlook邮件，保持原始清晰度
        </p>
      </header>

      {/* 步骤条 */}
      <div className="flex justify-center pb-4">
        <div
          className="inline-flex items-center gap-3 px-5 py-2 rounded-full text-sm"
          style={{ background: "#F1F3F5", color: "#586069" }}
        >
          <span className="font-medium">1 放入文件</span>
          <span style={{ color: "#D1D5DB" }}>→</span>
          <span className="font-medium">2 调整切线 / 添加链接</span>
          <span style={{ color: "#D1D5DB" }}>→</span>
          <span className="font-medium">3 创建邮件</span>
        </div>
      </div>

      {/* 主内容区 */}
      <main className="flex-1 flex flex-col items-center px-6 pb-4 max-w-3xl mx-auto w-full">
        {/* 错误提示 */}
        {error && (
          <div
            className="w-full p-3 rounded-md text-sm mb-4"
            style={{ background: "#FFF0F0", border: "1px solid #FFD0D0", color: "#CB2431" }}
          >
            错误：{error}
          </div>
        )}

        {/* 进度条 */}
        {tasks.length > 0 && (
          <div className="w-full mb-4">
            <ProgressBar visible tasks={tasks} />
          </div>
        )}

        {/* 高级设置（可折叠） */}
        {showSettings && (
          <div className="w-full mb-4">
            <SettingsPanel value={settings} onChange={setSettings} />
          </div>
        )}

        {/* DropZone（idle 状态） */}
        {step === "idle" && (
          <div className="w-full flex flex-col items-center">
            <DropZone onFile={onDropFile} onPick={onPickFile} />
          </div>
        )}

        {/* 文件已加载后的编辑区 */}
        {step !== "idle" && sourceInfo && sourcePath && (
          <div className="w-full space-y-4">
            {/* 图片预览 */}
            <ImagePreview
              path={sourcePath}
              width={sourceInfo.width}
              height={sourceInfo.height}
              maxHeight={300}
            />

            {/* 文件信息 */}
            <div className="text-xs text-center" style={{ color: "#586069" }}>
              原图 {sourceInfo.width}×{sourceInfo.height} · {sourceInfo.format} ·{" "}
              {(sourceInfo.size_bytes / 1024).toFixed(1)} KB · {slices.length} 个切片
            </div>

            {/* 切线编辑器 */}
            {showCutEditor && (
              <CutEditor
                image={{ width: sourceInfo.width, height: sourceInfo.height }}
                cuts={cuts}
                selectedId={selectedCutId}
                options={DEFAULT_CUT_OPTIONS}
                onChange={onCutsChange}
                onSelect={setSelectedCutId}
              />
            )}

            {/* 热区编辑器 */}
            {showHotspotEditor && slices.length > 0 && (
              <HotspotEditor
                slice={{ width: sourceInfo.width, height: sourceInfo.height }}
                hotspots={hotspots}
                selectedId={selectedHotspotId}
                options={DEFAULT_HOTSPOT_OPTIONS}
                onChange={setHotspots}
                onSelect={setSelectedHotspotId}
              />
            )}
          </div>
        )}

        {/* 设置行 */}
        <div className="w-full flex items-center gap-3 flex-wrap py-3">
          <button
            onClick={onReset}
            className="px-3 py-1.5 text-sm rounded-md transition-colors"
            style={{ background: "#F1F3F5", color: "#586069" }}
          >
            ↺ 重置
          </button>

          <span className="text-sm" style={{ color: "#586069" }}>邮件宽度：</span>
          <input
            type="number"
            min={400}
            max={1200}
            value={settings.emailWidth}
            onChange={(e) => {
              const v = Math.max(400, Math.min(1200, parseInt(e.target.value, 10) || 650));
              setSettings({ ...settings, emailWidth: v });
            }}
            className="w-16 px-2 py-1 text-sm rounded border text-center"
            style={{ borderColor: "#E1E4E8", background: "#FFF", color: "#24292E" }}
          />
          <span className="text-sm" style={{ color: "#586069" }}>px</span>

          {/* 蓝色滑块 */}
          <input
            type="range"
            min={400}
            max={1200}
            step={10}
            value={settings.emailWidth}
            onChange={(e) => setSettings({ ...settings, emailWidth: parseInt(e.target.value, 10) })}
            className="flex-1 min-w-[120px] accent-sky-600"
          />

          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.exportImage}
              onChange={(e) => setSettings({ ...settings, exportImage: e.target.checked })}
              className="w-4 h-4 accent-sky-600"
            />
            <span className="text-sm" style={{ color: "#586069" }}>导出图片</span>
          </label>

          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.avoidTextCut}
              onChange={(e) => setSettings({ ...settings, avoidTextCut: e.target.checked })}
              className="w-4 h-4 accent-sky-600"
            />
            <span className="text-sm" style={{ color: "#586069" }}>避开文字切图（推荐）</span>
          </label>

          <button
            onClick={() => setShowSettings(!showSettings)}
            className="ml-auto px-2 py-1 text-xs rounded transition-colors"
            style={{ color: "#586069" }}
          >
            ⚙ 高级
          </button>
        </div>

        {/* 操作按钮行 */}
        {step !== "idle" && (
          <div className="w-full flex items-center gap-2 flex-wrap py-2">
            <button
              data-testid="copy-clipboard"
              onClick={onCopyClipboard}
              title="复制为自包含 HTML，适用于 Gmail / 网页邮箱；Outlook 桌面版不支持 base64 图片，请改用「创建邮件」"
              className="px-4 py-2 rounded-full text-sm font-medium transition-colors"
              style={{ background: "#F1F3F5", color: "#24292E", border: "1px solid #E1E4E8" }}
            >
              📋 复制到 Outlook
            </button>

            <button
              onClick={() => { setShowCutEditor(!showCutEditor); }}
              className="px-4 py-2 rounded-full text-sm font-medium transition-colors"
              style={{ background: showCutEditor ? "#0078D4" : "#F1F3F5", color: showCutEditor ? "#FFF" : "#24292E", border: "1px solid #E1E4E8" }}
            >
              ✂ 调整切图位置
            </button>

            <button
              onClick={() => { setShowHotspotEditor(!showHotspotEditor); }}
              className="px-4 py-2 rounded-full text-sm font-medium transition-colors"
              style={{ background: showHotspotEditor ? "#0078D4" : "#F1F3F5", color: showHotspotEditor ? "#FFF" : "#24292E", border: "1px solid #E1E4E8" }}
            >
              🔗 添加可点击按钮
            </button>
          </div>
        )}

        {/* 邮件标题 */}
        {step !== "idle" && (
          <div className="w-full py-2">
            <label className="text-sm font-medium block mb-1" style={{ color: "#24292E" }}>
              邮件标题（可选）
            </label>
            <input
              type="text"
              value={emailSubject}
              onChange={(e) => setEmailSubject(e.target.value)}
              placeholder="在此输入邮件标题，留空则使用默认标题"
              className="w-full px-3 py-2 text-sm rounded-md border"
              style={{ borderColor: "#E1E4E8", background: "#FFF", color: "#24292E" }}
            />
          </div>
        )}

        {/* 提示信息 */}
        {step !== "idle" && (
          <div className="w-full py-2 flex items-center gap-2 text-sm" style={{ color: "#586069" }}>
            <span>ℹ️</span>
            <span>拖入文件后自动切图，再检查切线并在经典 Outlook 中创建邮件</span>
          </div>
        )}

        {/* 底部按钮 */}
        {step !== "idle" && (
          <div className="w-full flex items-center gap-3 pt-4 pb-4">
            <button
              data-testid="create-draft"
              onClick={onCreateDraft}
              className="flex-1 px-5 py-2.5 rounded-md font-medium text-sm transition-colors"
              style={{ background: "#0078D4", color: "#FFF" }}
            >
              ✉ 在 Outlook 中创建邮件
            </button>
            <button
              data-testid="save-html"
              onClick={onSaveHtml}
              className="px-5 py-2.5 rounded-md font-medium text-sm transition-colors"
              style={{ background: "#FFF", color: "#24292E", border: "1px solid #E1E4E8" }}
            >
              ↓ 保存切图
            </button>
          </div>
        )}

        {/* Sidecar 状态（底部细微显示） */}
        <div className="w-full text-center text-xs pt-2" style={{ color: "#B0B8C1" }}>
          {sidecarError
            ? `Sidecar 异常：${sidecarError}`
            : status?.is_alive
            ? `Sidecar 在线 · PID ${status.pid}`
            : "Sidecar 连接中…"}
        </div>
      </main>

      {/* 页脚 */}
      <footer className="text-center text-xs py-4" style={{ color: "#B0B8C1" }}>
        V6.0.3 xiaoming
      </footer>
    </div>
  );
}
