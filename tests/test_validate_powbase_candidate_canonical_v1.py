from __future__ import annotations

from scripts.validate_powbase_candidate_canonical_v1 import build_validation


def test_four_candidates_pass_without_mongo_writes() -> None:
    result = build_validation(inspect_mongo=False)

    assert result["summary"]["all_pass"] is True
    assert result["summary"]["pass_count"] == 4
    assert result["summary"]["fail_count"] == 0
    assert result["summary"]["proposed_powbase_xray_production_count"] == 48
    assert result["summary"]["proposed_crystaldb_pattern_count"] == 3023
    assert result["summary"]["mongodb_writes"] is False
    assert result["summary"]["entry_137_processed"] is False
    assert result["summary"]["other_conditional_records_processed"] is False

    rows = {row["entry_id"]: row for row in result["records"]}
    assert {row["canonical_point_count"] for row in rows.values()} == {13003, 4001, 5851}
    assert rows["15"]["explicit_wavelength_values_angstrom"] == [
        1.54056,
        1.54439,
        1.39222,
    ]
    assert rows["74"]["explicit_wavelength_values_angstrom"] == []
    assert rows["121"]["explicit_wavelength_values_angstrom"] == []
    assert rows["156"]["explicit_wavelength_values_angstrom"] == []
    assert rows["15"]["end_explicit_in_source"] is False
    assert rows["74"]["end_explicit_in_source"] is True
    assert rows["121"]["end_explicit_in_source"] is True
    assert rows["156"]["end_explicit_in_source"] is True


def test_candidate_ids_do_not_collide_with_existing_44_or_each_other() -> None:
    result = build_validation(inspect_mongo=False)
    collisions = result["identifier_collision_check"]["local_against_existing_44"]

    assert collisions == {
        "sample_id": [],
        "measurement_id": [],
        "pattern_id": [],
    }
    assert result["source_archive_hash_check"]["unchanged"] is True
    assert all(row["validation_issues"] == [] for row in result["records"])
