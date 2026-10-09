from __future__ import annotations

import json
from pathlib import Path

from scripts.integrate_powbase_production_v1 import (
    BACKUP_COLLECTIONS,
    EXPECTED_DELTA,
    EXPECTED_ENTRY_IDS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "powbase_production_integration_v1.json"
)


def test_integration_report_records_exact_expected_delta() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["integration_passed"] is True
    assert report["included_entry_ids"] == EXPECTED_ENTRY_IDS
    assert len(report["included_entry_ids"]) == 44
    assert report["backup"]["complete"] is True
    assert report["backup"]["errors"] == []
    assert report["unexpected_delta"] == {}
    assert report["unexpected_total_delta"] == {}
    assert report["post_write_validation"]["ready"] is True
    assert report["archive_hash_verification"]["all_byte_identical_to_inventory"] is True

    assert report["production_delta"] == EXPECTED_DELTA
    assert all(
        report["production_delta"][collection_name] == EXPECTED_DELTA[collection_name]
        for collection_name in BACKUP_COLLECTIONS
    )


def test_integration_report_preserves_conservative_scientific_fields() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    validation = report["post_write_validation"]

    assert validation["powbase_counts"] == {
        "sources": 1,
        "samples": 44,
        "measurements": 44,
        "patterns": 44,
    }
    assert validation["xy_payload_count"] == 44
    assert validation["known_wavelength_count"] == 6
    assert validation["unknown_wavelength_count"] == 38
    assert validation["phase_character_unknown_count"] == 44
    assert validation["powbase_relations"] == 0
    assert validation["errors"] == []
