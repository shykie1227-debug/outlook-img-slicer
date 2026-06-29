/**
 * ThemeSwitcher 单元测试
 */
import { describe, it, expect, beforeEach } from "vitest";
import { render, fireEvent } from "@testing-library/react";

import { ThemeSwitcher } from "./ThemeSwitcher";
import { useAppStore } from "../store";

describe("ThemeSwitcher", () => {
  beforeEach(() => {
    useAppStore.getState().reset();
    useAppStore.getState().setTheme("dark");
  });

  it("renders sun icon when dark", () => {
    const { getByTestId } = render(<ThemeSwitcher />);
    expect(getByTestId("theme-switcher").textContent).toBe("☀");
  });

  it("renders moon icon when light", () => {
    useAppStore.getState().setTheme("light");
    const { getByTestId } = render(<ThemeSwitcher />);
    expect(getByTestId("theme-switcher").textContent).toBe("🌙");
  });

  it("toggles theme on click", () => {
    const { getByTestId } = render(<ThemeSwitcher />);
    expect(useAppStore.getState().theme).toBe("dark");
    fireEvent.click(getByTestId("theme-switcher"));
    expect(useAppStore.getState().theme).toBe("light");
    fireEvent.click(getByTestId("theme-switcher"));
    expect(useAppStore.getState().theme).toBe("dark");
  });

  it("adds dark class to documentElement when dark", () => {
    useAppStore.getState().setTheme("dark");
    render(<ThemeSwitcher />);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes dark class when light", () => {
    useAppStore.getState().setTheme("light");
    render(<ThemeSwitcher />);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
