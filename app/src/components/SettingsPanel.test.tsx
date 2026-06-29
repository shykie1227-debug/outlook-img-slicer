/**
 * SettingsPanel 单元测试（V6.0.0 Phase 3.6）
 *
 * 验证：
 * - 渲染所有设置项
 * - 修改数值触发 onChange
 * - 校验数值范围
 * - 重置默认值
 * - localStorage 持久化
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { SettingsPanel, DEFAULT_SETTINGS, type Settings } from "./SettingsPanel";

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("SettingsPanel", () => {
  it("renders all setting sections", () => {
    render(<SettingsPanel value={DEFAULT_SETTINGS} onChange={vi.fn()} />);
    expect(screen.getByTestId("setting-emailWidth")).toBeInTheDocument();
    expect(screen.getByTestId("setting-maxSliceHeight")).toBeInTheDocument();
    expect(screen.getByTestId("setting-outputFormat")).toBeInTheDocument();
    expect(screen.getByTestId("setting-jpegQuality")).toBeInTheDocument();
    expect(screen.getByTestId("setting-theme")).toBeInTheDocument();
  });

  it("updates emailWidth via input change", () => {
    const onChange = vi.fn();
    render(<SettingsPanel value={DEFAULT_SETTINGS} onChange={onChange} />);
    const input = screen.getByTestId("setting-emailWidth");
    fireEvent.change(input, { target: { value: "700" } });
    expect(onChange).toHaveBeenCalled();
    const newSettings = onChange.mock.calls[0]![0] as Settings;
    expect(newSettings.emailWidth).toBe(700);
  });

  it("clamps emailWidth to [400, 1200]", () => {
    const onChange = vi.fn();
    render(<SettingsPanel value={DEFAULT_SETTINGS} onChange={onChange} />);
    const input = screen.getByTestId("setting-emailWidth");
    fireEvent.change(input, { target: { value: "9999" } });
    const newSettings = onChange.mock.calls[0]![0] as Settings;
    expect(newSettings.emailWidth).toBe(1200);
  });

  it("clamps maxSliceHeight to [500, 6000]", () => {
    const onChange = vi.fn();
    render(<SettingsPanel value={DEFAULT_SETTINGS} onChange={onChange} />);
    const input = screen.getByTestId("setting-maxSliceHeight");
    fireEvent.change(input, { target: { value: "100" } });
    const newSettings = onChange.mock.calls[0]![0] as Settings;
    expect(newSettings.maxSliceHeight).toBe(500);
  });

  it("changes outputFormat", () => {
    const onChange = vi.fn();
    render(<SettingsPanel value={DEFAULT_SETTINGS} onChange={onChange} />);
    const select = screen.getByTestId("setting-outputFormat");
    fireEvent.change(select, { target: { value: "JPEG" } });
    const newSettings = onChange.mock.calls[0]![0] as Settings;
    expect(newSettings.outputFormat).toBe("JPEG");
  });

  it("changes jpegQuality to valid value", () => {
    const onChange = vi.fn();
    render(<SettingsPanel value={DEFAULT_SETTINGS} onChange={onChange} />);
    const input = screen.getByTestId("setting-jpegQuality");
    fireEvent.change(input, { target: { value: "80" } });
    const newSettings = onChange.mock.calls[0]![0] as Settings;
    expect(newSettings.jpegQuality).toBe(80);
  });

  it("clamps jpegQuality to [50, 100]", () => {
    const onChange = vi.fn();
    render(<SettingsPanel value={DEFAULT_SETTINGS} onChange={onChange} />);
    const input = screen.getByTestId("setting-jpegQuality");
    fireEvent.change(input, { target: { value: "10" } });
    const newSettings = onChange.mock.calls[0]![0] as Settings;
    expect(newSettings.jpegQuality).toBe(50);
  });

  it("resets to defaults", () => {
    const onChange = vi.fn();
    render(
      <SettingsPanel
        value={{ ...DEFAULT_SETTINGS, emailWidth: 999 }}
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByTestId("reset-settings"));
    expect(onChange).toHaveBeenCalledWith(DEFAULT_SETTINGS);
  });

  it("persists to localStorage when persist prop is true", () => {
    const onChange = vi.fn();
    render(
      <SettingsPanel value={DEFAULT_SETTINGS} onChange={onChange} persist />
    );
    const input = screen.getByTestId("setting-emailWidth");
    fireEvent.change(input, { target: { value: "720" } });
    const stored = JSON.parse(localStorage.getItem("outlook-img-slicer-settings") ?? "{}");
    expect(stored.emailWidth).toBe(720);
  });

  it("renders provided value (loading is parent's responsibility)", () => {
    const custom: Settings = { ...DEFAULT_SETTINGS, emailWidth: 888 };
    render(<SettingsPanel value={custom} onChange={vi.fn()} />);
    const input = screen.getByTestId("setting-emailWidth") as HTMLInputElement;
    expect(input.value).toBe("888");
  });
});
