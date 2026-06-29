/**
 * IPC 路由（V6.0.0）
 *
 * 把 11 个 Sidecar 命令映射为 ipcMain.handle 通道：
 *   "image.info"  → "image:info"
 *   "image.slice" → "image:slice"
 *   ...
 *
 * 设计原则：
 * - 极简：纯映射，不做参数校验（Sidecar 端负责）
 * - 错误透传：sidecar.send 抛错时直接 reject
 * - 依赖注入：测试时传入 mock ipc
 */
import type { SidecarManager } from "./sidecar-manager.js";

/** IPC 通道 → Sidecar 命令的映射 */
const CHANNEL_TO_METHOD: Record<string, string> = {
  "image:info": "image.info",
  "image:slice": "image.slice",
  "image:smartSlice": "image.smartSlice",
  "pdf:toImages": "pdf.toImages",
  "pptx:toImages": "pptx.toImages",
  "psd:toImage": "psd.toImage",
  "html:assemble": "html.assemble",
  "html:clipboard": "html.clipboard",
  "outlook:createDraft": "outlook.createDraft",
  "outlook:copyClipboard": "outlook.copyClipboard",
  "sidecar:status": "__status__", // 特殊：直接读 sidecar.status()
};

export const IPC_CHANNELS = Object.keys(CHANNEL_TO_METHOD);

/** 简化的 IPC 接口，便于测试 */
export interface IpcLike {
  handle: (channel: string, handler: (event: unknown, ...args: unknown[]) => unknown | Promise<unknown>) => void;
  removeHandler: (channel: string) => void;
}

/**
 * 注册所有 IPC 通道。
 * 必须在 app.whenReady() 之后调用。
 */
export function registerIpc(ipc: IpcLike, sidecar: SidecarManager): void {
  for (const channel of IPC_CHANNELS) {
    const method = CHANNEL_TO_METHOD[channel]!;
    if (method === "__status__") {
      ipc.handle(channel, async () => sidecar.status());
    } else {
      ipc.handle(channel, async (_event, params) => {
        // 简化：直接透传 params
        // 真实场景下应做 zod 校验，但 Sidecar 端已经有 TypeError/FileNotFoundError 防御
        return sidecar.send(method as never, params as never);
      });
    }
  }
}

/**
 * 清理所有 IPC 通道（测试 / 优雅退出用）。
 */
export function unregisterIpc(ipc: IpcLike): void {
  for (const channel of IPC_CHANNELS) {
    ipc.removeHandler(channel);
  }
}
