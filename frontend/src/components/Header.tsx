"use client";

import { Compass, Menu, Search, TrendingUp, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/utils";

export function Header() {
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/?q=${encodeURIComponent(trimmed)}`);
      setQuery("");
      setMenuOpen(false);
    }
  }

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/95 shadow-sm backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-xl font-bold tracking-tight text-blue-600 transition hover:bg-blue-100"
          aria-label="Go to homepage"
        >
          <TrendingUp className="h-6 w-6" aria-hidden="true" />
          <span>Home</span>
        </Link>

        <form onSubmit={handleSearch} className="hidden flex-1 sm:flex" role="search">
          <div className="relative w-full max-w-lg">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search match or team..."
              className="w-full rounded-full border border-slate-200 bg-slate-50 py-2 pl-9 pr-24 text-sm outline-none transition focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100"
            />
            <button
              type="submit"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700"
            >
              Search
            </button>
          </div>
        </form>

        <nav className="hidden items-center gap-5 text-sm font-medium text-slate-600 sm:flex">
          <NavLink href="/" active={pathname === "/"}>
            Best odds
          </NavLink>
          <NavLink href="/surebets" active={pathname === "/surebets"} tone="emerald">
            Surebets
          </NavLink>
          <NavLink href="/polymarket-new" active={pathname === "/polymarket-new"} tone="blue">
            New markets
          </NavLink>
        </nav>

        <button
          onClick={() => setMenuOpen((value) => !value)}
          className="ml-auto rounded p-1 text-slate-500 hover:bg-slate-100 sm:hidden"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
        >
          {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {menuOpen ? (
        <div className="border-t border-slate-200 bg-white px-4 pb-4 pt-3 sm:hidden">
          <form onSubmit={handleSearch} className="mb-3" role="search">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search match or team..."
                className="w-full rounded-full border border-slate-200 bg-slate-50 py-2 pl-9 pr-24 text-sm outline-none focus:border-blue-400 focus:bg-white"
              />
              <button
                type="submit"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700"
              >
                Search
              </button>
            </div>
          </form>
          <nav className="flex flex-col gap-2 text-sm font-medium">
            <Link
              href="/"
              onClick={() => setMenuOpen(false)}
              className={cn(
                "rounded px-2 py-1 hover:bg-slate-100",
                pathname === "/" ? "bg-slate-900 text-white hover:bg-slate-800" : "text-slate-700"
              )}
            >
              Best odds
            </Link>
            <Link
              href="/surebets"
              onClick={() => setMenuOpen(false)}
              className={cn(
                "rounded px-2 py-1 hover:bg-emerald-50",
                pathname === "/surebets" ? "bg-emerald-600 text-white hover:bg-emerald-600" : "text-emerald-700"
              )}
            >
              Surebets
            </Link>
            <Link
              href="/polymarket-new"
              onClick={() => setMenuOpen(false)}
              className={cn(
                "rounded px-2 py-1 hover:bg-blue-50",
                pathname === "/polymarket-new" ? "bg-blue-600 text-white hover:bg-blue-600" : "text-blue-700"
              )}
            >
              New markets
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}

function NavLink({
  href,
  active,
  tone = "slate",
  children,
}: {
  href: string;
  active: boolean;
  tone?: "slate" | "emerald" | "blue";
  children: React.ReactNode;
}) {
  const tones = {
    slate: active
      ? "bg-slate-900 text-white shadow-sm"
      : "bg-slate-100 text-slate-700 hover:bg-slate-200",
    emerald: active
      ? "bg-emerald-600 text-white shadow-sm"
      : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100",
    blue: active
      ? "bg-blue-600 text-white shadow-sm"
      : "bg-blue-50 text-blue-700 hover:bg-blue-100",
  } as const;

  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold transition-colors",
        tones[tone]
      )}
    >
      {active ? <Compass className="h-3.5 w-3.5" /> : null}
      <span>{children}</span>
    </Link>
  );
}
