/**
 * 渲染进程入口（V6.1.0）
 *
 * V6.1.0：dev 环境注入 window.api mock，便于纯浏览器预览 UI 视觉。
 *         生产环境由 preload.ts 注入真实 api，mock 不生效。
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./index.css";

// dev 预览 mock：非 Electron 环境下 window.api 不存在，注入空实现以渲染首屏
if (import.meta.env.DEV && typeof window !== "undefined" && !window.api) {
  const noop = () => () => {};
  (window as unknown as { api: unknown }).api = {
    sidecarStatus: async () => ({ is_alive: false, pid: 0 }),
    onSidecarReady: noop,
    onSidecarExit: noop,
    onSidecarRestart: noop,
    onSidecarError: noop,
    openImage: async () => ({ path: "" }),
    imageInfo: async () => ({}),
    imageSlice: async () => ({ slices: [] }),
    htmlAssemble: async () => ({ html: "", cid_files: [] }),
    htmlClipboard: async () => ({ cf_html: "" }),
    outlookCopyClipboard: async () => undefined,
    outlookCreateDraft: async () => undefined,
    saveHtml: async () => ({ path: "" }),
    getPathForFile: (f: File) => f.name,
  };
}

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root container not found");
}
createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>
);
