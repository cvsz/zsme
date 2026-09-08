import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ZSME Enterprise",
    template: "%s | ZSME Enterprise",
  },
  description: "Thailand-first enterprise finance operations for growing businesses.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th" data-theme="dark" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
