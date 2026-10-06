from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crystaldb.cif_parser import parse_cif


INPUT_ROOT = PROJECT_ROOT / "data" / "mappings" / "rescue_review_v1"
SUMMARY_FILE = INPUT_ROOT / "rruff_rescue_summary_v1.csv"
DETAIL_FILE = INPUT_ROOT / "rruff_rescue_candidate_details_v1.csv"
OUTPUT_CSV = INPUT_ROOT / "high_priority_36_review.csv"
OUTPUT_MD = INPUT_ROOT / "high_priority_36_review.md"

MAX_LENGTH_DIFFERENCE = 0.02
MAX_ANGLE_DIFFERENCE = 1.0

# The legacy chemistry comparator intentionally returns null for grouped
# formulas. These 14 exact composition equivalences were checked manually
# from the RRUFF ideal formula and the local CIF formula for this 36-sample
# review only.
MANUAL_EXACT_CHEMISTRY: dict[tuple[str, str], str] = {
    ("R060018", "9008253"):
        "Cu(SO4).5H2O = Cu H10 O9 S",
    ("R060254", "9004913"):
        "Ba(UO2)2(AsO4)2.10H2O = As2 Ba H20 O22 U2",
    ("R060456", "9004736"):
        "Mg2(PO4)F x5 = F5 Mg10 O20 P5",
    ("R060624", "9011241"):
        "NaVO3 = Na O3 V",
    ("R070093", "9008075"):
        "Pb13CuSb7S24 x0.25 = Cu0.25 Pb3.25 S6 Sb1.75",
    ("R070607", "9008134"):
        "NaCa2Si3O8(OH) = Ca2 H Na O9 Si3",
    ("R080097", "9000212"):
        "Mn9(AsO4)2(AsO3)(OH)9.2H2O = As3 H13 Mn9 O22",
    ("R080124", "9004354"):
        "Cu3PbTeO6(OH)2 = Cu3 H2 O8 Pb Te",
    ("R090038", "9011792"):
        "PbAl2(CO3)2(OH)4.H2O = C2 H6 Al2 O11 Pb",
    ("R090052", "9004629"):
        "Cu(UO2)3(SeO3)2O2.8H2O = Cu H16 O22 Se2 U3",
    ("R100004", "9014374"):
        "Pb3AlF9.H2O = Al F9 H2 O Pb3",
    ("R120112", "9004394"):
        "PbCu(VO4)(OH) = Cu H O5 Pb V",
    ("R120155", "9015768"):
        "CuCl2.2NH3 = Cl2 Cu H6 N2",
    ("R140558", "9007451"):
        "FeAl2(PO4)2(OH)2 = Al2 Fe H2 O10 P2",
}


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value)


def _name_support(row: dict[str, Any]) -> str:
    sample = _bool(row.get("sample_name_match"))
    reference = _bool(row.get("reference_name_match"))
    if sample and reference:
        return "sample_and_reference_name"
    if sample:
        return "sample_name"
    if reference:
        return "reference_name"
    return "none"


def _chemistry_status(row: dict[str, Any]) -> str:
    raw = row.get("chemistry_compatible")
    if str(raw).strip().lower() == "true":
        return "compatible"
    if str(raw).strip().lower() == "false":
        return "incompatible"
    if (row.get("sample_id"), row.get("cod_id")) in MANUAL_EXACT_CHEMISTRY:
        return "compatible"
    # The existing comparator returned null for the complex formula cases.
    # Per the review request, preserve them as review rather than False.
    return "solid_solution_or_substitution_review"


def _chemistry_reason(row: dict[str, Any]) -> str:
    key = (row.get("sample_id"), row.get("cod_id"))
    if key in MANUAL_EXACT_CHEMISTRY:
        return "manual_exact_formula_equivalence"
    return str(row.get("chemistry_reason") or "")


def _chemistry_evidence(row: dict[str, Any]) -> str:
    key = (row.get("sample_id"), row.get("cod_id"))
    if key in MANUAL_EXACT_CHEMISTRY:
        return MANUAL_EXACT_CHEMISTRY[key]
    if str(row.get("chemistry_compatible")).strip().lower() == "true":
        return "existing comparator: same_composition_ratio"
    if str(row.get("chemistry_compatible")).strip().lower() == "false":
        return str(row.get("chemistry_reason") or "existing comparator: incompatible")
    return (
        "existing comparator returned null; formula requires "
        "solid-solution/substitution or manual chemistry review"
    )


