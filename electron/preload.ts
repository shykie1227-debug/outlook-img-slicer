/**
 * Preload 脚本（V6.0.0）
 *
 * 通过 contextBridge 暴露 window.api 给渲染进程：
 * - 10 个 Sidecar IPC 调用方法
 * - 2 个应用级 IPC（openImage / saveHtml）
 * - 4 个 Sidecar 事件订阅方法
 * - webUtils.getPathForFile 包装（Electron 30 安全方式）
 *
 * 设计原则：
 * - 零业务逻辑：只做 invoke 转发
 * - 类型安全：API 形状与 ipc.ts 同步
 * - contextIsolation: true（安全默认值）
 */
import { contextBridge, ipcRenderer, webUtils } from "electron";

import type { CommandMap, CommandName } from "./types";

/** 渲染进程可调用的 IPC 方法 */
const invoke = async <K extends CommandName>(
  method: K,
  params: CommandMap[K]["params"]
): Promise<CommandMap[K]["result"]> => {
  const channel = methodToChannel(method);
  return ipcRenderer.invoke(channel, params);
};

function methodToChannel(method: CommandName): string {
  return method.replace(/\./g, ":");
}

const api = {
  // ─── 图片 ───
  imageInfo: (params: CommandMap["image.info"]["params"]) =>
    invoke("image.info", params),
  imageSlice: (params: CommandMap["image.slice"]["params"]) =>
    invoke("image.slice", params),
  imageCompress: (params: CommandMap["image.compress"]["params"]) =>
    invoke("image.compress", params),

  // ─── 文档 ───
  pdfToImages: (params: CommandMap["pdf.toImages"]["params"]) =>
    invoke("pdf.toImages", params),
  pptxToImages: (params: CommandMap["pptx.toImages"]["params"]) =>
    invoke("pptx.toImages", params),
  psdToImage: (params: CommandMap["psd.toImage"]["params"]) =>
    invoke("psd.toImage", params),

  // ─── HTML ───
  htmlAssemble: (params: CommandMap["html.assemble"]["params"]) =>
    invoke("html.assemble", params),
  htmlClipboard: (params: CommandMap["html.clipboard"]["params"]) =>
    invoke("html.clipboard", params),

  // ─── Outlook ───
  outlookCreateDraft: (params: CommandMap["outlook.createDraft"]["params"]) =>
    invoke("outlook.createDraft", params),
  outlookCopyClipboard: (params: CommandMap["outlook.copyClipboard"]["params"]) =>
    invoke("outlook.copyClipboard", params),

  // ─── Sidecar 状态 ───
  sidecarStatus: () => invoke("sidecar.status", {}),

  // ─── 应用级 IPC（Phase 4 新增） ───
  openImage: (
    opts: { defaultPath?: string; filters?: Array<{ name: string; extensions: string[] }> } = {}
  ): Promise<{ path: string | null }> => ipcRenderer.invoke("app:openImage", opts),
  saveHtml: (opts: { defaultPath?: string } = {}): Promise<{ path: string | null }> =>
    ipcRenderer.invoke("app:saveHtml", opts),

  // ─── File → OS 路径（Electron 30 安全方式） ───
  getPathForFile: (file: File): string => webUtils.getPathForFile(file),

  // ─── 事件订阅 ───
  onSidecarReady: (cb: () => void) => {
    const handler = () => cb();
    ipcRenderer.on("sidecar:ready", handler);
    return () => ipcRenderer.removeListener("sidecar:ready", handler);
  },
  onSidecarExit: (cb: (code: number | null) => void) => {
    const handler = (_: unknown, code: number | null) => cb(code);
    ipcRenderer.on("sidecar:exit", handler);
    return () => ipcRenderer.removeListener("sidecar:exit", handler);
  },
  onSidecarRestart: (cb: () => void) => {
    const handler = () => cb();
    ipcRenderer.on("sidecar:restart", handler);
    return () => ipcRenderer.removeListener("sidecar:restart", handler);
  },
  onSidecarError: (cb: (msg: string) => void) => {
    const handler = (_: unknown, msg: string) => cb(msg);
    ipcRenderer.on("sidecar:error", handler);
    return () => ipcRenderer.removeListener("sidecar:error", handler);
  },

  // ─── 元信息 ───
  platform: process.platform,
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  },
};

contextBridge.exposeInMainWorld("api", api);

export type OutlookImgSlicerApi = typeof api;
