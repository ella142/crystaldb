#!/usr/bin/env python3
"""Prepare, validate, and stage the verified PowBase X-ray records.

This is a read-only source preparation step.  It reads the existing inclusion
manifest and cached PowBase archives, writes only isolated dry-run artifacts
under ``data/staging/powbase_canonical_v1`` and ``data/mappings``, and never
writes to MongoDB or modifies the cached source archives.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from scripts.audit_powbase import (
        collect_fullprof_metadata,
        collect_numeric_rows,
        collect_text_metadata,
        decode_member_text,
        find_intensity_header_and_block,
        numeric_token_value,
    )
except ModuleNotFoundError:
    from audit_powbase import (
        collect_fullprof_metadata,
        collect_numeric_rows,
        collect_text_metadata,
        decode_member_text,
        find_intensity_header_and_block,
        numeric_token_value,
    )


DEFAULT_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"
DEFAULT_INCLUSION_MANIFEST = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_v1_inclusion_manifest.csv"
)
DEFAULT_STAGING_ROOT = PROJECT_ROOT / "data" / "staging" / "powbase_canonical_v1"
DEFAULT_JSON_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
)
DEFAULT_CSV_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_validation_v1.csv"
)
DEFAULT_SUMMARY_OUTPUT = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_summary_v1.md"
)

NUMERIC_RE = re.compile(
    r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[EeDd][+-]?\d+)?$"
)
WAVELENGTH_WITH_UNIT_RE = re.compile(
    r"^\s*(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*A(?:ngstrom)?\s*$",
    re.IGNORECASE,
)
WAVELENGTH_FIELD_RE = re.compile(
    r"^\s*[!#]?\s*_(?P<key>WL[123])\s*=\s*['\"]?"
    r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))",
    re.IGNORECASE,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_json_if_unchanged(path: Path, value: Any) -> None:
    """Write a staging record without overwriting a different prior record."""

    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != payload:
            raise RuntimeError(f"staging path already contains different data: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def as_bool(value: Any) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes"}


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def safe_entry_token(entry_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", entry_id).strip("._") or "unknown"


def source_file_key(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def source_links(raw_index_text: str) -> list[str]:
    return list(
        dict.fromkeys(
            re.findall(
                r"""(?i)\bhref\s*=\s*["']([^"']+\.(?:gif|wrl))(?:["'])""",
                raw_index_text,
            )
        )
    )


def _float_from_token(token: str) -> float | None:
    value = numeric_token_value(token)
    return value if value is not None and math.isfinite(value) else None


def _numeric_tokens_from_line(line: str) -> list[str] | None:
    candidate = line.strip()
    if not candidate or candidate.startswith(("#", ";", "!", "//")):
        return None
    candidate = re.sub(r"[,;]+", " ", candidate)
    tokens = candidate.split()
    if not tokens or not all(NUMERIC_RE.fullmatch(token) for token in tokens):
        return None
    return tokens


def _independent_numeric_block(
    lines: list[str],
    header_line_number: int,
) -> dict[str, Any]:
    """Parse only the data block after the selected header independently."""

    rows: list[list[str]] = []
    for line in lines[header_line_number:]:
        if not line.strip():
            if rows:
                continue
            continue
        tokens = _numeric_tokens_from_line(line)
        if tokens is None:
            break
        rows.append(tokens)
    return {
        "rows": rows,
        "tokens": [token for row in rows for token in row],
        "count": sum(len(row) for row in rows),
    }


def _numeric_value(token: str) -> int | float:
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token)
    value = float(token.replace("D", "E").replace("d", "e"))
    if not math.isfinite(value):
        raise ValueError(f"non-finite intensity token: {token}")
    return value


def _dedupe_wavelength_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float]] = set()
    for record in records:
        key = (
            str(record.get("label") or ""),
            str(record.get("raw_value_text") or ""),
            float(record["value"]),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def explicit_wavelengths(
    *,
    index_tokens: list[str],
    text: str,
    fullprof: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if len(index_tokens) > 2:
        match = WAVELENGTH_WITH_UNIT_RE.fullmatch(index_tokens[2])
        if match:
            records.append(
                {
                    "label": "official_index_wavelength_token",
                    "value": float(match.group("value")),
                    "raw_value_text": index_tokens[2],
                    "source": "official_powbase_index",
                }
            )

    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        match = WAVELENGTH_FIELD_RE.match(line)
        if match:
            records.append(
                {
                    "label": match.group("key").lower(),
                    "value": float(match.group("value")),
                    "raw_value_text": match.group("value"),
                    "raw_line": line,
                    "line_number": line_number,
                    "source": "commented_source_metadata",
                }
            )

    for record in fullprof.get("fullprof_wavelength_records") or []:
        value = _float_from_token(str(record.get("raw_value_text") or ""))
        if value is None:
            continue
        records.append(
            {
                "label": str(record.get("label") or "").casefold(),
                "value": value,
                "raw_value_text": record.get("raw_value_text"),
                "raw_line": record.get("raw_line"),
                "source_label_line": record.get("source_label_line"),
                "source": "fullprof_labeled_metadata",
            }
        )

    for index, line in enumerate(lines):
        if not re.search(r"(?i)wavelength\s*\(\s*s\s*\)", line):
            continue
        for following in lines[index + 1 : index + 4]:
            candidate = re.sub(r"^\s*[!#]+\s?", "", following).strip()
            tokens = _numeric_tokens_from_line(candidate)
            if tokens is None or len(tokens) < 2:
                continue
            for label, token in zip(("wavelength_1", "wavelength_2"), tokens[:2]):
                value = _float_from_token(token)
                if value is not None:
                    records.append(
                        {
                            "label": label,
                            "value": value,
                            "raw_value_text": token,
                            "raw_line": following,
                            "source_label_line": line,
                            "source": "commented_wavelength_section",
                        }
                    )
            break
    return _dedupe_wavelength_records(records)


def select_wavelength(
    records: list[dict[str, Any]],
) -> tuple[float | None, float | None, list[str]]:
    primary_labels = {
        "official_index_wavelength_token",
        "wl1",
        "lambda1",
        "wavelength_1",
    }
    secondary_labels = {"wl2", "lambda2", "wavelength_2"}
    primary = [
        float(record["value"])
        for record in records
        if str(record.get("label") or "").casefold() in primary_labels
    ]
    secondary = [
        float(record["value"])
        for record in records
        if str(record.get("label") or "").casefold() in secondary_labels
    ]
    notes: list[str] = []
    unique_primary = list(dict.fromkeys(primary))
    unique_secondary = list(dict.fromkeys(secondary))
    if len(unique_primary) > 1:
        notes.append(f"conflicting explicit primary wavelengths: {unique_primary}")
        return None, None, notes
    if len(unique_secondary) > 1:
        notes.append(f"conflicting explicit secondary wavelengths: {unique_secondary}")
    return (
        unique_primary[0] if unique_primary else None,
        unique_secondary[0] if unique_secondary else None,
        notes,
    )


def axis_and_qc(
    *,
    start: float,
    step: float,
    end: float,
    expected_count: int,
    intensities: list[int | float],
    independent_count: int,
    independent_values: list[float],
) -> tuple[list[float], dict[str, Any], list[str]]:
    errors: list[str] = []
    finite_header = all(math.isfinite(value) for value in (start, step, end))
    ordered = finite_header and step > 0 and end > start
    ratio = (end - start) / step if ordered else None
    expected_from_axis = round(ratio) + 1 if ratio is not None else None
    grid_aligned = bool(
        ratio is not None
        and math.isclose(ratio, expected_from_axis - 1, rel_tol=1e-9, abs_tol=1e-6)
    )
    axis = [start + index * step for index in range(expected_count)]
    axis_finite = all(math.isfinite(value) for value in axis)
    axis_increasing = all(current > previous for previous, current in zip(axis, axis[1:]))
    final_matches_end = bool(
        axis and math.isclose(axis[-1], end, rel_tol=1e-9, abs_tol=1e-8)
    )
    count_match = len(intensities) == expected_count
    independent_count_match = independent_count == expected_count
    independent_values_match = (
        len(independent_values) == len(intensities)
        and all(
            math.isclose(float(left), float(right), rel_tol=0, abs_tol=0)
            for left, right in zip(independent_values, intensities)
        )
    )
    finite_intensities = all(math.isfinite(float(value)) for value in intensities)
    checks = {
        "header_finite": finite_header,
        "header_ordered": ordered,
        "grid_alignment_exact": grid_aligned,
        "expected_point_count": expected_count,
        "expected_point_count_from_axis": expected_from_axis,
        "observed_intensity_count": len(intensities),
        "independent_observed_intensity_count": independent_count,
        "point_count_match": count_match,
        "independent_point_count_match": independent_count_match,
        "independent_parser_values_match": independent_values_match,
        "axis_length": len(axis),
        "axis_finite": axis_finite,
        "axis_strictly_increasing": axis_increasing,
        "axis_final_matches_end": final_matches_end,
        "intensity_values_finite": finite_intensities,
    }
    for name, valid in checks.items():
        if isinstance(valid, bool) and not valid:
            errors.append(name)
    return axis, checks, errors


def source_evidence(
    row: dict[str, str],
    *,
    archive_path: Path,
    member_filename: str,
    archive_sha256: str,
    member_sha256: str,
    source_extension: str,
    embedded_metadata: dict[str, Any],
) -> dict[str, Any]:
    raw_tokens = json.loads(row["raw_hash_delimited_tokens"])
    return {
        "entry_id": row["entry_id"],
        "source_label_raw": row["source_label_raw"],
        "source_modality_raw": row["source_modality_raw"],
        "source_modality_class": row["source_modality_class"],
        "source_url": row["source_url"],
        "source_filename": row["source_filename"],
        "source_sha256": archive_sha256,
        "source_archive_file_key": source_file_key(archive_path),
        "contained_member_filename": member_filename,
        "contained_member_sha256": member_sha256,
        "source_extension": source_extension,
        "raw_index_text": row["raw_index_text"],
        "raw_hash_delimited_tokens": raw_tokens,
        "raw_bibliographic_comment_text": row["raw_bibliographic_comment_text"],
        "raw_optional_links": source_links(row["raw_index_text"]),
        "audit_review_status": row["review_status"],
        "audit_decision": row["v1_decision"],
        "audit_decision_reason": row["v1_decision_reason"],
        "detected_content_family": row["detected_content_family"],
        "embedded_metadata": embedded_metadata,
    }


def build_documents(
    row: dict[str, str],
    *,
    archive_path: Path,
    member_filename: str,
    archive_sha256: str,
    member_sha256: str,
    text: str,
    axis: list[float],
    intensities: list[int | float],
    start: float,
    step: float,
    end: float,
    expected_count: int,
    qc: dict[str, Any],
    wavelength_records: list[dict[str, Any]],
    wavelength: float | None,
    wavelength_secondary: float | None,
    fullprof: dict[str, Any],
    text_metadata: dict[str, Any],
    independent_parser: dict[str, Any],
) -> dict[str, Any]:
    entry_id = row["entry_id"]
    token = safe_entry_token(entry_id)
    source = {"code": "POWBASE", "source_id": entry_id}
    sample_id = f"POWBASE_SAM_{token}"
    measurement_id = f"POWBASE_MEAS_{token}"
    pattern_id = f"POWBASE_PAT_{token}"
    archive_key = source_file_key(archive_path)
    source_radiation_text = (
        json.loads(row["raw_hash_delimited_tokens"])[2]
        if len(json.loads(row["raw_hash_delimited_tokens"])) > 2
        else None
    )
    embedded_metadata = {
        "metadata_key_tokens": text_metadata.get("metadata_key_tokens") or [],
        "cif_tag_tokens": text_metadata.get("cif_tag_tokens") or [],
        "fullprof_style_evidence": fullprof.get("fullprof_style_evidence") or [],
        "fullprof_phase_block_identifiers": (
            fullprof.get("fullprof_phase_block_identifiers") or []
        ),
        "fullprof_phase_names": fullprof.get("fullprof_phase_names") or [],
        "fullprof_wavelength_records": (
            fullprof.get("fullprof_wavelength_records") or []
        ),
        "source_wavelength_records": wavelength_records,
        "source_radiation_probe_records": (
            text_metadata.get("source_radiation_probe_records") or []
        ),
    }
    evidence = source_evidence(
        row,
        archive_path=archive_path,
        member_filename=member_filename,
        archive_sha256=archive_sha256,
        member_sha256=member_sha256,
        source_extension=Path(member_filename).suffix,
        embedded_metadata=embedded_metadata,
    )
    provenance = {
        "source": "POWBASE",
        "source_id": entry_id,
        "source_file": archive_key,
        "label_type": "source_index",
        "label_method": "literal_official_powbase_index",
        "evidence": row["raw_index_text"],
        "notes": [
            "Dry-run preparation only; no MongoDB write was performed.",
            "Source intensity values are preserved without smoothing, "
            "normalization, interpolation, background subtraction, or "
            "zero-shift correction.",
            f"Contained member: {member_filename}",
            f"Contained member SHA256: {member_sha256}",
            f"Detected content family: {row['detected_content_family']}",
        ],
        "powbase_source_evidence": evidence,
        "bibliography_raw": row["raw_bibliographic_comment_text"],
    }
    sample = {
        "sample_id": sample_id,
        "api_source_code": "POWBASE",
        "api_source_id": entry_id,
        "source": source,
        "name": row["source_label_raw"],
        "formula": None,
        "source_label_raw": row["source_label_raw"],
        "nominal_formula_or_name": row["source_label_raw"],
        "phase_character": "unknown",
        "provenance": provenance,
    }
    measurement = {
        "measurement_id": measurement_id,
        "sample_id": sample_id,
        "pattern_id": pattern_id,
        "api_source_code": "POWBASE",
        "api_source_id": entry_id,
        "source": source,
        "data_origin": "experimental",
        "modality": "powder_xrd",
        "measurement_type": "powder_xrd",
        "conditions": {
            "radiation": source_radiation_text,
            "wavelength_angstrom": wavelength,
            "wavelength_kalpha2_angstrom": wavelength_secondary,
            "scan_range": [start, end],
            "step_size": step,
        },
        "source_file": archive_key,
        "provenance": provenance,
    }
    pattern_file_key = (
        f"staging/powbase_canonical_v1/records/patterns/{pattern_id}.json"
    )
    pattern = {
        "pattern_id": pattern_id,
        "measurement_id": measurement_id,
        "sample_id": sample_id,
        "api_source_code": "POWBASE",
        "api_source_id": entry_id,
        "source": source,
        "data_origin": "experimental",
        "modality": "powder_xrd",
        "dataset_role": "canonical",
        "phase_character": "unknown",
        "phase_components": [],
        "structure_linkage": {
            "status": "unlinked",
            "coverage": "none",
            "certainty": "unknown",
            "candidate_structure_ids": [],
        },
        "scan": {
            "axis": "two_theta",
            "scan_axis": "two_theta",
            "two_theta_min_deg": start,
            "two_theta_max_deg": end,
            "start_2theta_deg": start,
            "stop_2theta_deg": end,
            "step_2theta_deg": step,
            "point_count": expected_count,
        },
        "radiation": {
            "characteristic": source_radiation_text,
            "wavelength_angstrom": wavelength,
            "wavelength_kalpha2_angstrom": wavelength_secondary,
            "source_radiation_text": source_radiation_text,
        },
        "xrd": {
            "has_xy": True,
            "x_axis": "two_theta",
            "x_unit": "degree",
            "y_axis": "intensity",
            "y_unit": "source_native",
            "point_count": expected_count,
            "two_theta": axis,
            "intensity": intensities,
        },
        "data": {"two_theta": axis, "intensity": intensities},
        "file": {
            "key": pattern_file_key,
            "sha256": None,
            "size_bytes": None,
        },
        "provenance": provenance,
        "qc": {
            **qc,
            "source_extension": Path(member_filename).suffix,
            "detected_content_family": row["detected_content_family"],
            "parsing_method": "powbase_audit_verified_header_and_numeric_block",
            "independent_parser": independent_parser,
        },
        "parse_status": "ok",
        "parse_warnings": [],
    }
    pattern_xy = {
        "pattern_id": pattern_id,
        "source": source,
        "data_origin": "experimental",
        "modality": "powder_xrd",
        "x": {"name": "two_theta", "unit": "degree", "values": axis},
        "y": {"name": "intensity", "unit": "source_native", "values": intensities},
        "point_count": expected_count,
        "provenance": provenance,
    }
    return {
        "entry_id": entry_id,
        "sample_id": sample_id,
        "measurement_id": measurement_id,
        "pattern_id": pattern_id,
        "source_evidence": evidence,
        "sample": sample,
        "measurement": measurement,
        "pattern": pattern,
        "pattern_xy": pattern_xy,
        "axis": {
            "start": start,
            "step": step,
            "end": end,
            "expected_point_count": expected_count,
        },
        "intensity": {
            "observed_point_count": len(intensities),
            "values": intensities,
        },
        "member_filename": member_filename,
        "member_sha256": member_sha256,
        "archive_sha256": archive_sha256,
        "wavelength_records": wavelength_records,
    }


def inspect_local_duplicates(
    selected: list[dict[str, str]],
) -> dict[str, Any]:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.casefold())

    by_label: dict[str, list[str]] = defaultdict(list)
    for row in selected:
        by_label[normalize(row["source_label_raw"])].append(row["entry_id"])
    same_label = [
        {"normalized_label": key, "entry_ids": ids}
        for key, ids in sorted(by_label.items())
        if key and len(ids) > 1
    ]

    existing_matches: list[dict[str, Any]] = []
    lab_manifest = PROJECT_ROOT / "data" / "powder" / "lab" / "manifests" / "lab_xrd_manifest_v1.csv"
    if lab_manifest.exists():
        lab_rows = read_csv(lab_manifest)
        for row in selected:
            label = normalize(row["source_label_raw"])
            matches = [
                {
                    "source": "LAB",
                    "path": str(lab_manifest.resolve()),
                    "source_sample_label": item.get("source_sample_label", ""),
                    "nominal_element_ratio": item.get("nominal_element_ratio", ""),
                }
                for item in lab_rows
                if label
                and (
                    normalize(item.get("source_sample_label", "")) == label
                    or normalize(item.get("nominal_element_ratio", "")) == label
                )
            ]
            if matches:
                existing_matches.append(
                    {"powbase_entry_id": row["entry_id"], "matches": matches[:20]}
                )

    opxrd_root = PROJECT_ROOT / "data" / "powder" / "opxrd" / "json"
    if opxrd_root.exists():
        for path in opxrd_root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            candidate_strings = [str(payload.get("sample_id") or "")]
            phases = payload.get("phase")
            if isinstance(phases, list):
                for phase in phases:
                    if isinstance(phase, dict):
                        candidate_strings.extend(
                            str(phase.get(key) or "")
                            for key in ("name", "formula")
                        )
            for row in selected:
                label = normalize(row["source_label_raw"])
                if label and any(label == normalize(value) for value in candidate_strings):
                    existing_matches.append(
                        {
                            "powbase_entry_id": row["entry_id"],
                            "matches": [
                                {
                                    "source": "OPXRD",
                                    "path": str(path.resolve()),
                                    "match_type": "normalized_label_text",
                                }
                            ],
                        }
                    )

    return {
        "same_source_label_groups": same_label,
        "existing_local_matches": existing_matches,
        "deduplicated": False,
        "notes": [
            "Same-label and existing-local matches are review candidates only.",
            "No record was removed or merged by material name, formula, or phase.",
        ],
    }


def inspect_mongo_read_only(
    ids: list[str],
) -> dict[str, Any]:
    try:
        from pymongo import MongoClient
    except ImportError:
        return {"status": "unavailable", "reason": "pymongo is not installed"}

    uri = os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://localhost:27017")
    database_name = os.environ.get(
        "CRYSTALDB_MONGO_DATABASE",
        os.environ.get("CRYSTALDB_MONGO_DB", "crystaldb"),
    )
    client = MongoClient(uri, serverSelectionTimeoutMS=800)
    try:
        client.admin.command("ping")
        database = client[database_name]
        existing: dict[str, Any] = {}
        for collection_name, id_field, prefix in (
            ("samples", "sample_id", "POWBASE_SAM_"),
            ("measurements", "measurement_id", "POWBASE_MEAS_"),
            ("patterns", "pattern_id", "POWBASE_PAT_"),
        ):
            existing[collection_name] = {
                "source_powbase_count": database[collection_name].count_documents(
                    {"$or": [{"api_source_code": "POWBASE"}, {"source.code": "POWBASE"}, {"source": "POWBASE"}]}
                ),
                "id_collisions": list(
                    database[collection_name].find(
                        {id_field: {"$regex": f"^{re.escape(prefix)}"}},
                        {"_id": 0, id_field: 1},
                    )
                ),
            }
        return {
            "status": "ok",
            "database": database_name,
            "read_only": True,
            "collections": existing,
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "database": database_name,
            "read_only": True,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    finally:
        client.close()


def validation_row(
    result: dict[str, Any],
    row: dict[str, str],
    qc: dict[str, Any],
    errors: list[str],
    *,
    wavelength: float | None,
    wavelength_secondary: float | None,
    duplicate_note: str,
) -> dict[str, Any]:
    return {
        "entry_id": row["entry_id"],
        "sample_id": result["sample_id"],
        "measurement_id": result["measurement_id"],
        "pattern_id": result["pattern_id"],
        "source_label_raw": row["source_label_raw"],
        "source_modality_raw": row["source_modality_raw"],
        "source_modality_class": row["source_modality_class"],
        "source_filename": row["source_filename"],
        "source_sha256": result["archive_sha256"],
        "member_filename": result["member_filename"],
        "member_sha256": result["member_sha256"],
        "source_extension": Path(result["member_filename"]).suffix,
        "detected_content_family": row["detected_content_family"],
        "parsing_method": "powbase_audit_verified_header_and_numeric_block",
        "two_theta_start": result["axis"]["start"],
        "two_theta_step": result["axis"]["step"],
        "two_theta_end": result["axis"]["end"],
        "expected_point_count": result["axis"]["expected_point_count"],
        "observed_point_count": result["intensity"]["observed_point_count"],
        "axis_length": qc["axis_length"],
        "intensity_length": result["intensity"]["observed_point_count"],
        "point_count_consistency": qc["point_count_match"],
        "axis_finite": qc["axis_finite"],
        "axis_strictly_increasing": qc["axis_strictly_increasing"],
        "intensity_values_finite": qc["intensity_values_finite"],
        "independent_parser_match": qc["independent_parser_values_match"],
        "source_modality_is_xray": row["source_modality_class"] == "x-ray",
        "source_radiation_text": (
            json.loads(row["raw_hash_delimited_tokens"])[2]
            if len(json.loads(row["raw_hash_delimited_tokens"])) > 2
            else ""
        ),
        "wavelength_angstrom": wavelength,
        "wavelength_secondary_angstrom": wavelength_secondary,
        "wavelength_explicitly_supported": wavelength is not None,
        "phase_character": "unknown",
        "structure_linkage_status": "unlinked",
        "structure_linkage_candidate_count": 0,
        "potential_duplicate_note": duplicate_note,
        "validation_errors": json_text(errors),
        "validation_status": "ok" if not errors else "failed",
    }


VALIDATION_FIELDS = [
    "entry_id",
    "sample_id",
    "measurement_id",
    "pattern_id",
    "source_label_raw",
    "source_modality_raw",
    "source_modality_class",
    "source_filename",
    "source_sha256",
    "member_filename",
    "member_sha256",
    "source_extension",
    "detected_content_family",
    "parsing_method",
    "two_theta_start",
    "two_theta_step",
    "two_theta_end",
    "expected_point_count",
    "observed_point_count",
    "axis_length",
    "intensity_length",
    "point_count_consistency",
    "axis_finite",
    "axis_strictly_increasing",
    "intensity_values_finite",
    "independent_parser_match",
    "source_modality_is_xray",
    "source_radiation_text",
    "wavelength_angstrom",
    "wavelength_secondary_angstrom",
    "wavelength_explicitly_supported",
    "phase_character",
    "structure_linkage_status",
    "structure_linkage_candidate_count",
    "potential_duplicate_note",
    "validation_errors",
    "validation_status",
]


def write_validation_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=VALIDATION_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    path: Path,
    *,
    payload: dict[str, Any],
) -> None:
    summary = payload["summary"]
    duplicate = payload["potential_duplicates"]
    lines = [
        "# PowBase Canonical Dry-Run Preparation v1",
        "",
        "This report prepares the 44 records marked `include_verified` in the "
        "PowBase CrystalDB v1 inclusion manifest. It does not write MongoDB, "
        "modify production CrystalDB, modify the cached PowBase source "
        "archives, or perform canonical ingestion.",
        "",
        "## Scope and Mapping",
        "",
        "- One source entry produces one stable PowBase sample, measurement, "
        "pattern, and XY payload.",
        "- Stable identifiers are source-aware: `POWBASE_SAM_<entry_id>`, "
        "`POWBASE_MEAS_<entry_id>`, and `POWBASE_PAT_<entry_id>`.",
        "- Source labels remain literal nominal labels. Confirmed formulas "
        "are not assigned.",
        "- `phase_character` remains `unknown` for all records.",
        "- `structure_linkage` is `unlinked` with no candidate CIF or "
        "structure IDs.",
        "- Intensity arrays are copied as parsed numeric values. No smoothing, "
        "normalization, interpolation, background subtraction, zero-shift "
        "correction, or silent trimming is performed.",
        "",
        "## Results",
        "",
        "| Measure | Count |",
        "| --- | ---: |",
        f"| Selected inclusion records | {summary['selected_records']} |",
        f"| Successfully parsed profiles | {summary['successfully_parsed_profiles']} |",
        f"| Prepared samples | {summary['prepared_samples']} |",
        f"| Prepared measurements | {summary['prepared_measurements']} |",
        f"| Prepared patterns | {summary['prepared_patterns']} |",
        f"| Prepared XY payloads | {summary['prepared_xy_payloads']} |",
        f"| Failed or quarantined records | {summary['failed_or_quarantined_records']} |",
        f"| Missing explicit wavelength | {summary['missing_wavelength_count']} |",
        f"| Explicit primary wavelength available | {summary['explicit_wavelength_count']} |",
        f"| Validation errors | {summary['validation_error_record_count']} |",
        f"| Stable identifier collisions | {summary['stable_identifier_collision_count']} |",
        "",
        f"All 44 records ready for MongoDB staging after this dry-run: "
        f"`{str(summary['ready_for_mongodb_staging']).lower()}`.",
        "This statement means local source parsing and validation passed. "
        "No MongoDB staging or write was performed.",
        "",
        "## Validation",
        "",
        "- The audit parser selected the verified three-number 2θ header and "
        "numeric intensity block for each record.",
        "- An independent block parser re-read the same member bytes and "
        "matched the intensity count and numeric values.",
        "- The reconstructed axis has the source start, step, end, expected "
        "point count, finite values, and strictly increasing values.",
        "- Exact source member and archive SHA256 values are retained in every "
        "canonical document's provenance.",
        "",
        "## Wavelength Handling",
        "",
        "Wavelength values were retained only when explicitly stated by the "
        "official index token or labeled source metadata. Radiation text such "
        "as `Cu-Kalpha` remains source text and was not converted into an "
        "inferred numeric wavelength.",
        "",
        "## Potential Duplicates",
        "",
        "Potential duplicates are reported for review only. No record was "
        "deduplicated by material name, formula, or phase identity.",
        "",
        f"- Same-label PowBase groups: {len(duplicate['same_source_label_groups'])}",
        f"- Existing local matches: {len(duplicate['existing_local_matches'])}",
        "",
        "```json",
        json.dumps(duplicate, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Outputs",
        "",
        f"- Dry-run JSON: `{payload['outputs']['json']}`",
        f"- Validation CSV: `{payload['outputs']['csv']}`",
        f"- Isolated staging root: `{payload['outputs']['staging_root']}`",
        "",
        "No MongoDB write, production modification, source archive rewrite, "
        "Git staging, commit, or push was performed.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare(
    *,
    inclusion_manifest: Path = DEFAULT_INCLUSION_MANIFEST,
    archive_root: Path = DEFAULT_ROOT,
    staging_root: Path = DEFAULT_STAGING_ROOT,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    csv_output: Path = DEFAULT_CSV_OUTPUT,
    summary_output: Path = DEFAULT_SUMMARY_OUTPUT,
    inspect_mongo: bool = True,
) -> dict[str, Any]:
    inclusion_rows = [
        row
        for row in read_csv(inclusion_manifest)
        if row.get("v1_decision") == "include_verified"
    ]
    if len(inclusion_rows) != 44:
        raise ValueError(f"expected exactly 44 include_verified rows, found {len(inclusion_rows)}")
    if len({row["entry_id"] for row in inclusion_rows}) != 44:
        raise ValueError("inclusion manifest contains duplicate selected entry IDs")

    inventory_path = archive_root / "inventory" / "powbase_archive_inventory.jsonl"
    inventory = {
        str(record["entry_id"]): record
        for record in read_jsonl(inventory_path)
    }
    records: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    duplicate_report = inspect_local_duplicates(inclusion_rows)
    same_label_by_entry: dict[str, str] = {}
    for group in duplicate_report["same_source_label_groups"]:
        note = "same source label as entries " + ", ".join(group["entry_ids"])
        for entry_id in group["entry_ids"]:
            same_label_by_entry[entry_id] = note

    used_ids: dict[str, dict[str, str]] = {}
    archive_dir = archive_root / "archives"
    for row in sorted(inclusion_rows, key=lambda item: item["entry_id"]):
        entry_id = row["entry_id"]
        archive_path = archive_dir / row["source_filename"]
        failure_context: dict[str, Any] = {"entry_id": entry_id}
        try:
            if not archive_path.is_file():
                raise FileNotFoundError(archive_path)
            archive_sha256 = sha256_file(archive_path)
            if archive_sha256 != row["source_sha256"]:
                raise ValueError(
                    f"archive SHA256 mismatch: manifest={row['source_sha256']} actual={archive_sha256}"
                )
            inventory_record = inventory.get(entry_id)
            if inventory_record is None:
                raise ValueError("entry is absent from the full archive inventory")
            if inventory_record.get("source_sha256") != archive_sha256:
                raise ValueError("archive SHA256 differs from the audit inventory")

            with zipfile.ZipFile(archive_path) as archive:
                infos = [info for info in archive.infolist() if not info.is_dir()]
                if len(infos) != 1:
                    raise ValueError(
                        f"expected one contained data member, found {len(infos)}"
                    )
                info = infos[0]
                member_filename = info.filename
                member_raw = archive.read(info)
            member_sha256 = sha256_bytes(member_raw)

            inventory_members = {
                item.get("member_filename"): item
                for item in inventory_record.get("members") or []
            }
            inventory_member = inventory_members.get(member_filename)
            if inventory_member is None:
                raise ValueError("contained member is absent from the audit inventory")
            if inventory_member.get("member_sha256") != member_sha256:
                raise ValueError("member SHA256 differs from the audit inventory")

            text, encoding = decode_member_text(member_raw)
            if text is None:
                raise ValueError("contained member is not readable text")
            pattern = find_intensity_header_and_block(text)
            if not pattern.get("header_found"):
                raise ValueError("verified audit record has no numeric diffraction header")
            if pattern.get("point_count_consistency") is not True:
                raise ValueError("verified audit record is not point-count consistent")

            header_line_number = int(pattern["header_line_number"])
            lines = text.splitlines()
            audit_block = collect_numeric_rows(lines, header_line_number)
            independent_block = _independent_numeric_block(lines, header_line_number)
            audit_tokens = list(audit_block["values"])
            independent_tokens = list(independent_block["tokens"])
            if len(audit_tokens) != len(independent_tokens):
                raise ValueError("independent parser count differs from audit parser")
            intensities = [_numeric_value(token) for token in audit_tokens]
            independent_values = [
                float(token.replace("D", "E").replace("d", "e"))
                for token in independent_tokens
            ]
            start = float(pattern["two_theta_start"])
            step = float(pattern["step"])
            end = float(pattern["two_theta_end"])
            expected_count = int(pattern["expected_point_count"])
            if as_int(row["expected_point_count"]) != expected_count:
                raise ValueError(
                    "expected point count differs from inclusion manifest: "
                    f"manifest={row['expected_point_count']} parsed={expected_count}"
                )
            if as_int(row["observed_point_count"]) != len(intensities):
                raise ValueError(
                    "observed point count differs from inclusion manifest: "
                    f"manifest={row['observed_point_count']} parsed={len(intensities)}"
                )
            axis, qc, errors = axis_and_qc(
                start=start,
                step=step,
                end=end,
                expected_count=expected_count,
                intensities=intensities,
                independent_count=len(independent_values),
                independent_values=independent_values,
            )
            if errors:
                raise ValueError("validation errors: " + ", ".join(errors))

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
                raise ValueError("; ".join(wavelength_notes))

            result = build_documents(
                row,
                archive_path=archive_path,
                member_filename=member_filename,
                archive_sha256=archive_sha256,
                member_sha256=member_sha256,
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
                    "header_line_number": header_line_number,
                    "intensity_token_count": len(independent_tokens),
                    "numeric_rows": len(independent_block["rows"]),
                    "column_counts": dict(
                        Counter(len(row_values) for row_values in independent_block["rows"])
                    ),
                },
            )
            id_map = {
                "sample_id": result["sample_id"],
                "measurement_id": result["measurement_id"],
                "pattern_id": result["pattern_id"],
            }
            for kind, identifier in id_map.items():
                prior = used_ids.setdefault(identifier, {})
                prior[kind] = entry_id
                if len(set(prior.values())) > 1:
                    raise ValueError(f"stable identifier collision: {identifier}")

            entry_staging = staging_root / "records"
            write_json_if_unchanged(
                entry_staging / "samples" / f"{result['sample_id']}.json",
                result["sample"],
            )
            write_json_if_unchanged(
                entry_staging / "measurements" / f"{result['measurement_id']}.json",
                result["measurement"],
            )
            write_json_if_unchanged(
                entry_staging / "patterns" / f"{result['pattern_id']}.json",
                result["pattern"],
            )
            write_json_if_unchanged(
                staging_root / "xy" / f"{result['pattern_id']}.json",
                result["pattern_xy"],
            )

            validation_rows.append(
                validation_row(
                    result,
                    row,
                    qc,
                    [],
                    wavelength=wavelength,
                    wavelength_secondary=wavelength_secondary,
                    duplicate_note=same_label_by_entry.get(entry_id, ""),
                )
            )
            records.append(result)
        except Exception as exc:
            failure_context["error"] = f"{type(exc).__name__}: {exc}"
            failures.append(failure_context)

    if failures:
        quarantine_root = staging_root / "quarantine"
        for failure in failures:
            write_json(
                quarantine_root / f"{safe_entry_token(failure['entry_id'])}.json",
                failure,
            )

    local_id_collisions = [
        identifier
        for identifier, sources in used_ids.items()
        if len(set(sources.values())) > 1
    ]
    mongo_report = (
        inspect_mongo_read_only(
            [item["entry_id"] for item in records]
        )
        if inspect_mongo
        else {"status": "skipped", "read_only": True}
    )
    mongo_collisions = []
    if mongo_report.get("status") == "ok":
        for collection in mongo_report["collections"].values():
            mongo_collisions.extend(
                item.get("_id") or item
                for item in collection.get("id_collisions", [])
            )

    summary = {
        "selected_records": len(inclusion_rows),
        "successfully_parsed_profiles": len(records),
        "prepared_samples": len({item["sample_id"] for item in records}),
        "prepared_measurements": len({item["measurement_id"] for item in records}),
        "prepared_patterns": len({item["pattern_id"] for item in records}),
        "prepared_xy_payloads": len(records),
        "failed_or_quarantined_records": len(failures),
        "explicit_wavelength_count": sum(
            bool(item["wavelength_records"])
            for item in records
        ),
        "missing_wavelength_count": sum(
            not item["wavelength_records"]
            for item in records
        ),
        "validation_error_record_count": sum(
            item.get("validation_status") == "failed"
            for item in validation_rows
        ),
        "stable_identifier_collision_count": len(local_id_collisions) + len(mongo_collisions),
        "ready_for_mongodb_staging": bool(
            len(records) == 44
            and not failures
            and not local_id_collisions
            and not mongo_collisions
        ),
        "mongodb_writes": False,
        "production_modified": False,
        "source_archives_modified": False,
        "canonical_ingestion_performed": False,
        "phase_character_promoted": False,
    }
    outputs = {
        "json": str(json_output.resolve()),
        "csv": str(csv_output.resolve()),
        "summary": str(summary_output.resolve()),
        "staging_root": str(staging_root.resolve()),
    }
    payload = {
        "schema_version": "powbase-canonical-dryrun-v1",
        "inputs": {
            "inclusion_manifest": str(inclusion_manifest.resolve()),
            "archive_inventory": str(inventory_path.resolve()),
            "archive_root": str(archive_dir.resolve()),
        },
        "constraints": {
            "mongodb_writes": False,
            "production_modified": False,
            "source_archives_modified": False,
            "canonical_ingestion_performed": False,
            "structure_records_created": False,
            "phase_character": "unknown",
            "structure_linkage": "unlinked",
        },
        "summary": summary,
        "potential_duplicates": duplicate_report,
        "mongodb_read_only_check": mongo_report,
        "stable_identifier_collisions": {
            "local": local_id_collisions,
            "mongodb": mongo_collisions,
        },
        "failures": failures,
        "outputs": outputs,
        "validation_rows": validation_rows,
        "records": records,
    }
    write_json(json_output, payload)
    write_validation_csv(csv_output, validation_rows)
    write_summary(summary_output, payload=payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare verified PowBase X-ray records without MongoDB writes."
    )
    parser.add_argument("--inclusion-manifest", type=Path, default=DEFAULT_INCLUSION_MANIFEST)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument(
        "--skip-mongo-check",
        action="store_true",
        help="Skip the read-only duplicate check against the configured MongoDB.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = prepare(
        inclusion_manifest=args.inclusion_manifest,
        archive_root=args.archive_root,
        staging_root=args.staging_root,
        json_output=args.json_output,
        csv_output=args.csv_output,
        summary_output=args.summary_output,
        inspect_mongo=not args.skip_mongo_check,
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"JSON: {payload['outputs']['json']}")
    print(f"CSV: {payload['outputs']['csv']}")
    print(f"Summary: {payload['outputs']['summary']}")
    print(f"Staging root: {payload['outputs']['staging_root']}")
    return 1 if payload["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
