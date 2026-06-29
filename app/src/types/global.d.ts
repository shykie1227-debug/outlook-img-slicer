/**
 * 渲染进程 API 类型声明（V6.0.0）
 *
 * preload.ts 通过 contextBridge.exposeInMainWorld("api", ...) 暴露
 */
import type { OutlookImgSlicerApi } from "../../electron/preload.js";

declare global {
  interface Window {
    api: OutlookImgSlicerApi;
  }
}

export {};