def _space_group_status(row: dict[str, Any]) -> str:
    raw = row.get("sg_equivalent")
    if str(raw).strip().lower() == "true":
        return "equivalent"
    if str(raw).strip().lower() == "false":
        return "mismatch"
    return "unknown"


def _cell_status(row: dict[str, Any]) -> str:
    length = _float(row.get("max_length_relative_difference"))
    angle = _float(row.get("max_angle_difference"))
    if length is None or angle is None:
        return "incomplete"
    length_ok = length <= MAX_LENGTH_DIFFERENCE
    angle_ok = angle <= MAX_ANGLE_DIFFERENCE
    if length_ok and angle_ok:
        return "pass"
    if not length_ok and not angle_ok:
        return "exceeds_length_2pct_and_angle_1deg"
    if not length_ok:
        return "exceeds_length_2pct"
    return "exceeds_angle_1deg"


def _local_cif_path(row: dict[str, Any]) -> Path:
    relative = str(row.get("cif_file_path") or "").replace("/", "\\")
    return PROJECT_ROOT / relative


def _parse_local_cif(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    path = _local_cif_path(row)
    if not path.is_file():
        return "missing", {}
    try:
        return "ok", parse_cif(path)
    except Exception as exc:
        return f"parse_error:{type(exc).__name__}", {}


def _candidate_check_status(
    name_support: str,
    chemistry_status: str,
    space_group_status: str,
    cell_status: str,
    local_parse_status: str,
) -> str:
    if local_parse_status != "ok":
        return "local_cif_unusable"
    if name_support == "none":
        return "name_not_supported"
    if chemistry_status == "incompatible":
        return "chemistry_incompatible"
    if space_group_status == "mismatch":
        return "space_group_mismatch"
    if space_group_status == "unknown":
        return "space_group_unknown"
    if cell_status != "pass" and chemistry_status == (
        "solid_solution_or_substitution_review"
    ):
        return "chemistry_review_and_cell_threshold"
    if cell_status != "pass":
        return "cell_threshold_failure"
    if chemistry_status == "solid_solution_or_substitution_review":
        return "chemistry_review"
    return "passes_current_structure_conditions"


def _reason(
    row: dict[str, Any],
    name_support: str,
    chemistry_status: str,
    space_group_status: str,
    cell_status: str,
    local_parse_status: str,
    chemistry_reason: str,
    chemistry_evidence: str,
) -> str:
    parts: list[str] = []
    if name_support != "none":
        parts.append(f"name support={name_support}")
    else:
        parts.append("no sample/reference name support")

    if chemistry_status == "compatible":
        parts.append(f"chemistry clearly compatible ({chemistry_evidence})")
    elif chemistry_status == "incompatible":
        parts.append("chemistry explicitly incompatible")
    else:
        parts.append(
            "chemistry requires solid-solution/substitution review "
            f"({chemistry_reason or 'existing comparator returned null'}; "
            f"{chemistry_evidence})"
        )

    if space_group_status == "equivalent":
        parts.append("space group equivalent")
    elif space_group_status == "mismatch":
        parts.append("space group explicitly mismatched")
    else:
        parts.append("space group cannot be compared")

    length = _float(row.get("max_length_relative_difference"))
    angle = _float(row.get("max_angle_difference"))
    if length is None or angle is None:
        parts.append("cell comparison incomplete")
    elif cell_status == "pass":
        parts.append(
            f"cell pass (length={length:.4%} <= 2%, angle={angle:.4f}° <= 1°)"
        )
    else:
        parts.append(
            f"cell exceeds current limit "
            f"(length={length:.4%}, angle={angle:.4f}°; "
            "limits 2% and 1°)"
        )

    if local_parse_status != "ok":
        parts.append(f"local CIF={local_parse_status}")
    return "; ".join(parts)


def _strict_pass(
    name_support: str,
    chemistry_status: str,
    space_group_status: str,
    cell_status: str,
    local_parse_status: str,
) -> bool:
    return (
        name_support != "none"
        and chemistry_status == "compatible"
        and space_group_status == "equivalent"
        and cell_status == "pass"
        and local_parse_status == "ok"
    )


def _diffraction_candidate(
    row: dict[str, Any],
    name_support: str,
    chemistry_status: str,
    space_group_status: str,
    cell_status: str,
    local_parse_status: str,
) -> bool:
    """Whether existing evidence justifies sending the case to diffraction."""

    if local_parse_status != "ok" or name_support == "none":
        return False
    if space_group_status != "equivalent":
        return False
    if not _bool(row.get("broad_cell_match")):
        return False
    if chemistry_status not in {
        "compatible",
        "solid_solution_or_substitution_review",
    }:
        return False
    # A strict pass is already structurally ready. Every other broad,
    # name-supported candidate needs experimental validation here.
    return not (
        chemistry_status == "compatible"
        and cell_status == "pass"
    )


def _write_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "sample_id",
        "candidate_cod_id",
        "candidate_mineral_name",
        "candidate_formula",
        "ideal_chemistry",
        "metadata_ideal_chemistry",
        "cif_file_path",
        "local_cif_parse_status",
        "name_support",
        "sample_name_match",
        "reference_name_match",
        "chemistry_status",
        "chemistry_reason",
        "chemistry_evidence",
        "existing_chemistry_reason",
        "space_group_status",
        "cell_status",
        "max_length_relative_difference",
        "max_angle_difference",
        "candidate_check_status",
        "candidate_count_total",
        "candidate_count_passing",
        "candidate_count_reviewable",
        "final_status",
        "solid_solution_or_substitution_review",
        "reason",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(
    sample_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    summary: dict[str, int],
) -> None:
    candidate_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        candidate_by_sample[row["sample_id"]].append(row)

    lines = [
        "# High-Priority Rescue Review: 36 RRUFF Samples",
        "",
        "## Scope",
        "",
        "This review is restricted to the 36 samples already labeled "
        "`high_priority_rescue` in `rruff_rescue_summary_v1.csv`.",
        "It uses the existing rescue CSV files and local CIF files only.",
        "No COD search, CIF download, diffraction matching, MongoDB write, "
        "or old mapping modification was performed.",
        "",
        "The current structure test is:",
        "",
        "- name support from the sample or reference name;",
        "- chemistry clearly compatible, or explicitly retained for "
        "solid-solution/substitution review;",
        "- equivalent space group;",
        "- max cell-length difference <= 2%;",
        "- max cell-angle difference <= 1°.",
        "",
        "For `structurally_ready_for_rescue`, chemistry must be explicitly "
        "compatible. A null result from the existing chemistry comparator "
        "is not silently treated as compatible; only the exact formula "
        "equivalences listed in the CSV were manually promoted to "
        "`compatible`.",
        "",
        "## Summary",
        "",
        "| Metric | Samples |",
        "|---|---:|",
        f"| 36 total | {summary['total']} |",
        f"| structurally_ready_for_rescue | "
        f"{summary['structurally_ready_for_rescue']} |",
        f"| multiple_valid_candidates | "
        f"{summary['multiple_valid_candidates']} |",
        f"| diffraction_validation_needed | "
        f"{summary['diffraction_validation_needed']} |",
        f"| not_rescuable | {summary['not_rescuable']} |",
        f"| solid_solution_or_substitution_review | "
        f"{summary['solid_solution_or_substitution_review']} |",
        "",
        "The `solid_solution_or_substitution_review` count is a sample count. "
        "It includes samples with at least one candidate whose chemistry "
        "was not an exact composition match and therefore still needs "
        "solid-solution/substitution or manual chemistry review. It is a "
        "review flag, not a claim that every such sample has a confirmed "
        "solid solution.",
        "",
        "The legacy comparator returned null for grouped or otherwise complex "
        "formulas. Fourteen exact formula equivalences were manually checked "
        "for this 36-sample scope and recorded in the CSV "
        "`chemistry_evidence` column; no general chemistry search or new "
        "candidate retrieval was performed.",
        "",
        "## Sample Results",
        "",
        "| sample_id | candidate_cod_id(s) | passing | final_status | chemistry review | reason |",
        "|---|---|---:|---|---|---|",
    ]

    for sample in sample_rows:
        candidates = candidate_by_sample[sample["sample_id"]]
        ids = ", ".join(row["candidate_cod_id"] for row in candidates)
        chemistry_review = (
            "yes"
            if sample["solid_solution_or_substitution_review"] == "true"
            else "no"
        )
        reason = sample["reason"].replace("|", "\\|")
        lines.append(
            f"| {sample['sample_id']} | {ids} | "
            f"{sample['candidate_count_passing']} | "
            f"`{sample['final_status']}` | {chemistry_review} | "
            f"{reason} |"
        )

    lines.extend(
        [
            "",
            "## Candidate-Level Notes",
            "",
            "| sample_id | COD ID | name | chemistry | SG | cell | check |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in candidate_rows:
        reason = row["reason"].replace("|", "\\|")
        lines.append(
            f"| {row['sample_id']} | {row['candidate_cod_id']} | "
            f"{row['name_support']} | {row['chemistry_status']} | "
            f"{row['space_group_status']} | {row['cell_status']} | "
            f"{row['candidate_check_status']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "`structurally_ready_for_rescue` only means that the existing "
            "structure evidence satisfies the stated checks; it does not "
            "promote a final record-level resolution or modify the original "
            "807-profile dataset.",
            "",
            "The CSV contains one row per existing sample-CIF candidate. "
            "`candidate_count_passing` is repeated for all rows belonging "
            "to the same sample and counts only strict passes with explicit "
            "chemistry compatibility.",
            "",
            f"Generated at {datetime.now(timezone.utc).isoformat()}.",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    with SUMMARY_FILE.open(encoding="utf-8-sig", newline="") as handle:
        summary_rows = list(csv.DictReader(handle))
    with DETAIL_FILE.open(encoding="utf-8-sig", newline="") as handle:
        detail_rows = list(csv.DictReader(handle))

    high_priority = [
        row
        for row in summary_rows
        if row.get("rescue_category") == "high_priority_rescue"
    ]
    if len(high_priority) != 36:
        raise RuntimeError(
            f"Expected 36 high_priority_rescue samples, found {len(high_priority)}"
        )

    target_ids = {row["sample_id"] for row in high_priority}
    candidates = [
        row for row in detail_rows if row.get("sample_id") in target_ids
    ]
    candidates.sort(key=lambda row: (row["sample_id"], row["cod_id"]))

    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_sample[row["sample_id"]].append(row)

    enriched_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        name_support = _name_support(row)
        chemistry_status = _chemistry_status(row)
        chemistry_reason = _chemistry_reason(row)
        chemistry_evidence = _chemistry_evidence(row)
        space_group_status = _space_group_status(row)
        cell_status = _cell_status(row)
        local_parse_status, parsed_cif = _parse_local_cif(row)
        strict_pass = _strict_pass(
            name_support,
            chemistry_status,
            space_group_status,
            cell_status,
            local_parse_status,
        )
        diffraction_candidate = _diffraction_candidate(
            row,
            name_support,
            chemistry_status,
            space_group_status,
            cell_status,
            local_parse_status,
        )
        enriched = {
            "sample_id": row["sample_id"],
            "candidate_cod_id": row["cod_id"],
            "candidate_mineral_name": row.get("candidate_mineral_name"),
            "candidate_formula": row.get("candidate_formula"),
            "ideal_chemistry": (
                row.get("ideal_chemistry")
                or row.get("metadata_ideal_chemistry")
            ),
            "metadata_ideal_chemistry": row.get(
                "metadata_ideal_chemistry"
            ),
            "cif_file_path": row.get("cif_file_path"),
            "local_cif_parse_status": local_parse_status,
            "name_support": name_support,
            "sample_name_match": row.get("sample_name_match"),
            "reference_name_match": row.get("reference_name_match"),
            "chemistry_status": chemistry_status,
            "chemistry_reason": chemistry_reason,
            "chemistry_evidence": chemistry_evidence,
            "existing_chemistry_reason": row.get("chemistry_reason"),
            "space_group_status": space_group_status,
            "cell_status": cell_status,
            "max_length_relative_difference": row.get(
                "max_length_relative_difference"
            ),
            "max_angle_difference": row.get("max_angle_difference"),
            "candidate_check_status": _candidate_check_status(
                name_support,
                chemistry_status,
                space_group_status,
                cell_status,
                local_parse_status,
            ),
            "_strict_pass": strict_pass,
            "_diffraction_candidate": diffraction_candidate,
            "_parsed_cif_formula": parsed_cif.get("formula"),
            "_parsed_cif_space_group": parsed_cif.get("space_group"),
            "_parsed_cif_cell": parsed_cif.get("cell_parameters"),
            "reason": _reason(
                row,
                name_support,
                chemistry_status,
                space_group_status,
                cell_status,
                local_parse_status,
                chemistry_reason,
                chemistry_evidence,
            ),
        }
        enriched_by_sample[row["sample_id"]].append(enriched)

    final_sample_rows: list[dict[str, Any]] = []
    output_candidate_rows: list[dict[str, Any]] = []
    final_counts: Counter[str] = Counter()
    solid_solution_count = 0

    for sample in sorted(high_priority, key=lambda row: row["sample_id"]):
        sample_id = sample["sample_id"]
        rows = enriched_by_sample[sample_id]
        strict_rows = [row for row in rows if row["_strict_pass"]]
        review_rows = [
            row
            for row in rows
            if row["chemistry_status"]
            == "solid_solution_or_substitution_review"
        ]
        diffraction_rows = [
            row for row in rows if row["_diffraction_candidate"]
        ]

        if len(strict_rows) == 1:
            final_status = "structurally_ready_for_rescue"
        elif len(strict_rows) > 1:
            final_status = "multiple_valid_candidates"
        elif diffraction_rows:
            final_status = "diffraction_validation_needed"
        else:
            final_status = "not_rescuable"

        final_counts[final_status] += 1
        if review_rows:
            solid_solution_count += 1

        if strict_rows:
            reason = (
                f"{len(strict_rows)} candidate passes all current "
                "structure conditions."
            )
        elif diffraction_rows:
            reason = (
                "No strict pass. At least one candidate retains name, "
                "equivalent-SG, broad-cell, and usable local-CIF support; "
                "experimental diffraction or chemistry review is needed."
            )
        else:
            reason = (
                "No candidate satisfies the current structure conditions "
                "and no candidate remains suitable for targeted validation."
            )

        sample_result = {
            "sample_id": sample_id,
            "candidate_count_passing": str(len(strict_rows)),
            "candidate_count_reviewable": str(len(diffraction_rows)),
            "final_status": final_status,
            "solid_solution_or_substitution_review": (
                "true" if review_rows else "false"
            ),
            "reason": reason,
        }
        final_sample_rows.append(sample_result)

        for row in rows:
            output_candidate_rows.append(
                {
                    "sample_id": sample_id,
                    "candidate_cod_id": row["candidate_cod_id"],
                    "candidate_mineral_name": row["candidate_mineral_name"],
                    "candidate_formula": row["candidate_formula"],
                    "ideal_chemistry": (
                        row.get("ideal_chemistry")
                        or row.get("metadata_ideal_chemistry")
                    ),
                    "metadata_ideal_chemistry": row.get(
                        "metadata_ideal_chemistry"
                    ),
                    "cif_file_path": row["cif_file_path"],
                    "local_cif_parse_status": row["local_cif_parse_status"],
                    "name_support": row["name_support"],
                    "sample_name_match": row["sample_name_match"],
                    "reference_name_match": row["reference_name_match"],
                    "chemistry_status": row["chemistry_status"],
                    "chemistry_reason": row["chemistry_reason"],
                    "chemistry_evidence": row["chemistry_evidence"],
                    "existing_chemistry_reason": row[
                        "existing_chemistry_reason"
                    ],
                    "space_group_status": row["space_group_status"],
                    "cell_status": row["cell_status"],
                    "max_length_relative_difference": row[
                        "max_length_relative_difference"
                    ],
                    "max_angle_difference": row["max_angle_difference"],
                    "candidate_check_status": row["candidate_check_status"],
                    "candidate_count_total": str(len(rows)),
                    "candidate_count_passing": str(len(strict_rows)),
                    "candidate_count_reviewable": str(len(diffraction_rows)),
                    "final_status": final_status,
                    "solid_solution_or_substitution_review": (
                        "true" if review_rows else "false"
                    ),
                    "reason": row["reason"],
                }
            )

    summary = {
        "total": len(final_sample_rows),
        "structurally_ready_for_rescue": final_counts[
            "structurally_ready_for_rescue"
        ],
        "multiple_valid_candidates": final_counts[
            "multiple_valid_candidates"
        ],
        "diffraction_validation_needed": final_counts[
            "diffraction_validation_needed"
        ],
        "not_rescuable": final_counts["not_rescuable"],
        "solid_solution_or_substitution_review": solid_solution_count,
    }

    _write_csv(output_candidate_rows)
    _write_markdown(final_sample_rows, output_candidate_rows, summary)

    if len({row["sample_id"] for row in final_sample_rows}) != 36:
        raise RuntimeError("Final sample output does not contain 36 unique samples.")
    if sum(final_counts.values()) != 36:
        raise RuntimeError("Final status counts do not sum to 36.")

    print("36 total")
    print(
        "structurally_ready_for_rescue = "
        f"{summary['structurally_ready_for_rescue']}"
    )
    print(
        "multiple_valid_candidates = "
        f"{summary['multiple_valid_candidates']}"
    )
    print(
        "diffraction_validation_needed = "
        f"{summary['diffraction_validation_needed']}"
    )
    print(f"not_rescuable = {summary['not_rescuable']}")
    print(
        "solid_solution_or_substitution_review = "
        f"{summary['solid_solution_or_substitution_review']}"
    )
    print(f"candidate rows = {len(output_candidate_rows)}")
    print(f"CSV = {OUTPUT_CSV}")
    print(f"MD = {OUTPUT_MD}")


if __name__ == "__main__":
    main()
