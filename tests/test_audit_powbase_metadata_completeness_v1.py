from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.audit_powbase_metadata_completeness_v1 import (
    PRODUCTION_ENTRY_IDS,
    build_audit,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006" / "archives"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_metadata_completeness_scope_is_exactly_44_production_records() -> None:
    audit = build_audit()
    assert audit["scope"]["production_record_count"] == 44
    assert len(audit["records"]) == 44
    assert [row["powbase_entry"] for row in audit["records"]] == sorted(
        PRODUCTION_ENTRY_IDS, key=int
    )
    assert audit["scope"]["conditional_or_unresolved_records_inspected"] is False


def test_metadata_completeness_preserves_formula_uncertainty_and_structure_fields() -> None:
    audit = build_audit()
    rows = {row["powbase_entry"]: row for row in audit["records"]}

    assert audit["counts"]["explicit_formula"] == 0
    assert rows["10"]["formula_status"] == "formula_like_label_only"
    assert rows["10"]["explicit_formula"] is None

    assert rows["106"]["phase_model_count"] == 2
    assert rows["106"]["has_space_group"] is True
    assert rows["106"]["has_atomic_coordinates"] is True
    assert rows["106"]["has_full_unit_cell"] is True

    assert rows["125"]["has_structure_metadata"] is True
    assert rows["125"]["formula_status"] == "formula_like_label_only"
    assert rows["125"]["cif_recoverability"] == "sufficient_source_structure_metadata"

    assert rows["157"]["phase_model_count"] == 5
    assert rows["157"]["has_full_unit_cell"] is True
    assert rows["157"]["cif_recoverability"] == "sufficient_source_structure_metadata"


def test_metadata_completeness_expected_counts_and_no_source_changes() -> None:
    source = ARCHIVE_ROOT / "137.zip"
    before = _sha256(source)
    audit = build_audit()
    after = _sha256(source)

    assert before == after
    assert audit["counts"] == {
        "total_records": 44,
        "material_label": 44,
        "explicit_formula": 0,
        "formula_like_label_only": 36,
        "wavelength": 7,
        "complete_unit_cell": 9,
        "space_group": 9,
        "atomic_coordinates": 9,
        "explicit_refinement_or_phase_model": 9,
        "sufficient_structure_metadata_for_cif_recovery": 9,
        "profile_only": 35,
        "bibliographic_reference": 15,
        "bibliographic_comment_present": 44,
        "total_phase_models": 14,
    }
