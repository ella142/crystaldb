"use client";

import { useRef, useState } from "react";
import { apiUrl, getStructure, withQuery } from "@/lib/api/client";
import type {
  Pattern,
  ReflectionSet,
  Structure,
  StructureResolutionLevel,
} from "@/lib/types";
import {
  makePatternBundleFilename,
  makePatternFilename,
  makePatternSelectionBundleFilename,
  makeReflectionFilename,
  makeStructureFilename,
} from "@/lib/download-filenames";
import { DownloadPopover } from "@/components/download-popover";
import type { BundleAction, BundleResource } from "@/lib/download-types";
import {
  downloadBundle,
  type BundleManifest,
  type BundleUnavailableFile,
} from "@/lib/downloads";

export type PatternBatchDownloadFormat = "txt" | "cif" | "csv" | "data";

interface StructureLoadResult {
  structures: Structure[];
  unavailable: Array<{ structureId: string; reason: string }>;
}

type StructureFetchResult =
  | { structure: Structure }
  | { unavailable: { structureId: string; reason: string } };

function errorReason(error: unknown): string {
  return error instanceof Error ? error.message : "Structure metadata request failed.";
}

async function loadPatternStructures(
  pattern: Pattern,
  structureCache = new Map<string, Promise<StructureFetchResult>>(),
): Promise<StructureLoadResult> {
  const results: StructureFetchResult[] = await Promise.all(
    patternStructureIds(pattern).map(async (structureId) => {
      let request = structureCache.get(structureId);
      if (!request) {
        request = getStructure(structureId)
          .then((structure) => ({ structure }))
          .catch((error) => ({
            unavailable: {
              structureId,
              reason: errorReason(error),
            },
          }));
        structureCache.set(structureId, request);
      }
      return request;
    }),
  );
  return {
    structures: results.flatMap((result) =>
      "structure" in result ? [result.structure] : [],
    ),
    unavailable: results.flatMap((result) =>
      "unavailable" in result ? [result.unavailable] : [],
    ),
  };
}

function uniqueValues(values: Array<string | null | undefined>): string[] {
  return Array.from(
    new Set(values.filter((value): value is string => Boolean(value))),
  );
}

function canonicalStructureResolutionLevel(
  pattern: Pattern,
): StructureResolutionLevel | undefined {
  const candidates = [
    pattern.structure_resolution_level,
    pattern.structure_resolution?.resolution_level,
    pattern.structure_linkage.resolution_level,
  ];
  return candidates.find(
    (value): value is StructureResolutionLevel =>
      value === "record" || value === "group" || value === "review",
  );
}

function structureResolutionLevel(pattern: Pattern): StructureResolutionLevel {
  const canonical = canonicalStructureResolutionLevel(pattern);
  if (canonical) return canonical;

  // Legacy API records expose linkage axes but not the canonical curation level.
  // This compatibility map never uses candidate count to imply a record match.
  switch (pattern.structure_linkage.status) {
    case "complete":
      return "record";
    case "ambiguous":
      return "group";
    default:
      return "review";
  }
}

function patternStructureIds(pattern: Pattern): string[] {
  return uniqueValues([
    ...pattern.structure_linkage.candidate_structure_ids,
    ...pattern.phase_components.flatMap((component) => [
      component.structure.structure_id,
      ...component.structure.structure_ids,
    ]),
  ]);
}

function structureManifestRecord(structure: Structure) {
  return {
    structure_id: structure.structure_id,
    material_label: structure.mineral_name ?? null,
    formula: structure.formula ?? null,
    formula_normalized: structure.formula_normalized ?? null,
    source: structure.source,
    has_cif: Boolean(structure.links.cif),
  };
}

function normalizeExplicitFormula(formula: string): string {
  return formula.replace(/[\s_]/g, "");
}

