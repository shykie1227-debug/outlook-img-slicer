/**
 * SidecarManager（V6.0.0）
 *
 * 管理 Python Sidecar 子进程的生命周期：
 * - spawn Python 子进程
 * - 等待 {"ready": true} 握手
 * - 跟踪 {"ping": ts} 心跳
 * - JSON-RPC over stdio 通信
 * - 崩溃后自动重启（指数退避）
 * - 优雅关闭
 *
 * 设计原则：
 * - 依赖注入 spawner，便于测试
 * - 每个 send() 返回 Promise，按 id 匹配响应
 * - 简化：心跳超时检测放在主线程（Node 单线程）
 */
import { EventEmitter } from "node:events";
import { spawn as defaultSpawn, type ChildProcess } from "node:child_process";
import { randomUUID } from "node:crypto";
import type { Readable } from "node:stream";

import type {
  CommandMap,
  CommandName,
  SidecarResponse,
  SidecarStatusResult,
} from "./types.js";

export type SidecarSpawner = (
  command: string,
  args: string[],
  options: { stdio: ["pipe", "pipe", "pipe"] }
) => ChildProcess;

export interface SidecarOptions {
  command: string;
  args: string[];
  /** 心跳超时（ms），超过此时长无 ping 视为死亡 */
  heartbeatTimeoutMs?: number;
  /** 心跳检查间隔（ms） */
  heartbeatCheckMs?: number;
  /** 最大重启尝试次数 */
  maxRestartAttempts?: number;
  /** 重启退避基数（ms） */
  restartBackoffMs?: number;
  /** stop() 等待优雅退出超时（ms） */
  shutdownTimeoutMs?: number;
  /** send() 请求超时（ms），超过此时长自动 reject */
  requestTimeoutMs?: number;
  /** cwd 覆盖（默认 sidecar 目录） */
  cwd?: string;
  /** 注入：默认 spawn */
  spawn?: SidecarSpawner;
}

interface PendingRequest {
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
  method: string;
}

/**
 * Sidecar 进程管理
 */
export class SidecarManager extends EventEmitter {
  private proc: ChildProcess | null = null;
  private ready = false;
  private startedAt = 0;
  private lastPing: number | null = null;
  private pending = new Map<string, PendingRequest>();
  private restartAttempts = 0;
  private shuttingDown = false;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private stdoutBuf = "";

  private readonly opts: Required<Omit<SidecarOptions, "spawn" | "cwd">> & {
    cwd: string | undefined;
    spawn: SidecarSpawner;
  };

  constructor(spawner: SidecarSpawner, options: SidecarOptions) {
    super();
    this.opts = {
      command: options.command,
      args: options.args,
      heartbeatTimeoutMs: options.heartbeatTimeoutMs ?? 10_000,
      heartbeatCheckMs: options.heartbeatCheckMs ?? 1_000,
      maxRestartAttempts: options.maxRestartAttempts ?? 5,
      restartBackoffMs: options.restartBackoffMs ?? 500,
      shutdownTimeoutMs: options.shutdownTimeoutMs ?? 3_000,
      requestTimeoutMs: options.requestTimeoutMs ?? 60_000,
      cwd: options.cwd,
      spawn: spawner,
    };
  }

  // ─────────────────────────────────────
  // 公开 API
  // ─────────────────────────────────────

  isReady(): boolean {
    return this.ready;
  }

  status(): SidecarStatusResult {
    return {
      pid: this.proc?.pid ?? 0,
      platform: process.platform,
      uptime_seconds: this.startedAt > 0 ? (Date.now() - this.startedAt) / 1000 : 0,
      last_ping: this.lastPing,
      is_alive: this.ready,
    };
  }

  async start(): Promise<void> {
    if (this.proc) {
      throw new Error("SidecarManager: already started");
    }
    this.shuttingDown = false;
    await this._spawnAndWaitReady();
  }

