from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "mappings" / "rescue_review_v1"

READY12_PATH = OUT_DIR / "rruff_rescue_ready_12_v1.csv"
VALIDATION67_PATH = OUT_DIR / "diffraction_needed_67_validation.csv"
DETAILS_PATH = OUT_DIR / "rruff_rescue_candidate_details_v1.csv"
SUMMARY_PATH = OUT_DIR / "rruff_rescue_summary_v1.csv"
HP35_PATH = OUT_DIR / "high_priority_35_diffraction_validation.csv"
XY160_PATH = OUT_DIR / "diffraction_needed_160_xy_audit.csv"

READY24_PATH = OUT_DIR / "rruff_rescue_ready_24_v1.csv"
AMBIGUOUS48_PATH = OUT_DIR / "rruff_ambiguous_48_v1.csv"
FINAL_MD_PATH = OUT_DIR / "rruff_rescue_review_final_v1.md"

NULL = "null"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: NULL if value is None or value == "" else str(value)
                    for key, value in row.items()
                }
            )


def text(row: dict[str, str] | None, key: str, default: str = NULL) -> str:
    if not row:
        return default
    value = row.get(key, "")
    return value if value not in (None, "") else default


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sort_cod_ids(values: Iterable[str]) -> list[str]:
    unique = {str(value) for value in values if value not in (None, "", NULL)}
    return sorted(unique, key=lambda value: (len(value), value))


