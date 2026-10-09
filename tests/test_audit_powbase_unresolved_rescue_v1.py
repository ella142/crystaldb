from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.audit_powbase_unresolved_rescue_v1 import (
    RESCUE_ENTRY_IDS,
    build_audit,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006" / "archives"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rescue_scope_is_exactly_the_30_unresolved_xray_records() -> None:
    audit = build_audit()
    assert audit["scope"]["record_count"] == 30
    assert [record["entry_id"] for record in audit["records"]] == RESCUE_ENTRY_IDS
    assert all(
        record["source_modality_class"] == "x-ray"
        for record in audit["records"]
    )
    assert all(record["archive_member_count"] == 1 for record in audit["records"])


def test_koalariet_files_are_recovered_without_changing_archive_bytes() -> None:
    before = {entry_id: _sha256(ARCHIVE_ROOT / f"{entry_id}.zip") for entry_id in ("121", "156")}
    audit = build_audit()
    after = {entry_id: _sha256(ARCHIVE_ROOT / f"{entry_id}.zip") for entry_id in ("121", "156")}
    rows = {record["entry_id"]: record for record in audit["records"]}

    assert before == after
    for entry_id, phase_name in (("121", "CeO2"), ("156", "Cr2O3")):
        row = rows[entry_id]
        assert row["member_filename"] == f"{entry_id}.dat"
        assert row["text_decode_encoding"].startswith("rescue-")
        assert row["text_nul_byte_count"] == 22
        assert row["detected_content_family"] == "koalariet_style_pattern"
        assert row["model_content_present"] is True
        assert row["profile"]["expected_point_count"] == 5851
        assert row["profile"]["observed_intensity_count"] == 5851
        assert row["profile"]["point_count_consistency"] is True
        assert row["classification"] == "A_model_and_profile_recoverable"
        assert row["explicit_phase_block_count"] == 1
        assert phase_name in row["source_phase_names"]

    assert rows["144"]["explicit_phase_block_count"] == 1
    assert rows["155"]["explicit_phase_block_count"] == 1


def test_fullprof_and_other_model_evidence_remain_unresolved_when_profiles_mismatch() -> None:
    audit = build_audit()
    rows = {record["entry_id"]: record for record in audit["records"]}

    for entry_id in ("1", "81", "112", "144", "155"):
        row = rows[entry_id]
        assert row["model_evidence_present"] is True
        assert row["profile"]["point_count_consistency"] is False
        assert row["classification"] == "B_model_present_profile_unresolved"

    assert rows["81"]["reference_flags"]["fullprof"]["present"] is True
    assert rows["112"]["reference_flags"]["fullprof"]["present"] is True
    assert rows["90"]["reference_flags"]["cif"]["present"] is True
    assert rows["90"]["reference_flags"]["gsas"]["present"] is True


def test_padding_candidates_never_make_a_profile_recoverable() -> None:
    audit = build_audit()
    for row in audit["records"]:
        profile = row["profile"]
        if profile["padding_evidence"].get("trailing_zero_padding_candidate"):
            assert profile["profile_safely_recoverable"] is False
            assert "candidate only" in profile["padding_evidence"]["policy"]
    assert audit["counts"]["profile_safely_recoverable"] == 2
    assert audit["counts"]["still_unresolved"] == 28
