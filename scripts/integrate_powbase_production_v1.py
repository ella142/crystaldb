#!/usr/bin/env python3
"""Integrate the validated PowBase v1 records into production CrystalDB."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.stage_powbase_mongodb_v1 import (
    COLLECTIONS,
    EXPECTED_RECORD_COUNT,
    RECORD_COLLECTIONS,
    load_local_documents,
    validate_local_documents,
)

DEFAULT_STAGING_DATABASE = "crystaldb_powbase_staging_20261007"
DEFAULT_STAGING_ROOT = PROJECT_ROOT / "data" / "staging" / "powbase_canonical_v1"
DEFAULT_CANONICAL_JSON = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
)
DEFAULT_STAGING_VALIDATION = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_mongo_staging_validation_v1.json"
)
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"
DEFAULT_DATABASE = "crystaldb"
DEFAULT_JSON_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_production_integration_v1.json"
)
DEFAULT_CSV_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_production_validation_v1.csv"
)
DEFAULT_SUMMARY_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_production_summary_v1.md"
)
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
EXPECTED_DELTA = {
    "sources": 1,
    "samples": EXPECTED_RECORD_COUNT,
    "measurements": EXPECTED_RECORD_COUNT,
    "patterns": EXPECTED_RECORD_COUNT,
    "structures": 0,
    "reflection_sets": 0,
    "relations": 0,
    "refinements": 0,
    "releases": 0,
}
EXPECTED_ENTRY_IDS = [
    "4",
    "8",
    "10",
    "12",
    "13",
    "19",
    "38",
    "43",
    "45",
    "46",
    "58",
    "60",
    "66",
    "67",
    "68",
    "69",
    "71",
    "72",
    "73",
    "75",
    "76",
    "77",
    "78",
    "79",
    "80",
    "106",
    "111",
    "113",
    "116",
    "117",
    "124",
    "125",
    "126",
    "127",
    "128",
    "133",
    "140",
    "149",
    "157",
    "159",
    "160",
    "162",
    "163",
    "164",
]
ID_FIELDS = {
    "sources": "source_id",
    "samples": "sample_id",
    "measurements": "measurement_id",
    "patterns": "pattern_id",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def count_bson_documents(path: Path) -> int:
    from bson import decode_file_iter

    with path.open("rb") as stream:
        return sum(1 for _ in decode_file_iter(stream))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def backup_timestamp(backup_root: Path) -> str:
    return datetime.fromtimestamp(
        backup_root.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()


def backup_inventory(
    backup_root: Path,
    baseline_counts: dict[str, int],
) -> dict[str, Any]:
    database_root = backup_root / "crystaldb"
    errors: list[str] = []
    counts: dict[str, int] = {}
    if not database_root.is_dir():
        errors.append(f"missing backup database directory: {database_root}")
    for collection_name in BACKUP_COLLECTIONS:
        bson_path = database_root / f"{collection_name}.bson"
        metadata_path = database_root / f"{collection_name}.metadata.json"
        if not bson_path.is_file():
            errors.append(f"missing backup BSON: {bson_path.name}")
            continue
        if not metadata_path.is_file():
            errors.append(f"missing backup metadata: {metadata_path.name}")
        counts[collection_name] = count_bson_documents(bson_path)
        expected_count = baseline_counts.get(collection_name)
        if expected_count is not None and counts[collection_name] != expected_count:
            errors.append(
                f"backup count mismatch for {collection_name}: "
                f"backup={counts[collection_name]} "
                f"production={expected_count}"
            )
    return {
        "path": str(backup_root.resolve()),
        "database": "crystaldb",
        "timestamp_utc": backup_timestamp(backup_root),
        "collection_counts": counts,
        "errors": errors,
        "complete": not errors and (backup_root / "crystaldb" / "prelude.json").is_file(),
    }


def collection_counts(database: Any) -> dict[str, int]:
    return {
        collection_name: database[collection_name].count_documents({})
        for collection_name in BACKUP_COLLECTIONS
    }


def source_ref_code(document: dict[str, Any]) -> str | None:
    source = document.get("source")
    if isinstance(source, dict):
        return str(source.get("code") or "").upper() or None
    if isinstance(source, str):
        return source.upper()
    return None


def source_ref_id(document: dict[str, Any]) -> str | None:
    source = document.get("source")
    if isinstance(source, dict):
        value = source.get("source_id")
        return str(value) if value not in (None, "") else None
    return None


def without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return {key: value for key, value in document.items() if key != "_id"}


def load_staging_database(
    client: MongoClient,
    staging_database_name: str,
    selected_entry_ids: set[str],
) -> dict[str, Any]:
    database = client[staging_database_name]
    if not database.list_collection_names():
        raise ValueError(f"staging database is empty: {staging_database_name}")
    documents = {
        collection_name: [
            without_mongo_id(document)
            for document in database[collection_name].find({}, {"_id": 0})
        ]
        for collection_name in RECORD_COLLECTIONS
    }
    source_documents = [
        without_mongo_id(document)
        for document in database.sources.find({}, {"_id": 0})
    ]
    if len(source_documents) != 1:
        raise ValueError(f"expected one staging source document, found {len(source_documents)}")
    if len(database.relations.distinct("relation_id")) != 0:
        raise ValueError("staging database contains relations")
    if set(
        str(
            (document.get("source") or {}).get("source_id")
            or ""
        )
        for document in documents["samples"]
    ) != selected_entry_ids:
        raise ValueError("staging sample source IDs do not match selected entries")
    return {
        **documents,
        "sources": source_documents,
        "xy": [
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
        ],
        "selected_ids": sorted(selected_entry_ids),
    }


def compare_staging_to_canonical(
    staging_root: Path,
    canonical_json: Path,
    selected_entry_ids: set[str],
) -> dict[str, Any]:
    local = load_local_documents(staging_root, canonical_json)
    if set(local["selected_ids"]) != selected_entry_ids:
        raise ValueError("local staging IDs differ from expected inclusion IDs")
    local_validation = validate_local_documents(local)
    if local_validation["errors"]:
        raise ValueError(
            "local staging validation failed: "
            + "; ".join(local_validation["errors"][:20])
        )

    canonical_by_entry = {
        str(record["entry_id"]): record
        for record in local["canonical"].get("records") or []
    }
    discrepancies: list[str] = []
    for entry_id in sorted(selected_entry_ids):
        record = canonical_by_entry.get(entry_id)
        if record is None:
            discrepancies.append(f"missing canonical record {entry_id}")
            continue
        for collection_name, key in (
            ("samples", "sample"),
            ("measurements", "measurement"),
            ("patterns", "pattern"),
            ("xy", "pattern_xy"),
        ):
            identifier = {
                "samples": record["sample_id"],
                "measurements": record["measurement_id"],
                "patterns": record["pattern_id"],
                "xy": record["pattern_id"],
            }[collection_name]
            if collection_name == "xy":
                path = staging_root / "xy" / f"{identifier}.json"
            else:
                path = (
                    staging_root
                    / "records"
                    / collection_name
                    / f"{identifier}.json"
                )
            actual = read_json(path)
            if actual != record[key]:
                discrepancies.append(
                    f"{entry_id}:{collection_name} differs from canonical dry-run"
                )
    return {
        "selected_entry_count": len(selected_entry_ids),
        "canonical_record_count": len(canonical_by_entry),
        "discrepancies": discrepancies,
        "match": not discrepancies,
        "local_validation": local_validation,
    }


def compare_staging_database_to_local(
    staging_root: Path,
    canonical_json: Path,
    staging_documents: dict[str, Any],
) -> dict[str, Any]:
    local = load_local_documents(staging_root, canonical_json)
    discrepancies: list[str] = []
    for collection_name in RECORD_COLLECTIONS:
        id_field = ID_FIELDS[collection_name]
        local_by_id = {
            document[id_field]: document
            for document in local[collection_name]
        }
        database_by_id = {
            document[id_field]: document
            for document in staging_documents[collection_name]
        }
        if set(local_by_id) != set(database_by_id):
            discrepancies.append(f"{collection_name}: ID set differs")
            continue
        for identifier in sorted(local_by_id):
            if local_by_id[identifier] != database_by_id[identifier]:
                discrepancies.append(
                    f"{collection_name}:{identifier} differs from staging database"
                )
    local_source = local["canonical"].get("records") or []
    if len(local_source) != EXPECTED_RECORD_COUNT:
        discrepancies.append(
            f"canonical record count={len(local_source)} "
            f"expected={EXPECTED_RECORD_COUNT}"
        )
    return {
        "discrepancies": discrepancies,
        "match": not discrepancies,
    }


def expected_source_document(staging_documents: dict[str, Any]) -> dict[str, Any]:
    source_documents = staging_documents["sources"]
    source = source_documents[0]
    if source.get("api_source_code") != "POWBASE":
        raise ValueError("staging source document is not POWBASE")
    return source


def existing_powbase_documents(
    production: Any,
    staging_documents: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    source = expected_source_document(staging_documents)
    result["source"] = without_mongo_id(
        production.sources.find_one({"source_id": source["source_id"]}, {"_id": 0})
    )
    for collection_name in RECORD_COLLECTIONS:
        id_field = ID_FIELDS[collection_name]
        values = [
            document[id_field]
            for document in staging_documents[collection_name]
        ]
        result[collection_name] = [
            without_mongo_id(document)
            for document in production[collection_name].find(
                {id_field: {"$in": values}},
                {"_id": 0},
            )
        ]
    result["powbase_source_records"] = [
        without_mongo_id(document)
        for document in production.sources.find(
            {
                "$or": [
                    {"api_source_code": "POWBASE"},
                    {"source": "POWBASE"},
                ]
            },
            {"_id": 0},
        )
    ]
    return result


def collision_preflight(
    existing: dict[str, Any],
    staging_documents: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    exact_existing: dict[str, int] = {}
    new_documents: dict[str, int] = {}

    expected_source = expected_source_document(staging_documents)
    existing_source = existing["source"]
    if existing_source is not None:
        if existing_source != expected_source:
            errors.append("existing POWBASE source document differs from staging")
        else:
            exact_existing["sources"] = 1
    else:
        new_documents["sources"] = 1

    if len(existing["powbase_source_records"]) > 1:
        errors.append("more than one existing POWBASE source record")
    elif existing["powbase_source_records"] and (
        existing["powbase_source_records"][0] != expected_source
    ):
        errors.append("existing POWBASE source record conflicts with staging")

    for collection_name in RECORD_COLLECTIONS:
        existing_by_id = {
            document[ID_FIELDS[collection_name]]: document
            for document in existing[collection_name]
        }
        staging_by_id = {
            document[ID_FIELDS[collection_name]]: document
            for document in staging_documents[collection_name]
        }
        exact_count = 0
        new_count = 0
        for identifier, document in staging_by_id.items():
            existing_document = existing_by_id.get(identifier)
            if existing_document is None:
                new_count += 1
            elif existing_document == document:
                exact_count += 1
            else:
                errors.append(
                    f"{collection_name}:{identifier} existing document differs"
                )
        exact_existing[collection_name] = exact_count
        new_documents[collection_name] = new_count

    return {
        "errors": errors,
        "exact_existing": exact_existing,
        "new_documents": new_documents,
        "idempotent_exact_matches": not errors,
        "safe_to_write": not errors,
    }


def apply_documents(
    production: Any,
    staging_documents: dict[str, Any],
) -> dict[str, int]:
    write_counts = {"sources": 0, "samples": 0, "measurements": 0, "patterns": 0}
    source = expected_source_document(staging_documents)
    if production.sources.find_one({"source_id": source["source_id"]}) is None:
        production.sources.insert_one(source)
        write_counts["sources"] = 1
    for collection_name in RECORD_COLLECTIONS:
        id_field = ID_FIELDS[collection_name]
        for document in staging_documents[collection_name]:
            identifier = document[id_field]
            if production[collection_name].find_one(
                {id_field: identifier},
                {"_id": 1},
            ) is None:
                production[collection_name].insert_one(document)
                write_counts[collection_name] += 1
    return write_counts


def production_subset(production: Any, staging_documents: dict[str, Any]) -> dict[str, Any]:
    documents = {
        collection_name: []
        for collection_name in RECORD_COLLECTIONS
    }
    for collection_name in RECORD_COLLECTIONS:
        id_field = ID_FIELDS[collection_name]
        values = [
            document[id_field]
            for document in staging_documents[collection_name]
        ]
        documents[collection_name] = [
            without_mongo_id(document)
            for document in production[collection_name].find(
                {id_field: {"$in": values}},
                {"_id": 0},
            )
        ]
    documents["xy"] = [
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
    documents["selected_ids"] = staging_documents["selected_ids"]
    return documents


def validate_production(
    production: Any,
    staging_documents: dict[str, Any],
) -> dict[str, Any]:
    subset = production_subset(production, staging_documents)
    validation = validate_local_documents(subset)
    validation["powbase_counts"] = {
        "sources": production.sources.count_documents({"api_source_code": "POWBASE"}),
        "samples": production.samples.count_documents(
            {"api_source_code": "POWBASE"}
        ),
        "measurements": production.measurements.count_documents(
            {"api_source_code": "POWBASE"}
        ),
        "patterns": production.patterns.count_documents(
            {"api_source_code": "POWBASE"}
        ),
    }
    validation["powbase_relations"] = production.relations.count_documents(
        {
            "$or": [
                {"subject_id": {"$regex": r"^POWBASE_"}},
                {"object_id": {"$regex": r"^POWBASE_"}},
                {"api_source_code": "POWBASE"},
            ]
        }
    )
    sample_ids = {
        document.get("sample_id")
        for document in subset["samples"]
    }
    measurement_ids = {
        document.get("measurement_id")
        for document in subset["measurements"]
    }
    validation["orphan_counts"] = {
        "measurements_without_samples": sum(
            document.get("sample_id") not in sample_ids
            for document in subset["measurements"]
        ),
        "patterns_without_measurements": sum(
            document.get("measurement_id") not in measurement_ids
            for document in subset["patterns"]
        ),
        "patterns_without_samples": sum(
            document.get("sample_id") not in sample_ids
            for document in subset["patterns"]
        ),
        "xy_payloads_without_patterns": 0,
    }
    validation["duplicate_primary_id_counts"] = {
        collection_name: len(subset[collection_name])
        - len(
            {
                document.get(ID_FIELDS[collection_name])
                for document in subset[collection_name]
            }
        )
        for collection_name in RECORD_COLLECTIONS
    }
    validation["known_wavelength_count"] = sum(
        row["wavelength_angstrom"] is not None
        for row in validation["record_rows"]
    )
    validation["unknown_wavelength_count"] = sum(
        row["wavelength_angstrom"] is None
        for row in validation["record_rows"]
    )
    validation["phase_character_unknown_count"] = sum(
        row["phase_character"] == "unknown"
        for row in validation["record_rows"]
    )
    validation["source_powbase_pattern_count"] = sum(
        row["source"] == "POWBASE"
        for row in validation["record_rows"]
    )
    validation["xy_payload_count"] = validation["counts"]["xy_payloads"]
    validation["ready"] = bool(
        validation["powbase_counts"]
        == {
            "sources": 1,
            "samples": EXPECTED_RECORD_COUNT,
            "measurements": EXPECTED_RECORD_COUNT,
            "patterns": EXPECTED_RECORD_COUNT,
        }
        and validation["powbase_relations"] == 0
        and validation["known_wavelength_count"] == 6
        and validation["unknown_wavelength_count"] == 38
        and validation["phase_character_unknown_count"] == EXPECTED_RECORD_COUNT
        and validation["source_powbase_pattern_count"] == EXPECTED_RECORD_COUNT
        and not validation["errors"]
        and all(value == 0 for value in validation["orphan_counts"].values())
        and all(
            value == 0
            for value in validation["duplicate_primary_id_counts"].values()
        )
    )
    return validation


def archive_hash_verification(archive_root: Path) -> dict[str, Any]:
    inventory_path = archive_root / "inventory" / "powbase_archive_inventory.jsonl"
    records = [
        json.loads(line)
        for line in inventory_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    mismatches: list[str] = []
    missing: list[str] = []
    for record in records:
        path = archive_root / "archives" / record["source_filename"]
        if not path.is_file():
            missing.append(str(record["entry_id"]))
            continue
        if sha256_file(path) != record["source_sha256"]:
            mismatches.append(str(record["entry_id"]))
    return {
        "archives_checked": len(records),
        "missing_entries": missing,
        "sha256_mismatches": mismatches,
        "all_byte_identical_to_inventory": not missing and not mismatches,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, report: dict[str, Any]) -> None:
    baseline = report["production_baseline_counts"]
    final = report["production_final_counts"]
    delta = report["production_delta"]
    validation = report["post_write_validation"]
    backup = report["backup"]
    lines = [
        "# PowBase Production Integration v1",
        "",
        "Integrated exactly the 44 validated PowBase X-ray records into "
        "production `crystaldb`. Conditional, unresolved, neutron, and "
        "metadata-conflict records were excluded.",
        "",
        "## Backup",
        "",
        f"- Backup path: `{backup['path']}`",
        f"- Backup timestamp (UTC): `{backup['timestamp_utc']}`",
        f"- Backup complete: `{str(backup['complete']).lower()}`",
        f"- Backup errors: {len(backup['errors'])}",
        "",
        "## Production Counts",
        "",
        "| Collection | Before | Inserted | After | Delta |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for collection_name in BACKUP_COLLECTIONS:
        lines.append(
            f"| {collection_name} | {baseline[collection_name]} | "
            f"{report['inserted_counts'].get(collection_name, 0)} | "
            f"{final[collection_name]} | {delta[collection_name]} |"
        )
    lines.extend(
        [
            "",
            "## Post-Write Validation",
            "",
            f"- PowBase source records: "
            f"{validation['powbase_counts']['sources']}",
            f"- PowBase samples: {validation['powbase_counts']['samples']}",
            f"- PowBase measurements: "
            f"{validation['powbase_counts']['measurements']}",
            f"- PowBase patterns: {validation['powbase_counts']['patterns']}",
            f"- Embedded XY payloads: {validation['xy_payload_count']}",
            f"- PowBase relations: {validation['powbase_relations']}",
            f"- Known wavelengths: {validation['known_wavelength_count']}",
            f"- Unknown wavelengths: {validation['unknown_wavelength_count']}",
            f"- `phase_character=unknown`: "
            f"{validation['phase_character_unknown_count']}",
            f"- Pattern source `POWBASE`: "
            f"{validation['source_powbase_pattern_count']}",
            f"- Orphans: {sum(validation['orphan_counts'].values())}",
            f"- Duplicate IDs: "
            f"{sum(validation['duplicate_primary_id_counts'].values())}",
            f"- Validation errors: {len(validation['errors'])}",
            f"- Integration passed: `{str(report['integration_passed']).lower()}`",
            "",
            "## Provenance And Review Signals",
            "",
            "- PowBase entry IDs, raw index metadata, archive/member names and "
            "hashes, parsing method, and v1 decision remain in pattern "
            "provenance.",
            "- `phase_character` remains `unknown`; no formulas, CIF links, "
            "structure records, or relations were added.",
            "- Entries 66/67/68 and the LAB label matches for entries 10 and "
            "159 were preserved as review signals; no label-based deduplication "
            "was performed.",
            "",
            "## Included Entry IDs",
            "",
            ", ".join(report["included_entry_ids"]),
            "",
            f"Archive hash verification: "
            f"{report['archive_hash_verification']['archives_checked']} archives "
            f"checked; all byte-identical to inventory = "
            f"`{str(report['archive_hash_verification']['all_byte_identical_to_inventory']).lower()}`.",
            "",
            "No conditional records were added. No COD/CIF matching, public "
            "release update, manuscript update, Git staging, commit, or push "
            "was performed.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def integrate(
    *,
    backup_root: Path,
    staging_root: Path = DEFAULT_STAGING_ROOT,
    canonical_json: Path = DEFAULT_CANONICAL_JSON,
    staging_validation_json: Path = DEFAULT_STAGING_VALIDATION,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    database_name: str = DEFAULT_DATABASE,
    staging_database_name: str = DEFAULT_STAGING_DATABASE,
    uri: str | None = None,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    csv_output: Path = DEFAULT_CSV_OUTPUT,
    summary_output: Path = DEFAULT_SUMMARY_OUTPUT,
    allow_write: bool = False,
) -> dict[str, Any]:
    if not allow_write:
        raise ValueError("production integration requires allow_write=True")
    if database_name.casefold() != "crystaldb":
        raise ValueError("production database must be exactly 'crystaldb'")
    if staging_database_name.casefold() == database_name.casefold():
        raise ValueError("staging and production databases must differ")
    if not backup_root.is_dir():
        raise FileNotFoundError(f"backup directory does not exist: {backup_root}")

    mongo_uri = uri or os.environ.get(
        "CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"
    )
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        staging_report = read_json(staging_validation_json)
        if staging_report.get("database") != staging_database_name:
            raise ValueError("staging validation report database mismatch")
        if not staging_report.get("database_validation", {}).get(
            "ready_for_production_integration"
        ):
            raise ValueError("staging validation report is not ready")
        if staging_report.get("database_validation", {}).get("errors"):
            raise ValueError("staging validation report contains errors")

        selected_entry_ids = set(EXPECTED_ENTRY_IDS)
        canonical_comparison = compare_staging_to_canonical(
            staging_root,
            canonical_json,
            selected_entry_ids,
        )
        if not canonical_comparison["match"]:
            raise ValueError(
                "staging/canonical discrepancy: "
                + "; ".join(canonical_comparison["discrepancies"][:20])
            )
        staging_documents = load_staging_database(
            client,
            staging_database_name,
            selected_entry_ids,
        )
        staging_database_comparison = compare_staging_database_to_local(
            staging_root,
            canonical_json,
            staging_documents,
        )
        if not staging_database_comparison["match"]:
            raise ValueError(
                "staging database/local discrepancy: "
                + "; ".join(staging_database_comparison["discrepancies"][:20])
            )
        staging_validation = validate_local_documents(staging_documents)
        if staging_validation["errors"]:
            raise ValueError(
                "staging database records failed validation: "
                + "; ".join(staging_validation["errors"][:20])
            )

        production = client[database_name]
        pre_write_counts = collection_counts(production)
        backup = backup_inventory(backup_root, {})
        if not backup["complete"]:
            raise RuntimeError(
                "backup validation failed: "
                + "; ".join(backup["errors"][:20])
            )
        baseline_counts = backup["collection_counts"]
        pre_write_state_errors = []
        for collection_name in BACKUP_COLLECTIONS:
            allowed_counts = {
                baseline_counts[collection_name],
                baseline_counts[collection_name] + EXPECTED_DELTA[collection_name],
            }
            if pre_write_counts[collection_name] not in allowed_counts:
                pre_write_state_errors.append(
                    f"{collection_name}: current={pre_write_counts[collection_name]} "
                    f"allowed={sorted(allowed_counts)}"
                )
        if pre_write_state_errors:
            raise RuntimeError(
                "production state is neither pre-integration nor expected "
                "post-integration: " + "; ".join(pre_write_state_errors)
            )

        existing = existing_powbase_documents(production, staging_documents)
        collision = collision_preflight(existing, staging_documents)
        if not collision["safe_to_write"]:
            raise RuntimeError(
                "production collision preflight failed: "
                + "; ".join(collision["errors"][:20])
            )

        inserted_counts = {
            collection_name: 0
            for collection_name in BACKUP_COLLECTIONS
        }
        if any(collision["new_documents"].values()):
            writes = apply_documents(production, staging_documents)
            inserted_counts.update(writes)

        final_counts = collection_counts(production)
        current_run_delta = {
            collection_name: final_counts[collection_name]
            - pre_write_counts[collection_name]
            for collection_name in BACKUP_COLLECTIONS
        }
        unexpected_collections = sorted(
            set(production.list_collection_names())
            - set(BACKUP_COLLECTIONS)
        )
        expected_delta_for_run = {
            collection_name: collision["new_documents"].get(collection_name, 0)
            for collection_name in BACKUP_COLLECTIONS
        }
        unexpected_delta = {
            collection_name: value
            for collection_name, value in current_run_delta.items()
            if value != expected_delta_for_run[collection_name]
        }
        total_delta = {
            collection_name: final_counts[collection_name]
            - baseline_counts[collection_name]
            for collection_name in BACKUP_COLLECTIONS
        }
        unexpected_total_delta = {
            collection_name: value
            for collection_name, value in total_delta.items()
            if value != EXPECTED_DELTA[collection_name]
        }
        post_write = validate_production(production, staging_documents)
        archive_verification = archive_hash_verification(archive_root)
        integration_passed = bool(
            not unexpected_delta
            and not unexpected_total_delta
            and not unexpected_collections
            and post_write["ready"]
            and archive_verification["all_byte_identical_to_inventory"]
            and inserted_counts["sources"] in {0, 1}
            and inserted_counts["samples"] in {0, EXPECTED_RECORD_COUNT}
            and inserted_counts["measurements"] in {0, EXPECTED_RECORD_COUNT}
            and inserted_counts["patterns"] in {0, EXPECTED_RECORD_COUNT}
        )
        if not integration_passed:
            raise RuntimeError(
                "post-write production validation failed; "
                f"unexpected_delta={unexpected_delta}, "
                f"post_write_errors={post_write['errors']}"
            )
    finally:
        client.close()

    report = {
        "schema_version": "powbase-production-integration-v1",
        "generated_at_utc": utc_now(),
        "database": database_name,
        "staging_database": staging_database_name,
        "production_database_written": True,
        "conditional_records_added": 0,
        "unresolved_records_added": 0,
        "neutron_records_added": 0,
        "metadata_conflict_records_added": 0,
        "backup": backup,
        "production_baseline_counts": baseline_counts,
        "pre_write_counts": pre_write_counts,
        "write_operation_counts": inserted_counts,
        "inserted_counts": total_delta,
        "production_final_counts": final_counts,
        "production_delta": total_delta,
        "current_run_delta": current_run_delta,
        "unexpected_delta": unexpected_delta,
        "unexpected_total_delta": unexpected_total_delta,
        "pre_write_state_errors": pre_write_state_errors,
        "canonical_comparison": canonical_comparison,
        "staging_database_comparison": staging_database_comparison,
        "staging_validation": staging_validation,
        "collision_preflight": collision,
        "post_write_validation": post_write,
        "archive_hash_verification": archive_verification,
        "included_entry_ids": EXPECTED_ENTRY_IDS,
        "expected_delta_for_run": expected_delta_for_run,
        "unexpected_collections": unexpected_collections,
        "duplicate_review": staging_report.get("duplicate_review", {}),
        "integration_passed": integration_passed,
        "git_changes_staged_committed_or_pushed": False,
        "outputs": {
            "json": str(json_output.resolve()),
            "csv": str(csv_output.resolve()),
            "summary": str(summary_output.resolve()),
        },
    }
    write_json(json_output, report)
    write_csv(csv_output, post_write["record_rows"])
    write_summary(summary_output, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    parser.add_argument("--canonical-json", type=Path, default=DEFAULT_CANONICAL_JSON)
    parser.add_argument(
        "--staging-validation-json",
        type=Path,
        default=DEFAULT_STAGING_VALIDATION,
    )
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument(
        "--staging-database",
        default=DEFAULT_STAGING_DATABASE,
    )
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
    parser.add_argument(
        "--allow-production-write",
        action="store_true",
        help="Required explicit acknowledgement for the production write.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = integrate(
        backup_root=args.backup_root,
        staging_root=args.staging_root,
        canonical_json=args.canonical_json,
        staging_validation_json=args.staging_validation_json,
        archive_root=args.archive_root,
        database_name=args.database,
        staging_database_name=args.staging_database,
        uri=args.uri,
        json_output=args.json_output,
        csv_output=args.csv_output,
        summary_output=args.summary_output,
        allow_write=args.allow_production_write,
    )
    print(
        json.dumps(
            {
                "database": report["database"],
                "backup": report["backup"],
                "baseline_counts": report["production_baseline_counts"],
                "inserted_counts": report["inserted_counts"],
                "final_counts": report["production_final_counts"],
                "delta": report["production_delta"],
                "unexpected_delta": report["unexpected_delta"],
                "post_write_ready": report["post_write_validation"]["ready"],
                "archive_hashes_ok": report["archive_hash_verification"][
                    "all_byte_identical_to_inventory"
                ],
                "integration_passed": report["integration_passed"],
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