def group_by(rows: Iterable[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[text(row, key)].append(row)
    return dict(grouped)


def sample_status_map(rows: Iterable[dict[str, str]]) -> dict[str, str]:
    grouped = group_by(rows, "sample_id")
    result: dict[str, str] = {}
    for sample_id, sample_rows in grouped.items():
        statuses = {text(row, "final_status") for row in sample_rows}
        if len(statuses) != 1:
            raise ValueError(f"sample {sample_id} has inconsistent final_status values: {statuses}")
        result[sample_id] = next(iter(statuses))
    return result


def detail_evidence(detail: dict[str, str] | None) -> dict[str, str]:
    if not detail:
        return {}
    keys = [
        "sample_id",
        "cod_id",
        "sample_mineral",
        "reference_structure_name",
        "candidate_mineral_name",
        "candidate_formula",
        "candidate_space_group",
        "candidate_parse_status",
        "name_support",
        "name_status",
        "chemistry_status",
        "chemistry_reason",
        "chemistry_comparison",
        "sg_status",
        "sg_equivalent",
        "sg_same_number",
        "space_group_comparison",
        "candidate_cell_a",
        "candidate_cell_b",
        "candidate_cell_c",
        "candidate_cell_alpha",
        "candidate_cell_beta",
        "candidate_cell_gamma",
        "cell_status",
        "candidate_cell_close",
        "strong_cell_close",
        "max_length_relative_difference",
        "max_angle_difference",
        "length_relative_differences",
        "angle_absolute_differences",
        "cif_file_path",
        "cif_file_exists",
        "candidate_role",
    ]
    return {key: text(detail, key) for key in keys}


def candidate_separability(row: dict[str, str] | None) -> str:
    if not row:
        return NULL
    values = {
        "available": text(row, "candidate_separability_available"),
        "pair_count": text(row, "candidate_separability_pair_count"),
        "best_candidate_cod_id": text(row, "best_candidate_cod_id"),
        "runner_up_candidate_cod_id": text(row, "runner_up_candidate_cod_id"),
        "weighted_residual_gap": text(row, "weighted_residual_gap"),
        "best_runner_up_separation_median_nearest_difference": text(
            row, "best_runner_up_separation_median_nearest_difference"
        ),
        "best_runner_up_separation_bin": text(row, "best_runner_up_separation_bin"),
    }
    if all(value == NULL for value in values.values()):
        return NULL
    return json_text(values)


def cell_evidence_from_detail(detail: dict[str, str] | None) -> str:
    if not detail:
        return NULL
    values = {
        "candidate_cell_close": text(detail, "candidate_cell_close"),
        "strong_cell_close": text(detail, "strong_cell_close"),
        "max_length_relative_difference": text(
            detail, "max_length_relative_difference"
        ),
        "max_angle_difference": text(detail, "max_angle_difference"),
        "length_relative_differences": text(detail, "length_relative_differences"),
        "angle_absolute_differences": text(detail, "angle_absolute_differences"),
    }
    return json_text(values)


def chemistry_evidence_from_detail(detail: dict[str, str] | None) -> str:
    if not detail:
        return NULL
    values = {
        "name_support": text(detail, "name_support"),
        "name_status": text(detail, "name_status"),
        "chemistry_status": text(detail, "chemistry_status"),
        "chemistry_reason": text(detail, "chemistry_reason"),
        "chemistry_comparison": text(detail, "chemistry_comparison"),
    }
    return json_text(values)


def space_group_evidence_from_detail(detail: dict[str, str] | None) -> str:
    if not detail:
        return NULL
    values = {
        "candidate_space_group": text(detail, "candidate_space_group"),
        "sg_status": text(detail, "sg_status"),
        "sg_equivalent": text(detail, "sg_equivalent"),
        "sg_same_number": text(detail, "sg_same_number"),
        "space_group_comparison": text(detail, "space_group_comparison"),
    }
    return json_text(values)


def support_ready_row(
    validation: dict[str, str],
    detail: dict[str, str] | None,
) -> dict[str, Any]:
    candidate_id = text(validation, "candidate_cod_id")
    sample_mineral = text(detail, "sample_mineral") if detail else NULL
    if sample_mineral == NULL and detail:
        sample_mineral = text(detail, "reference_structure_name")
    evidence = detail_evidence(detail)
    source_files = [
        "data/mappings/rescue_review_v1/diffraction_needed_67_validation.csv",
        "data/mappings/rescue_review_v1/rruff_rescue_candidate_details_v1.csv",
        text(validation, "cif_file_path"),
    ]
    return {
        "sample_id": text(validation, "sample_id"),
        "candidate_cod_id": candidate_id,
        "candidate_cod_ids": json_text([candidate_id]),
        "mineral": sample_mineral,
        "candidate_name": text(validation, "candidate_mineral_name"),
        "candidate_formula": text(validation, "candidate_formula"),
        "chemistry_status": text(validation, "prior_chemistry_status"),
        "chemistry_evidence": chemistry_evidence_from_detail(detail),
        "space_group_status": text(validation, "prior_space_group_status"),
        "space_group_evidence": space_group_evidence_from_detail(detail),
        "cell_status": text(validation, "prior_cell_status"),
        "cell_evidence": cell_evidence_from_detail(detail),
        "filename_sample_id": text(validation, "filename_sample_id"),
        "experimental_description": text(validation, "experimental_description"),
        "diffraction_status": text(validation, "candidate_diffraction_status"),
        "matched_count": text(validation, "matched_count"),
        "matched_fraction": text(validation, "matched_fraction"),
        "median_residual": text(validation, "median_abs_residual"),
        "weighted_residual": text(validation, "weighted_mean_abs_residual"),
        "max_residual": text(validation, "max_abs_residual"),
        "residual_slope": text(validation, "residual_slope"),
        "zero_shift": text(validation, "zero_shift"),
        "candidate_separability": candidate_separability(validation),
        "candidate_count_total": text(validation, "candidate_count_total"),
        "candidate_count_evaluable": text(validation, "candidate_count_evaluable"),
        "candidate_count_diffraction_compatible": text(
            validation, "candidate_count_diffraction_compatible"
        ),
        "final_status": "diffraction_supported_rescue",
        "final_category": "rescue_ready",
        "rescue_basis": "diffraction_supported_rescue",
        "reason": text(validation, "reason"),
        "provenance_source_files": ";".join(source_files),
        "cif_file_path": text(validation, "cif_file_path"),
        "candidate_evidence_json": json_text(evidence),
    }


def historical_ready_row(row: dict[str, str]) -> dict[str, Any]:
    source_files = text(row, "source_files")
    return {
        "sample_id": text(row, "sample_id"),
        "candidate_cod_id": text(row, "candidate_cod_id"),
        "candidate_cod_ids": json_text([text(row, "candidate_cod_id")]),
        "mineral": text(row, "mineral_name"),
        "candidate_name": text(row, "candidate_name"),
        "candidate_formula": text(row, "candidate_formula"),
        "chemistry_status": text(row, "chemistry_status"),
        "chemistry_evidence": json_text(
            {
                "chemistry_status": text(row, "chemistry_status"),
                "name_support": text(row, "name_support"),
                "reason": text(row, "reason"),
            }
        ),
        "space_group_status": text(row, "space_group_status"),
        "space_group_evidence": json_text(
            {
                "space_group_status": text(row, "space_group_status"),
                "reason": text(row, "reason"),
            }
        ),
        "cell_status": text(row, "cell_status"),
        "cell_evidence": json_text(
            {
                "length_difference": text(row, "cell_length_difference"),
                "angle_difference": text(row, "cell_angle_difference"),
                "cell_status": text(row, "cell_status"),
            }
        ),
        "filename_sample_id": NULL,
        "experimental_description": NULL,
        "diffraction_status": text(row, "diffraction_status"),
        "matched_count": text(row, "matched_count"),
        "matched_fraction": NULL,
        "median_residual": text(row, "median_residual"),
        "weighted_residual": text(row, "weighted_residual"),
        "max_residual": text(row, "max_residual"),
        "residual_slope": NULL,
        "zero_shift": text(row, "zero_shift"),
        "candidate_separability": NULL,
        "candidate_count_total": NULL,
        "candidate_count_evaluable": NULL,
        "candidate_count_diffraction_compatible": NULL,
        "final_status": text(row, "rescue_basis"),
        "final_category": "rescue_ready",
        "rescue_basis": text(row, "rescue_basis"),
        "reason": text(row, "reason"),
        "provenance_source_files": source_files,
        "cif_file_path": text(row, "cif_file_path"),
        "candidate_evidence_json": json_text(row),
    }


def ambiguous_metrics(rows: list[dict[str, str]]) -> str:
    fields = [
        "candidate_cod_id",
        "candidate_diffraction_status",
        "matched_count",
        "matched_fraction",
        "median_abs_residual",
        "weighted_mean_abs_residual",
        "max_abs_residual",
        "residual_slope",
        "zero_shift",
        "same_radiation_reference_n",
        "core_three_inside_p95",
        "all_six_inside_p95",
        "minimum_core_compatibility",
        "candidate_evaluation_error",
        "reason",
    ]
    records = []
    for row in sorted(rows, key=lambda item: (text(item, "candidate_cod_id"),)):
        records.append({field: text(row, field) for field in fields})
    return json_text(records)


def ambiguous_candidate_evidence(
    sample_id: str,
    validation_rows: list[dict[str, str]],
    details_by_key: dict[tuple[str, str], list[dict[str, str]]],
) -> str:
    records: list[dict[str, Any]] = []
    for validation in sorted(
        validation_rows, key=lambda item: text(item, "candidate_cod_id")
    ):
        candidate_id = text(validation, "candidate_cod_id")
        candidate_details = details_by_key.get((sample_id, candidate_id), [])
        if candidate_details:
            for detail in candidate_details:
                records.append(detail_evidence(detail))
        else:
            records.append(
                {
                    "sample_id": sample_id,
                    "cod_id": candidate_id,
                    "candidate_mineral_name": text(
                        validation, "candidate_mineral_name"
                    ),
                    "candidate_formula": text(validation, "candidate_formula"),
                    "cif_file_path": text(validation, "cif_file_path"),
                    "candidate_parse_status": NULL,
                }
            )
    return json_text(records)


def ambiguous_row(
    sample_id: str,
    validation_rows: list[dict[str, str]],
    summary_row: dict[str, str] | None,
    details_by_key: dict[tuple[str, str], list[dict[str, str]]],
) -> dict[str, Any]:
    first = validation_rows[0]
    compatible_rows = [
        row
        for row in validation_rows
        if text(row, "candidate_diffraction_status")
        == "diffraction_compatible"
    ]
    candidate_ids = sort_cod_ids(
        text(row, "candidate_cod_id") for row in compatible_rows
    )
    cif_paths = []
    for row in validation_rows:
        cif_path = text(row, "cif_file_path")
        if cif_path != NULL and cif_path not in cif_paths:
            cif_paths.append(cif_path)
    summary_row = summary_row or {}
    source_files = [
        "data/mappings/rescue_review_v1/diffraction_needed_67_validation.csv",
        "data/mappings/rescue_review_v1/rruff_rescue_candidate_details_v1.csv",
        *cif_paths,
    ]
    candidate_summary = {
        "candidate_count_total": text(first, "candidate_count_total"),
        "candidate_count_evaluable": text(first, "candidate_count_evaluable"),
        "candidate_count_diffraction_compatible": text(
            first, "candidate_count_diffraction_compatible"
        ),
    }
    mineral = text(summary_row, "sample_mineral")
    if mineral == NULL:
        mineral = text(summary_row, "reference_structure_name")
    return {
        "sample_id": sample_id,
        "candidate_cod_id": NULL,
        "candidate_cod_ids": json_text(candidate_ids),
        "mineral": mineral,
        "candidate_name": NULL,
        "candidate_formula": NULL,
        "chemistry_status": text(summary_row, "chemistry_status"),
        "chemistry_evidence": json_text(
            {
                "summary_chemistry_status": text(summary_row, "chemistry_status"),
                "failure_signals": text(summary_row, "failure_signals"),
                "dominant_failure_reason": text(
                    summary_row, "dominant_failure_reason"
                ),
            }
        ),
        "space_group_status": text(summary_row, "sg_status"),
        "space_group_evidence": json_text(
            {
                "summary_sg_status": text(summary_row, "sg_status"),
                "failure_signals": text(summary_row, "failure_signals"),
                "failure_note": text(summary_row, "failure_note"),
            }
        ),
        "cell_status": text(summary_row, "cell_status"),
        "cell_evidence": json_text(
            {
                "summary_cell_status": text(summary_row, "cell_status"),
                "failure_note": text(summary_row, "failure_note"),
                "rescue_note": text(summary_row, "rescue_note"),
            }
        ),
        "filename_sample_id": text(first, "filename_sample_id"),
        "experimental_description": text(first, "experimental_description"),
        "diffraction_status": "multiple_diffraction_compatible_candidates",
        "matched_count": NULL,
        "matched_fraction": NULL,
        "median_residual": NULL,
        "weighted_residual": NULL,
        "max_residual": NULL,
        "residual_slope": NULL,
        "zero_shift": NULL,
        "candidate_separability": candidate_separability(first),
        "candidate_count_total": candidate_summary["candidate_count_total"],
        "candidate_count_evaluable": candidate_summary["candidate_count_evaluable"],
        "candidate_count_diffraction_compatible": candidate_summary[
            "candidate_count_diffraction_compatible"
        ],
        "final_status": "multiple_diffraction_compatible_candidates",
        "final_category": "ambiguous",
        "rescue_basis": "multiple_diffraction_compatible_candidates",
        "reason": text(first, "reason"),
        "provenance_source_files": ";".join(source_files),
        "cif_file_path": NULL,
        "candidate_metrics_json": ambiguous_metrics(validation_rows),
        "candidate_evidence_json": ambiguous_candidate_evidence(
            sample_id, validation_rows, details_by_key
        ),
    }


READY_FIELDS = [
    "sample_id",
    "candidate_cod_id",
    "candidate_cod_ids",
    "mineral",
    "candidate_name",
    "candidate_formula",
    "chemistry_status",
    "chemistry_evidence",
    "space_group_status",
    "space_group_evidence",
    "cell_status",
    "cell_evidence",
    "filename_sample_id",
    "experimental_description",
    "diffraction_status",
    "matched_count",
    "matched_fraction",
    "median_residual",
    "weighted_residual",
    "max_residual",
    "residual_slope",
    "zero_shift",
    "candidate_separability",
    "candidate_count_total",
    "candidate_count_evaluable",
    "candidate_count_diffraction_compatible",
    "final_status",
    "final_category",
    "rescue_basis",
    "reason",
    "provenance_source_files",
    "cif_file_path",
    "candidate_evidence_json",
]

AMBIGUOUS_FIELDS = [
    "sample_id",
    "candidate_cod_id",
    "candidate_cod_ids",
    "mineral",
    "candidate_name",
    "candidate_formula",
    "chemistry_status",
    "chemistry_evidence",
    "space_group_status",
    "space_group_evidence",
    "cell_status",
    "cell_evidence",
    "filename_sample_id",
    "experimental_description",
    "diffraction_status",
    "matched_count",
    "matched_fraction",
    "median_residual",
    "weighted_residual",
    "max_residual",
    "residual_slope",
    "zero_shift",
    "candidate_separability",
    "candidate_count_total",
    "candidate_count_evaluable",
    "candidate_count_diffraction_compatible",
    "final_status",
    "final_category",
    "rescue_basis",
    "reason",
    "provenance_source_files",
    "cif_file_path",
    "candidate_metrics_json",
    "candidate_evidence_json",
]


def build_final_summary(
    *,
    all_ids: set[str],
    ready_ids: set[str],
    ambiguous_ids: set[str],
    inconclusive_ids: set[str],
    no_validation_ids: set[str],
    low_priority_ids: set[str],
    not_rescuable_ids: set[str],
) -> str:
    categories = [
        ("rescue_ready", ready_ids),
        ("ambiguous", ambiguous_ids),
        ("inconclusive", inconclusive_ids),
        ("no_experimental_validation", no_validation_ids),
        ("low_priority_review", low_priority_ids),
        ("not_rescuable", not_rescuable_ids),
    ]
    counts = {name: len(ids) for name, ids in categories}
    union = set().union(*(ids for _, ids in categories))
    disjoint = sum(counts.values()) == len(union)
    validation = (
        len(all_ids) == 304
        and counts
        == {
            "rescue_ready": 24,
            "ambiguous": 48,
            "inconclusive": 9,
            "no_experimental_validation": 115,
            "low_priority_review": 56,
            "not_rescuable": 52,
        }
        and sum(counts.values()) == 304
        and union == all_ids
        and disjoint
    )
    validation_text = "PASS" if validation else "FAIL"
    category_table = "\n".join(
        f"| `{name}` | {counts[name]} |" for name, _ in categories
    )
    source_files = [
        "data/mappings/rescue_review_v1/rruff_rescue_ready_12_v1.csv",
        "data/mappings/rescue_review_v1/diffraction_needed_67_validation.csv",
        "data/mappings/rescue_review_v1/rruff_rescue_candidate_details_v1.csv",
        "data/mappings/rescue_review_v1/rruff_rescue_summary_v1.csv",
        "data/mappings/rescue_review_v1/high_priority_35_diffraction_validation.csv",
        "data/mappings/rescue_review_v1/diffraction_needed_160_xy_audit.csv",
    ]
    source_list = "\n".join(f"- `{path}`" for path in source_files)
    return f"""# RRUFF Rescue/Review Final v1

This is an organization-only manifest. It reads existing rescue/review outputs and
does not search COD, download CIF files, rerun diffraction, recalculate metrics, or
modify historical CrystalDB data.

## Final closure

| category | sample count |
|---|---:|
{category_table}
| **total** | **{sum(counts.values())}** |

The six categories are checked as a disjoint union of the 304 unique RRUFF sample
IDs. `sum(category counts) = {sum(counts.values())}` and `union size = {len(union)}`.

`validation = {validation_text}`

## Deliverables

- `rruff_rescue_ready_24_v1.csv`: {counts["rescue_ready"]} rows, consisting of the
  original 12 rescue-ready rows plus 12 existing `diffraction_supported_rescue`
  rows from the 67-sample validation output.
- `rruff_ambiguous_48_v1.csv`: {counts["ambiguous"]} rows, one row per sample.
  No candidate is selected as a representative; `candidate_cod_ids`,
  `candidate_metrics_json`, and `candidate_evidence_json` retain all compatible
  candidates and their existing values.

The ready CSV preserves the original structure-only row with diffraction fields as
`null`. It also preserves the existing solid-solution/substitution status where
present. For ambiguous samples, scalar diffraction metric columns remain `null`
because selecting one candidate would reinterpret the result; all candidate-level
metrics are retained in `candidate_metrics_json`.

## Gemmi compatibility record

The initial diffraction run recorded 6 candidate-level runtime errors associated
with Gemmi 0.7.5 API compatibility:

- COD `1011221`: samples `R050035`, `R050056`, `R050233`, `R050489`, `R060532`
- COD `9017229`: sample `R060060`

The existing validation output was subsequently read after applying an in-memory
runtime compatibility wrapper for the frozen engine. The wrapper only supplied the
required explicit space-group setting/fallback at the API boundary. The diffraction
algorithm, calibration, and thresholds were not changed. This final organization
step did not rerun diffraction.

## Provenance

The exact input files used for the closure and manifests were:

{source_list}

The historical 12-row ready manifest carries its own upstream provenance, including
the high-priority review and candidate-detail sources. The 304-row closure uses the
summary file for the low-priority and not-rescuable sets, the 67-row validation for
the new rescue-ready/ambiguous/inconclusive sets, the 35-row validation for the
remaining high-priority inconclusive/no-validation sets, and the 160-row XY audit
for the 93 calculated-only samples.

Protected artifacts were not modified: the original 807 curated data, the 177-row
DIF-outside final manifest, v2/v3 outputs, MongoDB, formal CrystalDB, and the paper.

## Final values

```text
rescue_ready_rows = {counts["rescue_ready"]}
ambiguous_samples = {counts["ambiguous"]}
final_total = {sum(counts.values())}
validation = {validation_text}
```
"""


def main() -> None:
    ready12 = read_csv(READY12_PATH)
    validation67 = read_csv(VALIDATION67_PATH)
    details = read_csv(DETAILS_PATH)
    summary304 = read_csv(SUMMARY_PATH)
    hp35 = read_csv(HP35_PATH)
    xy160 = read_csv(XY160_PATH)

    if len(ready12) != 12 or len({text(row, "sample_id") for row in ready12}) != 12:
        raise ValueError("rruff_rescue_ready_12_v1.csv must contain 12 unique rows")
    validation67_by_sample = group_by(validation67, "sample_id")
    if len(validation67_by_sample) != 67:
        raise ValueError(
            f"diffraction_needed_67_validation.csv has {len(validation67_by_sample)} "
            "unique samples, expected 67"
        )
    details_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for detail in details:
        details_by_key[(text(detail, "sample_id"), text(detail, "cod_id"))].append(
            detail
        )
    summary_by_sample = {
        text(row, "sample_id"): row for row in summary304
    }
    all_ids = set(summary_by_sample)
    if len(all_ids) != 304:
        raise ValueError(f"summary file has {len(all_ids)} unique samples, expected 304")

    validation_statuses = sample_status_map(validation67)
    support_ids = {
        sample_id
        for sample_id, status in validation_statuses.items()
        if status == "diffraction_supported_rescue"
    }
    ambiguous_ids = {
        sample_id
        for sample_id, status in validation_statuses.items()
        if status == "multiple_diffraction_compatible_candidates"
    }
    current_inconclusive_ids = {
        sample_id
        for sample_id, status in validation_statuses.items()
        if status == "diffraction_inconclusive"
    }
    if (len(support_ids), len(ambiguous_ids), len(current_inconclusive_ids)) != (
        12,
        48,
        7,
    ):
        raise ValueError(
            "unexpected 67-sample status counts: "
            f"{len(support_ids)}, {len(ambiguous_ids)}, {len(current_inconclusive_ids)}"
        )

    ready_rows: list[dict[str, Any]] = [
        historical_ready_row(row) for row in ready12
    ]
    for sample_id in sorted(support_ids):
        sample_rows = validation67_by_sample[sample_id]
        compatible_rows = [
            row
            for row in sample_rows
            if text(row, "candidate_diffraction_status")
            == "diffraction_compatible"
        ]
        if len(compatible_rows) != 1:
            raise ValueError(
                f"support sample {sample_id} has {len(compatible_rows)} "
                "diffraction-compatible candidates"
            )
        validation_row = compatible_rows[0]
        candidate_id = text(validation_row, "candidate_cod_id")
        candidate_detail_rows = details_by_key.get((sample_id, candidate_id), [])
        detail = candidate_detail_rows[0] if candidate_detail_rows else None
        ready_rows.append(support_ready_row(validation_row, detail))

    ready_ids = {text(row, "sample_id") for row in ready_rows}
    if len(ready_rows) != 24 or len(ready_ids) != 24:
        raise ValueError(
            f"ready manifest has {len(ready_rows)} rows and {len(ready_ids)} unique samples"
        )

    ambiguous_rows = [
        ambiguous_row(
            sample_id,
            validation67_by_sample[sample_id],
            summary_by_sample.get(sample_id),
            details_by_key,
        )
        for sample_id in sorted(ambiguous_ids)
    ]
    if len(ambiguous_rows) != 48:
        raise ValueError(f"ambiguous manifest has {len(ambiguous_rows)} rows")

    hp35_statuses = sample_status_map(hp35)
    hp35_inconclusive_ids = {
        sample_id
        for sample_id, status in hp35_statuses.items()
        if status == "diffraction_inconclusive"
    }
    hp35_no_validation_ids = {
        sample_id
        for sample_id, status in hp35_statuses.items()
        if status == "no_diffraction_available"
    }
    xy_calculated_only_ids = {
        text(row, "sample_id")
        for row in xy160
        if text(row, "xy_origin_status") == "calculated_only"
    }
    if len(hp35_inconclusive_ids) != 2:
        raise ValueError(
            f"high-priority inconclusive count is {len(hp35_inconclusive_ids)}, expected 2"
        )
    if len(hp35_no_validation_ids) != 22:
        raise ValueError(
            f"high-priority no-validation count is {len(hp35_no_validation_ids)}, expected 22"
        )
    if len(xy_calculated_only_ids) != 93:
        raise ValueError(
            f"calculated-only count is {len(xy_calculated_only_ids)}, expected 93"
        )

    inconclusive_ids = current_inconclusive_ids | hp35_inconclusive_ids
    no_validation_ids = xy_calculated_only_ids | hp35_no_validation_ids
    low_priority_ids = {
        text(row, "sample_id")
        for row in summary304
        if text(row, "rescue_category") == "low_priority_review"
    }
    not_rescuable_ids = {
        text(row, "sample_id")
        for row in summary304
        if text(row, "rescue_category") == "not_rescuable_with_current_evidence"
    }

    categories = [
        ready_ids,
        ambiguous_ids,
        inconclusive_ids,
        no_validation_ids,
        low_priority_ids,
        not_rescuable_ids,
    ]
    if any(left & right for index, left in enumerate(categories) for right in categories[index + 1 :]):
        raise ValueError("final categories overlap")
    if set().union(*categories) != all_ids:
        missing = sorted(all_ids - set().union(*categories))
        extra = sorted(set().union(*categories) - all_ids)
        raise ValueError(f"final categories do not close 304; missing={missing}, extra={extra}")

    write_csv(READY24_PATH, READY_FIELDS, ready_rows)
    write_csv(AMBIGUOUS48_PATH, AMBIGUOUS_FIELDS, ambiguous_rows)
    FINAL_MD_PATH.write_text(
        build_final_summary(
            all_ids=all_ids,
            ready_ids=ready_ids,
            ambiguous_ids=ambiguous_ids,
            inconclusive_ids=inconclusive_ids,
            no_validation_ids=no_validation_ids,
            low_priority_ids=low_priority_ids,
            not_rescuable_ids=not_rescuable_ids,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "rescue_ready_rows": len(ready_rows),
                "ambiguous_samples": len(ambiguous_rows),
                "final_total": len(all_ids),
                "validation": "PASS",
                "inconclusive": len(inconclusive_ids),
                "no_experimental_validation": len(no_validation_ids),
                "low_priority_review": len(low_priority_ids),
                "not_rescuable": len(not_rescuable_ids),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
