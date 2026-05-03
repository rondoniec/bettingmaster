"use client";

import { Menu, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/utils";

const NAV_ITEMS: { href: string; label: string }[] = [
  { href: "/", label: "Najlepšie kurzy" },
  { href: "/surebets", label: "Sigurebety" },
  { href: "/polymarket-new", label: "Nové trhy" },
];

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
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-screen-xl items-center gap-6 px-4 py-3.5 sm:px-6">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2 text-base font-semibold tracking-tight text-slate-900"
          aria-label="Domov"
        >
          <span className="inline-block h-3.5 w-3.5 bg-slate-900" aria-hidden="true" />
          BettingMaster
        </Link>

        <form onSubmit={handleSearch} className="hidden flex-1 sm:flex" role="search">
          <div className="relative w-full max-w-[420px]">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Hľadať zápas alebo tím…"
              className="w-full rounded-sm border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-900"
            />
          </div>
        </form>

        <nav className="ml-auto hidden items-center gap-6 text-sm font-medium sm:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              active={pathname === item.href || (item.href === "/" && pathname?.startsWith("/league"))}
            >
              {item.label}
            </NavLink>
          ))}
          <FeedStatus />
        </nav>

        <button
          onClick={() => setMenuOpen((value) => !value)}
          className="ml-auto rounded-sm p-1 text-slate-500 hover:bg-slate-100 sm:hidden"
          aria-label={menuOpen ? "Zavrieť menu" : "Otvoriť menu"}
        >
          {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {menuOpen ? (
        <div className="border-t border-slate-200 bg-white px-4 pb-4 pt-3 sm:hidden">
          <form onSubmit={handleSearch} className="mb-3" role="search">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Hľadať zápas alebo tím…"
                className="w-full rounded-sm border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-sm text-slate-900 outline-none focus:border-slate-900"
              />
            </div>
          </form>
          <nav className="flex flex-col gap-1 text-sm font-medium">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className={cn(
                  "border-l-2 px-3 py-2",
                  pathname === item.href
                    ? "border-slate-900 bg-slate-50 font-semibold text-slate-900"
                    : "border-transparent text-slate-600 hover:bg-slate-50",
                )}
              >
                {item.label}
              </Link>
            ))}
            <div className="px-3 pt-2">
              <FeedStatus />
            </div>
          </nav>
        </div>
      ) : null}
    </header>
  );
}

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "border-b-2 py-1.5 transition",
        active
          ? "border-slate-900 font-semibold text-slate-900"
          : "border-transparent text-slate-500 hover:text-slate-900",
      )}
    >
      {children}
    </Link>
  );
}

function FeedStatus() {
  return (
    <span className="ml-2 inline-flex items-center gap-2 border-l border-slate-200 pl-4 font-mono text-[11px] uppercase tracking-wider text-slate-500">
      <span className="bm-pulse inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
      Feed OK
    </span>
  );
}
