"""Import COD CIF/HKL experimental single-crystal pairs into CrystalDB.

The importer is resumable and intentionally keeps the large scientific files
on disk. MongoDB receives catalog metadata and file keys only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pymongo import UpdateOne


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crystaldb.data_paths import get_data_root, resolve_data_path  # noqa: E402
from crystaldb.mongo import get_database  # noqa: E402
from crystaldb.sources.cod.hkl_parser import parse_cod_hkl  # noqa: E402
from crystaldb.sources.cod.single_crystal_parser import parse_cod_cif  # noqa: E402


DEFAULT_SOURCE_CIF_DIR = Path(
    r"D:\document\aiformaterials\ai4\single_crystal_xray\cod\processed\pairs\cif"
)
DEFAULT_SOURCE_HKL_DIR = Path(
    r"D:\document\aiformaterials\ai4\single_crystal_xray\cod\processed\pairs\hkl"
)
DEFAULT_MAPPING = (
    PROJECT_ROOT / "data" / "mappings" / "cod_single_crystal_id_map_v1.json"
)
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_single_crystal_import_manifest_v1.json"
)
DEFAULT_RECORDS = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_single_crystal_import_records_v1.jsonl"
)

SOURCE_NAME = "COD"
SOURCE_FULL_NAME = "Crystallography Open Database"
PARSER_VERSIONS = {
    "cif": "cod_single_crystal_parser_v1",
    "hkl": "cod_hkl_parser_v2",
    "importer": "cod_single_crystal_importer_v2",
}
COD_ID_PATTERN = re.compile(r"^\d+$")
CANONICAL_ID_PATTERN = re.compile(r"^(STR|MEAS|REFL)_(\d+)$")
WINDOWS_ABSOLUTE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_jsonl_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            cod_id = record.get("cod_id")
            if isinstance(cod_id, str) and COD_ID_PATTERN.fullmatch(cod_id):
                records[cod_id] = record
    return records


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def file_metadata(path: Path) -> dict[str, Any]:
    return {
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def copy_and_verify(source: Path, destination: Path) -> tuple[str, dict[str, Any] | None]:
    """Copy one file without overwriting a conflicting destination."""
    if destination.exists():
        source_hash = sha256_file(source)
        destination_hash = sha256_file(destination)
        if source_hash != destination_hash:
            return "conflict", None
        return "skip", {
            "sha256": destination_hash,
            "size_bytes": destination.stat().st_size,
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_hash = sha256_file(source)
    destination_hash = sha256_file(destination)
    if source_hash != destination_hash:
        return "hash_mismatch", None
    return "copied", {
        "sha256": destination_hash,
        "size_bytes": destination.stat().st_size,
    }


def scan_source_pairs(
    cif_dir: Path,
    hkl_dir: Path,
) -> tuple[dict[str, Path], dict[str, Path], list[str]]:
    cif_files = {
        path.stem: path
        for path in cif_dir.glob("*.cif")
        if path.is_file() and COD_ID_PATTERN.fullmatch(path.stem)
    }
    hkl_files = {
        path.stem: path
        for path in hkl_dir.glob("*.hkl")
        if path.is_file() and COD_ID_PATTERN.fullmatch(path.stem)
    }
    pair_ids = sorted(cif_files.keys() & hkl_files.keys(), key=int)
    return cif_files, hkl_files, pair_ids


def load_mapping(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"mapping must be a JSON object: {path}")
    mapping: dict[str, dict[str, str]] = {}
    for cod_id, entry in value.items():
        if not COD_ID_PATTERN.fullmatch(str(cod_id)) or not isinstance(entry, dict):
            continue
        if all(isinstance(entry.get(key), str) for key in ("structure_id", "measurement_id", "reflection_set_id")):
            mapping[str(cod_id)] = {
                "structure_id": entry["structure_id"],
                "measurement_id": entry["measurement_id"],
                "reflection_set_id": entry["reflection_set_id"],
            }
    return mapping


def canonical_number(value: Any, prefix: str) -> int:
    if not isinstance(value, str):
        return 0
    match = CANONICAL_ID_PATTERN.fullmatch(value)
    if not match or match.group(1) != prefix:
        return 0
    return int(match.group(2))


class CanonicalIdAllocator:
    def __init__(
        self,
        mapping: dict[str, dict[str, str]],
        database: Any | None,
    ) -> None:
        self.next_numbers = {
            "STR": self._initial_next(mapping, "structure_id", "STR"),
            "MEAS": self._initial_next(mapping, "measurement_id", "MEAS"),
            "REFL": self._initial_next(mapping, "reflection_set_id", "REFL"),
        }
        if database is not None:
            self._include_database(database)

    @staticmethod
    def _initial_next(
        mapping: dict[str, dict[str, str]],
        field: str,
        prefix: str,
    ) -> int:
        highest = max(
            (canonical_number(entry.get(field), prefix) for entry in mapping.values()),
            default=0,
        )
        return highest + 1

    def _include_database(self, database: Any) -> None:
        for collection_name, field, prefix in (
            ("structures", "structure_id", "STR"),
            ("measurements", "measurement_id", "MEAS"),
            ("reflection_sets", "reflection_set_id", "REFL"),
        ):
            highest = 0
            for document in database[collection_name].find({}, {field: 1}):
                highest = max(highest, canonical_number(document.get(field), prefix))
            self.next_numbers[prefix] = max(self.next_numbers[prefix], highest + 1)

    def allocate(self) -> dict[str, str]:
        result = {
            "structure_id": f"STR_{self.next_numbers['STR']:06d}",
            "measurement_id": f"MEAS_{self.next_numbers['MEAS']:06d}",
            "reflection_set_id": f"REFL_{self.next_numbers['REFL']:06d}",
        }
        self.next_numbers["STR"] += 1
        self.next_numbers["MEAS"] += 1
        self.next_numbers["REFL"] += 1
        return result


def existing_mapping_from_database(database: Any | None, cod_id: str) -> dict[str, str] | None:
    if database is None:
        return None
    structure = database.structures.find_one(
        {"source": SOURCE_NAME, "source_structure_id": cod_id},
        {"structure_id": 1},
    )
    measurement = database.measurements.find_one(
        {
            "source": SOURCE_NAME,
            "source_record_id": cod_id,
            "measurement_type": "single_crystal_xrd",
        },
        {"measurement_id": 1},
    )
    reflection_set = database.reflection_sets.find_one(
        {"source": SOURCE_NAME, "source_record_id": cod_id},
        {"reflection_set_id": 1},
    )
    if not all(
        document is not None
        for document in (structure, measurement, reflection_set)
    ):
        return None
    return {
        "structure_id": structure["structure_id"],
        "measurement_id": measurement["measurement_id"],
        "reflection_set_id": reflection_set["reflection_set_id"],
    }


def ensure_mapping(
    cod_id: str,
    mapping: dict[str, dict[str, str]],
    allocator: CanonicalIdAllocator,
    database: Any | None,
) -> dict[str, str]:
    entry = mapping.get(cod_id)
    if entry is not None:
        return entry
    entry = existing_mapping_from_database(database, cod_id)
    if entry is None:
        entry = allocator.allocate()
    mapping[cod_id] = entry
    return entry


def file_record(key: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "sha256": metadata["sha256"],
        "size_bytes": metadata["size_bytes"],
    }


def build_structure_document(
    cod_id: str,
    ids: dict[str, str],
    parsed: dict[str, Any],
    cif_file: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    return {
        "structure_id": ids["structure_id"],
        "source": SOURCE_NAME,
        "source_structure_id": cod_id,
        "data_origin": "experimental",
        "structure_format": "CIF",
        "formula": parsed["formula"],
        "formula_reduced": parsed["formula_reduced"],
        "elements": parsed["elements"],
        "space_group": parsed["space_group"],
        "cell": parsed["cell"],
        "atom_count": parsed["atom_count"],
        "atomic_sites": parsed["atomic_sites"],
        "file": cif_file,
        "parse_status": parsed["parse_status"],
        "parse_warnings": parsed["parse_warnings"],
        "provenance": {
            "source_database": SOURCE_FULL_NAME,
            "source_record_id": cod_id,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def build_reflection_document(
    cod_id: str,
    ids: dict[str, str],
    parsed: dict[str, Any],
    hkl_file: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    return {
        "reflection_set_id": ids["reflection_set_id"],
        "measurement_id": ids["measurement_id"],
        "source": SOURCE_NAME,
        "source_record_id": cod_id,
        "data_origin": "experimental",
        "modality": "single_crystal_xrd",
        "reflection_count": parsed["reflection_count"],
        "observed_quantity": "F_squared",
        "reflection_fields": parsed["reflection_fields"],
        "has_hkl": parsed["has_hkl"],
        "has_measured_f_squared": parsed["has_measured_f_squared"],
        "has_f_squared_sigma": parsed["has_f_squared_sigma"],
        "has_calculated_f_squared": parsed["has_calculated_f_squared"],
        "has_observed_status": parsed["has_observed_status"],
        "optional_fields": parsed["optional_fields"],
        "summary": {
            "h_min": parsed["h_min"],
            "h_max": parsed["h_max"],
            "k_min": parsed["k_min"],
            "k_max": parsed["k_max"],
            "l_min": parsed["l_min"],
            "l_max": parsed["l_max"],
            "measured_f_squared_min": parsed["measured_f_squared_min"],
            "measured_f_squared_max": parsed["measured_f_squared_max"],
        },
        "file": hkl_file,
        "parse_status": parsed["parse_status"],
        "parse_warnings": parsed["parse_warnings"],
        "provenance": {
            "source_database": SOURCE_FULL_NAME,
            "source_record_id": cod_id,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def build_measurement_document(
    cod_id: str,
    ids: dict[str, str],
    cif_parsed: dict[str, Any],
    hkl_parsed: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    statuses = {cif_parsed["parse_status"], hkl_parsed["parse_status"]}
    parse_status = "partial" if "partial" in statuses else "ok"
    return {
        "measurement_id": ids["measurement_id"],
        "source": SOURCE_NAME,
        "source_record_id": cod_id,
        "measurement_type": "single_crystal_xrd",
        "data_origin": "experimental",
        "sample_id": None,
        "structure_id": ids["structure_id"],
        "reflection_set_id": ids["reflection_set_id"],
        "experimental_conditions": cif_parsed["experimental_conditions"],
        "parse_status": parse_status,
        "parse_warnings": sorted(
            set(cif_parsed["parse_warnings"] + hkl_parsed["parse_warnings"])
        ),
        "provenance": {
            "source_database": SOURCE_FULL_NAME,
            "source_record_id": cod_id,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def update_operation(
    collection: str,
    identity: dict[str, Any],
    document: dict[str, Any],
    preserve_null_fields: Iterable[str] = (),
    insert_only_fields: Iterable[str] = (),
) -> UpdateOne:
    set_document = dict(document)
    for field in preserve_null_fields:
        set_document.pop(field, None)
    set_on_insert = {
        "created_at": document.get("created_at"),
    }
    for field in insert_only_fields:
        value = document.get(field)
        set_document.pop(field, None)
        if value is not None:
            set_on_insert[field] = value
    set_document.pop("_id", None)
    set_document.pop("created_at", None)
    update: dict[str, Any] = {
        "$set": set_document,
        "$setOnInsert": set_on_insert,
    }
    return UpdateOne(identity, update, upsert=True)


def build_operations(
    cod_id: str,
    ids: dict[str, str],
    cif_parsed: dict[str, Any],
    hkl_parsed: dict[str, Any],
    cif_file: dict[str, Any],
    hkl_file: dict[str, Any],
    timestamp: str,
) -> list[tuple[str, UpdateOne]]:
    structure = build_structure_document(
        cod_id, ids, cif_parsed, cif_file, timestamp
    )
    reflection_set = build_reflection_document(
        cod_id, ids, hkl_parsed, hkl_file, timestamp
    )
    measurement = build_measurement_document(
        cod_id, ids, cif_parsed, hkl_parsed, timestamp
    )
    return [
        (
            "structures",
            update_operation(
                "structures",
                {"source": SOURCE_NAME, "source_structure_id": cod_id},
                structure,
                preserve_null_fields=("sample_id",),
                insert_only_fields=("provenance",),
            ),
        ),
        (
            "measurements",
            update_operation(
                "measurements",
                {
                    "source": SOURCE_NAME,
                    "source_record_id": cod_id,
                    "measurement_type": "single_crystal_xrd",
                },
                measurement,
                preserve_null_fields=("sample_id",),
                insert_only_fields=("provenance",),
            ),
        ),
        (
            "reflection_sets",
            update_operation(
                "reflection_sets",
                {"source": SOURCE_NAME, "source_record_id": cod_id},
                reflection_set,
                insert_only_fields=("provenance",),
            ),
        ),
    ]


def ensure_indexes(database: Any) -> list[str]:
    created: list[str] = []
    index_specs = {
        "structures": [
            ([("structure_id", 1)], {"unique": True, "name": "structure_id_unique"}),
            (
                [("source", 1), ("source_structure_id", 1)],
                {
                    "unique": True,
                    "name": "source_source_structure_id_unique",
                    "partialFilterExpression": {
                        "source": {"$type": "string"},
                        "source_structure_id": {"$exists": True},
                    },
                },
            ),
            ([("elements", 1)], {"name": "elements"}),
            ([("space_group.number", 1)], {"name": "space_group_number"}),
        ],
        "measurements": [
            ([("measurement_id", 1)], {"unique": True, "name": "measurement_id_unique"}),
            (
                [("source", 1), ("source_record_id", 1), ("measurement_type", 1)],
                {
                    "unique": True,
                    "name": "source_record_measurement_type_unique",
                    "partialFilterExpression": {
                        "source": {"$type": "string"},
                        "source_record_id": {"$exists": True},
                        "measurement_type": {"$exists": True},
                    },
                },
            ),
            ([("structure_id", 1)], {"name": "structure_id"}),
            ([("reflection_set_id", 1)], {"name": "reflection_set_id"}),
        ],
        "reflection_sets": [
            ([("reflection_set_id", 1)], {"unique": True, "name": "reflection_set_id_unique"}),
            (
                [("source", 1), ("source_record_id", 1)],
                {
                    "unique": True,
                    "name": "source_source_record_id_unique",
                    "partialFilterExpression": {
                        "source": {"$type": "string"},
                        "source_record_id": {"$exists": True},
                    },
                },
            ),
        ],
        "sources": [
            ([("source_id", 1)], {"unique": True, "sparse": True, "name": "source_id_unique"}),
        ],
    }
    for collection_name, specs in index_specs.items():
        collection = database[collection_name]
        for keys, options in specs:
            try:
                collection.create_index(keys, **options)
                created.append(f"{collection_name}.{options['name']}")
            except Exception as exc:
                print(
                    f"WARNING: index {collection_name}.{options['name']} "
                    f"failed: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
    return created


def ensure_cod_source(database: Any) -> None:
    database.sources.update_one(
        {"source_id": "SRC_COD"},
        {
            "$setOnInsert": {
                "source_id": "SRC_COD",
                "name": SOURCE_FULL_NAME,
                "short_name": SOURCE_NAME,
                "source_type": "external_database",
                "data_origin": "experimental",
                "modalities": ["single_crystal_xrd", "crystal_structure"],
            }
        },
        upsert=True,
    )


def has_windows_absolute_path(value: Any) -> bool:
    if isinstance(value, str):
        return bool(WINDOWS_ABSOLUTE_PATTERN.match(value))
    if isinstance(value, dict):
        return any(has_windows_absolute_path(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(has_windows_absolute_path(item) for item in value)
    return False


def count_absolute_path_violations(database: Any) -> int:
    count = 0
    for collection_name in ("structures", "measurements", "reflection_sets", "sources"):
        for document in database[collection_name].find({}):
            if has_windows_absolute_path(document):
                count += 1
    return count


def count_duplicate_values(
    database: Any,
    collection_name: str,
    key_fields: list[str],
    filter_document: dict[str, Any],
) -> int:
    group_id = {field.replace(".", "_"): f"${field}" for field in key_fields}
    pipeline = [
        {"$match": filter_document},
        {
            "$group": {
                "_id": group_id,
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "duplicates"},
    ]
    result = list(database[collection_name].aggregate(pipeline))
    return int(result[0]["duplicates"]) if result else 0


def flush_operations(
    database: Any,
    pending: list[tuple[str, str, UpdateOne]],
    records: dict[str, dict[str, Any]],
) -> None:
    grouped: dict[str, list[tuple[str, UpdateOne]]] = {}
    for cod_id, operation in pending:
        collection_name, update = operation
        grouped.setdefault(collection_name, []).append((cod_id, update))
    for collection_name, operations in grouped.items():
        try:
            database[collection_name].bulk_write(
                [update for _, update in operations],
                ordered=False,
            )
            for cod_id, _ in operations:
                records[cod_id]["mongo"][collection_name] = "upserted"
        except Exception as exc:
            print(
                f"WARNING: bulk write failed for {collection_name}; "
                f"falling back to individual writes: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            for cod_id, update in operations:
                try:
                    database[collection_name].bulk_write([update], ordered=True)
                    records[cod_id]["mongo"][collection_name] = "upserted"
                except Exception as item_exc:
                    records[cod_id]["mongo"][collection_name] = "failed"
                    records[cod_id]["errors"].append(
                        {
                            "stage": "mongo_" + collection_name,
                            "error_type": type(item_exc).__name__,
                            "error_message": str(item_exc),
                        }
                    )


def select_ids(
    pair_ids: list[str],
    explicit_ids: list[str] | None,
    limit: int | None,
) -> list[str]:
    selected = pair_ids
    if explicit_ids:
        requested = set(explicit_ids)
        unknown = sorted(requested - set(pair_ids), key=int)
        if unknown:
            raise ValueError("requested IDs are not complete source pairs: " + ", ".join(unknown))
        selected = [cod_id for cod_id in pair_ids if cod_id in requested]
    if limit is not None:
        selected = selected[:limit]
    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import COD experimental single-crystal CIF/HKL pairs."
    )
    parser.add_argument("--cif-dir", type=Path, default=DEFAULT_SOURCE_CIF_DIR)
    parser.add_argument("--hkl-dir", type=Path, default=DEFAULT_SOURCE_HKL_DIR)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--no-mongo", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    cif_dir = args.cif_dir
    hkl_dir = args.hkl_dir
    data_root = get_data_root(args.data_root)
    cif_files, hkl_files, pair_ids = scan_source_pairs(cif_dir, hkl_dir)
    selected_ids = select_ids(pair_ids, args.ids, args.limit)
    mapping = load_mapping(args.mapping)

    database = None
    index_names: list[str] = []
    if not args.no_mongo:
        database = get_database()
        database.client.admin.command("ping")
        index_names = ensure_indexes(database)
        ensure_cod_source(database)

    allocator = CanonicalIdAllocator(mapping, database)
    records: dict[str, dict[str, Any]] = load_jsonl_records(args.records)
    previous_manifest: dict[str, Any] = {}
    if args.manifest.exists():
        try:
            previous_manifest = json.loads(
                args.manifest.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            previous_manifest = {}
    pending: list[tuple[str, tuple[str, UpdateOne]]] = []
    copy_summary = Counter()
    cif_parse_summary = Counter()
    hkl_parse_summary = Counter()
    mongo_summary = Counter()
    failures: list[dict[str, Any]] = []
    conflicts: list[dict[str, str]] = []

    args.records.parent.mkdir(parents=True, exist_ok=True)
    temporary_records = args.records.with_name(args.records.name + ".part")
    if temporary_records.exists():
        temporary_records.unlink()

    print(
        f"Input CIF: {len(cif_files)}; Input HKL: {len(hkl_files)}; "
        f"complete source pairs: {len(pair_ids)}; processing: {len(selected_ids)}"
    )

    try:
        for position, cod_id in enumerate(selected_ids, start=1):
            ids = ensure_mapping(cod_id, mapping, allocator, database)
            record: dict[str, Any] = {
                "cod_id": cod_id,
                "canonical_ids": ids,
                "copy": {},
                "parse": {},
                "mongo": {},
                "errors": [],
            }
            records[cod_id] = record
            cif_source = cif_files[cod_id]
            hkl_source = hkl_files[cod_id]
            cif_key = f"single_crystal/cod/cif/{cod_id}.cif"
            hkl_key = f"single_crystal/cod/hkl/{cod_id}.hkl"

            try:
                cif_status, cif_metadata = copy_and_verify(
                    cif_source,
                    resolve_data_path(cif_key, data_root),
                )
                record["copy"]["cif"] = cif_status
                copy_summary[f"cif_{cif_status}"] += 1
                if cif_status not in {"copied", "skip"}:
                    raise RuntimeError(f"CIF copy status: {cif_status}")
            except Exception as exc:
                record["errors"].append(
                    {
                        "stage": "cif_copy",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                if record["copy"].get("cif") == "conflict":
                    conflicts.append({"cod_id": cod_id, "file": "cif"})
                failures.append({"cod_id": cod_id, "stage": "cif_copy"})
                continue

            try:
                hkl_status, hkl_metadata = copy_and_verify(
                    hkl_source,
                    resolve_data_path(hkl_key, data_root),
                )
                record["copy"]["hkl"] = hkl_status
                copy_summary[f"hkl_{hkl_status}"] += 1
                if hkl_status not in {"copied", "skip"}:
                    raise RuntimeError(f"HKL copy status: {hkl_status}")
            except Exception as exc:
                record["errors"].append(
                    {
                        "stage": "hkl_copy",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                if record["copy"].get("hkl") == "conflict":
                    conflicts.append({"cod_id": cod_id, "file": "hkl"})
                failures.append({"cod_id": cod_id, "stage": "hkl_copy"})
                continue

            try:
                cif_parsed = parse_cod_cif(cif_source, source_id=cod_id)
                cif_parse_summary[cif_parsed["parse_status"]] += 1
                record["parse"]["cif"] = {
                    "status": cif_parsed["parse_status"],
                    "warnings": cif_parsed["parse_warnings"],
                }
            except Exception as exc:
                cif_parse_summary["failed"] += 1
                record["errors"].append(
                    {
                        "stage": "cif_parse",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                failures.append({"cod_id": cod_id, "stage": "cif_parse"})
                continue

            try:
                hkl_parsed = parse_cod_hkl(hkl_source, source_id=cod_id)
                hkl_parse_summary[hkl_parsed["parse_status"]] += 1
                record["parse"]["hkl"] = {
                    "status": hkl_parsed["parse_status"],
                    "warnings": hkl_parsed["parse_warnings"],
                    "reflection_count": hkl_parsed["reflection_count"],
                    "reflection_fields": hkl_parsed["reflection_fields"],
                }
            except Exception as exc:
                hkl_parse_summary["failed"] += 1
                record["errors"].append(
                    {
                        "stage": "hkl_parse",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                failures.append({"cod_id": cod_id, "stage": "hkl_parse"})
                continue

            if database is not None:
                timestamp = utc_now()
                operations = build_operations(
                    cod_id,
                    ids,
                    cif_parsed,
                    hkl_parsed,
                    file_record(cif_key, cif_metadata),
                    file_record(hkl_key, hkl_metadata),
                    timestamp,
                )
                pending.extend((cod_id, operation) for operation in operations)
                if len(pending) >= args.batch_size * 3:
                    flush_operations(database, pending, records)
                    pending.clear()

            if position == 1 or position % 25 == 0 or position == len(selected_ids):
                print(f"[{position}/{len(selected_ids)}] {cod_id}", flush=True)

        if database is not None and pending:
            flush_operations(database, pending, records)
            pending.clear()
    finally:
        write_json_atomic(args.mapping, mapping)
        with temporary_records.open("w", encoding="utf-8", newline="\n") as handle:
            for cod_id in sorted(records, key=int):
                handle.write(json.dumps(records[cod_id], ensure_ascii=False) + "\n")
        os.replace(temporary_records, args.records)

    if database is not None:
        mongo_summary = Counter(
            {
                "structures": database.structures.count_documents({"source": SOURCE_NAME}),
                "measurements": database.measurements.count_documents({"source": SOURCE_NAME}),
                "reflection_sets": database.reflection_sets.count_documents({"source": SOURCE_NAME}),
            }
        )
        mongo_summary["absolute_path_violations"] = count_absolute_path_violations(database)

    all_records = list(records.values())
    cif_record_summary = Counter(
        record.get("parse", {}).get("cif", {}).get("status")
        for record in all_records
        if record.get("parse", {}).get("cif", {}).get("status")
    )
    hkl_record_summary = Counter(
        record.get("parse", {}).get("hkl", {}).get("status")
        for record in all_records
        if record.get("parse", {}).get("hkl", {}).get("status")
    )
    cif_failed_count = sum(
        1
        for record in all_records
        for error in record.get("errors", [])
        if error.get("stage") == "cif_parse"
    )
    hkl_failed_count = sum(
        1
        for record in all_records
        for error in record.get("errors", [])
        if error.get("stage") == "hkl_parse"
    )
    all_failed_ids = sorted(
        {
            record["cod_id"]
            for record in all_records
            if record.get("errors")
        },
        key=int,
    )
    if previous_manifest and len(selected_ids) < len(pair_ids):
        final_manifest = dict(previous_manifest)
    else:
        final_manifest = {}
    final_manifest.update(
        {
        "source": SOURCE_FULL_NAME,
        "source_short_name": SOURCE_NAME,
        "source_pair_count": len(pair_ids),
        "selected_pair_count": (
            previous_manifest.get("selected_pair_count", len(pair_ids))
            if previous_manifest and len(selected_ids) < len(pair_ids)
            else len(selected_ids)
        ),
        "last_run_selected_pair_count": len(selected_ids),
        "import_timestamp_utc": utc_now(),
        "parser_versions": PARSER_VERSIONS,
        "file_copy_summary": final_manifest.get(
            "file_copy_summary",
            {
                "input_cif": len(cif_files),
                "input_hkl": len(hkl_files),
                "complete_source_pairs": len(pair_ids),
                "cif_copied_new": copy_summary["cif_copied"],
                "cif_skipped_same": copy_summary["cif_skip"],
                "hkl_copied_new": copy_summary["hkl_copied"],
                "hkl_skipped_same": copy_summary["hkl_skip"],
                "hash_verified_cif": copy_summary["cif_copied"] + copy_summary["cif_skip"],
                "hash_verified_hkl": copy_summary["hkl_copied"] + copy_summary["hkl_skip"],
            },
        ),
        "hash_summary": final_manifest.get(
            "hash_summary",
            {"conflict_count": 0, "conflicts": []},
        ),
        "cif_parse_summary": {
            "ok": cif_record_summary["ok"],
            "partial": cif_record_summary["partial"],
            "failed": cif_failed_count,
        },
        "hkl_parse_summary": {
            "ok": hkl_record_summary["ok"],
            "partial": hkl_record_summary["partial"],
            "failed": hkl_failed_count,
        },
        "mongo_import_summary": {
            "structures_cod_count": mongo_summary["structures"],
            "measurements_cod_count": mongo_summary["measurements"],
            "reflection_sets_cod_count": mongo_summary["reflection_sets"],
            "absolute_path_violations": mongo_summary["absolute_path_violations"],
            "indexes_requested": index_names,
        },
        "failed_cod_ids": all_failed_ids,
        "failure_count": len(all_failed_ids),
        "conflicts": final_manifest.get("conflicts", []) + conflicts,
        "mapping_count": len(mapping),
        "data_root": str(data_root),
        }
    )
    write_json_atomic(args.manifest, final_manifest)

    print("\nFinal QC")
    print(f"Source pairs: {len(pair_ids)} (selected {len(selected_ids)})")
    print(
        f"CIF copied: {copy_summary['cif_copied']} new, "
        f"{copy_summary['cif_skip']} already verified"
    )
    print(
        f"HKL copied: {copy_summary['hkl_copied']} new, "
        f"{copy_summary['hkl_skip']} already verified"
    )
    print(f"CIF hash verified: {copy_summary['cif_copied'] + copy_summary['cif_skip']}")
    print(f"HKL hash verified: {copy_summary['hkl_copied'] + copy_summary['hkl_skip']}")
    print(f"Hash conflicts: {len(conflicts)}")
    print(
        f"CIF parse OK/partial/failed: {cif_parse_summary['ok']}/"
        f"{cif_parse_summary['partial']}/{cif_parse_summary['failed']}"
    )
    print(
        f"HKL parse OK/partial/failed: {hkl_parse_summary['ok']}/"
        f"{hkl_parse_summary['partial']}/{hkl_parse_summary['failed']}"
    )
    if database is not None:
        print(f"Mongo structures: {mongo_summary['structures']}")
        print(f"Mongo measurements: {mongo_summary['measurements']}")
        print(f"Mongo reflection_sets: {mongo_summary['reflection_sets']}")
        print(f"Mongo absolute-path violations: {mongo_summary['absolute_path_violations']}")
    print(f"Failed COD IDs: {len(set(item['cod_id'] for item in failures))}")
    print(f"Manifest: {args.manifest}")
    print(f"Records: {args.records}")
    return 0 if not failures and not conflicts else 1


if __name__ == "__main__":
    raise SystemExit(main())
