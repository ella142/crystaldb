"""Find local COD CIF candidates for the 177 confirmed experimental XY rows.

The input population is fixed by the existing RRUFF outside-DIF audit. This
script reads only those RRUFF measurements, reads the existing local COD CIF
index, and writes audit artifacts. It does not write MongoDB or run the old
RRUFF/DIF candidate pipeline.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crystaldb.matching.chemistry import compare_chemistry  # noqa: E402
from crystaldb.matching.cell_compare import compare_cells  # noqa: E402


AUDIT_INPUT = PROJECT_ROOT / "data" / "mappings" / "rruff_xy_not_in_dif_audit.csv"
COD_INDEX = PROJECT_ROOT / "data" / "mappings" / "cif_index.json"
CSV_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_xy_not_in_dif_experimental_cod_candidates.csv"
)
MD_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_xy_not_in_dif_experimental_cod_candidates.md"
)

MONGO_URI = "mongodb://127.0.0.1:27017"
DATABASE_NAME = "rruff"

CELL_LENGTH_TOLERANCE = 0.05
CELL_ANGLE_TOLERANCE = 2.0
REQUIRED_CELL_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")
CELL_VALUE_RE = re.compile(
    r"\b(a|b|c|alpha|beta|gamma)\s*:\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))",
    re.IGNORECASE,
)

CSV_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "candidate_cod_ids",
    "name_support",
    "chemistry_status",
    "cell_status",
    "candidate_count",
    "evidence_level",
    "reason",
]


def normalize_name(value: Any) -> str:
    return "".join(char for char in str(value or "").casefold() if char.isalnum())


def parse_rruff_cell(value: Any) -> dict[str, float] | None:
    if not value:
        return None
    parsed = {
        key.casefold(): float(number)
        for key, number in CELL_VALUE_RE.findall(str(value))
    }
    if not all(key in parsed for key in REQUIRED_CELL_KEYS):
        return None
    return parsed


def has_complete_cif_cell(value: Any) -> bool:
    return isinstance(value, dict) and all(
        value.get(key) is not None for key in REQUIRED_CELL_KEYS
    )


def read_audit_rows() -> list[dict[str, str]]:
    with AUDIT_INPUT.open(encoding="utf-8", newline="") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row.get("profile_origin") == "experimental"
        ]
    if len(rows) != 177:
        raise RuntimeError(f"Expected 177 experimental audit rows, found {len(rows)}")
    return rows


def load_rruff_metadata(database, rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
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
            records.setdefault(document["filename_sample_id"], {})[
                collection_name
            ] = document

    missing = [key for key in keys if key not in records]
    if missing:
        raise RuntimeError(f"Missing source XY metadata for {missing[:10]}")
    return records


def preferred_document(bundle: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return bundle.get("xy_raw") or bundle.get("xy_processed") or {}


def source_fields(document: dict[str, Any]) -> tuple[str, str | None, dict[str, float] | None]:
    metadata = document.get("metadata") or {}
    return (
        str(document.get("mineral") or metadata.get("NAMES") or "").strip(),
        str(metadata.get("IDEAL CHEMISTRY") or "").strip() or None,
        parse_rruff_cell(metadata.get("CELL PARAMETERS")),
    )


def chemistry_relation(
    source_formula: str | None,
    candidate_formula: Any,
) -> str:
    if not source_formula:
        return "missing"
    if not str(candidate_formula or "").strip():
        return "candidate_formula_missing"

    comparison = compare_chemistry(source_formula, candidate_formula)
    compatible = comparison.get("compatible")
    if compatible is True:
        return "compatible"
    if compatible is None:
        return "unresolved_complex_formula"

    source_elements = set(comparison.get("elements_a") or [])
    candidate_elements = set(comparison.get("elements_b") or [])
    if source_elements & candidate_elements:
        return "solid_solution_or_ratio_variant"
    return "hard_incompatible_element_set"


def cell_matches(source_cell: dict[str, float], candidate_cell: Any) -> bool:
    if not has_complete_cif_cell(candidate_cell):
        return False
    comparison = compare_cells(source_cell, candidate_cell)
    max_length_difference = comparison.get("max_length_relative_difference")
    max_angle_difference = comparison.get("max_angle_difference")
    return (
        max_length_difference is not None
        and max_angle_difference is not None
        and max_length_difference <= CELL_LENGTH_TOLERANCE
        and max_angle_difference <= CELL_ANGLE_TOLERANCE
    )


def aggregate_chemistry_status(
    source_formula: str | None,
    relations: list[str],
    candidate_count: int,
) -> str:
    if not source_formula:
        return "missing"
    if not candidate_count:
        return "not_evaluated_no_candidate"
    relation_set = set(relations)
    if "hard_incompatible_element_set" in relation_set:
        return "hard_incompatible_element_set"
    if "compatible" in relation_set and len(relation_set) > 1:
        return "compatible_plus_variant_or_uncertain"
    if "compatible" in relation_set:
        return "compatible"
    if "solid_solution_or_ratio_variant" in relation_set:
        return "solid_solution_or_ratio_possible"
    return "unresolved"


def build_rows(
    database,
    audit_rows: list[dict[str, str]],
    cif_index: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metadata_by_key = load_rruff_metadata(database, audit_rows)
    candidates_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in cif_index:
        if (
            candidate.get("source") == "COD"
            and candidate.get("parse_status") == "ok"
            and candidate.get("source_id")
        ):
            candidates_by_name[normalize_name(candidate.get("mineral_name"))].append(
                candidate
            )

    output_rows = []
    for audit_row in audit_rows:
        key = audit_row["filename_sample_id"]
        name, source_formula, source_cell = source_fields(
            preferred_document(metadata_by_key[key])
        )
        name_candidates = candidates_by_name.get(normalize_name(name), [])
        relations_by_id = {
            str(candidate["source_id"]): chemistry_relation(
                source_formula, candidate.get("formula")
            )
            for candidate in name_candidates
        }

        chemistry_allowed = {
            candidate_id
            for candidate_id, relation in relations_by_id.items()
            if relation != "hard_incompatible_element_set"
        }

        if source_cell is None:
            retained = [
                candidate
                for candidate in name_candidates
                if str(candidate["source_id"]) in chemistry_allowed
            ]
            cell_status = "not_available"
        else:
            retained = [
                candidate
                for candidate in name_candidates
                if str(candidate["source_id"]) in chemistry_allowed
                and cell_matches(source_cell, candidate.get("cell_parameters"))
            ]
            if not name_candidates:
                cell_status = "no_name_candidate"
            elif retained:
                cell_status = "match"
            else:
                cell_status = "no_match"

        retained.sort(key=lambda candidate: str(candidate["source_id"]))
        candidate_ids = [str(candidate["source_id"]) for candidate in retained]
        relations = [relations_by_id[candidate_id] for candidate_id in candidate_ids]
        chemistry_status = aggregate_chemistry_status(
            source_formula, relations, len(candidate_ids)
        )

        name_support = bool(name_candidates)
        if candidate_ids and source_cell is not None:
            evidence_level = "strong_candidate"
            reason_parts = [
                "normalized mineral name matched",
                "complete source cell matched candidate cell",
            ]
        elif candidate_ids:
            evidence_level = "weak_evidence"
            reason_parts = [
                "normalized mineral name matched",
                "source cell unavailable; name and chemistry only",
            ]
        else:
            evidence_level = "no_candidate"
            if not name_candidates:
                reason_parts = [
                    "no parsed local COD CIF with a normalized mineral-name match"
                ]
            elif source_cell is not None:
                reason_parts = [
                    "name candidates found, but none passed the complete-cell filter"
                ]
            else:
                reason_parts = [
                    "name candidates were removed by chemistry element-set filtering"
                ]

        if len(candidate_ids) > 1:
            reason_parts.append("multiple candidates retained; none selected")
        if source_formula is None:
            reason_parts.append("RRUFF chemistry missing")
        elif chemistry_status != "compatible":
            reason_parts.append(f"chemistry={chemistry_status}")

        output_rows.append(
            {
                "sample_id": audit_row["sample_id"],
                "filename_sample_id": key,
                "candidate_cod_ids": json.dumps(candidate_ids, separators=(",", ":")),
                "name_support": name_support,
                "chemistry_status": chemistry_status,
                "cell_status": cell_status,
                "candidate_count": len(candidate_ids),
                "evidence_level": evidence_level,
                "reason": "; ".join(reason_parts),
            }
        )

    return sorted(output_rows, key=lambda row: row["filename_sample_id"])


def write_outputs(rows: list[dict[str, Any]]) -> None:
    CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "177 total": len(rows),
        "with_cell": sum(row["cell_status"] != "not_available" for row in rows),
        "without_cell": sum(row["cell_status"] == "not_available" for row in rows),
        "strong_candidate": sum(
            row["evidence_level"] == "strong_candidate" for row in rows
        ),
        "multiple_candidates": sum(row["candidate_count"] > 1 for row in rows),
        "weak_evidence": sum(row["evidence_level"] == "weak_evidence" for row in rows),
        "no_candidate": sum(row["evidence_level"] == "no_candidate" for row in rows),
    }

    markdown_lines = [
        "# RRUFF Outside-DIF Experimental COD Candidate Audit",
        "",
        "This audit processes only the 177 rows already classified as `experimental` in `rruff_xy_not_in_dif_audit.csv`.",
        "No RRUFF collection, curated dataset, v2/v3 output, or formal CrystalDB data was modified.",
        "",
        "## Summary",
        "",
        f"177 total = {summary['177 total']}",
        f"with_cell = {summary['with_cell']}",
        f"without_cell = {summary['without_cell']}",
        f"strong_candidate = {summary['strong_candidate']}",
        f"multiple_candidates = {summary['multiple_candidates']}",
        f"weak_evidence = {summary['weak_evidence']}",
        f"no_candidate = {summary['no_candidate']}",
        "",
        "## Rules",
        "",
        "- Name support uses the RRUFF `mineral` value and normalized exact matching against parsed COD `_chemical_name_mineral`.",
        "- RRUFF chemistry uses `metadata[\"IDEAL CHEMISTRY\"]` when present; missing chemistry does not exclude a name candidate.",
        "- Complete source cells use `metadata[\"CELL PARAMETERS\"]` with `a,b,c,alpha,beta,gamma`; candidates require all six CIF cell values and pass 5% length / 2 degree angle thresholds.",
        "- No RRUFF space group is required or inferred. Candidate space groups are not used to populate RRUFF fields.",
        "- Chemistry only rejects a candidate when the parsed element sets are completely disjoint. Complex formulas and overlapping-element ratio differences are retained as unresolved or solid-solution/ratio possibilities.",
        "- Multiple retained COD IDs are listed together in the CSV; no candidate is selected.",
        "- Candidate source is the existing parsed local COD index `data/mappings/cif_index.json`; no remote retrieval or old pipeline rerun was performed.",
        "",
        "## Output",
        "",
        f"- Detail CSV: `{CSV_OUTPUT}`",
        f"- Candidate IDs in `candidate_cod_ids` are JSON arrays.",
        "",
    ]
    MD_OUTPUT.write_text("\n".join(markdown_lines), encoding="utf-8", newline="\n")

    for key, value in summary.items():
        print(f"{key} = {value}")
    print("CSV:", CSV_OUTPUT)
    print("MD:", MD_OUTPUT)


def main() -> None:
    audit_rows = read_audit_rows()
    cif_index = json.loads(COD_INDEX.read_text(encoding="utf-8"))
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        rows = build_rows(client[DATABASE_NAME], audit_rows, cif_index)
        write_outputs(rows)
    finally:
        client.close()


if __name__ == "__main__":
    main()
