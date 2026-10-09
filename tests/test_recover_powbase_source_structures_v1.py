from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.recover_powbase_source_structures_v1 import (
    TARGET_ENTRY_IDS,
    build_audit,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006" / "archives"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_structure_recovery_scope_and_model_counts() -> None:
    audit = build_audit()
    assert audit["scope"]["entry_ids"] == TARGET_ENTRY_IDS
    assert audit["counts"]["patterns_evaluated"] == 9
    assert audit["counts"]["total_source_structure_models"] == 14
    assert [row["entry_id"] for row in audit["records"]].count("157") == 5
    assert all(row["experimental_profile_present"] for row in audit["records"])


def test_source_models_are_separate_and_entry_157_is_ambiguous() -> None:
    audit = build_audit()
    rows = {row["entry_id"]: [item for item in audit["records"] if item["entry_id"] == row["entry_id"]] for row in audit["records"]}
    assert len(rows["106"]) == 2
    assert all(row["source_model_id"] in {"PHASE_1", "PHASE_2"} for row in rows["106"])
    assert len(rows["157"]) == 5
    assert {row["proposed_linkage_status"] for row in rows["157"]} == {
        "source_link_ambiguous"
    }
    assert {row["model_name"] for row in rows["157"]} == {
        "ICSD Collection Code 202243,  Anatase Ti O2",
        "ICSD Collection Code 6162,  Gibbsite Al (O H)3",
        "ICSD Collection Code 66756,  Hematite Fe2 O3",
        "Quartz",
        "Kaolinite Al4 (O H)8 (Si4 O10)",
    }


def test_cifs_validate_without_source_archive_changes() -> None:
    before = {
        entry_id: _sha256(ARCHIVE_ROOT / f"{entry_id}.zip")
        for entry_id in TARGET_ENTRY_IDS
    }
    audit = build_audit()
    after = {
        entry_id: _sha256(ARCHIVE_ROOT / f"{entry_id}.zip")
        for entry_id in TARGET_ENTRY_IDS
    }
    assert before == after
    assert audit["counts"]["cifs_successfully_recovered"] == 10
    assert audit["counts"]["cifs_failed"] == 0
    assert all(
        row["cif_validation_status"] == "passed"
        for row in audit["records"]
        if row["cif_recoverable"]
    )
    assert all(
        row["staging_cif_path"] is None
        for row in audit["records"]
        if not row["unit_cell_complete"]
    )


def test_wavelength_discrepancy_identifies_entry_116() -> None:
    audit = build_audit()
    discrepancy = audit["wavelength_discrepancy"]
    assert discrepancy["metadata_completeness_count"] == 7
    assert discrepancy["production_known_wavelength_count"] == 6
    assert discrepancy["discrepancy_entry_ids"] == ["116"]
    row = discrepancy["records"][0]
    assert row["parsed_numeric_wavelength_angstrom"] == [1.54056, 1.54439]
    assert row["production_stored_value"] == ""
