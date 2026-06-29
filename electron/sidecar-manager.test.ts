/**
 * SidecarManager 单元测试（V6.0.0）
 *
 * 测试目标：
 * 1. 启动子进程并等待 {"ready": true} 握手
 * 2. send() 发送 JSON-RPC 命令，收到响应
 * 3. 跟踪 {"ping": ts} 心跳
 * 4. 子进程崩溃后自动重启（指数退避）
 * 5. 优雅关闭（SIGTERM / 等待清理）
 * 6. status() 反映当前真实状态
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { PassThrough } from "node:stream";
import { EventEmitter } from "node:events";
import type { Readable, Writable } from "node:stream";
import type { ChildProcess } from "node:child_process";

import {
  SidecarManager,
  type SidecarSpawner,
  type SidecarOptions,
} from "./sidecar-manager.js";

/**
 * 模拟子进程：双工流 + EventEmitter
 * - stdout: 我们写
 * - stdin: 我们读
 * - exit 事件: kill() 后触发
 */
class FakeProcess extends EventEmitter {
  stdout = new PassThrough() as Readable;
  stdin = new PassThrough() as Writable;
  pid = 12345;
  killed = false;
  kill = vi.fn((signal?: NodeJS.Signals) => {
    this.killed = true;
    this.emit("exit", null, signal ?? "SIGTERM");
    return true;
  });
  /** 测试辅助：模拟 Python 启动握手 */
  emitReady(): void {
    this.stdout.write(JSON.stringify({ ready: true }) + "\n");
  }
  /** 测试辅助：模拟 Python 响应 */
  emitResponse(id: string, result: unknown): void {
    this.stdout.write(
      JSON.stringify({ id, ok: true, result }) + "\n"
    );
  }
  /** 测试辅助：模拟 Python 错误响应 */
  emitErrorResponse(id: string, error: string): void {
    this.stdout.write(
      JSON.stringify({ id, ok: false, error }) + "\n"
    );
  }
  /** 测试辅助：模拟心跳 */
  emitPing(ts: number): void {
    this.stdout.write(JSON.stringify({ ping: ts }) + "\n");
  }
}

