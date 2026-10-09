#!/usr/bin/env python3
"""Load the verified PowBase canonical dry-run into an isolated Mongo database."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGING_ROOT = PROJECT_ROOT / "data" / "staging" / "powbase_canonical_v1"
DEFAULT_CANONICAL_JSON = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
)
DEFAULT_DATABASE = "crystaldb_powbase_staging_20261007"
DEFAULT_JSON_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_mongo_staging_validation_v1.json"
)
DEFAULT_CSV_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_mongo_staging_validation_v1.csv"
)
DEFAULT_SUMMARY_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_mongo_staging_summary_v1.md"
)
FORBIDDEN_DATABASES = {
    "crystaldb",
    "rruff",
    "opxrd",
    "dara",
    "crystaldb_api_pilot",
}
COLLECTIONS = ("sources", "samples", "measurements", "patterns", "relations")
RECORD_COLLECTIONS = ("samples", "measurements", "patterns")
EXPECTED_RECORD_COUNT = 44


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_documents(directory: Path) -> list[dict[str, Any]]:
    return [
        read_json(path)
        for path in sorted(directory.glob("*.json"))
        if path.is_file()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def finite_increasing(values: list[Any]) -> bool:
    try:
        numbers = [float(value) for value in values]
    except (TypeError, ValueError):
        return False
    return bool(numbers) and all(
        math.isfinite(value) for value in numbers
    ) and all(
        current > previous
        for previous, current in zip(numbers, numbers[1:])
    )


def finite_values(values: list[Any]) -> bool:
    try:
        return all(math.isfinite(float(value)) for value in values)
    except (TypeError, ValueError):
        return False


def source_code(document: dict[str, Any]) -> str | None:
    source = document.get("source")
    if isinstance(source, dict):
        return str(source.get("code") or "").upper() or None
    if isinstance(source, str):
        return source.upper()
    return None


def source_id(document: dict[str, Any]) -> str | None:
    source = document.get("source")
    if isinstance(source, dict):
        value = source.get("source_id")
        return str(value) if value not in (None, "") else None
    return None


def production_index_specs() -> dict[str, list[tuple[list[tuple[str, int]], dict[str, Any]]]]:
    """The indexes used by the existing canonical API pilot builder."""

    return {
        "sources": [
            ([("source_id", 1)], {"unique": True, "name": "source_id_unique"}),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
        ],
        "samples": [
            ([("sample_id", 1)], {"unique": True, "name": "sample_id_unique"}),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
        ],
        "measurements": [
            (
                [("measurement_id", 1)],
                {"unique": True, "name": "measurement_id_unique"},
            ),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
        ],
        "patterns": [
            ([("pattern_id", 1)], {"unique": True, "name": "pattern_id_unique"}),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
            ([("modality", 1)], {"name": "modality"}),
            ([("phase_character", 1)], {"name": "phase_character"}),
            ([("dataset_role", 1)], {"name": "dataset_role"}),
            (
                [("phase_components.formula_normalized", 1)],
                {"name": "component_formula"},
            ),
            (
                [("structure_linkage.status", 1)],
                {"name": "structure_linkage"},
            ),
            ([("linked_structure_ids", 1)], {"name": "linked_structure_ids"}),
        ],
        "relations": [
            ([("relation_id", 1)], {"unique": True, "name": "relation_id_unique"}),
            ([("subject_id", 1)], {"name": "subject_id"}),
            ([("object_id", 1)], {"name": "object_id"}),
        ],
    }


def ensure_indexes(database: Any) -> None:
    for collection_name, specifications in production_index_specs().items():
        for keys, options in specifications:
            database[collection_name].create_index(keys, **options)


def load_local_documents(
    staging_root: Path,
    canonical_json: Path,
) -> dict[str, Any]:
    source_dir = staging_root / "records" / "samples"
    measurement_dir = staging_root / "records" / "measurements"
    pattern_dir = staging_root / "records" / "patterns"
    xy_dir = staging_root / "xy"
    quarantine_dir = staging_root / "quarantine"

    documents = {
        "samples": read_json_documents(source_dir),
        "measurements": read_json_documents(measurement_dir),
        "patterns": read_json_documents(pattern_dir),
        "xy": read_json_documents(xy_dir),
    }
    canonical = read_json(canonical_json)
    selected_ids = {
        str(record["entry_id"])
        for record in canonical.get("records") or []
    }
    if selected_ids != {
        str(document["source"].get("source_id"))
        for document in documents["samples"]
    }:
        raise ValueError("local staging sample source IDs differ from dry-run records")
    if len(selected_ids) != EXPECTED_RECORD_COUNT:
        raise ValueError(f"expected {EXPECTED_RECORD_COUNT} selected records")
    if quarantine_dir.exists() and list(quarantine_dir.glob("*.json")):
        raise ValueError("canonical staging contains quarantine records")
    return {
        **documents,
        "canonical": canonical,
        "selected_ids": sorted(selected_ids),
    }


def _index_ids(documents: list[dict[str, Any]], field: str) -> tuple[set[str], list[str]]:
    ids = [str(document.get(field) or "") for document in documents]
    missing = [value for value in ids if not value]
    return set(ids), missing


def validate_local_documents(local: dict[str, Any]) -> dict[str, Any]:
    samples = local["samples"]
    measurements = local["measurements"]
    patterns = local["patterns"]
    xy_payloads = local["xy"]
    errors: list[str] = []

    counts = {
        "samples": len(samples),
        "measurements": len(measurements),
        "patterns": len(patterns),
        "xy_payloads": len(xy_payloads),
    }
    for name, count in counts.items():
        if count != EXPECTED_RECORD_COUNT:
            errors.append(f"{name}_count={count}")

    sample_ids, missing_sample_ids = _index_ids(samples, "sample_id")
    measurement_ids, missing_measurement_ids = _index_ids(
        measurements, "measurement_id"
    )
    pattern_ids, missing_pattern_ids = _index_ids(patterns, "pattern_id")
    xy_ids, missing_xy_ids = _index_ids(xy_payloads, "pattern_id")

    for name, values in (
        ("sample", missing_sample_ids),
        ("measurement", missing_measurement_ids),
        ("pattern", missing_pattern_ids),
        ("xy", missing_xy_ids),
    ):
        if values:
            errors.append(f"missing_{name}_ids={values}")
    if len(sample_ids) != len(samples):
        errors.append("duplicate_sample_ids")
    if len(measurement_ids) != len(measurements):
        errors.append("duplicate_measurement_ids")
    if len(pattern_ids) != len(patterns):
        errors.append("duplicate_pattern_ids")
    if len(xy_ids) != len(xy_payloads):
        errors.append("duplicate_xy_pattern_ids")

    samples_by_id = {document["sample_id"]: document for document in samples}
    measurements_by_id = {
        document["measurement_id"]: document for document in measurements
    }
    patterns_by_id = {document["pattern_id"]: document for document in patterns}
    xy_by_pattern_id = {document["pattern_id"]: document for document in xy_payloads}
    record_rows: list[dict[str, Any]] = []

    for pattern in sorted(patterns, key=lambda item: item.get("pattern_id", "")):
        pattern_id = pattern.get("pattern_id")
        measurement_id = pattern.get("measurement_id")
        sample_id = pattern.get("sample_id")
        measurement = measurements_by_id.get(measurement_id)
        sample = samples_by_id.get(sample_id)
        xy = xy_by_pattern_id.get(pattern_id)
        pattern_errors: list[str] = []

        if measurement is None:
            pattern_errors.append("missing_measurement_reference")
        if sample is None:
            pattern_errors.append("missing_sample_reference")
        if xy is None:
            pattern_errors.append("missing_xy_payload")
        if pattern.get("api_source_code") != "POWBASE":
            pattern_errors.append("pattern_source_not_POWBASE")
        if source_code(pattern) != "POWBASE":
            pattern_errors.append("pattern_source_ref_not_POWBASE")
        if pattern.get("data_origin") != "experimental":
            pattern_errors.append("pattern_data_origin")
        if pattern.get("modality") != "powder_xrd":
            pattern_errors.append("pattern_modality")
        if pattern.get("phase_character") != "unknown":
            pattern_errors.append("pattern_phase_character")
        if pattern.get("phase_components") != []:
            pattern_errors.append("pattern_phase_components_not_empty")
        linkage = pattern.get("structure_linkage") or {}
        if linkage.get("status") != "unlinked":
            pattern_errors.append("structure_linkage_status")
        if linkage.get("candidate_structure_ids") != []:
            pattern_errors.append("structure_linkage_candidates")

        evidence = (pattern.get("provenance") or {}).get("powbase_source_evidence") or {}
        entry_id = str(evidence.get("entry_id") or "")
        if not entry_id or entry_id not in set(local["selected_ids"]):
            pattern_errors.append("missing_or_unselected_powbase_entry")
        if evidence.get("source_modality_class") != "x-ray":
            pattern_errors.append("source_modality_not_xray")
        if evidence.get("audit_decision") != "include_verified":
            pattern_errors.append("audit_decision_not_include_verified")
        for field in (
            "raw_index_text",
            "source_sha256",
            "contained_member_sha256",
            "source_archive_file_key",
        ):
            if not evidence.get(field):
                pattern_errors.append(f"missing_provenance_{field}")

        xrd = pattern.get("xrd") or {}
        x_values = list(xrd.get("two_theta") or [])
        y_values = list(xrd.get("intensity") or [])
        point_count = xrd.get("point_count")
        if len(x_values) != len(y_values):
            pattern_errors.append("xrd_xy_length_mismatch")
        if point_count != len(x_values):
            pattern_errors.append("xrd_point_count_mismatch")
        if not finite_increasing(x_values):
            pattern_errors.append("two_theta_not_finite_increasing")
        if not finite_values(y_values):
            pattern_errors.append("intensity_not_finite")
        if (pattern.get("data") or {}).get("two_theta") != x_values:
            pattern_errors.append("data_two_theta_differs_from_xrd")
        if (pattern.get("data") or {}).get("intensity") != y_values:
            pattern_errors.append("data_intensity_differs_from_xrd")

        if sample is not None:
            if sample.get("api_source_code") != "POWBASE":
                pattern_errors.append("sample_source")
            if sample.get("formula") is not None:
                pattern_errors.append("formula_not_null")
            if sample.get("phase_character") != "unknown":
                pattern_errors.append("sample_phase_character")
            if source_id(sample) != entry_id:
                pattern_errors.append("sample_source_id_mismatch")

        if measurement is not None:
            if measurement.get("api_source_code") != "POWBASE":
                pattern_errors.append("measurement_source")
            if measurement.get("data_origin") != "experimental":
                pattern_errors.append("measurement_data_origin")
            if measurement.get("modality") != "powder_xrd":
                pattern_errors.append("measurement_modality")
            if source_id(measurement) != entry_id:
                pattern_errors.append("measurement_source_id_mismatch")
            wavelength = (measurement.get("conditions") or {}).get(
                "wavelength_angstrom"
            )
            if wavelength is not None and (
                not isinstance(wavelength, (int, float))
                or not math.isfinite(float(wavelength))
            ):
                pattern_errors.append("wavelength_not_finite_or_null")
            if measurement.get("sample_id") != sample_id:
                pattern_errors.append("measurement_sample_reference")
            if measurement.get("pattern_id") != pattern_id:
                pattern_errors.append("measurement_pattern_reference")

        if xy is not None:
            if xy.get("pattern_id") != pattern_id:
                pattern_errors.append("xy_pattern_reference")
            if xy.get("source", {}).get("code") != "POWBASE":
                pattern_errors.append("xy_source")
            if xy.get("data_origin") != "experimental":
                pattern_errors.append("xy_data_origin")
            xy_x = list((xy.get("x") or {}).get("values") or [])
            xy_y = list((xy.get("y") or {}).get("values") or [])
            if xy.get("point_count") != len(xy_x) or len(xy_x) != len(xy_y):
                pattern_errors.append("xy_point_count_mismatch")
            if xy_x != x_values or xy_y != y_values:
                pattern_errors.append("xy_payload_differs_from_pattern")

        if pattern_errors:
            errors.extend(f"{pattern_id}:{error}" for error in pattern_errors)
        record_rows.append(
            {
                "entry_id": entry_id,
                "sample_id": sample_id,
                "measurement_id": measurement_id,
                "pattern_id": pattern_id,
                "source_label_raw": sample.get("source_label_raw") if sample else "",
                "source_modality_class": evidence.get("source_modality_class", ""),
                "wavelength_angstrom": (
                    (measurement.get("conditions") or {}).get("wavelength_angstrom")
                    if measurement
                    else None
                ),
                "point_count": point_count,
                "x_length": len(x_values),
                "y_length": len(y_values),
                "xy_point_count": xy.get("point_count") if xy else None,
                "source": source_code(pattern),
                "modality": pattern.get("modality"),
                "data_origin": pattern.get("data_origin"),
                "phase_character": pattern.get("phase_character"),
                "structure_linkage": linkage.get("status"),
                "validation_status": "ok" if not pattern_errors else "failed",
                "validation_errors": json.dumps(pattern_errors, ensure_ascii=False),
            }
        )

    if set(measurements_by_id) != {
        pattern.get("measurement_id") for pattern in patterns
    }:
        errors.append("measurement_pattern_reference_set_mismatch")
    if set(xy_by_pattern_id) != pattern_ids:
        errors.append("xy_pattern_reference_set_mismatch")

    wavelength_counts = Counter(
        "known"
        if row["wavelength_angstrom"] is not None
        else "unknown"
        for row in record_rows
    )
    source_counts = Counter(row["source"] for row in record_rows)
    phase_counts = Counter(row["phase_character"] for row in record_rows)
    return {
        "counts": counts,
        "ids": {
            "samples": sorted(sample_ids),
            "measurements": sorted(measurement_ids),
            "patterns": sorted(pattern_ids),
            "xy_payloads": sorted(xy_ids),
        },
        "record_rows": record_rows,
        "errors": errors,
        "wavelength_counts": dict(wavelength_counts),
        "source_distribution": dict(source_counts),
        "phase_character_distribution": dict(phase_counts),
    }


def powbase_source_document() -> dict[str, Any]:
    return {
        "source_id": "SRC_POWBASE",
        "api_source_code": "POWBASE",
        "name": "PowBase legacy powder diffraction index",
        "short_name": "PowBase",
        "source_type": "external_legacy_index",
        "data_origin": "experimental",
        "modalities": ["powder_xrd"],
        "provenance": {
            "source": "POWBASE",
            "method": "verified_powbase_canonical_dryrun_v1",
        },
    }


def insert_documents(database: Any, local: dict[str, Any]) -> dict[str, int]:
    ensure_indexes(database)
    database.sources.insert_one(powbase_source_document())
    for collection_name in RECORD_COLLECTIONS:
        database[collection_name].insert_many(local[collection_name], ordered=True)
    return {
        "sources": database.sources.count_documents({}),
        "samples": database.samples.count_documents({}),
        "measurements": database.measurements.count_documents({}),
        "patterns": database.patterns.count_documents({}),
        "relations": database.relations.count_documents({}),
    }


def validate_database(database: Any, local: dict[str, Any]) -> dict[str, Any]:
    documents = {
        name: list(database[name].find({}, {"_id": 0}))
        for name in RECORD_COLLECTIONS
    }
    xy_payloads = [
        {
            "pattern_id": document.get("pattern_id"),
            "source": document.get("source"),
            "data_origin": document.get("data_origin"),
            "point_count": (document.get("xrd") or {}).get("point_count"),
            "x": {
                "name": "two_theta",
                "unit": "degree",
                "values": (document.get("xrd") or {}).get("two_theta") or [],
            },
            "y": {
                "name": "intensity",
                "unit": "source_native",
                "values": (document.get("xrd") or {}).get("intensity") or [],
            },
        }
        for document in documents["patterns"]
    ]
    database_local = {
        **local,
        "samples": documents["samples"],
        "measurements": documents["measurements"],
        "patterns": documents["patterns"],
        "xy": xy_payloads,
    }
    result = validate_local_documents(database_local)
    result["collection_counts"] = {
        name: database[name].count_documents({})
        for name in COLLECTIONS
    }
    result["xy_storage"] = {
        "collection": None,
        "embedded_in": "patterns.xrd and patterns.data",
        "pattern_documents_with_xy": sum(
            bool((document.get("xrd") or {}).get("has_xy"))
            for document in documents["patterns"]
        ),
    }
    result["required_field_missing_count"] = len(result["errors"])
    result["orphan_counts"] = {
        "measurements_without_samples": sum(
            document.get("sample_id") not in {
                item.get("sample_id") for item in documents["samples"]
            }
            for document in documents["measurements"]
        ),
        "patterns_without_measurements": sum(
            document.get("measurement_id") not in {
                item.get("measurement_id") for item in documents["measurements"]
            }
            for document in documents["patterns"]
        ),
        "patterns_without_samples": sum(
            document.get("sample_id") not in {
                item.get("sample_id") for item in documents["samples"]
            }
            for document in documents["patterns"]
        ),
        "xy_payloads_without_patterns": 0,
    }
    result["duplicate_primary_id_counts"] = {
        collection_name: len(documents[collection_name])
        - len(
            {
                document.get(
                    {
                        "samples": "sample_id",
                        "measurements": "measurement_id",
                        "patterns": "pattern_id",
                    }[collection_name]
                )
                for document in documents[collection_name]
            }
        )
        for collection_name in RECORD_COLLECTIONS
    }
    result["all_ids_trace_to_powbase"] = all(
        source_code(document) == "POWBASE"
        and source_id(document) in set(local["selected_ids"])
        for collection_name in RECORD_COLLECTIONS
        for document in documents[collection_name]
    )
    result["xy_payload_count"] = result["xy_storage"]["pattern_documents_with_xy"]
    result["ready_for_production_integration"] = bool(
        all(
            result["collection_counts"].get(name, 0) == EXPECTED_RECORD_COUNT
            for name in RECORD_COLLECTIONS
        )
        and result["collection_counts"].get("sources") == 1
        and result["collection_counts"].get("relations") == 0
        and not result["errors"]
        and all(value == 0 for value in result["orphan_counts"].values())
        and all(
            value == 0
            for value in result["duplicate_primary_id_counts"].values()
        )
        and result["all_ids_trace_to_powbase"]
        and result["xy_payload_count"] == EXPECTED_RECORD_COUNT
    )
    return result


CSV_FIELDS = [
    "entry_id",
    "sample_id",
    "measurement_id",
    "pattern_id",
    "source_label_raw",
    "source_modality_class",
    "source",
    "modality",
    "data_origin",
    "phase_character",
    "structure_linkage",
    "wavelength_angstrom",
    "point_count",
    "x_length",
    "y_length",
    "xy_point_count",
    "validation_status",
    "validation_errors",
]


def write_summary(path: Path, report: dict[str, Any]) -> None:
    counts = report["database_validation"]["collection_counts"]
    checks = report["database_validation"]
    duplicates = report["duplicate_review"]
    source_distribution = json.dumps(
        checks["source_distribution"],
        ensure_ascii=False,
        sort_keys=True,
    )
    phase_distribution = json.dumps(
        checks["phase_character_distribution"],
        ensure_ascii=False,
        sort_keys=True,
    )
    duplicate_evidence = json.dumps(duplicates, ensure_ascii=False)
    lines = [
        "# PowBase MongoDB Staging Validation v1",
        "",
        "This report stages only the 44 `include_verified` PowBase X-ray "
        "records into the isolated MongoDB database "
        f"`{report['database']}`. Production `crystaldb` was not written.",
        "",
        "## Database And Collections",
        "",
        f"- MongoDB database: `{report['database']}`",
        "- Canonical collections: `sources`, `samples`, `measurements`, "
        "`patterns`, and `relations`.",
        "- XY storage: embedded in `patterns.xrd` and `patterns.data`, "
        "matching the existing CrystalDB API contract. No new XY collection "
        "was invented.",
        "",
        "| Collection | Count |",
        "| --- | ---: |",
        f"| sources | {counts.get('sources', 0)} |",
        f"| samples | {counts.get('samples', 0)} |",
        f"| measurements | {counts.get('measurements', 0)} |",
        f"| patterns | {counts.get('patterns', 0)} |",
        f"| relations | {counts.get('relations', 0)} |",
        f"| pattern documents with XY | {checks['xy_payload_count']} |",
        "",
        "## Validation",
        "",
        f"- Ready for production integration: "
        f"`{str(checks['ready_for_production_integration']).lower()}`",
        f"- Validation errors: {len(checks['errors'])}",
        f"- Missing required-field/reference checks: "
        f"{checks['required_field_missing_count']}",
        f"- Orphan records: {sum(checks['orphan_counts'].values())}",
        f"- Duplicate primary IDs: "
        f"{sum(checks['duplicate_primary_id_counts'].values())}",
        f"- All IDs trace to selected PowBase entries: "
        f"`{str(checks['all_ids_trace_to_powbase']).lower()}`",
        f"- Known wavelengths: {checks['wavelength_counts'].get('known', 0)}",
        f"- Unknown wavelengths: {checks['wavelength_counts'].get('unknown', 0)}",
        f"- Source distribution: `{source_distribution}`",
        f"- Phase-character distribution: "
        f"`{phase_distribution}`",
        "",
        "## Duplicate Review",
        "",
        "Possible duplicates were preserved and not merged.",
        "- PowBase entries 66/67/68 share a normalized source label.",
        "- PowBase entry 10 has possible existing LAB label matches "
        "`Al2O3-0.5` and `Al2O3-20`.",
        "- PowBase entry 159 has a possible existing LAB label match "
        "`CaCuO2`.",
        f"- Full duplicate evidence: `{duplicate_evidence}`",
        "",
        "## Scientific Constraints",
        "",
        "- `source=POWBASE` and `data_origin=experimental` were validated "
        "after insertion.",
        "- All staged records are X-ray source records with "
        "`modality=powder_xrd`.",
        "- `phase_character=unknown` for all records.",
        "- No formulas were inferred and no structure links or relations "
        "were created.",
        "- Numeric arrays were revalidated after Mongo insertion for equal "
        "lengths, point counts, finite values, and strictly increasing "
        "2theta.",
        "",
        "No production copy or merge was performed. No source archive was "
        "modified, and no Git staging, commit, or push was performed.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def stage(
    *,
    staging_root: Path = DEFAULT_STAGING_ROOT,
    canonical_json: Path = DEFAULT_CANONICAL_JSON,
    database_name: str = DEFAULT_DATABASE,
    uri: str | None = None,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    csv_output: Path = DEFAULT_CSV_OUTPUT,
    summary_output: Path = DEFAULT_SUMMARY_OUTPUT,
) -> dict[str, Any]:
    if database_name.casefold() in FORBIDDEN_DATABASES:
        raise ValueError(f"refusing to write forbidden database {database_name!r}")
    if not database_name.casefold().startswith("crystaldb_powbase_staging_"):
        raise ValueError(
            "staging database must start with crystaldb_powbase_staging_"
        )

    local = load_local_documents(staging_root, canonical_json)
    local_validation = validate_local_documents(local)
    if local_validation["errors"]:
        raise ValueError(
            "local canonical staging failed validation: "
            + "; ".join(local_validation["errors"][:20])
        )

    mongo_uri = uri or os.environ.get(
        "CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"
    )
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        existing_databases = set(client.list_database_names())
        reset_existing = database_name in existing_databases
        if reset_existing:
            client.drop_database(database_name)
        database = client[database_name]
        inserted_counts = insert_documents(database, local)
        database_validation = validate_database(database, local)
        if not database_validation["ready_for_production_integration"]:
            raise RuntimeError(
                "MongoDB staging validation failed: "
                + "; ".join(database_validation["errors"][:20])
            )
    finally:
        client.close()

    report = {
        "schema_version": "powbase-mongodb-staging-validation-v1",
        "database": database_name,
        "uri_host": mongo_uri.rsplit("@", 1)[-1],
        "production_database": "crystaldb",
        "production_database_written": False,
        "source_archives_modified": False,
        "git_staged_committed_or_pushed": False,
        "input": {
            "staging_root": str(staging_root.resolve()),
            "canonical_json": str(canonical_json.resolve()),
        },
        "collection_conventions": {
            "canonical_collections": list(COLLECTIONS),
            "record_collections": list(RECORD_COLLECTIONS),
            "xy_collection": None,
            "xy_storage": "patterns.xrd and patterns.data",
            "relations_created": False,
        },
        "reset_existing_staging_database": reset_existing,
        "local_validation": local_validation,
        "inserted_counts": inserted_counts,
        "database_validation": database_validation,
        "duplicate_review": local["canonical"].get("potential_duplicates", {}),
        "outputs": {
            "json": str(json_output.resolve()),
            "csv": str(csv_output.resolve()),
            "summary": str(summary_output.resolve()),
        },
    }
    write_json(json_output, report)
    write_csv(csv_output, database_validation["record_rows"], CSV_FIELDS)
    write_summary(summary_output, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    parser.add_argument("--canonical-json", type=Path, default=DEFAULT_CANONICAL_JSON)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument(
        "--uri",
        default=os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"),
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_SUMMARY_OUTPUT,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = stage(
        staging_root=args.staging_root,
        canonical_json=args.canonical_json,
        database_name=args.database,
        uri=args.uri,
        json_output=args.json_output,
        csv_output=args.csv_output,
        summary_output=args.summary_output,
    )
    print(
        json.dumps(
            {
                "database": report["database"],
                "inserted_counts": report["inserted_counts"],
                "database_validation": {
                    "collection_counts": report["database_validation"][
                        "collection_counts"
                    ],
                    "xy_payload_count": report["database_validation"][
                        "xy_payload_count"
                    ],
                    "errors": report["database_validation"]["errors"],
                    "ready_for_production_integration": report[
                        "database_validation"
                    ]["ready_for_production_integration"],
                },
                "production_database_written": report[
                    "production_database_written"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"JSON: {report['outputs']['json']}")
    print(f"CSV: {report['outputs']['csv']}")
    print(f"Summary: {report['outputs']['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
