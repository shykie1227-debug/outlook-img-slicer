import "@testing-library/jest-dom/vitest";
import { vi, beforeEach } from "vitest";
import { JSDOM } from "jsdom";

// jsdom 22 不实现 DataTransfer，stub 一个
class StubDataTransfer {
  dropEffect = "none";
  effectAllowed = "all";
  files: File[] = [];
  items: unknown[] = [];
  types: string[] = [];
}
if (typeof globalThis.DataTransfer === "undefined") {
  vi.stubGlobal("DataTransfer", StubDataTransfer);
}
if (typeof window !== "undefined" && typeof (window as unknown as { DataTransfer?: unknown }).DataTransfer === "undefined") {
  (window as unknown as { DataTransfer: typeof StubDataTransfer }).DataTransfer = StubDataTransfer;
}

// react-dom 18.3 的 getActiveElementDeep 用 `element instanceof win.HTMLIFrameElement`。
// vitest 1.6 + jsdom 22 下，win 是 vitest 注入的 jsdom window，
// 它的 HTMLIFrameElement 等 class 没有挂在 globalThis 上 → instanceof 失败。
// 优先用 vitest 的真实 window，回退到新建的 JSDOM。
const realWindow: Record<string, unknown> =
  typeof window !== "undefined"
    ? (window as unknown as Record<string, unknown>)
    : new JSDOM().window as unknown as Record<string, unknown>;
const bridge = (key: string): void => {
  const value = realWindow[key];
  if (typeof globalThis[key as keyof typeof globalThis] === "undefined" && value) {
    (globalThis as unknown as Record<string, unknown>)[key] = value;
  }
};
bridge("Comment");
bridge("Node");
bridge("DocumentFragment");
bridge("Text");
bridge("Element");
bridge("Event");
bridge("HTMLElement");
bridge("HTMLInputElement");
bridge("HTMLIFrameElement");
bridge("HTMLBodyElement");
bridge("HTMLDivElement");
bridge("HTMLButtonElement");
bridge("HTMLAnchorElement");
bridge("HTMLImageElement");
bridge("Document");
bridge("Window");
bridge("MouseEvent");
bridge("KeyboardEvent");
bridge("DragEvent");
bridge("InputEvent");
bridge("FocusEvent");
bridge("CustomEvent");
bridge("UIEvent");
bridge("SVGElement");
bridge("SVGSVGElement");
bridge("SVGRectElement");
bridge("SVGLineElement");
bridge("SVGTextElement");
bridge("HTMLSelectElement");
bridge("HTMLOptionElement");
bridge("HTMLLabelElement");

// 内存版 localStorage（jsdom 22 在 vitest 1.6 下也有不稳定行为）
const memoryStore = new Map<string, string>();
const memoryStorage = {
  getItem: (k: string) => memoryStore.get(k) ?? null,
  setItem: (k: string, v: string) => {
    memoryStore.set(k, String(v));
  },
  removeItem: (k: string) => {
    memoryStore.delete(k);
  },
  clear: () => {
    memoryStore.clear();
  },
  key: (i: number) => Array.from(memoryStore.keys())[i] ?? null,
  get length() {
    return memoryStore.size;
  },
} as Storage;

vi.stubGlobal("localStorage", memoryStorage);
if (typeof window !== "undefined") {
  (window as unknown as { localStorage: Storage }).localStorage = memoryStorage;
}

beforeEach(() => {
  memoryStore.clear();
});
