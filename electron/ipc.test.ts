/**
 * IPC 路由单元测试（V6.0.0）
 *
 * 测试目标：
 * 1. 注册所有 11 个 IPC 通道
 * 2. 收到 renderer 请求时调用 sidecar.send()
 * 3. 错误透传
 * 4. sidecar:status 直接返回 status()
 * 5. unregister 清理所有 handler
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

import { registerIpc, unregisterIpc, IPC_CHANNELS } from "./ipc.js";
import type { SidecarManager } from "./sidecar-manager.js";

type Handler = (event: unknown, ...args: unknown[]) => unknown | Promise<unknown>;

function createMockIpc() {
  const handlers = new Map<string, Handler>();
  return {
    handle: vi.fn((channel: string, handler: Handler) => {
      handlers.set(channel, handler);
    }),
    removeHandler: vi.fn((channel: string) => {
      handlers.delete(channel);
    }),
    handlers,
    invoke(channel: string, ...args: unknown[]): Promise<unknown> {
      const h = handlers.get(channel);
      if (!h) throw new Error(`No handler for ${channel}`);
      return Promise.resolve(h({}, ...args));
    },
  };
}

function createMockSidecar(): SidecarManager {
  return {
    send: vi.fn(async (method: string, params: unknown) => {
      return { method, params, mock: true };
    }),
    status: vi.fn(() => ({
      pid: 9999,
      platform: "win32" as NodeJS.Platform,
      uptime_seconds: 12.5,
      last_ping: 1700000000000,
      is_alive: true,
    })),
    isReady: vi.fn(() => true),
  } as unknown as SidecarManager;
}

describe("IPC channels", () => {
  it("exposes 11 channels", () => {
    expect(IPC_CHANNELS.length).toBe(11);
    expect(IPC_CHANNELS).toContain("image:info");
    expect(IPC_CHANNELS).toContain("image:slice");
    expect(IPC_CHANNELS).toContain("html:assemble");
    expect(IPC_CHANNELS).toContain("outlook:createDraft");
    expect(IPC_CHANNELS).toContain("sidecar:status");
  });
});

describe("registerIpc()", () => {
  let ipc: ReturnType<typeof createMockIpc>;
  let sidecar: SidecarManager;

  beforeEach(() => {
    ipc = createMockIpc();
    sidecar = createMockSidecar();
  });

  it("registers all 11 channels", () => {
    registerIpc(ipc as never, sidecar);
    expect(ipc.handle).toHaveBeenCalledTimes(11);
    for (const ch of IPC_CHANNELS) {
      expect(ipc.handlers.has(ch)).toBe(true);
    }
  });

  it("forwards image:info to sidecar.send('image.info', params)", async () => {
    registerIpc(ipc as never, sidecar);
    const result = await ipc.invoke("image:info", { path: "/tmp/a.png" });
    expect(sidecar.send).toHaveBeenCalledWith("image.info", { path: "/tmp/a.png" });
    expect(result).toEqual({
      method: "image.info",
      params: { path: "/tmp/a.png" },
      mock: true,
    });
  });

  it("forwards image:slice to sidecar.send('image.slice', params)", async () => {
    registerIpc(ipc as never, sidecar);
    await ipc.invoke("image:slice", { path: "/tmp/a.png", max_h: 2000 });
    expect(sidecar.send).toHaveBeenCalledWith("image.slice", {
      path: "/tmp/a.png",
      max_h: 2000,
    });
  });

  it("forwards html:assemble", async () => {
    registerIpc(ipc as never, sidecar);
    const html = "<p>hello</p>";
    await ipc.invoke("html:assemble", {
      slices: [{ path: "/tmp/s1.png", width: 650, height: 1000 }],
      width: 650,
    });
    expect(sidecar.send).toHaveBeenCalledWith("html.assemble", {
      slices: [{ path: "/tmp/s1.png", width: 650, height: 1000 }],
      width: 650,
    });
  });

  it("forwards outlook:createDraft", async () => {
    registerIpc(ipc as never, sidecar);
    await ipc.invoke("outlook:createDraft", {
      html: "<p>x</p>",
      subject: "hi",
      cid_files: { img1: "/tmp/img1.png" },
    });
    expect(sidecar.send).toHaveBeenCalledWith("outlook.createDraft", {
      html: "<p>x</p>",
      subject: "hi",
      cid_files: { img1: "/tmp/img1.png" },
    });
  });

  it("sidecar:status returns sidecar.status()", async () => {
    registerIpc(ipc as never, sidecar);
    const s = await ipc.invoke("sidecar:status");
    expect(s).toEqual({
      pid: 9999,
      platform: "win32",
      uptime_seconds: 12.5,
      last_ping: 1700000000000,
      is_alive: true,
    });
  });

  it("propagates sidecar errors as rejected promises", async () => {
    (sidecar.send as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("FileNotFoundError")
    );
    registerIpc(ipc as never, sidecar);
    await expect(ipc.invoke("image:info", { path: "/missing.png" })).rejects.toThrow(
      "FileNotFoundError"
    );
  });
});

describe("unregisterIpc()", () => {
  it("removes all handlers", () => {
    const ipc = createMockIpc();
    const sidecar = createMockSidecar();
    registerIpc(ipc as never, sidecar);
    unregisterIpc(ipc as never);
    expect(ipc.removeHandler).toHaveBeenCalledTimes(11);
  });
});
