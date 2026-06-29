/**
 * ProgressBar 单元测试（V6.0.0 Phase 3.5）
 *
 * 验证：
 * - 渲染进度条 + 百分比
 * - 显示当前任务名
 * - 错误状态视觉
 * - 取消按钮调用 onCancel
 * - 100% 状态
 * - 隐藏状态（不显示时）
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { ProgressBar, type ProgressTask } from "./ProgressBar";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProgressBar", () => {
  it("renders nothing when not visible", () => {
    const { container } = render(
      <ProgressBar visible={false} tasks={[]} onCancel={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the current task and percentage", () => {
    const tasks: ProgressTask[] = [
      { id: "t1", name: "解析图片", progress: 0.5 },
      { id: "t2", name: "切片", progress: 0 },
    ];
    const { container } = render(
      <ProgressBar visible tasks={tasks} currentTaskId="t1" onCancel={vi.fn()} />
    );
    expect(container.textContent).toContain("解析图片");
    expect(container.textContent).toContain("50%");
  });

  it("shows error state with message", () => {
    const tasks: ProgressTask[] = [
      { id: "t1", name: "解析图片", progress: 0.5, error: "文件不存在" },
    ];
    const { container } = render(
      <ProgressBar visible tasks={tasks} currentTaskId="t1" onCancel={vi.fn()} />
    );
    expect(container.textContent).toContain("文件不存在");
    expect(screen.getByTestId("progress-error")).toBeInTheDocument();
  });

  it("calls onCancel when cancel button is clicked", () => {
    const onCancel = vi.fn();
    render(
      <ProgressBar
        visible
        tasks={[{ id: "t1", name: "切片", progress: 0.3 }]}
        currentTaskId="t1"
        onCancel={onCancel}
        cancellable
      />
    );
    fireEvent.click(screen.getByTestId("cancel-btn"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("hides cancel button when not cancellable", () => {
    render(
      <ProgressBar
        visible
        tasks={[{ id: "t1", name: "切片", progress: 0.3 }]}
        currentTaskId="t1"
        onCancel={vi.fn()}
      />
    );
    expect(screen.queryByTestId("cancel-btn")).toBeNull();
  });

  it("shows 100% when all tasks complete", () => {
    const tasks: ProgressTask[] = [
      { id: "t1", name: "切片", progress: 1, done: true },
    ];
    const { container } = render(
      <ProgressBar visible tasks={tasks} currentTaskId="t1" onCancel={vi.fn()} />
    );
    expect(container.textContent).toContain("100%");
    expect(screen.getByTestId("progress-done")).toBeInTheDocument();
  });

  it("shows overall progress when no current task", () => {
    const tasks: ProgressTask[] = [
      { id: "t1", name: "切片", progress: 1, done: true },
      { id: "t2", name: "拼装", progress: 0.5, done: true },
    ];
    const { container } = render(
      <ProgressBar visible tasks={tasks} onCancel={vi.fn()} />
    );
    // 全部 done 时没有 current，currentPct fallback 到 overall = (1 + 0.5) / 2 = 75%
    expect(container.textContent).toContain("75%");
  });
});
