import { apiUrl } from "@/lib/api/client";
import type { BundleResource, DownloadAction } from "@/lib/download-types";
import { createZip } from "@/lib/zip";

export type { BundleAction, DownloadAction } from "@/lib/download-types";

export interface BundleUnavailableFile {
  file: string | null;
  resource: string;
  reason: string;
}

export type BundleManifest = Record<string, unknown> & {
  included_files?: string[];
  unavailable_files?: BundleUnavailableFile[];
};

export type BundleManifestFormat = "json" | "csv";

export interface BundleDownloadOptions {
  manifestFilename?: string;
  manifestFormat?: BundleManifestFormat;
  manifestRows?: BundleManifest[];
}

const manifestCsvColumns = [
  "schema_version",
  "record_type",
  "selected_format",
  "pattern_id",
  "measurement_id",
  "sample_id",
  "source",
  "source_record_id",
  "provenance_source_id",
  "material_label",
  "material_labels",
  "formula_fields",
  "phase_character",
  "dataset_role",
  "data_origin",
  "modality",
  "wavelength_angstrom",
  "structure_resolution_level",
  "structure_linkage",
  "linked_structure_ids",
  "candidate_structure_ids",
  "phase_components",
  "candidate_structure_records",
  "structure_scope",
  "included_files",
  "unavailable_files",
  "provenance",
] as const;

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return /[",\r\n]/.test(text)
    ? `"${text.replace(/"/g, '""')}"`
    : text;
}

export function serializeManifestCsv(rows: BundleManifest[]): Uint8Array {
  const lines = [
    manifestCsvColumns.join(","),
    ...rows.map((row) =>
      manifestCsvColumns
        .map((column) => csvCell(row[column]))
        .join(","),
    ),
  ];
  return new TextEncoder().encode(`${lines.join("\r\n")}\r\n`);
}

export async function fetchResourceBytes(
  url: string,
  label: string,
): Promise<Uint8Array> {
  let response: Response;
  try {
    response = await fetch(apiUrl(url), { cache: "no-store" });
  } catch {
    throw new Error(`${label} failed: the download endpoint is currently unavailable.`);
  }

  if (!response.ok) {
    throw new Error(`${label} failed with HTTP ${response.status}.`);
  }

  const bytes = new Uint8Array(await response.arrayBuffer());
  if (!bytes.length) {
    throw new Error(`${label} returned an empty file.`);
  }
  return bytes;
}

export function downloadBytes(
  bytes: Uint8Array,
  filename: string,
  mimeType = "application/octet-stream",
): void {
  const arrayBuffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(arrayBuffer).set(bytes);
  const blob = new Blob([arrayBuffer], { type: mimeType });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export async function downloadFile(url: string, filename: string): Promise<void> {
  const bytes = await fetchResourceBytes(url, filename);
  downloadBytes(bytes, filename);
}

export async function downloadBundle(
  resources: BundleResource[],
  manifest: BundleManifest,
  filename: string,
  options: BundleDownloadOptions = {},
): Promise<void> {
  const names = new Set<string>();
  for (const resource of resources) {
    if (names.has(resource.name)) {
      throw new Error(`Bundle contains a duplicate filename: ${resource.name}.`);
    }
    names.add(resource.name);
  }

  const manifestFilename = options.manifestFilename || "manifest.json";
  const manifestFormat = options.manifestFormat || "json";
  const unavailableFiles = [...(manifest.unavailable_files || [])];
  const manifestRows: BundleManifest[] = (options.manifestRows || []).map(
    (row) => ({
      ...row,
      included_files: [...(row.included_files || [])],
      unavailable_files: [...(row.unavailable_files || [])],
    }),
  );
  const rowsByRecordId = new Map(
    manifestRows
      .filter((row) => typeof row["pattern_id"] === "string")
      .map((row) => [row["pattern_id"] as string, row]),
  );
  type ResourceResult =
    | { resource: BundleResource; bytes: Uint8Array }
    | { resource: BundleResource; error: string };
  const results: ResourceResult[] = await Promise.all(
    resources.map(async (resource) => {
      try {
        return {
          resource,
          bytes: await fetchResourceBytes(resource.url, resource.label),
        };
      } catch (error) {
        return {
          resource,
          error: error instanceof Error ? error.message : `${resource.label} failed.`,
        };
      }
    }),
  );

  const requiredFailures = results.filter(
    (result): result is { resource: BundleResource; error: string } =>
      "error" in result && result.resource.required !== false,
  );
  if (requiredFailures.length) {
    throw new Error(
      [
        "Bundle creation failed.",
        ...requiredFailures.map(({ error }) => error),
      ].join(" "),
    );
  }

  const entries: Array<{ name: string; bytes: Uint8Array }> = [];
  for (const result of results) {
    if ("error" in result) {
      const unavailableFile = {
        file: result.resource.name,
        resource: result.resource.label,
        reason: result.error,
      };
      unavailableFiles.push(unavailableFile);
      const manifestRow = result.resource.manifestRecordId
        ? rowsByRecordId.get(result.resource.manifestRecordId)
        : undefined;
      manifestRow?.unavailable_files?.push(unavailableFile);
      continue;
    }
    entries.push({ name: result.resource.name, bytes: result.bytes });
    const manifestRow = result.resource.manifestRecordId
      ? rowsByRecordId.get(result.resource.manifestRecordId)
      : undefined;
    if (manifestRow) {
      manifestRow.included_files = [
        ...(manifestRow.included_files || []),
        result.resource.name,
      ];
    }
  }

  const includedFiles = [...entries.map((entry) => entry.name), manifestFilename];
  let manifestBytes: Uint8Array;
  if (manifestFormat === "csv") {
    manifestBytes = serializeManifestCsv(
      manifestRows.length ? manifestRows : [manifest],
    );
  } else {
    manifestBytes = new TextEncoder().encode(
      `${JSON.stringify(
        {
          ...manifest,
          included_files: includedFiles,
          unavailable_files: unavailableFiles,
        },
        null,
        2,
      )}\n`,
    );
  }
  const zipBytes = createZip([
    ...entries,
    { name: manifestFilename, bytes: manifestBytes },
  ]);
  if (!zipBytes.length) {
    throw new Error("Bundle creation produced an empty ZIP.");
  }
  downloadBytes(zipBytes, filename, "application/zip");
}