function makePatternManifest(
  pattern: Pattern,
  structures: Structure[],
  unavailable: Array<{ structureId: string; reason: string }>,
  selectedFormat: PatternBatchDownloadFormat = "data",
): BundleManifest {
  const materialLabels = uniqueValues(
    pattern.phase_components.map((component) => component.name),
  );
  const explicitPhaseFormulas = uniqueValues(
    pattern.phase_components.map((component) => component.formula),
  );
  const normalizedPhaseFormulas = uniqueValues(
    explicitPhaseFormulas.map(normalizeExplicitFormula),
  );
  const linkedStructureIds = uniqueValues([
    ...pattern.phase_components.flatMap((component) => [
      component.structure.structure_id,
      ...component.structure.structure_ids,
    ]),
    ...(pattern.structure_linkage.status === "complete"
      ? pattern.structure_linkage.candidate_structure_ids
      : []),
  ]);
  const unavailableFiles: BundleUnavailableFile[] = unavailable.map((item) => ({
    file: null,
    resource: `structure ${item.structureId}`,
    reason: item.reason,
  }));

  for (const structure of structures) {
    if (!structure.links.cif) {
      unavailableFiles.push({
        file: null,
        resource: `structure ${structure.structure_id}`,
        reason: "No CIF endpoint is registered for this candidate structure.",
      });
    }
  }
  const selectedXYFormats =
    selectedFormat === "data"
      ? (["csv", "txt"] as const)
      : selectedFormat === "csv" || selectedFormat === "txt"
        ? ([selectedFormat] as const)
        : [];
  if (!pattern.links.xy) {
    for (const format of selectedXYFormats) {
      unavailableFiles.push({
        file: makePatternFilename(pattern, format),
        resource: `${pattern.pattern_id} experimental ${format.toUpperCase()}`,
        reason: "No XY endpoint is registered for this pattern.",
      });
    }
  }

  return {
    schema_version: 2,
    record_type: "pattern_bundle",
    pattern_id: pattern.pattern_id,
    measurement_id: pattern.measurement_id ?? null,
    sample_id: pattern.sample_id ?? null,
    source: pattern.source.code,
    source_record_id: pattern.source.source_id ?? null,
    provenance_source_id: pattern.provenance.source_id ?? null,
    material_label: materialLabels.length === 1 ? materialLabels[0] : null,
    material_labels: materialLabels,
    formula_fields: {
      explicit_phase_formulas: explicitPhaseFormulas,
      normalized_phase_formulas: normalizedPhaseFormulas,
      nominal_composition: null,
    },
    metadata_not_provided: ["nominal_composition"],
    phase_character: pattern.phase_character,
    dataset_role: pattern.dataset_role ?? null,
    data_origin: pattern.data_origin,
    modality: pattern.modality,
    wavelength_angstrom: pattern.radiation.wavelength_angstrom ?? null,
    selected_format: selectedFormat,
    structure_resolution_level: structureResolutionLevel(pattern),
    structure_linkage: {
      status: pattern.structure_linkage.status,
      coverage: pattern.structure_linkage.coverage,
      certainty: pattern.structure_linkage.certainty,
    },
    linked_structure_ids: linkedStructureIds,
    candidate_structure_ids: [...pattern.structure_linkage.candidate_structure_ids],
    phase_components: pattern.phase_components,
    candidate_structure_records: structures.map(structureManifestRecord),
    provenance: pattern.provenance,
    structure_scope:
      selectedFormat !== "cif" && selectedFormat !== "data"
        ? "No CIF files were requested for this download selection."
        : pattern.phase_character === "multi_phase"
        ? "Included CIFs are linked or candidate phase structures only; they do not represent the entire mixed-phase measurement."
        : "Included CIFs are the linked or retained candidate structures reported for this pattern.",
    included_files: [],
    unavailable_files: unavailableFiles,
  };
}

function patternResourcesForFormat(
  pattern: Pattern,
  structures: Structure[],
  format: PatternBatchDownloadFormat,
): BundleResource[] {
  const resources: BundleResource[] = [];
  if (pattern.links.xy && (format === "csv" || format === "data")) {
    resources.push(
      {
        name: makePatternFilename(pattern, "csv"),
        label: `${pattern.pattern_id} experimental CSV`,
        url: withQuery(pattern.links.xy, { format: "csv" }),
        required: true,
      },
    );
  }
  if (pattern.links.xy && (format === "txt" || format === "data")) {
    resources.push({
        name: makePatternFilename(pattern, "txt"),
        label: `${pattern.pattern_id} experimental TXT`,
        url: withQuery(pattern.links.xy, { format: "txt" }),
        required: true,
    });
  }

  if (format === "cif" || format === "data") {
    for (const structure of structures) {
      if (!structure.links.cif) continue;
      resources.push({
        name: makeStructureFilename(structure),
        label: `${structure.structure_id} CIF`,
        url: apiUrl(structure.links.cif),
        required: true,
      });
    }
  }
  return resources;
}

