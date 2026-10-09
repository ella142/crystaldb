"""Build a read-only production integration proposal for recovered PowBase CIFs.

The proposal is derived from the existing source-structure recovery output and
the already staged CIFs.  It never writes MongoDB, source archives, or
canonical records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gemmi

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RECOVERY_JSON = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_source_structure_recovery_v1.json"
)
DEFAULT_INCLUSION_CSV = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_v1_inclusion_manifest.csv"
)
DEFAULT_PRODUCTION_JSON = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_production_integration_v1.json"
)
DEFAULT_STAGING_ROOT = (
    PROJECT_ROOT / "data" / "staging" / "powbase_source_structures_v1"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "mappings"

TARGET_ENTRY_IDS = ["106", "113", "116", "117", "124", "125", "157", "159", "160"]
SUPPORTED_LINK_ENTRY_IDS = ["113", "116", "117", "124", "125", "159", "160"]
AMBIGUOUS_ENTRY_IDS = ["106", "157"]
EXPECTED_INCOMPLETE_157_MODELS = 4

COLLECTIONS = (
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


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_inclusion_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {row["entry_id"]: row for row in csv.DictReader(stream)}


def _parse_json_cell(value: str | None, default: Any) -> Any:
    if not value:
        return deepcopy(default)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return deepcopy(default)


def _safe_id_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return token or "UNKNOWN"


def _structure_id(entry_id: str, model_id: str) -> str:
    return f"STR_POWBASE_{entry_id}_{_safe_id_token(model_id)}"


def _relation_id(entry_id: str, structure_id: str) -> str:
    return f"REL_POWBASE_{entry_id}_{structure_id}"


def _resolve_staging_path(staging_root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    candidate = candidate.resolve()
    root = staging_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"CIF path escapes staging root: {candidate}") from exc
    return candidate


def _cif_validation(path: Path) -> dict[str, Any]:
    cif = gemmi.cif.read_file(str(path))
    if len(cif) != 1:
        raise ValueError(f"expected one CIF block in {path}, found {len(cif)}")
    block = cif.sole_block()

    def value(tag: str) -> str | None:
        raw = block.find_value(tag)
        return raw if raw not in ("", None) else None

    atom_labels = block.find_loop("_atom_site_label")
    atom_count = len(atom_labels) if atom_labels is not None else 0
    sg = value("_space_group_name_H-M_alt") or value("_symmetry_space_group_name_H-M")
    cell_tags = (
        "_cell_length_a",
        "_cell_length_b",
        "_cell_length_c",
        "_cell_angle_alpha",
        "_cell_angle_beta",
        "_cell_angle_gamma",
    )
    cell_values = [float(value(tag)) for tag in cell_tags]
    return {
        "status": "passed",
        "block_name": block.name,
        "atom_site_count": atom_count,
        "space_group_raw": sg,
        "cell": {
            "a": cell_values[0],
            "b": cell_values[1],
            "c": cell_values[2],
            "alpha": cell_values[3],
            "beta": cell_values[4],
            "gamma": cell_values[5],
        },
        "sha256": _sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _make_provenance(
    recovery: dict[str, Any],
    inclusion: dict[str, str],
    cif_path: Path | None,
) -> dict[str, Any]:
    return {
        "source": "POWBASE",
        "source_id": recovery["entry_id"],
        "source_archive_path": recovery["source_archive_path"],
        "source_archive_sha256": recovery["source_archive_sha256"],
        "source_member": recovery["source_member"],
        "source_member_sha256": recovery["source_member_sha256"],
        "source_index_label_raw": inclusion["source_label_raw"],
        "raw_index_text": inclusion["raw_index_text"],
        "raw_hash_delimited_tokens": _parse_json_cell(
            inclusion["raw_hash_delimited_tokens"], []
        ),
        "raw_bibliographic_comment_text": inclusion[
            "raw_bibliographic_comment_text"
        ],
        "source_model_id": recovery["source_model_id"],
        "source_model_name": recovery["model_name"],
        "source_model_format": recovery["refinement_model_format"],
        "source_evidence": recovery["source_evidence"],
        "recovery_method": "source_literal_structural_fields_only",
        "cif_staging_path": str(cif_path.relative_to(PROJECT_ROOT))
        if cif_path is not None
        else None,
        "cif_sha256": _sha256_file(cif_path) if cif_path is not None else None,
    }


def _make_structure_document(
    recovery: dict[str, Any],
    inclusion: dict[str, str],
    cif_path: Path,
    cif_info: dict[str, Any],
) -> dict[str, Any]:
    entry_id = recovery["entry_id"]
    structure_id = _structure_id(entry_id, recovery["source_model_id"])
    cell = {
        key: recovery[key]
        for key in ("a", "b", "c", "alpha", "beta", "gamma")
    }
    atom_sites = deepcopy(recovery.get("atom_sites") or [])
    return {
        "structure_id": structure_id,
        "api_source_code": "POWBASE",
        "api_source_id": entry_id,
        "source": {"code": "POWBASE", "source_id": entry_id},
        "data_origin": "experimental",
        "structure_format": "CIF",
        "formula": None,
        "formula_normalized": None,
        "mineral_name": recovery["model_name"] or None,
        "space_group": {
            "hm": recovery["space_group_raw"],
            "number": None,
        },
        "cell": cell,
        "atom_site_count": len(atom_sites),
        "atomic_sites": atom_sites,
        "file": {
            "key": str(cif_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sha256": cif_info["sha256"],
            "size_bytes": cif_info["size_bytes"],
        },
        "parse_status": "ok",
        "parse_warnings": [],
        "provenance": _make_provenance(recovery, inclusion, cif_path),
        "source_literal_fields": {
            "source_label_raw": inclusion["source_label_raw"],
            "source_model_id": recovery["source_model_id"],
            "source_model_name": recovery["model_name"],
            "space_group_raw": recovery["space_group_raw"],
            "cell": cell,
            "atom_sites": atom_sites,
        },
    }


def _make_relation(
    entry_id: str,
    pattern_id: str,
    structure_id: str,
    inclusion: dict[str, str],
) -> dict[str, Any]:
    return {
        "relation_id": _relation_id(entry_id, structure_id),
        "subject_type": "pattern",
        "subject_id": pattern_id,
        "predicate": "has_structure_linkage",
        "object_type": "structure",
        "object_id": structure_id,
        "status": "complete",
        "provenance": {
            "source": "POWBASE",
            "source_id": entry_id,
            "method": "existing_recovery_source_link_supported",
            "raw_index_text": inclusion["raw_index_text"],
        },
    }


def _pattern_linkage_proposals(
    records_by_entry: dict[str, list[dict[str, Any]]],
    inclusion_rows: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for entry_id in TARGET_ENTRY_IDS:
        rows = records_by_entry[entry_id]
        recoverable_ids = [
            _structure_id(entry_id, row["source_model_id"])
            for row in rows
            if row["cif_recoverable"] and row["cif_validation_status"] == "passed"
        ]
        if entry_id in SUPPORTED_LINK_ENTRY_IDS:
            status = "complete"
            coverage = "complete"
            certainty = "resolved"
            reason = "One recoverable source model with source-supported linkage."
        elif entry_id == "106":
            status = "ambiguous"
            coverage = "partial"
            certainty = "ambiguous"
            reason = (
                "The source profile contains two explicit FullProf phase models; "
                "both CIFs are proposed, but no unique structure link is forced."
            )
        else:
            status = "ambiguous"
            coverage = "none"
            certainty = "ambiguous"
            reason = (
                "The source contains five entry-157 models, but four are incomplete "
                "and the one recoverable model is not uniquely linkable."
            )
        proposals.append(
            {
                "pattern_id": f"POWBASE_PAT_{entry_id}",
                "entry_id": entry_id,
                "proposed_structure_linkage": {
                    "status": status,
                    "coverage": coverage,
                    "certainty": certainty,
                    "candidate_structure_ids": recoverable_ids
                    if entry_id == "106"
                    else recoverable_ids if entry_id in SUPPORTED_LINK_ENTRY_IDS else [],
                },
                "source_label_raw": inclusion_rows[entry_id]["source_label_raw"],
                "review_reason": reason,
            }
        )
    return proposals


def _entry_116_wavelength_fix(
    recovery_audit: dict[str, Any],
    canonical_pattern: dict[str, Any] | None = None,
    canonical_measurement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    discrepancy = next(
        row
        for row in recovery_audit["wavelength_discrepancy"]["records"]
        if row["entry_id"] == "116"
    )
    return {
        "entry_id": "116",
        "pattern_id": "POWBASE_PAT_116",
        "source_line": discrepancy["source_wavelength_representation"][0],
        "explicit_wavelengths_angstrom": discrepancy[
            "parsed_numeric_wavelength_angstrom"
        ],
        "proposed_primary_wavelength_angstrom": 1.54056,
        "proposed_secondary_wavelength_angstrom": 1.54439,
        "proposed_wavelength_values_angstrom": [1.54056, 1.54439],
        "current_canonical_pattern": {
            "wavelength_angstrom": (canonical_pattern or {})
            .get("radiation", {})
            .get("wavelength_angstrom"),
            "wavelength_kalpha2_angstrom": (canonical_pattern or {})
            .get("radiation", {})
            .get("wavelength_kalpha2_angstrom"),
        },
        "current_canonical_measurement": {
            "wavelength_angstrom": (canonical_measurement or {}).get(
                "wavelength_angstrom"
            ),
            "wavelength_kalpha2_angstrom": (canonical_measurement or {}).get(
                "wavelength_kalpha2_angstrom"
            ),
        },
        "reason": (
            "The source labels Alpha1 and Alpha2 explicitly. The proposal preserves "
            "both values without changing the source or canonical record."
        ),
    }


def _load_canonical_document(entry_id: str, collection: str) -> dict[str, Any] | None:
    path = (
        PROJECT_ROOT
        / "data"
        / "staging"
        / "powbase_canonical_v1"
        / "records"
        / collection
        / f"POWBASE_{'PAT' if collection == 'patterns' else 'MEAS'}_{entry_id}.json"
    )
    if not path.is_file():
        return None
    return _read_json(path)


def _mongo_collision_check(
    structure_ids: list[str],
    relation_ids: list[str],
    uri: str,
    database_name: str,
) -> dict[str, Any]:
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        database = client[database_name]
        structure_collisions = [
            row["structure_id"]
            for row in database.structures.find(
                {"structure_id": {"$in": structure_ids}},
                {"_id": 0, "structure_id": 1},
            )
        ]
        relation_collisions = [
            row["relation_id"]
            for row in database.relations.find(
                {"relation_id": {"$in": relation_ids}},
                {"_id": 0, "relation_id": 1},
            )
        ]
        client.close()
        return {
            "available": True,
            "read_only": True,
            "database": database_name,
            "structure_collisions": sorted(structure_collisions),
            "relation_collisions": sorted(relation_collisions),
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - depends on local Mongo
        return {
            "available": False,
            "read_only": True,
            "database": database_name,
            "structure_collisions": [],
            "relation_collisions": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_dryrun(
    recovery_path: Path = DEFAULT_RECOVERY_JSON,
    inclusion_path: Path = DEFAULT_INCLUSION_CSV,
    production_path: Path = DEFAULT_PRODUCTION_JSON,
    staging_root: Path = DEFAULT_STAGING_ROOT,
    check_mongo: bool = False,
    mongo_uri: str | None = None,
    mongo_database: str = "crystaldb",
) -> dict[str, Any]:
    recovery_audit = _read_json(recovery_path)
    inclusion_rows = _read_inclusion_rows(inclusion_path)
    production = _read_json(production_path)
    records = recovery_audit["records"]
    records_by_entry: dict[str, list[dict[str, Any]]] = {
        entry_id: [row for row in records if row["entry_id"] == entry_id]
        for entry_id in TARGET_ENTRY_IDS
    }
    if any(not rows for rows in records_by_entry.values()):
        missing = [entry_id for entry_id, rows in records_by_entry.items() if not rows]
        raise ValueError(f"recovery output missing entries: {missing}")

    structures: list[dict[str, Any]] = []
    cif_validations: list[dict[str, Any]] = []
    source_evidence_only: list[dict[str, Any]] = []
    for entry_id in TARGET_ENTRY_IDS:
        for row in records_by_entry[entry_id]:
            if not row["cif_recoverable"]:
                source_evidence_only.append(
                    {
                        "entry_id": entry_id,
                        "pattern_id": row["pattern_id"],
                        "source_member": row["source_member"],
                        "source_model_id": row["source_model_id"],
                        "model_name": row["model_name"],
                        "refinement_model_format": row["refinement_model_format"],
                        "unit_cell_complete": row["unit_cell_complete"],
                        "cell": {
                            key: row.get(key)
                            for key in ("a", "b", "c", "alpha", "beta", "gamma")
                        },
                        "space_group_raw": row["space_group_raw"],
                        "atom_site_count": row["atom_site_count"],
                        "atom_sites": deepcopy(row.get("atom_sites") or []),
                        "source_evidence": deepcopy(row.get("source_evidence") or []),
                        "reason": row["cif_validation_status"],
                    }
                )
                continue
            if row["cif_validation_status"] != "passed":
                raise ValueError(
                    f"recoverable model did not pass CIF validation: "
                    f"{entry_id}/{row['source_model_id']}"
                )
            cif_path = _resolve_staging_path(staging_root, row["staging_cif_path"])
            cif_info = _cif_validation(cif_path)
            cif_validations.append(
                {
                    "entry_id": entry_id,
                    "source_model_id": row["source_model_id"],
                    "path": str(cif_path.relative_to(PROJECT_ROOT)),
                    **cif_info,
                }
            )
            structures.append(
                _make_structure_document(
                    row,
                    inclusion_rows[entry_id],
                    cif_path,
                    cif_info,
                )
            )

    structure_ids = [row["structure_id"] for row in structures]
    relation_entries = {
        entry_id: next(row for row in records_by_entry[entry_id] if row["cif_recoverable"])
        for entry_id in SUPPORTED_LINK_ENTRY_IDS
    }
    relations = [
        _make_relation(
            entry_id,
            relation_entries[entry_id]["pattern_id"],
            _structure_id(entry_id, relation_entries[entry_id]["source_model_id"]),
            inclusion_rows[entry_id],
        )
        for entry_id in SUPPORTED_LINK_ENTRY_IDS
    ]
    relation_ids = [row["relation_id"] for row in relations]

    local_duplicate_ids = {
        "structure_ids": sorted(
            {value for value in structure_ids if structure_ids.count(value) > 1}
        ),
        "relation_ids": sorted(
            {value for value in relation_ids if relation_ids.count(value) > 1}
        ),
    }
    structure_id_set = set(structure_ids)
    pattern_id_set = {f"POWBASE_PAT_{entry_id}" for entry_id in TARGET_ENTRY_IDS}
    orphan_relations = [
        relation["relation_id"]
        for relation in relations
        if relation["object_id"] not in structure_id_set
        or relation["subject_id"] not in pattern_id_set
    ]
    provenance_errors = [
        structure["structure_id"]
        for structure in structures
        if not (
            structure["provenance"].get("source_archive_sha256")
            and structure["provenance"].get("source_member_sha256")
            and structure["provenance"].get("raw_index_text")
        )
    ]

    wavelength_fix = _entry_116_wavelength_fix(
        recovery_audit,
        _load_canonical_document("116", "patterns"),
        _load_canonical_document("116", "measurements"),
    )

    baseline_counts = deepcopy(production["production_final_counts"])
    proposed_counts = deepcopy(baseline_counts)
    proposed_counts["structures"] += len(structures)
    proposed_counts["relations"] += len(relations)
    count_delta = {
        collection: proposed_counts[collection] - baseline_counts[collection]
        for collection in COLLECTIONS
    }

    mongo_check = {
        "available": False,
        "read_only": True,
        "database": mongo_database,
        "structure_collisions": [],
        "relation_collisions": [],
        "error": "not requested",
    }
    if check_mongo:
        mongo_check = _mongo_collision_check(
            structure_ids,
            relation_ids,
            mongo_uri or os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"),
            mongo_database,
        )

    entry_157_literal_values = [
        site["y"]
        for row in records_by_entry["157"]
        if row["source_model_id"] == "STR(C_1)"
        for site in row.get("atom_sites") or []
        if site["label"] == "Al" and site["raw_line"].find("y 51323") >= 0
    ]
    if entry_157_literal_values != [51323.0]:
        raise ValueError(
            "entry 157 literal source value was not preserved exactly: "
            f"{entry_157_literal_values}"
        )

    return {
        "schema_version": "powbase_source_structure_integration_dryrun_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "scope": {
            "entry_ids": TARGET_ENTRY_IDS,
            "recovery_input": str(recovery_path.resolve()),
            "staging_cif_root": str(staging_root.resolve()),
        },
        "structures_to_add": structures,
        "relations_to_add": relations,
        "pattern_linkage_proposals": _pattern_linkage_proposals(
            records_by_entry, inclusion_rows
        ),
        "source_evidence_only_models": source_evidence_only,
        "ambiguous_entries": [
            {
                "entry_id": "106",
                "reason": "Two explicit source phase models; both CIFs proposed, no unique link.",
                "candidate_structure_ids": [
                    row["structure_id"]
                    for row in structures
                    if row["provenance"]["source_id"] == "106"
                ],
            },
            {
                "entry_id": "157",
                "reason": (
                    "Five source models; four incomplete and one recoverable, "
                    "so no unique link is forced."
                ),
                "candidate_structure_ids": [],
                "source_evidence_only_model_count": len(source_evidence_only),
            },
        ],
        "entry_116_wavelength_fix": wavelength_fix,
        "entry_157_literal_source_value": {
            "value": "51323",
            "numeric_parse": 51323.0,
            "preserved": True,
            "note": "Preserved as source evidence; no correction or normalization applied.",
        },
        "cif_validation": {
            "all_passed": all(row["status"] == "passed" for row in cif_validations),
            "records": cif_validations,
        },
        "validation": {
            "proposed_structure_count": len(structures),
            "proposed_relation_count": len(relations),
            "expected_proposed_structure_count": 10,
            "expected_proposed_relation_count": 7,
            "local_duplicate_ids": local_duplicate_ids,
            "orphan_relations": orphan_relations,
            "provenance_errors": provenance_errors,
            "source_evidence_only_entry_157_count": len(source_evidence_only),
            "source_evidence_only_entry_157_expected": EXPECTED_INCOMPLETE_157_MODELS,
            "mongo_collision_check": mongo_check,
            "passed": (
                len(structures) == 10
                and len(relations) == 7
                and len(source_evidence_only) == EXPECTED_INCOMPLETE_157_MODELS
                and not local_duplicate_ids["structure_ids"]
                and not local_duplicate_ids["relation_ids"]
                and not orphan_relations
                and not provenance_errors
                and all(row["status"] == "passed" for row in cif_validations)
                and entry_157_literal_values == [51323.0]
                and not mongo_check["structure_collisions"]
                and not mongo_check["relation_collisions"]
            ),
        },
        "production_count_changes": {
            "baseline_final_counts": baseline_counts,
            "delta": count_delta,
            "proposed_final_counts": proposed_counts,
        },
        "prohibited_operations": {
            "mongodb_write": False,
            "source_archive_modified": False,
            "canonical_record_modified": False,
            "cod_matching_run": False,
            "git_commit_or_push": False,
        },
    }


CSV_FIELDS = [
    "record_type",
    "entry_id",
    "pattern_id",
    "source_label_raw",
    "source_model_id",
    "model_name",
    "structure_id",
    "relation_id",
    "linkage_status",
    "cif_path",
    "cif_sha256",
    "source_archive_sha256",
    "source_member",
    "source_member_sha256",
    "source_evidence_only",
    "review_reason",
]


def write_outputs(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "powbase_source_structure_integration_dryrun_v1.json"
    csv_path = output_dir / "powbase_source_structure_integration_dryrun_v1.csv"
    summary_path = output_dir / "powbase_source_structure_integration_dryrun_v1_summary.md"

    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    rows: list[dict[str, Any]] = []
    for structure in result["structures_to_add"]:
        provenance = structure["provenance"]
        rows.append(
            {
                "record_type": "structure",
                "entry_id": provenance["source_id"],
                "pattern_id": f"POWBASE_PAT_{provenance['source_id']}",
                "source_label_raw": provenance["source_index_label_raw"],
                "source_model_id": provenance["source_model_id"],
                "model_name": provenance["source_model_name"],
                "structure_id": structure["structure_id"],
                "relation_id": "",
                "linkage_status": "proposed_structure_only",
                "cif_path": structure["file"]["key"],
                "cif_sha256": structure["file"]["sha256"],
                "source_archive_sha256": provenance["source_archive_sha256"],
                "source_member": provenance["source_member"],
                "source_member_sha256": provenance["source_member_sha256"],
                "source_evidence_only": False,
                "review_reason": "",
            }
        )
    for relation in result["relations_to_add"]:
        rows.append(
            {
                "record_type": "relation",
                "entry_id": relation["provenance"]["source_id"],
                "pattern_id": relation["subject_id"],
                "source_label_raw": "",
                "source_model_id": "",
                "model_name": "",
                "structure_id": relation["object_id"],
                "relation_id": relation["relation_id"],
                "linkage_status": "source_link_supported",
                "cif_path": "",
                "cif_sha256": "",
                "source_archive_sha256": "",
                "source_member": "",
                "source_member_sha256": "",
                "source_evidence_only": False,
                "review_reason": "",
            }
        )
    for evidence in result["source_evidence_only_models"]:
        rows.append(
            {
                "record_type": "source_evidence_only",
                "entry_id": evidence["entry_id"],
                "pattern_id": evidence["pattern_id"],
                "source_label_raw": "",
                "source_model_id": evidence["source_model_id"],
                "model_name": evidence["model_name"],
                "structure_id": "",
                "relation_id": "",
                "linkage_status": "ambiguous_review",
                "cif_path": "",
                "cif_sha256": "",
                "source_archive_sha256": "",
                "source_member": evidence["source_member"],
                "source_member_sha256": "",
                "source_evidence_only": True,
                "review_reason": evidence["reason"],
            }
        )
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts = result["production_count_changes"]
    validation = result["validation"]
    wavelength = result["entry_116_wavelength_fix"]
    summary = f"""# PowBase Source-Structure Integration Dry-Run v1

