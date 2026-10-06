"""Run the frozen diffraction validation for the current 67 XY samples.

This is a read-only, targeted validation artifact. It reuses the existing
diffraction functions and calibration annotations through
review_high_priority_35_diffraction_v1.py, but reads the fixed 67-sample
experimental-XY audit and the existing rescue candidate-detail table.

It does not search COD, download CIFs, write MongoDB, or modify historical
mapping/manuscript/curated outputs.
"""

from __future__ import annotations

import ast
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from crystaldb.mongo import get_database  # noqa: E402
import review_high_priority_35_diffraction_v1 as frozen_review  # noqa: E402


REVIEW_DIR = PROJECT_ROOT / "data" / "mappings" / "rescue_review_v1"
XY_AUDIT_FILE = REVIEW_DIR / "diffraction_needed_160_xy_audit.csv"
CANDIDATE_DETAILS_FILE = REVIEW_DIR / "rruff_rescue_candidate_details_v1.csv"
CALIBRATION_FILE = PROJECT_ROOT / "data" / "mappings" / "rruff_diffraction_calibration_v1.json"
FROZEN_ENGINE_FILE = PROJECT_ROOT / "scripts" / "annotate_rruff_group_diffraction_v1.py"

OUTPUT_CSV = REVIEW_DIR / "diffraction_needed_67_validation.csv"
OUTPUT_MD = REVIEW_DIR / "diffraction_needed_67_validation.md"

TARGET_STATUS = "experimental_xy_available"
FINAL_STATUSES = (
    "diffraction_supported_rescue",
    "multiple_diffraction_compatible_candidates",
    "diffraction_inconclusive",
    "diffraction_incompatible",
)

CSV_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "candidate_cod_id",
    "candidate_mineral_name",
    "candidate_formula",
    "cif_file_path",
    "prior_structure_status",
    "prior_chemistry_status",
    "prior_space_group_status",
    "prior_cell_status",
    "xy_available",
    "xy_source_collection",
    "measurement_id",
    "experimental_description",
    "experimental_point_count",
    "experimental_peak_count",
    "raw_profile_count",
    "processed_profile_count",
    "dif_available",
    "radiation_class",
    "validation_wavelength",
    "implied_wavelength_median",
    "implied_wavelength_mad",
    "generated_reflection_count",
    "theoretical_peak_count",
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
    "candidate_diffraction_status",
    "candidate_evaluation_error",
    "candidate_separability_available",
    "candidate_separability_pair_count",
    "best_candidate_cod_id",
    "runner_up_candidate_cod_id",
    "weighted_residual_gap",
    "best_runner_up_separation_median_nearest_difference",
    "best_runner_up_separation_bin",
    "candidate_count_total",
    "candidate_count_evaluable",
    "candidate_count_diffraction_compatible",
    "final_status",
    "reason",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def target_xy_rows() -> list[dict[str, str]]:
    rows = [
        row
        for row in read_csv(XY_AUDIT_FILE)
        if row.get("xy_origin_status", "").strip() == TARGET_STATUS
    ]
    sample_ids = [row.get("sample_id", "").strip() for row in rows]
    if len(rows) != 67:
        raise RuntimeError(f"Expected 67 experimental XY rows, found {len(rows)}")
    if not all(sample_ids):
        raise RuntimeError("The 67-row XY audit contains a blank sample_id")
    if len(set(sample_ids)) != 67:
        raise RuntimeError("The 67-row XY audit contains duplicate sample_id values")
    filename_ids = [row.get("filename_sample_id", "").strip() for row in rows]
    if not all(filename_ids):
        raise RuntimeError("The 67-row XY audit contains a blank filename_sample_id")
    if len(set(filename_ids)) != 67:
        raise RuntimeError(
            "The 67-row XY audit contains duplicate filename_sample_id values"
        )
    return sorted(rows, key=lambda row: row["sample_id"])


