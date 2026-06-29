/**
 * safe-file 协议单元测试
 */
import { describe, it, expect, vi } from "vitest";
import { Buffer } from "node:buffer";

import {
  handleSafeFile,
  isAllowedExtension,
  getExt,
} from "./safe-file-protocol";

describe("getExt", () => {
  it("returns lowercase extension with dot", () => {
    expect(getExt("a.PNG")).toBe(".png");
    expect(getExt("/path/to/b.JPEG")).toBe(".jpeg");
  });
  it("returns empty when no extension", () => {
    expect(getExt("noext")).toBe("");
    expect(getExt("Makefile")).toBe("");
  });
  it("uses the last dot in the filename portion", () => {
    expect(getExt("archive.tar.gz")).toBe(".gz");
  });
});

describe("isAllowedExtension", () => {
  it("accepts common image formats", () => {
    expect(isAllowedExtension("photo.png")).toBe(true);
    expect(isAllowedExtension("PHOTO.JPG")).toBe(true);
    expect(isAllowedExtension("a/b/c.WebP")).toBe(true);
    expect(isAllowedExtension("x.tiff")).toBe(true);
  });
  it("rejects non-image extensions", () => {
    expect(isAllowedExtension("virus.exe")).toBe(false);
    expect(isAllowedExtension("script.ps1")).toBe(false);
    expect(isAllowedExtension("doc.pdf")).toBe(false);
    expect(isAllowedExtension("noext")).toBe(false);
  });
});

describe("handleSafeFile", () => {
  it("returns 200 with image content for allowed PNG", async () => {
    const reader = { read: vi.fn(async () => Buffer.from("\x89PNG-fake")) };
    const r = await handleSafeFile(
      { url: "safe-file:///Users/test/photo.png" },
      reader
    );
    expect(r.status).toBe(200);
    expect(r.contentType).toBe("image/png");
    expect(r.data.toString()).toBe("\x89PNG-fake");
    expect(reader.read).toHaveBeenCalledWith("/Users/test/photo.png");
  });

  it("returns correct mime for jpg/jpeg", async () => {
    const reader = { read: vi.fn(async () => Buffer.from("x")) };
    const r1 = await handleSafeFile({ url: "safe-file:///a/b.jpg" }, reader);
    expect(r1.contentType).toBe("image/jpeg");
    const r2 = await handleSafeFile({ url: "safe-file:///a/b.jpeg" }, reader);
    expect(r2.contentType).toBe("image/jpeg");
  });

  it("strips leading slash on Windows for /C:/... paths", async () => {
    const reader = { read: vi.fn(async () => Buffer.from("x")) };
    const r = await handleSafeFile(
      { url: "safe-file:///C:/Users/test/photo.png" },
      reader,
      "win32"
    );
    expect(r.status).toBe(200);
    expect(reader.read).toHaveBeenCalledWith("C:/Users/test/photo.png");
  });

  it("returns 403 and does not read when extension is not allowed", async () => {
    const reader = { read: vi.fn(async () => Buffer.from("dangerous")) };
    const r = await handleSafeFile(
      { url: "safe-file:///tmp/virus.exe" },
      reader
    );
    expect(r.status).toBe(403);
    expect(r.contentType).toBe("text/plain");
    expect(reader.read).not.toHaveBeenCalled();
  });

  it("returns 404 when file is missing", async () => {
    const reader = {
      read: vi.fn(async () => {
        throw new Error("ENOENT");
      }),
    };
    const r = await handleSafeFile(
      { url: "safe-file:///tmp/missing.png" },
      reader
    );
    expect(r.status).toBe(404);
  });

  it("returns 400 for malformed URL", async () => {
    const reader = { read: vi.fn(async () => Buffer.from("x")) };
    const r = await handleSafeFile({ url: "not a url" }, reader);
    expect(r.status).toBe(400);
  });

  it("decodes percent-encoded paths", async () => {
    const reader = { read: vi.fn(async () => Buffer.from("x")) };
    await handleSafeFile(
      { url: "safe-file:///Users/test/my%20photo.png" },
      reader
    );
    expect(reader.read).toHaveBeenCalledWith("/Users/test/my photo.png");
  });
});
