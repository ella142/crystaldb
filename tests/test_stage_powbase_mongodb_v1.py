from __future__ import annotations

from pathlib import Path

import pytest

from scripts.stage_powbase_mongodb_v1 import (
    DEFAULT_CANONICAL_JSON,
    DEFAULT_STAGING_ROOT,
    load_local_documents,
    stage,
    validate_local_documents,
)


def test_cached_powbase_staging_has_44_valid_records() -> None:
    local = load_local_documents(DEFAULT_STAGING_ROOT, DEFAULT_CANONICAL_JSON)
    validation = validate_local_documents(local)

    assert validation["counts"] == {
        "samples": 44,
        "measurements": 44,
        "patterns": 44,
        "xy_payloads": 44,
    }
    assert validation["errors"] == []
    assert validation["wavelength_counts"] == {"known": 6, "unknown": 38}
    assert validation["source_distribution"] == {"POWBASE": 44}
    assert validation["phase_character_distribution"] == {"unknown": 44}


def test_staging_database_guard_rejects_production_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="forbidden database"):
        stage(
            database_name="crystaldb",
            staging_root=DEFAULT_STAGING_ROOT,
            canonical_json=DEFAULT_CANONICAL_JSON,
            json_output=tmp_path / "validation.json",
            csv_output=tmp_path / "validation.csv",
            summary_output=tmp_path / "summary.md",
        )
