#!/usr/bin/env python3
"""Integrate the 75 final-validated PowBase X-ray records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import decode_file_iter
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_powbase import (
    collect_fullprof_metadata,
    collect_numeric_rows,
    collect_text_metadata,
    find_intensity_header_and_block,
)
from scripts.audit_powbase_unresolved_rescue_v1 import _decode_for_rescue
from scripts.prepare_powbase_canonical_v1 import (
    _independent_numeric_block,
    _numeric_value,
    axis_and_qc,
    build_documents,
    explicit_wavelengths,
    select_wavelength,
)
from scripts.validate_powbase_candidate_canonical_v1 import (
    _archive_member,
    _parse_candidate_profile,
    _validate_document_shape,
    build_validation,
)

ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"
ARCHIVE_DIR = ARCHIVE_ROOT / "archives"
INCLUSION_PATH = PROJECT_ROOT / "data" / "mappings" / "powbase_v1_inclusion_manifest.csv"
FAST_PATH = PROJECT_ROOT / "data" / "mappings" / "powbase_fast_conditional_review_v1.csv"
RESCUE_PATH = PROJECT_ROOT / "data" / "mappings" / "powbase_unresolved_rescue_audit_v1.csv"
DEEP_PATH = PROJECT_ROOT / "powbase_deep_rescue_v1.csv"
CANONICAL_PATH = PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "mappings"
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "backups" / "powbase_final_xray_pre_integration_20261007_194415"

FINALIZED_IDS = ["15", "74", "121", "156"]
ALL_COLLECTIONS = [
    "sources",
    "samples",
    "measurements",
    "patterns",
    "structures",
    "reflection_sets",
    "relations",
    "refinements",
    "releases",
]
ID_FIELDS = {
    "samples": "sample_id",
    "measurements": "measurement_id",
    "patterns": "pattern_id",
}


def read_csv_map(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["entry_id"]: row for row in csv.DictReader(handle)}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return {key: value for key, value in document.items() if key != "_id"}


def collection_counts(database: Any) -> dict[str, int]:
    return {
        collection: database[collection].count_documents({})
        for collection in ALL_COLLECTIONS
    }


def backup_counts(backup_root: Path) -> dict[str, int]:
    database_root = backup_root / "crystaldb"
    counts: dict[str, int] = {}
    for collection in ALL_COLLECTIONS:
        bson_path = database_root / f"{collection}.bson"
        metadata_path = database_root / f"{collection}.metadata.json"
        if not bson_path.is_file() or not metadata_path.is_file():
            raise RuntimeError(f"backup is missing {collection} BSON or metadata")
        with bson_path.open("rb") as stream:
            counts[collection] = sum(1 for _ in decode_file_iter(stream))
    return counts


def archive_member(path: Path) -> tuple[str, bytes, str]:
    raw = path.read_bytes()
    try:
        with zipfile.ZipFile(path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if len(infos) != 1:
                raise RuntimeError(
                    f"{path.name}: expected one data member, found {len(infos)}"
                )
            info = infos[0]
            return info.filename, archive.read(info), "zip"
    except zipfile.BadZipFile:
        return path.name, raw, "plain_text"


def validate_document(
    document: dict[str, Any],
    *,
    entry_id: str,
    source_row: dict[str, str],
    archive_sha: str,
    member_sha: str,
    expected_count: int,
    wavelength_records: list[dict[str, Any]],
    canonical_pattern_keys: set[str],
) -> list[str]:
    errors = _validate_document_shape(document, canonical_pattern_keys)
    expected_ids = {
        "sample_id": f"POWBASE_SAM_{entry_id}",
        "measurement_id": f"POWBASE_MEAS_{entry_id}",
        "pattern_id": f"POWBASE_PAT_{entry_id}",
    }
    for field, expected in expected_ids.items():
        if document[field] != expected:
            errors.append(f"{field} does not match canonical PowBase ID")

    sample = document["sample"]
    measurement = document["measurement"]
    pattern = document["pattern"]
    xy = document["pattern_xy"]
    if sample.get("formula") is not None:
        errors.append("formula is populated")
    if sample.get("phase_character") != "unknown":
        errors.append("sample phase_character is not unknown")
    if pattern.get("phase_character") != "unknown":
        errors.append("pattern phase_character is not unknown")
    if (pattern.get("structure_linkage") or {}).get("status") != "unlinked":
        errors.append("structure linkage is not unlinked")

    for name, value in (
        ("sample", sample),
        ("measurement", measurement),
        ("pattern", pattern),
        ("xy", xy),
    ):
        source = value.get("source") or {}
        if source.get("code") != "POWBASE" or str(source.get("source_id")) != entry_id:
            errors.append(f"{name} source reference is not POWBASE/{entry_id}")
        provenance = value.get("provenance") or {}
        if provenance.get("source") != "POWBASE" or str(provenance.get("source_id")) != entry_id:
            errors.append(f"{name} provenance source is not POWBASE/{entry_id}")
        evidence = provenance.get("powbase_source_evidence") or {}
        if evidence.get("source_sha256") != archive_sha:
            errors.append(f"{name} archive SHA256 provenance mismatch")
        if evidence.get("contained_member_sha256") != member_sha:
            errors.append(f"{name} member SHA256 provenance mismatch")
        if evidence.get("raw_index_text") != source_row["raw_index_text"]:
            errors.append(f"{name} raw index provenance mismatch")

    xrd = pattern.get("xrd") or {}
    if xrd.get("point_count") != expected_count:
        errors.append("pattern point_count mismatch")
    if len(xrd.get("two_theta") or []) != expected_count:
        errors.append("pattern 2theta length mismatch")
    if len(xrd.get("intensity") or []) != expected_count:
        errors.append("pattern intensity length mismatch")
    if xy.get("point_count") != expected_count:
        errors.append("XY point_count mismatch")
    if len((xy.get("x") or {}).get("values") or []) != expected_count:
        errors.append("XY x length mismatch")
    if len((xy.get("y") or {}).get("values") or []) != expected_count:
        errors.append("XY y length mismatch")
    if (xy.get("x") or {}).get("values") != xrd.get("two_theta"):
        errors.append("XY x payload differs from pattern axis")
    if (xy.get("y") or {}).get("values") != xrd.get("intensity"):
        errors.append("XY y payload differs from pattern intensities")

    radiation = pattern.get("radiation") or {}
    conditions = measurement.get("conditions") or {}
    if radiation.get("wavelength_angstrom") != conditions.get("wavelength_angstrom"):
        errors.append("primary wavelength differs between pattern and measurement")
    if radiation.get("wavelength_kalpha2_angstrom") != conditions.get(
        "wavelength_kalpha2_angstrom"
    ):
        errors.append("secondary wavelength differs between pattern and measurement")
    source_wavelengths = [record["value"] for record in wavelength_records]
    embedded_wavelengths = [
        record["value"]
        for record in (
            (
                (pattern.get("provenance") or {})
                .get("powbase_source_evidence") or {}
            )
            .get("embedded_metadata", {})
            .get("source_wavelength_records", [])
        )
    ]
    if embedded_wavelengths != source_wavelengths:
        errors.append("explicit wavelength provenance was not preserved")
    selected_wavelengths = [
        value
        for value in (
            radiation.get("wavelength_angstrom"),
            radiation.get("wavelength_kalpha2_angstrom"),
        )
        if value is not None
    ]
    if selected_wavelengths != source_wavelengths[: len(selected_wavelengths)]:
        errors.append("canonical wavelength fields contain non-source values")
    return sorted(set(errors))


def build_finalized_documents(
    inclusion: dict[str, dict[str, str]],
    fast: dict[str, dict[str, str]],
    rescue: dict[str, dict[str, str]],
    canonical_pattern_keys: set[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    validation = build_validation(inspect_mongo=False)
    if validation["summary"]["all_pass"] is not True:
        raise RuntimeError("four-entry canonical validation is not all PASS")
    validation_by_id = {row["entry_id"]: row for row in validation["records"]}
    documents: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}

    for entry_id in FINALIZED_IDS:
        row = dict(inclusion[entry_id])
        archive_path = ARCHIVE_DIR / row["source_filename"]
        member_filename, member_raw, archive_sha, member_sha = _archive_member(
            archive_path
        )
        hashes[entry_id] = archive_sha
        text, encoding, nul_count, decode_note = _decode_for_rescue(member_raw)
        if text is None:
            raise RuntimeError(f"entry {entry_id}: unreadable source member")
        profile = _parse_candidate_profile(
            entry_id,
            text,
            fast.get(entry_id),
            rescue.get(entry_id),
        )
        row["detected_content_family"] = profile["detected_content_family"]
        fullprof = collect_fullprof_metadata(text)
        text_metadata = collect_text_metadata(text)
        index_tokens = json.loads(row["raw_hash_delimited_tokens"])
        wavelength_records = explicit_wavelengths(
            index_tokens=index_tokens,
            text=text,
            fullprof=fullprof,
        )
        wavelength, wavelength_secondary, wavelength_notes = select_wavelength(
            wavelength_records
        )
        if wavelength_notes:
            raise RuntimeError(f"entry {entry_id}: {wavelength_notes}")
        document = build_documents(
            row,
            archive_path=archive_path,
            member_filename=member_filename,
            archive_sha256=archive_sha,
            member_sha256=member_sha,
            text=text,
            axis=profile["axis"],
            intensities=profile["intensities"],
            start=profile["start"],
            step=profile["step"],
            end=profile["end"],
            expected_count=profile["expected_point_count"],
            qc=profile["qc"],
            wavelength_records=wavelength_records,
            wavelength=wavelength,
            wavelength_secondary=wavelength_secondary,
            fullprof=fullprof,
            text_metadata=text_metadata,
            independent_parser={
                "encoding": encoding,
                "nul_byte_count": nul_count,
                "decode_note": decode_note,
                "header_line_number": profile["recovery_rule_evidence"].get(
                    "header_line_number"
                ),
                "intensity_token_count": profile["independent_parser_count"],
            },
        )
        expected_count = int(validation_by_id[entry_id]["canonical_point_count"])
        errors = validate_document(
            document,
            entry_id=entry_id,
            source_row=row,
            archive_sha=archive_sha,
            member_sha=member_sha,
            expected_count=expected_count,
            wavelength_records=wavelength_records,
            canonical_pattern_keys=canonical_pattern_keys,
        )
        if errors:
            raise RuntimeError(f"entry {entry_id}: {errors}")
        documents.append(document)
    return documents, hashes


def build_deep_documents(
    inclusion: dict[str, dict[str, str]],
    deep: dict[str, dict[str, str]],
    canonical_pattern_keys: set[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    promoted_ids = sorted(
        [
            entry_id
            for entry_id, row in deep.items()
            if row["final_status"] == "promote_verified"
        ],
        key=int,
    )
    if len(promoted_ids) != 71:
        raise RuntimeError(f"expected 71 promoted deep-rescue records, found {len(promoted_ids)}")
    if set(promoted_ids) & (set(FINALIZED_IDS) | {"36", "114"}):
        raise RuntimeError("deep-rescue scope contains finalized or excluded entries")

    documents: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for entry_id in promoted_ids:
        row = dict(inclusion[entry_id])
        review = deep[entry_id]
        archive_path = ARCHIVE_DIR / row["source_filename"]
        archive_raw = archive_path.read_bytes()
        archive_sha = sha256_bytes(archive_raw)
        if archive_sha != row["source_sha256"] or archive_sha != review["source_sha256"]:
            raise RuntimeError(f"entry {entry_id}: source SHA256 differs from review")
        member_filename, member_raw, container_type = archive_member(archive_path)
        member_sha = sha256_bytes(member_raw)
        hashes[entry_id] = archive_sha
        text, encoding, nul_count, decode_note = _decode_for_rescue(member_raw)
        if text is None:
            raise RuntimeError(f"entry {entry_id}: unreadable source member")
        detected = find_intensity_header_and_block(text)
        if not detected.get("header_found"):
            raise RuntimeError(f"entry {entry_id}: diffraction header missing")
        lines = text.splitlines()
        header_line = int(detected["header_line_number"])
        block = collect_numeric_rows(lines, header_line)
        raw_intensities = [_numeric_value(token) for token in block["values"]]
        expected_count = int(review["expected_point_count"])
        observed_count = int(review["observed_point_count"])
        padding_count = int(review["terminal_padding_points"] or 0)
        start = float(detected["two_theta_start"])
        step = float(detected["step"])
        end = float(detected["two_theta_end"])
        for actual, expected, name in (
            (start, float(review["start"]), "start"),
            (step, float(review["step"]), "step"),
            (end, float(review["end"]), "end"),
        ):
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9):
                raise RuntimeError(f"entry {entry_id}: {name} differs from review")
        if len(raw_intensities) != observed_count:
            raise RuntimeError(f"entry {entry_id}: observed count differs from review")
        trailing_count = 0
        for value in reversed(raw_intensities):
            if value == 0:
                trailing_count += 1
            else:
                break
        if trailing_count != padding_count:
            raise RuntimeError(f"entry {entry_id}: padding count differs from review")
        intensities = (
            raw_intensities[:-padding_count]
            if padding_count
            else raw_intensities[:]
        )
        independent = _independent_numeric_block(lines, header_line)
        independent_values = [_numeric_value(token) for token in independent["tokens"]]
        independent_canonical = (
            independent_values[:-padding_count]
            if padding_count
            else independent_values[:]
        )
        if independent_canonical != intensities:
            raise RuntimeError(f"entry {entry_id}: independent profile differs")
        axis, qc, qc_errors = axis_and_qc(
            start=start,
            step=step,
            end=end,
            expected_count=expected_count,
            intensities=intensities,
            independent_count=len(independent_canonical),
            independent_values=independent_canonical,
        )
        endpoint_compatible = bool(
            axis and abs(axis[-1] - end) <= max(abs(step) / 2, 1e-9)
        )
        disallowed_errors = [
            error
            for error in qc_errors
            if error not in {"grid_alignment_exact", "axis_final_matches_end"}
        ]
        if disallowed_errors or not endpoint_compatible:
            raise RuntimeError(f"entry {entry_id}: recovery QC failed: {qc_errors}")
        qc["axis_final_matches_end"] = endpoint_compatible
        qc["axis_endpoint_compatible_within_half_step"] = endpoint_compatible
        row["detected_content_family"] = review["content_family"]
        fullprof = collect_fullprof_metadata(text)
        text_metadata = collect_text_metadata(text)
        index_tokens = json.loads(row["raw_hash_delimited_tokens"])
        wavelength_records = explicit_wavelengths(
            index_tokens=index_tokens,
            text=text,
            fullprof=fullprof,
        )
        wavelength, wavelength_secondary, wavelength_notes = select_wavelength(
            wavelength_records
        )
        if wavelength_notes:
            raise RuntimeError(f"entry {entry_id}: {wavelength_notes}")
        document = build_documents(
            row,
            archive_path=archive_path,
            member_filename=member_filename,
            archive_sha256=archive_sha,
            member_sha256=member_sha,
            text=text,
            axis=axis,
            intensities=intensities,
            start=start,
            step=step,
            end=end,
            expected_count=expected_count,
            qc=qc,
            wavelength_records=wavelength_records,
            wavelength=wavelength,
            wavelength_secondary=wavelength_secondary,
            fullprof=fullprof,
            text_metadata=text_metadata,
            independent_parser={
                "encoding": encoding,
                "nul_byte_count": nul_count,
                "decode_note": decode_note,
                "container_type": container_type,
                "header_line_number": header_line,
                "intensity_token_count": len(independent_canonical),
                "terminal_padding_points_applied": padding_count,
                "recovery_rule_source": "powbase_deep_rescue_v1",
            },
        )
        errors = validate_document(
            document,
            entry_id=entry_id,
            source_row=row,
            archive_sha=archive_sha,
            member_sha=member_sha,
            expected_count=expected_count,
            wavelength_records=wavelength_records,
            canonical_pattern_keys=canonical_pattern_keys,
        )
        if errors:
            raise RuntimeError(f"entry {entry_id}: {errors}")
        documents.append(document)
    return documents, hashes


def preflight_collection(
    database: Any,
    collection: str,
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    field = ID_FIELDS[collection]
    identifiers = [document[field] for document in documents]
    existing = {
        document[field]: without_mongo_id(document)
        for document in database[collection].find(
            {field: {"$in": identifiers}},
            {"_id": 0},
        )
    }
    new_ids: list[str] = []
    exact_ids: list[str] = []
    conflicts: list[str] = []
    for document in documents:
        identifier = document[field]
        if identifier not in existing:
            new_ids.append(identifier)
        elif existing[identifier] == without_mongo_id(document):
            exact_ids.append(identifier)
        else:
            conflicts.append(identifier)
    return {
        "new_ids": sorted(new_ids),
        "exact_ids": sorted(exact_ids),
        "conflicts": sorted(conflicts),
        "safe": len(identifiers) == len(set(identifiers)) and not conflicts,
    }


def duplicate_ids(database: Any) -> dict[str, list[str]]:
    duplicates: dict[str, list[str]] = {}
    for collection, field in ID_FIELDS.items():
        duplicates[collection] = [
            str(row["_id"])
            for row in database[collection].aggregate(
                [
                    {"$group": {"_id": f"${field}", "n": {"$sum": 1}}},
                    {"$match": {"n": {"$gt": 1}}},
                    {"$sort": {"_id": 1}},
                ]
            )
        ]
    return duplicates


def report_record(document: dict[str, Any], action: str) -> dict[str, Any]:
    pattern = document["pattern"]
    radiation = pattern.get("radiation") or {}
    evidence = (
        (pattern.get("provenance") or {})
        .get("powbase_source_evidence")
        or {}
    )
    xrd = pattern.get("xrd") or {}
    return {
        "entry_id": document["entry_id"],
        "sample_id": document["sample_id"],
        "measurement_id": document["measurement_id"],
        "pattern_id": document["pattern_id"],
        "action": action,
        "point_count": xrd.get("point_count"),
        "x_length": len(xrd.get("two_theta") or []),
        "y_length": len(xrd.get("intensity") or []),
        "wavelength_angstrom": radiation.get("wavelength_angstrom"),
        "wavelength_kalpha2_angstrom": radiation.get(
            "wavelength_kalpha2_angstrom"
        ),
        "source_file": evidence.get("source_archive_file_key"),
        "source_sha256": evidence.get("source_sha256"),
        "member_filename": evidence.get("contained_member_filename"),
        "member_sha256": evidence.get("contained_member_sha256"),
        "phase_character": pattern.get("phase_character"),
        "structure_linkage": (pattern.get("structure_linkage") or {}).get(
            "status"
        ),
        "validation_status": "PASS",
    }


def integrate(
    *,
    backup_root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    uri: str | None = None,
    database_name: str = "crystaldb",
) -> dict[str, Any]:
    if database_name != "crystaldb":
        raise ValueError("production database must be exactly crystaldb")
    if not backup_root.is_dir():
        raise FileNotFoundError(backup_root)

    inclusion = read_csv_map(INCLUSION_PATH)
    fast = read_csv_map(FAST_PATH)
    rescue = read_csv_map(RESCUE_PATH)
    deep = read_csv_map(DEEP_PATH)
    canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    canonical_pattern_keys = set(canonical["records"][0]["pattern"].keys())
    promoted_ids = sorted(
        [
            entry_id
            for entry_id, row in deep.items()
            if row["final_status"] == "promote_verified"
        ],
        key=int,
    )
    entry_ids = FINALIZED_IDS + promoted_ids
    if len(entry_ids) != 75 or len(set(entry_ids)) != 75:
        raise RuntimeError("integration scope is not exactly 75 unique entries")
    if {"36", "114"} & set(entry_ids):
        raise RuntimeError("entries 36 or 114 are in the integration scope")

    final_documents, final_hashes = build_finalized_documents(
        inclusion,
        fast,
        rescue,
        canonical_pattern_keys,
    )
    deep_documents, deep_hashes = build_deep_documents(
        inclusion,
        deep,
        canonical_pattern_keys,
    )
    documents = final_documents + deep_documents
    if len(documents) != 75:
        raise RuntimeError("did not build exactly 75 documents")
    source_hashes_before = {**final_hashes, **deep_hashes}

    mongo_uri = uri or os.environ.get(
        "CRYSTALDB_MONGO_URI",
        "mongodb://localhost:27017",
    )
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        database = client[database_name]
        before_counts = collection_counts(database)
        saved_backup_counts = backup_counts(backup_root)
        expected_counts_from_backup = dict(saved_backup_counts)
        for collection in ("samples", "measurements", "patterns"):
            expected_counts_from_backup[collection] += 75
        if before_counts not in (saved_backup_counts, expected_counts_from_backup):
            raise RuntimeError(
                "live state is neither the backed-up pre-write state nor the "
                f"expected post-write state: backup={saved_backup_counts}, "
                f"live={before_counts}, expected={expected_counts_from_backup}"
            )
        if database.sources.count_documents({"api_source_code": "POWBASE"}) != 1:
            raise RuntimeError("expected exactly one POWBASE source record")

        by_collection = {
            "samples": [document["sample"] for document in documents],
            "measurements": [document["measurement"] for document in documents],
            "patterns": [document["pattern"] for document in documents],
        }
        preflight = {
            collection: preflight_collection(database, collection, docs)
            for collection, docs in by_collection.items()
        }
        if any(not result["safe"] for result in preflight.values()):
            raise RuntimeError(f"collision preflight failed: {preflight}")

        inserted_counts = {"samples": 0, "measurements": 0, "patterns": 0}
        for collection in ("samples", "measurements", "patterns"):
            new_ids = set(preflight[collection]["new_ids"])
            documents_to_insert = [
                document
                for document in by_collection[collection]
                if document[ID_FIELDS[collection]] in new_ids
            ]
            if documents_to_insert:
                database[collection].insert_many(
                    documents_to_insert,
                    ordered=True,
                )
                inserted_counts[collection] = len(documents_to_insert)

        after_counts = collection_counts(database)
        expected_counts = dict(before_counts)
        for collection in ("samples", "measurements", "patterns"):
            expected_counts[collection] += len(preflight[collection]["new_ids"])
        if after_counts != expected_counts:
            raise RuntimeError(
                f"unexpected post-write counts: {after_counts} != {expected_counts}"
            )

        post_preflight = {
            collection: preflight_collection(database, collection, docs)
            for collection, docs in by_collection.items()
        }
        if any(
            result["new_ids"]
            or result["conflicts"]
            or len(result["exact_ids"]) != 75
            for result in post_preflight.values()
        ):
            raise RuntimeError(
                f"idempotence preflight failed: {post_preflight}"
            )

        sample_ids = {document["sample_id"] for document in by_collection["samples"]}
        measurement_ids = {
            document["measurement_id"]
            for document in by_collection["measurements"]
        }
        pattern_ids = {
            document["pattern_id"]
            for document in by_collection["patterns"]
        }
        orphan_counts = {
            "measurements_without_samples": sum(
                document["sample_id"] not in sample_ids
                for document in by_collection["measurements"]
            ),
            "patterns_without_samples": sum(
                document["sample_id"] not in sample_ids
                for document in by_collection["patterns"]
            ),
            "patterns_without_measurements": sum(
                document["measurement_id"] not in measurement_ids
                for document in by_collection["patterns"]
            ),
            "xy_payloads_without_patterns": sum(
                document["pattern_id"] not in pattern_ids
                for document in by_collection["patterns"]
            ),
        }
        duplicates = duplicate_ids(database)
        source_hashes_after = {
            entry_id: sha256_file(
                ARCHIVE_DIR / inclusion[entry_id]["source_filename"]
            )
            for entry_id in entry_ids
        }
        source_hashes_unchanged = source_hashes_before == source_hashes_after
        production_delta_from_backup = {
            collection: after_counts[collection] - saved_backup_counts[collection]
            for collection in ALL_COLLECTIONS
        }
        powbase_pattern_count = database.patterns.count_documents(
            {"api_source_code": "POWBASE"}
        )
        structure_relation_counts_unchanged = (
            after_counts["structures"] == before_counts["structures"]
            and after_counts["relations"] == before_counts["relations"]
        )
        if (
            powbase_pattern_count != 119
            or after_counts["patterns"] != 3094
            or any(orphan_counts.values())
            or any(duplicates.values())
            or not source_hashes_unchanged
            or not structure_relation_counts_unchanged
        ):
            raise RuntimeError("post-write validation failed")

        report_rows = [
            report_record(
                document,
                (
                    "inserted"
                    if document["pattern_id"]
                    in set(preflight["patterns"]["new_ids"])
                    else "exact_existing"
                ),
            )
            for document in documents
        ]
        report = {
            "schema_version": "powbase-final-xray-production-integration-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": database_name,
            "production_database_written": True,
            "scope": {
                "entry_count": 75,
                "entry_ids": entry_ids,
                "finalized_entry_ids": FINALIZED_IDS,
                "deep_rescue_promoted_entry_count": len(promoted_ids),
                "excluded_entry_ids": ["36", "114"],
            },
            "backup": {
                "path": str(backup_root.resolve()),
                "complete": True,
                "collection_counts": saved_backup_counts,
            },
            "before_counts": before_counts,
            "after_counts": after_counts,
            "inserted_counts": inserted_counts,
            "production_delta_from_backup": production_delta_from_backup,
            "powbase_xray_pattern_count": powbase_pattern_count,
            "expected_powbase_xray_pattern_count": 119,
            "expected_total_pattern_count": 3094,
            "preflight": preflight,
            "post_write_idempotence_preflight": post_preflight,
            "duplicate_primary_ids": duplicates,
            "orphan_counts": orphan_counts,
            "source_hashes_unchanged": source_hashes_unchanged,
            "source_hashes_before": source_hashes_before,
            "source_hashes_after": source_hashes_after,
            "structure_relation_counts_unchanged": structure_relation_counts_unchanged,
            "xy_payload_count": 75,
            "known_wavelength_count": sum(
                (
                    (document["pattern"].get("radiation") or {}).get(
                        "wavelength_angstrom"
                    )
                    is not None
                )
                for document in documents
            ),
            "unknown_wavelength_count": sum(
                (
                    (document["pattern"].get("radiation") or {}).get(
                        "wavelength_angstrom"
                    )
                    is None
                )
                for document in documents
            ),
            "phase_character_unknown_count": sum(
                document["pattern"].get("phase_character") == "unknown"
                for document in documents
            ),
            "prohibited_operations": {
                "entries_36_114_processed": False,
                "powbase_structures_modified": False,
                "powbase_relations_modified": False,
                "cod_matching": False,
                "website_manuscript_release_updated": False,
                "git_updated": False,
            },
            "records": report_rows,
            "integration_passed": True,
        }
    finally:
        client.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "powbase_final_xray_production_integration_v1.json"
    csv_path = output_dir / "powbase_final_xray_production_integration_v1.csv"
    summary_path = (
        output_dir / "powbase_final_xray_production_integration_v1_summary.md"
    )
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(report_rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(report_rows)
    summary_path.write_text(
        "\n".join(
            [
                "# PowBase Final X-ray Production Integration v1",
                "",
                "Integrated the 75 final-validated PowBase X-ray records into production `crystaldb`.",
                "",
                f"- Backup: `{report['backup']['path']}`",
                f"- Production delta from backup, samples: **{production_delta_from_backup['samples']}**",
                f"- Production delta from backup, measurements: **{production_delta_from_backup['measurements']}**",
                f"- Production delta from backup, patterns: **{production_delta_from_backup['patterns']}**",
                f"- Writes performed in this run: **{sum(inserted_counts.values())}**",
                f"- PowBase X-ray patterns: **{powbase_pattern_count}**",
                f"- Total CrystalDB patterns: **{after_counts['patterns']}**",
                "- Embedded XY payloads: **75**",
                "- Duplicate IDs: **0**",
                "- Orphan records: **0**",
                "- Source hashes unchanged: **yes**",
                "- Structures and relations unchanged: **yes**",
                "- Idempotence preflight: **pass**",
                "",
                "Entries 36 and 114 were excluded. No COD matching, release, website, manuscript, or Git update was performed.",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report["outputs"] = {
        "json": str(json_path.resolve()),
        "csv": str(csv_path.resolve()),
        "summary": str(summary_path.resolve()),
    }
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--database", default="crystaldb")
    parser.add_argument(
        "--uri",
        default=os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"),
    )
    parser.add_argument("--allow-production-write", action="store_true")
    args = parser.parse_args()
    if not args.allow_production_write:
        raise SystemExit("production write requires --allow-production-write")
    report = integrate(
        backup_root=args.backup_root,
        output_dir=args.output_dir,
        uri=args.uri,
        database_name=args.database,
    )
    print(
        json.dumps(
            {
                "backup": report["backup"],
                "inserted_counts": report["inserted_counts"],
                "before_counts": report["before_counts"],
                "after_counts": report["after_counts"],
                "powbase_xray_pattern_count": report[
                    "powbase_xray_pattern_count"
                ],
                "duplicate_primary_ids": report["duplicate_primary_ids"],
                "orphan_counts": report["orphan_counts"],
                "source_hashes_unchanged": report["source_hashes_unchanged"],
                "idempotence": "pass",
                "outputs": report["outputs"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
