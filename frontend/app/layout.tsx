import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";
import "../styles/theme.css";

export const metadata: Metadata = {
  title: "OrthoAssist",
  description: "OrthoAssist frontend scaffold",
};

const themeScript = `
(() => {
  try {
    const storageKey = "orthoassist-theme";
    const persisted = window.localStorage.getItem(storageKey);
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const mode =
      persisted === "dark" || persisted === "light"
        ? persisted
        : systemDark
          ? "dark"
          : "light";
    const root = document.documentElement;
    root.classList.toggle("dark", mode === "dark");
    root.style.colorScheme = mode === "dark" ? "dark" : "light";
  } catch (_) {}
})();
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <head>
          <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        </head>
        <body>
          <TooltipProvider delayDuration={120}>
            <div>{children}</div>
          </TooltipProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
