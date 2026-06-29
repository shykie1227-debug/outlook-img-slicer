/**
 * app:* IPC handlers 单元测试
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  registerAppHandlers,
  unregisterAppHandlers,
  type IpcLike,
  type DialogApi,
  type ShellApi,
} from "./dialog-handlers";

function makeIpc(): IpcLike & { handlers: Map<string, (event: unknown, ...args: unknown[]) => unknown | Promise<unknown>> } {
  const handlers = new Map();
  return {
    handlers,
    handle: vi.fn((channel, handler) => {
      handlers.set(channel, handler);
    }),
    removeHandler: vi.fn((channel) => {
      handlers.delete(channel);
    }),
  };
}

function makeDialog(over: Partial<DialogApi> = {}): DialogApi {
  return {
    showOpenDialog: vi.fn(async () => ({ canceled: false, filePaths: ["/Users/test/a.png"] })),
    showSaveDialog: vi.fn(async () => ({ canceled: false, filePath: "/Users/test/out.html" })),
    ...over,
  };
}

function makeShell(): ShellApi {
  return { showItemInFolder: vi.fn() };
}

describe("registerAppHandlers", () => {
  let ipc: ReturnType<typeof makeIpc>;
  let dialog: DialogApi;
  let shell: ShellApi;

  beforeEach(() => {
    ipc = makeIpc();
    dialog = makeDialog();
    shell = makeShell();
  });

  it("registers app:openImage and app:saveHtml", () => {
    const channels = registerAppHandlers(ipc, dialog, shell, () => null);
    expect(channels).toContain("app:openImage");
    expect(channels).toContain("app:saveHtml");
    expect(ipc.handlers.has("app:openImage")).toBe(true);
    expect(ipc.handlers.has("app:saveHtml")).toBe(true);
  });

  describe("app:openImage handler", () => {
    it("returns first selected path", async () => {
      registerAppHandlers(ipc, dialog, shell, () => null);
      const handler = ipc.handlers.get("app:openImage")!;
      const r = await handler(null, {});
      expect(r).toEqual({ path: "/Users/test/a.png" });
      expect(dialog.showOpenDialog).toHaveBeenCalled();
    });

    it("returns null when user cancels", async () => {
      dialog = makeDialog({ showOpenDialog: vi.fn(async () => ({ canceled: true, filePaths: [] })) });
      registerAppHandlers(ipc, dialog, shell, () => null);
      const handler = ipc.handlers.get("app:openImage")!;
      expect(await handler(null, {})).toEqual({ path: null });
    });

    it("uses custom filters and default path", async () => {
      registerAppHandlers(ipc, dialog, shell, () => null);
      const handler = ipc.handlers.get("app:openImage")!;
      await handler(null, {
        defaultPath: "/Users/test/Pictures",
        filters: [{ name: "PNG", extensions: ["png"] }],
      });
      const call = (dialog.showOpenDialog as ReturnType<typeof vi.fn>).mock.calls[0]!;
      const opts = call[1] as { defaultPath?: string; filters?: unknown };
      expect(opts.defaultPath).toBe("/Users/test/Pictures");
      expect(opts.filters).toEqual([{ name: "PNG", extensions: ["png"] }]);
    });
  });

  describe("app:saveHtml handler", () => {
    it("returns the chosen file path", async () => {
      registerAppHandlers(ipc, dialog, shell, () => null);
      const handler = ipc.handlers.get("app:saveHtml")!;
      const r = await handler(null, {});
      expect(r).toEqual({ path: "/Users/test/out.html" });
    });

    it("returns null when user cancels", async () => {
      dialog = makeDialog({ showSaveDialog: vi.fn(async () => ({ canceled: true })) });
      registerAppHandlers(ipc, dialog, shell, () => null);
      const handler = ipc.handlers.get("app:saveHtml")!;
      expect(await handler(null, {})).toEqual({ path: null });
    });

    it("uses custom default path", async () => {
      registerAppHandlers(ipc, dialog, shell, () => null);
      const handler = ipc.handlers.get("app:saveHtml")!;
      await handler(null, { defaultPath: "/Users/x/custom.html" });
      const call = (dialog.showSaveDialog as ReturnType<typeof vi.fn>).mock.calls[0]!;
      const opts = call[1] as { defaultPath?: string };
      expect(opts.defaultPath).toBe("/Users/x/custom.html");
    });
  });

  it("unregisterAppHandlers removes registered channels", () => {
    const channels = registerAppHandlers(ipc, dialog, shell, () => null);
    unregisterAppHandlers(ipc, channels);
    expect(ipc.handlers.size).toBe(0);
  });
});
