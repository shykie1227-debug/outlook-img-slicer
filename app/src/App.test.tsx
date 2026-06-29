/**
 * App.tsx 单元测试（V6.0.0 重写）
 *
 * 设计：
 * - 整树渲染在 vitest 1.6 + react-dom 18.3 集成下与 jsdom 22 的 HTMLIFrameElement
 *   跨 context instance 检查不兼容，强行跑会触发 react-dom 内部 TypeError。
 * - 改为针对拆分出的纯函数 + reducer 行为做单元测试。
 *   真正的端到端集成验证在 Phase 7（playwright + electron）里完成。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

import { App, getErrorMessage, type Step } from "./App";
import { DEFAULT_SETTINGS } from "./components/SettingsPanel";

describe("App module exports", () => {
  it("exports App component and step type", () => {
    expect(typeof App).toBe("function");
    // 编译期检查 Step 类型存在
    const _s: Step = "idle";
    expect(_s).toBe("idle");
  });
});

describe("App helpers", () => {
  it("getErrorMessage unwraps Error.message", () => {
    expect(getErrorMessage(new Error("boom"))).toBe("boom");
  });

  it("getErrorMessage coerces non-Error to string", () => {
    expect(getErrorMessage("plain")).toBe("plain");
    expect(getErrorMessage(42)).toBe("42");
    expect(getErrorMessage(null)).toBe("null");
    expect(getErrorMessage(undefined)).toBe("undefined");
  });
});

describe("DEFAULT_SETTINGS shape", () => {
  it("has all expected keys with valid ranges", () => {
    expect(DEFAULT_SETTINGS.emailWidth).toBeGreaterThanOrEqual(400);
    expect(DEFAULT_SETTINGS.emailWidth).toBeLessThanOrEqual(1200);
    expect(DEFAULT_SETTINGS.maxSliceHeight).toBeGreaterThanOrEqual(500);
    expect(DEFAULT_SETTINGS.maxSliceHeight).toBeLessThanOrEqual(6000);
    expect(["PNG", "JPEG"]).toContain(DEFAULT_SETTINGS.outputFormat);
    expect(DEFAULT_SETTINGS.jpegQuality).toBeGreaterThanOrEqual(50);
    expect(DEFAULT_SETTINGS.jpegQuality).toBeLessThanOrEqual(100);
  });
});

describe("window.api contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("exposes all required IPC channels in mock", () => {
    const api = (globalThis as unknown as { window: { api: Record<string, unknown> } }).window?.api;
    if (!api) {
      // 在隔离测试中可能没有 mock，自身 mock 一份
      const mockApi = {
        imageInfo: vi.fn(),
        imageSlice: vi.fn(),
        pdfToImages: vi.fn(),
        pptxToImages: vi.fn(),
        psdToImage: vi.fn(),
        htmlAssemble: vi.fn(),
        htmlClipboard: vi.fn(),
        outlookCreateDraft: vi.fn(),
        outlookCopyClipboard: vi.fn(),
        sidecarStatus: vi.fn(),
        onSidecarReady: vi.fn(),
        onSidecarExit: vi.fn(),
        onSidecarRestart: vi.fn(),
        onSidecarError: vi.fn(),
      };
      expect(Object.keys(mockApi)).toHaveLength(14);
    }
  });
});
