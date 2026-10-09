"""Apply the validated PowBase source-structure proposal to production MongoDB.

This is an intentionally narrow production operation.  It consumes the
completed read-only structure-integration dry-run, inserts only the proposed
structure and relation documents, and updates only the two entry-116
wavelength fields in its existing measurement and pattern documents.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gemmi
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.integrate_powbase_production_v1 import (  # noqa: E402
    BACKUP_COLLECTIONS,
    backup_inventory,
    collection_counts,
)

DEFAULT_DRYRUN_JSON = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "powbase_source_structure_integration_dryrun_v1.json"
)
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "backups"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "mappings"
DEFAULT_DATABASE = "crystaldb"
DEFAULT_URI = "mongodb://localhost:27017"

TARGET_ENTRY_IDS = ["106", "113", "116", "117", "124", "125", "157", "159", "160"]
AMBIGUOUS_ENTRY_IDS = {"106", "157"}
ENTRY_116_PRIMARY = 1.54056
ENTRY_116_SECONDARY = 1.54439
EXPECTED_STRUCTURE_COUNT = 10
EXPECTED_RELATION_COUNT = 7


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _without_id(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {key: item for key, item in value.items() if key != "_id"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_cif(path: Path) -> dict[str, Any]:
    cif = gemmi.cif.read_file(str(path))
    if len(cif) != 1:
        raise ValueError(f"expected one CIF block in {path}, found {len(cif)}")
    block = cif.sole_block()
    atom_labels = block.find_loop("_atom_site_label")
    return {
        "block_name": block.name,
        "atom_site_count": len(atom_labels) if atom_labels is not None else 0,
        "sha256": _sha256_file(path),
    }


def _load_proposal(path: Path) -> dict[str, Any]:
    proposal = _read_json(path)
    if proposal.get("read_only") is not True:
        raise ValueError("structure proposal is not marked read-only")
    if len(proposal.get("structures_to_add") or []) != EXPECTED_STRUCTURE_COUNT:
        raise ValueError("dry-run does not contain exactly 10 proposed structures")
    if len(proposal.get("relations_to_add") or []) != EXPECTED_RELATION_COUNT:
        raise ValueError("dry-run does not contain exactly 7 proposed relations")
    if proposal.get("validation", {}).get("passed") is not True:
        raise ValueError("dry-run validation did not pass")
    if len(proposal.get("source_evidence_only_models") or []) != 4:
        raise ValueError("dry-run does not preserve exactly four incomplete entry-157 models")
    wavelength = proposal.get("entry_116_wavelength_fix", {})
    if wavelength.get("proposed_wavelength_values_angstrom") != [
        ENTRY_116_PRIMARY,
        ENTRY_116_SECONDARY,
    ]:
        raise ValueError("entry-116 wavelength proposal is not authoritative")
    return proposal


def _validate_proposal_cifs(proposal: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for structure in proposal["structures_to_add"]:
        path = PROJECT_ROOT / structure["file"]["key"]
        if not path.is_file():
            raise FileNotFoundError(path)
        parsed = _parse_cif(path)
        if parsed["sha256"] != structure["file"]["sha256"]:
            raise ValueError(f"CIF SHA256 differs from dry-run: {path}")
        if structure["formula"] is not None:
            raise ValueError(f"formula is populated for {structure['structure_id']}")
        if structure["provenance"]["source"] != "POWBASE":
            raise ValueError(f"source provenance is not POWBASE: {structure['structure_id']}")
        results.append(
            {
                "structure_id": structure["structure_id"],
                "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                **parsed,
            }
        )
    return {
        "count": len(results),
        "all_gemmi_parse": len(results) == EXPECTED_STRUCTURE_COUNT,
        "records": results,
    }


def _duplicate_ids(database: Any, collection: str, field: str) -> list[str]:
    rows = database[collection].aggregate(
        [
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"_id": 1}},
        ]
    )
    return [str(row["_id"]) for row in rows]


def _orphan_relations(database: Any) -> list[str]:
    pattern_ids = set(database.patterns.distinct("pattern_id"))
    structure_ids = set(database.structures.distinct("structure_id"))
    orphans: list[str] = []
    for relation in database.relations.find(
        {},
        {
            "_id": 0,
            "relation_id": 1,
            "subject_type": 1,
            "subject_id": 1,
            "object_type": 1,
            "object_id": 1,
        },
    ):
        if (
            relation.get("subject_type") == "pattern"
            and relation.get("subject_id") not in pattern_ids
        ):
            orphans.append(f"{relation.get('relation_id')}:subject")
        if (
            relation.get("object_type") == "structure"
            and relation.get("object_id") not in structure_ids
        ):
            orphans.append(f"{relation.get('relation_id')}:object")
    return sorted(orphans)


def _structure_preflight(
    database: Any,
    structures: list[dict[str, Any]],
) -> dict[str, Any]:
    new_ids: list[str] = []
    exact_ids: list[str] = []
    conflicts: list[str] = []
    for document in structures:
        identifier = document["structure_id"]
        existing = _without_id(
            database.structures.find_one({"structure_id": identifier})
        )
        if existing is None:
            new_ids.append(identifier)
        elif existing == document:
            exact_ids.append(identifier)
        else:
            conflicts.append(identifier)
    return {
        "new_ids": sorted(new_ids),
        "exact_ids": sorted(exact_ids),
        "conflicts": sorted(conflicts),
    }


def _relation_preflight(
    database: Any,
    relations: list[dict[str, Any]],
) -> dict[str, Any]:
    new_ids: list[str] = []
    exact_ids: list[str] = []
    conflicts: list[str] = []
    for document in relations:
        identifier = document["relation_id"]
        existing = _without_id(
            database.relations.find_one({"relation_id": identifier})
        )
        if existing is None:
            new_ids.append(identifier)
        elif existing == document:
            exact_ids.append(identifier)
        else:
            conflicts.append(identifier)
    return {
        "new_ids": sorted(new_ids),
        "exact_ids": sorted(exact_ids),
        "conflicts": sorted(conflicts),
    }


def _metadata_preflight(database: Any) -> dict[str, Any]:
    pattern = database.patterns.find_one(
        {"pattern_id": "POWBASE_PAT_116"},
        {"_id": 0},
    )
    measurement = database.measurements.find_one(
        {"measurement_id": "POWBASE_MEAS_116"},
        {"_id": 0},
    )
    if pattern is None or measurement is None:
        raise ValueError("entry 116 production pattern or measurement is missing")
    current = {
        "pattern": {
            "wavelength_angstrom": (pattern.get("radiation") or {}).get(
                "wavelength_angstrom"
            ),
            "wavelength_kalpha2_angstrom": (pattern.get("radiation") or {}).get(
                "wavelength_kalpha2_angstrom"
            ),
        },
        "measurement": {
            "wavelength_angstrom": (measurement.get("conditions") or {}).get(
                "wavelength_angstrom"
            ),
            "wavelength_kalpha2_angstrom": (measurement.get("conditions") or {}).get(
                "wavelength_kalpha2_angstrom"
            ),
        },
    }
    expected = {
        "pattern": {
            "wavelength_angstrom": ENTRY_116_PRIMARY,
            "wavelength_kalpha2_angstrom": ENTRY_116_SECONDARY,
        },
        "measurement": {
            "wavelength_angstrom": ENTRY_116_PRIMARY,
            "wavelength_kalpha2_angstrom": ENTRY_116_SECONDARY,
        },
    }
    conflicts = []
    for document_name in ("pattern", "measurement"):
        for field in ("wavelength_angstrom", "wavelength_kalpha2_angstrom"):
            value = current[document_name][field]
            if value is not None and value != expected[document_name][field]:
                conflicts.append(f"{document_name}.{field}")
    return {
        "current": current,
        "expected": expected,
        "conflicts": conflicts,
        "needs_pattern_update": current["pattern"] != expected["pattern"],
        "needs_measurement_update": current["measurement"] != expected["measurement"],
    }


def _ambiguous_linkage_check(database: Any) -> dict[str, Any]:
    relation_counts: dict[str, int] = {}
    for entry_id in sorted(AMBIGUOUS_ENTRY_IDS):
        pattern_id = f"POWBASE_PAT_{entry_id}"
        relation_counts[entry_id] = database.relations.count_documents(
            {
                "subject_type": "pattern",
                "subject_id": pattern_id,
                "predicate": "has_structure_linkage",
            }
        )
    return {
        "relation_counts": relation_counts,
        "clear": all(count == 0 for count in relation_counts.values()),
    }


def _entry_157_literal_check(database: Any) -> dict[str, Any]:
    document = database.structures.find_one(
        {"structure_id": "STR_POWBASE_157_STR_C_1"},
        {"_id": 0},
    )
    literal_matches: list[dict[str, Any]] = []
    if document:
        for site in document.get("atomic_sites") or []:
            if site.get("y") == 51323.0 or "51323" in str(site.get("raw_line", "")):
                literal_matches.append(site)
    return {
        "structure_present": document is not None,
        "literal_51323_preserved": len(literal_matches) == 1
        and literal_matches[0].get("y") == 51323.0
        and "51323" in str(literal_matches[0].get("raw_line", "")),
        "matching_sites": literal_matches,
    }


def _incomplete_entry_157_check(
    database: Any,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    incomplete_ids = []
    for model in proposal["source_evidence_only_models"]:
        token = "".join(
            character if character.isalnum() else "_"
            for character in model["source_model_id"]
        ).strip("_")
        incomplete_ids.append(f"STR_POWBASE_157_{token}")
    present = [
        identifier
        for identifier in incomplete_ids
        if database.structures.find_one({"structure_id": identifier}, {"_id": 1})
    ]
    return {
        "expected_incomplete_structure_ids": incomplete_ids,
        "present_in_production": present,
        "clear": not present,
    }


def _post_write_structure_checks(
    database: Any,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    proposed_ids = {
        structure["structure_id"] for structure in proposal["structures_to_add"]
    }
    source_157_ids = {
        structure["structure_id"]
        for structure in proposal["structures_to_add"]
        if structure["provenance"]["source_id"] == "157"
    }
    actual_157_ids = {
        document["structure_id"]
        for document in database.structures.find(
            {"provenance.source_id": "157"},
            {"_id": 0, "structure_id": 1},
        )
    }
    all_expected_present = (
        sum(
            database.structures.count_documents({"structure_id": identifier})
            for identifier in proposed_ids
        )
        == EXPECTED_STRUCTURE_COUNT
    )
    return {
        "all_proposed_structures_present": all_expected_present,
        "entry_157_structure_ids": sorted(actual_157_ids),
        "entry_157_only_recoverable_cif": actual_157_ids == source_157_ids,
        "ambiguous_linkage": _ambiguous_linkage_check(database),
        "entry_157_literal": _entry_157_literal_check(database),
        "incomplete_entry_157": _incomplete_entry_157_check(database, proposal),
        "gemmi_parse_count": len(
            [
                _parse_cif(PROJECT_ROOT / structure["file"]["key"])
                for structure in proposal["structures_to_add"]
            ]
        ),
    }


def _write_outputs(
    report: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "powbase_source_structure_production_integration_v1.json"
    csv_path = output_dir / "powbase_source_structure_production_integration_v1.csv"
    summary_path = (
        output_dir / "powbase_source_structure_production_integration_v1_summary.md"
    )
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    fields = [
        "record_type",
        "entry_id",
        "identifier",
        "action",
        "status",
        "details",
    ]
    rows: list[dict[str, Any]] = []
    for item in report["write_sets"]["structures"]:
        rows.append(
            {
                "record_type": "structure",
                "entry_id": item["entry_id"],
                "identifier": item["structure_id"],
                "action": "insert",
                "status": item["status"],
                "details": item["source_model_id"],
            }
        )
    for item in report["write_sets"]["relations"]:
        rows.append(
            {
                "record_type": "relation",
                "entry_id": item["entry_id"],
                "identifier": item["relation_id"],
                "action": "insert",
                "status": item["status"],
                "details": item["object_id"],
            }
        )
    rows.extend(
        [
            {
                "record_type": "metadata",
                "entry_id": "116",
                "identifier": "POWBASE_PAT_116",
                "action": "update",
                "status": report["write_sets"]["entry_116_pattern_update"]["status"],
                "details": _json(report["write_sets"]["entry_116_pattern_update"]),
            },
            {
                "record_type": "metadata",
                "entry_id": "116",
                "identifier": "POWBASE_MEAS_116",
                "action": "update",
                "status": report["write_sets"]["entry_116_measurement_update"]["status"],
                "details": _json(
                    report["write_sets"]["entry_116_measurement_update"]
                ),
            },
        ]
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    before = report["counts"]["before"]
    after = report["counts"]["after"]
    lines = [
        "# PowBase Source-Structure Production Integration v1",
        "",
        "Production integration was applied from the completed authoritative "
        "dry-run. No new PowBase patterns, COD matches, release changes, or "
        "source-archive changes were made.",
        "",
        "## Write Set",
        "",
        "- Structures inserted: "
        f"**{report['write_counts']['structures_inserted']}**",
        "- Relations inserted: "
        f"**{report['write_counts']['relations_inserted']}**",
        "- Entry-116 pattern wavelength update: "
        f"**{report['write_counts']['entry_116_pattern_modified']}**",
        "- Entry-116 measurement wavelength update: "
        f"**{report['write_counts']['entry_116_measurement_modified']}**",
        "- Entry 106: ambiguous/review; no relation added.",
        "- Entry 157: ambiguous/review; four incomplete models were not registered.",
        "- Entry 157 literal source value `51323`: preserved.",
        "",
        "## Counts",
        "",
        "| Collection | Before | After | Delta |",
        "|---|---:|---:|---:|",
    ]
    for collection in BACKUP_COLLECTIONS:
        lines.append(
            f"| {collection} | {before[collection]} | {after[collection]} | "
            f"{after[collection] - before[collection]:+d} |"
        )
    lines.extend(
        [
            "",
            "## Validation",
            "",
            f"- Backup complete: **{report['backup']['complete']}**",
            f"- Structures increased by exactly 10: **{report['validation']['structure_delta_exact']}**",
            f"- Relations increased by exactly 7: **{report['validation']['relation_delta_exact']}**",
            f"- Pattern count unchanged: **{report['validation']['pattern_count_unchanged']}**",
            f"- Duplicate IDs: **{report['validation']['duplicate_ids_total']}**",
            f"- Orphan relations: **{len(report['validation']['orphan_relations'])}**",
            f"- Gemmi CIF parses: **{report['validation']['gemmi_parse_count']}/10**",
            f"- Ambiguous relation guard: **{report['validation']['ambiguous_linkage']['clear']}**",
            f"- Entry-157 literal preserved: **{report['validation']['entry_157_literal']['literal_51323_preserved']}**",
            f"- Four incomplete entry-157 models absent: **{report['validation']['incomplete_entry_157']['clear']}**",
            f"- Idempotence preflight: **{report['validation']['idempotent_exact_matches']}**",
            f"- Integration passed: **{report['integration_passed']}**",
            "",
            f"Backup: `{report['backup']['path']}`",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return json_path, csv_path, summary_path


def integrate(
    *,
    backup_root: Path,
    dryrun_json: Path = DEFAULT_DRYRUN_JSON,
    database_name: str = DEFAULT_DATABASE,
    uri: str = DEFAULT_URI,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    allow_production_write: bool = False,
) -> dict[str, Any]:
    if not allow_production_write:
        raise ValueError("production write requires --allow-production-write")
    if database_name != "crystaldb":
        raise ValueError("production database must be exactly 'crystaldb'")

    proposal = _load_proposal(dryrun_json)
    cif_validation = _validate_proposal_cifs(proposal)
    backup = backup_inventory(backup_root, {})
    if not backup["complete"]:
        raise RuntimeError("production backup is incomplete: " + "; ".join(backup["errors"]))

    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        database = client[database_name]
        before = collection_counts(database)
        if before != backup["collection_counts"]:
            raise RuntimeError(
                "live production counts differ from the fresh backup: "
                f"live={before}, backup={backup['collection_counts']}"
            )

        structures = proposal["structures_to_add"]
        relations = proposal["relations_to_add"]
        structure_preflight = _structure_preflight(database, structures)
        relation_preflight = _relation_preflight(database, relations)
        if structure_preflight["conflicts"]:
            raise RuntimeError(
                "structure collision conflicts: "
                + ", ".join(structure_preflight["conflicts"])
            )
        if relation_preflight["conflicts"]:
            raise RuntimeError(
                "relation collision conflicts: "
                + ", ".join(relation_preflight["conflicts"])
            )

        metadata_preflight = _metadata_preflight(database)
        if metadata_preflight["conflicts"]:
            raise RuntimeError(
                "entry-116 wavelength conflicts: "
                + ", ".join(metadata_preflight["conflicts"])
            )
        ambiguous_preflight = _ambiguous_linkage_check(database)
        if not ambiguous_preflight["clear"]:
            raise RuntimeError("ambiguous entries already have structure relations")

        if any(
            database.patterns.count_documents({"pattern_id": f"POWBASE_PAT_{entry_id}"})
            != 1
            for entry_id in TARGET_ENTRY_IDS
        ):
            raise RuntimeError("one or more target PowBase patterns are missing")

        structure_inserted: list[str] = []
        for document in structures:
            if document["structure_id"] in structure_preflight["new_ids"]:
                database.structures.insert_one(deepcopy(document))
                structure_inserted.append(document["structure_id"])

        relation_inserted: list[str] = []
        for document in relations:
            if document["relation_id"] in relation_preflight["new_ids"]:
                database.relations.insert_one(deepcopy(document))
                relation_inserted.append(document["relation_id"])

        pattern_update = {
            "$set": {
                "radiation.wavelength_angstrom": ENTRY_116_PRIMARY,
                "radiation.wavelength_kalpha2_angstrom": ENTRY_116_SECONDARY,
            }
        }
        measurement_update = {
            "$set": {
                "conditions.wavelength_angstrom": ENTRY_116_PRIMARY,
                "conditions.wavelength_kalpha2_angstrom": ENTRY_116_SECONDARY,
            }
        }
        pattern_result = database.patterns.update_one(
            {"pattern_id": "POWBASE_PAT_116"},
            pattern_update,
        )
        measurement_result = database.measurements.update_one(
            {"measurement_id": "POWBASE_MEAS_116"},
            measurement_update,
        )

        after = collection_counts(database)
        post_checks = _post_write_structure_checks(database, proposal)
        duplicate_ids = {
            "structures": _duplicate_ids(database, "structures", "structure_id"),
            "relations": _duplicate_ids(database, "relations", "relation_id"),
            "patterns": _duplicate_ids(database, "patterns", "pattern_id"),
            "measurements": _duplicate_ids(
                database, "measurements", "measurement_id"
            ),
            "samples": _duplicate_ids(database, "samples", "sample_id"),
        }
        duplicate_total = sum(len(values) for values in duplicate_ids.values())
        orphans = _orphan_relations(database)

        second_structure_preflight = _structure_preflight(database, structures)
        second_relation_preflight = _relation_preflight(database, relations)
        second_metadata_preflight = _metadata_preflight(database)
        idempotent_exact_matches = bool(
            not second_structure_preflight["new_ids"]
            and not second_relation_preflight["new_ids"]
            and not second_structure_preflight["conflicts"]
            and not second_relation_preflight["conflicts"]
            and not second_metadata_preflight["conflicts"]
            and not second_metadata_preflight["needs_pattern_update"]
            and not second_metadata_preflight["needs_measurement_update"]
        )

        validation = {
            "structure_delta_exact": after["structures"] - before["structures"] == 10,
            "relation_delta_exact": after["relations"] - before["relations"] == 7,
            "pattern_count_unchanged": after["patterns"] == before["patterns"],
            "duplicate_ids": duplicate_ids,
            "duplicate_ids_total": duplicate_total,
            "orphan_relations": orphans,
            "gemmi_parse_count": cif_validation["count"],
            "gemmi_parse_all": cif_validation["all_gemmi_parse"],
            "ambiguous_linkage": post_checks["ambiguous_linkage"],
            "entry_157_literal": post_checks["entry_157_literal"],
            "incomplete_entry_157": post_checks["incomplete_entry_157"],
            "entry_157_only_recoverable_cif": post_checks[
                "entry_157_only_recoverable_cif"
            ],
            "idempotent_exact_matches": idempotent_exact_matches,
            "second_structure_preflight": second_structure_preflight,
            "second_relation_preflight": second_relation_preflight,
            "second_metadata_preflight": second_metadata_preflight,
        }
        integration_passed = bool(
            validation["structure_delta_exact"]
            and validation["relation_delta_exact"]
            and validation["pattern_count_unchanged"]
            and duplicate_total == 0
            and not orphans
            and validation["gemmi_parse_all"]
            and validation["ambiguous_linkage"]["clear"]
            and validation["entry_157_literal"]["literal_51323_preserved"]
            and validation["incomplete_entry_157"]["clear"]
            and validation["entry_157_only_recoverable_cif"]
            and idempotent_exact_matches
        )

        report = {
            "schema_version": "powbase_source_structure_production_integration_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": database_name,
            "production_database_written": True,
            "dryrun_input": str(dryrun_json.resolve()),
            "backup": backup,
            "scope": {
                "entry_ids": TARGET_ENTRY_IDS,
                "ambiguous_entry_ids": sorted(AMBIGUOUS_ENTRY_IDS),
                "incomplete_entry_157_models_registered": 0,
            },
            "counts": {"before": before, "after": after},
            "write_counts": {
                "structures_inserted": len(structure_inserted),
                "relations_inserted": len(relation_inserted),
                "entry_116_pattern_modified": pattern_result.modified_count,
                "entry_116_measurement_modified": measurement_result.modified_count,
            },
            "write_sets": {
                "structures": [
                    {
                        "entry_id": structure["provenance"]["source_id"],
                        "structure_id": structure["structure_id"],
                        "source_model_id": structure["provenance"]["source_model_id"],
                        "status": (
                            "inserted"
                            if structure["structure_id"] in structure_inserted
                            else "already_present_exact"
                        ),
                    }
                    for structure in structures
                ],
                "relations": [
                    {
                        "entry_id": relation["provenance"]["source_id"],
                        "relation_id": relation["relation_id"],
                        "subject_id": relation["subject_id"],
                        "object_id": relation["object_id"],
                        "status": (
                            "inserted"
                            if relation["relation_id"] in relation_inserted
                            else "already_present_exact"
                        ),
                    }
                    for relation in relations
                ],
                "entry_116_pattern_update": {
                    "status": "modified" if pattern_result.modified_count else "already_exact",
                    "values": {
                        "wavelength_angstrom": ENTRY_116_PRIMARY,
                        "wavelength_kalpha2_angstrom": ENTRY_116_SECONDARY,
                    },
                },
                "entry_116_measurement_update": {
                    "status": (
                        "modified"
                        if measurement_result.modified_count
                        else "already_exact"
                    ),
                    "values": {
                        "wavelength_angstrom": ENTRY_116_PRIMARY,
                        "wavelength_kalpha2_angstrom": ENTRY_116_SECONDARY,
                    },
                },
            },
            "cif_validation": cif_validation,
            "validation": validation,
            "integration_passed": integration_passed,
            "prohibited_operations": {
                "new_powbase_patterns": False,
                "entries_15_74_121_156_processed": False,
                "cod_matching": False,
                "source_archives_modified": False,
                "website_manuscript_release_updated": False,
                "git_commit_or_push": False,
            },
        }
    finally:
        client.close()

    outputs = _write_outputs(report, output_dir)
    report["outputs"] = {
        "json": str(outputs[0].resolve()),
        "csv": str(outputs[1].resolve()),
        "summary": str(outputs[2].resolve()),
    }
    # Refresh the JSON with the final output paths included.
    outputs[0].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not report["integration_passed"]:
        raise RuntimeError("production integration validation failed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--dryrun-json", type=Path, default=DEFAULT_DRYRUN_JSON)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument(
        "--uri",
        default=os.environ.get("CRYSTALDB_MONGO_URI", DEFAULT_URI),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--allow-production-write", action="store_true")
    args = parser.parse_args()
    report = integrate(
        backup_root=args.backup_root,
        dryrun_json=args.dryrun_json,
        database_name=args.database,
        uri=args.uri,
        output_dir=args.output_dir,
        allow_production_write=args.allow_production_write,
    )
    print(
        json.dumps(
            {
                "backup": report["backup"]["path"],
                "counts": report["counts"],
                "write_counts": report["write_counts"],
                "validation": {
                    "structure_delta_exact": report["validation"][
                        "structure_delta_exact"
                    ],
                    "relation_delta_exact": report["validation"][
                        "relation_delta_exact"
                    ],
                    "pattern_count_unchanged": report["validation"][
                        "pattern_count_unchanged"
                    ],
                    "duplicate_ids_total": report["validation"][
                        "duplicate_ids_total"
                    ],
                    "orphan_relations": len(
                        report["validation"]["orphan_relations"]
                    ),
                    "idempotent_exact_matches": report["validation"][
                        "idempotent_exact_matches"
                    ],
                },
                "integration_passed": report["integration_passed"],
                "outputs": report["outputs"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
