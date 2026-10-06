from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crystaldb.matching.candidate_compare import compare_candidate
from crystaldb.matching.cell_compare import compare_cells
from crystaldb.matching.rruff_signature import build_rruff_signature
from crystaldb.mongo import get_database


COVERAGE_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_coverage_results_full_v1.json"
)
INDEX_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cif_index.json"
)
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rescue_review_v1"
)

TARGET_STATUSES = {
    "needs_review_only",
    "reference_structure_only",
}

FINDER_MAX_LENGTH = 0.05
FINDER_MAX_ANGLE = 2.0
CANDIDATE_MAX_LENGTH = 0.02
CANDIDATE_MAX_ANGLE = 1.0
STRONG_MAX_LENGTH = 0.005
STRONG_MAX_ANGLE = 0.5


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _bool_text(value: Any) -> str:
    if value is None:
        return ""
    return "true" if bool(value) else "false"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _metadata_value(
    raw_by_sample: dict[str, list[dict[str, Any]]],
    processed_by_sample: dict[str, list[dict[str, Any]]],
    sample_id: str,
    key: str,
) -> Any:
    for doc in raw_by_sample.get(sample_id, []) + processed_by_sample.get(
        sample_id, []
    ):
        value = (doc.get("metadata") or {}).get(key)
        if value not in (None, ""):
            return value
    return None


def _cell_from_signature(signature: dict[str, Any]) -> dict[str, Any]:
    return signature.get("cell_parameters") or {}


def _cell_flags(cell: dict[str, Any]) -> dict[str, Any]:
    max_length = cell.get("max_length_relative_difference")
    max_angle = cell.get("max_angle_difference")
    broad = (
        max_length is not None
        and max_angle is not None
        and max_length <= FINDER_MAX_LENGTH
        and max_angle <= FINDER_MAX_ANGLE
    )
    candidate = (
        max_length is not None
        and max_angle is not None
        and max_length <= CANDIDATE_MAX_LENGTH
        and max_angle <= CANDIDATE_MAX_ANGLE
    )
    strong = (
        max_length is not None
        and max_angle is not None
        and max_length <= STRONG_MAX_LENGTH
        and max_angle <= STRONG_MAX_ANGLE
    )
    return {
        "broad_cell_match": broad,
        "candidate_cell_close": candidate,
        "strong_cell_close": strong,
        "max_length_relative_difference": max_length,
        "max_angle_difference": max_angle,
    }


def _name_status(
    sample_name_match: bool,
    reference_name_match: bool,
) -> str:
    if sample_name_match and reference_name_match:
        return "sample_and_reference_name_match"
    if sample_name_match:
        return "sample_name_match_only"
    if reference_name_match:
        return "reference_name_match_only"
    return "no_name_match"


def _chemistry_status(value: Any) -> str:
    if value is True:
        return "compatible"
    if value is False:
        return "incompatible"
    return "uncertain"


def _sg_status(value: Any) -> str:
    if value is True:
        return "equivalent"
    if value is False:
        return "mismatch"
    return "unknown"


def _cell_status(flags: dict[str, Any]) -> str:
    max_length = flags["max_length_relative_difference"]
    max_angle = flags["max_angle_difference"]
    if max_length is None or max_angle is None:
        return "missing_cell_comparison"
    if flags["candidate_cell_close"]:
        return "candidate_window"
    if flags["broad_cell_match"]:
        return "finder_window_only"
    return "outside_finder_window"


def _positive_evidence_count(
    sample_name_match: bool,
    reference_name_match: bool,
    chemistry_compatible: Any,
    sg_equivalent: Any,
    broad_cell_match: bool,
) -> int:
    return sum(
        [
            bool(sample_name_match),
            bool(reference_name_match),
            chemistry_compatible is True,
            sg_equivalent is True,
            bool(broad_cell_match),
        ]
    )


def _available_evidence_count(
    sample_name_match: bool,
    reference_name_match: bool,
    chemistry_compatible: Any,
    sg_equivalent: Any,
    broad_cell_match: bool,
    cell_has_values: bool,
) -> int:
    return sum(
        [
            sample_name_match is not None,
            reference_name_match is not None,
            chemistry_compatible is not None,
            sg_equivalent is not None,
            cell_has_values,
            broad_cell_match,
        ]
    )


def _failure_flags(
    *,
    sample_name_match: bool,
    reference_name_match: bool,
    chemistry_compatible: Any,
    sg_equivalent: Any,
    cell_flags: dict[str, Any],
    original_relation_type: Any,
) -> list[str]:
    flags: list[str] = []
    if original_relation_type == "reference_structure":
        flags.append("reference_structure_only_by_original_rule")
    elif original_relation_type == "sample_structure":
        return []

    if chemistry_compatible is False:
        flags.append("chemistry_incompatible")
    elif chemistry_compatible is None:
        flags.append("chemistry_uncertain")

    if sg_equivalent is False:
        flags.append("space_group_mismatch")
    elif sg_equivalent is None:
        flags.append("space_group_unknown")

    max_length = cell_flags["max_length_relative_difference"]
    max_angle = cell_flags["max_angle_difference"]
    if max_length is None or max_angle is None:
        flags.append("cell_comparison_incomplete")
    elif not cell_flags["broad_cell_match"]:
        flags.append("cell_mismatch")
    elif not cell_flags["candidate_cell_close"]:
        flags.append("threshold_borderline_cell")

    if not sample_name_match and not reference_name_match:
        flags.append("name_mismatch")
    elif not sample_name_match and reference_name_match:
        flags.append("sample_name_mismatch_reference_only")

    return flags


def _candidate_pattern(flags: list[str]) -> str:
    if "reference_structure_only_by_original_rule" in flags:
        return "reference_structure_only_by_original_rule"
    if not flags:
        return "already_classified_by_original_rule"
    if len(flags) == 1:
        return flags[0]
    return "multiple_conflicting_evidence_types"


