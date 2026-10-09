import Link from "next/link";
import type { Structure } from "@/lib/types";
import { displaySource, structureTitle } from "@/lib/format";
import { StructureDownloadMenu } from "@/components/resource-downloads";

export function StructureTable({ structures }: { structures: Structure[] }) {
  return (
    <div className="table-scroll panel">
      <table className="scientific-table">
        <thead>
          <tr>
            <th>Structure ID</th>
            <th>Material</th>
            <th>Formula</th>
            <th>Space group</th>
            <th>Cell</th>
            <th>Source</th>
            <th>Download</th>
          </tr>
        </thead>
        <tbody>
          {structures.map((structure) => (
            <tr key={structure.structure_id}>
              <td>
                <Link href={`/structures/${encodeURIComponent(structure.structure_id)}`} className="link-blue text-xs">
                  {structure.structure_id}
                </Link>
                <div className="mt-1 text-xs text-slate-500">
                  {structure.atom_site_count ?? "Unknown"} atom-site rows
                </div>
              </td>
              <td className="font-semibold text-ink">{structureTitle(structure)}</td>
              <td className="text-xs text-slate-600">
                {structure.formula || "Not available"}
              </td>
              <td className="text-xs text-slate-600">
                {structure.space_group.hm || "Unknown"}
                {structure.space_group.number ? ` · #${structure.space_group.number}` : ""}
              </td>
              <td className="text-xs text-slate-600">
                {structure.cell.a && structure.cell.b && structure.cell.c
                  ? `${structure.cell.a} × ${structure.cell.b} × ${structure.cell.c} Å`
                  : "Unknown"}
              </td>
              <td className="whitespace-nowrap text-xs text-slate-600">
                {displaySource(structure.source)}
              </td>
              <td>
                <StructureDownloadMenu structure={structure} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
