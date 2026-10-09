from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from scripts.prepare_powbase_canonical_v1 import (
    _independent_numeric_block,
    axis_and_qc,
    explicit_wavelengths,
    prepare,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_independent_numeric_block_and_axis_qc() -> None:
    lines = [
        "! KCAF3 SOLUTION 1 ANISO",
        "15.00 0.04 15.08",
        "1 2",
        "3",
    ]

    block = _independent_numeric_block(lines, 2)
    axis, checks, errors = axis_and_qc(
        start=15.00,
        step=0.04,
        end=15.08,
        expected_count=3,
        intensities=[1, 2, 3],
        independent_count=block["count"],
        independent_values=[1.0, 2.0, 3.0],
    )

    assert block["tokens"] == ["1", "2", "3"]
    assert axis == [15.0, 15.04, 15.08]
    assert checks["point_count_match"] is True
    assert checks["independent_parser_values_match"] is True
    assert errors == []


def test_explicit_wavelength_policy_does_not_infer_from_radiation_text() -> None:
    assert explicit_wavelengths(
        index_tokens=["Sample", "X", "Cu-Kalpha"],
        text="! radiation probe Cu-Kalpha\n",
        fullprof={},
    ) == []

    records = explicit_wavelengths(
        index_tokens=["Al2O3", "X", "1.54056 A"],
        text="",
        fullprof={},
    )
    assert records[0]["source"] == "official_powbase_index"
    assert records[0]["value"] == 1.54056


def test_full_cached_powbase_preparation_is_complete_and_source_read_only(
    tmp_path: Path,
) -> None:
    source_archive = ARCHIVE_ROOT / "archives" / "10.zip"
    source_hash_before = sha256_file(source_archive)

    payload = prepare(
        inclusion_manifest=PROJECT_ROOT
        / "data"
        / "mappings"
        / "powbase_v1_inclusion_manifest.csv",
        archive_root=ARCHIVE_ROOT,
        staging_root=tmp_path / "staging",
        json_output=tmp_path / "powbase_canonical_dryrun_v1.json",
        csv_output=tmp_path / "powbase_canonical_validation_v1.csv",
        summary_output=tmp_path / "powbase_canonical_summary_v1.md",
        inspect_mongo=False,
    )

    summary = payload["summary"]
    assert summary["selected_records"] == 44
    assert summary["successfully_parsed_profiles"] == 44
    assert summary["prepared_samples"] == 44
    assert summary["prepared_measurements"] == 44
    assert summary["prepared_patterns"] == 44
    assert summary["prepared_xy_payloads"] == 44
    assert summary["failed_or_quarantined_records"] == 0
    assert summary["validation_error_record_count"] == 0
    assert summary["explicit_wavelength_count"] == 6
    assert summary["missing_wavelength_count"] == 38
    assert summary["stable_identifier_collision_count"] == 0
    assert summary["ready_for_mongodb_staging"] is True
    assert payload["mongodb_read_only_check"]["status"] == "skipped"

    records = {record["entry_id"]: record for record in payload["records"]}
    assert len(records) == 44
    assert len({record["sample_id"] for record in records.values()}) == 44
    assert len({record["measurement_id"] for record in records.values()}) == 44
    assert len({record["pattern_id"] for record in records.values()}) == 44

    entry_4 = records["4"]
    assert entry_4["sample"]["formula"] is None
    assert entry_4["sample"]["phase_character"] == "unknown"
    assert entry_4["pattern"]["structure_linkage"]["status"] == "unlinked"
    assert entry_4["measurement"]["conditions"]["wavelength_angstrom"] is None

    entry_106 = records["106"]
    assert entry_106["pattern"]["phase_character"] == "unknown"
    assert entry_106["pattern"]["structure_linkage"]["candidate_structure_ids"] == []
    assert entry_106["measurement"]["conditions"]["wavelength_angstrom"] == 1.54056
    assert entry_106["measurement"]["conditions"]["wavelength_kalpha2_angstrom"] == 1.54439

    duplicate_groups = payload["potential_duplicates"]["same_source_label_groups"]
    assert {"entry_ids": ["66", "67", "68"], "normalized_label": "alphakalf4"} in duplicate_groups
    assert len(payload["potential_duplicates"]["existing_local_matches"]) == 2
    assert all(
        record["pattern"]["xrd"]["point_count"]
        == len(record["pattern"]["xrd"]["two_theta"])
        == len(record["pattern"]["xrd"]["intensity"])
        for record in records.values()
    )

    with (tmp_path / "powbase_canonical_validation_v1.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 44
    assert all(row["validation_status"] == "ok" for row in rows)

    assert sha256_file(source_archive) == source_hash_before
