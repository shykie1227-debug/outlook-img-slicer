/**
 * ImagePreview 单元测试
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";

import { ImagePreview, toSafeFileUrl } from "./ImagePreview";

describe("toSafeFileUrl", () => {
  it("converts Unix absolute path to safe-file URL", () => {
    expect(toSafeFileUrl("/Users/test/photo.png")).toBe(
      "safe-file:///Users/test/photo.png"
    );
  });
  it("percent-encodes spaces in filename", () => {
    expect(toSafeFileUrl("/Users/test/my photo.png")).toBe(
      "safe-file:///Users/test/my%20photo.png"
    );
  });
  it("percent-encodes brackets", () => {
    expect(toSafeFileUrl("/Users/x/[1]/a.png")).toBe(
      "safe-file:///Users/x/%5B1%5D/a.png"
    );
  });
});

describe("ImagePreview", () => {
  it("renders an img with safe-file URL", () => {
    const { getByTestId } = render(
      <ImagePreview path="/Users/test/photo.png" maxHeight={300} />
    );
    const wrap = getByTestId("image-preview");
    expect(wrap).toBeInTheDocument();
    const img = wrap.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe("safe-file:///Users/test/photo.png");
    expect(img?.getAttribute("alt")).toBe("原图预览");
  });

  it("shows loading placeholder before load", () => {
    const { getByText } = render(<ImagePreview path="/a.png" />);
    expect(getByText("加载中…")).toBeInTheDocument();
  });

  it("uses custom alt when provided", () => {
    const { container } = render(
      <ImagePreview path="/a.png" alt="用户上传的长图" />
    );
    const img = container.querySelector("img");
    expect(img?.getAttribute("alt")).toBe("用户上传的长图");
  });
});
