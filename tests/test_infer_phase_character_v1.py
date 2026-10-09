from __future__ import annotations

import json
from pathlib import Path

from scripts.infer_phase_character_v1 import (
    build_report,
    classify_powbase_record,
    classify_rruff_row,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_rruff_source_multiphase_evidence_is_positive() -> None:
    result = classify_rruff_row(
        {
            "sample_id": "R040043",
            "filename_sample_id": "R040043-1",
            "mineral": "Marialite",
            "structure_status": "ambiguous",
            "diffraction_status": "ambiguous_group",
            "candidate_count": "3",
        },
        {
            "diffraction_sample_description": "Powder, 78% marialite, 22% calcite, by weight",
            "phase_character_evidence": "quantitative_fraction",
        },
        None,
        None,
        None,
    )

    assert result["decision"] == "infer_multi_phase"
    assert result["proposed_phase_character"] == "multi_phase"
    assert result["phase_character_origin"] == "source"
    assert result["phase_character_method"] == "source_annotation"


def test_rruff_unique_structure_and_diffraction_do_not_infer_single_phase() -> None:
    result = classify_rruff_row(
        {
            "sample_id": "R040001",
            "filename_sample_id": "R040001-1",
            "mineral": "Andradite",
            "structure_status": "resolved",
            "diffraction_status": "resolved_candidate",
            "candidate_count": "1",
            "selected_cod_id": "9000239",
        },
        {
            "diffraction_sample_description": "Powder",
            "phase_character_evidence": "no explicit multi-phase evidence",
        },
        {
            "structure_resolution": {
                "resolution_level": "record",
                "resolution_status": "unique_bibliographic_match",
            }
        },
        {
            "radiation": {"radiation_class": "Cu-like"},
            "metrics": {
                "matched_fraction": 0.95,
                "median_abs_residual": 0.02,
            },
        },
        None,
    )

    assert result["decision"] == "retain_unknown"
    assert result["proposed_phase_character"] == "unknown"
    assert "phase-purity threshold" in result["decision_reason"]


def test_powbase_fullprof_rules_distinguish_single_and_two_allotropic_forms() -> None:
    dryrun = json.loads(
        (
            PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
        ).read_text(encoding="utf-8")
    )
    records = {record["entry_id"]: record for record in dryrun["records"]}

    single = classify_powbase_record(records["113"])
    assert single["decision"] == "infer_single_phase"
    assert single["powbase_phase_block_count"] == 1

    single = classify_powbase_record(records["124"])
    assert single["decision"] == "infer_single_phase"

    multi = classify_powbase_record(records["106"])
    assert multi["decision"] == "infer_multi_phase"
    assert multi["powbase_phase_block_count"] == 2


def test_phase_inference_report_has_all_target_records_and_expected_counts() -> None:
    report = build_report()
    assert report["summary"]["total_evaluated"] == 1108
    assert report["summary"]["source_counts"]["RRUFF"] == {
        "total": 1064,
        "infer_single_phase": 0,
        "infer_multi_phase": 13,
        "retain_unknown": 1051,
    }
    assert report["summary"]["source_counts"]["POWBASE"] == {
        "total": 44,
        "infer_single_phase": 2,
        "infer_multi_phase": 1,
        "retain_unknown": 41,
    }
    assert report["summary"]["hypothetical_production_distribution"] == {
        "single_phase": 857,
        "multi_phase": 54,
        "unknown": 2108,
        "total": 3019,
    }
    assert len(report["decisions"]) == 1108
    assert len({row["pattern_id"] for row in report["decisions"]}) == 1108
