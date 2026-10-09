"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { looksLikeFormula } from "@/lib/formula";

interface SearchBoxProps {
  compact?: boolean;
  initialValue?: string;
  baseParams?: Record<string, string | undefined>;
}

function databaseUrl(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const encoded = search.toString();
  return `/database${encoded ? `?${encoded}` : ""}`;
}

export function SearchBox({
  compact = false,
  initialValue = "",
  baseParams = {},
}: SearchBoxProps) {
  const router = useRouter();
  const [query, setQuery] = useState(initialValue);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (!value) {
      router.push(databaseUrl(baseParams));
      return;
    }
    const formulaShortcutEnabled =
      baseParams.modality !== "single_crystal_xrd";
    if (/^STR_[A-Za-z0-9_-]+$/i.test(value)) {
      router.push(databaseUrl({ ...baseParams, structure_id: value }));
      return;
    }
    if (formulaShortcutEnabled && looksLikeFormula(value)) {
      router.push(databaseUrl({ ...baseParams, component_formula: value }));
      return;
    }
    router.push(databaseUrl({ ...baseParams, q: value }));
  }

  return (
    <form onSubmit={submit} className="flex w-full flex-col gap-2 sm:flex-row">
      <label className="sr-only" htmlFor="crystaldb-search">
        Search CrystalDB
      </label>
      <input
        id="crystaldb-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search pattern ID, material, formula, structure or source ID"
        className={`min-w-0 flex-1 border border-line bg-white px-4 text-sm text-ink placeholder:text-slate-400 ${
          compact ? "h-11" : "h-14"
        }`}
      />
      <button type="submit" className={compact ? "button-secondary h-11" : "button-primary h-14"}>
        Search database
      </button>
    </form>
  );
}
