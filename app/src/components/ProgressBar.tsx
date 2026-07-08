/**
 * ProgressBar 组件（V6.1.0 — 豆包风格）
 *
 * 多任务进度条 + 状态消息 + 错误态 + 取消
 *
 * 计算逻辑：
 * - 整体进度 = 所有任务 progress 的平均值
 * - 当前任务 = currentTaskId 指定，否则取 progress 最小且未 done 的
 *
 * 视觉：浅色卡片 + 豆包状态色（成功 #10b981 / 错误 #ef4444 / 进行中 #0065fd）
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

  // 豆包状态色
  const barColor = hasError
    ? "var(--color-error)"
    : allDone
    ? "var(--color-success)"
    : "var(--color-primary)";

  const stateColor = hasError
    ? "var(--color-error)"
    : allDone
    ? "var(--color-success)"
    : "var(--color-primary)";

  return (
    <div
      data-testid="progress-bar"
      data-state={hasError ? "error" : allDone ? "done" : "active"}
      role="progressbar"
      aria-valuenow={Math.round((current ? current.progress : overall) * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className="w-full max-w-2xl mx-auto p-4 space-y-2"
      style={{
        background: "#fff",
        border: "1px solid var(--color-border)",
        borderRadius: "12px",
      }}
    >
      <div className="flex items-center justify-between text-sm">
        <div data-testid={stateTestId} className="flex items-center gap-2">
          {hasError ? (
            <span style={{ color: stateColor }}>⚠</span>
          ) : allDone ? (
            <span style={{ color: stateColor }}>✓</span>
          ) : (
            <span style={{ color: stateColor }} className="animate-pulse">●</span>
          )}
          <span style={{ color: stateColor }}>
            {hasError ? "错误" : allDone ? "已完成" : "进行中"}
          </span>
          <span style={{ color: "var(--color-text-secondary)" }}>{label}</span>
          {current?.error && (
            <span style={{ color: "var(--color-error)" }} className="text-xs">
              · {current.error}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span style={{ color: "var(--color-text-weak)" }} className="text-xs">
            {current ? `${currentPct}%` : `${overallPct}%`}
          </span>
          {cancellable && onCancel && !allDone && (
            <button
              data-testid="cancel-btn"
              onClick={onCancel}
              className="px-2 py-0.5 text-xs rounded"
              style={{
                background: "#fef2f2",
                color: "var(--color-error)",
              }}
            >
              取消
            </button>
          )}
        </div>
      </div>

      <div
        className="w-full h-2 rounded-full overflow-hidden"
        style={{ background: "var(--color-muted)" }}
      >
        <div
          className="h-full transition-[width] duration-300"
          style={{
            width: `${current ? currentPct : overallPct}%`,
            background: barColor,
          }}
        />
      </div>

      {tasks.length > 1 && (
        <div className="space-y-1 pt-1">
          {tasks.map((t) => (
            <div key={t.id} className="flex items-center justify-between text-xs">
              <span
                style={{
                  color: t.error
                    ? "var(--color-error)"
                    : t.done
                    ? "var(--color-success)"
                    : "var(--color-text-weak)",
                }}
              >
                <span aria-hidden="true">
                  {t.error ? "✗" : t.done ? "✓" : "○"}
                </span>{" "}
                {t.name}
              </span>
              <span style={{ color: "var(--color-text-weak)" }}>
                {Math.round(t.progress * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
