"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getMeasurement, getPattern, getPatternXY, getSample } from "@/lib/api/client";
import type { Measurement, Pattern, PatternXY, Sample } from "@/lib/types";
import {
  bestMaterialName,
  displaySource,
  formatFraction,
  formatNumber,
  formatWavelengths,
} from "@/lib/format";
import { ApiUnavailable, EmptyState } from "@/components/empty-state";
import { PatternChart } from "@/components/pattern-chart";
import { PhaseBadge, LinkageBadge } from "@/components/status-badge";
import { PatternDownloadMenu } from "@/components/resource-downloads";
import { ProvenancePanel } from "@/components/provenance-panel";
import { LongValue } from "@/components/long-value";

export function PatternDetailView() {
  const params = useParams<{ id: string }>();
  const patternId = decodeURIComponent(params.id);
  const [pattern, setPattern] = useState<Pattern | null>(null);
  const [xy, setXY] = useState<PatternXY | null>(null);
  const [measurement, setMeasurement] = useState<Measurement | null>(null);
  const [sample, setSample] = useState<Sample | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([getPattern(patternId), getPatternXY(patternId).catch(() => null)])
      .then(async ([nextPattern, nextXY]) => {
        if (!active) return;
        setPattern(nextPattern);
        setXY(nextXY);
        const [nextMeasurement, nextSample] = await Promise.all([
          nextPattern.measurement_id ? getMeasurement(nextPattern.measurement_id).catch(() => null) : Promise.resolve(null),
          nextPattern.sample_id ? getSample(nextPattern.sample_id).catch(() => null) : Promise.resolve(null),
        ]);
        if (!active) return;
        setMeasurement(nextMeasurement);
        setSample(nextSample);
      })
      .catch(() => active && setFailed(true))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [patternId]);

  if (loading) {
    return <div className="page-frame py-16"><div className="panel p-8 text-sm text-slate-500">Loading experimental record…</div></div>;
  }
  if (failed || !pattern) {
    return <div className="page-frame py-16"><ApiUnavailable /></div>;
  }

  const conditions = measurement?.conditions;
  const candidateIds = pattern.structure_linkage.candidate_structure_ids;
  const wavelengthValues = [
    ...(conditions?.wavelengths_angstrom || []),
    conditions?.wavelength_angstrom,
    conditions?.wavelength_kalpha2_angstrom,
    ...(pattern.radiation.wavelengths_angstrom || []),
    pattern.radiation.wavelength_angstrom,
    pattern.radiation.wavelength_kalpha2_angstrom,
  ];

  return (
    <div className="page-frame py-12">
      <div className="flex flex-col gap-5 border-b border-line pb-8 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Link href="/database" className="link-blue text-xs">← Back to database</Link>
          <div className="eyebrow mt-6">{pattern.modality} · {pattern.data_origin}</div>
          <h1 className="mt-3 max-w-4xl break-words text-2xl font-semibold text-ink sm:text-4xl">{pattern.pattern_id}</h1>
          <p className="mt-3 text-base text-slate-600">{bestMaterialName(pattern)} · {displaySource(pattern.source)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PhaseBadge value={pattern.phase_character} />
          <LinkageBadge value={pattern.structure_linkage.status} />
          <PatternDownloadMenu pattern={pattern} />
        </div>
      </div>

      <div className="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-8">
          <section className="panel p-5 sm:p-7">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="eyebrow">Experimental diffraction</div>
                <h2 className="mt-2 section-title">Canonical 2θ-intensity profile</h2>
              </div>
              <div className="text-xs text-slate-500">{formatNumber(pattern.scan.point_count, 0)} points · no smoothing or normalization</div>
            </div>
            <div className="mt-5">
              {xy ? <PatternChart x={xy.x.values} y={xy.y.values} /> : <EmptyState title="Experimental XY data is not available." body="This record remains browsable as metadata, but the API did not expose a canonical profile for plotting." />}
            </div>
          </section>

          <section className="panel p-5 sm:p-7">
            <div className="eyebrow">Phase information</div>
            <h2 className="mt-2 section-title">
              {pattern.phase_character === "multi_phase" ? "Multiple components retained" : "Phase characterization"}
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              {pattern.phase_character === "multi_phase"
                ? "This experimental pattern is explicitly multi-phase. Its components are shown descriptively; no single structure is presented as a complete mixture CIF."
                : pattern.phase_character === "single_phase"
                  ? "The source metadata characterizes this record as single-phase. Structure linkage remains a separate evidence field."
                  : "The phase character is not established in the available metadata."}
            </p>
            {pattern.phase_components.length ? (
              <div className="mt-6 divide-y divide-line border-y border-line">
                {pattern.phase_components.map((component, index) => (
                  <div key={`${component.formula || component.name || "phase"}-${index}`} className="grid gap-4 py-4 sm:grid-cols-[1fr_auto]">
                    <div>
                      <div className="font-semibold text-ink">{component.name || component.formula || `Component ${index + 1}`}</div>
                      <div className="mt-1 text-xs text-slate-500">{component.formula || "Formula not available"}</div>
                      {component.role ? <div className="mt-2 text-xs text-slate-500">Role: {component.role}</div> : null}
                    </div>
                    <div className="text-left sm:text-right">
                      <div className="data-label">Fraction</div>
                      <div className="mt-1 text-sm text-ink">{formatFraction(component.fraction.value, 4)}</div>
                      <div className="mt-1 text-xs text-slate-500">{component.fraction.basis || "Basis not available"}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : <div className="mt-5 text-sm text-slate-500">No phase components were returned for this record.</div>}
          </section>

          <section className="panel p-5 sm:p-7">
            <div className="eyebrow">Structure relation</div>
            <h2 className="mt-2 section-title">Interpret linkage with the stored evidence</h2>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <LinkageBadge value={pattern.structure_linkage.status} />
              <span className="text-sm text-slate-600">
                Coverage: <strong className="text-ink">{pattern.structure_linkage.coverage}</strong> · Certainty: <strong className="text-ink">{pattern.structure_linkage.certainty}</strong>
              </span>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">
              {pattern.structure_linkage.status === "ambiguous"
                ? "Multiple candidate structures remain meaningfully retained. CrystalDB does not promote one candidate to a unique answer."
                : pattern.structure_linkage.status === "complete"
                  ? "A retained structure record is linked according to the available source and relation evidence."
                  : "A unique structure assignment is not established for this record."}
            </p>
            {candidateIds.length ? (
              <div className="mt-5 grid gap-2 sm:grid-cols-2">
                {candidateIds.map((structureId) => (
                  <Link key={structureId} href={`/structures/${encodeURIComponent(structureId)}`} className="rounded-md border border-line px-3 py-3 text-xs font-semibold text-blue-700 hover:border-blue-300 hover:bg-blue-50">
                    {structureId} <span aria-hidden="true">→</span>
                  </Link>
                ))}
              </div>
            ) : null}
          </section>
        </div>

        <aside className="space-y-6">
          <section className="panel p-5">
            <div className="eyebrow">Identity</div>
            <dl className="mt-5 space-y-4">
              {[
                ["Measurement ID", pattern.measurement_id],
                ["Sample ID", pattern.sample_id],
                ["Source record", pattern.source.source_id],
                ["Material label", pattern.material_label],
                ["Data role", pattern.dataset_role],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0">
                  <dt className="data-label">{label}</dt>
                  <dd className="data-value">
                    <LongValue value={value} path={typeof label === "string" && label.includes("ID")} />
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="panel p-5">
            <div className="eyebrow">Measurement metadata</div>
            <dl className="mt-5 grid gap-4">
              <div><dt className="data-label">Wavelength(s)</dt><dd className="data-value">{formatWavelengths(wavelengthValues, 6)}</dd></div>
              <div><dt className="data-label">Radiation</dt><dd className="data-value">{conditions?.radiation || "Unknown"}</dd></div>
              <div><dt className="data-label">Anode</dt><dd className="data-value">{conditions?.anode || pattern.radiation.anode || "Unknown"}</dd></div>
              <div><dt className="data-label">Scan range</dt><dd className="data-value">{conditions?.scan_range?.length === 2 ? `${conditions.scan_range[0]} – ${conditions.scan_range[1]}°` : pattern.scan.two_theta_min_deg != null && pattern.scan.two_theta_max_deg != null ? `${pattern.scan.two_theta_min_deg} – ${pattern.scan.two_theta_max_deg}°` : "Unknown"}</dd></div>
              <div><dt className="data-label">Step size</dt><dd className="data-value">{formatNumber(conditions?.step_size, 6)}{conditions?.step_size ? "°" : ""}</dd></div>
              <div><dt className="data-label">Counting time</dt><dd className="data-value">{formatNumber(conditions?.counting_time_seconds, 3)}{conditions?.counting_time_seconds ? " s" : ""}</dd></div>
              <div><dt className="data-label">Sample</dt><dd className="data-value">{sample?.name || sample?.formula || "Not available"}</dd></div>
            </dl>
          </section>

          <ProvenancePanel provenance={pattern.provenance} />
        </aside>
      </div>
    </div>
  );
}