def candidate_rows_for_targets(
    target_ids: set[str],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(CANDIDATE_DETAILS_FILE):
        sample_id = row.get("sample_id", "").strip()
        if sample_id in target_ids:
            grouped[sample_id].append(row)

    missing = sorted(target_ids - set(grouped))
    if missing:
        raise RuntimeError(
            "No existing candidate-detail rows for: " + ", ".join(missing)
        )

    duplicate_keys = [
        (row.get("sample_id", "").strip(), row.get("cod_id", "").strip())
        for rows in grouped.values()
        for row in rows
    ]
    if len(duplicate_keys) != len(set(duplicate_keys)):
        raise RuntimeError("Duplicate sample_id/COD candidate pairs found")

    for sample_id in grouped:
        grouped[sample_id].sort(key=lambda row: row.get("cod_id", "").strip())
        for row in grouped[sample_id]:
            cod_id = row.get("cod_id", "").strip()
            cif_path = row.get("cif_file_path", "").strip()
            if not cod_id:
                raise RuntimeError(f"Missing COD ID for candidate in {sample_id}")
            if not cif_path:
                raise RuntimeError(f"Missing CIF path for {sample_id} / {cod_id}")
            path = PROJECT_ROOT / cif_path.replace("/", "\\")
            if not path.is_file():
                raise RuntimeError(
                    f"Missing local CIF for {sample_id} / {cod_id}: {path}"
                )
            if row.get("candidate_parse_status", "").strip() != "ok":
                raise RuntimeError(
                    f"Candidate CIF is not parse-ok for {sample_id} / {cod_id}"
                )
    return grouped


def valid_xy(document: dict[str, Any] | None) -> bool:
    xrd = (document or {}).get("xrd") or {}
    two_theta = xrd.get("two_theta") or []
    intensity = xrd.get("intensity") or []
    return bool(two_theta) and bool(intensity) and len(two_theta) == len(intensity)


def load_compatibility_engine() -> dict[str, Any]:
    """Load the frozen engine with a Gemmi API/setting compatibility shim.

    The frozen code calls ``determine_and_set_spacegroup()`` without the
    explicit order argument required by the installed Gemmi 0.7.5. The
    in-memory source patch supplies the historical ``S.H2`` order and, for
    CIFs whose setting suffix is not recognized, falls back to the standard
    space group identified by the CIF's IT number. No diffraction algorithm,
    calibration, or threshold is changed.
    """

    source = FROZEN_ENGINE_FILE.read_text(encoding="utf-8").lstrip("\ufeff")
    source = source.replace(
        "structure.determine_and_set_spacegroup()",
        'structure.determine_and_set_spacegroup("S.H2")',
    )
    source = source.replace(
        """    if spacegroup is None:
        raise RuntimeError(
            "Unable to determine space group."
        )
""",
        """    if spacegroup is None:
        spacegroup = gemmi.find_spacegroup_by_number(
            structure.spacegroup_number
        )

    if spacegroup is None:
        raise RuntimeError(
            "Unable to determine space group."
        )
""",
    )
    tree = ast.parse(source, filename=str(FROZEN_ENGINE_FILE))
    constants = {
        "CU_WAVELENGTH",
        "MO_WAVELENGTH",
        "TOP_THEORETICAL",
        "INITIAL_WINDOW",
        "FINAL_WINDOW",
        "SMOOTH_RADIUS",
        "MIN_EXPERIMENTAL_INTENSITY",
        "MIN_PEAK_SEPARATION",
        "MAX_EXPERIMENTAL_PEAKS",
    }
    nodes: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            nodes.append(node)
            continue
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & constants:
                nodes.append(node)
    namespace: dict[str, Any] = {"__name__": "_frozen_diffraction_engine_compat"}
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(module, str(FROZEN_ENGINE_FILE), "exec"), namespace)
    required = {
        "normalize",
        "detect_experimental_peaks",
        "derive_validation_wavelength",
        "calculate_reflections",
        "summarize_candidate",
        "theoretical_separation",
        "separation_bin",
    }
    missing = sorted(name for name in required if name not in namespace)
    if missing:
        raise RuntimeError(
            "Frozen diffraction engine compatibility load missing definitions: "
            + ", ".join(missing)
        )
    return namespace


