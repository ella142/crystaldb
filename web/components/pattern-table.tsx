import { useEffect, useRef } from "react";
import Link from "next/link";
import type { Pattern } from "@/lib/types";
import {
  bestMaterialName,
  displaySource,
  formatWavelengths,
} from "@/lib/format";
import { PatternDownloadMenu } from "@/components/resource-downloads";
import { LinkageBadge, PhaseBadge } from "@/components/status-badge";

export function PatternTable({
  patterns,
  selectedPatternIds,
  onToggleSelection,
  onToggleAllSelection,
}: {
  patterns: Pattern[];
  selectedPatternIds?: ReadonlySet<string>;
  onToggleSelection?: (patternId: string) => void;
  onToggleAllSelection?: (selectAll: boolean) => void;
}) {
  const selectionEnabled = Boolean(onToggleSelection);
  const selectAllEnabled = Boolean(onToggleAllSelection);
  const allSelected =
    patterns.length > 0 &&
    patterns.every((pattern) => selectedPatternIds?.has(pattern.pattern_id));
  const someSelected =
    !allSelected &&
    patterns.some((pattern) => selectedPatternIds?.has(pattern.pattern_id));
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  return (
    <div className="table-scroll panel">
      <table className="scientific-table">
        <thead>
          <tr>
            <th>
              <input
                ref={selectAllRef}
                type="checkbox"
                checked={allSelected}
                disabled={!selectionEnabled || !selectAllEnabled}
                onChange={() => onToggleAllSelection?.(!allSelected)}
                aria-label={allSelected ? "Clear all selected records" : "Select all records on this page"}
              />
            </th>
            <th>Pattern ID</th>
            <th>Material</th>
            <th>Source</th>
            <th>Phase character</th>
            <th>Wavelength</th>
            <th>Structure linkage</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {patterns.map((pattern) => (
            <tr key={pattern.pattern_id}>
              <td>
                <input
                  type="checkbox"
                  checked={selectedPatternIds?.has(pattern.pattern_id) ?? false}
                  disabled={!selectionEnabled}
                  onChange={() => onToggleSelection?.(pattern.pattern_id)}
                  aria-label={`Select ${pattern.pattern_id}`}
                />
              </td>
              <td>
                <Link
                  href={`/patterns/${encodeURIComponent(pattern.pattern_id)}`}
                  className="link-blue text-xs"
                >
                  {pattern.pattern_id}
                </Link>
                <div className="mt-1 text-xs text-slate-500">
                  {pattern.measurement_id || "Measurement not linked"}
                </div>
              </td>
              <td>
                <div className="font-semibold text-ink">{bestMaterialName(pattern)}</div>
                <div className="mt-1 text-xs text-slate-500">
                  {pattern.sample_id || "Sample not linked"}
                </div>
              </td>
              <td className="whitespace-nowrap text-xs text-slate-600">
                {displaySource(pattern.source)}
              </td>
              <td>
                <PhaseBadge value={pattern.phase_character} />
              </td>
              <td className="whitespace-nowrap text-xs text-slate-600">
                {formatWavelengths(
                  pattern.radiation.wavelengths_angstrom?.length
                    ? pattern.radiation.wavelengths_angstrom
                    : [
                        pattern.radiation.wavelength_angstrom,
                        pattern.radiation.wavelength_kalpha2_angstrom,
                      ],
                )}
              </td>
              <td>
                <LinkageBadge value={pattern.structure_linkage.status} />
                {pattern.structure_linkage.candidate_structure_ids.length ? (
                  <div className="mt-1 text-xs text-slate-500">
                    {pattern.structure_linkage.candidate_structure_ids.length} candidate
                    {pattern.structure_linkage.candidate_structure_ids.length === 1 ? "" : "s"}
                  </div>
                ) : null}
              </td>
              <td>
                <PatternDownloadMenu pattern={pattern} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
