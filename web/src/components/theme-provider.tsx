"use client";
import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<{ theme: Theme; setTheme: (value: Theme) => void }>({ theme: "system", setTheme: () => {} });
let fallback: Theme = "system";
function snapshot(): Theme {
  try { const saved = localStorage.getItem("hopfan-theme"); return saved === "light" || saved === "dark" || saved === "system" ? saved : fallback; }
  catch { return fallback; }
}
function subscribe(listener: () => void) {
  window.addEventListener("storage", listener); window.addEventListener("hopfan-theme-change", listener);
  return () => { window.removeEventListener("storage", listener); window.removeEventListener("hopfan-theme-change", listener); };
}
export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useSyncExternalStore<Theme>(subscribe, snapshot, () => "system");
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => { document.documentElement.dataset.theme = theme === "system" ? (media.matches ? "dark" : "light") : theme; };
    apply(); media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  const change = (value: Theme) => { fallback = value; try { localStorage.setItem("hopfan-theme", value); } catch { /* Keep an in-memory visual preference when storage is unavailable. */ } window.dispatchEvent(new Event("hopfan-theme-change")); };
  return <ThemeContext.Provider value={{ theme, setTheme: change }}>{children}</ThemeContext.Provider>;
}
export function ThemeControl() {
  const { theme, setTheme } = useContext(ThemeContext);
  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  return <label className="theme-control"><Icon size={16} aria-hidden="true" /><span className="sr-only">Colour theme</span>
    <select aria-label="Colour theme" value={theme} onChange={event => setTheme(event.target.value as Theme)}>
      <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
    </select></label>;
}
