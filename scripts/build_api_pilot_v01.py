#!/usr/bin/env python
"""Build the isolated CrystalDB API v0.1.2 pilot database.

The builder reads existing source/canonical databases and writes only to the
explicit pilot database. It deliberately does not delete or modify any source
database, source file, CIF, HKL, or manuscript.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from crystaldb.data_paths import get_data_root, normalize_file_key
from crystaldb.cif_parser import parse_cif
FORBIDDEN_DATABASES = {"rruff", "opxrd", "dara", "crystaldb"}
DEFAULT_DATABASE = "crystaldb_api_pilot"
SOURCE_DATABASE = "crystaldb"


def normalize_formula(value: Any) -> str | None:
    if value in (None, "", ".", "?"):
        return None
    return re.sub(r"[\s_]", "", str(value))


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


def source_ref(code: str, source_id: str | None = None) -> dict[str, str | None]:
    return {"code": code.upper(), "source_id": source_id}


def canonical_headers(path: Path) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not path.is_file():
        return headers
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#\s*([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", line.strip())
        if match:
            headers[match.group(1)] = match.group(2)
    return headers


def header_number(headers: dict[str, str], key: str) -> float | None:
    match = re.match(
        r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)",
        headers.get(key, ""),
    )
    return float(match.group(1)) if match else None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_metadata(data_root: Path, file_key: str | None) -> dict[str, Any] | None:
    if not file_key:
        return None
    normalized = normalize_file_key(file_key)
    path = (data_root / Path(*normalized.split("/"))).resolve()
    root = data_root.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"file key escapes data root: {file_key}")
    if not path.is_file():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "key": normalized,
        "sha256": digest,
        "size_bytes": path.stat().st_size,
    }


def upsert(collection: Any, key: str, value: str, document: dict[str, Any]) -> None:
    collection.replace_one({key: value}, {**document, key: value}, upsert=True)


def ensure_indexes(database: Any) -> None:
    specifications = {
        "sources": [
            ([("source_id", 1)], {"unique": True, "name": "source_id_unique"}),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
        ],
        "samples": [
            ([("sample_id", 1)], {"unique": True, "name": "sample_id_unique"}),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
        ],
        "measurements": [
            ([("measurement_id", 1)], {"unique": True, "name": "measurement_id_unique"}),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
        ],
        "patterns": [
            ([("pattern_id", 1)], {"unique": True, "name": "pattern_id_unique"}),
            ([("api_source_code", 1)], {"name": "api_source_code"}),
            ([("modality", 1)], {"name": "modality"}),
            ([("phase_character", 1)], {"name": "phase_character"}),
            ([("dataset_role", 1)], {"name": "dataset_role"}),
            ([("phase_components.formula_normalized", 1)], {"name": "component_formula"}),
            ([("structure_linkage.status", 1)], {"name": "structure_linkage"}),
            ([("linked_structure_ids", 1)], {"name": "linked_structure_ids"}),
        ],
        "structures": [
            ([("structure_id", 1)], {"unique": True, "name": "structure_id_unique"}),
            ([("api_source_code", 1), ("api_source_id", 1)], {"name": "source_source_id"}),
            ([("formula_normalized", 1)], {"name": "formula_normalized"}),
            ([("space_group.number", 1)], {"name": "space_group_number"}),
        ],
        "reflection_sets": [
            ([("reflection_set_id", 1)], {"unique": True, "name": "reflection_set_id_unique"}),
            ([("api_source_code", 1), ("api_source_id", 1)], {"name": "source_source_id"}),
        ],
        "relations": [
            ([("relation_id", 1)], {"unique": True, "name": "relation_id_unique"}),
            ([("subject_id", 1)], {"name": "subject_id"}),
            ([("object_id", 1)], {"name": "object_id"}),
        ],
        "releases": [
            ([("release_id", 1)], {"unique": True, "name": "release_id_unique"}),
        ],
    }
    for collection_name, indexes in specifications.items():
        for keys, options in indexes:
            database[collection_name].create_index(keys, **options)


def read_rruff_phase_components(data_root: Path, filename_sample_id: str) -> list[dict[str, Any]]:
    manifest_path = data_root / "multi-phase" / "rruff" / "manifests" / "rruff_multiphase_manifest_v1.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("filename_sample_id") != filename_sample_id:
                continue
            raw = json.loads(row.get("phase_components") or "[]")
            components = []
            for item in raw:
                fraction = item.get("fraction")
                fraction_unit = item.get("fraction_unit")
                if fraction_unit == "wt_percent" and fraction is not None:
                    fraction = float(fraction) / 100.0
                    basis = "weight_fraction"
                else:
                    basis = fraction_unit or "unknown"
                components.append(
                    {
                        "name": item.get("name"),
                        "formula": None,
                        "formula_normalized": None,
                        "fraction": {"value": fraction, "basis": basis},
                        "role": item.get("role"),
                        "structure": {
                            "structure_id": None,
                            "structure_ids": [],
                            "status": None,
                            "coverage": "none",
                            "certainty": "unknown",
                        },
                    }
                )
            return components
    raise ValueError(f"RRUFF multiphase manifest record not found: {filename_sample_id}")


def pattern_document(
    *,
    pattern_id: str,
    measurement_id: str,
    sample_id: str | None,
    code: str,
    source_id: str | None,
    x_values: list[Any],
    y_values: list[Any],
    modality: str = "powder_xrd",
    phase_character: str = "unknown",
    phase_components: list[dict[str, Any]] | None = None,
    dataset_role: str | None = None,
    linkage_status: str = "unlinked",
    linkage_coverage: str = "none",
    linkage_certainty: str = "unknown",
    candidate_structure_ids: list[str] | None = None,
    scan_axis: str | None = "two_theta",
    anode: str | None = None,
    wavelength: float | None = None,
    provenance: dict[str, Any] | None = None,
    file_key: str | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    x_values = list(x_values)
    y_values = list(y_values)
    scan = {
        "axis": scan_axis,
        "two_theta_min_deg": float(x_values[0]) if x_values else None,
        "two_theta_max_deg": float(x_values[-1]) if x_values else None,
        "point_count": len(x_values),
    }
    document: dict[str, Any] = {
        "pattern_id": pattern_id,
        "measurement_id": measurement_id,
        "sample_id": sample_id,
        "api_source_code": code.upper(),
        "api_source_id": source_id,
        "source": source_ref(code, source_id),
        "data_origin": "experimental",
        "modality": modality,
        "dataset_role": dataset_role,
        "phase_character": phase_character,
        "phase_components": phase_components or [],
        "structure_linkage": {
            "status": linkage_status,
            "coverage": linkage_coverage,
            "certainty": linkage_certainty,
            "candidate_structure_ids": list(candidate_structure_ids or []),
        },
        "linked_structure_ids": list(candidate_structure_ids or []),
        "has_xy": bool(x_values and len(x_values) == len(y_values)),
        "scan": scan,
        "radiation": {"anode": anode, "wavelength_angstrom": wavelength},
        "provenance": provenance or {},
        "data": {"two_theta": x_values, "intensity": y_values},
        "file": file_metadata(data_root or get_data_root(), file_key) if file_key else None,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    if document["file"] is None:
        document.pop("file")
    return document


def make_source_documents() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "SRC_RRUFF",
            "api_source_code": "RRUFF",
            "name": "RRUFF experimental powder XRD",
            "short_name": "RRUFF",
            "source_type": "external_database",
            "data_origin": "experimental",
            "modalities": ["powder_xrd"],
        },
        {
            "source_id": "SRC_DARA",
            "api_source_code": "DARA",
            "name": "DARA precursor diffraction benchmark",
            "short_name": "DARA",
            "source_type": "external_dataset",
            "data_origin": "experimental",
            "modalities": ["powder_xrd"],
        },
        {
            "source_id": "SRC_OPXRD",
            "api_source_code": "OPXRD",
            "name": "OPXRD experimental diffraction",
            "short_name": "OPXRD",
            "source_type": "external_dataset",
            "data_origin": "experimental",
            "modalities": ["powder_xrd"],
        },
        {
            "source_id": "SRC_LAB",
            "api_source_code": "LAB",
            "name": "Laboratory experimental XRD",
            "short_name": "LAB",
            "source_type": "internal_experiment",
            "data_origin": "experimental",
            "modalities": ["powder_xrd"],
        },
        {
            "source_id": "SRC_COD",
            "api_source_code": "COD",
            "name": "Crystallography Open Database",
            "short_name": "COD",
            "source_type": "external_database",
            "data_origin": "experimental",
            "modalities": ["single_crystal_xrd", "crystal_structure"],
        },
    ]


def build_rruff(
    source_db: Any,
    database: Any,
    data_root: Path,
    canonical_db: Any | None = None,
) -> dict[str, list[str]]:
    result = {"patterns": [], "structures": [], "measurements": [], "samples": []}
    if canonical_db is None:
        canonical_db = source_db

    source_id = "R080016-1"
    raw = source_db.xy_raw.find_one({"filename_sample_id": source_id})
    if raw is None:
        raise RuntimeError(f"missing RRUFF pilot record: {source_id}")
    xrd = raw.get("xrd") or {}
    metadata = raw.get("metadata") or {}
    explicit_phase_value = str(
        metadata.get("PHASE CHARACTER")
        or metadata.get("PHASE DESCRIPTION")
        or raw.get("phase_character")
        or ""
    ).casefold()
    phase_character = (
        "single_phase"
        if explicit_phase_value in {"single_phase", "single phase", "single-phase"}
        else "unknown"
    )
    sample_id = "RRUFF_SAM_R080016"
    measurement_id = "RRUFF_MEAS_R080016_1"
    pattern_id = "RRUFF_PAT_R080016_1"
    formula = normalize_formula(metadata.get("IDEAL CHEMISTRY"))
    sample = {
        "sample_id": sample_id,
        "api_source_code": "RRUFF",
        "api_source_id": raw.get("sample_id"),
        "source": source_ref("RRUFF", raw.get("sample_id")),
        "name": raw.get("mineral"),
        "formula": (raw.get("metadata") or {}).get("IDEAL CHEMISTRY"),
        "phase_character": phase_character,
        "provenance": {
            "source": "RRUFF",
            "source_id": raw.get("sample_id"),
            "label_type": "source_annotation",
            "label_method": "diffraction_sample_description",
            "evidence": metadata.get("DIFFRACTION SAMPLE DESCRIPTION"),
        },
    }
    upsert(database.samples, "sample_id", sample_id, sample)
    result["samples"].append(sample_id)

    structure_id = "STR_COD_9000253"
    existing_structure = canonical_db.structures.find_one({"structure_id": "STR_000001"}) or {}
    matched = existing_structure.get("matched_cif") or {}
    cif_key = "raw/cod/9000253.cif"
    parsed_cif = parse_cif(data_root / Path(*cif_key.split("/")))
    publication = parsed_cif.get("publication") or {}
    structure = {
        "structure_id": structure_id,
        "api_source_code": "COD",
        "api_source_id": "9000253",
        "source": source_ref("COD", "9000253"),
        "data_origin": "experimental",
        "formula": matched.get("formula") or "Ag2 S",
        "formula_normalized": normalize_formula(matched.get("formula") or "Ag2 S"),
        "mineral_name": matched.get("mineral_name") or raw.get("mineral"),
        "space_group": {
            "hm": matched.get("space_group"),
            "number": None,
        },
        "cell": matched.get("cell_parameters") or existing_structure.get("cell_parameters") or {},
        "atom_site_count": matched.get("atom_count"),
        "file": file_metadata(data_root, cif_key),
        "provenance": {
            "source": "COD",
            "source_id": "9000253",
            "source_file": cif_key,
            "label_type": "source_record",
            "label_method": "COD_CIF",
            "evidence": cif_key,
            "bibliography": publication,
        },
    }
    upsert(database.structures, "structure_id", structure_id, structure)
    result["structures"].append(structure_id)

    components = [
        {
            "name": raw.get("mineral"),
            "formula": metadata.get("IDEAL CHEMISTRY"),
            "formula_normalized": formula,
            "fraction": {"value": None, "basis": "unknown"},
            "role": "primary",
            "structure": {
                "structure_id": structure_id,
                "structure_ids": [structure_id],
                "status": "complete",
                "coverage": "complete",
                "certainty": "resolved",
            },
        }
    ]
    pattern = pattern_document(
        pattern_id=pattern_id,
        measurement_id=measurement_id,
        sample_id=sample_id,
        code="RRUFF",
        source_id=source_id,
        x_values=xrd.get("two_theta", []),
        y_values=xrd.get("intensity", []),
        phase_character=phase_character,
        phase_components=components,
        dataset_role="raw",
        linkage_status="complete",
        linkage_coverage="complete",
        linkage_certainty="resolved",
        candidate_structure_ids=[structure_id],
        provenance={
            "source": "RRUFF",
            "source_id": source_id,
            "label_type": "source_annotation",
            "label_method": "diffraction_sample_description",
            "evidence": metadata.get("DIFFRACTION SAMPLE DESCRIPTION"),
        },
        data_root=data_root,
    )
    upsert(database.patterns, "pattern_id", pattern_id, pattern)
    result["patterns"].append(pattern_id)

    measurement = {
        "measurement_id": measurement_id,
        "api_source_code": "RRUFF",
        "api_source_id": source_id,
        "source": source_ref("RRUFF", source_id),
        "sample_id": sample_id,
        "modality": "powder_xrd",
        "data_origin": "experimental",
        "conditions": {
            "radiation": None,
            "wavelength_angstrom": None,
            "scan_range": [xrd["two_theta"][0], xrd["two_theta"][-1]],
        },
        "source_file": None,
        "provenance": pattern["provenance"],
    }
    upsert(database.measurements, "measurement_id", measurement_id, measurement)
    result["measurements"].append(measurement_id)

    multi_source_id = "R040043-1"
    multi = source_db.xy_raw.find_one({"filename_sample_id": multi_source_id})
    if multi is None:
        raise RuntimeError(f"missing RRUFF multiphase record: {multi_source_id}")
    multi_xrd = multi.get("xrd") or {}
    multi_sample_id = "RRUFF_SAM_R040043"
    multi_measurement_id = "RRUFF_MEAS_R040043_1"
    multi_pattern_id = "RRUFF_PAT_R040043_1"
    multi_components = read_rruff_phase_components(data_root, multi_source_id)
    multi_pattern = pattern_document(
        pattern_id=multi_pattern_id,
        measurement_id=multi_measurement_id,
        sample_id=multi_sample_id,
        code="RRUFF",
        source_id=multi_source_id,
        x_values=multi_xrd.get("two_theta", []),
        y_values=multi_xrd.get("intensity", []),
        phase_character="multi_phase",
        phase_components=multi_components,
        dataset_role="raw",
        linkage_status="unlinked",
        provenance={
            "source": "RRUFF",
            "source_id": multi_source_id,
            "label_type": "source_annotation",
            "label_method": "diffraction_sample_description",
            "evidence": (multi.get("metadata") or {}).get("DIFFRACTION SAMPLE DESCRIPTION"),
        },
        file_key="multi-phase/rruff/RRUFF_R040043-1.txt",
        data_root=data_root,
    )
    multi_pattern["sample_id"] = multi_sample_id
    upsert(database.patterns, "pattern_id", multi_pattern_id, multi_pattern)
    result["patterns"].append(multi_pattern_id)
    multi_sample = {
        "sample_id": multi_sample_id,
        "api_source_code": "RRUFF",
        "api_source_id": multi.get("sample_id"),
        "source": source_ref("RRUFF", multi.get("sample_id")),
        "name": multi.get("mineral"),
        "formula": (multi.get("metadata") or {}).get("IDEAL CHEMISTRY"),
        "phase_character": "multi_phase",
        "provenance": multi_pattern["provenance"],
    }
    upsert(database.samples, "sample_id", multi_sample_id, multi_sample)
    result["samples"].append(multi_sample_id)
    multi_measurement = {
        "measurement_id": multi_measurement_id,
        "api_source_code": "RRUFF",
        "api_source_id": multi_source_id,
        "source": source_ref("RRUFF", multi_source_id),
        "sample_id": multi_sample_id,
        "modality": "powder_xrd",
        "data_origin": "experimental",
        "conditions": {"radiation": None, "wavelength_angstrom": None},
        "source_file": "multi-phase/rruff/RRUFF_R040043-1.txt",
        "provenance": multi_pattern["provenance"],
    }
    upsert(database.measurements, "measurement_id", multi_measurement_id, multi_measurement)
    result["measurements"].append(multi_measurement_id)
    return result


def build_dara(source_db: Any, database: Any, data_root: Path) -> dict[str, list[str]]:
    result = {"patterns": [], "measurements": [], "samples": []}
    mixture_id = "In2O3_0p3022-La(OH)3_0p5014-TiO2_0p2004"
    document = source_db.precursor_mixture_20.find_one({"mixture_id": mixture_id})
    if document is None:
        raise RuntimeError(f"missing DARA pilot record: {mixture_id}")
    components = [
        {
            "name": item.get("formula"),
            "formula": item.get("formula"),
            "formula_normalized": normalize_formula(item.get("formula")),
            "fraction": {"value": item.get("weight_fraction"), "basis": "weight_fraction"},
            "role": "precursor",
            "structure": {
                "structure_id": None,
                "structure_ids": [],
                "status": None,
                "coverage": "none",
                "certainty": "unknown",
            },
        }
        for item in document.get("components", [])
    ]
    phase_character = "multi_phase" if len(components) > 1 else "single_phase"
    for scan_name in ("2min", "8min"):
        scan = (document.get("scans") or {}).get(scan_name)
        if not scan:
            continue
        source_scan_id = f"{mixture_id}--{scan_name}"
        sample_id = f"DARA_SAM_{safe_id(mixture_id)}"
        measurement_id = f"DARA_MEAS_{safe_id(source_scan_id)}"
        pattern_id = f"DARA_PAT_{safe_id(source_scan_id)}"
        xrd = scan.get("xrd") or {}
        file_key = f"multi-phase/dara/{mixture_id}--{scan_name}.txt"
        headers = canonical_headers(data_root / Path(*file_key.split("/")))
        canonical_step_size = header_number(headers, "STEP_SIZE")
        canonical_anode = headers.get("ANODE_MATERIAL")
        provenance = {
            "source": "DARA",
            "source_id": source_scan_id,
            "label_type": "source_ground_truth",
            "label_method": "known_precursor_mixture",
            "evidence": document.get("record_key"),
        }
        sample_provenance = {
            **provenance,
            "source_id": mixture_id,
        }
        sample = {
            "sample_id": sample_id,
            "api_source_code": "DARA",
            "api_source_id": mixture_id,
            "source": source_ref("DARA", mixture_id),
            "name": document.get("mixture_id"),
            "formula": None,
            "phase_character": phase_character,
            "provenance": sample_provenance,
        }
        upsert(database.samples, "sample_id", sample_id, sample)
        if sample_id not in result["samples"]:
            result["samples"].append(sample_id)
        pattern = pattern_document(
            pattern_id=pattern_id,
            measurement_id=measurement_id,
            sample_id=sample_id,
            code="DARA",
            source_id=source_scan_id,
            x_values=xrd.get("two_theta", []),
            y_values=xrd.get("intensity", []),
            phase_character=phase_character,
            phase_components=components,
            dataset_role="precursor_mixture_benchmark",
            linkage_status="unlinked",
            anode=canonical_anode,
            wavelength=((scan.get("wavelength") or {}).get("k_alpha_1_angstrom")),
            provenance=provenance,
            file_key=file_key,
            data_root=data_root,
        )
        upsert(database.patterns, "pattern_id", pattern_id, pattern)
        result["patterns"].append(pattern_id)
        measurement = {
            "measurement_id": measurement_id,
            "api_source_code": "DARA",
            "api_source_id": source_scan_id,
            "source": source_ref("DARA", source_scan_id),
            "sample_id": sample_id,
            "modality": "powder_xrd",
            "data_origin": "experimental",
            "conditions": {
                "anode": canonical_anode,
                "radiation": (scan.get("wavelength") or {}).get("intended"),
                "wavelength_angstrom": (scan.get("wavelength") or {}).get("k_alpha_1_angstrom"),
                "scan_range": [
                    (scan.get("two_theta_range") or {}).get("start"),
                    (scan.get("two_theta_range") or {}).get("end"),
                ],
                "step_size": canonical_step_size,
                "counting_time_seconds": (scan.get("scan_meta") or {}).get("common_counting_time_seconds"),
                "scan_program": (scan.get("scan_meta") or {}).get("mode"),
            },
            "source_file": file_key,
            "provenance": provenance,
        }
        upsert(database.measurements, "measurement_id", measurement_id, measurement)
        result["measurements"].append(measurement_id)
    return result


def _read_dara_single_precursor(path: Path) -> tuple[dict[str, str], list[float], list[int | float]]:
    headers = canonical_headers(path)
    x_values: list[float] = []
    y_values: list[int | float] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) != 2:
            raise ValueError(f"invalid DARA XY row at {path}:{line_number}")
        try:
            x_value = float(fields[0])
            y_value = float(fields[1])
        except ValueError as exc:
            raise ValueError(f"invalid DARA XY value at {path}:{line_number}") from exc
        x_values.append(x_value)
        y_values.append(int(y_value) if y_value.is_integer() else y_value)
    if not x_values or len(x_values) != len(y_values):
        raise ValueError(f"DARA canonical pattern has invalid XY arrays: {path}")
    return headers, x_values, y_values


def build_dara_single_precursors(database: Any, data_root: Path) -> dict[str, list[str]]:
    result = {"patterns": [], "measurements": [], "samples": []}
    precursor_root = data_root / "powder" / "dara"
    for path in sorted(precursor_root.glob("*.txt")):
        headers, x_values, y_values = _read_dara_single_precursor(path)
        dataset_group = headers.get("DATASET_GROUP", "").casefold()
        if dataset_group not in {
            "singple_phase_precursor_patterns",
            "single_phase_precursor_patterns",
        }:
            continue
        formula = headers.get("SAMPLE_ID") or path.stem
        safe_formula = safe_id(formula)
        sample_id = f"DARA_SAM_{safe_formula}_SINGLE_PRECURSOR"
        measurement_id = f"DARA_MEAS_{safe_formula}_SINGLE_PRECURSOR"
        pattern_id = f"DARA_PAT_{safe_formula}_SINGLE_PRECURSOR"
        file_key = f"powder/dara/{path.name}"
        wavelength = header_number(headers, "WAVELENGTH")
        counting_time = header_number(headers, "COUNTING_TIME")
        radiation = None
        wavelength_source = headers.get("WAVELENGTH_SOURCE", "")
        intended_match = re.search(r"intended\s*=\s*([^,;]+)", wavelength_source, re.IGNORECASE)
        if intended_match:
            radiation = intended_match.group(1).strip()
        phase_components = [
            {
                "name": formula,
                "formula": formula,
                "formula_normalized": normalize_formula(formula),
                "fraction": {"value": None, "basis": "unknown"},
                "role": "precursor",
                "structure": {
                    "structure_id": None,
                    "structure_ids": [],
                    "status": None,
                    "coverage": "none",
                    "certainty": "unknown",
                },
            }
        ]
        provenance = {
            "source": "DARA",
            "source_id": formula,
            "label_type": "source_ground_truth",
            "label_method": "known_single_precursor",
            "evidence": headers.get("ORIGINAL_RELATIVE_PATH") or headers.get("DATASET_GROUP"),
        }
        sample = {
            "sample_id": sample_id,
            "api_source_code": "DARA",
            "api_source_id": formula,
            "source": source_ref("DARA", formula),
            "name": formula,
            "formula": formula,
            "phase_character": "single_phase",
            "provenance": provenance,
        }
        upsert(database.samples, "sample_id", sample_id, sample)
        result["samples"].append(sample_id)
        pattern = pattern_document(
            pattern_id=pattern_id,
            measurement_id=measurement_id,
            sample_id=sample_id,
            code="DARA",
            source_id=formula,
            x_values=x_values,
            y_values=y_values,
            phase_character="single_phase",
            phase_components=phase_components,
            dataset_role="single_phase_precursor",
            linkage_status="unlinked",
            anode=headers.get("ANODE_MATERIAL"),
            wavelength=wavelength,
            provenance=provenance,
            file_key=file_key,
            data_root=data_root,
        )
        upsert(database.patterns, "pattern_id", pattern_id, pattern)
        result["patterns"].append(pattern_id)
        measurement = {
            "measurement_id": measurement_id,
            "api_source_code": "DARA",
            "api_source_id": formula,
            "source": source_ref("DARA", formula),
            "sample_id": sample_id,
            "modality": "powder_xrd",
            "data_origin": "experimental",
            "conditions": {
                "anode": headers.get("ANODE_MATERIAL"),
                "radiation": radiation,
                "wavelength_angstrom": wavelength,
                "scan_range": [x_values[0], x_values[-1]],
                "step_size": header_number(headers, "STEP_SIZE"),
                "counting_time_seconds": counting_time,
                "scan_program": headers.get("SCAN_MODE"),
            },
            "source_file": file_key,
            "provenance": provenance,
        }
        upsert(database.measurements, "measurement_id", measurement_id, measurement)
        result["measurements"].append(measurement_id)
    return result


def build_opxrd(
    source_db: Any,
    database: Any,
    data_root: Path,
) -> dict[str, list[str]]:
    result = {"patterns": [], "measurements": []}
    record_key = "OPXRD/CNRS/pattern_0.json"
    document = source_db.patterns.find_one({"record_key": record_key})
    if document is None:
        raise RuntimeError(f"missing OPXRD pilot record: {record_key}")
    xrd = document.get("xrd") or {}
    xray_info = (document.get("label") or {}).get("xray_info") or {}
    raw_wavelength = xray_info.get("primary_wavelength")
    try:
        wavelength = float(raw_wavelength) if raw_wavelength not in (None, "") else None
    except (TypeError, ValueError):
        wavelength = None
    pattern_id = "OPXRD_PAT_CNRS_pattern_0"
    measurement_id = "OPXRD_MEAS_CNRS_pattern_0"
    phase_count = document.get("phase_count")
    phase_components = [
        {
            "name": None,
            "formula": None,
            "formula_normalized": None,
            "fraction": {"value": None, "basis": "unknown"},
            "role": "primary",
            "structure": {"structure_id": None, "status": None},
        }
    ] if phase_count == 1 else []
    provenance = {
        "source": "OPXRD",
        "source_id": record_key,
        "label_type": "source_metadata",
        "label_method": "phase_count",
        "evidence": f"source phase_count={phase_count}",
    }
    pattern = pattern_document(
        pattern_id=pattern_id,
        measurement_id=measurement_id,
        sample_id=None,
        code="OPXRD",
        source_id=record_key,
        x_values=xrd.get("two_theta", []),
        y_values=xrd.get("intensity", []),
        phase_character="single_phase" if phase_count == 1 else "unknown",
        phase_components=phase_components,
        dataset_role="raw",
        linkage_status="unlinked",
        wavelength=wavelength,
        provenance=provenance,
        data_root=data_root,
    )
    upsert(database.patterns, "pattern_id", pattern_id, pattern)
    result["patterns"].append(pattern_id)
    measurement = {
        "measurement_id": measurement_id,
        "api_source_code": "OPXRD",
        "api_source_id": record_key,
        "source": source_ref("OPXRD", record_key),
        "sample_id": None,
        "modality": "powder_xrd",
        "data_origin": "experimental",
        "conditions": {
            "radiation": (
                xray_info.get("radiation")
                or xray_info.get("radiation_type")
            ),
            "wavelength_angstrom": wavelength,
            "scan_range": [xrd.get("two_theta_min"), xrd.get("two_theta_max")],
        },
        "source_file": None,
        "provenance": provenance,
    }
    upsert(database.measurements, "measurement_id", measurement_id, measurement)
    result["measurements"].append(measurement_id)
    return result


def build_lab(
    source_db: Any,
    database: Any,
    data_root: Path,
) -> dict[str, list[str]]:
    result = {"patterns": [], "measurements": [], "samples": []}
    source_pattern_id = "LAB_PAT_000001"
    source_pattern = source_db.patterns.find_one({"pattern_id": source_pattern_id})
    source_measurement = source_db.measurements.find_one({"measurement_id": "LAB_MEAS_000001"})
    source_sample = source_db.samples.find_one({"sample_id": "LAB_SAM_000001"})
    if not source_pattern or not source_measurement or not source_sample:
        raise RuntimeError("missing LAB pilot records in crystaldb")
    sample_id = "LAB_SAM_000001"
    measurement_id = "LAB_MEAS_000001"
    pattern_id = "LAB_PAT_000001"
    xrd = source_pattern.get("xrd") or {}
    provenance = {
        "source": "LAB",
        "source_id": pattern_id,
        "label_type": "unknown",
        "label_method": None,
        "evidence": source_sample.get("source_sample_label"),
        "notes": ["No structure linkage was copied because none is documented for this pilot sample."],
    }
    sample = {
        "sample_id": sample_id,
        "api_source_code": "LAB",
        "api_source_id": sample_id,
        "source": source_ref("LAB", sample_id),
        "name": source_sample.get("source_sample_label"),
        "formula": source_sample.get("nominal_element_ratio"),
        "phase_character": "unknown",
        "provenance": provenance,
    }
    upsert(database.samples, "sample_id", sample_id, sample)
    result["samples"].append(sample_id)
    file_key = (source_pattern.get("file") or {}).get("key")
    pattern = pattern_document(
        pattern_id=pattern_id,
        measurement_id=measurement_id,
        sample_id=sample_id,
        code="LAB",
        source_id=pattern_id,
        x_values=xrd.get("two_theta", []),
        y_values=xrd.get("intensity", []),
        phase_character="unknown",
        phase_components=[],
        dataset_role="canonical",
        linkage_status="unlinked",
        wavelength=(source_measurement.get("radiation") or {}).get("wavelength_kalpha1_angstrom"),
        provenance=provenance,
        file_key=file_key,
        data_root=data_root,
    )
    upsert(database.patterns, "pattern_id", pattern_id, pattern)
    result["patterns"].append(pattern_id)
    measurement = {
        "measurement_id": measurement_id,
        "api_source_code": "LAB",
        "api_source_id": measurement_id,
        "source": source_ref("LAB", measurement_id),
        "sample_id": sample_id,
        "modality": "powder_xrd",
        "data_origin": "experimental",
        "conditions": {
            "radiation": (source_measurement.get("radiation") or {}).get("characteristic"),
            "wavelength_angstrom": (source_measurement.get("radiation") or {}).get("wavelength_kalpha1_angstrom"),
            "scan_range": [
                (source_pattern.get("scan") or {}).get("start_2theta_deg"),
                (source_pattern.get("scan") or {}).get("stop_2theta_deg"),
            ],
        },
        "source_file": file_key,
        "provenance": provenance,
    }
    upsert(database.measurements, "measurement_id", measurement_id, measurement)
    result["measurements"].append(measurement_id)
    return result


def build_cod(source_db: Any, database: Any, data_root: Path) -> dict[str, list[str]]:
    result = {"structures": [], "measurements": [], "reflection_sets": []}
    source_structure = source_db.structures.find_one({"source_structure_id": "1100908"})
    source_measurement = source_db.measurements.find_one({"source_record_id": "1100908"})
    source_reflection = source_db.reflection_sets.find_one({"source_record_id": "1100908"})
    if not source_structure or not source_measurement or not source_reflection:
        raise RuntimeError("missing COD pilot records: 1100908")
    structure_id = "STR_COD_1100908"
    measurement_id = "COD_MEAS_1100908"
    reflection_id = "REFL_COD_1100908"
    structure_file_key = (source_structure.get("file") or {}).get("key")
    structure = {
        "structure_id": structure_id,
        "api_source_code": "COD",
        "api_source_id": "1100908",
        "source": source_ref("COD", "1100908"),
        "data_origin": "experimental",
        "formula": source_structure.get("formula"),
        "formula_normalized": source_structure.get("formula_reduced"),
        "mineral_name": source_structure.get("source_structure_name"),
        "space_group": source_structure.get("space_group") or {},
        "cell": source_structure.get("cell") or source_structure.get("cell_parameters") or {},
        "atom_site_count": source_structure.get("atom_count"),
        "file": file_metadata(data_root, structure_file_key),
        "provenance": {
            "source": "COD",
            "source_id": "1100908",
            "source_file": structure_file_key,
            "label_type": "source_record",
            "label_method": "COD_CIF",
            "evidence": structure_file_key,
        },
    }
    upsert(database.structures, "structure_id", structure_id, structure)
    result["structures"].append(structure_id)
    measurement = {
        "measurement_id": measurement_id,
        "api_source_code": "COD",
        "api_source_id": "1100908",
        "source": source_ref("COD", "1100908"),
        "sample_id": None,
        "structure_id": structure_id,
        "reflection_set_id": reflection_id,
        "modality": "single_crystal_xrd",
        "data_origin": "experimental",
        "conditions": source_measurement.get("experimental_conditions") or {},
        "source_file": (source_reflection.get("file") or {}).get("key"),
        "provenance": source_measurement.get("provenance") or {},
    }
    upsert(database.measurements, "measurement_id", measurement_id, measurement)
    result["measurements"].append(measurement_id)
    reflection_file_key = (source_reflection.get("file") or {}).get("key")
    reflection = {
        "reflection_set_id": reflection_id,
        "measurement_id": measurement_id,
        "structure_id": structure_id,
        "api_source_code": "COD",
        "api_source_id": "1100908",
        "source": source_ref("COD", "1100908"),
        "data_origin": "experimental",
        "modality": "single_crystal_xrd",
        "reflection_count": source_reflection.get("reflection_count"),
        "observed_quantity": source_reflection.get("observed_quantity"),
        "reflection_fields": source_reflection.get("reflection_fields") or [],
        "file": file_metadata(data_root, reflection_file_key),
        "provenance": source_reflection.get("provenance") or {},
    }
    upsert(database.reflection_sets, "reflection_set_id", reflection_id, reflection)
    result["reflection_sets"].append(reflection_id)
    return result


def build_pilot(uri: str, database_name: str, data_root: Path) -> dict[str, Any]:
    if database_name.casefold() in FORBIDDEN_DATABASES:
        raise ValueError(
            f"Refusing to write database {database_name!r}; "
            f"pilot database must not be one of {sorted(FORBIDDEN_DATABASES)}"
        )
    if database_name.casefold() != DEFAULT_DATABASE.casefold():
        raise ValueError(
            f"Refusing to rebuild database {database_name!r}; "
            f"only the isolated {DEFAULT_DATABASE!r} database may be rebuilt"
        )
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    client.drop_database(DEFAULT_DATABASE)
    source_db = client[SOURCE_DATABASE]
    pilot_db = client[DEFAULT_DATABASE]
    ensure_indexes(pilot_db)

    for document in make_source_documents():
        upsert(pilot_db.sources, "source_id", document["source_id"], document)

    counts: dict[str, Any] = {}
    counts["rruff"] = build_rruff(client["rruff"], pilot_db, data_root, source_db)
    counts["dara"] = build_dara(client["dara"], pilot_db, data_root)
    counts["dara_single_precursors"] = build_dara_single_precursors(pilot_db, data_root)
    counts["opxrd"] = build_opxrd(client["opxrd"], pilot_db, data_root)
    counts["lab"] = build_lab(source_db, pilot_db, data_root)
    counts["cod"] = build_cod(source_db, pilot_db, data_root)

    relations = [
        {
            "relation_id": "REL_RRUFF_PAT_R080016_1_STR_COD_9000253",
            "subject_type": "pattern",
            "subject_id": "RRUFF_PAT_R080016_1",
            "predicate": "has_structure_linkage",
            "object_type": "structure",
            "object_id": "STR_COD_9000253",
            "status": "complete",
            "provenance": {"source": "RRUFF", "method": "existing_rruff_structure_link"},
        },
        {
            "relation_id": "REL_REFL_COD_1100908_STR_COD_1100908",
            "subject_type": "reflection_set",
            "subject_id": "REFL_COD_1100908",
            "predicate": "measures_structure",
            "object_type": "structure",
            "object_id": "STR_COD_1100908",
            "status": "complete",
            "provenance": {"source": "COD", "method": "shared_source_record_id"},
        },
    ]
    for relation in relations:
        upsert(pilot_db.relations, "relation_id", relation["relation_id"], relation)

    release = {
        "release_id": "crystaldb-api-pilot-v0.1.2",
        "api_version": "v1",
        "api_release": "0.1.2",
        "dataset_release": "crystaldb-api-pilot-v0.1.2",
        "database": DEFAULT_DATABASE,
        "generated_at": now_utc(),
        "read_only": True,
        "source_databases": ["rruff", "opxrd", "dara", "crystaldb"],
        "notes": [
            "Pilot records are real source/canonical records selected for API contract validation.",
            "No source database is written by this builder.",
        ],
    }
    upsert(pilot_db.releases, "release_id", release["release_id"], release)

    report = {
        "schema_version": "crystaldb_api_pilot_build_v012",
        "generated_at": now_utc(),
        "target_database": DEFAULT_DATABASE,
        "source_databases_read": ["rruff", "opxrd", "dara", "crystaldb"],
        "counts": counts,
        "database_counts": {
            collection: pilot_db[collection].count_documents({})
            for collection in (
                "sources",
                "samples",
                "measurements",
                "patterns",
                "structures",
                "reflection_sets",
                "relations",
                "releases",
            )
        },
        "unavailable_pilot_categories": [],
    }
    report_path = data_root / "mappings" / "api_pilot_v012_build_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    client.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uri",
        default=os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"),
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("CRYSTALDB_MONGO_DB", DEFAULT_DATABASE),
    )
    parser.add_argument("--data-root", default=os.environ.get("CRYSTALDB_DATA_ROOT"))
    args = parser.parse_args()
    report = build_pilot(args.uri, args.database, get_data_root(args.data_root))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
