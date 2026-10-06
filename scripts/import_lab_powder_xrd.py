#!/usr/bin/env python3
"""Import canonical laboratory powder-XRD TXT files into CrystalDB."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from crystaldb.data_paths import get_data_root, make_file_key
from crystaldb.sources.lab.canonical_xrd_parser import (
    CanonicalXrdRecord,
    parse_canonical_xrd,
)


WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
SOURCE_DOCUMENT = {
    "source_id": "SRC_LAB",
    "name": "Laboratory experimental XRD",
    "short_name": "lab",
    "source_type": "internal_experiment",
    "data_origin": "experimental",
    "modalities": ["powder_xrd"],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_pattern_files(
    pattern_root: Path,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[Path]:
    files = sorted(
        (path for path in pattern_root.glob("*.txt") if path.is_file()),
        key=lambda path: (path.name.casefold(), path.name),
    )
    if offset:
        files = files[offset:]
    if limit is not None:
        files = files[:limit]
    return files


def _relative_file_key(path: Path, data_root: Path) -> str:
    relative = path.resolve().relative_to(data_root.resolve())
    return make_file_key(relative)


def build_documents(
    record: CanonicalXrdRecord,
    *,
    file_key: str,
    file_sha256: str,
    file_size_bytes: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sample = {
        "sample_id": record.sample_id,
        "source": record.source,
        "contributor": record.contributor,
        "source_series_label": record.source_series_label,
        "source_sample_label": record.source_sample_label,
        "nominal_element_ratio": record.nominal_element_ratio,
        "phase_character": record.phase_character,
        "provenance": {"source_type": "lab_experiment"},
    }
    measurement = {
        "measurement_id": record.measurement_id,
        "sample_id": record.sample_id,
        "pattern_id": record.pattern_id,
        "source": record.source,
        "data_origin": record.data_origin,
        "measurement_type": record.modality,
        "measurement_date": record.measurement_date,
        "radiation": {
            "characteristic": record.radiation_characteristic,
            "wavelength_kalpha1_angstrom": record.wavelength_kalpha1_angstrom,
            "wavelength_kalpha2_angstrom": record.wavelength_kalpha2_angstrom,
        },
        "instrument": {
            "voltage_kv": record.voltage_kv,
            "current_ma": record.current_ma,
            "detector": record.detector,
        },
        "parse_status": record.parse_status,
    }
    pattern = {
        "pattern_id": record.pattern_id,
        "measurement_id": record.measurement_id,
        "sample_id": record.sample_id,
        "source": record.source,
        "data_origin": record.data_origin,
        "modality": record.modality,
        "xrd": {
            "has_xy": True,
            "x_axis": "two_theta",
            "x_unit": record.x_unit,
            "y_axis": "intensity",
            "y_unit": record.y_unit,
            "point_count": record.point_count,
            "two_theta": list(record.two_theta),
            "intensity": list(record.intensity),
        },
        "scan": {
            "scan_axis": record.scan_axis,
            "start_2theta_deg": record.start_2theta_deg,
            "stop_2theta_deg": record.stop_2theta_deg,
            "step_2theta_deg": record.step_2theta_deg,
        },
        "file": {
            "key": file_key,
            "sha256": file_sha256,
            "size_bytes": file_size_bytes,
        },
        "provenance": {
            "original_filename": record.original_filename,
            "original_relative_path": record.original_relative_path,
            "original_sha256": record.original_sha256,
        },
        "qc": {
            **record.qc,
        },
        "parse_status": record.parse_status,
        "parse_warnings": list(record.parse_warnings),
    }
    return sample, measurement, pattern


def _sample_update(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": document["sample_id"],
        "source": document["source"],
        "contributor": document["contributor"],
        "source_series_label": document["source_series_label"],
        "source_sample_label": document["source_sample_label"],
        "nominal_element_ratio": document["nominal_element_ratio"],
        "phase_character": document["phase_character"],
        "provenance.source_type": document["provenance"]["source_type"],
    }


def _measurement_update(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "measurement_id": document["measurement_id"],
        "sample_id": document["sample_id"],
        "pattern_id": document["pattern_id"],
        "source": document["source"],
        "data_origin": document["data_origin"],
        "measurement_type": document["measurement_type"],
        "measurement_date": document["measurement_date"],
        "radiation.characteristic": document["radiation"]["characteristic"],
        "radiation.wavelength_kalpha1_angstrom": document["radiation"][
            "wavelength_kalpha1_angstrom"
        ],
        "radiation.wavelength_kalpha2_angstrom": document["radiation"][
            "wavelength_kalpha2_angstrom"
        ],
        "instrument.voltage_kv": document["instrument"]["voltage_kv"],
        "instrument.current_ma": document["instrument"]["current_ma"],
        "instrument.detector": document["instrument"]["detector"],
        "parse_status": document["parse_status"],
    }


def _pattern_update(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern_id": document["pattern_id"],
        "measurement_id": document["measurement_id"],
        "sample_id": document["sample_id"],
        "source": document["source"],
        "data_origin": document["data_origin"],
        "modality": document["modality"],
        "xrd": document["xrd"],
        "scan": document["scan"],
        "file": document["file"],
        "provenance": document["provenance"],
        "qc": document["qc"],
        "parse_status": document["parse_status"],
        "parse_warnings": document["parse_warnings"],
    }


def _contains_windows_absolute_path(value: Any) -> bool:
    if isinstance(value, str):
        return bool(WINDOWS_ABSOLUTE_RE.match(value))
    if isinstance(value, dict):
        return any(_contains_windows_absolute_path(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_windows_absolute_path(item) for item in value)
    return False


def _print_record(
    record: CanonicalXrdRecord,
    *,
    file_key: str | None = None,
) -> None:
    print(f"FILE: {file_key or record.path}")
    print(f"sample_id: {record.sample_id}")
    print(f"measurement_id: {record.measurement_id}")
    print(f"pattern_id: {record.pattern_id}")
    print(f"point_count: {record.point_count}")
    print(f"first_5_two_theta: {list(record.two_theta[:5])}")
    print(f"first_5_intensity: {list(record.intensity[:5])}")
    print(f"last_5_two_theta: {list(record.two_theta[-5:])}")
    print(f"last_5_intensity: {list(record.intensity[-5:])}")
    print(f"QC: {json.dumps(record.qc, sort_keys=True)}")
    print(f"parse_status: {record.parse_status}")
    if record.parse_warnings:
        print(f"parse_warnings: {list(record.parse_warnings)}")


def _new_summary(files: list[Path]) -> dict[str, Any]:
    return {
        "canonical_files": len(files),
        "parsed_ok": 0,
        "parsed_partial": 0,
        "parsed_failed": 0,
        "samples_upserted": 0,
        "measurements_upserted": 0,
        "patterns_upserted": 0,
        "unique_samples": 0,
        "unique_measurements": 0,
        "unique_patterns": 0,
        "samples_with_repeated_measurements": 0,
        "point_count_mismatch": 0,
        "axis_inconsistency": 0,
        "missing_sample_id": 0,
        "missing_measurement_id": 0,
        "missing_pattern_id": 0,
        "duplicate_sample_ids": 0,
        "duplicate_measurement_ids": 0,
        "duplicate_pattern_ids": 0,
        "mongo_sample_documents": None,
        "mongo_measurement_documents": None,
        "mongo_pattern_documents": None,
        "absolute_path_violations": None,
        "mongo_array_checks": [],
    }


def _update_parse_summary(
    summary: dict[str, Any],
    record: CanonicalXrdRecord,
    counters: dict[str, Counter[str]],
) -> None:
    status_key = {
        "ok": "parsed_ok",
        "partial": "parsed_partial",
        "failed": "parsed_failed",
    }[record.parse_status]
    summary[status_key] += 1
    for field, counter_key in (
        ("sample_id", "missing_sample_id"),
        ("measurement_id", "missing_measurement_id"),
        ("pattern_id", "missing_pattern_id"),
    ):
        value = getattr(record, field)
        if value:
            counters[field][value] += 1
        else:
            summary[counter_key] += 1
    if record.qc["point_count_match"] is False:
        summary["point_count_mismatch"] += 1
    if record.qc["axis_consistent"] is False:
        summary["axis_inconsistency"] += 1


def _write_report(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _ensure_indexes(database: Any) -> None:
    index_specs = {
        "samples": [
            ([("sample_id", 1)], {"unique": True, "name": "sample_id_unique"}),
            ([("source", 1)], {"name": "source"}),
            ([("contributor", 1)], {"name": "contributor"}),
            ([("nominal_element_ratio", 1)], {"name": "nominal_element_ratio"}),
        ],
        "measurements": [
            [
                [("measurement_id", 1)],
                {"unique": True, "name": "measurement_id_unique"},
            ],
            [[("sample_id", 1)], {"name": "sample_id"}],
            [[("pattern_id", 1)], {"name": "pattern_id"}],
            [[("source", 1)], {"name": "source"}],
            [[("measurement_type", 1)], {"name": "measurement_type"}],
        ],
        "patterns": [
            ([("pattern_id", 1)], {"unique": True, "name": "pattern_id_unique"}),
            ([("measurement_id", 1)], {"name": "measurement_id"}),
            ([("sample_id", 1)], {"name": "sample_id"}),
            ([("source", 1)], {"name": "source"}),
            ([("data_origin", 1)], {"name": "data_origin"}),
        ],
    }
    for collection_name, specs in index_specs.items():
        collection = database[collection_name]
        for keys, options in specs:
            collection.create_index(keys, **options)


def _upsert_source(database: Any) -> None:
    database.sources.update_one(
        {"source_id": SOURCE_DOCUMENT["source_id"]},
        {"$set": SOURCE_DOCUMENT},
        upsert=True,
    )


def _upsert_documents(
    database: Any,
    sample: dict[str, Any],
    measurement: dict[str, Any],
    pattern: dict[str, Any],
) -> None:
    database.samples.update_one(
        {"sample_id": sample["sample_id"]},
        {"$set": _sample_update(sample)},
        upsert=True,
    )
    database.measurements.update_one(
        {"measurement_id": measurement["measurement_id"]},
        {"$set": _measurement_update(measurement)},
        upsert=True,
    )
    database.patterns.update_one(
        {"pattern_id": pattern["pattern_id"]},
        {"$set": _pattern_update(pattern)},
        upsert=True,
    )


def _mongo_counts(database: Any) -> dict[str, int]:
    return {
        "samples": database.samples.count_documents({"source": "lab"}),
        "measurements": database.measurements.count_documents({"source": "lab"}),
        "patterns": database.patterns.count_documents({"source": "lab"}),
    }


def _mongo_absolute_path_violations(database: Any) -> int:
    count = 0
    for collection_name in ("samples", "measurements", "patterns"):
        for document in database[collection_name].find({"source": "lab"}):
            if _contains_windows_absolute_path(document):
                count += 1
    return count


def _verify_random_patterns(
    database: Any,
    successful_files: list[tuple[Path, str]],
    *,
    data_root: Path,
    seed: int = 20261003,
) -> list[dict[str, Any]]:
    if not successful_files:
        return []
    selected = random.Random(seed).sample(
        successful_files,
        min(5, len(successful_files)),
    )
    checks: list[dict[str, Any]] = []
    for path, pattern_id in selected:
        record = parse_canonical_xrd(path)
        document = database.patterns.find_one(
            {"pattern_id": pattern_id},
            {"_id": 0, "xrd": 1},
        )
        actual = document.get("xrd", {}) if document else {}
        expected_x = list(record.two_theta)
        expected_y = list(record.intensity)
        actual_x = actual.get("two_theta", [])
        actual_y = actual.get("intensity", [])
        check = {
            "pattern_id": pattern_id,
            "file_key": _relative_file_key(path, data_root),
            "point_count_match": actual.get("point_count") == record.point_count,
            "two_theta_length_match": len(actual_x) == len(expected_x),
            "intensity_length_match": len(actual_y) == len(expected_y),
            "first_5_match": (
                actual_x[:5] == expected_x[:5]
                and actual_y[:5] == expected_y[:5]
            ),
            "last_5_match": (
                actual_x[-5:] == expected_x[-5:]
                and actual_y[-5:] == expected_y[-5:]
            ),
        }
        check["ok"] = all(
            value for key, value in check.items() if key != "pattern_id"
            and key != "file_key"
        )
        checks.append(check)
    return checks


def run_import(args: argparse.Namespace) -> dict[str, Any]:
    data_root = get_data_root(args.data_root)
    pattern_root = (
        Path(args.patterns_dir)
        if args.patterns_dir
        else data_root / "powder" / "lab" / "patterns"
    )
    files = discover_pattern_files(
        pattern_root,
        limit=args.limit,
        offset=args.offset,
    )
    summary = _new_summary(files)
    counters = {
        "sample_id": Counter(),
        "measurement_id": Counter(),
        "pattern_id": Counter(),
    }
    failures: list[dict[str, Any]] = []
    successful_files: list[tuple[Path, str]] = []
    parsed_records: list[tuple[Path, CanonicalXrdRecord, str, str, int]] = []

    if not pattern_root.exists():
        failures.append(
            {
                "file_key": None,
                "parse_status": "failed",
                "parse_warnings": [f"missing_patterns_directory:{pattern_root}"],
            }
        )
    for path in files:
        record = parse_canonical_xrd(path)
        try:
            file_key = _relative_file_key(path, data_root)
        except (OSError, ValueError) as exc:
            file_key = None
            record = CanonicalXrdRecord(
                **{
                    **record.__dict__,
                    "parse_status": "failed",
                    "parse_warnings": tuple(
                        list(record.parse_warnings)
                        + [f"invalid_file_key:{exc}"]
                    ),
                }
            )
        file_sha256 = sha256_file(path)
        file_size_bytes = path.stat().st_size
        _update_parse_summary(summary, record, counters)
        if args.print_records:
            _print_record(record, file_key=file_key)
        if record.parse_status == "failed":
            failures.append(
                {
                    "file_key": file_key,
                    "parse_status": record.parse_status,
                    "parse_warnings": list(record.parse_warnings),
                    "sample_id": record.sample_id,
                    "measurement_id": record.measurement_id,
                    "pattern_id": record.pattern_id,
                }
            )
            continue
        parsed_records.append(
            (path, record, file_key, file_sha256, file_size_bytes)
        )
        successful_files.append((path, record.pattern_id or ""))

    for counter_name, field_name in (
        ("sample_id", "duplicate_sample_ids"),
        ("measurement_id", "duplicate_measurement_ids"),
        ("pattern_id", "duplicate_pattern_ids"),
    ):
        summary[field_name] = sum(
            1 for count in counters[counter_name].values() if count > 1
        )
    summary["unique_samples"] = len(counters["sample_id"])
    summary["unique_measurements"] = len(counters["measurement_id"])
    summary["unique_patterns"] = len(counters["pattern_id"])
    summary["samples_with_repeated_measurements"] = sum(
        1 for count in counters["sample_id"].values() if count > 1
    )

    if not args.dry_run and parsed_records:
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise RuntimeError(
                "pymongo is required for Mongo import; install project dependencies"
            ) from exc
        client = MongoClient(
            args.uri,
            serverSelectionTimeoutMS=args.server_selection_timeout_ms,
        )
        database = client[args.database]
        database.command("ping")
        _ensure_indexes(database)
        _upsert_source(database)
        for path, record, file_key, file_sha256, file_size_bytes in parsed_records:
            sample, measurement, pattern = build_documents(
                record,
                file_key=file_key,
                file_sha256=file_sha256,
                file_size_bytes=file_size_bytes,
            )
            _upsert_documents(database, sample, measurement, pattern)
        summary["samples_upserted"] = summary["unique_samples"]
        summary["measurements_upserted"] = len(parsed_records)
        summary["patterns_upserted"] = len(parsed_records)
        counts = _mongo_counts(database)
        summary["mongo_sample_documents"] = counts["samples"]
        summary["mongo_measurement_documents"] = counts["measurements"]
        summary["mongo_pattern_documents"] = counts["patterns"]
        summary["absolute_path_violations"] = _mongo_absolute_path_violations(
            database
        )
        summary["mongo_array_checks"] = _verify_random_patterns(
            database,
            successful_files,
            data_root=data_root,
        )
        client.close()

    if args.failure_report:
        _write_report(Path(args.failure_report), failures)
    if args.summary_json:
        _write_report(Path(args.summary_json), summary)

    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if failures:
        print(f"Failure report: {args.failure_report or '<not written>'}")
    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import canonical lab powder-XRD TXT files into CrystalDB."
    )
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--patterns-dir", default=None)
    parser.add_argument("--uri", default=os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"))
    parser.add_argument("--database", default=os.environ.get("CRYSTALDB_MONGO_DATABASE", "crystaldb"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-records", action="store_true")
    parser.add_argument("--failure-report", default="reports/lab_xrd_import_failures_v1.json")
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--server-selection-timeout-ms", type=int, default=5000)
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    try:
        run_import(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
