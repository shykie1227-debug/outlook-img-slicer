/**
 * App store 单元测试
 */
import { describe, it, expect, beforeEach } from "vitest";

import { useAppStore } from "./store";

describe("useAppStore", () => {
  beforeEach(() => {
    // 重置到 INITIAL
    useAppStore.getState().reset();
  });

  it("starts in idle step with empty data", () => {
    const s = useAppStore.getState();
    expect(s.step).toBe("idle");
    expect(s.sourcePath).toBeNull();
    expect(s.sourceInfo).toBeNull();
    expect(s.slices).toEqual([]);
    expect(s.cuts).toEqual([]);
    expect(s.assembledHtml).toBeNull();
    expect(s.error).toBeNull();
    expect(s.tasks).toEqual([]);
  });

  it("setStep changes step", () => {
    useAppStore.getState().setStep("slicing");
    expect(useAppStore.getState().step).toBe("slicing");
  });

  it("setSourcePath + setSourceInfo + setSlices + setCuts flow", () => {
    useAppStore.getState().setSourcePath("/Users/x/a.png");
    useAppStore.getState().setSourceInfo({
      width: 1000, height: 5000, format: "PNG", mode: "RGB", size_bytes: 1024,
    });
    useAppStore.getState().setSlices([
      { path: "/tmp/s1.png", width: 1000, height: 1200, index: 0 },
    ]);
    useAppStore.getState().setCuts([{ id: "c1", y: 1200 }]);
    const s = useAppStore.getState();
    expect(s.sourcePath).toBe("/Users/x/a.png");
    expect(s.sourceInfo?.width).toBe(1000);
    expect(s.slices).toHaveLength(1);
    expect(s.cuts).toEqual([{ id: "c1", y: 1200 }]);
  });

  it("patchTask updates a single task by id", () => {
    useAppStore.getState().setTasks([
      { id: "info", name: "读取图片信息", progress: 0 },
      { id: "slice", name: "切片", progress: 0 },
    ]);
    useAppStore.getState().patchTask("info", { progress: 1, done: true });
    const s = useAppStore.getState();
    expect(s.tasks[0]).toMatchObject({ id: "info", progress: 1, done: true });
    expect(s.tasks[1]).toEqual({ id: "slice", name: "切片", progress: 0 });
  });

  it("reset clears transient state but keeps settings", () => {
    useAppStore.getState().setSettings({ ...useAppStore.getState().settings, emailWidth: 800 });
    useAppStore.getState().setSourcePath("/x.png");
    useAppStore.getState().setError("boom");
    useAppStore.getState().reset();
    const s = useAppStore.getState();
    expect(s.sourcePath).toBeNull();
    expect(s.error).toBeNull();
    expect(s.step).toBe("idle");
    expect(s.settings.emailWidth).toBe(800);
  });
});
