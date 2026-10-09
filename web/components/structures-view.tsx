"use client";

import { useEffect, useState } from "react";
import { getSources, getStructures } from "@/lib/api/client";
import type { Structure } from "@/lib/types";
import { StructureTable } from "@/components/structure-table";
import { ApiUnavailable, EmptyState } from "@/components/empty-state";

export function StructuresView() {
  const [structures, setStructures] = useState<Structure[]>([]);
  const [formula, setFormula] = useState("");
  const [source, setSource] = useState("");
  const [sourceOptions, setSourceOptions] = useState([
    "COD",
    "POWBASE",
  ]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  function load(cursor?: string) {
    setLoading(true);
    setFailed(false);
    getStructures({ formula: formula.trim() || undefined, source: source || undefined, limit: 25, cursor })
      .then((result) => {
        setStructures(result.items);
        setNextCursor(result.meta.next_cursor || null);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // The initial load intentionally runs once; filter changes use the explicit form action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    getSources()
      .then((result) => {
        const codes = result.items
          .map((item) => item.api_source_code)
          .filter((code): code is string => Boolean(code))
          .map((code) => code.toUpperCase())
          .sort();
        if (codes.length) setSourceOptions(codes);
      })
      .catch(() => {
        // Keep the known structure-source options available if the catalog fails.
      });
  }, []);

  return (
    <div className="page-frame py-12">
      <div className="max-w-3xl">
        <div className="eyebrow">Structure catalog</div>
        <h1 className="mt-3 page-title">Crystal structures</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">
          Source-retained crystallographic records with formula, cell, space-group and provenance metadata.
        </p>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          load();
        }}
        className="mt-8 panel grid gap-4 p-5 sm:grid-cols-[1fr_220px_auto]"
      >
        <label><span className="data-label">Formula</span><input value={formula} onChange={(event) => setFormula(event.target.value)} placeholder="e.g. C18 H22 Cu" className="mt-2 h-10 w-full border border-line px-3 text-sm" /></label>
        <label><span className="data-label">Source</span><select value={source} onChange={(event) => setSource(event.target.value)} className="mt-2 h-10 w-full border border-line bg-white px-3 text-sm"><option value="">All sources</option>{sourceOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <button className="button-primary self-end" type="submit">Apply filters</button>
      </form>
      <div className="mt-10 flex items-end justify-between"><div><div className="eyebrow">Results</div><h2 className="mt-2 section-title">{loading ? "Loading structures…" : `${structures.length} structures in this view`}</h2></div></div>
      <div className="mt-5">{failed ? <ApiUnavailable /> : loading ? <div className="panel p-8 text-sm text-slate-500">Loading structure metadata…</div> : structures.length ? <StructureTable structures={structures} /> : <EmptyState title="No structures were found." body="Try a broader formula or remove the source filter." />}</div>
      {nextCursor ? <div className="mt-5 flex justify-end"><button className="button-secondary" onClick={() => load(nextCursor)}>Next page <span aria-hidden="true">→</span></button></div> : null}
    </div>
  );
}