function patternActions(pattern: Pattern, structures: Structure[]) {
  const actions = pattern.links.xy
    ? [
        {
          id: `${pattern.pattern_id}-csv`,
          group: "Experimental pattern",
          label: "CSV",
          filename: makePatternFilename(pattern, "csv"),
          url: withQuery(pattern.links.xy, { format: "csv" }),
        },
        {
          id: `${pattern.pattern_id}-txt`,
          group: "Experimental pattern",
          label: "TXT",
          filename: makePatternFilename(pattern, "txt"),
          url: withQuery(pattern.links.xy, { format: "txt" }),
        },
      ]
    : [];

  for (const structure of structures) {
    if (!structure.links.cif) continue;
    actions.push({
      id: `${pattern.pattern_id}-${structure.structure_id}-cif`,
      group:
        pattern.structure_linkage.status === "ambiguous" ||
        patternStructureIds(pattern).length > 1
          ? "Candidate structures"
          : "Linked structure",
      label: "CIF",
      filename: makeStructureFilename(structure),
      url: apiUrl(structure.links.cif),
    });
  }
  return actions;
}

function archiveNameSegment(patternId: string): string {
  const safeName = patternId
    .replace(/[^A-Za-z0-9._-]+/g, "_")
    .replace(/^\.+/, "");
  return safeName || "record";
}

function fileExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot > 0 ? filename.slice(dot) : "";
}

function uniqueFlatFilename(
  preferredName: string,
  patternId: string,
  usedNames: Set<string>,
): string {
  const baseName = preferredName.replace(/^.*[\\/]/, "");
  if (!usedNames.has(baseName)) {
    usedNames.add(baseName);
    return baseName;
  }

  const extension = fileExtension(baseName);
  const stem = extension ? baseName.slice(0, -extension.length) : baseName;
  const prefix = `${archiveNameSegment(patternId)}_`;
  let candidate = `${prefix}${stem}${extension}`;
  let suffix = 2;
  while (usedNames.has(candidate)) {
    candidate = `${prefix}${stem}_${suffix}${extension}`;
    suffix += 1;
  }
  usedNames.add(candidate);
  return candidate;
}

export async function downloadSelectedPatterns(
  patterns: Pattern[],
  format: PatternBatchDownloadFormat,
): Promise<void> {
  if (!patterns.length) {
    throw new Error("Select at least one record before downloading.");
  }

  const structureCache = new Map<string, Promise<StructureFetchResult>>();
  const needsStructures = format === "cif" || format === "data";
  const records = await Promise.all(
    patterns.map(async (pattern) => ({
      pattern,
      result: needsStructures
        ? await loadPatternStructures(pattern, structureCache)
        : { structures: [], unavailable: [] },
    })),
  );

  if (records.length === 1) {
    const { pattern, result } = records[0];
    await downloadBundle(
      patternResourcesForFormat(pattern, result.structures, format),
      makePatternManifest(pattern, result.structures, result.unavailable, format),
      format === "data"
        ? makePatternBundleFilename(pattern)
        : makePatternSelectionBundleFilename(1, format),
    );
    return;
  }

  const resources: BundleResource[] = [];
  const recordManifests: BundleManifest[] = [];
  const unavailableFiles: BundleUnavailableFile[] = [];
  const usedNames = new Set<string>();

  for (const { pattern, result } of records) {
    const sourceResources = patternResourcesForFormat(
      pattern,
      result.structures,
      format,
    );
    const recordManifest = makePatternManifest(
      pattern,
      result.structures,
      result.unavailable,
      format,
    );
    const flatNames = new Map<string, string>();
    const recordResources = sourceResources.map((resource) => {
      const flatName = uniqueFlatFilename(
        resource.name,
        pattern.pattern_id,
        usedNames,
      );
      flatNames.set(resource.name, flatName);
      return {
        ...resource,
        name: flatName,
        label: `${pattern.pattern_id}: ${resource.label}`,
        manifestRecordId: pattern.pattern_id,
      };
    });
    const recordUnavailable = (recordManifest.unavailable_files || []).map(
      (item) => ({
        ...item,
        file: item.file
          ? flatNames.get(item.file) ||
            uniqueFlatFilename(item.file, pattern.pattern_id, usedNames)
          : null,
        resource: `${pattern.pattern_id}: ${item.resource}`,
      }),
    );
    recordManifest.unavailable_files = recordUnavailable;
    recordManifests.push(recordManifest);
    unavailableFiles.push(...recordUnavailable);
    resources.push(...recordResources);
  }

  await downloadBundle(
    resources,
    {
      schema_version: 2,
      record_type: "pattern_selection_bundle",
      selected_pattern_ids: patterns.map((pattern) => pattern.pattern_id),
      selected_format: format,
      included_files: [],
      unavailable_files: unavailableFiles,
    },
    makePatternSelectionBundleFilename(patterns.length, format),
    {
      manifestFilename: "manifest.csv",
      manifestFormat: "csv",
      manifestRows: recordManifests,
    },
  );
}