def description(document: dict[str, Any] | None) -> str:
    return str(
        ((document or {}).get("metadata") or {}).get(
            "DIFFRACTION SAMPLE DESCRIPTION"
        )
        or ""
    ).strip()


def pick_confirmed_experimental_xy(
    database: Any,
    target: dict[str, str],
) -> dict[str, Any]:
    """Pick the already audited experimental measurement, RAW first.

    The population was classified in the preceding XY audit using source
    description metadata. This picker preserves that population and does not
    apply the narrower historical clean-description allow-list, so the three
    genuine powder descriptions with explicit mixture/contamination wording
    remain in the requested 67 samples.
    """

    sample_id = target["sample_id"].strip()
    filename_sample_id = target["filename_sample_id"].strip()
    raw = database.xy_raw.find_one(
        {"filename_sample_id": filename_sample_id},
        {
            "_id": 0,
            "sample_id": 1,
            "filename_sample_id": 1,
            "xrd": 1,
            "metadata": 1,
        },
    )
    processed = database.xy_processed.find_one(
        {"filename_sample_id": filename_sample_id},
        {
            "_id": 0,
            "sample_id": 1,
            "filename_sample_id": 1,
            "xrd": 1,
            "metadata": 1,
        },
    )

    candidates = [
        ("rruff.xy_raw", raw),
        ("rruff.xy_processed", processed),
    ]
    eligible = [
        (collection, document)
        for collection, document in candidates
        if document is not None and valid_xy(document)
    ]
    if not eligible:
        raise RuntimeError(
            f"No valid XY for audited experimental sample {sample_id} / "
            f"{filename_sample_id}"
        )

    collection, document = eligible[0]
    if str(document.get("sample_id") or "").strip() != sample_id:
        raise RuntimeError(
            f"XY sample mismatch for {filename_sample_id}: "
            f"expected {sample_id}, got {document.get('sample_id')}"
        )

    xrd = document.get("xrd") or {}
    raw_count = int((raw or {}).get("xrd", {}).get("point_count") or 0)
    processed_count = int((processed or {}).get("xrd", {}).get("point_count") or 0)
    if not raw_count and raw is not None:
        raw_count = len((raw.get("xrd") or {}).get("two_theta") or [])
    if not processed_count and processed is not None:
        processed_count = len((processed.get("xrd") or {}).get("two_theta") or [])

    return {
        "available": True,
        "collection": collection,
        "measurement_id": filename_sample_id,
        "description": description(document),
        "point_count": len(xrd.get("two_theta") or []),
        "x": [float(value) for value in xrd.get("two_theta") or []],
        "y": [float(value) for value in xrd.get("intensity") or []],
        "raw_profile_count": int(raw is not None),
        "processed_profile_count": int(processed is not None),
        "raw_point_count": raw_count,
        "processed_point_count": processed_count,
        "reason": "experimental_xy_audit_confirmed",
    }


def candidate_status(
    metrics: dict[str, Any] | None,
    compatibility: dict[str, Any] | None,
    error: str | None,
) -> str:
    return frozen_review._candidate_status(metrics, compatibility, error)


def sample_status(
    candidate_results: list[dict[str, Any]],
) -> tuple[str, str]:
    compatible = [
        item
        for item in candidate_results
        if item.get("candidate_diffraction_status") == "diffraction_compatible"
    ]
    if len(compatible) > 1:
        return (
            "multiple_diffraction_compatible_candidates",
            "More than one existing candidate is inside the calibrated "
            "same-radiation core compatibility envelope.",
        )
    if len(compatible) == 1:
        return (
            "diffraction_supported_rescue",
            "Exactly one existing candidate is inside the calibrated "
            "same-radiation core compatibility envelope.",
        )

    evaluated = [
        item
        for item in candidate_results
        if item.get("candidate_diffraction_status")
        in {"diffraction_inconclusive", "diffraction_incompatible"}
    ]
    if evaluated and all(
        item.get("candidate_diffraction_status") == "diffraction_incompatible"
        for item in evaluated
    ):
        return (
            "diffraction_incompatible",
            "All evaluable candidates produced zero one-to-one matches.",
        )
    return (
        "diffraction_inconclusive",
        "Diffraction metrics were obtained, but no candidate met the "
        "existing core compatibility envelope and the result is not a "
        "zero-match rejection.",
    )


