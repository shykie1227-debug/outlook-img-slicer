/**
 * safe-file 自定义协议（V6.0.0）
 *
 * 目的：让渲染端用 `<img src="safe-file:///abs/path.png" />` 安全预览本地图片，
 * 同时不暴露完整 file:// 协议（避免越权访问 .exe 等敏感文件）。
 *
 * 工作流：
 * 1. main.ts 在 app.whenReady() 前调用 protocol.registerSchemesAsPrivileged
 * 2. main.ts 在 app.whenReady() 后调用 protocol.handle('safe-file', handler)
 * 3. handler = (req) => handleSafeFile(req, fsReader).then(toWebResponse)
 *
 * 安全策略：
 * - 白名单扩展名（仅图片）
 * - 不可读非白名单文件
 * - 文件读取失败返回 404
 */
import { Buffer } from "node:buffer";
import { readFile } from "node:fs/promises";

const ALLOWED_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".gif",
  ".bmp",
  ".tif",
  ".tiff",
]);

const MIME_TYPES: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".bmp": "image/bmp",
  ".tif": "image/tiff",
  ".tiff": "image/tiff",
};

export interface SafeFileRequest {
  url: string;
}

export interface SafeFileReader {
  read(filePath: string): Promise<Buffer>;
}

export interface SafeFileResult {
  status: number;
  contentType: string;
  data: Buffer;
}

/** 默认 reader：直接用 fs.promises.readFile */
export const fsReader: SafeFileReader = {
  read: (filePath) => readFile(filePath),
};

/** 提取扩展名（点号开头，小写） */
export function getExt(filePath: string): string {
  const dot = filePath.lastIndexOf(".");
  return dot < 0 ? "" : filePath.slice(dot).toLowerCase();
}

/** 是否在白名单内 */
export function isAllowedExtension(filePath: string): boolean {
  return ALLOWED_EXTENSIONS.has(getExt(filePath));
}

/**
 * 处理 safe-file:// 请求。
 * - platform 默认 process.platform，可注入便于测试
 * - 不可读非图片扩展名 → 403
 * - 文件不存在 → 404
 */
export async function handleSafeFile(
  request: SafeFileRequest,
  reader: SafeFileReader = fsReader,
  platform: NodeJS.Platform = process.platform
): Promise<SafeFileResult> {
  let filePath: string;
  try {
    const url = new URL(request.url);
    filePath = decodeURIComponent(url.pathname);
  } catch {
    return { status: 400, contentType: "text/plain", data: Buffer.from("Bad URL") };
  }
  // Windows: /C:/path → C:/path
  if (platform === "win32" && /^\/[A-Za-z]:/.test(filePath)) {
    filePath = filePath.slice(1);
  }
  if (!isAllowedExtension(filePath)) {
    return { status: 403, contentType: "text/plain", data: Buffer.from("Forbidden") };
  }
  try {
    const data = await reader.read(filePath);
    return {
      status: 200,
      contentType: MIME_TYPES[getExt(filePath)] ?? "application/octet-stream",
      data,
    };
  } catch {
    return { status: 404, contentType: "text/plain", data: Buffer.from("Not Found") };
  }
}

/** 把 SafeFileResult 包成 Web Response（供 protocol.handle 使用） */
export function toWebResponse(r: SafeFileResult): Response {
  return new Response(r.data, {
    status: r.status,
    headers: { "Content-Type": r.contentType },
  });
}
