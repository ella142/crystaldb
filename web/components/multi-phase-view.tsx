"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPatterns, getStats } from "@/lib/api/client";
import type { ApiStats, Pattern } from "@/lib/types";
import { displaySource, formatFraction, formatNumber } from "@/lib/format";
import { ApiUnavailable, EmptyState } from "@/components/empty-state";
import { PatternDownloadMenu } from "@/components/resource-downloads";
import { LinkageBadge } from "@/components/status-badge";

export function MultiPhaseView() {
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [stats, setStats] = useState<ApiStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([
      getPatterns({ phase_character: "multi_phase", limit: 50 }),
      getStats(),
    ])
      .then(([result, statsResult]) => {
        setPatterns(result.items);
        setStats(statsResult);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-frame py-12">
      <div className="max-w-3xl">
        <div className="eyebrow">Phase complexity</div>
        <h1 className="mt-3 page-title">Multi-phase records</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">
          Mixtures and secondary phases are first-class experimental data. CrystalDB preserves their
          components and does not force a single structure to explain the complete pattern.
        </p>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <div className="quiet-panel p-5">
          <div className="data-label">Interpretation</div>
          <p className="mt-3 text-sm leading-6 text-slate-600">A multi-phase label describes the measured sample, not a unique CIF.</p>
        </div>
        <div className="quiet-panel p-5">
          <div className="data-label">Components</div>
          <p className="mt-3 text-sm leading-6 text-slate-600">Available names, formulas, fractions and roles remain visible per phase.</p>
        </div>
        <div className="quiet-panel p-5">
          <div className="data-label">Linkage</div>
          <p className="mt-3 text-sm leading-6 text-slate-600">Each candidate relation carries its own coverage and certainty state.</p>
        </div>
      </div>

      <div className="mt-10">
        <div className="eyebrow">Browse</div>
        <h2 className="mt-2 section-title">
          {loading
            ? "Loading multi-phase records…"
            : `${formatNumber(stats?.phase_character_counts?.multi_phase ?? patterns.length, 0)} multi-phase records`}
        </h2>
        {!loading && stats?.phase_character_counts?.multi_phase !== undefined ? (
          <p className="mt-2 text-sm text-slate-500">
            Showing the first {formatNumber(patterns.length, 0)} records from the live API.
          </p>
        ) : null}
      </div>

      <div className="mt-5">
        {failed ? <ApiUnavailable /> : loading ? <div className="panel p-8 text-sm text-slate-500">Loading phase metadata…</div> : patterns.length ? (
          <div className="space-y-4">
            {patterns.map((pattern) => (
              <article key={pattern.pattern_id} className="panel p-5 sm:p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <Link href={`/patterns/${encodeURIComponent(pattern.pattern_id)}`} className="link-blue text-xs">{pattern.pattern_id}</Link>
                    <h3 className="mt-2 text-lg font-semibold text-ink">{pattern.phase_components[0]?.name || pattern.phase_components[0]?.formula || "Multi-phase sample"}</h3>
                    <p className="mt-1 text-xs text-slate-500">{displaySource(pattern.source)} · {pattern.sample_id || "Sample not linked"} · {pattern.measurement_id || "Measurement not linked"}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <LinkageBadge value={pattern.structure_linkage.status} />
                    <PatternDownloadMenu pattern={pattern} />
                  </div>
                </div>
                <div className="mt-5 grid gap-4 border-t border-line pt-5 md:grid-cols-2">
                  {pattern.phase_components.map((component, index) => (
                    <div key={`${component.formula || component.name || "component"}-${index}`} className="rounded-md border border-line bg-slate-50 p-4">
                      <div className="data-label">Component {index + 1}</div>
                      <div className="mt-2 font-semibold text-ink">{component.name || component.formula || "Not available"}</div>
                      <div className="mt-1 text-xs text-slate-500">{component.formula || "Formula not available"}</div>
                      <div className="mt-3 text-xs text-slate-600">
                        Fraction: {formatFraction(component.fraction.value, 4)}
                        {" · "}
                        {component.fraction.basis || "basis not available"}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-500">
                  <span>Wavelength: {pattern.radiation.wavelength_angstrom ? `${pattern.radiation.wavelength_angstrom} Å` : "Unknown"}</span>
                  <span>Points: {pattern.scan.point_count ?? "Unknown"}</span>
                  <span>Evidence: {pattern.provenance.evidence || "Not available"}</span>
                </div>
              </article>
            ))}
          </div>
        ) : <EmptyState title="No multi-phase records were found." body="The API returned no records with phase_character=multi_phase." />}
      </div>
    </div>
  );
}