def evaluate_candidate(
    source: dict[str, str],
    profile: dict[str, Any],
    dif: dict[str, Any],
    experimental_peaks: list[dict[str, Any]],
    radiation: dict[str, Any],
    engine: dict[str, Any],
    reference_records: dict[str, list[dict[str, Any]]],
    reflection_cache: dict[tuple[str, float, float, float], dict[str, Any]],
) -> dict[str, Any]:
    sample_id = source["sample_id"].strip()
    cod_id = source["cod_id"].strip()
    cif_path = source["cif_file_path"].strip()
    item: dict[str, Any] = {
        "sample_id": sample_id,
        "filename_sample_id": profile["measurement_id"],
        "candidate_cod_id": cod_id,
        "candidate_mineral_name": source.get("candidate_mineral_name", "").strip(),
        "candidate_formula": source.get("candidate_formula", "").strip(),
        "cif_file_path": cif_path,
        "prior_structure_status": source.get("original_status", "").strip(),
        "prior_chemistry_status": source.get("chemistry_status", "").strip(),
        "prior_space_group_status": source.get("sg_status", "").strip(),
        "prior_cell_status": source.get("cell_status", "").strip(),
        "xy_available": "true",
        "xy_source_collection": profile["collection"],
        "measurement_id": profile["measurement_id"],
        "experimental_description": profile["description"],
        "experimental_point_count": profile["point_count"],
        "experimental_peak_count": len(experimental_peaks),
        "raw_profile_count": profile["raw_profile_count"],
        "processed_profile_count": profile["processed_profile_count"],
        "dif_available": "true",
        "radiation_class": radiation.get("radiation_class", ""),
        "validation_wavelength": radiation.get("validation_wavelength", ""),
        "implied_wavelength_median": radiation.get(
            "implied_wavelength_median", ""
        ),
        "implied_wavelength_mad": radiation.get("implied_wavelength_mad", ""),
        "generated_reflection_count": "",
        "theoretical_peak_count": "",
        "matched_count": "",
        "matched_fraction": "",
        "median_abs_residual": "",
        "weighted_mean_abs_residual": "",
        "max_abs_residual": "",
        "residual_slope": "",
        "zero_shift": "",
        "same_radiation_reference_n": "",
        "core_three_inside_p95": "",
        "all_six_inside_p95": "",
        "minimum_core_compatibility": "",
        "candidate_diffraction_status": "evaluation_error",
        "candidate_evaluation_error": "",
        "_theoretical": None,
        "metrics": None,
    }
    try:
        path = PROJECT_ROOT / cif_path.replace("/", "\\")
        cache_key = (
            str(path.resolve()).casefold(),
            float(radiation["validation_wavelength"]),
            float(profile["x"][0]),
            float(profile["x"][-1]),
        )
        calculated = reflection_cache.get(cache_key)
        if calculated is None:
            calculated = engine["calculate_reflections"](
                path,
                radiation["validation_wavelength"],
                profile["x"][0],
                profile["x"][-1],
            )
            reflection_cache[cache_key] = calculated
        theoretical = calculated["top_reflections"]
        metrics = engine["summarize_candidate"](
            theoretical,
            experimental_peaks,
        )
        compatibility = frozen_review._compatibility_annotation(
            metrics,
            radiation["radiation_class"],
            reference_records,
        )
        status = candidate_status(metrics, compatibility, None)
        item.update(
            {
                "generated_reflection_count": calculated[
                    "total_reflection_count"
                ],
                "theoretical_peak_count": len(theoretical),
                "matched_count": metrics.get("matched_count"),
                "matched_fraction": metrics.get("matched_fraction"),
                "median_abs_residual": metrics.get("median_abs_residual"),
                "weighted_mean_abs_residual": metrics.get(
                    "weighted_mean_abs_residual"
                ),
                "max_abs_residual": metrics.get("max_abs_residual"),
                "residual_slope": metrics.get("residual_slope"),
                "zero_shift": metrics.get("zero_shift"),
                "same_radiation_reference_n": compatibility["reference_n"],
                "core_three_inside_p95": str(
                    compatibility["core_three_inside_p95"]
                ).lower(),
                "all_six_inside_p95": str(
                    compatibility["all_six_inside_p95"]
                ).lower(),
                "minimum_core_compatibility": compatibility[
                    "minimum_core_compatibility"
                ],
                "candidate_diffraction_status": status,
                "_theoretical": theoretical,
                "metrics": metrics,
                "_compatibility": compatibility,
            }
        )
    except Exception as exc:
        item["candidate_evaluation_error"] = f"{type(exc).__name__}: {exc}"
    return item


