#!/usr/bin/env python3
"""Integrate the 996 validated additional OPXRD records into production."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import decode_file_iter
from pymongo import MongoClient, UpdateOne

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

VALIDATION_PATH = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "opxrd_source_labeled_canonical_validation_v1.csv"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "mappings"
DEFAULT_DATABASE = "crystaldb"
DEFAULT_SOURCE_DATABASE = "opxrd"
DEFAULT_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
BACKUP_COLLECTIONS = (
    "sources",
    "samples",
    "measurements",
    "patterns",
    "structures",
    "reflection_sets",
    "relations",
    "refinements",
    "releases",
)
RECORD_COLLECTIONS = ("samples", "measurements", "patterns")
ID_FIELDS = {
    "samples": "sample_id",
    "measurements": "measurement_id",
    "patterns": "pattern_id",
}
EXPECTED_TOTAL_INPUT = 1334
EXPECTED_PASS = 996
EXPECTED_FAILED = 338
EXPECTED_FINAL_PATTERNS = 4090
EXPECTED_FINAL_OPXRD = 1841
EXPECTED_FINAL_PHASE_COUNTS = {
    "single_phase": 1069,
    "multi_phase": 772,
    "unknown": 0,
}
EXPECTED_ADDED_PHASE_COUNTS = {
    "single_phase": 224,
    "multi_phase": 772,
}
EXPECTED_ADDED_EFFECTIVE_PHASE_COUNTS = {1: 224, 2: 770, 3: 1, 4: 1}
EXPECTED_SOURCE_PROVIDERS = {"CNRS", "EMPA", "HKUST"}
SOURCE_GROUP = "opxrd_source_labeled_validated_996"
PHASE_METHOD = "opxrd_effective_phase_count_v1"
PHASE_ORIGIN = "inferred"


def parse_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def parse_int(value: Any, field: str) -> int:
    if value is None or str(value).strip() == "":
        raise ValueError(f"{field} is missing")
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{field} is not an integer: {value!r}") from exc


def finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def numeric_or_none(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        for key in ("value", "wavelength_angstrom", "value_angstrom"):
            if key in value:
                return numeric_or_none(value[key])
        return None
    if not finite_number(value):
        return None
    return value


def json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def source_ref(source_id: str) -> dict[str, str]:
    return {"code": "OPXRD", "source_id": source_id}


def read_validation_rows(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_TOTAL_INPUT:
        raise RuntimeError(
            f"authoritative validation row count is {len(rows)}, "
            f"expected {EXPECTED_TOTAL_INPUT}"
        )
    pass_rows = [row for row in rows if row.get("validation_status") == "PASS"]
    failed_rows = [row for row in rows if row.get("validation_status") != "PASS"]
    if len(pass_rows) != EXPECTED_PASS or len(failed_rows) != EXPECTED_FAILED:
        raise RuntimeError(
            f"authoritative PASS/FAIL counts are {len(pass_rows)}/{len(failed_rows)}, "
            f"expected {EXPECTED_PASS}/{EXPECTED_FAILED}"
        )
    source_ids = [row.get("source_id", "") for row in rows]
    if not all(source_ids) or len(set(source_ids)) != len(source_ids):
        raise RuntimeError("authoritative source IDs are missing or duplicated")
    if any(row.get("source_id") != row.get("record_key") for row in rows):
        raise RuntimeError("authoritative source_id and record_key differ")
    return pass_rows, failed_rows


def validate_authoritative_rows(
    pass_rows: list[dict[str, str]],
    failed_rows: list[dict[str, str]],
) -> None:
    pass_ids = {row["source_id"] for row in pass_rows}
    failed_ids = {row["source_id"] for row in failed_rows}
    if pass_ids & failed_ids:
        raise RuntimeError("a source ID appears in both PASS and failed validation rows")
    if not all(row["source_provider"] in EXPECTED_SOURCE_PROVIDERS for row in pass_rows):
        raise RuntimeError("PASS rows contain an unexpected source provider")
    if any(row["source_provider"] == "USC" for row in pass_rows):
        raise RuntimeError("a USC record is present in the 996 PASS set")
    if len({row["proposed_sample_id"] for row in pass_rows}) != EXPECTED_PASS:
        raise RuntimeError("proposed sample IDs are duplicated")
    if len({row["proposed_measurement_id"] for row in pass_rows}) != EXPECTED_PASS:
        raise RuntimeError("proposed measurement IDs are duplicated")
    if len({row["proposed_pattern_id"] for row in pass_rows}) != EXPECTED_PASS:
        raise RuntimeError("proposed pattern IDs are duplicated")

    phase_counts = Counter()
    phase_characters = Counter()
    for row in pass_rows:
        effective_count = parse_int(row["effective_phase_count"], "effective_phase_count")
        phase_counts[effective_count] += 1
        expected_character = (
            "single_phase" if effective_count == 1 else "multi_phase"
        )
        if effective_count < 1 or row["phase_character"] != expected_character:
            raise RuntimeError(
                f"{row['source_id']}: authoritative phase decision is inconsistent"
            )
        if row["phase_character_origin"] != PHASE_ORIGIN:
            raise RuntimeError(f"{row['source_id']}: unexpected phase origin")
        if row["phase_character_method"] != PHASE_METHOD:
            raise RuntimeError(f"{row['source_id']}: unexpected phase method")
        if parse_bool(row["source_metadata_preserved"]) is not True:
            raise RuntimeError(f"{row['source_id']}: source metadata was not preserved")
        if parse_bool(row["valid_experimental_xy"]) is not True:
            raise RuntimeError(f"{row['source_id']}: source XY is not validated")
        if any(
            parse_bool(row[field]) is True
            for field in (
                "sample_id_collision",
                "measurement_id_collision",
                "pattern_id_collision",
            )
        ):
            raise RuntimeError(f"{row['source_id']}: authoritative ID collision flag is true")
        phase_characters[row["phase_character"]] += 1

    if dict(phase_counts) != EXPECTED_ADDED_EFFECTIVE_PHASE_COUNTS:
        raise RuntimeError(
            f"PASS effective phase count distribution is {dict(phase_counts)}, "
            f"expected {EXPECTED_ADDED_EFFECTIVE_PHASE_COUNTS}"
        )
    if dict(phase_characters) != EXPECTED_ADDED_PHASE_COUNTS:
        raise RuntimeError(
            f"PASS phase distribution is {dict(phase_characters)}, "
            f"expected {EXPECTED_ADDED_PHASE_COUNTS}"
        )


def compact_source_metadata(
    source_document: dict[str, Any],
    row: dict[str, str],
) -> dict[str, Any]:
    """Retain source metadata without copying the source XY payload twice."""
    label = source_document.get("label")
    label_summary: dict[str, Any] = {}
    if isinstance(label, dict):
        label_summary["is_simulated"] = label.get("is_simulated")
        label_summary["xray_info"] = deepcopy(label.get("xray_info"))
        label_summary["crystallite_size_nm"] = label.get("crystallite_size_nm")
        label_summary["temp_K"] = label.get("temp_K")
        phases = label.get("phases")
        if isinstance(phases, list):
            selected_phases: list[dict[str, Any]] = []
            for phase in phases:
                if not isinstance(phase, dict):
                    selected_phases.append({"value": deepcopy(phase)})
                    continue
                selected_phases.append(
                    {
                        key: deepcopy(phase.get(key))
                        for key in (
                            "name",
                            "phase_name",
                            "chemical_composition",
                            "formula",
                            "space_group",
                            "spacegroup",
                            "fraction",
                            "phase_fraction",
                            "weight_fraction",
                            "volume_fraction",
                        )
                        if key in phase
                    }
                )
            label_summary["phases"] = selected_phases

    xrd = source_document.get("xrd")
    xrd_metadata: dict[str, Any] = {}
    if isinstance(xrd, dict):
        xrd_metadata = {
            key: deepcopy(value)
            for key, value in xrd.items()
            if key not in {"two_theta", "intensity"}
        }

    return {
        "source": source_document.get("source"),
        "dataset": source_document.get("dataset"),
        "record_key": source_document.get("record_key"),
        "source_provider": source_document.get("source_provider"),
        "pattern_name": source_document.get("pattern_name"),
        "source_file_format": row.get("source_file_format") or None,
        "phase_count": source_document.get("phase_count"),
        "phase_chemical_compositions": deepcopy(
            source_document.get("phase_chemical_compositions")
        ),
        "phase_spacegroups": deepcopy(source_document.get("phase_spacegroups")),
        "is_mixed_phase": source_document.get("is_mixed_phase"),
        "is_simulated": (
            source_document.get("is_simulated")
            if "is_simulated" in source_document
            else label_summary.get("is_simulated")
        ),
        "metadata": deepcopy(source_document.get("metadata")),
        "import_meta": deepcopy(source_document.get("import_meta")),
        "quality": deepcopy(source_document.get("quality")),
        "label_summary": label_summary,
        "xrd_metadata": xrd_metadata,
        "source_metadata_sha256": row.get("source_metadata_sha256"),
    }


def phase_components(
    source_document: dict[str, Any],
    effective_phase_count: int,
) -> list[dict[str, Any]]:
    compositions = source_document.get("phase_chemical_compositions")
    compositions = compositions if isinstance(compositions, list) else []
    label = source_document.get("label")
    phases = label.get("phases") if isinstance(label, dict) else []
    phases = phases if isinstance(phases, list) else []

    components: list[dict[str, Any]] = []
    for index in range(effective_phase_count):
        phase = phases[index] if index < len(phases) else {}
        phase = phase if isinstance(phase, dict) else {}
        formula = (
            compositions[index]
            if index < len(compositions)
            else phase.get("chemical_composition") or phase.get("formula")
        )
        fraction = None
        for key in ("fraction", "phase_fraction", "weight_fraction", "volume_fraction"):
            candidate = phase.get(key)
            if candidate is not None:
                fraction = candidate
                break
        components.append(
            {
                "phase_index": index + 1,
                "role": "primary" if index == 0 else "secondary",
                "name": phase.get("name") or phase.get("phase_name"),
                "formula": formula,
                "formula_normalized": formula,
                "fraction": fraction,
                "fraction_basis": "source_metadata" if fraction is not None else None,
                "structure_ids": [],
            }
        )
    return components


def wavelength_info(source_document: dict[str, Any]) -> tuple[Any, Any]:
    label = source_document.get("label")
    xray_info = label.get("xray_info") if isinstance(label, dict) else {}
    if not isinstance(xray_info, dict):
        return None, None
    primary = None
    secondary = None
    for key in ("primary_wavelength", "wavelength_angstrom", "wavelength"):
        if key in xray_info:
            primary = numeric_or_none(xray_info.get(key))
            if primary is not None:
                break
    for key in ("secondary_wavelength", "wavelength_kalpha2", "kalpha2_wavelength"):
        if key in xray_info:
            secondary = numeric_or_none(xray_info.get(key))
            if secondary is not None:
                break
    return primary, secondary


def source_evidence(
    row: dict[str, str],
    source_document: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source": "OPXRD",
        "source_id": row["source_id"],
        "record_key": row["record_key"],
        "source_provider": row["source_provider"],
        "source_metadata_sha256": row["source_metadata_sha256"],
        "effective_phase_count": parse_int(
            row["effective_phase_count"], "effective_phase_count"
        ),
        "source_phase_count": source_document.get("phase_count"),
        "label_type": "source_metadata",
        "label_method": "effective_phase_count",
        "evidence": (
            "source effective_phase_count="
            + row["effective_phase_count"]
        ),
    }


def build_documents(
    row: dict[str, str],
    source_document: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    source_id = row["source_id"]
    effective_count = parse_int(row["effective_phase_count"], "effective_phase_count")
    phase_character = row["phase_character"]
    source_metadata = compact_source_metadata(source_document, row)
    evidence = source_evidence(row, source_document)
    source = source_ref(source_id)
    provenance = {
        **evidence,
        "source_file": row["import_relative_path"],
        "original_file_format": row.get("source_file_format") or None,
    }
    xrd = source_document.get("xrd") or {}
    x_values = list(xrd.get("two_theta") or [])
    y_values = list(xrd.get("intensity") or [])
    point_count = len(x_values)
    two_theta_min = xrd.get("two_theta_min")
    two_theta_max = xrd.get("two_theta_max")
    if two_theta_min is None and x_values:
        two_theta_min = x_values[0]
    if two_theta_max is None and x_values:
        two_theta_max = x_values[-1]
    primary_wavelength, secondary_wavelength = wavelength_info(source_document)
    label = source_document.get("label")
    temperature = label.get("temp_K") if isinstance(label, dict) else None
    sample_formula = None
    compositions = source_document.get("phase_chemical_compositions")
    if (
        effective_count == 1
        and isinstance(compositions, list)
        and len(compositions) == 1
    ):
        sample_formula = compositions[0]
    common = {
        "api_source_code": "OPXRD",
        "api_source_id": source_id,
        "source": source,
        "data_origin": "experimental",
        "profile_origin": "experimental",
        "phase_character": phase_character,
        "phase_character_origin": PHASE_ORIGIN,
        "phase_character_method": PHASE_METHOD,
        "effective_phase_count": effective_count,
        "phase_count_raw": parse_int(row["phase_count_raw"], "phase_count_raw"),
        "is_mixed_phase": parse_bool(row["is_mixed_phase"]),
        "is_simulated": parse_bool(row["is_simulated"]),
        "provenance": provenance,
        "source_metadata": source_metadata,
    }
    sample = {
        "sample_id": row["proposed_sample_id"],
        **common,
        "name": row["pattern_name"],
        "formula": sample_formula,
    }
    measurement = {
        "measurement_id": row["proposed_measurement_id"],
        **common,
        "sample_id": row["proposed_sample_id"],
        "pattern_id": row["proposed_pattern_id"],
        "modality": "powder_xrd",
        "measurement_type": "powder_xrd",
        "conditions": {
            "radiation": "x-ray",
            "wavelength_angstrom": primary_wavelength,
            "wavelength_kalpha2_angstrom": secondary_wavelength,
            "temperature_K": numeric_or_none(temperature),
            "scan_axis": "2theta",
        },
        "source_file": row["import_relative_path"],
    }
    pattern = {
        "pattern_id": row["proposed_pattern_id"],
        **common,
        "sample_id": row["proposed_sample_id"],
        "measurement_id": row["proposed_measurement_id"],
        "modality": "powder_xrd",
        "dataset_role": "canonical",
        "phase_components": phase_components(source_document, effective_count),
        "structure_linkage": {
            "status": "unlinked",
            "coverage": "none",
            "certainty": "unknown",
            "candidate_structure_ids": [],
        },
        "linked_structure_ids": [],
        "has_xy": True,
        "scan": {
            "axis": "two_theta",
            "two_theta_min_deg": two_theta_min,
            "two_theta_max_deg": two_theta_max,
            "point_count": point_count,
        },
        "radiation": {
            "anode": None,
            "wavelength_angstrom": primary_wavelength,
            "wavelength_kalpha2_angstrom": secondary_wavelength,
        },
        "data": {
            "two_theta": x_values,
            "intensity": y_values,
        },
        "file": {
            "key": row["import_relative_path"],
            "sha256": (source_document.get("import_meta") or {}).get(
                "content_sha256"
            ),
            "size_bytes": (source_document.get("import_meta") or {}).get(
                "file_size_bytes"
            ),
        },
        "source_group": SOURCE_GROUP,
        "source_record_key": source_id,
    }
    return {
        "samples": sample,
        "measurements": measurement,
        "patterns": pattern,
    }


def load_source_documents(
    source_database: Any,
    source_ids: set[str],
) -> dict[str, dict[str, Any]]:
    documents = {
        str(document.get("record_key")): document
        for document in source_database.patterns.find(
            {"record_key": {"$in": sorted(source_ids)}},
            {"_id": 0},
        )
    }
    if set(documents) != source_ids:
        missing = sorted(source_ids - set(documents))
        extra = sorted(set(documents) - source_ids)
        raise RuntimeError(
            f"source record mismatch: missing={missing[:10]}, extra={extra[:10]}"
        )
    return documents


def validate_source_against_row(
    row: dict[str, str],
    source_document: dict[str, Any],
) -> None:
    effective_count = parse_int(row["effective_phase_count"], "effective_phase_count")
    source_phase_count = source_document.get("phase_count")
    if source_phase_count is not None and int(source_phase_count) != effective_count:
        raise RuntimeError(
            f"{row['source_id']}: source phase_count {source_phase_count} "
            f"does not match authoritative effective_phase_count {effective_count}"
        )
    x_values = list((source_document.get("xrd") or {}).get("two_theta") or [])
    y_values = list((source_document.get("xrd") or {}).get("intensity") or [])
    if len(x_values) != parse_int(row["x_point_count"], "x_point_count"):
        raise RuntimeError(f"{row['source_id']}: source X point count changed")
    if len(y_values) != parse_int(row["y_point_count"], "y_point_count"):
        raise RuntimeError(f"{row['source_id']}: source Y point count changed")
    if len(x_values) != len(y_values):
        raise RuntimeError(f"{row['source_id']}: source XY lengths differ")
    if not all(finite_number(value) for value in x_values + y_values):
        raise RuntimeError(f"{row['source_id']}: source XY contains non-finite values")
    if len(x_values) > 1 and not all(
        float(left) < float(right)
        for left, right in zip(x_values, x_values[1:])
    ):
        raise RuntimeError(f"{row['source_id']}: source axis is not strictly increasing")


def collection_counts(database: Any) -> dict[str, int]:
    return {
        collection: database[collection].count_documents({})
        for collection in BACKUP_COLLECTIONS
    }


def backup_counts(backup_root: Path) -> dict[str, int]:
    database_root = backup_root / DEFAULT_DATABASE
    if not database_root.is_dir():
        raise RuntimeError(f"backup database directory is missing: {database_root}")
    counts: dict[str, int] = {}
    for collection in BACKUP_COLLECTIONS:
        bson_path = database_root / f"{collection}.bson"
        metadata_path = database_root / f"{collection}.metadata.json"
        if not bson_path.is_file() or not metadata_path.is_file():
            raise RuntimeError(f"backup is missing {collection} BSON or metadata")
        with bson_path.open("rb") as stream:
            counts[collection] = sum(1 for _ in decode_file_iter(stream))
    return counts


def existing_documents_by_id(
    database: Any,
    collection: str,
    ids: list[str],
) -> dict[str, dict[str, Any]]:
    id_field = ID_FIELDS[collection]
    return {
        str(document[id_field]): document
        for document in database[collection].find(
            {id_field: {"$in": ids}},
            {"_id": 0},
        )
    }


def compare_existing_document(
    existing: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for key, expected_value in expected.items():
        if existing.get(key) != expected_value:
            errors.append(key)
    return errors


def preflight_ids(
    database: Any,
    documents: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    collisions: dict[str, list[str]] = {}
    existing_counts: dict[str, int] = {}
    for collection, expected_documents in documents.items():
        id_field = ID_FIELDS[collection]
        expected_by_id = {document[id_field]: document for document in expected_documents}
        existing = existing_documents_by_id(
            database,
            collection,
            sorted(expected_by_id),
        )
        existing_counts[collection] = len(existing)
        for identifier, existing_document in existing.items():
            mismatches = compare_existing_document(
                existing_document,
                expected_by_id[identifier],
            )
            if mismatches:
                collisions[f"{collection}:{identifier}"] = mismatches
    if collisions:
        raise RuntimeError(
            "production ID collisions contain non-identical documents: "
            + json.dumps(collisions, ensure_ascii=False, default=json_default)
        )
    return {"existing_counts": existing_counts, "collision_count": 0}


def bulk_upsert(
    database: Any,
    collection: str,
    documents: list[dict[str, Any]],
    timestamp: datetime,
) -> dict[str, int]:
    id_field = ID_FIELDS[collection]
    operations = [
        UpdateOne(
            {id_field: document[id_field]},
            {
                "$set": document,
                "$setOnInsert": {
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            },
            upsert=True,
        )
        for document in documents
    ]
    result = database[collection].bulk_write(operations, ordered=True)
    return {
        "matched": int(result.matched_count),
        "modified": int(result.modified_count),
        "upserted": int(result.upserted_count),
    }


def duplicate_ids(database: Any, collection: str, id_field: str) -> list[Any]:
    return list(
        database[collection].aggregate(
            [
                {
                    "$group": {
                        "_id": f"${id_field}",
                        "count": {"$sum": 1},
                    }
                },
                {"$match": {"count": {"$gt": 1}}},
                {"$limit": 20},
            ]
        )
    )


def phase_counts(database: Any) -> dict[str, int]:
    result = Counter()
    for document in database.patterns.find(
        {"api_source_code": "OPXRD"},
        {"_id": 0, "phase_character": 1},
    ):
        result[document.get("phase_character", "unknown")] += 1
    return {
        phase_character: result.get(phase_character, 0)
        for phase_character in ("single_phase", "multi_phase", "unknown")
    }


def verify_references(
    database: Any,
    source_ids: set[str] | None = None,
) -> list[str]:
    sample_ids = set(database.samples.distinct("sample_id"))
    measurement_ids = set(database.measurements.distinct("measurement_id"))
    errors: list[str] = []
    if source_ids is None:
        pattern_filter: dict[str, Any] = {}
    else:
        pattern_filter = {"source.source_id": {"$in": sorted(source_ids)}}
    scoped_patterns = list(
        database.patterns.find(
            pattern_filter,
            {"_id": 0, "pattern_id": 1, "sample_id": 1, "measurement_id": 1},
        )
    )
    for pattern in scoped_patterns:
        if pattern.get("sample_id") not in sample_ids:
            errors.append(f"pattern {pattern.get('pattern_id')} missing sample")
        if pattern.get("measurement_id") not in measurement_ids:
            errors.append(f"pattern {pattern.get('pattern_id')} missing measurement")
    if source_ids is None:
        measurement_filter: dict[str, Any] = {}
    else:
        measurement_filter = {
            "measurement_id": {
                "$in": sorted(
                    {
                        pattern.get("measurement_id")
                        for pattern in scoped_patterns
                        if pattern.get("measurement_id")
                    }
                )
            }
        }
    for measurement in database.measurements.find(
        measurement_filter,
        {"_id": 0, "measurement_id": 1, "sample_id": 1},
    ):
        if measurement.get("sample_id") not in sample_ids:
            errors.append(
                f"measurement {measurement.get('measurement_id')} missing sample"
            )
    return errors[:20]


def verify_added_records(
    database: Any,
    pass_rows: list[dict[str, str]],
    source_documents: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    by_pattern_id = {
        row["proposed_pattern_id"]: row for row in pass_rows
    }
    production_patterns = {
        document["pattern_id"]: document
        for document in database.patterns.find(
            {"pattern_id": {"$in": sorted(by_pattern_id)}},
            {"_id": 0},
        )
    }
    production_samples = {
        document["sample_id"]: document
        for document in database.samples.find(
            {
                "sample_id": {
                    "$in": [row["proposed_sample_id"] for row in pass_rows]
                }
            },
            {"_id": 0},
        )
    }
    production_measurements = {
        document["measurement_id"]: document
        for document in database.measurements.find(
            {
                "measurement_id": {
                    "$in": [row["proposed_measurement_id"] for row in pass_rows]
                }
            },
            {"_id": 0},
        )
    }
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in pass_rows:
        source_id = row["source_id"]
        pattern_id = row["proposed_pattern_id"]
        sample_id = row["proposed_sample_id"]
        measurement_id = row["proposed_measurement_id"]
        source_document = source_documents[source_id]
        source_x = list((source_document.get("xrd") or {}).get("two_theta") or [])
        source_y = list((source_document.get("xrd") or {}).get("intensity") or [])
        pattern = production_patterns.get(pattern_id)
        sample = production_samples.get(sample_id)
        measurement = production_measurements.get(measurement_id)
        record_errors: list[str] = []
        if pattern is None:
            record_errors.append("missing pattern")
        if sample is None:
            record_errors.append("missing sample")
        if measurement is None:
            record_errors.append("missing measurement")
        if pattern is not None:
            if pattern.get("data", {}).get("two_theta") != source_x:
                record_errors.append("X data changed")
            if pattern.get("data", {}).get("intensity") != source_y:
                record_errors.append("Y data changed")
            if pattern.get("source_metadata") != compact_source_metadata(
                source_document, row
            ):
                record_errors.append("source metadata changed")
            if pattern.get("effective_phase_count") != parse_int(
                row["effective_phase_count"], "effective_phase_count"
            ):
                record_errors.append("effective phase count changed")
            if pattern.get("phase_character") != row["phase_character"]:
                record_errors.append("phase character changed")
            if pattern.get("phase_character_origin") != PHASE_ORIGIN:
                record_errors.append("phase origin changed")
            if pattern.get("phase_character_method") != PHASE_METHOD:
                record_errors.append("phase method changed")
            if pattern.get("measurement_id") != measurement_id:
                record_errors.append("pattern measurement link changed")
            if pattern.get("sample_id") != sample_id:
                record_errors.append("pattern sample link changed")
        if sample is not None and sample.get("phase_character") != row["phase_character"]:
            record_errors.append("sample phase character changed")
        if (
            measurement is not None
            and measurement.get("pattern_id") != pattern_id
        ):
            record_errors.append("measurement pattern link changed")
        if record_errors:
            errors.append(f"{source_id}: " + "; ".join(record_errors))
        records.append(
            {
                "source_id": source_id,
                "source_provider": row["source_provider"],
                "sample_id": sample_id,
                "measurement_id": measurement_id,
                "pattern_id": pattern_id,
                "effective_phase_count": parse_int(
                    row["effective_phase_count"], "effective_phase_count"
                ),
                "phase_character": row["phase_character"],
                "x_point_count": len(source_x),
                "y_point_count": len(source_y),
                "xy_preserved": not any(
                    error in {"X data changed", "Y data changed"}
                    for error in record_errors
                ),
                "source_metadata_preserved": "source metadata changed"
                not in record_errors,
                "status": "PASS" if not record_errors else "FAIL",
                "errors": "; ".join(record_errors),
            }
        )
    return records, errors


def verify_database(
    database: Any,
    pass_rows: list[dict[str, str]],
    failed_rows: list[dict[str, str]],
    source_documents: dict[str, dict[str, Any]],
    before_counts: dict[str, int],
    expected_collection_deltas: dict[str, int] | None = None,
) -> dict[str, Any]:
    counts = collection_counts(database)
    opxrd_count = database.patterns.count_documents({"api_source_code": "OPXRD"})
    phase_distribution = phase_counts(database)
    added_records, record_errors = verify_added_records(
        database,
        pass_rows,
        source_documents,
    )
    duplicate_results = {
        collection: duplicate_ids(database, collection, id_field)
        for collection, id_field in ID_FIELDS.items()
    }
    duplicate_errors = {
        collection: values
        for collection, values in duplicate_results.items()
        if values
    }
    target_source_ids = {row["source_id"] for row in pass_rows}
    orphan_errors = verify_references(database, target_source_ids)
    global_orphan_sample = verify_references(database)
    failed_ids = [row["source_id"] for row in failed_rows]
    failed_production_count = database.patterns.count_documents(
        {"source.source_id": {"$in": failed_ids}}
    )
    added_pattern_count = database.patterns.count_documents(
        {
            "source_group": SOURCE_GROUP,
            "api_source_code": "OPXRD",
        }
    )
    if expected_collection_deltas is None:
        expected_collection_deltas = {
            "samples": 0,
            "measurements": 0,
            "patterns": 0,
            "structures": 0,
            "reflection_sets": 0,
            "relations": 0,
            "refinements": 0,
            "releases": 0,
            "sources": 0,
        }
    collection_delta_ok = {
        collection: counts[collection] - before_counts[collection]
        == expected_collection_deltas[collection]
        for collection in expected_collection_deltas
    }
    checks = {
        "total_pattern_count": counts["patterns"] == EXPECTED_FINAL_PATTERNS,
        "opxrd_pattern_count": opxrd_count == EXPECTED_FINAL_OPXRD,
        "phase_distribution": phase_distribution == EXPECTED_FINAL_PHASE_COUNTS,
        "added_pattern_count": added_pattern_count == EXPECTED_PASS,
        "failed_usc_absent": failed_production_count == 0,
        "record_payloads_preserved": not record_errors,
        "no_duplicate_ids": not duplicate_errors,
        "no_orphan_records": not orphan_errors,
        "collection_deltas": all(collection_delta_ok.values()),
    }
    return {
        "collection_counts": counts,
        "opxrd_pattern_count": opxrd_count,
        "phase_distribution": phase_distribution,
        "added_pattern_count": added_pattern_count,
        "failed_validation_records_in_production": failed_production_count,
        "record_errors": record_errors,
        "duplicate_ids": duplicate_results,
        "orphan_errors": orphan_errors,
        "global_orphan_sample": global_orphan_sample,
        "global_orphan_sample_count": len(global_orphan_sample),
        "collection_deltas": {
            collection: counts[collection] - before_counts[collection]
            for collection in expected_collection_deltas
        },
        "collection_delta_checks": collection_delta_ok,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "record_results": added_records,
    }


def write_record_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "source_provider",
        "sample_id",
        "measurement_id",
        "pattern_id",
        "effective_phase_count",
        "phase_character",
        "x_point_count",
        "y_point_count",
        "xy_preserved",
        "source_metadata_preserved",
        "status",
        "errors",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def write_summary(
    path: Path,
    *,
    backup_root: Path,
    run_timestamp: datetime,
    before_counts: dict[str, int],
    verification: dict[str, Any],
    write_results: dict[str, dict[str, int]],
    idempotence_results: dict[str, dict[str, int]],
) -> None:
    counts = verification["collection_counts"]
    phase_distribution = verification["phase_distribution"]
    lines = [
        "# OPXRD Additional 996 Production Integration v1",
        "",
        f"- Run timestamp UTC: {run_timestamp.isoformat()}",
        f"- Production database: `{DEFAULT_DATABASE}`",
        f"- Authoritative validation CSV: `{VALIDATION_PATH}`",
        f"- Production backup: `{backup_root.resolve()}`",
        f"- Source database: `{DEFAULT_SOURCE_DATABASE}.patterns`",
        f"- Source group: `{SOURCE_GROUP}`",
        f"- Phase method: `{PHASE_METHOD}`",
        "",
        "## Write Scope",
        "",
        "- PASS records integrated: 996",
        "- USC unresolved records integrated: 0",
        "- CIF matching: not performed",
        "- Structures and relations added: 0",
        "",
        "## Counts",
        "",
        f"- Total CrystalDB patterns: {counts['patterns']}",
        f"- OPXRD production patterns: {verification['opxrd_pattern_count']}",
        f"- OPXRD single_phase: {phase_distribution.get('single_phase', 0)}",
        f"- OPXRD multi_phase: {phase_distribution.get('multi_phase', 0)}",
        f"- OPXRD unknown: {phase_distribution.get('unknown', 0)}",
        f"- New 996 orphan references: {len(verification['orphan_errors'])}",
        f"- Existing out-of-scope orphan sample size: "
        f"{verification['global_orphan_sample_count']}",
        "",
        "## Write Result",
        "",
        f"- First pass: `{json.dumps(write_results, sort_keys=True)}`",
        f"- Idempotence pass: `{json.dumps(idempotence_results, sort_keys=True)}`",
        "",
        "## Verification",
        "",
    ]
    for name, passed in verification["checks"].items():
        lines.append(f"- {name}: {passed}")
    lines.extend(
        [
            "",
            "## Collection Counts",
            "",
            f"- Before: `{json.dumps(before_counts, sort_keys=True)}`",
            f"- After: `{json.dumps(counts, sort_keys=True)}`",
            "",
            "No XY data, source metadata, structures, relations, website, manuscript, "
            "release files, or Git history were modified outside the requested 996 "
            "sample/measurement/pattern records. Existing out-of-scope orphan "
            "references were not modified.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_backup_manifest(
    backup_root: Path,
    expected_backup_counts: dict[str, int],
    verified_counts: dict[str, int],
) -> None:
    write_json(
        backup_root / "integration_backup_manifest.json",
        {
            "created_for": "opxrd_additional_996_production_integration_v1",
            "database": DEFAULT_DATABASE,
            "backup_root": str(backup_root.resolve()),
            "created_at_utc": utc_now(),
            "collection_counts_at_backup": expected_backup_counts,
            "collection_counts_from_backup": verified_counts,
            "complete": expected_backup_counts == verified_counts,
        },
    )


def build_all_documents(
    pass_rows: list[dict[str, str]],
    source_documents: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    documents = {collection: [] for collection in RECORD_COLLECTIONS}
    for row in pass_rows:
        source_document = source_documents[row["source_id"]]
        validate_source_against_row(row, source_document)
        built = build_documents(row, source_document)
        for collection in RECORD_COLLECTIONS:
            documents[collection].append(built[collection])
    return documents


def run(args: argparse.Namespace) -> int:
    pass_rows, failed_rows = read_validation_rows(args.validation_csv)
    validate_authoritative_rows(pass_rows, failed_rows)
    pass_ids = {row["source_id"] for row in pass_rows}

    client = MongoClient(args.uri, serverSelectionTimeoutMS=10_000)
    try:
        production = client[args.database]
        source_database = client[args.source_database]
        source_documents = load_source_documents(source_database, pass_ids)
        documents = build_all_documents(pass_rows, source_documents)
        before_counts = collection_counts(production)
        existing_target_counts = {
            collection: production[collection].count_documents(
                {"source.source_id": {"$in": sorted(pass_ids)}}
            )
            for collection in RECORD_COLLECTIONS
        }
        if any(count > EXPECTED_PASS for count in existing_target_counts.values()):
            raise RuntimeError(
                "more than 996 authoritative target records are already present: "
                + json.dumps(existing_target_counts, sort_keys=True)
            )
        expected_new_counts = {
            collection: EXPECTED_PASS - existing_target_counts[collection]
            for collection in RECORD_COLLECTIONS
        }
        expected_backup_counts = dict(before_counts)
        for collection in RECORD_COLLECTIONS:
            expected_backup_counts[collection] -= existing_target_counts[collection]
        if before_counts["patterns"] + (
            expected_new_counts["patterns"]
        ) != EXPECTED_FINAL_PATTERNS:
            raise RuntimeError(
                "production pattern baseline is incompatible with expected final count: "
                + json.dumps(before_counts, sort_keys=True)
            )
        if production.sources.count_documents(
            {"source_id": "SRC_OPXRD"}
        ) != 1:
            raise RuntimeError("expected existing SRC_OPXRD source document")
        preflight = preflight_ids(production, documents)
        if args.verify_only:
            verification = verify_database(
                production,
                pass_rows,
                failed_rows,
                source_documents,
                before_counts,
                expected_new_counts,
            )
            print(
                json.dumps(
                    {
                        "mode": "verify-only",
                        "preflight": preflight,
                        "verification": verification,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=json_default,
                )
            )
            return 0 if verification["all_checks_pass"] else 1

        if not args.write:
            print(
                json.dumps(
                    {
                        "mode": "preflight",
                        "authoritative_pass_count": len(pass_rows),
                        "failed_count": len(failed_rows),
                        "before_counts": before_counts,
                        "preflight": preflight,
                        "expected_added_effective_phase_counts": (
                            EXPECTED_ADDED_EFFECTIVE_PHASE_COUNTS
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        if args.backup_root is None:
            raise RuntimeError("--backup-root is required with --write")
        backup_root = args.backup_root.resolve()
        verified_backup_counts = backup_counts(backup_root)
        if verified_backup_counts != expected_backup_counts:
            raise RuntimeError(
                "production backup counts do not match the pre-write counts: "
                + json.dumps(
                    {
                        "expected_backup": expected_backup_counts,
                        "backup": verified_backup_counts,
                    },
                    sort_keys=True,
                )
            )
        write_backup_manifest(
            backup_root,
            expected_backup_counts,
            verified_backup_counts,
        )

        run_timestamp = utc_now()
        write_results = {
            collection: bulk_upsert(
                production,
                collection,
                documents[collection],
                run_timestamp,
            )
            for collection in RECORD_COLLECTIONS
        }
        verification = verify_database(
            production,
            pass_rows,
            failed_rows,
            source_documents,
            before_counts,
            expected_new_counts,
        )
        if not verification["all_checks_pass"]:
            raise RuntimeError(
                "post-write verification failed: "
                + json.dumps(
                    verification["checks"],
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )

        idempotence_before_counts = collection_counts(production)
        idempotence_results = {
            collection: bulk_upsert(
                production,
                collection,
                documents[collection],
                run_timestamp,
            )
            for collection in RECORD_COLLECTIONS
        }
        idempotence_after_counts = collection_counts(production)
        idempotence_passes = (
            all(
                result["upserted"] == 0 and result["modified"] == 0
                for result in idempotence_results.values()
            )
            and idempotence_before_counts == idempotence_after_counts
        )
        if not idempotence_passes:
            raise RuntimeError(
                "idempotence verification failed: "
                + json.dumps(
                    {
                        "results": idempotence_results,
                        "before": idempotence_before_counts,
                        "after": idempotence_after_counts,
                    },
                    sort_keys=True,
                )
            )

        verification["checks"]["idempotence"] = idempotence_passes
        verification["all_checks_pass"] = all(verification["checks"].values())
        output_dir = args.output_dir.resolve()
        record_csv = output_dir / "opxrd_additional_996_production_integration_v1.csv"
        json_output = output_dir / "opxrd_additional_996_production_integration_v1.json"
        summary_output = (
            output_dir / "opxrd_additional_996_production_integration_v1_summary.md"
        )
        write_record_csv(record_csv, verification["record_results"])
        write_json(
            json_output,
            {
                "run_timestamp_utc": run_timestamp,
                "database": args.database,
                "source_database": args.source_database,
                "validation_csv": str(args.validation_csv.resolve()),
                "backup_root": str(backup_root),
                "preflight": preflight,
                "before_counts": before_counts,
                "write_results": write_results,
                "idempotence_results": idempotence_results,
                "verification": verification,
            },
        )
        write_summary(
            summary_output,
            backup_root=backup_root,
            run_timestamp=run_timestamp,
            before_counts=before_counts,
            verification=verification,
            write_results=write_results,
            idempotence_results=idempotence_results,
        )
        print(
            json.dumps(
                {
                    "mode": "write",
                    "backup_root": str(backup_root),
                    "write_results": write_results,
                    "idempotence_results": idempotence_results,
                    "verification": {
                        key: value
                        for key, value in verification.items()
                        if key != "record_results"
                    },
                    "outputs": {
                        "csv": str(record_csv),
                        "json": str(json_output),
                        "summary": str(summary_output),
                    },
                },
                ensure_ascii=False,
                indent=2,
                default=json_default,
            )
        )
        return 0
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--source-database", default=DEFAULT_SOURCE_DATABASE)
    parser.add_argument("--validation-csv", type=Path, default=VALIDATION_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.write and args.verify_only:
        parser.error("--write and --verify-only are mutually exclusive")
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
