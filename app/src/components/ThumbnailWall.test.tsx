/**
 * ThumbnailWall 单元测试（V6.0.0 Phase 3.2）
 *
 * 验证：
 * - 渲染缩略图列表
 * - 点击选中缩略图
 * - 显示索引与文件名
 * - 删除按钮触发 onRemove
 * - 空列表显示占位
 * - 键盘左右切换
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { ThumbnailWall, type ThumbnailItem } from "./ThumbnailWall";

const SAMPLE: ThumbnailItem[] = [
  { id: "a", name: "a.png", width: 1000, height: 800 },
  { id: "b", name: "b.png", width: 1000, height: 1500 },
  { id: "c", name: "c.png", width: 1000, height: 2000 },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ThumbnailWall", () => {
  it("renders a thumbnail per item", () => {
    render(<ThumbnailWall items={SAMPLE} selectedId={null} onSelect={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getAllByTestId("thumb")).toHaveLength(3);
  });

  it("shows index badge for each thumb", () => {
    render(<ThumbnailWall items={SAMPLE} selectedId={null} onSelect={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows file name and dimensions", () => {
    render(<ThumbnailWall items={SAMPLE} selectedId={null} onSelect={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText("a.png")).toBeInTheDocument();
    expect(screen.getByText(/1000×800/)).toBeInTheDocument();
  });

  it("marks selected thumb with aria-selected", () => {
    render(<ThumbnailWall items={SAMPLE} selectedId="b" onSelect={vi.fn()} onRemove={vi.fn()} />);
    const thumbs = screen.getAllByTestId("thumb");
    expect(thumbs[0]).toHaveAttribute("aria-selected", "false");
    expect(thumbs[1]).toHaveAttribute("aria-selected", "true");
    expect(thumbs[2]).toHaveAttribute("aria-selected", "false");
  });

  it("calls onSelect when thumb is clicked", () => {
    const onSelect = vi.fn();
    render(<ThumbnailWall items={SAMPLE} selectedId={null} onSelect={onSelect} onRemove={vi.fn()} />);
    fireEvent.click(screen.getAllByTestId("thumb")[1]);
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("calls onRemove when delete button is clicked", () => {
    const onRemove = vi.fn();
    render(<ThumbnailWall items={SAMPLE} selectedId={null} onSelect={vi.fn()} onRemove={onRemove} />);
    const deleteButtons = screen.getAllByTestId("thumb-remove");
    fireEvent.click(deleteButtons[0]);
    expect(onRemove).toHaveBeenCalledWith("a");
  });

  it("shows empty placeholder when no items", () => {
    render(<ThumbnailWall items={[]} selectedId={null} onSelect={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText(/暂无切片/)).toBeInTheDocument();
  });

  it("navigates right with ArrowRight key", () => {
    const onSelect = vi.fn();
    render(<ThumbnailWall items={SAMPLE} selectedId="a" onSelect={onSelect} onRemove={vi.fn()} />);
    const wall = screen.getByTestId("thumbnail-wall");
    fireEvent.keyDown(wall, { key: "ArrowRight" });
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("navigates left with ArrowLeft key", () => {
    const onSelect = vi.fn();
    render(<ThumbnailWall items={SAMPLE} selectedId="b" onSelect={onSelect} onRemove={vi.fn()} />);
    const wall = screen.getByTestId("thumbnail-wall");
    fireEvent.keyDown(wall, { key: "ArrowLeft" });
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("clamps navigation at boundaries", () => {
    const onSelect = vi.fn();
    render(<ThumbnailWall items={SAMPLE} selectedId="a" onSelect={onSelect} onRemove={vi.fn()} />);
    const wall = screen.getByTestId("thumbnail-wall");
    fireEvent.keyDown(wall, { key: "ArrowLeft" });
    expect(onSelect).toHaveBeenCalledWith("a");
  });
});