def public_candidate_row(
    item: dict[str, Any],
    separability: dict[str, Any],
    final_status: str,
    reason: str,
    candidate_total: int,
    evaluable_count: int,
    compatible_count: int,
) -> dict[str, Any]:
    output = {
        key: value
        for key, value in item.items()
        if not key.startswith("_") and key not in {"metrics"}
    }
    separation = separability.get("best_runner_up_separation") or {}
    output.update(
        {
            "candidate_separability_available": str(
                separability["available"]
            ).lower(),
            "candidate_separability_pair_count": separability["pair_count"],
            "best_candidate_cod_id": separability["best_candidate_cod_id"] or "",
            "runner_up_candidate_cod_id": separability[
                "runner_up_candidate_cod_id"
            ]
            or "",
            "weighted_residual_gap": (
                separability["weighted_residual_gap"]
                if separability["weighted_residual_gap"] is not None
                else ""
            ),
            "best_runner_up_separation_median_nearest_difference": separation.get(
                "median_nearest_difference",
                "",
            ),
            "best_runner_up_separation_bin": separability[
                "best_runner_up_separation_bin"
            ]
            or "",
            "candidate_count_total": candidate_total,
            "candidate_count_evaluable": evaluable_count,
            "candidate_count_diffraction_compatible": compatible_count,
            "final_status": final_status,
            "reason": reason,
        }
    )
    return output


def write_csv(rows: list[dict[str, Any]]) -> None:
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def md_value(value: Any) -> str:
    if value in (None, ""):
        return "null"
    return str(value).replace("|", "\\|")


