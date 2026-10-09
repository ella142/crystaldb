import Link from "next/link";
import type { ReflectionSet } from "@/lib/types";
import { displaySource, formatNumber } from "@/lib/format";
import { ReflectionDownloadMenu } from "@/components/resource-downloads";

function reflectionMetadata(reflectionSet: ReflectionSet): string {
  const fields = reflectionSet.available_fields;
  if (!fields.length) return "Metadata not available";
  const preview = fields.slice(0, 3).join(", ");
  const remainder = fields.length - Math.min(fields.length, 3);
  return remainder > 0 ? `${preview} + ${remainder} more` : preview;
}

export function ReflectionTable({
  reflectionSets,
}: {
  reflectionSets: ReflectionSet[];
}) {
  return (
    <div className="table-scroll panel">
      <table className="scientific-table">
        <thead>
          <tr>
            <th>Reflection set ID</th>
            <th>Entity</th>
            <th>Source</th>
            <th>Linked structure</th>
            <th>Observed quantity</th>
            <th>HKL / intensity metadata</th>
            <th>Download</th>
          </tr>
        </thead>
        <tbody>
          {reflectionSets.map((reflectionSet) => (
            <tr key={reflectionSet.reflection_set_id}>
              <td>
                <div className="text-xs font-semibold text-blue-700">
                  {reflectionSet.reflection_set_id}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {reflectionSet.measurement_id || "Measurement not linked"}
                </div>
              </td>
              <td>
                <span className="pill border-blue-100 bg-blue-50 text-blue-700">
                  Single-crystal reflection set
                </span>
              </td>
              <td className="text-xs text-slate-600">
                {displaySource(reflectionSet.source)}
                {reflectionSet.provenance.source_file ? (
                  <div className="mt-1 max-w-44 break-words text-[11px] text-slate-400">
                    {reflectionSet.provenance.source_file}
                  </div>
                ) : null}
              </td>
              <td>
                {reflectionSet.structure_id ? (
                  <Link
                    href={`/structures/${encodeURIComponent(reflectionSet.structure_id)}`}
                    className="link-blue text-xs"
                  >
                    {reflectionSet.structure_id}
                  </Link>
                ) : (
                  <span className="text-xs text-slate-500">Not linked</span>
                )}
              </td>
              <td className="text-xs text-slate-600">
                {reflectionSet.observed_quantity || "Not available"}
              </td>
              <td className="max-w-64 text-xs text-slate-600">
                <div>{formatNumber(reflectionSet.reflection_count, 0)} rows</div>
                <div className="mt-1 break-words text-[11px] text-slate-500">
                  {reflectionMetadata(reflectionSet)}
                </div>
              </td>
              <td>
                <ReflectionDownloadMenu reflectionSet={reflectionSet} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
