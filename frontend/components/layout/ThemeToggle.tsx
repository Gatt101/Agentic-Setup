"use client";

import { MoonIcon, SunIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type ThemeMode = "dark" | "light";

const THEME_STORAGE_KEY = "orthoassist-theme";

function applyTheme(mode: ThemeMode) {
  const root = document.documentElement;
  const darkMode = mode === "dark";
  root.classList.toggle("dark", darkMode);
  root.style.colorScheme = darkMode ? "dark" : "light";
}

function resolveInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "light";
  }

  const persisted = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (persisted === "dark" || persisted === "light") {
    return persisted;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => resolveInitialTheme());

  useEffect(() => {
    applyTheme(mode);
  }, [mode]);

  const toggleTheme = () => {
    setMode((previousMode) => {
      const nextMode = previousMode === "light" ? "dark" : "light";
      window.localStorage.setItem(THEME_STORAGE_KEY, nextMode);
      return nextMode;
    });
  };

  return (
    <Button
      aria-label={`Switch to ${mode === "light" ? "dark" : "light"} mode`}
      className="h-8 w-8 rounded-full border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
      onClick={toggleTheme}
      size="icon-sm"
      type="button"
      variant="outline"
    >
      {mode === "light" ? (
        <MoonIcon className="size-4" />
      ) : (
        <SunIcon className="size-4" />
      )}
    </Button>
  );
}
