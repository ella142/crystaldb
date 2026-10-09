from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "powbase_source_structure_production_integration_v1.json"
)


def test_production_structure_integration_report_is_exact_and_idempotent() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["integration_passed"] is True
    assert report["write_counts"]["structures_inserted"] == 10
    assert report["write_counts"]["relations_inserted"] == 7
    assert report["counts"]["after"]["patterns"] == report["counts"]["before"]["patterns"]
    assert report["validation"]["duplicate_ids_total"] == 0
    assert report["validation"]["orphan_relations"] == []
    assert report["validation"]["idempotent_exact_matches"] is True
    assert report["validation"]["ambiguous_linkage"]["clear"] is True
    assert report["validation"]["entry_157_literal"]["literal_51323_preserved"] is True
    assert report["validation"]["incomplete_entry_157"]["clear"] is True


def test_entry_116_wavelengths_and_scope_are_conservative() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["write_sets"]["entry_116_pattern_update"]["values"] == {
        "wavelength_angstrom": 1.54056,
        "wavelength_kalpha2_angstrom": 1.54439,
    }
    assert report["write_sets"]["entry_116_measurement_update"]["values"] == {
        "wavelength_angstrom": 1.54056,
        "wavelength_kalpha2_angstrom": 1.54439,
    }
    assert report["scope"]["incomplete_entry_157_models_registered"] == 0
    assert report["prohibited_operations"]["new_powbase_patterns"] is False
    assert report["prohibited_operations"]["entries_15_74_121_156_processed"] is False
