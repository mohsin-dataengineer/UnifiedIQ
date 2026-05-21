"use client";

import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/contexts/theme-context";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      className="flex h-9 items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--bg)] px-1 text-[var(--muted)] transition-colors hover:text-[var(--fg)]"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      aria-pressed={dark}
      title={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      <span
        className={`flex h-7 w-7 items-center justify-center rounded-full transition-colors ${
          dark
            ? "text-[var(--muted)]"
            : "bg-[var(--surface)] text-[var(--accent)] shadow-sm"
        }`}
      >
        <Sun size={14} />
      </span>
      <span
        className={`flex h-7 w-7 items-center justify-center rounded-full transition-colors ${
          dark
            ? "bg-[var(--surface)] text-[var(--accent)] shadow-sm"
            : "text-[var(--muted)]"
        }`}
      >
        <Moon size={14} />
      </span>
    </button>
  );
}
