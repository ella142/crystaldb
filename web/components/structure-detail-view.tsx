"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getStructure } from "@/lib/api/client";
import type { Structure } from "@/lib/types";
import { cellVolume, displaySource, structureTitle } from "@/lib/format";
import { ApiUnavailable } from "@/components/empty-state";
import { StructureDownloadMenu } from "@/components/resource-downloads";
import { ProvenancePanel } from "@/components/provenance-panel";

export function StructureDetailView() {
  const params = useParams<{ id: string }>();
  const structureId = decodeURIComponent(params.id);
  const [structure, setStructure] = useState<Structure | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getStructure(structureId)
      .then((value) => active && setStructure(value))
      .catch(() => active && setFailed(true))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [structureId]);

  if (loading) return <div className="page-frame py-16"><div className="panel p-8 text-sm text-slate-500">Loading structure record…</div></div>;
  if (failed || !structure) return <div className="page-frame py-16"><ApiUnavailable /></div>;

  return (
    <div className="page-frame py-12">
      <Link href="/structures" className="link-blue text-xs">← Back to structures</Link>
      <div className="mt-6 flex flex-col gap-5 border-b border-line pb-8 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="eyebrow">{displaySource(structure.source)} · structure record</div>
          <h1 className="mt-3 break-words text-3xl font-semibold text-ink sm:text-4xl">{structureTitle(structure)}</h1>
          <p className="mt-3 break-words text-sm text-slate-500">{structure.structure_id}</p>
        </div>
        <StructureDownloadMenu structure={structure} />
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="space-y-8">
          <section className="panel p-5 sm:p-7">
            <div className="eyebrow">Structure summary</div>
            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              <div><div className="data-label">Formula</div><div className="data-value">{structure.formula || "Not available"}</div></div>
              <div><div className="data-label">Normalized formula</div><div className="data-value">{structure.formula_normalized || "Not available"}</div></div>
              <div><div className="data-label">Space group</div><div className="data-value">{structure.space_group.hm || "Unknown"}{structure.space_group.number ? ` · #${structure.space_group.number}` : ""}</div></div>
              <div><div className="data-label">Atom-site rows</div><div className="data-value">{structure.atom_site_count ?? "Unknown"}</div></div>
              <div><div className="data-label">Cell lengths</div><div className="data-value">{structure.cell.a && structure.cell.b && structure.cell.c ? `${structure.cell.a} × ${structure.cell.b} × ${structure.cell.c} Å` : "Unknown"}</div></div>
              <div><div className="data-label">Cell volume estimate</div><div className="data-value">{cellVolume(structure.cell)}</div></div>
            </div>
            <div className="mt-7 border-t border-line pt-5">
              <div className="data-label">Attribution</div>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                This is a {structure.source.code} source record retained by CrystalDB. It is not described as a CrystalDB-authored crystal structure.
              </p>
            </div>
          </section>

          <section className="panel p-5 sm:p-7">
            <div className="eyebrow">Related experimental data</div>
            <h2 className="mt-2 section-title">Pattern linkage</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">Open the API-filtered pattern view to inspect records that reference this structure ID.</p>
            <Link href={`/database?structure_id=${encodeURIComponent(structure.structure_id)}`} className="button-secondary mt-5">Open linked patterns</Link>
          </section>
        </div>
        <aside><ProvenancePanel provenance={structure.provenance} /></aside>
      </div>
    </div>
  );
}