  async stop(): Promise<void> {
    this.shuttingDown = true;
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (!this.proc) return;

    const proc = this.proc;
    const exitPromise = new Promise<void>((resolve) => {
      if (!proc.pid) {
        resolve();
        return;
      }
      proc.once("exit", () => resolve());
    });

    try {
      proc.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    const timeout = new Promise<void>((resolve) =>
      setTimeout(resolve, this.opts.shutdownTimeoutMs)
    );
    await Promise.race([exitPromise, timeout]);

    if (!proc.killed && proc.exitCode === null) {
      try {
        proc.kill("SIGKILL");
      } catch {
        /* ignore */
      }
    }
    this._cleanupProc();
  }

  async send<K extends CommandName>(
    method: K,
    params: unknown
  ): Promise<CommandMap[K]["result"]> {
    if (!this.ready || !this.proc || !this.proc.stdin) {
      throw new Error(`SidecarManager: not ready (method=${method})`);
    }
    const id = randomUUID();
    const payload = JSON.stringify({ id, method, params }) + "\n";

    const requestPromise = new Promise<CommandMap[K]["result"]>((resolve, reject) => {
      this.pending.set(id, {
        resolve: resolve as (r: unknown) => void,
        reject,
        method,
      });
      this.proc!.stdin!.write(payload, (err) => {
        if (err) {
          this.pending.delete(id);
          reject(err);
        }
      });
    });

    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`SidecarManager: request timeout (method=${method}, id=${id})`));
      }, this.opts.requestTimeoutMs);
    });

    return Promise.race([requestPromise, timeoutPromise]);
  }

  // ─────────────────────────────────────
  // 内部：spawn 与握手
  // ─────────────────────────────────────

  private async _spawnAndWaitReady(): Promise<void> {
    let proc: ChildProcess;
    try {
      proc = this.opts.spawn(this.opts.command, this.opts.args, {
        stdio: ["pipe", "pipe", "pipe"],
      });
    } catch (err) {
      this.emit("error", err);
      throw err;
    }
    this.proc = proc;
    this.ready = false;
    this.startedAt = Date.now();
    this.lastPing = null;
    this.stdoutBuf = "";

    // 监听 stdout
    if (proc.stdout) {
      proc.stdout.on("data", (chunk: Buffer) => this._onStdout(chunk));
    }
    // 监听 stderr → 透传给日志
    if (proc.stderr) {
      proc.stderr.on("data", (chunk: Buffer) => {
        this.emit("log", chunk.toString());
      });
    }
    // 监听 exit
    proc.on("exit", (code, signal) => this._onExit(code, signal));

    // 等待 ready 握手
    await new Promise<void>((resolve, reject) => {
      const onReady = () => {
        cleanup();
        resolve();
      };
      const onExit = (code: number | null) => {
        cleanup();
        reject(new Error(`Sidecar exited before ready (code=${code})`));
      };
      const cleanup = () => {
        this.off("ready", onReady);
        proc.off("exit", onExit);
      };
      this.once("ready", onReady);
      proc.once("exit", onExit);
    });

    this.ready = true;
    this.restartAttempts = 0;
    this._startHeartbeatMonitor();
    this.emit("ready");
  }

  private _onStdout(chunk: Buffer): void {
    this.stdoutBuf += chunk.toString("utf8");
    let nl: number;
    while ((nl = this.stdoutBuf.indexOf("\n")) >= 0) {
      const line = this.stdoutBuf.slice(0, nl).trim();
      this.stdoutBuf = this.stdoutBuf.slice(nl + 1);
      if (!line) continue;
      this._handleLine(line);
    }
  }

  private _handleLine(line: string): void {
    let msg: unknown;
    try {
      msg = JSON.parse(line);
    } catch {
      this.emit("log", `[sidecar] unparseable line: ${line}`);
      return;
    }
    if (!msg || typeof msg !== "object") return;
    const m = msg as Record<string, unknown>;

    if (m["ready"] === true) {
      this.emit("ready");
      return;
    }
    if (typeof m["ping"] === "number") {
      this.lastPing = m["ping"];
      this.emit("ping", this.lastPing);
      return;
    }
    if (typeof m["id"] === "string") {
      const id = m["id"];
      const pending = this.pending.get(id);
      if (!pending) return;
      this.pending.delete(id);
      const resp = msg as SidecarResponse;
      if (resp.ok) {
        pending.resolve(resp.result);
      } else {
        pending.reject(new Error(resp.error));
      }
      return;
    }
  }

  // ─────────────────────────────────────
  // 内部：心跳监控
  // ─────────────────────────────────────

  private _startHeartbeatMonitor(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = setInterval(() => {
      if (!this.ready) return;
      if (this.lastPing === null) {
        // 启动后还没收到过 ping - 暂时不判定死亡，给 Python 3s 启动时间
        return;
      }
      if (Date.now() - this.lastPing > this.opts.heartbeatTimeoutMs) {
        this._safeEmitError(new Error("Sidecar heartbeat timeout"));
        if (this.proc) {
          try {
            this.proc.kill("SIGKILL");
          } catch {
            /* ignore */
          }
        }
      }
    }, this.opts.heartbeatCheckMs);
  }

  // ─────────────────────────────────────
  // 内部：退出与重启
  // ─────────────────────────────────────

  private _onExit(code: number | null, signal: NodeJS.Signals | null): void {
    this.ready = false;
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    // 拒绝所有未完成请求
    for (const [, p] of this.pending) {
      p.reject(new Error(`Sidecar exited (code=${code}, signal=${signal})`));
    }
    this.pending.clear();
    this.emit("exit", code, signal);

    if (this.shuttingDown) {
      this._cleanupProc();
      return;
    }
    if (code === 0) {
      // 主动退出，不重启
      this._cleanupProc();
      return;
    }
    // 崩溃：尝试重启
    this._scheduleRestart();
  }

  private _scheduleRestart(): void {
    if (this.restartAttempts >= this.opts.maxRestartAttempts) {
      this._safeEmitError(new Error("Sidecar restart limit reached"));
      this._cleanupProc();
      return;
    }
    this.restartAttempts += 1;
    const backoff = this.opts.restartBackoffMs * Math.pow(2, this.restartAttempts - 1);
    setTimeout(() => {
      this._spawnAndWaitReady()
        .then(() => this.emit("restart"))
        .catch((err) => this._safeEmitError(err));
    }, backoff);
  }

  private _cleanupProc(): void {
    this.proc = null;
    this.ready = false;
  }

  /**
   * 安全发送 "error" 事件：EventEmitter 在无监听时会同步抛出，
   * 可能在 proc 事件链中遮蔽真正的错误。仅在有监听时才 emit。
   */
  private _safeEmitError(err: Error): void {
    if (this.listenerCount("error") > 0) {
      this.emit("error", err);
    }
  }
}

// ─────────────────────────────────────
// 默认工厂：直接使用 child_process.spawn
// ─────────────────────────────────────

export function defaultSpawner(
  command: string,
  args: string[],
  options: { stdio: ["pipe", "pipe", "pipe"] }
): ChildProcess {
  return defaultSpawn(command, args, options);
}
