import Link from "next/link";
import { API_BASE } from "@/lib/api/client";

const navigation = [
  { href: "/", label: "Home" },
  { href: "/database", label: "Database" },
  { href: "/multi-phase", label: "Multi-phase" },
  { href: "/structures", label: "Structures" },
  { href: "/reflection-sets", label: "Reflection sets" },
  { href: "/sources", label: "Sources" },
  { href: "/downloads", label: "Downloads" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-white/85 shadow-sm backdrop-blur">
      <div className="page-frame flex min-h-20 items-center justify-between gap-5">
        <Link href="/" className="flex min-w-fit items-center gap-3">
          <span
            aria-hidden="true"
            className="grid h-9 w-9 place-items-center rounded-md border border-blue-200 bg-blue-50 text-sm font-bold text-blue-700"
          >
            CDB
          </span>
          <span>
            <span className="block text-lg font-bold text-ink">
              CrystalDB
            </span>
            <span className="hidden text-[10px] font-semibold uppercase text-slate-500 sm:block">
              Experimental diffraction data
            </span>
          </span>
        </Link>

        <nav aria-label="Primary navigation" className="hidden items-center gap-5 lg:flex">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm font-semibold text-slate-600 transition hover:text-blue-700"
            >
              {item.label}
            </Link>
          ))}
          <a
            href={`${API_BASE.replace(/\/$/, "")}/docs`}
            target="_blank"
            rel="noreferrer"
            className="border-l border-line pl-5 text-sm font-semibold text-slate-600 transition hover:text-blue-700"
          >
            Docs
          </a>
        </nav>

        <details className="relative lg:hidden">
          <summary className="cursor-pointer list-none rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink">
            Menu
          </summary>
          <nav
            aria-label="Mobile navigation"
            className="absolute right-0 z-20 mt-2 w-52 rounded-lg border border-line bg-white p-2 shadow-panel"
          >
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="block px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-blue-50 hover:text-blue-700"
              >
                {item.label}
              </Link>
            ))}
            <a
              href={`${API_BASE.replace(/\/$/, "")}/docs`}
              target="_blank"
              rel="noreferrer"
              className="block border-t border-line px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-blue-50 hover:text-blue-700"
            >
              API Docs
            </a>
          </nav>
        </details>
      </div>
    </header>
  );
}
