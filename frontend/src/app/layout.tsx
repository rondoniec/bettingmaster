import type { Metadata } from "next";

import { Header } from "@/components/Header";
import { QueryProvider } from "@/providers/QueryProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "BettingMaster - Best Odds",
  description: "Compare bookmaker prices and spot the best odds for every match.",
  keywords: ["odds", "betting", "comparison", "Fortuna", "Nike", "DOXXbet", "Tipsport", "Tipos"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50 antialiased">
        <QueryProvider>
          <Header />
          <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
          <footer className="mt-12 border-t border-slate-200 bg-white py-6 text-center text-sm text-slate-500">
            <p>BettingMaster &copy; {new Date().getFullYear()} - live bookmaker comparison</p>
            <p className="mt-1 text-xs text-slate-400">Play responsibly. 18+. Odds are informational.</p>
          </footer>
        </QueryProvider>
      </body>
    </html>
  );
}
