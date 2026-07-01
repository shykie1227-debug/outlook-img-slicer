/**
 * ProgressBar 组件（V6.0.0 Phase 3.5）
 *
 * 多任务进度条 + 状态消息 + 错误态 + 取消
 *
 * 计算逻辑：
 * - 整体进度 = 所有任务 progress 的平均值
 * - 当前任务 = currentTaskId 指定，否则取 progress 最小且未 done 的
 */
export interface ProgressTask {
  id: string;
  name: string;
  /** 0~1 */
  progress: number;
  done?: boolean;
  error?: string;
}

export interface ProgressBarProps {
  visible: boolean;
  tasks: ProgressTask[];
  currentTaskId?: string | null;
  cancellable?: boolean;
  onCancel?: () => void;
}

export function ProgressBar({
  visible,
  tasks,
  currentTaskId = null,
  cancellable = false,
  onCancel,
}: ProgressBarProps): JSX.Element | null {
  if (!visible) return null;

  const current =
    tasks.find((t) => t.id === currentTaskId) ??
    tasks.find((t) => !t.done && !t.error) ??
    null;

  const overall =
    tasks.length > 0
      ? tasks.reduce((sum, t) => sum + t.progress, 0) / tasks.length
      : 0;

  const hasError = tasks.some((t) => t.error);
  const allDone = tasks.length > 0 && tasks.every((t) => t.done);

  const overallPct = Math.round(overall * 100);
  const currentPct = current ? Math.round(current.progress * 100) : overallPct;
  const label = current?.name ?? (allDone ? "已完成" : "等待中…");

  const stateTestId = hasError
    ? "progress-error"
    : allDone
    ? "progress-done"
    : "progress-active";

  const barColor = hasError
    ? "bg-rose-500"
    : allDone
    ? "bg-emerald-500"
    : "bg-sky-500";

  return (
    <div
      data-testid="progress-bar"
      data-state={hasError ? "error" : allDone ? "done" : "active"}
      role="progressbar"
      aria-valuenow={Math.round((current ? current.progress : overall) * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className="w-full max-w-2xl mx-auto p-4 rounded-lg border border-slate-800 bg-slate-900/80 space-y-2"
    >
      <div className="flex items-center justify-between text-sm">
        <div data-testid={stateTestId} className="flex items-center gap-2">
          {hasError ? (
            <>
              <span aria-hidden="true" className="text-rose-400">⚠</span>
              <span className="text-rose-400">错误</span>
            </>
          ) : allDone ? (
            <>
              <span aria-hidden="true" className="text-emerald-400">✓</span>
              <span className="text-emerald-400">已完成</span>
            </>
          ) : (
            <>
              <span aria-hidden="true" className="text-sky-400 animate-pulse">●</span>
              <span className="text-sky-400">进行中</span>
            </>
          )}
          <span className="text-slate-300">{label}</span>
          {current?.error && (
            <span className="text-rose-300 text-xs">· {current.error}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-slate-400 text-xs">
            {current ? `${currentPct}%` : `${overallPct}%`}
          </span>
          {cancellable && onCancel && !allDone && (
            <button
              data-testid="cancel-btn"
              onClick={onCancel}
              className="px-2 py-0.5 text-xs rounded bg-rose-600/30 text-rose-300 hover:bg-rose-600/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
            >
              取消
            </button>
          )}
        </div>
      </div>

      <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} transition-[width] duration-300`}
          style={{ width: `${current ? currentPct : overallPct}%` }}
        />
      </div>

      {tasks.length > 1 && (
        <div className="space-y-1 pt-1">
          {tasks.map((t) => (
            <div key={t.id} className="flex items-center justify-between text-xs">
              <span className={t.error ? "text-rose-300" : t.done ? "text-emerald-300" : "text-slate-400"}>
                <span aria-hidden="true">
                  {t.error ? "✗" : t.done ? "✓" : "○"}
                </span>{" "}
                {t.name}
              </span>
              <span className="text-slate-500">{Math.round(t.progress * 100)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
