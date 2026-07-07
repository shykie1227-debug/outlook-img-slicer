/**
 * Sidecar IPC 契约类型（V6.0.0）
 *
 * 与 sidecar/commands.md 保持一致。
 * Python 端响应通过 JSON-RPC 风格传输，TypeScript 端用这些类型校验。
 */

/** Python 进程启动握手 */
export interface SidecarReady {
  ready: true;
}

/** Python 进程心跳 */
export interface SidecarPing {
  ping: number;
}

/** Sidecar 通用响应 */
export type SidecarResponse<T = unknown> =
  | { id: string; ok: true; result: T }
  | { id: string; ok: false; error: string };

/** image.info 命令 */
export interface ImageInfoParams {
  path: string;
}
export interface ImageInfoResult {
  width: number;
  height: number;
  format: string;
  mode: string;
  size_bytes: number;
}

/** image.safetyCheck 命令 */
export interface SafetyCheckParams {
  path: string;
  max_edge?: number;
}
export interface SafetyCheckResult {
  is_safe: boolean;
  width: number;
  height: number;
  reason?: string;
}

/** image.slice 命令 */
export interface SliceParams {
  path: string;
  max_h: number;
  max_w?: number;
  mode?: "fixed" | "smart";
}
export interface SliceSlice {
  path: string;
  width: number;
  height: number;
  index: number;
}
export interface SliceResult {
  slices: SliceSlice[];
}

/** pdf.toImages / pptx.toImages 命令 */
export interface ToImagesResult {
  pages: Array<{
    path: string;
    width: number;
    height: number;
    index: number;
  }>;
}

/** psd.toImage 命令 */
export interface PsdToImageResult {
  image_path: string;
  width: number;
  height: number;
}

/** html.assemble 命令 */
export interface AssembleSlice {
  path: string;
  width: number;
  height: number;
  href?: string;
  alt_text?: string;
  sort_key?: number;
  original_width?: number;
}
export interface AssembleParams {
  slices: AssembleSlice[];
  display_w: number;
  /** "base64" = 剪贴板/网页邮箱（自包含）；"cid" = Outlook 草稿（CID 附件） */
  mode?: "base64" | "cid";
}
export interface AssembleResult {
  html: string;
  cid_files: Record<string, string>;
}

/** html.clipboard 命令 */
export interface ClipboardParams {
  html: string;
}
export interface ClipboardResult {
  cf_html: string;
  cf_html_size: number;
}

/** outlook.createDraft 命令（仅 Windows） */
export interface CreateDraftParams {
  html: string;
  subject: string;
  cid_files: Record<string, string>;
}
export interface CreateDraftResult {
  mail_id: string;
  subject: string;
  opened: boolean;
}

/** outlook.copyClipboard 命令（仅 Windows） */
export interface CopyClipboardParams {
  cf_html: string;
}
export interface CopyClipboardResult {
  ok: true;
}

/** sidecar.status 命令 */
export interface SidecarStatusResult {
  pid: number;
  platform: NodeJS.Platform;
  uptime_seconds: number;
  last_ping: number | null;
  is_alive: boolean;
}

/** 所有命令的入参映射 */
export interface CommandMap {
  "image.info": { params: ImageInfoParams; result: ImageInfoResult };
  "image.safetyCheck": { params: SafetyCheckParams; result: SafetyCheckResult };
  "image.slice": { params: SliceParams; result: SliceResult };
  "image.smartSlice": { params: SliceParams; result: SliceResult };
  "pdf.toImages": { params: { path: string; dpi?: number }; result: ToImagesResult };
  "pptx.toImages": { params: { path: string }; result: ToImagesResult };
  "psd.toImage": { params: { path: string }; result: PsdToImageResult };
  "html.assemble": { params: AssembleParams; result: AssembleResult };
  "html.clipboard": { params: ClipboardParams; result: ClipboardResult };
  "outlook.createDraft": { params: CreateDraftParams; result: CreateDraftResult };
  "outlook.copyClipboard": { params: CopyClipboardParams; result: CopyClipboardResult };
  "sidecar.status": { params: Record<string, never>; result: SidecarStatusResult };
}

export type CommandName = keyof CommandMap;
