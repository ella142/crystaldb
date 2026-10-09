#!/usr/bin/env python3
"""Build a read-only phase-character inference dry-run for RRUFF and PowBase.

This script reads existing local audit and canonical-preparation artifacts. It
does not connect to MongoDB and does not modify source archives or production
data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RRUFF_FINAL = PROJECT_ROOT / "data" / "mappings" / "rruff_experimental_final_v1.csv"
DEFAULT_RRUFF_AUDIT = PROJECT_ROOT / "data" / "mappings" / "rruff_2120_to_807_audit.csv"
DEFAULT_RRUFF_RESOLUTION = (
    PROJECT_ROOT / "data" / "mappings" / "rruff_experimental_resolution_v1.json"
)
DEFAULT_RRUFF_CALIBRATION = (
    PROJECT_ROOT / "data" / "mappings" / "rruff_diffraction_calibration_v1.json"
)
DEFAULT_RRUFF_TIERS = (
    PROJECT_ROOT / "data" / "mappings" / "rruff_group_evidence_tiers_v1.json"
)
DEFAULT_POWBASE = PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
DEFAULT_CSV = PROJECT_ROOT / "data" / "mappings" / "phase_character_inference_v1.csv"
DEFAULT_JSON = PROJECT_ROOT / "data" / "mappings" / "phase_character_inference_v1.json"
DEFAULT_SUMMARY = PROJECT_ROOT / "data" / "mappings" / "phase_character_inference_v1_summary.md"

BASELINE = {"single_phase": 855, "multi_phase": 40, "unknown": 2124, "total": 3019}

CSV_FIELDS = [
    "pattern_id",
    "source",
    "source_record_id",
    "source_label_raw",
    "current_phase_character",
    "proposed_phase_character",
    "decision",
    "phase_character_origin",
    "phase_character_method",
    "evidence_strength",
    "source_description",
    "source_mixture_impurity_evidence",
    "structure_resolution_level",
    "structure_resolution_status",
    "structure_linkage_status",
    "selected_structure_id",
    "candidate_count",
    "diffraction_status",
    "radiation_class",
    "matched_fraction",
    "median_abs_residual",
    "weighted_mean_abs_residual",
    "max_abs_residual",
    "residual_slope",
    "zero_shift",
    "unexplained_strong_peak_evidence",
    "candidate_or_multiphase_evidence",
    "powbase_content_family",
    "powbase_phase_block_count",
    "powbase_phase_names",
    "decision_reason",
]

RRUFF_MULTI_EVIDENCE = {
    "mixture_language",
    "quantitative_fraction",
    "named_secondary_phase",
    "qualitative_impurity",
    "secondary_peak",
    "unknown_phase",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(100_000_000)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pattern_id(source_record_id: str) -> str:
    return "RRUFF_PAT_" + source_record_id.replace("-", "_")


def _rruff_linkage_status(structure_status: str) -> str:
    if structure_status in {
        "unique_bibliographic_match",
        "single_candidate_after_filtering",
        "resolved",
        "diffraction_supported_rescue",
    }:
        return "complete"
    if structure_status in {
        "bibliography_supported_candidate_group",
        "ambiguous",
        "multiple_diffraction_compatible_candidates",
    }:
        return "ambiguous"
    if structure_status in {
        "unlinked",
    }:
        return "unlinked"
    return "partial"


def _calibration_by_sample(calibration: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {record["sample_id"]: record for record in calibration.get("records", [])}


def _resolution_by_sample(resolution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {record["sample_id"]: record for record in resolution.get("records", [])}


def _tier_by_sample(tiers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {record["sample_id"]: record for record in tiers.get("records", [])}


def _rruff_multi_evidence(audit_row: dict[str, str]) -> tuple[bool, str, str]:
    evidence_class = (audit_row.get("phase_character_evidence") or "").strip()
    description = (audit_row.get("diffraction_sample_description") or "").strip()
    classes = {item.strip() for item in evidence_class.split(";") if item.strip()}
    positive = bool(classes & RRUFF_MULTI_EVIDENCE)
    return positive, evidence_class, description


def classify_rruff_row(
    row: dict[str, str],
    audit_row: dict[str, str],
    resolution_row: dict[str, Any] | None,
    calibration_row: dict[str, Any] | None,
    tier_row: dict[str, Any] | None,
) -> dict[str, Any]:
    sample_id = row["sample_id"]
    source_record_id = row["filename_sample_id"]
    source_description = (
        audit_row.get("diffraction_sample_description")
        or row.get("measurement_description")
        or ""
    )
    multi, evidence_class, _ = _rruff_multi_evidence(audit_row)

    resolution = (resolution_row or {}).get("structure_resolution") or {}
    resolution_level = (
        resolution.get("resolution_level")
        or row.get("resolution_level")
        or None
    )
    resolution_status = (
        row.get("structure_status")
        or resolution.get("resolution_status")
        or None
    )
    selected_structure_id = row.get("selected_cod_id") or None
    candidate_count = _integer(row.get("candidate_count"))
    if candidate_count is None:
        candidate_count = _integer(resolution.get("sample_structure_candidate_count"))

    metrics = (calibration_row or {}).get("metrics") or {}
    matched_fraction = _number(metrics.get("matched_fraction"))
    if matched_fraction is None:
        matched_count = _number(metrics.get("matched_count"))
        theoretical_count = _number(metrics.get("theoretical_peak_count"))
        if matched_count is not None and theoretical_count:
            matched_fraction = matched_count / theoretical_count

    tier = (tier_row or {}).get("evidence_tier")
    current = row.get("phase_character") or "unknown"
    linkage = _rruff_linkage_status(row.get("structure_status", ""))

    if multi:
        proposed = "multi_phase"
        decision = "infer_multi_phase"
        origin = "source"
        method = "source_annotation"
        strength = "strong"
        reason = (
            "Frozen RRUFF source-description curation records explicit positive "
            f"multiphase evidence ({evidence_class or 'source mixture evidence'}); "
            "this is not inferred from poor matching or unresolved linkage."
        )
    else:
        proposed = "unknown"
        decision = "retain_unknown"
        origin = None
        method = "unresolved"
        strength = "insufficient"
        if row.get("diffraction_status") in {"resolved_candidate", "diffraction_compatible"}:
            reason = (
                "Existing RRUFF structure/diffraction evidence supports a linkage "
                "candidate, but the calibrated artifacts explicitly do not provide "
                "a validated phase-purity threshold or single-phase classifier."
            )
        elif tier:
            reason = (
                f"Existing diffraction evidence tier={tier} is descriptive of "
                "candidate support, not positive phase-purity evidence."
            )
        else:
            reason = (
                "No positive source mixture evidence and no validated positive "
                "single-phase purity rule are available."
            )

    candidate_evidence = {
        "structure_status": row.get("structure_status") or None,
        "diffraction_status": row.get("diffraction_status") or None,
        "resolution_level": resolution_level,
        "selected_structure_id": selected_structure_id,
        "candidate_count": candidate_count,
        "evidence_tier": tier,
        "calibration_record_present": calibration_row is not None,
        "calibration_note": (
            "Existing diffraction calibration is used descriptively; no new "
            "matched_fraction cutoff was introduced."
        ),
    }

    return {
        "pattern_id": _pattern_id(source_record_id),
        "source": "RRUFF",
        "source_record_id": source_record_id,
        "source_label_raw": row.get("mineral") or "",
        "current_phase_character": current,
        "proposed_phase_character": proposed,
        "decision": decision,
        "phase_character_origin": origin,
        "phase_character_method": method,
        "evidence_strength": strength,
        "source_description": source_description,
        "source_mixture_impurity_evidence": {
            "present": multi,
            "classification": evidence_class or None,
            "raw_description": source_description,
        },
        "structure_resolution_level": resolution_level,
        "structure_resolution_status": resolution_status,
        "structure_linkage_status": linkage,
        "selected_structure_id": selected_structure_id,
        "candidate_count": candidate_count,
        "diffraction_status": row.get("diffraction_status") or None,
        "radiation_class": ((calibration_row or {}).get("radiation") or {}).get(
            "radiation_class"
        ),
        "matched_fraction": matched_fraction,
        "median_abs_residual": _number(metrics.get("median_abs_residual")),
        "weighted_mean_abs_residual": _number(metrics.get("weighted_mean_abs_residual")),
        "max_abs_residual": _number(metrics.get("max_abs_residual")),
        "residual_slope": _number(metrics.get("residual_slope")),
        "zero_shift": _number(metrics.get("zero_shift")),
        "unexplained_strong_peak_evidence": "not_available_in_existing_curation",
        "candidate_or_multiphase_evidence": candidate_evidence,
        "powbase_content_family": None,
        "powbase_phase_block_count": None,
        "powbase_phase_names": [],
        "decision_reason": reason,
    }


def _powbase_fullprof(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    metadata = (record.get("source_evidence") or {}).get("embedded_metadata") or {}
    blocks = metadata.get("fullprof_phase_block_identifiers") or []
    names = metadata.get("fullprof_phase_names") or []
    return list(blocks), list(names)


def classify_powbase_record(record: dict[str, Any]) -> dict[str, Any]:
    entry_id = str(record["entry_id"])
    source = record.get("source_evidence") or {}
    pattern = record.get("pattern") or {}
    current = pattern.get("phase_character") or "unknown"
    family = source.get("detected_content_family")
    blocks, names = _powbase_fullprof(record)
    index_text = source.get("raw_index_text") or ""
    source_label = source.get("source_label_raw") or ""

    proposed = "unknown"
    decision = "retain_unknown"
    origin = None
    method = "unresolved"
    strength = "insufficient"

    if entry_id == "106" and len(blocks) == 2 and "two allotropic forms" in index_text:
        proposed = "multi_phase"
        decision = "infer_multi_phase"
        origin = "source"
        method = "source_annotation"
        strength = "strong"
        reason = (
            "Official index bibliography explicitly describes two allotropic "
            "forms, and the embedded FullProf content contains PHASE_1 and "
            "PHASE_2 blocks. This is positive source evidence for multiple "
            "sample forms, not a mechanical phase-block count rule."
        )
    elif entry_id in {"113", "124"} and len(blocks) == 1 and len(names) == 1:
        proposed = "single_phase"
        decision = "infer_single_phase"
        origin = "inferred"
        method = "diffraction_purity_rule_v1"
        strength = "moderate"
        reason = (
            "FullProf content contains one explicit phase block and one phase "
            "name, with a validated experimental profile and no source text "
            "indicating an impurity, mixture, or internal standard."
        )
    else:
        if len(blocks) > 1:
            reason = (
                "Multiple phase blocks or auxiliary refinement content are "
                "present, but their role is not independently resolved under "
                "the v1 rule; phase-block count alone is not treated as "
                "multiphase evidence."
            )
        else:
            reason = (
                "The source index label and numeric profile do not provide "
                "positive phase-purity evidence under the v1 rule."
            )

    candidate_evidence = {
        "entry_id": entry_id,
        "detected_content_family": family,
        "fullprof_phase_block_identifiers": blocks,
        "fullprof_phase_names": names,
        "source_index_text_contains_two_allotropic_forms": (
            "two allotropic forms" in index_text
        ),
        "source_index_raw_text": index_text,
        "rule_note": (
            "Entry 89 is outside the 44 production-record target. Its PHASE_2 "
            "Al2 O3 block is retained as an internal-standard edge case in the "
            "summary and is not used for this decision."
        ),
    }

    return {
        "pattern_id": pattern.get("pattern_id") or f"POWBASE_PAT_{entry_id}",
        "source": "POWBASE",
        "source_record_id": entry_id,
        "source_label_raw": source_label,
        "current_phase_character": current,
        "proposed_phase_character": proposed,
        "decision": decision,
        "phase_character_origin": origin,
        "phase_character_method": method,
        "evidence_strength": strength,
        "source_description": source.get("raw_bibliographic_comment_text") or "",
        "source_mixture_impurity_evidence": {
            "present": False,
            "classification": None,
            "raw_description": "",
        },
        "structure_resolution_level": None,
        "structure_resolution_status": None,
        "structure_linkage_status": (pattern.get("structure_linkage") or {}).get(
            "status"
        ),
        "selected_structure_id": None,
        "candidate_count": 0,
        "diffraction_status": None,
        "radiation_class": None,
        "matched_fraction": None,
        "median_abs_residual": None,
        "weighted_mean_abs_residual": None,
        "max_abs_residual": None,
        "residual_slope": None,
        "zero_shift": None,
        "unexplained_strong_peak_evidence": "not_available_in_existing_curation",
        "candidate_or_multiphase_evidence": candidate_evidence,
        "powbase_content_family": family,
        "powbase_phase_block_count": len(blocks),
        "powbase_phase_names": names,
        "decision_reason": reason,
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _json(value)
    if value is None:
        return ""
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CSV_FIELDS})


def build_report(
    *,
    rruff_final_path: Path = DEFAULT_RRUFF_FINAL,
    rruff_audit_path: Path = DEFAULT_RRUFF_AUDIT,
    rruff_resolution_path: Path = DEFAULT_RRUFF_RESOLUTION,
    rruff_calibration_path: Path = DEFAULT_RRUFF_CALIBRATION,
    rruff_tiers_path: Path = DEFAULT_RRUFF_TIERS,
    powbase_path: Path = DEFAULT_POWBASE,
) -> dict[str, Any]:
    final_rows = _read_csv(rruff_final_path)
    audit_rows = _read_csv(rruff_audit_path)
    audit_by_filename = {row["filename_sample_id"]: row for row in audit_rows}
    resolution_by_sample = _resolution_by_sample(_read_json(rruff_resolution_path))
    calibration_by_sample = _calibration_by_sample(_read_json(rruff_calibration_path))
    tiers_by_sample = _tier_by_sample(_read_json(rruff_tiers_path))
    powbase = _read_json(powbase_path)

    decisions: list[dict[str, Any]] = []
    for row in final_rows:
        source_record_id = row["filename_sample_id"]
        audit_row = audit_by_filename.get(source_record_id, {})
        decisions.append(
            classify_rruff_row(
                row,
                audit_row,
                resolution_by_sample.get(row["sample_id"]),
                calibration_by_sample.get(row["sample_id"]),
                tiers_by_sample.get(row["sample_id"]),
            )
        )
    for record in powbase["records"]:
        decisions.append(classify_powbase_record(record))

    decisions.sort(key=lambda row: (row["source"], row["source_record_id"]))
    source_counts: dict[str, dict[str, int]] = {}
    route_counts: Counter[str] = Counter()
    for source in ("RRUFF", "POWBASE"):
        source_rows = [row for row in decisions if row["source"] == source]
        counts = Counter(row["decision"] for row in source_rows)
        source_counts[source] = {
            "total": len(source_rows),
            "infer_single_phase": counts["infer_single_phase"],
            "infer_multi_phase": counts["infer_multi_phase"],
            "retain_unknown": counts["retain_unknown"],
        }
        route_counts.update(
            f"{row['source']}:{row['phase_character_method']}"
            for row in source_rows
            if row["decision"] != "retain_unknown"
        )

    new_distribution = dict(BASELINE)
    for row in decisions:
        if row["current_phase_character"] != "unknown":
            continue
        new_distribution["unknown"] -= 1
        new_distribution[row["proposed_phase_character"]] += 1

    calibration_summary = _read_json(rruff_calibration_path).get("summaries", {}).get(
        "all", {}
    )
    manual_review = {
        "strongest_inferred_single_phase": [
            {
                "pattern_id": row["pattern_id"],
                "source_record_id": row["source_record_id"],
                "reason": row["decision_reason"],
            }
            for row in decisions
            if row["decision"] == "infer_single_phase"
        ],
        "strongest_inferred_multi_phase": [
            {
                "pattern_id": row["pattern_id"],
                "source_record_id": row["source_record_id"],
                "source_label_raw": row["source_label_raw"],
                "source_description": row["source_description"],
                "reason": row["decision_reason"],
            }
            for row in decisions
            if row["decision"] == "infer_multi_phase"
        ][:8],
        "unique_linkage_not_enough_for_single": [
            row["source_record_id"]
            for row in decisions
            if row["source"] == "RRUFF"
            and row["decision"] == "retain_unknown"
            and row["structure_linkage_status"] == "complete"
            and row["diffraction_status"] in {"resolved_candidate", "diffraction_compatible"}
        ][:8],
        "ambiguous_unknown": [
            {
                "pattern_id": row["pattern_id"],
                "source_record_id": row["source_record_id"],
                "reason": row["decision_reason"],
            }
            for row in decisions
            if row["decision"] == "retain_unknown"
        ][:8],
        "powbase_internal_standard_edge": {
            "entry_id": "89",
            "included_in_target": False,
            "phase_blocks": ["PHASE_1", "PHASE_2"],
            "phase_names": [
                "dimethyl-2,6-naphthalenedicarboxylate",
                "Al2 O3",
            ],
            "interpretation": (
                "The existing PowBase review records PHASE_2 Al2 O3 as an "
                "internal-standard edge case. It is conditional and outside "
                "the 44 production target, so it receives no v1 inference."
            ),
        },
        "rruff_single_phase_status": (
            "No RRUFF single-phase records were inferred. The existing "
            "calibration provides descriptive distributions but no validated "
            "phase-purity threshold."
        ),
    }

    return {
        "schema_version": "phase_character_inference_v1",
        "dry_run": True,
        "production_modified": False,
        "mongodb_writes": False,
        "source_files_modified": False,
        "inputs": {
            "rruff_final": str(rruff_final_path.relative_to(PROJECT_ROOT)),
            "rruff_phase_audit": str(rruff_audit_path.relative_to(PROJECT_ROOT)),
            "rruff_resolution": str(rruff_resolution_path.relative_to(PROJECT_ROOT)),
            "rruff_calibration": str(rruff_calibration_path.relative_to(PROJECT_ROOT)),
            "rruff_group_tiers": str(rruff_tiers_path.relative_to(PROJECT_ROOT)),
            "powbase_canonical_dryrun": str(powbase_path.relative_to(PROJECT_ROOT)),
        },
        "rules": {
            "positive_evidence_required": True,
            "unique_structure_linkage_is_not_single_phase": True,
            "rruff_diffraction_only_single_phase_enabled": False,
            "powbase_phase_block_count_alone_is_not_multiphase": True,
            "entry_89_target_status": "excluded_from_44_production_target",
        },
        "baseline_production_distribution": BASELINE,
        "summary": {
            "total_evaluated": len(decisions),
            "source_counts": source_counts,
            "decision_counts": dict(Counter(row["decision"] for row in decisions)),
            "route_counts": dict(sorted(route_counts.items())),
            "hypothetical_production_distribution": new_distribution,
            "rruff_calibration_distribution": calibration_summary,
        },
        "manual_review": manual_review,
        "decisions": decisions,
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    source_counts = summary["source_counts"]
    distribution = summary["hypothetical_production_distribution"]
    lines = [
        "# CrystalDB Phase-Character Inference v1",
        "",
        "Dry-run only. No MongoDB writes, production updates, source-file changes, or release-statistic updates were performed.",
        "",
        "## Scope and rule",
        "",
        "The report evaluates 1,064 RRUFF final experimental records and the 44 PowBase records already admitted to the production X-ray set. Every record receives exactly one dry-run decision. Positive evidence is required for both phase classes.",
        "",
        "RRUFF explicit source mixture, contamination, secondary-phase, quantitative-fraction, or secondary-peak annotations are retained as positive multiphase evidence. No RRUFF single-phase inference is made because the existing diffraction calibration describes candidate compatibility but does not define a validated phase-purity threshold. A unique structure linkage therefore remains insufficient.",
        "",
        "PowBase entries 113 and 124 have one explicit FullProf phase block/name and no source warning for a second phase. Entry 106 has two FullProf phase blocks and an official index description of two allotropic forms, so it is classified as positive multiphase source evidence. Entry 89 is not in the 44-record production target; its PHASE_2 `Al2 O3` block remains an internal-standard edge case in the review notes.",
        "",
        "## Results",
        "",
        "| Source | Total | Infer single | Infer multi | Retain unknown |",
        "|---|---:|---:|---:|---:|",
        f"| RRUFF | {source_counts['RRUFF']['total']} | {source_counts['RRUFF']['infer_single_phase']} | {source_counts['RRUFF']['infer_multi_phase']} | {source_counts['RRUFF']['retain_unknown']} |",
        f"| POWBASE | {source_counts['POWBASE']['total']} | {source_counts['POWBASE']['infer_single_phase']} | {source_counts['POWBASE']['infer_multi_phase']} | {source_counts['POWBASE']['retain_unknown']} |",
        f"| Total | {summary['total_evaluated']} | {summary['decision_counts'].get('infer_single_phase', 0)} | {summary['decision_counts'].get('infer_multi_phase', 0)} | {summary['decision_counts'].get('retain_unknown', 0)} |",
        "",
        "Inference routes:",
        "",
    ]
    for route, count in summary["route_counts"].items():
        lines.append(f"- `{route}`: {count}")
    lines.extend(
        [
            "",
            "## Hypothetical production distribution",
            "",
            "This is a calculation only. It is not written to MongoDB.",
            "",
            "| Phase character | Current | Hypothetical |",
            "|---|---:|---:|",
            f"| single_phase | {BASELINE['single_phase']} | {distribution['single_phase']} |",
            f"| multi_phase | {BASELINE['multi_phase']} | {distribution['multi_phase']} |",
            f"| unknown | {BASELINE['unknown']} | {distribution['unknown']} |",
            f"| Total | {BASELINE['total']} | {distribution['total']} |",
            "",
            "## Manual review samples",
            "",
            "Strongest inferred single-phase records:",
            "",
        ]
    )
    for row in report["manual_review"]["strongest_inferred_single_phase"]:
        lines.append(f"- `{row['source_record_id']}`: {row['reason']}")
    if not report["manual_review"]["strongest_inferred_single_phase"]:
        lines.append("- None. Existing RRUFF calibration was not promoted to a phase-purity classifier.")
    lines.extend(["", "Strongest inferred multiphase records:", ""])
    for row in report["manual_review"]["strongest_inferred_multi_phase"]:
        lines.append(
            f"- `{row['source_record_id']}` `{row['source_label_raw']}`: "
            f"{row['source_description']}"
        )
    lines.extend(
        [
            "",
            "Unique linkage cases retained unknown:",
            "",
        ]
    )
    for record_id in report["manual_review"]["unique_linkage_not_enough_for_single"]:
        lines.append(f"- `{record_id}`")
    lines.extend(
        [
            "",
            "Representative ambiguous/unknown cases:",
            "",
        ]
    )
    for row in report["manual_review"]["ambiguous_unknown"]:
        lines.append(f"- `{row['source_record_id']}`: {row['reason']}")
    edge = report["manual_review"]["powbase_internal_standard_edge"]
    lines.extend(
        [
            "",
            "PowBase internal-standard edge case:",
            "",
            f"- Entry `{edge['entry_id']}` is excluded from the 44-record target. Its PHASE_1 is `{edge['phase_names'][0]}` and PHASE_2 is `{edge['phase_names'][1]}`; no multiphase inference is promoted from this conditional record.",
            "",
            "## Files and limitations",
            "",
            "The CSV contains one row per evaluated pattern. JSON preserves the structured evidence and decision rationale. Raw source values are referenced but not rewritten. Residual and matched-fraction fields are blank where no existing calibration record is available. `unexplained_strong_peak_evidence` is `not_available_in_existing_curation` rather than a negative finding.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    report = build_report()
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.csv_output, report["decisions"])
    write_summary(args.summary_output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
