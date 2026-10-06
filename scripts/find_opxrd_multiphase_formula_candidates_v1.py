from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_DATABASE = "opxrd"
SOURCE_COLLECTION = "patterns"
CANDIDATE_COLLECTION = "multiphase_formula_candidates_v1"
REVIEW_CSV = PROJECT_ROOT / "data" / "mappings" / "opxrd_multiphase_review_v1.csv"
DRY_RUN_REPORT = PROJECT_ROOT / "reports" / "opxrd_multiphase_dry_run_v1.json"
FINAL_REPORT = PROJECT_ROOT / "reports" / "opxrd_multiphase_formula_candidates_v1.json"

PLACEHOLDER_TOKENS = {"", "nan", "null", "none", "n/a", "na"}
AMBIGUOUS_FORMULA_RE = re.compile(r"[+/;]")
WHITESPACE_RE = re.compile(r"\s+")

SCAN_PROJECTION = {
    "_id": 1,
    "source": 1,
    "dataset": 1,
    "record_key": 1,
    "source_provider": 1,
    "pattern_name": 1,
    "phase_count": 1,
    "is_mixed_phase": 1,
    "phase_chemical_compositions": 1,
    "label.phases.chemical_composition": 1,
    "label.phases.phase_fraction": 1,
    "label.phases.spacegroup": 1,
    "label.phases.lattice": 1,
    "metadata.institution": 1,
    "metadata.original_file_format": 1,
    "import_meta.relative_path": 1,
}

SOURCE_PHASE_PROJECTION = {
    "_id": 1,
    "label.phases": 1,
    "phase_chemical_compositions": 1,
}


def normalize_formula(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = WHITESPACE_RE.sub(" ", value.strip())
    if normalized.lower() in PLACEHOLDER_TOKENS:
        return None
    return normalized or None


def phase_entries_from_doc(doc: dict[str, Any]) -> list[dict[str, Any]]:
    label = doc.get("label")
    if not isinstance(label, dict):
        return []
    phases = label.get("phases")
    if not isinstance(phases, list):
        return []
    return [phase for phase in phases if isinstance(phase, dict)]


def top_compositions_from_doc(doc: dict[str, Any]) -> list[Any]:
    compositions = doc.get("phase_chemical_compositions")
    return compositions if isinstance(compositions, list) else []


def has_phase_metadata(doc: dict[str, Any]) -> bool:
    label = doc.get("label")
    if isinstance(label, dict) and "phases" in label:
        return True
    if "phase_count" in doc or "is_mixed_phase" in doc:
        return True
    return bool(top_compositions_from_doc(doc))


def source_record_id(doc: dict[str, Any]) -> str:
    record_key = doc.get("record_key")
    if record_key not in (None, ""):
        return str(record_key)
    import_meta = doc.get("import_meta")
    if isinstance(import_meta, dict) and import_meta.get("relative_path"):
        return str(import_meta["relative_path"])
    return str(doc["_id"])


def extract_formula_entries(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Any]]:
    phases = phase_entries_from_doc(doc)
    entries: list[dict[str, Any]] = []
    raw_values: list[Any] = []

    if phases:
        for phase_index, phase in enumerate(phases):
            raw = phase.get("chemical_composition")
            raw_values.append(raw)
            normalized = normalize_formula(raw)
            if normalized is not None:
                entries.append(
                    {
                        "phase_index": phase_index,
                        "field": f"label.phases[{phase_index}].chemical_composition",
                        "formula_raw": raw,
                        "formula_normalized": normalized,
                    }
                )
        return entries, raw_values

    # This is only a fallback for records that have no label.phases container.
    # It is kept explicit so the evidence still identifies the source field.
    for phase_index, raw in enumerate(top_compositions_from_doc(doc)):
        raw_values.append(raw)
        normalized = normalize_formula(raw)
        if normalized is not None:
            entries.append(
                {
                    "phase_index": phase_index,
                    "field": f"phase_chemical_compositions[{phase_index}]",
                    "formula_raw": raw,
                    "formula_normalized": normalized,
                }
            )
    return entries, raw_values