def write_markdown(
    sample_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    counts: Counter[str],
    calculation_error_count: int,
) -> None:
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_sample[row["sample_id"]].append(row)

    lines = [
        "# Diffraction Validation for 67 Experimental-XY RRUFF Samples",
        "",
        "## Scope",
        "",
        "本文件只处理现有 `diffraction_needed_160_xy_audit.csv` 中标记为 "
        "`experimental_xy_available` 的 67 条样品。",
        "未处理 93 条 `calculated_only`，未重新搜索 COD、下载 CIF，未修改 "
        "807 curated、12 条 rescue-ready、177 条 DIF 外 final manifest、v2/v3、"
        "MongoDB 或正式 CrystalDB。",
        "",
        "## Existing Pipeline Reused",
        "",
        f"- Frozen engine: `{FROZEN_ENGINE_FILE.relative_to(PROJECT_ROOT).as_posix()}`",
        f"- Existing wrapper/calibration logic: `scripts/review_high_priority_35_diffraction_v1.py`",
        f"- Calibration: `{CALIBRATION_FILE.relative_to(PROJECT_ROOT).as_posix()}`",
        "- CIF -> theoretical reflections",
        "- experimental XY -> peak detection",
        "- one-to-one peak matching",
        "- zero-shift correction",
        "- median, weighted, maximum residual and residual slope",
        "- candidate separability for multi-candidate samples",
        "",
        "A compatibility shim was applied only for the installed Gemmi 0.7.5 "
        "API: the frozen no-argument space-group call was supplied its required "
        "order, and CIFs with an unrecognized setting suffix used the standard "
        "space group identified by the CIF IT number. This resolved a concrete "
        "runtime compatibility error without changing the diffraction algorithm, "
        "calibration, thresholds, or candidate inputs.",
        "",
        "The existing calibration and core compatibility rule were reused unchanged: "
        "a candidate is `diffraction_compatible` when the matched fraction, median "
        "absolute residual, and weighted mean absolute residual are all inside the "
        "existing same-radiation positive-reference P95 envelope.",
        "",
        "The 67-sample XY audit population is preserved exactly. RAW is preferred "
        "when a valid RAW profile exists; processed is used only as fallback. "
        "The original `DIFFRACTION SAMPLE DESCRIPTION` is retained, including "
        "experimental powder descriptions with mixture or contamination wording.",
        "",
        "## Summary",
        "",
        "| Metric | Samples |",
        "|---|---:|",
        f"| 67 total | {len(sample_rows)} |",
        f"| diffraction_supported_rescue | {counts['diffraction_supported_rescue']} |",
        f"| multiple_diffraction_compatible_candidates | {counts['multiple_diffraction_compatible_candidates']} |",
        f"| diffraction_inconclusive | {counts['diffraction_inconclusive']} |",
        f"| diffraction_incompatible | {counts['diffraction_incompatible']} |",
        f"| candidate calculation errors | {calculation_error_count} |",
        f"| samples with output | {len(sample_rows)} |",
        "",
        "## Sample Results",
        "",
        "| sample_id | filename_sample_id | candidate_count | evaluable | compatible | final_status | compatible COD IDs | reason |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for sample in sample_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_value(sample["sample_id"]),
                    md_value(sample["filename_sample_id"]),
                    md_value(sample["candidate_count_total"]),
                    md_value(sample["candidate_count_evaluable"]),
                    md_value(sample["candidate_count_diffraction_compatible"]),
                    md_value(sample["final_status"]),
                    md_value(sample["compatible_cod_ids"]),
                    md_value(sample["reason"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Candidate Metrics",
            "",
            "| sample_id | COD ID | candidate status | matched_count | median_residual | weighted_residual | max_residual | residual_slope | zero_shift | core P95 | separability | calculation error |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in candidate_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_value(row["sample_id"]),
                    md_value(row["candidate_cod_id"]),
                    md_value(row["candidate_diffraction_status"]),
                    md_value(row["matched_count"]),
                    md_value(row["median_abs_residual"]),
                    md_value(row["weighted_mean_abs_residual"]),
                    md_value(row["max_abs_residual"]),
                    md_value(row["residual_slope"]),
                    md_value(row["zero_shift"]),
                    md_value(row["core_three_inside_p95"]),
                    md_value(row["candidate_separability_available"]),
                    md_value(row["candidate_evaluation_error"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Exact Sources",
            "",
            f"- XY population: `{XY_AUDIT_FILE.relative_to(PROJECT_ROOT).as_posix()}` filtered by `xy_origin_status=experimental_xy_available`.",
            f"- Existing candidate details and local CIF paths: `{CANDIDATE_DETAILS_FILE.relative_to(PROJECT_ROOT).as_posix()}`.",
            "- Experimental XY: read-only MongoDB `rruff.xy_raw` and `rruff.xy_processed`.",
            "- Radiation provenance: read-only MongoDB `rruff.dif`, used only by the existing wavelength-derivation function.",
            f"- Calibration: `{CALIBRATION_FILE.relative_to(PROJECT_ROOT).as_posix()}`.",
            "",
            "All results are audit outputs only. No candidate was written as a final "
            "record and no historical mapping was changed.",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    targets = target_xy_rows()
    target_ids = {row["sample_id"] for row in targets}
    candidates_by_sample = candidate_rows_for_targets(target_ids)

    engine = load_compatibility_engine()
    calibration = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    reference_records = frozen_review._build_reference_values(calibration)
    database = get_database(database_name="rruff")
    reflection_cache: dict[tuple[str, float, float, float], dict[str, Any]] = {}

    sample_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    final_counts: Counter[str] = Counter()
    calculation_error_count = 0

    for index, target in enumerate(targets, start=1):
        sample_id = target["sample_id"]
        profile = pick_confirmed_experimental_xy(database, target)
        dif = database.dif.find_one({"sample_id": sample_id})
        if dif is None:
            raise RuntimeError(f"Missing DIF radiation provenance for {sample_id}")

        experimental_peaks = engine["detect_experimental_peaks"](
            profile["x"],
            engine["normalize"](profile["y"]),
        )
        radiation = engine["derive_validation_wavelength"](dif)

        source_candidates = []
        for source in candidates_by_sample[sample_id]:
            normalized = dict(source)
            normalized["sample_id"] = sample_id
            source_candidates.append(normalized)

        candidate_results = [
            evaluate_candidate(
                source,
                profile,
                dif,
                experimental_peaks,
                radiation,
                engine,
                reference_records,
                reflection_cache,
            )
            for source in source_candidates
        ]

        separability = frozen_review._evaluate_separability(
            candidate_results,
            engine,
        )
        final_status, reason = sample_status(candidate_results)
        if final_status not in FINAL_STATUSES:
            raise RuntimeError(f"Unexpected final status for {sample_id}: {final_status}")
        final_counts[final_status] += 1

        evaluable_count = sum(
            item.get("metrics") is not None for item in candidate_results
        )
        compatible_ids = [
            str(item["candidate_cod_id"])
            for item in candidate_results
            if item.get("candidate_diffraction_status")
            == "diffraction_compatible"
        ]
        compatible_count = len(compatible_ids)
        sample_rows.append(
            {
                "sample_id": sample_id,
                "filename_sample_id": profile["measurement_id"],
                "candidate_count_total": len(candidate_results),
                "candidate_count_evaluable": evaluable_count,
                "candidate_count_diffraction_compatible": compatible_count,
                "compatible_cod_ids": ",".join(compatible_ids),
                "final_status": final_status,
                "reason": reason,
            }
        )

        for item in candidate_results:
            if item.get("candidate_evaluation_error"):
                calculation_error_count += 1
            candidate_rows.append(
                public_candidate_row(
                    item,
                    separability,
                    final_status,
                    reason,
                    len(candidate_results),
                    evaluable_count,
                    compatible_count,
                )
            )

        print(
            f"[{index}/{len(targets)}] {sample_id}: {final_status} "
            f"candidates={len(candidate_results)} "
            f"evaluable={evaluable_count} compatible={compatible_count}",
            flush=True,
        )

    database.client.close()

    if len(sample_rows) != 67:
        raise RuntimeError(f"Expected 67 sample outputs, found {len(sample_rows)}")
    if len({row["sample_id"] for row in sample_rows}) != 67:
        raise RuntimeError("Sample output contains duplicate sample IDs")
    if len({row["filename_sample_id"] for row in sample_rows}) != 67:
        raise RuntimeError("Sample output contains duplicate filename_sample_id values")
    if sum(final_counts[status] for status in FINAL_STATUSES) != 67:
        raise RuntimeError(f"Final status total is not 67: {final_counts}")

    write_csv(candidate_rows)
    write_markdown(sample_rows, candidate_rows, final_counts, calculation_error_count)

    print("67 total =", len(sample_rows))
    for status in FINAL_STATUSES:
        print(f"{status} = {final_counts[status]}")
    print("candidate rows =", len(candidate_rows))
    print("candidate calculation errors =", calculation_error_count)
    print("CSV =", OUTPUT_CSV)
    print("MD =", OUTPUT_MD)


if __name__ == "__main__":
    main()
