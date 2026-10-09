from __future__ import annotations

import csv
from pathlib import Path

from scripts.review_powbase_v1 import (
    detect_header_with_suffix,
    detect_uxd_style,
    radiation_evidence,
    run_review,
)


def test_detect_uxd_style_requires_explicit_axis_and_counts() -> None:
    text = (
        "_START= 18.000\n"
        "_STEPSIZE= 0.0100000\n"
        "_STEPCOUNT=3\n"
        "_COUNTS\n"
        "10 20\n"
        "30\n"
    )

    result = detect_uxd_style(text)

    assert result is not None
    assert result["format_family"] == "uxd_style_pattern"
    assert result["expected_point_count"] == 3
    assert result["raw_numeric_value_count"] == 3
    assert result["point_count_consistency"] is True


def test_detect_header_with_source_suffix() -> None:
    text = (
        "16.00 0.03 16.06 CuKalpha\n"
        "10 20 30\n"
    )

    result = detect_header_with_suffix(text)

    assert result is not None
    assert result["format_family"] == (
        "legacy_intensity_array_with_source_suffix"
    )
    assert result["source_suffix"] == "CuKalpha"
    assert result["expected_point_count"] == 3
    assert result["point_count_consistency"] is True


def test_radiation_conflict_uses_explicit_source_token_only() -> None:
    neutron_index = {"raw_hash_delimited_tokens": ["Example", "N", "1.5945"]}
    xray_text_index = {
        "raw_hash_delimited_tokens": ["Example", "N", "Cu-Kalpha"]
    }

    assert radiation_evidence(neutron_index)[0] == "neutron"
    assert radiation_evidence(neutron_index)[2] is False
    assert radiation_evidence(xray_text_index)[2] is True


def test_full_cached_review_includes_entry_137_and_preserves_raw_index(
    tmp_path: Path,
) -> None:
    root = Path("data/archive/powbase_20261006")
    manifest = run_review(
        inventory_path=root / "inventory/powbase_archive_inventory.jsonl",
        index_path=root / "inventory/powbase_index_inventory.jsonl",
        output_dir=tmp_path,
    )

    assert manifest["summary"]["record_count"] == 170
    assert manifest["summary"]["verified_diffraction_profile_count"] == 48
    assert manifest["summary"]["conditionally_parseable_profile_count"] == 76
    assert manifest["summary"]["unresolved_profile_count"] == 46

    with (tmp_path / "powbase_review_records_v1.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    entry_137 = next(row for row in rows if row["entry_id"] == "137")

    assert entry_137["review_status"] == "conditionally_parseable"
    assert entry_137["expected_point_count"] == "3001"
    assert entry_137["observed_intensity_count"] == "3010"
    assert entry_137["trailing_zero_padding_count"] == "9"
    assert entry_137["phase_character"] == "unknown"
    assert "<A href=" in entry_137["raw_index_text"]
