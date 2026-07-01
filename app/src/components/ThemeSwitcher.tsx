/**
 * ThemeSwitcher 组件（V6.0.0 Phase 5）
 *
 * 暗/亮主题切换按钮，点击切换并同步到 <html> 上的 class。
 */
import { useEffect } from "react";

import { useAppStore } from "../store";

export function ThemeSwitcher(): JSX.Element {
  const theme = useAppStore((s) => s.theme);
  const toggleTheme = useAppStore((s) => s.toggleTheme);

  // 同步到 <html class="dark"> 让 Tailwind dark: 变体生效
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  return (
    <button
      data-testid="theme-switcher"
      onClick={toggleTheme}
      title={theme === "dark" ? "切换到亮色" : "切换到暗色"}
      aria-label={theme === "dark" ? "切换到亮色" : "切换到暗色"}
      className="px-3 py-1.5 text-sm rounded-md text-slate-300 hover:text-white hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
    >
      <span aria-hidden="true">{theme === "dark" ? "☀" : "🌙"}</span>
    </button>
  );
}
