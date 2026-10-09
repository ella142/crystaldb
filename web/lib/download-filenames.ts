import type { Pattern, ReflectionSet, Structure } from "@/lib/types";

function normalizedSegment(value: string): string {
  return value
    .trim()
    .replace(/[<>:"/\\|?*]/g, "")
    .replace(/\s+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^[.\s_]+|[.\s_]+$/g, "");
}

function joinFilenameParts(
  parts: Array<string | null | undefined>,
  stableId: string,
  extension: string,
): string {
  const id = normalizedSegment(stableId) || "record";
  const prefix = parts
    .map((part) => (part ? normalizedSegment(part) : ""))
    .filter(Boolean)
    .join("_");
  const suffix = `_${id}.${extension}`;
  const maxLength = 180;
  const availablePrefixLength = Math.max(0, maxLength - suffix.length);
  const shortenedPrefix = prefix.slice(0, availablePrefixLength).replace(/[._\s]+$/g, "");
  return `${shortenedPrefix}${suffix}`.replace(/^_+/, "");
}

export function patternMaterialName(pattern: Pattern): string | undefined {
  return pattern.phase_components.find((component) => component.name)?.name || undefined;
}

export function makePatternFilename(
  pattern: Pattern,
  format: "csv" | "txt",
): string {
  return joinFilenameParts(
    [patternMaterialName(pattern)],
    `${pattern.pattern_id}_xy`,
    format,
  );
}

export function makePatternBundleFilename(pattern: Pattern): string {
  return joinFilenameParts(
    [patternMaterialName(pattern)],
    `${pattern.pattern_id}_bundle`,
    "zip",
  );
}

export function makePatternSelectionBundleFilename(
  count: number,
  format: "txt" | "cif" | "csv" | "data" = "data",
): string {
  const suffix = format === "data" ? "bundle" : `${format}_bundle`;
  return `CrystalDB_selected_${count}_records_${suffix}.zip`;
}

export function makeStructureFilename(structure: Structure): string {
  return joinFilenameParts(
    [structure.mineral_name, structure.formula_normalized || structure.formula],
    structure.structure_id,
    "cif",
  );
}

export function makeReflectionFilename(
  reflectionSet: ReflectionSet,
  structure?: Structure | null,
): string {
  return joinFilenameParts(
    [structure?.mineral_name, structure?.formula_normalized || structure?.formula],
    reflectionSet.reflection_set_id,
    "hkl",
  );
}
