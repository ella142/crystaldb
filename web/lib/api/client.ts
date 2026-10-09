import type {
  ApiStats,
  Measurement,
  PaginatedResponse,
  Pattern,
  PatternXY,
  ReflectionSet,
  Sample,
  SearchResponse,
  SourceCatalogItem,
  Structure,
} from "@/lib/types";

export const API_BASE =
  process.env.NEXT_PUBLIC_CRYSTALDB_API_URL || "http://127.0.0.1:8000";

export class ApiClientError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiClientError("CrystalDB API is currently unavailable.");
  }

  if (!response.ok) {
    let message = `CrystalDB API returned HTTP ${response.status}.`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the stable HTTP error message when the body is not JSON.
    }
    throw new ApiClientError(message, response.status);
  }

  return (await response.json()) as T;
}

export interface PatternQuery {
  source?: string;
  modality?: string;
  phase_character?: string;
  component_formula?: string;
  structure_linkage?: string;
  structure_id?: string;
  dataset_role?: string;
  limit?: number;
  cursor?: string;
}

type QueryValue = string | number | undefined;

function queryString<T extends object>(params: T): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as Array<
    [string, QueryValue]
  >) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export function getPatterns(
  params: PatternQuery = {},
): Promise<PaginatedResponse<Pattern>> {
  return requestJson<PaginatedResponse<Pattern>>(
    `/api/v1/patterns${queryString(params)}`,
  );
}

export function getPattern(patternId: string): Promise<Pattern> {
  return requestJson<Pattern>(
    `/api/v1/patterns/${encodeURIComponent(patternId)}`,
  );
}

export function getPatternXY(patternId: string): Promise<PatternXY> {
  return requestJson<PatternXY>(
    `/api/v1/patterns/${encodeURIComponent(patternId)}/xy`,
  );
}

export function getMeasurement(measurementId: string): Promise<Measurement> {
  return requestJson<Measurement>(
    `/api/v1/measurements/${encodeURIComponent(measurementId)}`,
  );
}

export function getSample(sampleId: string): Promise<Sample> {
  return requestJson<Sample>(`/api/v1/samples/${encodeURIComponent(sampleId)}`);
}

export interface StructureQuery {
  source?: string;
  formula?: string;
  limit?: number;
  cursor?: string;
}

export function getStructures(
  params: StructureQuery = {},
): Promise<PaginatedResponse<Structure>> {
  return requestJson<PaginatedResponse<Structure>>(
    `/api/v1/structures${queryString(params)}`,
  );
}

export function getStructure(structureId: string): Promise<Structure> {
  return requestJson<Structure>(
    `/api/v1/structures/${encodeURIComponent(structureId)}`,
  );
}

export function getReflectionSets(
  params: {
    source?: string;
    q?: string;
    structure_id?: string;
    limit?: number;
    cursor?: string;
  } = {},
): Promise<PaginatedResponse<ReflectionSet>> {
  return requestJson<PaginatedResponse<ReflectionSet>>(
    `/api/v1/reflection-sets${queryString(params)}`,
  );
}

export function getStats(): Promise<ApiStats> {
  return requestJson<ApiStats>("/api/v1/stats");
}

export function getSources(): Promise<{ items: SourceCatalogItem[] }> {
  return requestJson<{ items: SourceCatalogItem[] }>("/api/v1/sources");
}

export function getSearch(query: string, limit = 20): Promise<SearchResponse> {
  return requestJson<SearchResponse>(
    `/api/v1/search${queryString({ q: query, limit })}`,
  );
}

export function getReleases(): Promise<{ items: Record<string, unknown>[] }> {
  return requestJson<{ items: Record<string, unknown>[] }>("/api/v1/releases");
}

export function safeRequest<T>(
  request: Promise<T>,
): Promise<T | null> {
  return request.catch(() => null);
}

export function withQuery(url: string, params: Record<string, string>): string {
  const resolved = new URL(apiUrl(url));
  for (const [key, value] of Object.entries(params)) {
    resolved.searchParams.set(key, value);
  }
  return resolved.toString();
}