export function PatternDownloadMenu({ pattern }: { pattern: Pattern }) {
  const [structures, setStructures] = useState<Structure[]>([]);
  const [unavailable, setUnavailable] = useState<
    Array<{ structureId: string; reason: string }>
  >([]);
  const [loadingStructures, setLoadingStructures] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const loadPromiseRef = useRef<Promise<StructureLoadResult> | null>(null);

  async function loadStructures(): Promise<StructureLoadResult> {
    if (loaded) {
      return { structures, unavailable };
    }
    if (loadPromiseRef.current) {
      return loadPromiseRef.current;
    }

    const request = (async () => {
      setLoadingStructures(true);
      try {
        const result = await loadPatternStructures(pattern);
        setStructures(result.structures);
        setUnavailable(result.unavailable);
        setLoaded(true);
        return result;
      } finally {
        setLoadingStructures(false);
      }
    })();
    loadPromiseRef.current = request;
    try {
      return await request;
    } finally {
      loadPromiseRef.current = null;
    }
  }

  const bundle: BundleAction = {
    id: `${pattern.pattern_id}-bundle`,
    label: "Download all (.zip)",
    filename: makePatternBundleFilename(pattern),
    onDownload: async () => {
      const result = await loadStructures();
      await downloadBundle(
        patternResourcesForFormat(pattern, result.structures, "data"),
        makePatternManifest(pattern, result.structures, result.unavailable),
        makePatternBundleFilename(pattern),
      );
    },
  };

  return (
    <DownloadPopover
      actions={patternActions(pattern, structures)}
      bundle={bundle}
      loading={loadingStructures}
      onOpen={loadStructures}
    />
  );
}

export function StructureDownloadMenu({ structure }: { structure: Structure }) {
  const actions = structure.links.cif
    ? [
        {
          id: `${structure.structure_id}-cif`,
          group: "Structure record",
          label: "CIF",
          filename: makeStructureFilename(structure),
          url: apiUrl(structure.links.cif),
        },
      ]
    : [];
  return <DownloadPopover actions={actions} />;
}

export function ReflectionDownloadMenu({ reflectionSet }: { reflectionSet: ReflectionSet }) {
  const [structure, setStructure] = useState<Structure | null>(null);
  const [loadingStructure, setLoadingStructure] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function loadStructure() {
    if (loaded || !reflectionSet.structure_id) return;
    setLoadingStructure(true);
    setStructure(await getStructure(reflectionSet.structure_id).catch(() => null));
    setLoaded(true);
    setLoadingStructure(false);
  }

  const actions = reflectionSet.links.hkl
    ? [
        {
          id: `${reflectionSet.reflection_set_id}-hkl`,
          group: "Reflection data",
          label: "HKL",
          filename: makeReflectionFilename(reflectionSet, structure),
          url: apiUrl(reflectionSet.links.hkl),
        },
      ]
    : [];

  return (
    <DownloadPopover actions={actions} loading={loadingStructure} onOpen={loadStructure} />
  );
}
