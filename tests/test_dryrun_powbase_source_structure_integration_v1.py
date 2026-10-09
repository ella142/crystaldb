from __future__ import annotations

from scripts.dryrun_powbase_source_structure_integration_v1 import build_dryrun


def test_proposal_has_ten_structures_seven_relations_and_four_source_only_models() -> None:
    result = build_dryrun(check_mongo=False)

    assert len(result["structures_to_add"]) == 10
    assert len(result["relations_to_add"]) == 7
    assert len(result["source_evidence_only_models"]) == 4
    assert result["ambiguous_entries"][0]["entry_id"] == "106"
    assert result["ambiguous_entries"][1]["entry_id"] == "157"
    assert result["validation"]["orphan_relations"] == []
    assert result["validation"]["local_duplicate_ids"] == {
        "structure_ids": [],
        "relation_ids": [],
    }
    assert result["cif_validation"]["all_passed"] is True


def test_entry_116_wavelengths_and_entry_157_literal_are_preserved() -> None:
    result = build_dryrun(check_mongo=False)

    assert result["entry_116_wavelength_fix"]["explicit_wavelengths_angstrom"] == [
        1.54056,
        1.54439,
    ]
    assert result["entry_116_wavelength_fix"]["proposed_wavelength_values_angstrom"] == [
        1.54056,
        1.54439,
    ]
    assert result["entry_116_wavelength_fix"]["current_canonical_pattern"] == {
        "wavelength_angstrom": None,
        "wavelength_kalpha2_angstrom": None,
    }
    assert result["entry_157_literal_source_value"] == {
        "value": "51323",
        "numeric_parse": 51323.0,
        "preserved": True,
        "note": "Preserved as source evidence; no correction or normalization applied.",
    }


def test_proposed_counts_change_only_structures_and_relations() -> None:
    result = build_dryrun(check_mongo=False)
    delta = result["production_count_changes"]["delta"]

    assert delta["structures"] == 10
    assert delta["relations"] == 7
    assert all(
        delta[name] == 0
        for name in delta
        if name not in {"structures", "relations"}
    )
