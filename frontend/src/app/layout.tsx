import type { Metadata } from "next";
import { Geist, JetBrains_Mono } from "next/font/google";

import { Header } from "@/components/Header";
import { QueryProvider } from "@/providers/QueryProvider";

import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});

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
    <html lang="sk" suppressHydrationWarning className={`${geist.variable} ${jetbrains.variable}`}>
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <QueryProvider>
          <Header />
          <main className="mx-auto max-w-screen-xl px-4 py-6 sm:px-6">{children}</main>
          <footer className="mt-12 border-t border-slate-200 bg-white py-6 text-center font-mono text-[11px] uppercase tracking-wider text-slate-500">
            <p>BettingMaster &copy; {new Date().getFullYear()} — live bookmaker comparison</p>
            <p className="mt-1 text-[10px] text-slate-400">Hraj zodpovedne. 18+. Kurzy sú informačné.</p>
          </footer>
        </QueryProvider>
      </body>
    </html>
  );
}