def _candidate_support_flags(row: dict[str, Any]) -> dict[str, bool]:
    chemistry = row["chemistry_compatible"]
    sg = row["sg_equivalent"]
    broad = row["broad_cell_match"]
    candidate_cell = row["candidate_cell_close"]
    name_support = row["name_support"]
    sample_name = row["sample_name_match"]

    chemistry_not_conflicting = chemistry is True or chemistry is None
    sample_compatible = (
        chemistry is True
        or (chemistry is None and sample_name)
    )

    return {
        # Exact current sample rule, expressed for audit only.
        "current_sample_rule_support": bool(
            sg is True
            and candidate_cell
            and sample_compatible
        ),
        # Broad structural support for rescue or diffraction review.
        "structural_support": bool(
            sg is True
            and broad
            and name_support
            and chemistry_not_conflicting
        ),
        "sample_structural_support": bool(
            sg is True
            and broad
            and sample_name
            and chemistry_not_conflicting
        ),
        "reference_structural_support": bool(
            sg is True
            and broad
            and row["reference_name_match"]
            and chemistry_not_conflicting
        ),
        "threshold_borderline_support": bool(
            sg is True
            and broad
            and not candidate_cell
            and name_support
            and chemistry_not_conflicting
        ),
        "symmetry_conflict_support": bool(
            sg is False
            and broad
            and name_support
            and chemistry_not_conflicting
        ),
        "weak_name_cell_support": bool(
            broad
            and name_support
            and chemistry_not_conflicting
            and sg is not True
        ),
    }


def _candidate_pair_equivalent(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    if not left["structural_support"] or not right["structural_support"]:
        return False

    left_sg = left.get("candidate_space_group_details") or {}
    right_sg = right.get("candidate_space_group_details") or {}
    left_number = left_sg.get("number")
    right_number = right_sg.get("number")
    if left_number is not None and right_number is not None:
        if left_number != right_number:
            return False
    elif left.get("candidate_space_group") != right.get(
        "candidate_space_group"
    ):
        return False

    left_cell = left.get("candidate_cell_parameters") or {}
    right_cell = right.get("candidate_cell_parameters") or {}
    cell = compare_cells(left_cell, right_cell)
    max_length = cell.get("max_length_relative_difference")
    max_angle = cell.get("max_angle_difference")
    if (
        max_length is None
        or max_angle is None
        or max_length > CANDIDATE_MAX_LENGTH
        or max_angle > CANDIDATE_MAX_ANGLE
    ):
        return False

    left_elements = set(
        (left.get("chemistry_comparison") or {}).get("elements_b") or []
    )
    right_elements = set(
        (right.get("chemistry_comparison") or {}).get("elements_b") or []
    )
    if left_elements and right_elements and left_elements != right_elements:
        return False
    return True


def _equivalent_group_size(rows: list[dict[str, Any]]) -> int:
    supportive = [
        row for row in rows if row.get("structural_support")
    ]
    if len(supportive) < 2:
        return 0

    adjacency: dict[int, set[int]] = defaultdict(set)
    for i, left in enumerate(supportive):
        for j in range(i + 1, len(supportive)):
            right = supportive[j]
            if _candidate_pair_equivalent(left, right):
                adjacency[i].add(j)
                adjacency[j].add(i)

    largest = 0
    visited: set[int] = set()
    for start in range(len(supportive)):
        if start in visited:
            continue
        stack = [start]
        component: set[int] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            visited.add(current)
            stack.extend(adjacency[current] - component)
        largest = max(largest, len(component))
    return largest


def _row_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    chemistry_rank = {
        True: 2,
        None: 1,
        False: 0,
    }.get(row.get("chemistry_compatible"), 0)
    sg_rank = {
        True: 2,
        None: 1,
        False: 0,
    }.get(row.get("sg_equivalent"), 0)
    return (
        int(row.get("structural_support", False)),
        int(row.get("current_sample_rule_support", False)),
        chemistry_rank,
        sg_rank,
        int(row.get("candidate_cell_close", False)),
        int(row.get("strong_cell_close", False)),
        row.get("evidence_count", 0),
        -(
            row.get("max_length_relative_difference")
            if row.get("max_length_relative_difference") is not None
            else 999.0
        ),
        -(
            row.get("max_angle_difference")
            if row.get("max_angle_difference") is not None
            else 999.0
        ),
    )


def _sample_failure_reason(
    rows: list[dict[str, Any]],
    original_status: str,
) -> tuple[str, str]:
    if not rows:
        return "no_candidate_rows", "No candidate comparison row was retained."

    current = [row for row in rows if row.get("current_sample_rule_support")]
    structural = [row for row in rows if row.get("structural_support")]
    borderline = [
        row for row in rows if row.get("threshold_borderline_support")
    ]
    symmetry = [
        row for row in rows if row.get("symmetry_conflict_support")
    ]
    weak = [
        row for row in rows if row.get("weak_name_cell_support")
    ]

    if original_status == "reference_structure_only" and not (
        structural or current or borderline or symmetry or weak
    ):
        chemistry_incompatible = sum(
            row.get("chemistry_compatible") is False
            for row in rows
        )
        if chemistry_incompatible == len(rows):
            return (
                "reference_candidate_chemistry_incompatible",
                "Reference candidates have name/cell evidence but all retained chemistry comparisons are incompatible.",
            )
        return (
            "reference_structure_only_no_sample_support",
            "Only reference-structure evidence remains; no combined sample-structure support is available.",
        )

    if len(current) >= 2:
        return (
            "multiple_plausible_candidates",
            "At least two candidates satisfy the current sample-structure rule.",
        )
    if len(structural) >= 2:
        return (
            "multiple_plausible_or_near_equivalent_candidates",
            "At least two candidates retain positive chemistry/name, SG, and cell support.",
        )
    if len(borderline) >= 1:
        return (
            "threshold_borderline_cell",
            "The candidate is inside the finder window but outside the stricter 2%/1° candidate window.",
        )
    if len(current) == 1:
        return (
            "single_current_rule_candidate",
            "One candidate meets the current sample rule; the original status should be manually reconciled.",
        )
    if len(symmetry) >= 1 and len(structural) == 0:
        return (
            "space_group_mismatch",
            "Cell and name/chemistry support exist, but the candidate space group is not equivalent.",
        )
    if weak:
        return (
            "space_group_unknown_or_conflicting",
            "Name and cell support exist, but space-group evidence is missing or conflicting.",
        )

    ranked = sorted(rows, key=_row_rank, reverse=True)
    best = ranked[0]
    pattern = best.get("candidate_failure_pattern") or "weak_evidence"
    if pattern == "chemistry_uncertain":
        pattern = "chemistry_uncertain"
    elif pattern == "chemistry_incompatible":
        pattern = "chemistry_incompatible"
    elif pattern == "space_group_unknown":
        pattern = "space_group_unknown"
    elif pattern == "space_group_mismatch":
        pattern = "space_group_mismatch"
    elif pattern in {"cell_mismatch", "cell_comparison_incomplete"}:
        pattern = "cell_mismatch"
    elif pattern == "name_mismatch":
        pattern = "name_mismatch"
    else:
        pattern = "weak_evidence_across_candidates"
    return pattern, (
        "No candidate met the rescue support rule; the best retained row "
        f"has pattern {pattern}."
    )


def _rescue_category(
    rows: list[dict[str, Any]],
    original_status: str,
    group_size: int,
) -> tuple[str, bool, str]:
    structural = [row for row in rows if row.get("structural_support")]
    current = [row for row in rows if row.get("current_sample_rule_support")]
    borderline = [
        row for row in rows if row.get("threshold_borderline_support")
    ]
    reference_structural = [
        row for row in rows if row.get("reference_structural_support")
    ]
    symmetry = [
        row for row in rows if row.get("symmetry_conflict_support")
    ]
    weak = [row for row in rows if row.get("weak_name_cell_support")]

    if group_size >= 2:
        return (
            "equivalent_group_candidate",
            True,
            f"{group_size} structurally supported candidates form a near-equivalent group.",
        )

    if len(structural) >= 2 or len(current) >= 2 or (
        len(weak) >= 2 and original_status == "needs_review_only"
    ):
        return (
            "diffraction_validation_needed",
            True,
            "Multiple plausible or weakly separated candidates remain.",
        )

    if len(structural) == 1:
        row = structural[0]
        if row.get("threshold_borderline_support"):
            return (
                "high_priority_rescue",
                True,
                "One structurally supported candidate is outside only the stricter candidate cell window.",
            )
        return (
            "high_priority_rescue",
            True,
            "One candidate has compatible/uncertain chemistry, equivalent SG, and compatible cell evidence.",
        )

    if len(reference_structural) == 1:
        return (
            "high_priority_rescue",
            True,
            "A reference-structure candidate is structurally plausible, but sample identity remains unconfirmed.",
        )

    if borderline:
        return (
            "high_priority_rescue",
            True,
            "A candidate is close to the cell threshold and merits targeted validation.",
        )

    if symmetry:
        return (
            "diffraction_validation_needed",
            True,
            "A symmetry conflict remains while cell and name/chemistry evidence are supportive.",
        )

    if not (
        structural
        or current
        or borderline
        or symmetry
        or weak
    ):
        return (
            "not_rescuable_with_current_evidence",
            False,
            "No candidate has meaningful combined chemistry, name, SG, and cell support.",
        )

    if rows and (weak or any(row.get("name_support") for row in rows)):
        return (
            "low_priority_review",
            False,
            "Candidates retain limited evidence but lack a defensible sample-structure assignment.",
        )

    return (
        "not_rescuable_with_current_evidence",
        False,
        "No candidate has meaningful combined chemistry, name, SG, and cell support.",
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: row.get(field, "")
                    for field in fields
                }
            )


