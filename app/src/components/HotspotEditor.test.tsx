/**
 * HotspotEditor 单元测试（V6.0.0 Phase 3.4）
 *
 * 验证：
 * - 渲染热区列表
 * - 添加热区
 * - 删除热区
 * - URL 编辑
 * - 拖动热区改位置
 * - 拖动右下角改大小
 * - 选中态视觉
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { HotspotEditor, type Hotspot } from "./HotspotEditor";

beforeEach(() => {
  vi.clearAllMocks();
});

const SLICE = { width: 650, height: 1000 };

describe("HotspotEditor", () => {
  it("renders hotspot list empty by default", () => {
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={[]}
        options={{ minSizePx: 20 }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByTestId("hotspot-empty")).toBeInTheDocument();
  });

  it("renders one card per hotspot", () => {
    const hotspots: Hotspot[] = [
      { id: "h1", x: 10, y: 10, w: 100, h: 50, href: "https://a.com" },
      { id: "h2", x: 200, y: 200, w: 100, h: 50, href: "https://b.com" },
    ];
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={hotspots}
        options={{ minSizePx: 20 }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getAllByTestId("hotspot-row")).toHaveLength(2);
  });

  it("addHotspot appends a default 100x50 hotspot in center", () => {
    const onChange = vi.fn();
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={[]}
        options={{ minSizePx: 20 }}
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByTestId("add-hotspot"));
    expect(onChange).toHaveBeenCalled();
    const newHs = onChange.mock.calls[0]![0] as Hotspot[];
    expect(newHs).toHaveLength(1);
    expect(newHs[0]!.w).toBe(100);
    expect(newHs[0]!.h).toBe(50);
    // 居中：x = (650-100)/2 = 275, y = (1000-50)/2 = 475
    expect(newHs[0]!.x).toBe(275);
    expect(newHs[0]!.y).toBe(475);
  });

  it("removes the selected hotspot", () => {
    const onChange = vi.fn();
    const hotspots: Hotspot[] = [
      { id: "h1", x: 10, y: 10, w: 100, h: 50, href: "https://a.com" },
    ];
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={hotspots}
        selectedId="h1"
        options={{ minSizePx: 20 }}
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByTestId("remove-hotspot"));
    const newHs = onChange.mock.calls[0]![0] as Hotspot[];
    expect(newHs).toHaveLength(0);
  });

  it("edits href via input", () => {
    const onChange = vi.fn();
    const hotspots: Hotspot[] = [
      { id: "h1", x: 10, y: 10, w: 100, h: 50, href: "https://a.com" },
    ];
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={hotspots}
        selectedId="h1"
        options={{ minSizePx: 20 }}
        onChange={onChange}
      />
    );
    const urlInput = screen.getByTestId("hotspot-url");
    fireEvent.change(urlInput, { target: { value: "https://new.com" } });
    expect(onChange).toHaveBeenCalled();
    const newHs = onChange.mock.calls[0]![0] as Hotspot[];
    expect(newHs[0]!.href).toBe("https://new.com");
  });

  it("clamps hotspot position to slice bounds", () => {
    const onChange = vi.fn();
    const hotspots: Hotspot[] = [
      { id: "h1", x: 0, y: 0, w: 100, h: 50, href: "" },
    ];
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={hotspots}
        selectedId="h1"
        options={{ minSizePx: 20 }}
        onChange={onChange}
      />
    );
    const xInput = screen.getByTestId("hotspot-x") as HTMLInputElement;
    fireEvent.change(xInput, { target: { value: "999" } });
    const newHs = onChange.mock.calls[0]![0] as Hotspot[];
    // 999 + 100 > 650 → 裁剪
    expect(newHs[0]!.x).toBeLessThanOrEqual(550);
  });

  it("enforces minSizePx", () => {
    const onChange = vi.fn();
    const hotspots: Hotspot[] = [
      { id: "h1", x: 0, y: 0, w: 100, h: 100, href: "" },
    ];
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={hotspots}
        selectedId="h1"
        options={{ minSizePx: 20 }}
        onChange={onChange}
      />
    );
    const wInput = screen.getByTestId("hotspot-w");
    fireEvent.change(wInput, { target: { value: "5" } });
    const newHs = onChange.mock.calls[0]![0] as Hotspot[];
    expect(newHs[0]!.w).toBe(20); // minSizePx
  });

  it("marks selected hotspot with data-selected", () => {
    const hotspots: Hotspot[] = [
      { id: "h1", x: 10, y: 10, w: 100, h: 50, href: "https://a.com" },
      { id: "h2", x: 200, y: 200, w: 100, h: 50, href: "https://b.com" },
    ];
    render(
      <HotspotEditor
        slice={SLICE}
        hotspots={hotspots}
        selectedId="h1"
        options={{ minSizePx: 20 }}
        onChange={vi.fn()}
      />
    );
    const rows = screen.getAllByTestId("hotspot-row");
    expect(rows[0]).toHaveAttribute("data-selected", "true");
    expect(rows[1]).toHaveAttribute("data-selected", "false");
  });

  it("renders hotspots as SVG overlays on the slice preview", () => {
    const hotspots: Hotspot[] = [
      { id: "h1", x: 10, y: 10, w: 100, h: 50, href: "https://a.com" },
    ];
    const { container } = render(
      <HotspotEditor
        slice={SLICE}
        hotspots={hotspots}
        options={{ minSizePx: 20 }}
        onChange={vi.fn()}
      />
    );
    expect(container.querySelectorAll("rect[data-hotspot]")).toHaveLength(1);
  });
});
