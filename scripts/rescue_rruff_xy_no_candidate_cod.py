"""Targeted COD rescue audit for the 118 existing no-candidate rows.

This is deliberately separate from the historical RRUFF recovery workflows.
It reads the fixed 118-row input, queries COD name metadata, filters by the
available RRUFF chemistry and complete cell, and downloads only retained COD
CIFs that are missing from the existing local index.
"""

from __future__ import annotations

import csv
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crystaldb.matching.cell_compare import compare_cells  # noqa: E402
from crystaldb.matching.chemistry import compare_chemistry, extract_elements  # noqa: E402


INPUT_CSV = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_xy_not_in_dif_experimental_cod_candidates.csv"
)
COD_INDEX = PROJECT_ROOT / "data" / "mappings" / "cif_index.json"
OUTPUT_CSV = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_xy_not_in_dif_cod_rescue_candidates.csv"
)
OUTPUT_MD = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_xy_not_in_dif_cod_rescue_candidates.md"
)
STAGING_ROOT = (
    PROJECT_ROOT
    / "data"
    / "staging"
    / "rruff_xy_not_in_dif_cod_rescue_v1"
)
QUERY_CACHE = STAGING_ROOT / "cod_name_query_metadata.json"
SHORTLIST_MANIFEST = STAGING_ROOT / "shortlist_cod_ids.json"
CIF_ROOT = STAGING_ROOT / "cif"

MONGO_URI = "mongodb://127.0.0.1:27017"
DATABASE_NAME = "rruff"
COD_SEARCH_URL = "https://www.crystallography.net/cod/result"
COD_CIF_URL = "https://www.crystallography.net/cod/{cod_id}.cif"

CELL_LENGTH_TOLERANCE = 0.05
CELL_ANGLE_TOLERANCE = 2.0
REQUIRED_CELL_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")
CELL_KEY_RE = re.compile(
    r"\b(?P<key>a|b|c|alpha|beta|gamma)\s*[:=]\s*"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+))",
    re.IGNORECASE,
)

CSV_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "mineral",
    "rruff_chemistry",
    "rruff_cell",
    "query_status",
    "query_result_count",
    "candidate_cod_ids",
    "candidate_details",
    "candidate_count",
    "final_status",
    "downloaded_missing_cif_count",
    "reason",
]


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def normalize_name(value: Any) -> str:
    return "".join(char for char in str(value or "").casefold() if char.isalnum())


def as_float(value: Any) -> float | None:
    if value in (None, "", ".", "?"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_rruff_cell(value: Any) -> dict[str, float] | None:
    if not value:
        return None
    parsed = {
        match.group("key").casefold(): float(match.group("value"))
        for match in CELL_KEY_RE.finditer(str(value))
    }
    if not all(key in parsed for key in REQUIRED_CELL_KEYS):
        return None
    return parsed


def complete_cell(value: Any) -> bool:
    return isinstance(value, dict) and all(
        as_float(value.get(key)) is not None for key in REQUIRED_CELL_KEYS
    )


def read_input_rows() -> list[dict[str, str]]:
    with INPUT_CSV.open(encoding="utf-8-sig", newline="") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row.get("evidence_level") == "no_candidate"
        ]
    keys = [row.get("filename_sample_id") for row in rows]
    if len(rows) != 118 or len(set(keys)) != 118:
        raise RuntimeError(
            f"Expected 118 unique no_candidate rows, found {len(rows)} rows and "
            f"{len(set(keys))} unique filename_sample_id values"
        )
    return rows


