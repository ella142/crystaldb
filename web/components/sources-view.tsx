"use client";

import { useEffect, useState } from "react";
import { getSources, getStats } from "@/lib/api/client";
import type { ApiStats, SourceCatalogItem } from "@/lib/types";
import { ApiUnavailable, EmptyState } from "@/components/empty-state";
import { formatNumber } from "@/lib/format";

export function SourcesView() {
  const [sources, setSources] = useState<SourceCatalogItem[]>([]);
  const [stats, setStats] = useState<ApiStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([getSources(), getStats()])
      .then(([sourceResult, statsResult]) => {
        setSources(sourceResult.items);
        setStats(statsResult);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-frame py-12">
      <div className="max-w-3xl">
        <div className="eyebrow">Data provenance</div>
        <h1 className="mt-3 page-title">Sources</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">
          CrystalDB keeps experimental diffraction, structure records and reflection data tied to their
          source identifiers. The catalog below is returned by the live API.
        </p>
      </div>
      <div className="mt-10">
        {failed ? <ApiUnavailable /> : loading ? <div className="panel p-8 text-sm text-slate-500">Loading source catalog…</div> : sources.length ? (
          <div className="grid gap-4 md:grid-cols-2">
            {sources.map((source) => {
              const code = String(source.api_source_code || source.short_name || source.label || "Unknown source");
              const patternCount = stats?.powder_pattern_counts_by_source?.[code.toUpperCase()];
              const phaseCounts = stats?.source_phase_counts?.[code.toUpperCase()] || {};
              return (
                <article key={String(source.source_id || code)} className="panel p-6">
                  <div className="flex items-start justify-between gap-5">
                    <div>
                      <div className="eyebrow">{code}</div>
                      <h2 className="mt-2 text-xl font-semibold text-ink">{String(source.name || source.label || code)}</h2>
                    </div>
                    <span className="pill border-line bg-slate-50 text-slate-600">API catalog</span>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-slate-600">
                    {String(source.description || `${source.source_type || "Source"} · ${source.data_origin || "Data origin not specified"}. The API does not provide a longer description for this entry.`)}
                  </p>
                  {Array.isArray(source.modalities) && source.modalities.length ? (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {source.modalities.map((modality) => <span key={modality} className="pill border-blue-100 bg-blue-50 text-blue-700">{modality.replaceAll("_", " ")}</span>)}
                    </div>
                  ) : null}
                  <div className="mt-5 grid grid-cols-3 gap-2 border-t border-line pt-4">
                    <div>
                      <div className="data-label">Powder</div>
                      <div className="mt-1 text-sm font-semibold text-ink">
                        {patternCount === undefined ? "—" : formatNumber(patternCount, 0)}
                      </div>
                    </div>
                    <div>
                      <div className="data-label">Single</div>
                      <div className="mt-1 text-sm font-semibold text-ink">
                        {phaseCounts.single_phase === undefined ? "—" : formatNumber(phaseCounts.single_phase, 0)}
                      </div>
                    </div>
                    <div>
                      <div className="data-label">Multi</div>
                      <div className="mt-1 text-sm font-semibold text-ink">
                        {phaseCounts.multi_phase === undefined ? "—" : formatNumber(phaseCounts.multi_phase, 0)}
                      </div>
                    </div>
                  </div>
                  <dl className="mt-5 border-t border-line pt-4">
                    <div><dt className="data-label">Source ID</dt><dd className="data-value">{String(source.source_id || "Not available")}</dd></div>
                  </dl>
                </article>
              );
            })}
          </div>
        ) : <EmptyState title="No source catalog entries were returned." body="The API is available, but the source collection is empty." />}
      </div>
    </div>
  );
}
