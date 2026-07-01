/**
 * Electron 主进程入口（V6.0.0）
 *
 * 职责：
 * 1. 创建主窗口（加载 Vite dev 或打包后 index.html）
 * 2. 启动 Python Sidecar 子进程
 * 3. 注册 IPC 路由
 * 4. 转发 Sidecar 事件到渲染进程
 * 5. 优雅退出
 *
 * 硬约束（继承自 LOCAL_RULES.md）：
 * - 不联网
 * - 不自动更新
 * - 不埋点
 */
import { app, BrowserWindow, dialog, ipcMain, Menu, protocol, shell } from "electron";
import { join } from "node:path";

import { SidecarManager, defaultSpawner } from "./sidecar-manager.js";
import { registerIpc, unregisterIpc } from "./ipc.js";
import { registerAppHandlers, unregisterAppHandlers } from "./dialog-handlers.js";
import { handleSafeFile, toWebResponse } from "./safe-file-protocol.js";

const PROJECT_ROOT = join(__dirname, "..");

// ─────────────────────────────────────
// 自定义协议：safe-file://（白名单图片预览）
// 必须在 app.whenReady() 之前注册为 privileged
// ─────────────────────────────────────

protocol.registerSchemesAsPrivileged([
  {
    scheme: "safe-file",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      bypassCSP: false,
    },
  },
]);

// ─────────────────────────────────────
// 路径解析
// ─────────────────────────────────────

/** Sidecar 路径（开发 vs 打包） */
function getSidecarPath(): string {
  if (app.isPackaged) {
    return join(process.resourcesPath, "sidecar", "sidecar_server.exe");
  }
  return join(PROJECT_ROOT, "sidecar", "sidecar_server.py");
}

function isDev(): boolean {
  return !app.isPackaged && !!process.env["VITE_DEV_SERVER_URL"];
}

function getViteDevUrl(): string {
  return process.env["VITE_DEV_SERVER_URL"] ?? "http://localhost:5173";
}

function getProdIndexPath(): string {
  // 打包后：renderer 在 resources/app/index.html
  if (app.isPackaged) {
    return join(process.resourcesPath, "app", "index.html");
  }
  return join(PROJECT_ROOT, "app", "dist", "index.html");
}

// ─────────────────────────────────────
// 主窗口
// ─────────────────────────────────────

let mainWindow: BrowserWindow | null = null;
let sidecar: SidecarManager | null = null;
let isQuitting = false;
let appHandlerChannels: string[] = [];

function createMainWindow(): BrowserWindow {
  // V6.0.0：窗口图标（开发用项目根 icon.ico，打包用 resources）
  const iconPath = app.isPackaged
    ? join(process.resourcesPath, "icon.ico")
    : join(PROJECT_ROOT, "icon.ico");

  const win = new BrowserWindow({
    minWidth: 900,
    minHeight: 600,
    title: "Outlook 长图助手 V6.0.0",
    backgroundColor: "#0f172a",
    show: false,
    icon: iconPath,
    webPreferences: {
      preload: join(__dirname, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // 关闭时清理临时目录
  win.on("closed", () => {
    mainWindow = null;
  });

  // 阻止外链导航（新窗口打开）
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http")) {
      void shell.openExternal(url);
    }
    return { action: "deny" };
  });

  // 阻止应用内导航到外部 URL
  win.webContents.on("will-navigate", (event, url) => {
    if (isDev() && url.startsWith(getViteDevUrl())) return;
    event.preventDefault();
    if (url.startsWith("http")) {
      void shell.openExternal(url);
    }
  });

  return win;
}

async function loadRenderer(win: BrowserWindow): Promise<void> {
  if (isDev()) {
    await win.loadURL(getViteDevUrl());
  } else {
    await win.loadFile(getProdIndexPath());
  }
  win.once("ready-to-show", () => win.show());
}

// ─────────────────────────────────────
// Sidecar 启动与事件转发
// ─────────────────────────────────────

function startSidecar(): SidecarManager {
  const isWindows = process.platform === "win32";
  // 打包后是 .exe，开发是 .py
  const isPackaged = app.isPackaged;
  const cmd = isPackaged
    ? getSidecarPath()
    : isWindows
    ? "python"
    : "python3";
  const sidecarArgs = isPackaged ? [] : ["-u", getSidecarPath()];
  const manager = new SidecarManager(defaultSpawner, {
    command: cmd,
    args: sidecarArgs,
    heartbeatTimeoutMs: 10_000,
    maxRestartAttempts: 5,
  });

  manager.on("ready", () => {
    mainWindow?.webContents.send("sidecar:ready");
  });
  manager.on("exit", (code: number | null) => {
    mainWindow?.webContents.send("sidecar:exit", code);
  });
  manager.on("restart", () => {
    mainWindow?.webContents.send("sidecar:restart");
  });
  manager.on("error", (err: Error) => {
    mainWindow?.webContents.send("sidecar:error", err.message);
  });
  manager.on("log", (line: string) => {
    process.stderr.write(`[sidecar] ${line}`);
  });

  return manager;
}

// ─────────────────────────────────────
// 应用菜单（极简）
// ─────────────────────────────────────

function buildMenu(): Menu {
  const isMac = process.platform === "darwin";
  return Menu.buildFromTemplate([
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: "about" as const },
              { type: "separator" as const },
              { role: "quit" as const },
            ],
          },
        ]
      : []),
    {
      label: "文件",
      submenu: [
        {
          label: "退出",
          accelerator: "CmdOrCtrl+Q",
          click: () => app.quit(),
        },
      ],
    },
    {
      label: "视图",
      submenu: [
        { role: "reload" as const },
        { role: "toggleDevTools" as const },
        { type: "separator" as const },
        { role: "resetZoom" as const },
        { role: "zoomIn" as const },
        { role: "zoomOut" as const },
      ],
    },
  ]);
}

// ─────────────────────────────────────
// 生命周期
// ─────────────────────────────────────

app.whenReady().then(async () => {
  // 注册 safe-file 协议 handler
  protocol.handle("safe-file", async (request) => {
    const r = await handleSafeFile({ url: request.url });
    return toWebResponse(r);
  });

  Menu.setApplicationMenu(buildMenu());
  mainWindow = createMainWindow();

  sidecar = startSidecar();
  try {
    await sidecar.start();
  } catch (err) {
    process.stderr.write(`[main] sidecar start failed: ${(err as Error).message}\n`);
    // 继续运行，UI 会显示 Sidecar 错误状态
  }
  registerIpc(ipcMain, sidecar);
  appHandlerChannels = registerAppHandlers(
    ipcMain,
    {
      showOpenDialog: (win, opts) =>
        dialog.showOpenDialog(win as never, opts as never),
      showSaveDialog: (win, opts) =>
        dialog.showSaveDialog(win as never, opts as never),
    },
    {
      showItemInFolder: (p) => shell.showItemInFolder(p),
    },
    () => mainWindow
  );
  await loadRenderer(mainWindow);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow();
      void loadRenderer(mainWindow);
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", async (event) => {
  if (sidecar && !isQuitting) {
    isQuitting = true;
    event.preventDefault();
    try {
      await sidecar.stop();
    } catch {
      /* ignore */
    }
    unregisterIpc(ipcMain);
    if (appHandlerChannels.length > 0) {
      unregisterAppHandlers(ipcMain, appHandlerChannels);
      appHandlerChannels = [];
    }
    sidecar = null;
    app.quit();
  }
});
