/**
 * 开发环境启动脚本（V6.0.0）
 *
 * 流程：
 * 1. 启动 Vite dev server（app/）
 * 2. 等待 Vite 就绪（http://localhost:5173）
 * 3. 编译 Electron 主进程（electron/ → dist-electron/）
 * 4. 启动 Electron 主进程（加载编译产物 + VITE_DEV_SERVER_URL）
 * 5. Vite / Electron 任意一方退出，另一方也退出
 *
 * 用户在 Mac 上跑 dev 时不会启动 Sidecar 的 outlook.* 命令（仅 Windows 有效）。
 */
import { spawn, type ChildProcess } from "node:child_process";
import { spawn as exec } from "node:child_process";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "..");
const ELECTRON_DIR = join(PROJECT_ROOT, "electron");

const VITE_URL = "http://localhost:5173";
const VITE_READY_TIMEOUT_MS = 30_000;

let vite: ChildProcess | null = null;
let electron: ChildProcess | null = null;
let cleaning = false;

function startVite(): ChildProcess {
  console.log("[dev] starting Vite dev server...");
  const proc = spawn("npm", ["run", "dev", "--prefix", "app"], {
    cwd: PROJECT_ROOT,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env },
  });
  proc.stdout?.on("data", (chunk: Buffer) => {
    process.stdout.write(`[vite] ${chunk.toString()}`);
  });
  proc.stderr?.on("data", (chunk: Buffer) => {
    process.stderr.write(`[vite] ${chunk.toString()}`);
  });
  proc.on("exit", (code) => {
    console.log(`[dev] Vite exited with code=${code}`);
    cleanup(code);
  });
  return proc;
}

function compileMain(): Promise<void> {
  return new Promise((res, rej) => {
    console.log("[dev] compiling Electron main process (tsc)...");
    const tsc = spawn("npm", ["run", "build", "--prefix", "electron"], {
      cwd: PROJECT_ROOT,
      stdio: "inherit",
    });
    tsc.on("exit", (code) => {
      if (code === 0) {
        console.log("[dev] tsc done");
        res();
      } else {
        rej(new Error(`tsc exited with code=${code}`));
      }
    });
  });
}

function startElectron(): ChildProcess {
  console.log("[dev] starting Electron main process...");
  // 注意：npx electron + 工作目录切换
  const proc = spawn("npx", ["electron", "."], {
    cwd: ELECTRON_DIR,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      VITE_DEV_SERVER_URL: VITE_URL,
      ELECTRON_DISABLE_SANDBOX: "1",
    },
  });
  proc.stdout?.on("data", (chunk: Buffer) => {
    process.stdout.write(`[electron] ${chunk.toString()}`);
  });
  proc.stderr?.on("data", (chunk: Buffer) => {
    process.stderr.write(`[electron] ${chunk.toString()}`);
  });
  proc.on("exit", (code) => {
    console.log(`[dev] Electron exited with code=${code}`);
    cleanup(code);
  });
  return proc;
}

async function waitForVite(url: string, timeoutMs: number): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 304) {
        console.log(`[dev] Vite ready at ${url}`);
        return;
      }
    } catch {
      // Vite 还没起来
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Vite dev server did not start within ${timeoutMs}ms`);
}

function cleanup(code: number | null = 0): void {
  if (cleaning) return;
  cleaning = true;
  if (electron) {
    try {
      electron.kill("SIGTERM");
    } catch {
      /* ignore */
    }
  }
  if (vite) {
    try {
      vite.kill("SIGTERM");
    } catch {
      /* ignore */
    }
  }
  setTimeout(() => process.exit(code ?? 0), 200);
}

async function main(): Promise<void> {
  process.on("SIGINT", () => cleanup(0));
  process.on("SIGTERM", () => cleanup(0));

  vite = startVite();
  try {
    await waitForVite(VITE_URL, VITE_READY_TIMEOUT_MS);
  } catch (err) {
    console.error(`[dev] ${(err as Error).message}`);
    cleanup(1);
    return;
  }

  try {
    await compileMain();
  } catch (err) {
    console.error(`[dev] ${(err as Error).message}`);
    cleanup(1);
    return;
  }

  electron = startElectron();
}

void main();
