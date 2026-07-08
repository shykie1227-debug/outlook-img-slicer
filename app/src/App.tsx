/**
 * App 根组件（V6.1.0 — 豆包风格设计系统）
 *
 * 视觉层按豆包设计规范重写：
 * - 配色 token 统一走 CSS 变量（var(--color-xxx)）
 * - 按钮统一胶丸形（border-radius: 999px），Primary/Secondary 44px，Ghost 34px
 * - 所有 emoji 替换为 icons/ 目录下的 Lucide 风格 SVG
 *
 * 业务逻辑：onCopyClipboard / onCreateDraft / onSaveClick → onExportConfirm / doSaveHtml / CutEditor / HotspotEditor
 */
import { useEffect, useState } from "react";

import { DropZone } from "./components/DropZone";
import { CutEditor, type CutLine } from "./components/CutEditor";
import { HotspotEditor, type Hotspot } from "./components/HotspotEditor";
import { ProgressBar, type ProgressTask } from "./components/ProgressBar";
import { SettingsPanel, type Settings } from "./components/SettingsPanel";
import { ImagePreview } from "./components/ImagePreview";
import { Icon } from "./components/icons";

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

  // 导出弹窗状态
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportCompress, setExportCompress] = useState(false);
  const [exportQuality, setExportQuality] = useState(80);
  const [exportFormat, setExportFormat] = useState<"JPEG" | "PNG">("JPEG");

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

  /** 点击"保存切图" → 打开导出弹窗 */
  const onSaveClick = (): void => {
    setExportCompress(settings.compressImage);
    setExportQuality(settings.compressQuality);
    setExportFormat(settings.compressFormat);
    setShowExportDialog(true);
  };

  /** 导出弹窗确认 → 执行保存（按弹窗中的压缩设置） */
  const onExportConfirm = async (): Promise<void> => {
    setShowExportDialog(false);
    // 持久化弹窗中的压缩设置
    setSettings({
      ...settings,
      compressImage: exportCompress,
      compressQuality: exportQuality,
      compressFormat: exportFormat,
    });
    // 压缩开启时需要重新拼装，清掉缓存
    if (exportCompress) {
      setAssembledHtml(null);
    }
    await doSaveHtml(exportCompress, exportQuality, exportFormat);
  };

  /** 实际保存逻辑（compress/quality/format 由弹窗传入） */
  const doSaveHtml = async (
    compress: boolean,
    quality: number,
    format: "JPEG" | "PNG"
  ): Promise<void> => {
    try {
      let html: string = assembledHtml ?? "";
      if (!html) {
        let slicesToUse = slices;
        if (compress) {
          const cr = await window.api.imageCompress({
            slices: slices.map((s) => ({
              path: s.path,
              width: s.width,
              height: s.height,
              index: s.index,
            })),
            format,
            quality,
          });
          slicesToUse = slices.map((s, i) => ({
            ...s,
            path: cr.slices[i]?.path ?? s.path,
          }));
        }
        const r = await window.api.htmlAssemble({
          slices: slicesToUse.map((s) => ({
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
    <div
      className="min-h-screen flex flex-col"
      style={{ background: "var(--color-bg)", color: "var(--color-text)" }}
    >
      {/* 顶部标题区 */}
      <header className="text-center pt-8 pb-3">
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--color-text)" }}
        >
          Outlook 长图助手 V6.1.0
        </h1>
        <p
          className="text-xs mt-1"
          style={{ color: "var(--color-text-secondary)" }}
        >
          长图/PDF/PPT切片后插入Outlook邮件，保持原始清晰度
        </p>
      </header>

      {/* 步骤条（胶丸形） */}
      <div className="flex justify-center pb-4">
        <div
          className="inline-flex items-center gap-3 px-5 py-2 text-xs font-medium"
          style={{
            background: "var(--color-muted)",
            border: "1px solid var(--color-border)",
            borderRadius: "999px",
            color: "var(--color-text-secondary)",
            letterSpacing: "0.3px",
          }}
        >
          <span>1 放入文件</span>
          <span style={{ color: "var(--color-border-hover)" }}>→</span>
          <span>2 调整切线 / 添加链接</span>
          <span style={{ color: "var(--color-border-hover)" }}>→</span>
          <span>3 创建邮件</span>
        </div>
      </div>

      {/* 主内容区 */}
      <main className="flex-1 flex flex-col items-center px-6 pb-4 max-w-3xl mx-auto w-full">
        {/* 错误提示 */}
        {error && (
          <div
            className="w-full p-3 mb-4 flex items-center gap-2 text-sm"
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "8px",
              color: "var(--color-error)",
            }}
          >
            <img src={Icon.alertTriangle} alt="" className="w-4 h-4 flex-shrink-0" />
            <span>错误：{error}</span>
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
          <div className="w-full space-y-3">
            {/* 图片预览 */}
            <ImagePreview
              path={sourcePath}
              width={sourceInfo.width}
              height={sourceInfo.height}
              maxHeight={300}
            />

            {/* 文件信息 */}
            <div
              className="text-xs text-center"
              style={{ color: "var(--color-text-weak)" }}
            >
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
        <div className="w-full flex items-center gap-2.5 flex-wrap py-3 justify-center">
          {/* 重置（Ghost 34px） */}
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1 px-3.5 text-xs transition-colors"
            style={{
              height: "34px",
              background: "var(--color-muted)",
              border: "none",
              borderRadius: "999px",
              color: "var(--color-text)",
              fontFamily: "inherit",
            }}
          >
            <img src={Icon.rotateCcw} alt="" className="w-[18px] h-[18px]" />
            重置
          </button>

          <span
            className="text-xs"
            style={{ color: "var(--color-text-secondary)" }}
          >
            邮件宽度：
          </span>
          <input
            type="number"
            min={400}
            max={1200}
            value={settings.emailWidth}
            onChange={(e) => {
              const v = Math.max(400, Math.min(1200, parseInt(e.target.value, 10) || 650));
              setSettings({ ...settings, emailWidth: v });
            }}
            className="w-[80px] text-center text-xs outline-none"
            style={{
              height: "34px",
              background: "var(--color-card)",
              border: "1px solid var(--color-border)",
              borderRadius: "8px",
              color: "var(--color-text)",
              fontFamily: "inherit",
            }}
          />
          <span
            className="text-xs"
            style={{ color: "var(--color-text-weak)" }}
          >
            px
          </span>

          {/* 蓝色滑块 */}
          <input
            type="range"
            min={400}
            max={1200}
            step={10}
            value={settings.emailWidth}
            onChange={(e) => setSettings({ ...settings, emailWidth: parseInt(e.target.value, 10) })}
            className="doubao-slider"
            style={{ width: "140px" }}
          />

          {/* 复选框：导出图片 */}
          <label className="doubao-checkbox">
            <img src={Icon.image} alt="" className="w-[18px] h-[18px]" />
            <span className="text-xs font-medium">导出图片</span>
            <input
              type="checkbox"
              checked={settings.exportImage}
              onChange={(e) => setSettings({ ...settings, exportImage: e.target.checked })}
            />
            <span className="doubao-checkbox-box">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            </span>
          </label>

          <span className="doubao-sep">│</span>

          {/* 复选框：避开文字切图 */}
          <label className="doubao-checkbox">
            <span className="text-xs font-medium">避开文字切图（推荐）</span>
            <input
              type="checkbox"
              checked={settings.avoidTextCut}
              onChange={(e) => setSettings({ ...settings, avoidTextCut: e.target.checked })}
            />
            <span className="doubao-checkbox-box">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            </span>
          </label>

          {/* 高级 */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="inline-flex items-center gap-1 px-3 text-xs transition-colors ml-auto"
            style={{
              height: "34px",
              background: "transparent",
              border: "none",
              borderRadius: "999px",
              color: "var(--color-text-weak)",
              fontFamily: "inherit",
            }}
          >
            <img src={Icon.palette} alt="" className="w-[18px] h-[18px]" />
            高级
          </button>
        </div>

        {/* 操作按钮行（Ghost 34px） */}
        {step !== "idle" && (
          <div className="w-full flex items-center gap-2.5 flex-wrap py-2 justify-center">
            <button
              data-testid="copy-clipboard"
              onClick={onCopyClipboard}
              title="复制为自包含 HTML，适用于 Gmail / 网页邮箱；Outlook 桌面版不支持 base64 图片，请改用「创建邮件」"
              className="doubao-ghost-btn"
            >
              <img src={Icon.clipboardCopy} alt="" className="w-[18px] h-[18px]" />
              复制到 Outlook
            </button>

            <button
              onClick={() => { setShowCutEditor(!showCutEditor); }}
              className="doubao-ghost-btn"
              style={
                showCutEditor
                  ? { background: "var(--color-primary)", color: "#fff" }
                  : undefined
              }
            >
              <img src={Icon.scissors} alt="" className="w-[18px] h-[18px]" />
              调整切图位置
            </button>

            <button
              onClick={() => { setShowHotspotEditor(!showHotspotEditor); }}
              className="doubao-ghost-btn"
              style={
                showHotspotEditor
                  ? { background: "var(--color-primary)", color: "#fff" }
                  : undefined
              }
            >
              <img src={Icon.mousePointerClick} alt="" className="w-[18px] h-[18px]" />
              添加可点击按钮
            </button>
          </div>
        )}

        {/* 邮件标题 */}
        {step !== "idle" && (
          <div className="w-full py-2">
            <label
              className="text-xs font-medium block mb-1 text-center"
              style={{ color: "var(--color-text)" }}
            >
              邮件标题（可选）
            </label>
            <input
              type="text"
              value={emailSubject}
              onChange={(e) => setEmailSubject(e.target.value)}
              placeholder="在此输入邮件标题，留空则使用默认标题"
              className="w-full text-sm outline-none"
              style={{
                height: "40px",
                background: "var(--color-card)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
                color: "var(--color-text)",
                padding: "0 12px",
                fontFamily: "inherit",
              }}
            />
          </div>
        )}

        {/* 提示信息 */}
        {step !== "idle" && (
          <div
            className="w-full py-2 flex items-center justify-center gap-2 text-xs"
            style={{ color: "var(--color-text-secondary)" }}
          >
            <img src={Icon.info} alt="" className="w-4 h-4" />
            <span>拖入文件后自动切图，再检查切线并在经典 Outlook 中创建邮件</span>
          </div>
        )}

        {/* 底部按钮 */}
        {step !== "idle" && (
          <div className="w-full flex items-center gap-3 pt-3 pb-4">
            <button
              data-testid="create-draft"
              onClick={onCreateDraft}
              className="flex-1 inline-flex items-center justify-center gap-1.5 font-bold text-sm transition-colors"
              style={{
                height: "44px",
                background: "var(--color-primary)",
                color: "#fff",
                border: "none",
                borderRadius: "999px",
                fontFamily: "inherit",
              }}
            >
              <img src={Icon.mail} alt="" className="w-5 h-5" />
              在 Outlook 中创建邮件
            </button>
            <button
              data-testid="save-html"
              onClick={onSaveClick}
              className="flex-1 inline-flex items-center justify-center gap-1.5 font-medium text-sm transition-colors"
              style={{
                height: "44px",
                background: "#fff",
                color: "var(--color-text)",
                border: "1px solid var(--color-border)",
                borderRadius: "999px",
                fontFamily: "inherit",
              }}
            >
              <img src={Icon.arrowDownToLine} alt="" className="w-[18px] h-[18px]" />
              保存切图
            </button>
          </div>
        )}

        {/* Sidecar 状态（底部细微显示） */}
        <div
          className="w-full text-center text-xs pt-2"
          style={{ color: "var(--color-text-weak)" }}
        >
          {sidecarError
            ? `Sidecar 异常：${sidecarError}`
            : status?.is_alive
            ? `Sidecar 在线 · PID ${status.pid}`
            : "Sidecar 连接中…"}
        </div>
      </main>

      {/* 页脚 */}
      <footer
        className="text-center text-xs py-4"
        style={{ color: "var(--color-text-weak)" }}
      >
        V6.1.0 xiaoming
      </footer>

      {/* 导出弹窗 */}
      {showExportDialog && (
        <div
          className="fixed inset-0 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.35)", zIndex: 9999 }}
          onClick={() => setShowExportDialog(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-[420px] max-w-[90vw] p-6"
            style={{
              background: "var(--color-bg)",
              border: "1px solid var(--color-border)",
              borderRadius: "16px",
              boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
            }}
          >
            {/* 标题 */}
            <div className="flex items-center gap-2 mb-5">
              <img src={Icon.arrowDownToLine} alt="" className="w-5 h-5" />
              <h3 className="text-base font-bold" style={{ color: "var(--color-text)" }}>
                导出设置
              </h3>
            </div>

            {/* 压缩选项 */}
            <label className="doubao-checkbox mb-3" style={{ display: "flex" }}>
              <img src={Icon.compress} alt="" className="w-[18px] h-[18px]" />
              <span className="text-sm font-medium">压缩图片</span>
              <input
                type="checkbox"
                checked={exportCompress}
                onChange={(e) => setExportCompress(e.target.checked)}
              />
              <span className="doubao-checkbox-box">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              </span>
            </label>

            {/* 压缩参数（开启时显示） */}
            {exportCompress && (
              <div className="space-y-3 mb-5 pl-1">
                {/* 格式选择 */}
                <div className="flex items-center gap-3">
                  <span className="text-xs" style={{ color: "var(--color-text-secondary)", minWidth: "40px" }}>格式</span>
                  <select
                    value={exportFormat}
                    onChange={(e) => setExportFormat(e.target.value as "JPEG" | "PNG")}
                    className="text-xs outline-none flex-1"
                    style={{
                      height: "34px",
                      background: "var(--color-card)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      color: "var(--color-text)",
                      padding: "0 8px",
                      fontFamily: "inherit",
                    }}
                  >
                    <option value="JPEG">JPEG（有损 / 文件小）</option>
                    <option value="PNG">PNG（无损 / 文件大）</option>
                  </select>
                </div>

                {/* 质量滑块 */}
                <div className="flex items-center gap-3">
                  <span className="text-xs" style={{ color: "var(--color-text-secondary)", minWidth: "40px" }}>质量</span>
                  <input
                    type="range"
                    min={10}
                    max={100}
                    step={5}
                    value={exportQuality}
                    onChange={(e) => setExportQuality(parseInt(e.target.value, 10))}
                    className="doubao-slider flex-1"
                  />
                  <span
                    className="text-xs font-medium"
                    style={{ color: "var(--color-text-secondary)", minWidth: "32px", textAlign: "right" }}
                  >
                    {exportQuality}%
                  </span>
                </div>
              </div>
            )}

            {!exportCompress && <div className="mb-5" />}

            {/* 按钮行 */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowExportDialog(false)}
                className="flex-1 text-sm font-medium transition-colors"
                style={{
                  height: "40px",
                  background: "var(--color-muted)",
                  border: "none",
                  borderRadius: "999px",
                  color: "var(--color-text)",
                  fontFamily: "inherit",
                }}
              >
                取消
              </button>
              <button
                onClick={onExportConfirm}
                className="flex-1 inline-flex items-center justify-center gap-1.5 text-sm font-bold transition-colors"
                style={{
                  height: "40px",
                  background: "var(--color-primary)",
                  border: "none",
                  borderRadius: "999px",
                  color: "#fff",
                  fontFamily: "inherit",
                }}
              >
                <img src={Icon.arrowDownToLine} alt="" className="w-[18px] h-[18px]" />
                导出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
