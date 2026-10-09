"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import {
  getPatterns,
  getReflectionSets,
  getSearch,
  getSources,
} from "@/lib/api/client";
import type { Pattern, ReflectionSet } from "@/lib/types";
import { looksLikeFormula } from "@/lib/formula";
import { recordCountLabel } from "@/lib/format";
import { SearchBox } from "@/components/search-box";
import { PatternTable } from "@/components/pattern-table";
import { ReflectionTable } from "@/components/reflection-table";
import { ApiUnavailable, EmptyState } from "@/components/empty-state";
import {
  downloadSelectedPatterns,
  type PatternBatchDownloadFormat,
} from "@/components/resource-downloads";
import { useRouter } from "next/navigation";

const filters = [
  { key: "source", label: "Source", options: [] as string[] },
  { key: "modality", label: "Modality", options: ["powder_xrd", "single_crystal_xrd"] },
  { key: "phase_character", label: "Phase character", options: ["single_phase", "multi_phase", "unknown"] },
  { key: "structure_linkage", label: "Structure linkage", options: ["complete", "partial", "ambiguous", "unlinked"] },
  { key: "dataset_role", label: "Dataset role", options: ["raw", "canonical", "single_phase_precursor", "precursor_mixture_benchmark"] },
];

const fallbackSourceOptions = ["COD", "DARA", "LAB", "OPXRD", "POWBASE", "RRUFF"];

const pageSizeOptions = [10, 25, 50, 100];
const defaultPageSize = 25;
const batchDownloadOptions: Array<{
  format: PatternBatchDownloadFormat;
  label: string;
}> = [
  { format: "txt", label: "All TXT" },
  { format: "cif", label: "All CIF" },
  { format: "csv", label: "All CSV" },
  { format: "data", label: "Download data (.zip)" },
];

type PageItem = number | "ellipsis";

function parsePageSize(value: string | null): number {
  const parsed = Number(value);
  return pageSizeOptions.includes(parsed) ? parsed : defaultPageSize;
}

