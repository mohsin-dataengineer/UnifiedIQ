import type { Metadata } from "next";

import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "UnifiedIQ",
  description: "Governed conversational analytics over enterprise data",
};

// Runs before React hydrates so the theme is applied without a flash of the
// wrong palette. Reads localStorage; falls back to prefers-color-scheme.
const THEME_BOOT = `
(function(){
  try {
    var t = localStorage.getItem('unifiediq:theme');
    if (t !== 'light' && t !== 'dark') {
      t = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
