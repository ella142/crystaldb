"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPatterns, getSources, getStats } from "@/lib/api/client";
import type { ApiStats, Pattern, SourceCatalogItem } from "@/lib/types";
import { bestMaterialName, formatNumber } from "@/lib/format";
import { SearchBox } from "@/components/search-box";
import { MetricCard } from "@/components/metric-card";
import { ApiUnavailable } from "@/components/empty-state";
import { PhaseBadge } from "@/components/status-badge";

const entryPoints = [
  {
    href: "/database?modality=powder_xrd",
    label: "Experimental powder XRD",
    body: "Browse measured 2θ-intensity patterns with source-aware metadata and phase context.",
  },
  {
    href: "/multi-phase",
    label: "Multi-phase data",
    body: "Inspect mixtures as first-class records, including their explicit component descriptions.",
  },
  {
    href: "/structures",
    label: "Crystal structures",
    body: "Browse source-retained structure records and open registered CIF files where available.",
  },
  {
    href: "/database?modality=single_crystal_xrd",
    label: "Reflection data",
    body: "Find single-crystal datasets and their associated reflection-set resources.",
  },
];

export function HomeView() {
  const [stats, setStats] = useState<ApiStats | null>(null);
  const [sources, setSources] = useState<SourceCatalogItem[]>([]);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([getStats(), getSources(), getPatterns({ limit: 4 })])
      .then(([nextStats, nextSources, nextPatterns]) => {
        setStats(nextStats);
        setSources(nextSources.items);
        setPatterns(nextPatterns.items);
      })
      .catch(() => setFailed(true));
  }, []);

  return (
    <div>
      <section className="border-b border-line bg-white">
        <div className="page-frame grid gap-8 py-14 lg:grid-cols-[1.12fr_0.88fr] lg:items-end lg:py-20">
          <div>
            <div className="eyebrow">Production research data portal</div>
            <h1 className="mt-4 max-w-3xl text-4xl font-semibold text-ink sm:text-6xl">
              CrystalDB
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
              A provenance-aware crystallographic database linking experimental
              X-ray diffraction measurements to crystal structures.
            </p>
            <div className="panel mt-8 max-w-3xl p-3">
              <SearchBox />
              <p className="mt-3 text-xs text-slate-500">
                Search identifiers, material names, formulas, source records, or structure IDs.
              </p>
            </div>
          </div>
          <div className="quiet-panel border-l-4 border-blue-500 p-6">
            <div className="eyebrow">Scientific scope</div>
            <p className="mt-3 text-xl leading-8 text-ink">
              Experimental observations and structural relations remain
              separate, inspectable, and honest about uncertainty.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <span className="pill border-blue-100 bg-blue-50 text-blue-700">Experimental XRD</span>
              <span className="pill border-teal-100 bg-teal-50 text-teal-700">Provenance</span>
              <span className="pill border-amber-100 bg-amber-50 text-amber-700">Ambiguity preserved</span>
            </div>
          </div>
        </div>
      </section>

      <section className="page-frame py-12">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          <MetricCard label="Sources" value={formatNumber(stats?.source_count, 0)} detail="Catalogued data sources" />
          <MetricCard label="Samples" value={formatNumber(stats?.sample_count, 0)} detail="Canonical sample records" />
          <MetricCard label="Measurements" value={formatNumber(stats?.measurement_count, 0)} detail="Experimental measurements" />
          <MetricCard label="Patterns" value={formatNumber(stats?.pattern_count, 0)} detail="Experimental diffraction patterns" />
          <MetricCard label="Structures" value={formatNumber(stats?.structure_count, 0)} detail="Source-retained records" />
          <MetricCard label="Reflection sets" value={formatNumber(stats?.reflection_set_count, 0)} detail="Single-crystal datasets" />
          <MetricCard label="Relations" value={formatNumber(stats?.relation_count, 0)} detail="Stored provenance relations" />
          <MetricCard label="PowBase X-ray" value={formatNumber(stats?.powbase_xray_pattern_count, 0)} detail="PowBase powder patterns" />
          <MetricCard label="Powder patterns" value={formatNumber(stats?.powder_pattern_count, 0)} detail="Experimental powder XRD" />
          <MetricCard label="Multi-phase" value={formatNumber(stats?.multiphase_pattern_count, 0)} detail="Explicit mixture records" />
        </div>
        {failed ? <div className="mt-6"><ApiUnavailable /></div> : null}
      </section>

      <section className="border-y border-line bg-[#edf3f7]">
        <div className="page-frame py-12">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="eyebrow">Browse by evidence</div>
              <h2 className="mt-2 section-title">Start with the record type you need</h2>
            </div>
            <Link href="/database" className="link-blue text-sm">Open database browser</Link>
          </div>
          <div className="mt-7 grid gap-4 md:grid-cols-2">
            {entryPoints.map((entry, index) => (
              <Link key={entry.href} href={entry.href} className="panel group p-6 transition hover:-translate-y-0.5 hover:border-blue-300">
                <div className="flex items-start justify-between gap-4">
                  <span className="text-sm font-bold text-blue-600">0{index + 1}</span>
                  <span aria-hidden="true" className="text-lg text-slate-400 transition group-hover:translate-x-1 group-hover:text-blue-600">→</span>
                </div>
                <h3 className="mt-8 text-lg font-semibold text-ink">{entry.label}</h3>
                <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">{entry.body}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="page-frame grid gap-8 py-12 lg:grid-cols-[1fr_0.82fr]">
        <div>
          <div className="eyebrow">Records from the live API</div>
          <h2 className="mt-2 section-title">A small window into the live API</h2>
          <div className="mt-6 overflow-hidden rounded-lg border border-line bg-white">
            {patterns.length ? patterns.map((pattern) => (
              <Link key={pattern.pattern_id} href={`/patterns/${encodeURIComponent(pattern.pattern_id)}`} className="flex flex-col gap-3 border-b border-line p-5 last:border-0 hover:bg-blue-50/40 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="link-blue text-xs">{pattern.pattern_id}</div>
                  <div className="mt-2 text-sm font-semibold text-ink">{bestMaterialName(pattern)}</div>
                  <div className="mt-1 text-xs text-slate-500">{pattern.source.code} · {pattern.modality}</div>
                </div>
                <PhaseBadge value={pattern.phase_character} />
              </Link>
            )) : <div className="p-6 text-sm text-slate-500">Loading records from the CrystalDB API…</div>}
          </div>
        </div>
        <div>
          <div className="eyebrow">Source catalog</div>
          <h2 className="mt-2 section-title">Where the data comes from</h2>
          <div className="mt-6 grid gap-3">
            {sources.length ? sources.map((source) => (
              (() => {
                const code = String(source.api_source_code || source.short_name || source.label || "UNKNOWN").toUpperCase();
                const patternCount = stats?.powder_pattern_counts_by_source?.[code];
                const phaseCounts = stats?.source_phase_counts?.[code] || {};
                const href = code === "COD" ? "/structures" : `/database?source=${encodeURIComponent(code)}`;
                return (
                  <Link key={String(source.source_id || code)} href={href} className="panel group p-5 transition hover:-translate-y-0.5 hover:border-blue-300">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="eyebrow">{code}</div>
                        <div className="mt-2 text-sm font-semibold text-ink">{String(source.name || source.description || "Source catalog entry")}</div>
                      </div>
                      <span aria-hidden="true" className="text-lg text-slate-400 transition group-hover:translate-x-1 group-hover:text-blue-600">→</span>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                      {patternCount !== undefined ? <span className="pill border-blue-100 bg-blue-50 text-blue-700">{formatNumber(patternCount, 0)} powder patterns</span> : <span className="pill border-line bg-slate-50 text-slate-600">Structure catalog</span>}
                      {phaseCounts.single_phase ? <span className="pill border-teal-100 bg-teal-50 text-teal-700">{formatNumber(phaseCounts.single_phase, 0)} single</span> : null}
                      {phaseCounts.multi_phase ? <span className="pill border-amber-100 bg-amber-50 text-amber-700">{formatNumber(phaseCounts.multi_phase, 0)} multi</span> : null}
                      {phaseCounts.unknown ? <span className="pill border-slate-200 bg-slate-50 text-slate-600">{formatNumber(phaseCounts.unknown, 0)} unknown</span> : null}
                    </div>
                  </Link>
                );
              })()
            )) : <div className="p-6 text-sm text-slate-500">Loading source catalog…</div>}
          </div>
        </div>
      </section>
    </div>
  );
}