def _scan_existing_diffraction_evidence(
    target_ids: set[str],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for path in sorted((PROJECT_ROOT / "data" / "mappings").glob("*.json")):
        if path.name == COVERAGE_FILE.name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        hits = sorted(sample_id for sample_id in target_ids if sample_id in text)
        if hits:
            evidence.append(
                {
                    "file": str(path.relative_to(PROJECT_ROOT)).replace(
                        "\\", "/"
                    ),
                    "target_id_hits": len(hits),
                    "target_ids": hits,
                    "contains_diffraction_metrics_key": (
                        "diffraction_metrics" in text
                        or "median_abs_residual" in text
                        or "weighted_mean_abs_residual" in text
                    ),
                }
            )
    return evidence


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    coverage = _read_json(COVERAGE_FILE)
    cif_index = _read_json(INDEX_FILE)
    index_by_id = {
        str(row.get("source_id")): row
        for row in cif_index
        if row.get("source") == "COD"
    }

    target_coverage = [
        row for row in coverage if row.get("status") in TARGET_STATUSES
    ]
    target_coverage.sort(key=lambda row: str(row.get("rruff_sample_id")))
    target_ids = [str(row["rruff_sample_id"]) for row in target_coverage]

    db = get_database(database_name="rruff")
    dif_docs = list(
        db.dif.find({"sample_id": {"$in": target_ids}})
    )
    raw_docs = list(
        db.xy_raw.find({"sample_id": {"$in": target_ids}})
    )
    processed_docs = list(
        db.xy_processed.find({"sample_id": {"$in": target_ids}})
    )

    dif_by_sample = {
        str(doc.get("sample_id")): doc for doc in dif_docs
    }
    raw_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    processed_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in raw_docs:
        raw_by_sample[str(doc.get("sample_id"))].append(doc)
    for doc in processed_docs:
        processed_by_sample[str(doc.get("sample_id"))].append(doc)

    candidate_detail_rows: list[dict[str, Any]] = []
    sample_summary_rows: list[dict[str, Any]] = []
    detailed_records: list[dict[str, Any]] = []
    candidate_pattern_counter: Counter[str] = Counter()
    sample_failure_counter: Counter[str] = Counter()
    rescue_counter: Counter[str] = Counter()
    original_status_counter: Counter[str] = Counter()
    reference_analysis_counter: Counter[str] = Counter()
    threshold_counter: Counter[str] = Counter()
    sample_failure_signal_counter: Counter[str] = Counter()

    for coverage_row in target_coverage:
        sample_id = str(coverage_row["rruff_sample_id"])
        original_status = str(coverage_row["status"])
        original_status_counter[original_status] += 1

        dif_doc = dif_by_sample.get(sample_id, {})
        metadata_ideal_chemistry = _metadata_value(
            raw_by_sample,
            processed_by_sample,
            sample_id,
            "IDEAL CHEMISTRY",
        )
        # Preserve the chemistry value used by the frozen coverage run.
        # Processed-only metadata is retained separately as supplemental
        # context and must not silently change the historical comparison.
        ideal_chemistry = coverage_row.get("ideal_chemistry")
        signature = build_rruff_signature(
            dif_doc,
            ideal_chemistry=ideal_chemistry,
        )
        rruff_cell = _cell_from_signature(signature)
        references = dif_doc.get("references") or []
        sample_mineral = signature.get("sample_mineral")
        reference_name = signature.get("reference_structure_name")
        description = _metadata_value(
            raw_by_sample,
            processed_by_sample,
            sample_id,
            "DIFFRACTION SAMPLE DESCRIPTION",
        )

        rows_for_sample: list[dict[str, Any]] = []
        for original_candidate in coverage_row.get("matches") or []:
            cod_id = str(original_candidate.get("source_id"))
            index_row = index_by_id.get(cod_id, {})
            comparison = compare_candidate(signature, index_row)
            chemistry = comparison.get("chemistry") or {}
            sg = comparison.get("space_group") or {}
            cell = comparison.get("cell") or {}
            names = {
                "sample_name_match": bool(
                    comparison.get("sample_name_match")
                ),
                "reference_name_match": bool(
                    comparison.get("reference_name_match")
                ),
            }
            name_support = (
                names["sample_name_match"]
                or names["reference_name_match"]
            )
            flags = _cell_flags(cell)
            failure_flags = _failure_flags(
                sample_name_match=names["sample_name_match"],
                reference_name_match=names["reference_name_match"],
                chemistry_compatible=chemistry.get("compatible"),
                sg_equivalent=sg.get("equivalent"),
                cell_flags=flags,
                original_relation_type=original_candidate.get(
                    "relation_type"
                ),
            )
            candidate_row = {
                "sample_id": sample_id,
                "original_status": original_status,
                "sample_mineral": sample_mineral,
                "reference_structure_name": reference_name,
                "ideal_chemistry": ideal_chemistry,
                "metadata_ideal_chemistry": metadata_ideal_chemistry,
                "rruff_space_group": signature.get("space_group"),
                "rruff_cell_a": rruff_cell.get("a"),
                "rruff_cell_b": rruff_cell.get("b"),
                "rruff_cell_c": rruff_cell.get("c"),
                "rruff_cell_alpha": rruff_cell.get("alpha"),
                "rruff_cell_beta": rruff_cell.get("beta"),
                "rruff_cell_gamma": rruff_cell.get("gamma"),
                "rruff_atom_count": signature.get("atom_count"),
                "rruff_references": _json(references),
                "diffraction_sample_description": description,
                "source": original_candidate.get("source"),
                "cod_id": cod_id,
                "cif_file_path": index_row.get("file_path"),
                "cif_file_exists": bool(
                    index_row.get("file_path")
                    and (PROJECT_ROOT / index_row["file_path"]).is_file()
                ),
                "candidate_mineral_name": index_row.get("mineral_name"),
                "candidate_formula": index_row.get("formula"),
                "candidate_space_group": index_row.get("space_group"),
                "candidate_cell_a": (
                    index_row.get("cell_parameters") or {}
                ).get("a"),
                "candidate_cell_b": (
                    index_row.get("cell_parameters") or {}
                ).get("b"),
                "candidate_cell_c": (
                    index_row.get("cell_parameters") or {}
                ).get("c"),
                "candidate_cell_alpha": (
                    index_row.get("cell_parameters") or {}
                ).get("alpha"),
                "candidate_cell_beta": (
                    index_row.get("cell_parameters") or {}
                ).get("beta"),
                "candidate_cell_gamma": (
                    index_row.get("cell_parameters") or {}
                ).get("gamma"),
                "candidate_atom_count": index_row.get("atom_count"),
                "candidate_parse_status": index_row.get("parse_status"),
                "candidate_role": original_candidate.get(
                    "candidate_type"
                ),
                "original_classification_status": original_candidate.get(
                    "status"
                ),
                "original_relation_type": original_candidate.get(
                    "relation_type"
                ),
                "sample_name_match": names["sample_name_match"],
                "reference_name_match": names["reference_name_match"],
                "name_support": name_support,
                "name_status": _name_status(
                    names["sample_name_match"],
                    names["reference_name_match"],
                ),
                "chemistry_compatible": chemistry.get("compatible"),
                "chemistry_status": _chemistry_status(
                    chemistry.get("compatible")
                ),
                "chemistry_reason": chemistry.get("reason"),
                "chemistry_comparison": chemistry,
                "sg_equivalent": sg.get("equivalent"),
                "sg_status": _sg_status(sg.get("equivalent")),
                "sg_same_number": sg.get("same_number"),
                "rruff_space_group_details": sg.get("a"),
                "candidate_space_group_details": sg.get("b"),
                "space_group_comparison": sg,
                "broad_cell_match": flags["broad_cell_match"],
                "candidate_cell_close": flags["candidate_cell_close"],
                "strong_cell_close": flags["strong_cell_close"],
                "cell_status": _cell_status(flags),
                "max_length_relative_difference": flags[
                    "max_length_relative_difference"
                ],
                "max_angle_difference": flags["max_angle_difference"],
                "length_relative_differences": cell.get(
                    "length_relative_differences"
                ),
                "angle_absolute_differences": cell.get(
                    "angle_absolute_differences"
                ),
                "candidate_margin_length": (
                    CANDIDATE_MAX_LENGTH
                    - flags["max_length_relative_difference"]
                    if flags["max_length_relative_difference"] is not None
                    else None
                ),
                "candidate_margin_angle": (
                    CANDIDATE_MAX_ANGLE
                    - flags["max_angle_difference"]
                    if flags["max_angle_difference"] is not None
                    else None
                ),
                "finder_margin_length": (
                    FINDER_MAX_LENGTH
                    - flags["max_length_relative_difference"]
                    if flags["max_length_relative_difference"] is not None
                    else None
                ),
                "finder_margin_angle": (
                    FINDER_MAX_ANGLE
                    - flags["max_angle_difference"]
                    if flags["max_angle_difference"] is not None
                    else None
                ),
                "evidence_count": _positive_evidence_count(
                    names["sample_name_match"],
                    names["reference_name_match"],
                    chemistry.get("compatible"),
                    sg.get("equivalent"),
                    flags["broad_cell_match"],
                ),
                "available_evidence_count": _available_evidence_count(
                    names["sample_name_match"],
                    names["reference_name_match"],
                    chemistry.get("compatible"),
                    sg.get("equivalent"),
                    flags["broad_cell_match"],
                    flags["max_length_relative_difference"] is not None
                    and flags["max_angle_difference"] is not None,
                ),
                "failure_flags": failure_flags,
                "candidate_failure_pattern": _candidate_pattern(
                    failure_flags
                ),
                "original_evidence": original_candidate.get("evidence")
                or {},
                "comparison": comparison,
            }
            candidate_row.update(_candidate_support_flags(candidate_row))
            rows_for_sample.append(candidate_row)

            candidate_pattern_counter[
                candidate_row["candidate_failure_pattern"]
            ] += 1
            if (
                candidate_row["broad_cell_match"]
                and not candidate_row["candidate_cell_close"]
            ):
                threshold_counter["candidate_window_borderline"] += 1
            if (
                candidate_row["broad_cell_match"]
                and candidate_row["max_length_relative_difference"]
                is not None
                and candidate_row["max_length_relative_difference"]
                > CANDIDATE_MAX_LENGTH
            ):
                threshold_counter["length_over_candidate_threshold"] += 1
            if (
                candidate_row["broad_cell_match"]
                and candidate_row["max_angle_difference"] is not None
                and candidate_row["max_angle_difference"]
                > CANDIDATE_MAX_ANGLE
            ):
                threshold_counter["angle_over_candidate_threshold"] += 1
            if (
                candidate_row["max_length_relative_difference"] is not None
                and candidate_row["max_length_relative_difference"]
                > FINDER_MAX_LENGTH
            ):
                threshold_counter["outside_finder_length_window"] += 1

            candidate_detail_rows.append(
                {
                    key: (
                        _json(value)
                        if isinstance(value, (dict, list))
                        else value
                    )
                    for key, value in candidate_row.items()
                    if key != "comparison"
                }
            )

        for row in rows_for_sample:
            # Pairwise helpers are calculated after all candidate rows exist.
            row["equivalent_group_support"] = False

        group_size = _equivalent_group_size(rows_for_sample)
        if group_size >= 2:
            supportive = [
                row
                for row in rows_for_sample
                if row.get("structural_support")
            ]
            for row in supportive:
                row["equivalent_group_support"] = True

        failure_reason, failure_note = _sample_failure_reason(
            rows_for_sample,
            original_status,
        )
        rescue_category, diffraction_recommended, rescue_note = (
            _rescue_category(
                rows_for_sample,
                original_status,
                group_size,
            )
        )
        sample_failure_counter[failure_reason] += 1
        rescue_counter[rescue_category] += 1
        failure_signals: list[str] = []
        if any(
            row["chemistry_compatible"] is None
            for row in rows_for_sample
        ):
            failure_signals.append("chemistry_uncertain")
        if any(
            row["chemistry_compatible"] is False
            for row in rows_for_sample
        ):
            failure_signals.append("chemistry_incompatible")
        if any(
            row["sg_equivalent"] is False
            for row in rows_for_sample
        ):
            failure_signals.append("space_group_mismatch")
        if any(
            row["sg_equivalent"] is None
            for row in rows_for_sample
        ):
            failure_signals.append("space_group_unknown")
        if any(
            not row["broad_cell_match"]
            for row in rows_for_sample
        ):
            failure_signals.append("cell_mismatch")
        if any(
            row["threshold_borderline_support"]
            for row in rows_for_sample
        ):
            failure_signals.append("threshold_borderline")
        if any(
            not row["name_support"]
            for row in rows_for_sample
        ):
            failure_signals.append("name_mismatch")
        if any(
            row["reference_name_match"]
            and not row["sample_name_match"]
            for row in rows_for_sample
        ):
            failure_signals.append("reference_name_without_sample_name")
        if len(rows_for_sample) > 1:
            failure_signals.append("multiple_candidate_rows")
        if sum(
            row["structural_support"] for row in rows_for_sample
        ) >= 2:
            failure_signals.append("multiple_plausible_candidates")
        if group_size >= 2:
            failure_signals.append("multiple_equivalent_candidates")
        for signal in failure_signals:
            sample_failure_signal_counter[signal] += 1
        if any(row.get("threshold_borderline_support") for row in rows_for_sample):
            threshold_counter["sample_with_threshold_borderline"] += 1

        ranked_rows = sorted(rows_for_sample, key=_row_rank, reverse=True)
        best = ranked_rows[0] if ranked_rows else {}
        chemistry_statuses = sorted(
            {
                row["chemistry_status"]
                for row in rows_for_sample
            }
        )
        sg_statuses = sorted(
            {
                row["sg_status"]
                for row in rows_for_sample
            }
        )
        cell_statuses = sorted(
            {
                row["cell_status"]
                for row in rows_for_sample
            }
        )
        name_statuses = sorted(
            {
                row["name_status"]
                for row in rows_for_sample
            }
        )

        if original_status == "reference_structure_only":
            ref_name_match = any(
                row["reference_name_match"] for row in rows_for_sample
            )
            sample_name_match = any(
                row["sample_name_match"] for row in rows_for_sample
            )
            ref_structural = any(
                row["reference_structural_support"]
                for row in rows_for_sample
            )
            ref_chem_unknown = any(
                row["chemistry_compatible"] is None
                for row in rows_for_sample
            )
            ref_chem_incompatible = any(
                row["chemistry_compatible"] is False
                for row in rows_for_sample
            )
            ref_chem_ratio_difference = any(
                row.get("chemistry_reason")
                == "different_composition_ratio"
                for row in rows_for_sample
            )
            ref_element_difference = any(
                row.get("chemistry_reason")
                == "different_element_set"
                for row in rows_for_sample
            )
            reference_analysis_counter[
                "samples_with_reference_name_match"
            ] += int(ref_name_match)
            reference_analysis_counter[
                "samples_with_sample_name_match"
            ] += int(sample_name_match)
            reference_analysis_counter[
                "samples_with_structurally_plausible_reference_candidate"
            ] += int(ref_structural)
            reference_analysis_counter[
                "samples_with_chemistry_uncertain"
            ] += int(ref_chem_unknown)
            reference_analysis_counter[
                "samples_with_chemistry_incompatible"
            ] += int(ref_chem_incompatible)
            reference_analysis_counter[
                "samples_with_possible_substitution_or_ratio_difference"
            ] += int(ref_chem_ratio_difference)
            reference_analysis_counter[
                "samples_with_different_element_set"
            ] += int(ref_element_difference)
            reference_analysis_counter[
                "samples_with_any_space_group_mismatch"
            ] += int(
                any(row["sg_equivalent"] is False for row in rows_for_sample)
            )
            reference_analysis_counter[
                "samples_with_any_cell_outside_candidate_window"
            ] += int(
                any(
                    not row["candidate_cell_close"]
                    for row in rows_for_sample
                )
            )

        sample_summary = {
            "sample_id": sample_id,
            "original_status": original_status,
            "sample_mineral": sample_mineral,
            "reference_structure_name": reference_name,
            "ideal_chemistry": ideal_chemistry,
            "metadata_ideal_chemistry": metadata_ideal_chemistry,
            "rruff_space_group": signature.get("space_group"),
            "rruff_cell_a": rruff_cell.get("a"),
            "rruff_cell_b": rruff_cell.get("b"),
            "rruff_cell_c": rruff_cell.get("c"),
            "rruff_cell_alpha": rruff_cell.get("alpha"),
            "rruff_cell_beta": rruff_cell.get("beta"),
            "rruff_cell_gamma": rruff_cell.get("gamma"),
            "rruff_atom_count": signature.get("atom_count"),
            "rruff_references": _json(references),
            "diffraction_sample_description": description,
            "raw_document_count": len(raw_by_sample.get(sample_id, [])),
            "processed_document_count": len(
                processed_by_sample.get(sample_id, [])
            ),
            "candidate_count": len(rows_for_sample),
            "plausible_candidate_count": sum(
                row["structural_support"] for row in rows_for_sample
            ),
            "current_sample_rule_candidate_count": sum(
                row["current_sample_rule_support"]
                for row in rows_for_sample
            ),
            "reference_structurally_plausible_count": sum(
                row["reference_structural_support"]
                for row in rows_for_sample
            ),
            "equivalent_group_size": group_size,
            "best_candidate_cod_id": best.get("cod_id"),
            "best_candidate_role": best.get("candidate_role"),
            "best_candidate_failure_pattern": best.get(
                "candidate_failure_pattern"
            ),
            "dominant_failure_reason": failure_reason,
            "failure_signals": ";".join(sorted(failure_signals)),
            "chemistry_status": ";".join(chemistry_statuses),
            "sg_status": ";".join(sg_statuses),
            "cell_status": ";".join(cell_statuses),
            "name_status": ";".join(name_statuses),
            "rescue_category": rescue_category,
            "diffraction_validation_recommended": diffraction_recommended,
            "threshold_borderline": any(
                row.get("threshold_borderline_support")
                for row in rows_for_sample
            ),
            "failure_note": failure_note,
            "rescue_note": rescue_note,
        }
        sample_summary_rows.append(sample_summary)

        detailed_records.append(
            {
                "sample": {
                    key: value
                    for key, value in sample_summary.items()
                },
                "original_coverage": coverage_row,
                "candidates": rows_for_sample,
            }
        )

        # Update the CSV rows with post-pairwise group information.
        for detail_row, enriched_row in zip(
            candidate_detail_rows[-len(rows_for_sample):],
            rows_for_sample,
        ):
            detail_row["structural_support"] = enriched_row[
                "structural_support"
            ]
            detail_row["sample_structural_support"] = enriched_row[
                "sample_structural_support"
            ]
            detail_row["reference_structural_support"] = enriched_row[
                "reference_structural_support"
            ]
            detail_row["threshold_borderline_support"] = enriched_row[
                "threshold_borderline_support"
            ]
            detail_row["symmetry_conflict_support"] = enriched_row[
                "symmetry_conflict_support"
            ]
            detail_row["weak_name_cell_support"] = enriched_row[
                "weak_name_cell_support"
            ]
            detail_row["current_sample_rule_support"] = enriched_row[
                "current_sample_rule_support"
            ]
            detail_row["equivalent_group_support"] = enriched_row[
                "equivalent_group_support"
            ]

    existing_diffraction_evidence = _scan_existing_diffraction_evidence(
        set(target_ids)
    )

    failure_payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_sample_count": len(target_ids),
        "original_status_counts": dict(original_status_counter),
        "candidate_row_count": len(candidate_detail_rows),
        "candidate_failure_pattern_counts": dict(candidate_pattern_counter),
        "sample_dominant_failure_reason_counts": dict(sample_failure_counter),
        "sample_failure_signal_counts": dict(
            sample_failure_signal_counter
        ),
        "rescue_category_counts": dict(rescue_counter),
        "threshold_counts": dict(threshold_counter),
        "reference_structure_only_analysis": dict(reference_analysis_counter),
        "existing_diffraction_evidence_scan": existing_diffraction_evidence,
        "definitions": {
            "evidence_count": (
                "Count of positive sample/reference-name, chemistry=true, "
                "SG=equivalent, and broad-cell evidence signals."
            ),
            "structural_support": (
                "SG equivalent + broad finder-window cell + name support "
                " + chemistry true or unknown."
            ),
            "threshold_borderline": (
                "Inside the old 5%/2 degree finder window but outside the "
                "2%/1 degree candidate window."
            ),
            "equivalent_group_candidate": (
                "At least two structural-support candidates with same SG "
                "number/setting compatibility, close cells, and matching "
                "candidate element sets."
            ),
        },
    }

    summary_fields = [
        "sample_id",
        "original_status",
        "sample_mineral",
        "reference_structure_name",
        "ideal_chemistry",
        "metadata_ideal_chemistry",
        "rruff_space_group",
        "rruff_cell_a",
        "rruff_cell_b",
        "rruff_cell_c",
        "rruff_cell_alpha",
        "rruff_cell_beta",
        "rruff_cell_gamma",
        "rruff_atom_count",
        "rruff_references",
        "diffraction_sample_description",
        "raw_document_count",
        "processed_document_count",
        "candidate_count",
        "plausible_candidate_count",
        "current_sample_rule_candidate_count",
        "reference_structurally_plausible_count",
        "equivalent_group_size",
        "best_candidate_cod_id",
        "best_candidate_role",
        "best_candidate_failure_pattern",
        "dominant_failure_reason",
        "failure_signals",
        "chemistry_status",
        "sg_status",
        "cell_status",
        "name_status",
        "rescue_category",
        "diffraction_validation_recommended",
        "threshold_borderline",
        "failure_note",
        "rescue_note",
    ]
    candidate_fields = [
        "sample_id",
        "original_status",
        "sample_mineral",
        "reference_structure_name",
        "ideal_chemistry",
        "metadata_ideal_chemistry",
        "rruff_space_group",
        "rruff_cell_a",
        "rruff_cell_b",
        "rruff_cell_c",
        "rruff_cell_alpha",
        "rruff_cell_beta",
        "rruff_cell_gamma",
        "rruff_atom_count",
        "rruff_references",
        "diffraction_sample_description",
        "source",
        "cod_id",
        "cif_file_path",
        "cif_file_exists",
        "candidate_mineral_name",
        "candidate_formula",
        "candidate_space_group",
        "candidate_cell_a",
        "candidate_cell_b",
        "candidate_cell_c",
        "candidate_cell_alpha",
        "candidate_cell_beta",
        "candidate_cell_gamma",
        "candidate_atom_count",
        "candidate_parse_status",
        "candidate_role",
        "original_classification_status",
        "original_relation_type",
        "sample_name_match",
        "reference_name_match",
        "name_support",
        "name_status",
        "chemistry_compatible",
        "chemistry_status",
        "chemistry_reason",
        "chemistry_comparison",
        "sg_equivalent",
        "sg_status",
        "sg_same_number",
        "rruff_space_group_details",
        "candidate_space_group_details",
        "space_group_comparison",
        "broad_cell_match",
        "candidate_cell_close",
        "strong_cell_close",
        "cell_status",
        "max_length_relative_difference",
        "max_angle_difference",
        "length_relative_differences",
        "angle_absolute_differences",
        "candidate_margin_length",
        "candidate_margin_angle",
        "finder_margin_length",
        "finder_margin_angle",
        "evidence_count",
        "available_evidence_count",
        "failure_flags",
        "candidate_failure_pattern",
        "original_evidence",
        "current_sample_rule_support",
        "structural_support",
        "sample_structural_support",
        "reference_structural_support",
        "threshold_borderline_support",
        "symmetry_conflict_support",
        "weak_name_cell_support",
        "equivalent_group_support",
    ]

    _write_json(
        OUTPUT_ROOT / "rruff_rescue_candidates_v1.json",
        {
            "schema_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scope": {
                "coverage_file": str(
                    COVERAGE_FILE.relative_to(PROJECT_ROOT)
                ).replace("\\", "/"),
                "target_statuses": sorted(TARGET_STATUSES),
                "target_sample_count": len(target_ids),
                "target_status_counts": dict(original_status_counter),
                "candidate_row_count": len(candidate_detail_rows),
                "new_diffraction_computation": False,
                "database_modified": False,
                "source_files_modified": False,
                "existing_results_modified": False,
            },
            "method": failure_payload["definitions"],
            "records": detailed_records,
        },
    )
    _write_csv(
        OUTPUT_ROOT / "rruff_rescue_summary_v1.csv",
        sample_summary_rows,
        summary_fields,
    )
    _write_csv(
        OUTPUT_ROOT / "rruff_rescue_candidate_details_v1.csv",
        candidate_detail_rows,
        candidate_fields,
    )
    _write_json(
        OUTPUT_ROOT / "rruff_rescue_failure_counts_v1.json",
        failure_payload,
    )

    reference_rows = [
        row
        for row in sample_summary_rows
        if row["original_status"] == "reference_structure_only"
    ]
    ref_plausible = sum(
        row["reference_structurally_plausible_count"] > 0
        for row in reference_rows
    )
    category_lines = "\n".join(
        f"| `{key}` | {value} |"
        for key, value in sorted(rescue_counter.items())
    )
    failure_lines = "\n".join(
        f"| `{key}` | {value} |"
        for key, value in sorted(sample_failure_counter.items())
    )
    candidate_failure_lines = "\n".join(
        f"| `{key}` | {value} |"
        for key, value in sorted(candidate_pattern_counter.items())
    )
    reference_lines = "\n".join(
        f"| `{key}` | {value} |"
        for key, value in sorted(reference_analysis_counter.items())
    )

    example_rows: list[dict[str, Any]] = []
    for category in (
        "high_priority_rescue",
        "diffraction_validation_needed",
        "equivalent_group_candidate",
        "low_priority_review",
        "not_rescuable_with_current_evidence",
    ):
        category_rows = sorted(
            [
                row
                for row in sample_summary_rows
                if row["rescue_category"] == category
            ],
            key=lambda row: (
                row["original_status"],
                row["dominant_failure_reason"],
                row["sample_id"],
            ),
        )
        example_rows.extend(category_rows[:4])

    if len(example_rows) < 20:
        seen = {row["sample_id"] for row in example_rows}
        for row in sorted(
            sample_summary_rows,
            key=lambda item: (
                item["dominant_failure_reason"],
                item["sample_id"],
            ),
        ):
            if row["sample_id"] in seen:
                continue
            example_rows.append(row)
            seen.add(row["sample_id"])
            if len(example_rows) == 20:
                break
    examples = "\n".join(
        (
            f"- `{row['sample_id']}` ({row['original_status']}): "
            f"`{row['rescue_category']}`, "
            f"failure=`{row['dominant_failure_reason']}`, "
            f"best COD=`{row.get('best_candidate_cod_id') or 'none'}`"
        )
        for row in example_rows
    )

    report = f"""# RRUFF Rescue/Review Analysis v1

## Scope

This is a read-only analysis of the frozen COD coverage output. It examines
only the 304 records with original status `needs_review_only` or
`reference_structure_only`.

| Population | Count |
|---|---:|
| Target samples | {len(target_ids)} |
| `needs_review_only` | {original_status_counter["needs_review_only"]} |
| `reference_structure_only` | {original_status_counter["reference_structure_only"]} |
| Existing candidate comparison rows | {len(candidate_detail_rows)} |

The original statuses are preserved. No existing mapping, CIF, MongoDB
collection, source module, or diffraction result was modified. No new
diffraction simulation or matching was run.

## Evidence Sources

- `data/mappings/cod_coverage_results_full_v1.json`: original 3013-record
  coverage and candidate-level evidence.
- `data/mappings/cif_index.json`: COD candidate metadata and parse status.
- MongoDB database `rruff`, collections `dif`, `xy_raw`, and
  `xy_processed`: RRUFF sample metadata and crystallographic signatures.
- Existing comparison functions:
  `candidate_compare.compare_candidate`,
  `chemistry.compare_chemistry`, `space_group.compare_space_groups`,
  and `cell_compare.compare_cells`.

The candidate detail output keeps both the original stored evidence and the
reconstructed comparison object. `evidence_count` is the number of positive
signals among sample-name match, reference-name match, chemistry compatible,
space-group equivalent, and broad cell match.

## Failure Patterns

### Sample-level dominant failure reason

These labels are an audit grouping, not a replacement for the original
status.

| Failure pattern | Samples |
|---|---:|
{failure_lines}

### Candidate-level failure pattern

| Candidate pattern | Candidate rows |
|---|---:|
{candidate_failure_lines}

The principal patterns are:

- `space_group_unknown`: name and cell evidence exist, but one or both
  space-group symbols could not be compared by the existing Gemmi-based
  logic.
- `space_group_mismatch`: the candidate cell/name evidence is supportive but
  the resolved space-group operations differ.
- `chemistry_uncertain`: one formula uses notation the current parser does
  not interpret exactly; this is not treated as chemistry incompatibility.
- `chemistry_incompatible`: parsed compositions or element sets disagree.
- `threshold_borderline_cell`: the candidate is inside the historical finder
  window of 5% / 2 degrees but outside the stricter candidate window of
  2% / 1 degree.
- `multiple_conflicting_evidence_types`: more than one major evidence type
  remains unresolved for the candidate.

### Non-mutually-exclusive sample-level signals

| Signal | Samples |
|---|---:|
{chr(10).join(f"| `{key}` | {value} |" for key, value in sorted(sample_failure_signal_counter.items()))}

These signal counts are intentionally non-mutually-exclusive. A single
sample can have chemistry uncertainty, an unknown space group, and multiple
candidate rows at the same time.

## Rescue Categories

| Provisional category | Samples |
|---|---:|
{category_lines}

These categories are provisional review labels only:

- `high_priority_rescue`: one structurally persuasive candidate, usually
  needing a targeted check of a narrow threshold, formula notation, or the
  sample/reference-name distinction.
- `diffraction_validation_needed`: more than one plausible candidate or an
  unresolved symmetry choice where powder diffraction could discriminate.
- `equivalent_group_candidate`: several candidates are close enough to
  retain as a crystallographic candidate group rather than force one COD ID.
- `low_priority_review`: some evidence exists, but no defensible single
  rescue candidate is isolated.
- `not_rescuable_with_current_evidence`: no candidate has meaningful
  combined support under the available metadata.

## Reference-Structure-Only Review

There are {len(reference_rows)} `reference_structure_only` samples. The
following counts describe their existing evidence; they do not promote any
candidate to a sample structure:

| Measure | Samples |
|---|---:|
| Structurally plausible reference candidate | {ref_plausible} |
{reference_lines}

A reference candidate is considered structurally plausible here when its
reference name matches, its space group is equivalent, its cell is in the
finder window, and chemistry is compatible or uncertain. A candidate with
chemistry incompatible remains a reference-only warning even when its cell
and symmetry agree. The original reference-only interpretation is retained:
the CIF may describe the bibliography/reference structure rather than the
measured sample.

## Threshold Effects

| Threshold diagnostic | Count |
|---|---:|
{chr(10).join(f"| `{key}` | {value} |" for key, value in sorted(threshold_counter.items()))}

The analysis does not relax any threshold globally.

## Existing Diffraction Evidence

The output scan checked existing JSON mapping files for the 304 target IDs and
for diffraction-metric fields. It did not recalculate patterns. Details are
stored in `rruff_rescue_failure_counts_v1.json`.

## Representative Examples

{examples}

## Output Files

- `rruff_rescue_candidates_v1.json`
- `rruff_rescue_summary_v1.csv`
- `rruff_rescue_candidate_details_v1.csv`
- `rruff_rescue_failure_counts_v1.json`
- `rruff_rescue_report_v1.md`
"""
    (OUTPUT_ROOT / "rruff_rescue_report_v1.md").write_text(
        report,
        encoding="utf-8",
    )

    print(f"Target samples: {len(target_ids)}")
    print(
        "needs_review_only: "
        f"{original_status_counter['needs_review_only']}"
    )
    print(
        "reference_structure_only: "
        f"{original_status_counter['reference_structure_only']}"
    )
    print()
    print(
        "High-priority rescue: "
        f"{rescue_counter['high_priority_rescue']}"
    )
    print(
        "Diffraction validation needed: "
        f"{rescue_counter['diffraction_validation_needed']}"
    )
    print(
        "Equivalent-group candidates: "
        f"{rescue_counter['equivalent_group_candidate']}"
    )
    print(
        "Low-priority review: "
        f"{rescue_counter['low_priority_review']}"
    )
    print(
        "Not rescuable with current evidence: "
        f"{rescue_counter['not_rescuable_with_current_evidence']}"
    )
    print()
    print("Main failure modes:")
    for key, value in sorted(sample_failure_counter.items()):
        print(f"- {key}: {value}")
    print()
    print("Examples:")
    for row in example_rows:
        print(
            f"- {row['sample_id']} | {row['original_status']} | "
            f"{row['rescue_category']} | "
            f"{row['dominant_failure_reason']} | "
            f"best COD {row.get('best_candidate_cod_id') or 'none'}"
        )
    print()
    print(f"Outputs: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