describe("SidecarManager", () => {
  let fake: FakeProcess;
  let spawner: SidecarSpawner;
  let manager: SidecarManager;

  beforeEach(() => {
    fake = new FakeProcess();
    spawner = vi.fn(() => fake as unknown as ChildProcess);
    const options: SidecarOptions = {
      command: "python",
      args: ["-u", "sidecar/sidecar_server.py"],
      heartbeatTimeoutMs: 500,
      maxRestartAttempts: 3,
      restartBackoffMs: 0,
    };
    manager = new SidecarManager(spawner, options);
  });

  afterEach(async () => {
    await manager.stop();
  });

  describe("start()", () => {
    it("spawns the child process and resolves on ready handshake", async () => {
      const startPromise = manager.start();
      // 启动时 spawn 应被调用
      expect(spawner).toHaveBeenCalledTimes(1);
      // 模拟 Python 发送握手
      fake.emitReady();
      await expect(startPromise).resolves.toBeUndefined();
      expect(manager.isReady()).toBe(true);
    });

    it("rejects when spawn fails", async () => {
      const brokenSpawner: SidecarSpawner = vi.fn(() => {
        throw new Error("spawn ENOENT");
      });
      const m = new SidecarManager(brokenSpawner, {
        command: "missing",
        args: [],
      });
      await expect(m.start()).rejects.toThrow("spawn ENOENT");
    });
  });

  describe("send()", () => {
    it("sends a JSON-RPC request and resolves with the response", async () => {
      const collectedWrites: string[] = [];
      fake.stdin.on("data", (chunk: Buffer) => {
        collectedWrites.push(chunk.toString());
      });
      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      const sendPromise = manager.send("image.info", { path: "/tmp/a.png" });
      // 等待 microtask 让 send 把请求写入 stdin
      await new Promise((r) => setImmediate(r));
      const written = collectedWrites.join("");
      expect(written).toContain('"method":"image.info"');
      expect(written).toContain('"params":{"path":"/tmp/a.png"}');

      const reqMatch = written.match(/"id":"([^"]+)"/);
      const reqId = reqMatch ? reqMatch[1] : "";
      expect(reqId).not.toBe("");
      fake.emitResponse(reqId, { width: 100, height: 200, format: "PNG", mode: "RGB", size_bytes: 1024 });

      await expect(sendPromise).resolves.toEqual({
        width: 100,
        height: 200,
        format: "PNG",
        mode: "RGB",
        size_bytes: 1024,
      });
    });

    it("rejects when the response is an error", async () => {
      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      const collected: string[] = [];
      fake.stdin.on("data", (chunk: Buffer) => collected.push(chunk.toString()));
      const sendPromise = manager.send("image.info", { path: "/missing.png" });
      await new Promise((r) => setImmediate(r));
      const reqId = (collected.join("").match(/"id":"([^"]+)"/) ?? [])[1] ?? "";
      fake.emitErrorResponse(reqId, "FileNotFoundError: /missing.png");
      await expect(sendPromise).rejects.toThrow("FileNotFoundError");
    });

    it("rejects if not ready", async () => {
      await expect(
        manager.send("image.info", { path: "/tmp/a.png" })
      ).rejects.toThrow(/not ready/i);
    });
  });

  describe("heartbeat", () => {
    it("emits ping events with timestamp", async () => {
      const onPing = vi.fn();
      manager.on("ping", onPing);
      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      fake.emitPing(1700000000.5);
      fake.emitPing(1700000003.5);
      expect(onPing).toHaveBeenCalledTimes(2);
      expect(onPing).toHaveBeenNthCalledWith(1, 1700000000.5);
      expect(onPing).toHaveBeenNthCalledWith(2, 1700000003.5);
    });
  });

  describe("crash & restart", () => {
    it("restarts the child process after unexpected exit", async () => {
      const onRestart = vi.fn();
      manager.on("restart", onRestart);

      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      // 模拟子进程崩溃（exit code 非 0）
      const secondProcess = new FakeProcess();
      (spawner as ReturnType<typeof vi.fn>).mockReturnValueOnce(
        secondProcess as unknown as ChildProcess
      );
      fake.emit("exit", 1, null);
      // 等待重启退避
      await new Promise((r) => setTimeout(r, 10));
      secondProcess.emitReady();
      await new Promise((r) => setImmediate(r));

      expect(spawner).toHaveBeenCalledTimes(2);
      expect(onRestart).toHaveBeenCalled();
      expect(manager.isReady()).toBe(true);
    });

    it("rejects all pending requests when the process crashes", async () => {
      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      const collected: string[] = [];
      fake.stdin.on("data", (chunk: Buffer) => collected.push(chunk.toString()));

      const p1 = manager.send("image.info", { path: "/tmp/a.png" });
      const p2 = manager.send("image.info", { path: "/tmp/b.png" });
      await new Promise((r) => setImmediate(r));
      expect(collected.length).toBeGreaterThan(0);

      // 模拟 crash（不调用 ready 前 emit exit）
      fake.emit("exit", 1, null);

      await expect(p1).rejects.toThrow(/exited/);
      await expect(p2).rejects.toThrow(/exited/);
      expect(manager.status().is_alive).toBe(false);
    });

    it("stops restarting after max attempts", async () => {
      const onError = vi.fn();
      manager.on("error", onError);
      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      for (let i = 0; i < 5; i++) {
        const p = new FakeProcess();
        (spawner as ReturnType<typeof vi.fn>).mockReturnValueOnce(
          p as unknown as ChildProcess
        );
        fake.emit("exit", 1, null);
        await new Promise((r) => setTimeout(r, 5));
        fake = p;
      }
      expect(onError).toHaveBeenCalled();
      expect(manager.isReady()).toBe(false);
    });
  });

  describe("start() failure paths", () => {
    it("rejects when child process exits before ready handshake", async () => {
      // 新建一个不会发送 ready 的子进程
      const silent = new FakeProcess();
      const localSpawner: SidecarSpawner = vi.fn(
        () => silent as unknown as ChildProcess
      );
      const m = new SidecarManager(localSpawner, {
        command: "python",
        args: [],
        maxRestartAttempts: 0,
      });
      const startPromise = m.start();
      // 立即 emit exit（没 ready）
      silent.emit("exit", 1, null);
      await expect(startPromise).rejects.toThrow(/before ready/);
    });
  });

  describe("stop()", () => {
    it("sends SIGTERM and waits for exit", async () => {
      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      const stopPromise = manager.stop();
      // FakeProcess.kill 已经 emit("exit")
      await expect(stopPromise).resolves.toBeUndefined();
      expect(fake.kill).toHaveBeenCalledWith("SIGTERM");
    });
  });

  describe("status()", () => {
    it("reports alive and uptime after start", async () => {
      const startPromise = manager.start();
      fake.emitReady();
      await startPromise;

      const s = manager.status();
      expect(s.is_alive).toBe(true);
      expect(s.pid).toBe(12345);
      expect(s.uptime_seconds).toBeGreaterThanOrEqual(0);
    });

    it("reports not alive before start", () => {
      const s = manager.status();
      expect(s.is_alive).toBe(false);
      expect(s.pid).toBe(0);
    });
  });
});