function parsePage(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function getPageItems(totalPages: number, currentPage: number): PageItem[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const items: PageItem[] = [1];
  if (currentPage > 3) {
    items.push("ellipsis");
  }

  const start = Math.max(2, currentPage - 1);
  const end = Math.min(totalPages - 1, currentPage + 1);
  for (let page = start; page <= end; page += 1) {
    items.push(page);
  }

  if (currentPage < totalPages - 2) {
    items.push("ellipsis");
  }
  items.push(totalPages);
  return items;
}

export function DatabaseView() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const searchTerm = searchParams.get("q") || "";
  const paramsKey = searchParams.toString();
  const pageSize = parsePageSize(searchParams.get("limit"));
  const currentPage = parsePage(searchParams.get("page"));
  const cursorParam = searchParams.get("cursor") || undefined;
  const reflectionMode =
    searchParams.get("modality") === "single_crystal_xrd";
  const structureSearch = /^STR_[A-Za-z0-9_-]+$/i.test(searchTerm.trim());
  const formulaSearch =
    !structureSearch && looksLikeFormula(searchTerm.trim());
  const cursorPaginationEnabled =
    reflectionMode || !searchTerm || structureSearch || formulaSearch;
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [reflectionSets, setReflectionSets] = useState<ReflectionSet[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [pageCursors, setPageCursors] = useState<Record<number, string | null>>({
    1: null,
  });
  const [resolvingPage, setResolvingPage] = useState<number | null>(null);
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [bulkDownloadOpen, setBulkDownloadOpen] = useState(false);
  const [bulkDownloadError, setBulkDownloadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [selectedPatternIds, setSelectedPatternIds] = useState<Set<string>>(
    new Set(),
  );
  const [componentFormulaInput, setComponentFormulaInput] = useState("");
  const [structureIdInput, setStructureIdInput] = useState("");
  const [sourceOptions, setSourceOptions] = useState(fallbackSourceOptions);

  const currentFilters = useMemo(
    () => ({
      source: searchParams.get("source") || "",
      modality: searchParams.get("modality") || "",
      phase_character: searchParams.get("phase_character") || "",
      structure_linkage: searchParams.get("structure_linkage") || "",
      dataset_role: searchParams.get("dataset_role") || "",
      component_formula: searchParams.get("component_formula") || "",
      structure_id: searchParams.get("structure_id") || "",
    }),
    [paramsKey],
  );

  const browseKey = useMemo(() => {
    const next = new URLSearchParams(searchParams.toString());
    next.delete("cursor");
    next.delete("page");
    return next.toString();
  }, [paramsKey]);

  const patternQueryBase = useMemo(
    () => {
      if (structureSearch) {
        return { structure_id: searchTerm.trim(), limit: pageSize };
      }
      if (formulaSearch) {
        return {
          ...currentFilters,
          component_formula: searchTerm.trim(),
          limit: pageSize,
        };
      }
      return { ...currentFilters, limit: pageSize };
    },
    [currentFilters, formulaSearch, pageSize, searchTerm, structureSearch],
  );

  const previousBrowseKey = useRef(browseKey);
  const bulkMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (previousBrowseKey.current === browseKey) return;
    previousBrowseKey.current = browseKey;
    setPageCursors({ 1: null });
    setTotalCount(0);
  }, [browseKey]);

  useEffect(() => {
    setComponentFormulaInput(currentFilters.component_formula);
    setStructureIdInput(currentFilters.structure_id);
  }, [currentFilters.component_formula, currentFilters.structure_id]);

  useEffect(() => {
    getSources()
      .then((result) => {
        const codes = result.items
          .map((source) => source.api_source_code)
          .filter((code): code is string => Boolean(code))
          .map((code) => code.toUpperCase())
          .sort();
        if (codes.length) setSourceOptions(codes);
      })
      .catch(() => {
        // Keep the production source fallback available if the catalog request fails.
      });
  }, []);

  useEffect(() => {
    if (!bulkDownloadOpen) return;
    const handlePointerDown = (event: PointerEvent) => {
      if (!bulkMenuRef.current?.contains(event.target as Node)) {
        setBulkDownloadOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setBulkDownloadOpen(false);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [bulkDownloadOpen]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFailed(false);

    const applyMeta = (meta: {
      count: number;
      total_count?: number | null;
      next_cursor?: string | null;
    }) => {
      if (!active) return;
      setNextCursor(meta.next_cursor || null);
      setTotalCount(meta.total_count ?? meta.count);
      if (cursorPaginationEnabled) {
        setPageCursors((current) => ({
          ...current,
          [currentPage + 1]: meta.next_cursor || null,
        }));
      }
      setSelectedPatternIds(new Set());
    };

    if (reflectionMode) {
      getReflectionSets({
        source: currentFilters.source || undefined,
        q: searchTerm || undefined,
        structure_id: currentFilters.structure_id || undefined,
        limit: pageSize,
        cursor: cursorParam,
      })
        .then((result) => {
          if (!active) return;
          setReflectionSets(result.items);
          setPatterns([]);
          applyMeta(result.meta);
        })
        .catch(() => active && setFailed(true))
        .finally(() => active && setLoading(false));
    } else {
      const request = cursorPaginationEnabled
        ? getPatterns({
            ...patternQueryBase,
            cursor: cursorParam,
          })
        : getSearch(searchTerm, pageSize).then((result) => ({
            items: result.patterns,
            meta: {
              count: result.patterns.length,
              total_count: result.patterns.length,
              next_cursor: null,
            },
          }));

      request
        .then((result) => {
          if (!active) return;
          setPatterns(result.items);
          setReflectionSets([]);
          applyMeta(result.meta);
        })
        .catch(() => active && setFailed(true))
        .finally(() => active && setLoading(false));
    }
    return () => {
      active = false;
    };
  }, [
    browseKey,
    currentFilters,
    currentPage,
    cursorPaginationEnabled,
    cursorParam,
    formulaSearch,
    pageSize,
    patternQueryBase,
    reflectionMode,
    searchTerm,
    structureSearch,
  ]);

  const buildHref = (key: string, value: string, clearSearch = false) => {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    if (key === "modality" && value === "single_crystal_xrd") {
      next.delete("phase_character");
      next.delete("structure_linkage");
      next.delete("dataset_role");
      next.delete("component_formula");
    }
    if (clearSearch) next.delete("q");
    next.delete("cursor");
    next.delete("page");
    return `/database${next.toString() ? `?${next.toString()}` : ""}`;
  };

  const submitTextFilter = (
    event: FormEvent<HTMLFormElement>,
    key: "component_formula" | "structure_id",
  ) => {
    event.preventDefault();
    const value =
      key === "component_formula" ? componentFormulaInput : structureIdInput;
    router.push(buildHref(key, value.trim(), true));
  };

  const buildPageHref = (page: number, cursor?: string | null) => {
    const next = new URLSearchParams(searchParams.toString());
    if (page <= 1) {
      next.delete("page");
      next.delete("cursor");
    } else {
      next.set("page", String(page));
      if (cursor) next.set("cursor", cursor);
      else next.delete("cursor");
    }
    return `/database${next.toString() ? `?${next.toString()}` : ""}`;
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const pageItems = getPageItems(totalPages, currentPage);

  const goToPage = async (targetPage: number) => {
    if (
      !cursorPaginationEnabled ||
      targetPage < 1 ||
      targetPage > totalPages ||
      targetPage === currentPage ||
      resolvingPage !== null
    ) {
      return;
    }

    if (targetPage === 1) {
      router.push(buildPageHref(1));
      return;
    }

    setResolvingPage(targetPage);
    const knownCursors = { ...pageCursors };
    let cursor: string | undefined = knownCursors[1] || undefined;

    try {
      for (let page = 1; page < targetPage; page += 1) {
        const knownNextCursor = knownCursors[page + 1];
        if (knownNextCursor !== undefined) {
          if (!knownNextCursor) break;
          cursor = knownNextCursor;
          continue;
        }

        const result = reflectionMode
          ? await getReflectionSets({
              source: currentFilters.source || undefined,
              q: searchTerm || undefined,
              structure_id: currentFilters.structure_id || undefined,
              limit: pageSize,
              cursor,
            })
          : await getPatterns({
              ...patternQueryBase,
              cursor,
            });
        const next = result.meta.next_cursor || null;
        knownCursors[page + 1] = next;
        if (!next) break;
        cursor = next;
      }

      setPageCursors(knownCursors);
      const targetCursor = knownCursors[targetPage];
      if (targetCursor) {
        router.push(buildPageHref(targetPage, targetCursor));
      }
    } catch {
      setFailed(true);
    } finally {
      setResolvingPage(null);
    }
  };

  const handleDownloadSelected = async (
    format: PatternBatchDownloadFormat,
  ) => {
    if (!selectedPatternIds.size || bulkDownloading) return;
    const selectedPatterns = patterns.filter((pattern) =>
      selectedPatternIds.has(pattern.pattern_id),
    );
    setBulkDownloading(true);
    setBulkDownloadOpen(false);
    setBulkDownloadError(null);
    try {
      await downloadSelectedPatterns(selectedPatterns, format);
    } catch (error) {
      setBulkDownloadError(
        error instanceof Error ? error.message : "Selected records download failed.",
      );
    } finally {
      setBulkDownloading(false);
    }
  };

  const hasRecords = reflectionMode
    ? reflectionSets.length > 0
    : patterns.length > 0;

  return (
    <div className="page-frame py-12">
      <div className="max-w-3xl">
        <div className="eyebrow">Database browser</div>
        <h1 className="mt-3 page-title">Experimental records</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">
          Search and filter metadata records without loading scientific arrays into the browse view.
        </p>
      </div>

      <div className="mt-8 grid items-start gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="panel p-5 lg:sticky lg:top-24">
          <div className="eyebrow">Search & filters</div>
          <div className="mt-4">
            <SearchBox
              compact
              initialValue={searchTerm || currentFilters.structure_id}
              baseParams={{
                modality: currentFilters.modality,
                source: currentFilters.source,
              }}
            />
          </div>
          <div className="mt-5 grid gap-4">
            {filters
              .filter(
                (filter) =>
                  !reflectionMode ||
                  filter.key === "source" ||
                  filter.key === "modality",
              )
              .map((filter) => (
              <label key={filter.key} className="block">
                <span className="data-label">{filter.label}</span>
                <select
                  value={currentFilters[filter.key as keyof typeof currentFilters]}
                  onChange={(event) => {
                    router.push(buildHref(filter.key, event.target.value));
                  }}
                  className="mt-2 h-10 w-full border border-line bg-white px-3 text-sm text-ink"
                >
                  <option value="">All</option>
                  {(filter.key === "source" ? sourceOptions : filter.options).map((option) => (
                    <option key={option} value={option}>{option.replaceAll("_", " ")}</option>
                  ))}
                </select>
              </label>
            ))}
            {!reflectionMode ? (
              <div className="block">
                <span className="data-label">Component formula</span>
                <form
                  className="mt-2 flex gap-2"
                  onSubmit={(event) => submitTextFilter(event, "component_formula")}
                >
                  <input
                    value={componentFormulaInput}
                    onChange={(event) => setComponentFormulaInput(event.target.value)}
                    placeholder="e.g. TiO2"
                    aria-label="Component formula"
                    className="h-10 min-w-0 flex-1 border border-line bg-white px-3 text-sm text-ink placeholder:text-slate-400"
                  />
                  <button type="submit" className="button-secondary h-10 shrink-0 px-3 text-xs">
                    Search
                  </button>
                </form>
              </div>
            ) : null}
            <div className="block">
              <span className="data-label">Structure ID</span>
              <form
                className="mt-2 flex gap-2"
                onSubmit={(event) => submitTextFilter(event, "structure_id")}
              >
                <input
                  value={structureIdInput}
                  onChange={(event) => setStructureIdInput(event.target.value)}
                  placeholder="e.g. STR_COD_9000253"
                  aria-label="Structure ID"
                  className="h-10 min-w-0 flex-1 border border-line bg-white px-3 text-sm text-ink placeholder:text-slate-400"
                />
                <button type="submit" className="button-secondary h-10 shrink-0 px-3 text-xs">
                  Search
                </button>
              </form>
            </div>
          </div>
        </aside>

        <main className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="eyebrow">Results</div>
              {!loading && !failed ? (
                <div className="mt-2 text-xl font-semibold text-ink">
                  {recordCountLabel(
                    totalCount,
                    reflectionMode ? "reflection set" : "pattern",
                  )}
                </div>
              ) : null}
            </div>
            {searchTerm ? (
              <div className="text-sm text-slate-500">
                Search: <span className="font-semibold text-ink">{searchTerm}</span>
              </div>
            ) : null}
          </div>

          <div className="mt-4">
        {failed ? (
          <ApiUnavailable />
        ) : loading ? (
          <div className="panel p-8 text-sm text-slate-500">
            Loading metadata from the CrystalDB API…
          </div>
        ) : reflectionMode ? (
          hasRecords ? (
            <ReflectionTable reflectionSets={reflectionSets} />
          ) : (
            <EmptyState
              title="No matching reflection sets were found."
              body="Try another source, structure ID, or identifier. Reflection sets remain separate from powder XRD patterns."
            />
          )
        ) : patterns.length ? (
          <>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-white px-3 py-2">
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">
                  {selectedPatternIds.size} selected
                </span>
                {bulkDownloadError ? (
                  <span role="alert" className="text-xs text-red-700">
                    {bulkDownloadError}
                  </span>
                ) : null}
              </div>
              <div ref={bulkMenuRef} className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={bulkDownloadOpen}
                  disabled={!selectedPatternIds.size || bulkDownloading}
                  onClick={() => {
                    setBulkDownloadError(null);
                    setBulkDownloadOpen((open) => !open);
                  }}
                  className="button-secondary px-3 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {bulkDownloading ? "Preparing ZIP…" : "Download selected"}
                </button>
                {bulkDownloadOpen ? (
                  <div
                    role="menu"
                    aria-label="Selected download formats"
                    className="absolute right-0 z-20 mt-2 w-64 rounded-lg border border-line bg-white p-2 shadow-panel"
                  >
                    <div className="border-b border-line px-2 pb-2 text-xs leading-5 text-slate-500">
                      {selectedPatternIds.size} record
                      {selectedPatternIds.size === 1 ? "" : "s"} · ZIP +
                      {selectedPatternIds.size === 1
                        ? " manifest.json"
                        : " manifest.csv"}
                    </div>
                    <div className="mt-1">
                      {batchDownloadOptions.map((option) => (
                        <button
                          key={option.format}
                          type="button"
                          role="menuitem"
                          onClick={() => void handleDownloadSelected(option.format)}
                          className="block w-full rounded-md px-2 py-2 text-left text-sm text-ink hover:bg-blue-50"
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
            <PatternTable
              patterns={patterns}
              selectedPatternIds={selectedPatternIds}
              onToggleSelection={(patternId) => {
                setSelectedPatternIds((current) => {
                  const next = new Set(current);
                  if (next.has(patternId)) next.delete(patternId);
                  else next.add(patternId);
                  return next;
                });
              }}
              onToggleAllSelection={(selectAll) => {
                setSelectedPatternIds((current) => {
                  if (!selectAll) return new Set();
                  return new Set(patterns.map((pattern) => pattern.pattern_id));
                });
              }}
            />
          </>
        ) : (
          <EmptyState
            title="No matching records were found."
            body={
              currentFilters.component_formula || formulaSearch
                ? "Check the stoichiometry and try the stored formula form, such as Ag2S or Ag_2_S. Formula order and element counts are not changed automatically."
                : "Try a broader identifier, remove a filter, or inspect the multi-phase and structures sections directly."
            }
          />
        )}
          </div>

          {!loading && !failed && hasRecords && cursorPaginationEnabled ? (
        <div className="mt-5 flex flex-col gap-4 border-t border-line pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <label className="flex items-center gap-2">
              <span>Records per page</span>
              <select
                value={pageSize}
                onChange={(event) => {
                  router.push(buildHref("limit", event.target.value));
                }}
                className="h-9 rounded-md border border-line bg-white px-2 text-sm text-ink"
              >
                {pageSizeOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <nav
            aria-label="Database pages"
            className="flex flex-wrap items-center gap-1.5"
          >
            <button
              type="button"
              aria-label="Previous page"
              disabled={currentPage <= 1 || resolvingPage !== null}
              onClick={() => void goToPage(currentPage - 1)}
              className="inline-flex h-9 min-w-9 items-center justify-center rounded-md border border-line bg-white px-2 text-sm text-ink transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              <span aria-hidden="true">←</span>
            </button>
            {pageItems.map((item, index) =>
              item === "ellipsis" ? (
                <span
                  key={`ellipsis-${index}`}
                  aria-hidden="true"
                  className="px-1 text-slate-400"
                >
                  …
                </span>
              ) : (
                <button
                  key={item}
                  type="button"
                  aria-current={item === currentPage ? "page" : undefined}
                  disabled={resolvingPage !== null}
                  onClick={() => void goToPage(item)}
                  className={`inline-flex h-9 min-w-9 items-center justify-center rounded-md border px-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
                    item === currentPage
                      ? "border-accent bg-accent text-white"
                      : "border-line bg-white text-ink hover:border-accent hover:text-accent"
                  }`}
                >
                  {item}
                </button>
              ),
            )}
            <button
              type="button"
              aria-label="Next page"
              disabled={
                currentPage >= totalPages ||
                !nextCursor ||
                resolvingPage !== null
              }
              onClick={() => void goToPage(currentPage + 1)}
              className="inline-flex h-9 min-w-9 items-center justify-center rounded-md border border-line bg-white px-2 text-sm text-ink transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              <span aria-hidden="true">→</span>
            </button>
          </nav>
        </div>
      ) : null}
        </main>
      </div>
    </div>
  );
}