def load_metadata(database, rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    keys = [row["filename_sample_id"] for row in rows]
    records: dict[str, dict[str, Any]] = {}
    projection = {
        "_id": 0,
        "sample_id": 1,
        "filename_sample_id": 1,
        "mineral": 1,
        "metadata": 1,
    }
    query = {"filename_sample_id": {"$in": keys}}
    for collection_name in ("xy_raw", "xy_processed"):
        for document in database[collection_name].find(query, projection):
            key = document.get("filename_sample_id")
            if key:
                records.setdefault(key, {})[collection_name] = document

    missing = [key for key in keys if key not in records]
    if missing:
        raise RuntimeError(f"Missing XY metadata for {missing[:10]}")
    return records


def preferred_document(bundle: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return bundle.get("xy_raw") or bundle.get("xy_processed") or {}


def source_fields(document: dict[str, Any]) -> tuple[str, str | None, dict[str, float] | None]:
    metadata = document.get("metadata") or {}
    mineral = str(document.get("mineral") or metadata.get("NAMES") or "").strip()
    formula = str(metadata.get("IDEAL CHEMISTRY") or "").strip() or None
    cell = parse_rruff_cell(metadata.get("CELL PARAMETERS"))
    return mineral, formula, cell


def extract_query_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("results", "records", "data", "entries"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get("file") or payload.get("cod_id"):
            return [payload]
    return []


def candidate_id(record: dict[str, Any]) -> str | None:
    value = record.get("file") or record.get("cod_id") or record.get("id")
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return match.group(0) if match else None


def candidate_formula(record: dict[str, Any]) -> str | None:
    for key in ("formula", "chemical_formula_sum", "chemformula"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return None


def candidate_cell(record: dict[str, Any]) -> dict[str, float | None]:
    return {key: as_float(record.get(key)) for key in REQUIRED_CELL_KEYS}


def chemistry_relation(source_formula: str | None, candidate: dict[str, Any]) -> str:
    if not source_formula:
        return "missing_source_formula"
    formula = candidate_formula(candidate)
    if not formula:
        return "candidate_formula_missing"

    comparison = compare_chemistry(source_formula, formula)
    if comparison.get("compatible") is True:
        return "compatible"

    source_elements = set(comparison.get("elements_a") or extract_elements(source_formula))
    candidate_elements = set(comparison.get("elements_b") or extract_elements(formula))
    if not source_elements or not candidate_elements:
        return "unresolved_formula"
    if source_elements & candidate_elements:
        return "solid_solution_or_ratio_variant"
    return "hard_incompatible_element_set"


def name_support(source_name: str, candidate: dict[str, Any]) -> str | None:
    source_norm = normalize_name(source_name)
    values = [
        candidate.get("mineral"),
        candidate.get("commonname"),
    ]
    for value in values:
        value_norm = normalize_name(value)
        if value_norm and value_norm == source_norm:
            return "query_hit_exact_metadata_name"
    return None


def cell_matches(source_cell: dict[str, float], candidate: dict[str, Any]) -> bool:
    candidate_values = candidate_cell(candidate)
    if not complete_cell(candidate_values):
        return False
    comparison = compare_cells(source_cell, candidate_values)
    return (
        comparison["max_length_relative_difference"] is not None
        and comparison["max_angle_difference"] is not None
        and comparison["max_length_relative_difference"] <= CELL_LENGTH_TOLERANCE
        and comparison["max_angle_difference"] <= CELL_ANGLE_TOLERANCE
    )


def load_query_cache() -> dict[str, dict[str, Any]]:
    if not QUERY_CACHE.exists():
        return {}
    payload = json.loads(QUERY_CACHE.read_text(encoding="utf-8"))
    return {
        item["normalized_name"]: item
        for item in payload.get("queries", [])
        if item.get("normalized_name")
    }


def write_query_cache(cache: dict[str, dict[str, Any]]) -> None:
    QUERY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": COD_SEARCH_URL,
        "format": "json",
        "queries": [cache[key] for key in sorted(cache)],
    }
    QUERY_CACHE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def query_cod_name(
    session: requests.Session,
    mineral: str,
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    normalized_name = normalize_name(mineral)
    if normalized_name in cache:
        return cache[normalized_name]
    item: dict[str, Any] = {
        "normalized_name": normalized_name,
        "query_text": mineral,
        "url": None,
        "status": "error",
        "records": [],
        "error": None,
    }
    if not normalized_name:
        item["status"] = "missing_name"
        cache[normalized_name] = item
        return item

    last_error = None
    for attempt in range(1, 4):
        try:
            response = session.get(
                COD_SEARCH_URL,
                params={"text": mineral, "format": "json"},
                timeout=(10, 60),
            )
            item["url"] = response.url
            response.raise_for_status()
            item["records"] = extract_query_records(response.json())
            item["status"] = "ok"
            break
        except (requests.RequestException, ValueError) as exc:
            last_error = repr(exc)
            if attempt < 3:
                time.sleep(2 ** (attempt - 1))
    if item["status"] != "ok":
        item["error"] = last_error
    cache[normalized_name] = item
    return item


def local_file_exists(record: dict[str, Any]) -> bool:
    file_path = record.get("file_path")
    if not file_path:
        return False
    path = Path(str(file_path))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.exists()


def download_shortlist_cifs(
    session: requests.Session,
    candidate_ids: list[str],
    local_index: dict[str, dict[str, Any]],
) -> dict[str, str]:
    CIF_ROOT.mkdir(parents=True, exist_ok=True)
    statuses: dict[str, str] = {}
    for cod_id in sorted(set(candidate_ids)):
        if local_file_exists(local_index.get(cod_id, {})):
            statuses[cod_id] = "already_local"
            continue
        destination = CIF_ROOT / f"{cod_id}.cif"
        if destination.exists() and destination.stat().st_size > 0:
            statuses[cod_id] = "already_staged"
            continue
        try:
            time.sleep(0.2)
            response = session.get(COD_CIF_URL.format(cod_id=cod_id), timeout=(10, 60))
            response.raise_for_status()
            if not response.content.strip():
                statuses[cod_id] = "empty_response"
                continue
            destination.write_bytes(response.content)
            statuses[cod_id] = "downloaded_missing"
        except requests.RequestException as exc:
            statuses[cod_id] = f"download_error:{exc.__class__.__name__}"
    return statuses


def build_rows(
    database,
    input_rows: list[dict[str, str]],
    local_index_rows: list[dict[str, Any]],
    download: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    metadata = load_metadata(database, input_rows)
    local_index = {
        str(item.get("source_id")): item
        for item in local_index_rows
        if item.get("source") == "COD" and item.get("source_id")
    }
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "crystaldb/rruff-cod-rescue-audit"})
    query_cache = load_query_cache()
    unique_names = sorted(
        {
            source_fields(preferred_document(metadata[row["filename_sample_id"]]))[0]
            for row in input_rows
        },
        key=lambda value: (normalize_name(value), value),
    )
    for index, mineral in enumerate(unique_names, start=1):
        query_cod_name(session, mineral, query_cache)
        write_query_cache(query_cache)
        print(f"[COD query {index}/{len(unique_names)}] {mineral}", flush=True)

    shortlist_ids: list[str] = []
    output_rows: list[dict[str, Any]] = []
    for input_row in input_rows:
        key = input_row["filename_sample_id"]
        mineral, source_formula, source_cell = source_fields(
            preferred_document(metadata[key])
        )
        query = query_cache.get(normalize_name(mineral), {})
        all_records = query.get("records", []) if query.get("status") == "ok" else []
        records_by_id: dict[str, dict[str, Any]] = {}
        for record in all_records:
            cod_id = candidate_id(record)
            if cod_id:
                records_by_id.setdefault(cod_id, record)

        retained: list[dict[str, Any]] = []
        rejection_counts: defaultdict[str, int] = defaultdict(int)
        for cod_id, record in records_by_id.items():
            support = name_support(mineral, record)
            if support is None:
                rejection_counts["name_metadata_mismatch"] += 1
                continue
            relation = chemistry_relation(source_formula, record)
            if relation == "hard_incompatible_element_set":
                rejection_counts[relation] += 1
                continue
            if source_cell is not None and not cell_matches(source_cell, record):
                rejection_counts["cell_mismatch_or_missing"] += 1
                continue
            record = dict(record)
            record["_cod_id"] = cod_id
            record["_name_support"] = support
            record["_chemistry_status"] = relation
            record["_cell_status"] = (
                "match" if source_cell is not None else "not_available"
            )
            retained.append(record)

        retained.sort(key=lambda item: item["_cod_id"])
        candidate_ids = [item["_cod_id"] for item in retained]
        shortlist_ids.extend(candidate_ids)
        details = [
            {
                "cod_id": item["_cod_id"],
                "name_support": item["_name_support"],
                "formula": candidate_formula(item),
                "chemistry_status": item["_chemistry_status"],
                "cell_status": item["_cell_status"],
                "cell": candidate_cell(item),
                "space_group_ignored": True,
            }
            for item in retained
        ]

        if not candidate_ids:
            final_status = "still_no_candidate"
        elif len(candidate_ids) >= 2:
            final_status = "multiple_valid_candidates"
        elif source_cell is not None and details[0]["chemistry_status"] in {
            "compatible",
            "solid_solution_or_ratio_variant",
        }:
            final_status = "single_strong_candidate"
        else:
            final_status = "weak_candidate"

        reason_parts = []
        if query.get("status") != "ok":
            reason_parts.append(query.get("status") or "query_failed")
        elif not all_records:
            reason_parts.append("COD name query returned no records")
        if rejection_counts:
            reason_parts.append(
                "filtered=" + json_text(dict(sorted(rejection_counts.items())))
            )
        if source_cell is None:
            reason_parts.append("RRUFF complete cell unavailable")
        if source_formula is None:
            reason_parts.append("RRUFF chemistry unavailable; missing chemistry did not exclude candidates")
        if len(candidate_ids) >= 2:
            reason_parts.append("multiple reasonable candidates retained; none selected")
        if not reason_parts:
            reason_parts.append("retained after targeted name, chemistry, and cell rules")

        output_rows.append(
            {
                "sample_id": input_row["sample_id"],
                "filename_sample_id": key,
                "mineral": mineral,
                "rruff_chemistry": source_formula or "",
                "rruff_cell": json_text(source_cell) if source_cell else "",
                "query_status": query.get("status", "missing_query"),
                "query_result_count": len(all_records),
                "candidate_cod_ids": json_text(candidate_ids),
                "candidate_details": json_text(details),
                "candidate_count": len(candidate_ids),
                "final_status": final_status,
                "downloaded_missing_cif_count": 0,
                "reason": "; ".join(reason_parts),
            }
        )

    write_query_cache(query_cache)
    SHORTLIST_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    SHORTLIST_MANIFEST.write_text(
        json.dumps(
            {
                "candidate_count": len(set(shortlist_ids)),
                "candidate_cod_ids": sorted(set(shortlist_ids)),
                "download_policy": "only shortlist IDs missing from existing local index",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )
    download_statuses = (
        download_shortlist_cifs(session, shortlist_ids, local_index)
        if download
        else {cod_id: "plan_only" for cod_id in set(shortlist_ids)}
    )
    for row in output_rows:
        ids = json.loads(row["candidate_cod_ids"])
        row["downloaded_missing_cif_count"] = sum(
            download_statuses.get(cod_id) == "downloaded_missing" for cod_id in ids
        )
    return output_rows, query_cache, download_statuses


def write_outputs(
    rows: list[dict[str, Any]],
    query_cache: dict[str, dict[str, Any]],
    download_statuses: dict[str, str],
) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["filename_sample_id"]))

    counts = defaultdict(int)
    for row in rows:
        counts[row["final_status"]] += 1
    candidate_found = len(rows) - counts["still_no_candidate"]
    downloaded = sum(status == "downloaded_missing" for status in download_statuses.values())
    md_lines = [
        "# RRUFF outside-DIF COD rescue audit",
        "",
        "This artifact processes only the 118 rows already classified as `no_candidate` in the existing local-index result.",
        "It does not modify MongoDB, the 807 dataset, 304 rescue/review outputs, v2/v3, or formal CrystalDB data.",
        "",
        "## Summary",
        "",
        f"118 total = {len(rows)}",
        f"candidate_found = {candidate_found}",
        f"single_strong_candidate = {counts['single_strong_candidate']}",
        f"multiple_valid_candidates = {counts['multiple_valid_candidates']}",
        f"weak_candidate = {counts['weak_candidate']}",
        f"still_no_candidate = {counts['still_no_candidate']}",
        "",
        "## Rules",
        "",
        "- COD was queried by each distinct RRUFF mineral name using the COD JSON metadata endpoint; retained records also require an exact normalized match in COD `mineral` or `commonname` metadata.",
        "- The RRUFF formula was used when present; missing formula did not exclude a candidate.",
        "- Completely disjoint element sets were rejected. Overlapping-element ratio differences and solid-solution notation were retained.",
        "- Complete RRUFF cells were compared directly on a,b,c,alpha,beta,gamma using 5% length and 2 degree angle tolerances.",
        "- RRUFF space group was not required or inferred; COD space group was ignored for sample classification.",
        "- Multiple retained COD IDs are all listed; no candidate was selected.",
        f"- Only final-shortlist COD IDs missing from the local index were downloaded: {downloaded} CIF files.",
        "",
        "## Artifacts",
        "",
        f"- Detail CSV: `{OUTPUT_CSV}`",
        f"- Query metadata cache: `{QUERY_CACHE}`",
        f"- Missing shortlist CIF staging directory: `{CIF_ROOT}`",
        "",
    ]
    OUTPUT_MD.write_text("\n".join(md_lines), encoding="utf-8", newline="\n")
    print(f"118 total = {len(rows)}")
    print(f"candidate_found = {candidate_found}")
    print(f"single_strong_candidate = {counts['single_strong_candidate']}")
    print(f"multiple_valid_candidates = {counts['multiple_valid_candidates']}")
    print(f"weak_candidate = {counts['weak_candidate']}")
    print(f"still_no_candidate = {counts['still_no_candidate']}")
    print(f"downloaded_missing_cifs = {downloaded}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"MD: {OUTPUT_MD}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Filter and write the shortlist without downloading CIF files.",
    )
    args = parser.parse_args()
    input_rows = read_input_rows()
    local_index_rows = json.loads(COD_INDEX.read_text(encoding="utf-8"))
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        rows, query_cache, download_statuses = build_rows(
            client[DATABASE_NAME],
            input_rows,
            local_index_rows,
            download=not args.plan_only,
        )
        write_outputs(rows, query_cache, download_statuses)
    finally:
        client.close()


if __name__ == "__main__":
    main()
