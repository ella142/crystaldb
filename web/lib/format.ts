import type { Pattern, Provenance, Structure } from "@/lib/types";

export function displaySource(source?: { code?: string | null; source_id?: string | null } | null): string {
  if (!source?.code) {
    return "Unknown source";
  }
  return source.source_id ? `${source.code} · ${source.source_id}` : source.code;
}

export function labelPhase(value?: string | null): string {
  if (value === "single_phase") return "Single-phase";
  if (value === "multi_phase") return "Multi-phase";
  return "Unknown / unresolved";
}

export function labelLinkage(value?: string | null): string {
  if (value === "complete") return "Record";
  if (value === "partial") return "Partial coverage";
  if (value === "ambiguous") return "Candidate group";
  return "Review / unlinked";
}

export function formatNumber(value?: number | null, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Unknown";
  }
  return value.toLocaleString("en-US", {
    maximumFractionDigits: digits,
  });
}

export function formatList(values?: string[] | null): string {
  return values && values.length ? values.join(", ") : "Not available";
}

export function formatWavelengths(
  values?: Array<number | null | undefined> | null,
  digits = 4,
): string {
  const unique = Array.from(
    new Set(
      (values || []).filter(
        (value): value is number =>
          value !== null && value !== undefined && !Number.isNaN(value),
      ),
    ),
  );
  return unique.length
    ? unique.map((value) => `${formatNumber(value, digits)} Å`).join(" / ")
    : "Unknown";
}

export function formatFraction(value?: number | null, digits = 4): string {
  return value === null || value === undefined ? "Not reported" : formatNumber(value, digits);
}

export function recordCountLabel(count: number, noun = "record"): string {
  return `${count.toLocaleString("en-US")} ${count === 1 ? noun : `${noun}s`} in this view`;
}

export function bestMaterialName(pattern: Pattern): string {
  const first = pattern.phase_components[0];
  return (
    pattern.material_label ||
    first?.name ||
    first?.formula ||
    pattern.sample_id ||
    "Unlabelled material"
  );
}

export function structureTitle(structure: Structure): string {
  return structure.mineral_name || structure.formula || structure.structure_id;
}

export function provenanceRows(provenance?: Provenance | null): Array<[string, string]> {
  const rows: Array<[string, string]> = [
    ["Source", provenance?.source || "Not available"],
    ["Source record", provenance?.source_id || "Not available"],
    ["Label method", provenance?.label_method || "Not available"],
    ["Source file", provenance?.source_file || "Not available"],
  ];
  return rows.filter(([, value]) => value !== "Not available");
}

export function cellVolume(cell: Structure["cell"]): string {
  const values = [cell.a, cell.b, cell.c, cell.alpha, cell.beta, cell.gamma];
  if (values.some((value) => value === null || value === undefined)) {
    return "Unknown";
  }
  const toRadians = (degrees: number) => (degrees * Math.PI) / 180;
  const alpha = toRadians(cell.alpha as number);
  const beta = toRadians(cell.beta as number);
  const gamma = toRadians(cell.gamma as number);
  const metric =
    1 +
    2 * Math.cos(alpha) * Math.cos(beta) * Math.cos(gamma) -
    Math.cos(alpha) ** 2 -
    Math.cos(beta) ** 2 -
    Math.cos(gamma) ** 2;
  if (metric < 0) {
    return "Unknown";
  }
  const volume = (cell.a as number) * (cell.b as number) * (cell.c as number) * Math.sqrt(metric);
  return `${volume.toFixed(2)} Å³`;
}