def phase_summary(doc: dict[str, Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for phase_index, phase in enumerate(phase_entries_from_doc(doc)):
        summary.append(
            {
                "phase_index": phase_index,
                "chemical_composition": phase.get("chemical_composition"),
                "phase_fraction": phase.get("phase_fraction"),
                "spacegroup": phase.get("spacegroup"),
            }
        )
    if summary:
        return summary
    return [
        {
            "phase_index": phase_index,
            "chemical_composition": value,
        }
        for phase_index, value in enumerate(top_compositions_from_doc(doc))
    ]


def classify_record(doc: dict[str, Any]) -> dict[str, Any]:
    entries, raw_values = extract_formula_entries(doc)
    formulas = [entry["formula_normalized"] for entry in entries]
    distinct_formulas = list(dict.fromkeys(formulas))
    phase_entries = phase_entries_from_doc(doc)
    phase_count = doc.get("phase_count")
    structural_phase_count = phase_count if isinstance(phase_count, int) else len(phase_entries)
    has_structural_multiple_phases = structural_phase_count >= 2 or len(phase_entries) >= 2
    invalid_non_string_values = [
        value
        for value in raw_values
        if value is not None
        and not isinstance(value, str)
    ]
    ambiguous_formula_values = [
        entry["formula_raw"]
        for entry in entries
        if isinstance(entry["formula_raw"], str)
        and AMBIGUOUS_FORMULA_RE.search(entry["formula_raw"])
    ]

    if ambiguous_formula_values or invalid_non_string_values:
        status = "needs_review"
        if ambiguous_formula_values:
            review_reason = "formula_string_may_contain_multiple_formulas"
        else:
            review_reason = "non_string_formula_value"
    elif len(distinct_formulas) >= 2:
        status = "confirmed_multiple_formulas"
        review_reason = None
    elif len(entries) == 0 and has_structural_multiple_phases:
        status = "needs_review"
        review_reason = "multiple_phase_metadata_without_explicit_formula"
    else:
        status = "not_multiple_formulas"
        review_reason = None

    missing_or_placeholder_slots = sum(
        value is None
        or (isinstance(value, str) and value.strip().lower() in PLACEHOLDER_TOKENS)
        for value in raw_values
    )

    return {
        "status": status,
        "review_reason": review_reason,
        "entries": entries,
        "raw_values": raw_values,
        "formulas": formulas,
        "distinct_formulas": distinct_formulas,
        "phase_entry_count": len(phase_entries),
        "has_phase_metadata": has_phase_metadata(doc),
        "has_structural_multiple_phases": has_structural_multiple_phases,
        "missing_or_placeholder_slots": missing_or_placeholder_slots,
        "ambiguous_formula_values": ambiguous_formula_values,
        "invalid_non_string_values": invalid_non_string_values,
    }


def compact_record_summary(doc: dict[str, Any]) -> dict[str, Any]:
    metadata = doc.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    import_meta = doc.get("import_meta")
    import_meta = import_meta if isinstance(import_meta, dict) else {}
    return {
        "source": doc.get("source"),
        "dataset": doc.get("dataset"),
        "record_key": source_record_id(doc),
        "source_provider": doc.get("source_provider"),
        "pattern_name": doc.get("pattern_name"),
        "phase_count": doc.get("phase_count"),
        "is_mixed_phase": doc.get("is_mixed_phase"),
        "metadata": {
            "institution": metadata.get("institution"),
            "original_file_format": metadata.get("original_file_format"),
        },
        "import_meta": {
            "relative_path": import_meta.get("relative_path"),
        },
    }


def sample_view(doc: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": str(doc["_id"]),
        "source_record_id": source_record_id(doc),
        "phase": phase_summary(doc),
        "formulas": analysis["formulas"],
        "distinct_count": len(analysis["distinct_formulas"]),
        "classification_status": analysis["status"],
        "review_reason": analysis["review_reason"],
    }


def json_default(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value)!r}")


def write_review_csv(records: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "_id",
        "source_record_id",
        "source_provider",
        "phase_count",
        "phase_entry_count",
        "phase_summary",
        "formulas",
        "distinct_formula_count",
        "classification_status",
        "review_reason",
    ]
    with REVIEW_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for doc, analysis in records:
            writer.writerow(
                {
                    "_id": str(doc["_id"]),
                    "source_record_id": source_record_id(doc),
                    "source_provider": doc.get("source_provider"),
                    "phase_count": doc.get("phase_count"),
                    "phase_entry_count": analysis["phase_entry_count"],
                    "phase_summary": json.dumps(
                        phase_summary(doc),
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                    "formulas": json.dumps(
                        analysis["formulas"],
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                    "distinct_formula_count": len(analysis["distinct_formulas"]),
                    "classification_status": analysis["status"],
                    "review_reason": analysis["review_reason"] or "",
                }
            )


def build_candidate_doc(
    source_doc: dict[str, Any],
    source_phase_doc: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    phase_entries = phase_entries_from_doc(source_phase_doc)
    formula_evidence = [
        {
            "phase_index": entry["phase_index"],
            "field": entry["field"],
            "formula_raw": entry["formula_raw"],
            "formula_normalized": entry["formula_normalized"],
        }
        for entry in analysis["entries"]
    ]
    source_summary = compact_record_summary(source_doc)
    source_summary.pop("source", None)
    return {
        "_id": source_doc["_id"],
        "source_collection": SOURCE_COLLECTION,
        "source_record_id": source_record_id(source_doc),
        "source": "opxrd",
        "phase_detection": {
            "method": "explicit_multiple_phase_formulas",
            "formula_count": len(analysis["entries"]),
            "distinct_formula_count": len(analysis["distinct_formulas"]),
            "formulas": analysis["formulas"],
            "formula_evidence": formula_evidence,
            "classification_status": "confirmed_multiple_formulas",
        },
        "phase_original": {
            "phases": deepcopy(phase_entries),
        },
        "source_document_summary": source_summary,
    }


def scan_records(patterns: Any) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    all_records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    cursor = patterns.find({}, SCAN_PROJECTION, batch_size=250)
    for doc in cursor:
        analysis = classify_record(doc)
        all_records.append((doc, analysis))

    counts = Counter()
    duplicate_formula_records = 0
    duplicate_only_formula_records = 0
    formula_values_with_parentheses = 0
    formula_values_with_composition_variable = 0
    for doc, analysis in all_records:
        counts["total_records_scanned"] += 1
        counts["records_with_phase_metadata"] += int(analysis["has_phase_metadata"])
        counts["records_with_at_least_one_explicit_formula"] += int(
            len(analysis["entries"]) >= 1
        )
        counts["records_with_at_least_two_formula_entries"] += int(
            len(analysis["entries"]) >= 2
        )
        counts["records_with_at_least_two_distinct_formulas"] += int(
            len(analysis["distinct_formulas"]) >= 2
        )
        counts["needs_review"] += int(analysis["status"] == "needs_review")
        counts["not_multiple_formulas"] += int(
            analysis["status"] == "not_multiple_formulas"
        )
        counts["records_missing_or_null_phase_metadata"] += int(
            not analysis["has_phase_metadata"]
        )
        counts["records_with_phase_metadata_but_no_explicit_formula"] += int(
            analysis["has_phase_metadata"] and len(analysis["entries"]) == 0
        )
        counts["records_with_any_missing_or_null_formula_slot"] += int(
            analysis["missing_or_placeholder_slots"] > 0
        )
        counts["single_or_distinct_one_formula_records"] += int(
            len(analysis["entries"]) >= 1 and len(analysis["distinct_formulas"]) == 1
        )
        counts["null_or_no_formula_records"] += int(len(analysis["entries"]) == 0)
        counts["formula_values_with_plus_slash_or_semicolon"] += len(
            analysis["ambiguous_formula_values"]
        )
        counts["non_string_formula_values"] += len(
            analysis["invalid_non_string_values"]
        )
        formula_set = set(analysis["formulas"])
        if len(analysis["formulas"]) >= 2 and len(formula_set) < len(
            analysis["formulas"]
        ):
            duplicate_formula_records += 1
            if len(formula_set) < 2:
                duplicate_only_formula_records += 1
        for formula in analysis["formulas"]:
            if "(" in formula or ")" in formula:
                formula_values_with_parentheses += 1
            if re.search(r"[A-Za-z]x|x[A-Za-z]|\bx\b", formula):
                formula_values_with_composition_variable += 1

    counts["records_with_duplicate_formula_entries"] = duplicate_formula_records
    counts["records_with_duplicate_only_formula_entries"] = (
        duplicate_only_formula_records
    )
    counts["formula_values_with_parentheses"] = formula_values_with_parentheses
    counts["formula_values_with_composition_variable"] = (
        formula_values_with_composition_variable
    )
    return all_records, dict(counts)


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=True, indent=2, default=json_default)
        handle.write("\n")


def write_candidates(
    db: Any,
    candidate_records: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    patterns = db[SOURCE_COLLECTION]
    candidates = db[CANDIDATE_COLLECTION]
    inserted = 0
    matched_existing = 0
    modified = 0
    seen_source_ids: set[ObjectId] = set()
    duplicate_input_ids = 0

    for source_doc, analysis in candidate_records:
        if source_doc["_id"] in seen_source_ids:
            duplicate_input_ids += 1
        seen_source_ids.add(source_doc["_id"])
        source_phase_doc = patterns.find_one(
            {"_id": source_doc["_id"]},
            SOURCE_PHASE_PROJECTION,
        )
        if source_phase_doc is None:
            raise RuntimeError(f"Source document disappeared: {source_doc['_id']}")
        candidate_doc = build_candidate_doc(source_doc, source_phase_doc, analysis)
        result = candidates.replace_one(
            {"_id": source_doc["_id"]},
            candidate_doc,
            upsert=True,
        )
        if result.upserted_id is not None:
            inserted += 1
        else:
            matched_existing += 1
            modified += int(result.modified_count > 0)

    index_names = [
        candidates.create_index(
            [("source_record_id", ASCENDING)],
            name="source_record_id",
        ),
        candidates.create_index(
            [("phase_detection.distinct_formula_count", ASCENDING)],
            name="phase_detection_distinct_formula_count",
        ),
        candidates.create_index(
            [("phase_detection.formulas", ASCENDING)],
            name="phase_detection_formulas",
        ),
        candidates.create_index(
            [("phase_detection.classification_status", ASCENDING)],
            name="phase_detection_classification_status",
        ),
    ]
    return {
        "documents_written": len(candidate_records),
        "inserted": inserted,
        "matched_existing": matched_existing,
        "modified": modified,
        "duplicate_or_upsert_conflicts": duplicate_input_ids,
        "indexes": index_names,
    }


def qc_candidates(
    db: Any,
    candidate_records: list[tuple[dict[str, Any], dict[str, Any]]],
    seed: int,
) -> dict[str, Any]:
    candidates = db[CANDIDATE_COLLECTION]
    docs = list(
        candidates.find(
            {},
            {
                "_id": 1,
                "source_record_id": 1,
                "phase_detection": 1,
            },
        )
    )
    invalid_distinct_count = []
    duplicate_formula_docs = []
    for doc in docs:
        detection = doc.get("phase_detection", {})
        formulas = detection.get("formulas", [])
        unique_formulas = list(dict.fromkeys(formulas))
        if detection.get("distinct_formula_count", 0) < 2:
            invalid_distinct_count.append(str(doc["_id"]))
        if len(unique_formulas) < 2:
            duplicate_formula_docs.append(str(doc["_id"]))

    rng = random.Random(seed)
    qc_sample = rng.sample(docs, min(20, len(docs)))
    source_id_set = {doc["_id"] for doc, _ in candidate_records}
    source_id_mismatches = [
        str(doc["_id"])
        for doc in qc_sample
        if doc["_id"] not in source_id_set
    ]
    return {
        "collection_count": len(docs),
        "qc_sample_size": len(qc_sample),
        "invalid_distinct_formula_count": invalid_distinct_count,
        "duplicate_or_single_formula_documents": duplicate_formula_docs,
        "source_id_mismatches_in_qc_sample": source_id_mismatches,
        "all_documents_passed": not (
            invalid_distinct_count
            or duplicate_formula_docs
            or source_id_mismatches
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find OPXRD records with >=2 distinct explicit phase formulas."
    )
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--seed", type=int, default=20261003)
    args = parser.parse_args()

    client = MongoClient(args.uri, serverSelectionTimeoutMS=10_000)
    db = client[args.database]
    patterns = db[SOURCE_COLLECTION]

    all_records, counts = scan_records(patterns)
    confirmed_records = [
        (doc, analysis)
        for doc, analysis in all_records
        if analysis["status"] == "confirmed_multiple_formulas"
    ]
    review_records = [
        (doc, analysis)
        for doc, analysis in all_records
        if analysis["status"] == "needs_review"
    ]

    rng = random.Random(args.seed)
    confirmed_samples = [
        sample_view(doc, analysis)
        for doc, analysis in rng.sample(
            confirmed_records,
            min(10, len(confirmed_records)),
        )
    ]
    review_samples = [
        sample_view(doc, analysis)
        for doc, analysis in rng.sample(
            review_records,
            min(10, len(review_records)),
        )
    ]

    schema_observation = {
        "formula_source_field": "label.phases[*].chemical_composition",
        "fallback_formula_source_field": "phase_chemical_compositions[*] only when label.phases is absent",
        "phase_boundaries": "label.phases array entries; formula strings are not split",
        "element_list_policy": "no elements/basis/phase name fields are used as formulas",
        "solid_solution_policy": "composition expressions remain one source string; no formula expansion or chemistry normalization",
        "placeholder_values_treated_as_missing": sorted(PLACEHOLDER_TOKENS),
        "delimiter_policy": "formula strings containing +, /, or ; are sent to needs_review; comma is retained as source text",
        "observed_formula_values_with_plus_slash_or_semicolon": counts[
            "formula_values_with_plus_slash_or_semicolon"
        ],
    }
    report = {
        "database": args.database,
        "source_collection": SOURCE_COLLECTION,
        "candidate_collection": CANDIDATE_COLLECTION,
        "mode": "write" if args.write else "dry_run",
        "seed": args.seed,
        "counts": counts,
        "schema_observation": schema_observation,
        "samples": {
            "confirmed_multiple_formulas": confirmed_samples,
            "needs_review": review_samples,
        },
        "review_csv": str(REVIEW_CSV),
    }

    write_review_csv(review_records)
    write_report(DRY_RUN_REPORT, report)

    if args.write:
        write_result = write_candidates(db, confirmed_records)
        qc_result = qc_candidates(db, confirmed_records, args.seed)
        report["write_result"] = write_result
        report["qc"] = qc_result
        write_report(FINAL_REPORT, report)

    print(json.dumps(report, ensure_ascii=True, indent=2, default=json_default))


if __name__ == "__main__":
    main()
