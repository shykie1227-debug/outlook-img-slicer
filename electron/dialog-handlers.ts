/**
 * 应用级 IPC 处理器（V6.0.0 Phase 4）
 *
 * 与 ipc.ts（Sidecar 命令透传）解耦，专门处理：
 * - app:openImage  打开文件选择对话框
 * - app:saveHtml    保存拼装好的 HTML 到本地（可选）
 * - app:revealInFolder 在资源管理器中显示文件
 *
 * 依赖注入：
 * - dialog: Electron dialog 模块（测试时用 mock）
 * - shell: Electron shell 模块（测试时用 mock）
 */
import { existsSync } from "node:fs";
import type { BrowserWindow } from "electron";

export interface OpenImageDialogOptions {
  /** 默认展示的目录 */
  defaultPath?: string;
  /** 文件类型过滤器 */
  filters?: Array<{ name: string; extensions: string[] }>;
  /** 窗口引用（macOS 需要） */
  window?: BrowserWindow | null;
}

export interface OpenImageResult {
  /** 绝对路径，null = 用户取消 */
  path: string | null;
}

export interface SaveHtmlDialogOptions {
  defaultPath?: string;
  window?: BrowserWindow | null;
}

export interface SaveHtmlResult {
  path: string | null;
}

export interface DialogApi {
  showOpenDialog: (
    window: unknown,
    options: unknown
  ) => Promise<{ canceled: boolean; filePaths: string[] }>;
  showSaveDialog: (
    window: unknown,
    options: unknown
  ) => Promise<{ canceled: boolean; filePath?: string }>;
}

export interface ShellApi {
  showItemInFolder: (filePath: string) => void;
}

export interface IpcLike {
  handle: (
    channel: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    handler: (event: unknown, ...args: any[]) => unknown | Promise<unknown>
  ) => void;
  removeHandler: (channel: string) => void;
}

const DEFAULT_IMAGE_FILTERS: Array<{ name: string; extensions: string[] }> = [
  { name: "图片", extensions: ["png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff"] },
  { name: "所有文件", extensions: ["*"] },
];

/**
 * 注册 app:* 系列 IPC 处理器。
 * 返回已注册的 channel 列表，便于测试 / 清理。
 */
export function registerAppHandlers(
  ipc: IpcLike,
  dialog: DialogApi,
  _shell: ShellApi,
  getWindow: () => BrowserWindow | null
): string[] {
  const channels: string[] = [];

  ipc.handle(
    "app:openImage",
    async (_event, opts: OpenImageDialogOptions = {}) => {
      const win = opts.window ?? getWindow();
      const r = await dialog.showOpenDialog(win ?? undefined, {
        title: "选择长图",
        defaultPath: opts.defaultPath,
        filters: opts.filters ?? DEFAULT_IMAGE_FILTERS,
        properties: ["openFile"],
      });
      if (r.canceled || r.filePaths.length === 0) {
        return { path: null } satisfies OpenImageResult;
      }
      return { path: r.filePaths[0]! } satisfies OpenImageResult;
    }
  );
  channels.push("app:openImage");

  ipc.handle(
    "app:saveHtml",
    async (_event, opts: SaveHtmlDialogOptions = {}) => {
      const win = opts.window ?? getWindow();
      const r = await dialog.showSaveDialog(win ?? undefined, {
        title: "保存 HTML",
        defaultPath: opts.defaultPath ?? "long-image.html",
        filters: [
          { name: "HTML", extensions: ["html", "htm"] },
          { name: "所有文件", extensions: ["*"] },
        ],
      });
      if (r.canceled || !r.filePath) {
        return { path: null } satisfies SaveHtmlResult;
      }
      return { path: r.filePath } satisfies SaveHtmlResult;
    }
  );
  channels.push("app:saveHtml");

  return channels;
}

/** 清理 app:* 通道 */
export function unregisterAppHandlers(ipc: IpcLike, channels: string[]): void {
  for (const ch of channels) {
    ipc.removeHandler(ch);
  }
}

/** 校验路径是否存在（用于 openImage 返回后立即校验） */
export function pathExists(p: string): boolean {
  return existsSync(p);
}
