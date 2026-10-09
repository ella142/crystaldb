"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getReflectionSets } from "@/lib/api/client";
import type { ReflectionSet } from "@/lib/types";
import { displaySource, formatNumber } from "@/lib/format";
import { ApiUnavailable, EmptyState } from "@/components/empty-state";
import { ReflectionDownloadMenu } from "@/components/resource-downloads";

export function ReflectionSetsView() {
  const [sets, setSets] = useState<ReflectionSet[]>([]);
  const [totalCount, setTotalCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getReflectionSets({ limit: 50 })
      .then((result) => {
        setSets(result.items);
        setTotalCount(result.meta.total_count ?? result.meta.count);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-frame py-12">
      <div className="max-w-3xl">
        <div className="eyebrow">Single-crystal data</div>
        <h1 className="mt-3 page-title">Reflection sets</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">
          HKL reflection data is represented separately from powder XRD patterns and can be linked to a structure record.
        </p>
      </div>
      <div className="mt-10">
        {!loading && !failed && totalCount !== null ? (
          <div className="mb-4 text-xl font-semibold text-ink">
            {formatNumber(totalCount, 0)} single-crystal reflection sets
          </div>
        ) : null}
        {failed ? <ApiUnavailable /> : loading ? <div className="panel p-8 text-sm text-slate-500">Loading reflection sets…</div> : sets.length ? (
          <div className="table-scroll panel">
            <table className="scientific-table">
              <thead><tr><th>Reflection set</th><th>Structure</th><th>Source</th><th>Observed</th><th>Rows</th><th>Download</th></tr></thead>
              <tbody>
                {sets.map((set) => (
                  <tr key={set.reflection_set_id}>
                    <td><div className="text-xs font-semibold text-blue-700">{set.reflection_set_id}</div><div className="mt-1 text-xs text-slate-500">{set.measurement_id || "Measurement not linked"}</div></td>
                    <td>{set.structure_id ? <Link href={`/structures/${encodeURIComponent(set.structure_id)}`} className="link-blue text-xs">{set.structure_id}</Link> : <span className="text-xs text-slate-500">Not linked</span>}</td>
                    <td className="text-xs text-slate-600">{displaySource(set.source)}</td>
                    <td className="text-xs text-slate-600">{set.observed_quantity || "Not available"}</td>
                    <td className="text-xs text-slate-600">{formatNumber(set.reflection_count, 0)}</td>
                    <td><ReflectionDownloadMenu reflectionSet={set} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <EmptyState title="No reflection sets were found." body="The API returned no registered single-crystal reflection resources." />}
      </div>
    </div>
  );
}