Read-only proposal generated from the existing recovery output. No MongoDB
write, source-archive modification, canonical-record modification, COD match,
commit, or push was performed.

## Proposal

- Structures to add: **{len(result["structures_to_add"])}**
- Relations to add: **{len(result["relations_to_add"])}**
- Entry 106: ambiguous review; two CIFs proposed, no unique relation.
- Entry 157: ambiguous review; one CIF proposed, four incomplete models kept as source evidence only.
- Entry 157 literal source value `51323`: preserved unchanged.
- Entry 116 explicit wavelengths: **1.54056 Å** and **1.54439 Å**.

## Validation

- Gemmi-validated CIFs: **{sum(1 for row in result["cif_validation"]["records"] if row["status"] == "passed")}/{len(result["cif_validation"]["records"])}**
- Local duplicate structure IDs: **{len(validation["local_duplicate_ids"]["structure_ids"])}**
- Local duplicate relation IDs: **{len(validation["local_duplicate_ids"]["relation_ids"])}**
- Proposed orphan relations: **{len(validation["orphan_relations"])}**
- Provenance errors: **{len(validation["provenance_errors"])}**
- Read-only Mongo structure collisions: **{len(validation["mongo_collision_check"]["structure_collisions"])}**
- Read-only Mongo relation collisions: **{len(validation["mongo_collision_check"]["relation_collisions"])}**
- Dry-run passed: **{validation["passed"]}**

## Proposed Production Counts

| Collection | Current | Delta | Proposed |
|---|---:|---:|---:|
{chr(10).join(f"| {name} | {counts['baseline_final_counts'][name]} | {counts['delta'][name]:+d} | {counts['proposed_final_counts'][name]} |" for name in COLLECTIONS)}

Entry 116's current canonical pattern/measurement wavelength fields were
blank. The proposal retains the source-labeled Kα1/Kα2 pair without changing
the existing canonical record.
"""
    summary_path.write_text(summary, encoding="utf-8", newline="\n")
    return json_path, csv_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-mongo", action="store_true")
    parser.add_argument("--mongo-uri", default=None)
    parser.add_argument("--mongo-database", default="crystaldb")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    result = build_dryrun(
        check_mongo=args.check_mongo,
        mongo_uri=args.mongo_uri,
        mongo_database=args.mongo_database,
    )
    paths = write_outputs(result, args.output_dir)
    print(json.dumps({"validation": result["validation"], "outputs": [str(p) for p in paths]}, indent=2))


if __name__ == "__main__":
    main()
