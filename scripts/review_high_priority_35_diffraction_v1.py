from __future__ import annotations

import ast
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

from crystaldb.mongo import get_database


INPUT_ROOT = PROJECT_ROOT / "data" / "mappings" / "rescue_review_v1"
REVIEW_FILE = INPUT_ROOT / "high_priority_36_review.csv"
CALIBRATION_FILE = (
    PROJECT_ROOT / "data" / "mappings" / "rruff_diffraction_calibration_v1.json"
)
FROZEN_ENGINE_FILE = PROJECT_ROOT / "scripts" / "annotate_rruff_group_diffraction_v1.py"
OUTPUT_CSV = INPUT_ROOT / "high_priority_35_diffraction_validation.csv"
OUTPUT_MD = INPUT_ROOT / "high_priority_35_diffraction_validation.md"


CLEAN_EXPERIMENTAL_DESCRIPTIONS = {
    "Powder",
    "Powder, using Mo radiation",
    "Powder, cell parameters are from single crystal",
    "Powder using Cu radiation",
}

CORE_METRICS = (
    "matched_fraction",
    "median_abs_residual",
    "weighted_mean_abs_residual",
)

ALL_METRICS = (
    "matched_fraction",
    "median_abs_residual",
    "weighted_mean_abs_residual",
    "max_abs_residual",
    "abs_zero_shift",
    "abs_residual_slope",
)

METRIC_DIRECTIONS = {
    "matched_fraction": "higher",
    "median_abs_residual": "lower",
    "weighted_mean_abs_residual": "lower",
    "max_abs_residual": "lower",
    "abs_zero_shift": "lower",
    "abs_residual_slope": "lower",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load_frozen_diffraction_engine() -> dict[str, Any]:
    """Load only the frozen functions/constants, never the old batch runner."""

    source = FROZEN_ENGINE_FILE.read_text(encoding="utf-8").lstrip("\ufeff")
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
    namespace: dict[str, Any] = {"__name__": "_frozen_diffraction_engine"}
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
            "Frozen diffraction engine missing definitions: "
            + ", ".join(missing)
        )
    return namespace


def _valid_xy(doc: dict[str, Any]) -> bool:
    xrd = doc.get("xrd") or {}
    two_theta = xrd.get("two_theta") or []
    intensity = xrd.get("intensity") or []
    return bool(two_theta) and bool(intensity) and len(two_theta) == len(intensity)


def _description(doc: dict[str, Any]) -> str:
    return str(
        (doc.get("metadata") or {}).get("DIFFRACTION SAMPLE DESCRIPTION") or ""
    ).strip()


def _pick_experimental_xy(db: Any, sample_id: str) -> dict[str, Any]:
    """Prefer the historical clean RAW/processed linkage, RAW first."""

    raw_docs = list(db.xy_raw.find({"sample_id": sample_id}))
    processed_docs = list(db.xy_processed.find({"sample_id": sample_id}))
    all_docs = [
        ("rruff.xy_raw", doc)
        for doc in raw_docs
    ] + [
        ("rruff.xy_processed", doc)
        for doc in processed_docs
    ]

    eligible = [
        (collection, doc)
        for collection, doc in all_docs
        if _valid_xy(doc) and _description(doc) in CLEAN_EXPERIMENTAL_DESCRIPTIONS
    ]
    if eligible:
        eligible.sort(
            key=lambda item: (
                0 if item[0] == "rruff.xy_raw" else 1,
                str(item[1].get("filename_sample_id") or ""),
            )
        )
        collection, doc = eligible[0]
        xrd = doc.get("xrd") or {}
        return {
            "available": True,
            "collection": collection,
            "measurement_id": doc.get("filename_sample_id"),
            "description": _description(doc),
            "point_count": len(xrd.get("two_theta") or []),
            "x": [float(value) for value in xrd.get("two_theta") or []],
            "y": [float(value) for value in xrd.get("intensity") or []],
            "raw_profile_count": len(raw_docs),
            "processed_profile_count": len(processed_docs),
            "reason": "clean_experimental_allow_list",
        }

    valid_profiles = [
        (collection, doc)
        for collection, doc in all_docs
        if _valid_xy(doc)
    ]
    if valid_profiles:
        descriptions = sorted(
            {
                _description(doc)
                for _, doc in valid_profiles
            }
        )
        return {
            "available": False,
            "collection": None,
            "measurement_id": None,
            "description": "; ".join(descriptions),
            "point_count": 0,
            "x": [],
            "y": [],
            "raw_profile_count": len(raw_docs),
            "processed_profile_count": len(processed_docs),
            "reason": "profiles_present_but_not_clean_experimental",
        }

    return {
        "available": False,
        "collection": None,
        "measurement_id": None,
        "description": "",
        "point_count": 0,
        "x": [],
        "y": [],
        "raw_profile_count": len(raw_docs),
        "processed_profile_count": len(processed_docs),
        "reason": "no_valid_xy",
    }


def _extract_metric(metrics: dict[str, Any], metric_name: str) -> float | None:
    if metric_name == "abs_zero_shift":
        value = metrics.get("zero_shift")
        return abs(float(value)) if value is not None else None
    if metric_name == "abs_residual_slope":
        value = metrics.get("residual_slope")
        return abs(float(value)) if value is not None else None
    value = metrics.get(metric_name)
    return float(value) if value is not None else None


def _empirical_compatibility(
    value: float | None,
    references: list[float],
    direction: str,
) -> float | None:
    if value is None or not references:
        return None
    if direction == "higher":
        favorable = sum(reference <= value for reference in references)
    else:
        favorable = sum(reference >= value for reference in references)
    return favorable / len(references)


def _build_reference_values(
    calibration: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    primary = [
        record
        for record in calibration.get("records", [])
        if record.get("resolution_status") == "unique_bibliographic_match"
    ]
    by_radiation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in primary:
        radiation = (record.get("radiation") or {}).get("radiation_class")
        if radiation:
            by_radiation[radiation].append(record)
    return dict(by_radiation)


def _compatibility_annotation(
    metrics: dict[str, Any],
    radiation_class: str,
    reference_records: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    references = reference_records.get(radiation_class, [])
    percentiles: dict[str, float | None] = {}
    reference_n = len(references)
    for metric_name in ALL_METRICS:
        values = [
            extracted
            for record in references
            if (
                extracted := _extract_metric(
                    record.get("metrics") or {},
                    metric_name,
                )
            )
            is not None
        ]
        percentiles[metric_name] = _empirical_compatibility(
            _extract_metric(metrics, metric_name),
            values,
            METRIC_DIRECTIONS[metric_name],
        )
    marginal_inside = {
        metric_name: (
            value is not None and value >= 0.05
        )
        for metric_name, value in percentiles.items()
    }
    core_inside = bool(marginal_inside) and all(
        marginal_inside.get(metric_name, False)
        for metric_name in CORE_METRICS
    )
    all_inside = bool(marginal_inside) and all(
        marginal_inside.get(metric_name, False)
        for metric_name in ALL_METRICS
    )
    core_values = [
        value
        for metric_name, value in percentiles.items()
        if metric_name in CORE_METRICS and value is not None
    ]
    return {
        "reference_n": reference_n,
        "metric_percentiles": percentiles,
        "marginal_inside_p95": marginal_inside,
        "core_three_inside_p95": core_inside,
        "all_six_inside_p95": all_inside,
        "minimum_core_compatibility": min(core_values)
        if len(core_values) == len(CORE_METRICS)
        else None,
    }


def _candidate_status(
    metrics: dict[str, Any] | None,
    compatibility: dict[str, Any] | None,
    error: str | None,
) -> str:
    if error:
        return "evaluation_error"
    if not metrics:
        return "evaluation_error"
    if compatibility and compatibility.get("core_three_inside_p95"):
        return "diffraction_compatible"
    if metrics.get("matched_count", 0) == 0:
        return "diffraction_incompatible"
    return "diffraction_inconclusive"


def _evaluate_separability(
    candidate_results: list[dict[str, Any]],
    engine: dict[str, Any],
) -> dict[str, Any]:
    successful = [
        item
        for item in candidate_results
        if item.get("_theoretical")
    ]
    if len(successful) < 2:
        return {
            "available": False,
            "pair_count": 0,
            "best_candidate_cod_id": None,
            "runner_up_candidate_cod_id": None,
            "weighted_residual_gap": None,
            "best_runner_up_separation": None,
            "best_runner_up_separation_bin": None,
        }

    ranked = sorted(
        successful,
        key=lambda item: (
            item["metrics"].get("weighted_mean_abs_residual")
            if item["metrics"].get("weighted_mean_abs_residual") is not None
            else float("inf"),
            -float(item["metrics"].get("matched_fraction") or 0.0),
            str(item["candidate_cod_id"]),
        ),
    )
    best = ranked[0]
    runner = ranked[1]
    separation = engine["theoretical_separation"](
        best["_theoretical"],
        runner["_theoretical"],
    )
    separation["separability_bin"] = engine["separation_bin"](
        separation["median_nearest_difference"]
    )
    gap = (
        runner["metrics"].get("weighted_mean_abs_residual")
        - best["metrics"].get("weighted_mean_abs_residual")
    )
    return {
        "available": True,
        "pair_count": len(successful) * (len(successful) - 1) // 2,
        "best_candidate_cod_id": best["candidate_cod_id"],
        "runner_up_candidate_cod_id": runner["candidate_cod_id"],
        "weighted_residual_gap": gap,
        "best_runner_up_separation": separation,
        "best_runner_up_separation_bin": separation["separability_bin"],
    }


def _sample_status(
    profile: dict[str, Any],
    candidate_results: list[dict[str, Any]],
) -> tuple[str, str]:
    if not profile.get("available"):
        if profile.get("reason") == "profiles_present_but_not_clean_experimental":
            return (
                "no_diffraction_available",
                "XY exists but the profile description is calculated rather "
                "than a clean experimental powder profile.",
            )
        return (
            "no_diffraction_available",
            "No usable clean experimental XY was found in raw or processed linkage.",
        )

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


def _write_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "sample_id",
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
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(
    sample_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    summary: dict[str, int],
) -> None:
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_sample[row["sample_id"]].append(row)

    lines = [
        "# High-Priority Rescue Diffraction Validation: 35 RRUFF Samples",
        "",
        "## Scope",
        "",
        "This audit is restricted to the 35 samples marked "
        "`diffraction_validation_needed` in "
        "`high_priority_36_review.csv`.",
        "It uses existing raw/processed RRUFF XY, existing DIF records, "
        "and the already downloaded local CIF candidates only.",
        "No COD search, CIF download, MongoDB write, 807-data modification, "
        "v2/v3 modification, or formal CrystalDB update was performed.",
        "",
        "## Existing Pipeline Reused",
        "",
        "The diffraction functions and fixed settings were loaded from the "
        "function definitions in `scripts/annotate_rruff_group_diffraction_v1.py`; "
        "the historical group batch body was not executed.",
        "",
        "- theoretical reflections: CIF -> Gemmi structure factors",
        "- experimental peaks: smoothing, local maxima, intensity and separation filters",
        "- matching: one-to-one assignment",
        "- zero shift: weighted median from the initial window",
        "- final matching window: 0.15 degrees",
        "- metrics: matched count, matched fraction, median/weighted/max residual, "
        "residual slope, zero shift",
        "- candidate separability: existing theoretical peak nearest-difference calculation",
        "",
        "The experimental XY allow-list is the same frozen clean allow-list used "
        "by `build_rruff_experimental_resolution_v1.py`. Profiles described as "
        "`Single crystal, powder profile is calculated` are not treated as "
        "experimental XY.",
        "",
        "## Status Rule",
        "",
        "For an evaluable candidate, `diffraction_compatible` means that all "
        "three existing core metrics are inside the existing same-radiation "
        "positive-reference P95 envelope: matched fraction, median absolute "
        "residual, and weighted mean absolute residual. This reproduces the "
        "existing `core_three_inside_p95` annotation logic. The envelope is "
        "descriptive calibration evidence, not a new scientific threshold.",
        "",
        "- one compatible candidate: `diffraction_supported_rescue`",
        "- more than one compatible candidate: `multiple_diffraction_compatible_candidates`",
        "- metrics obtained but no compatible candidate and not all zero-match: "
        "`diffraction_inconclusive`",
        "- all evaluable candidates have zero matches: `diffraction_incompatible`",
        "- no clean experimental XY: `no_diffraction_available`",
        "",
        "These statuses are audit labels only. They do not create a final record "
        "and do not alter the curated 807, v2/v3, MongoDB, or formal CrystalDB.",
        "",
        "## Summary",
        "",
        "| Metric | Samples |",
        "|---|---:|",
        f"| 35 total | {summary['total']} |",
        f"| with_usable_experimental_xy | {summary['with_usable_experimental_xy']} |",
        f"| no_diffraction_available | {summary['no_diffraction_available']} |",
        f"| diffraction_supported_rescue | {summary['diffraction_supported_rescue']} |",
        f"| multiple_diffraction_compatible_candidates | "
        f"{summary['multiple_diffraction_compatible_candidates']} |",
        f"| diffraction_inconclusive | {summary['diffraction_inconclusive']} |",
        f"| diffraction_incompatible | {summary['diffraction_incompatible']} |",
        "",
        "## Sample Results",
        "",
        "| sample_id | candidate COD IDs | XY | evaluable | compatible | final status | reason |",
        "|---|---|---|---:|---:|---|---|",
    ]

    for sample in sample_rows:
        reason = str(sample["reason"]).replace("|", "\\|")
        lines.append(
            f"| {sample['sample_id']} | {sample['candidate_cod_ids']} | "
            f"{sample['xy_source_collection'] or 'none'} | "
            f"{sample['candidate_count_evaluable']} | "
            f"{sample['candidate_count_diffraction_compatible']} | "
            f"`{sample['final_status']}` | {reason} |"
        )

    lines.extend(
        [
            "",
            "## Candidate Metrics",
            "",
            "| sample_id | COD ID | matched | median residual | weighted residual | max residual | slope | zero shift | core P95 | candidate status |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in candidate_rows:
        def value(name: str) -> str:
            return row.get(name, "") or ""

        lines.append(
            f"| {row['sample_id']} | {row['candidate_cod_id']} | "
            f"{value('matched_count')} | {value('median_abs_residual')} | "
            f"{value('weighted_mean_abs_residual')} | {value('max_abs_residual')} | "
            f"{value('residual_slope')} | {value('zero_shift')} | "
            f"{value('core_three_inside_p95')} | "
            f"`{row['candidate_diffraction_status']}` |"
        )

    lines.extend(
        [
            "",
            "## Provenance",
            "",
            f"- Candidate review input: `{REVIEW_FILE.relative_to(PROJECT_ROOT).as_posix()}`",
            f"- Calibration input: `{CALIBRATION_FILE.relative_to(PROJECT_ROOT).as_posix()}`",
            f"- Frozen diffraction engine: `{FROZEN_ENGINE_FILE.relative_to(PROJECT_ROOT).as_posix()}`",
            "- Experimental data: read-only `rruff.xy_raw`, then `rruff.xy_processed` fallback",
            "- DIF data: read-only `rruff.dif`",
            "",
            f"Generated at {datetime.now(timezone.utc).isoformat()}.",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    review_rows = _read_csv(REVIEW_FILE)
    target_rows = [
        row
        for row in review_rows
        if row.get("final_status") == "diffraction_validation_needed"
    ]
    target_ids = sorted({row["sample_id"] for row in target_rows})
    if len(target_ids) != 35:
        raise RuntimeError(
            f"Expected 35 diffraction-validation samples, found {len(target_ids)}"
        )

    candidates_by_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in target_rows:
        candidates_by_sample[row["sample_id"]].append(row)
    for sample_id in candidates_by_sample:
        candidates_by_sample[sample_id].sort(
            key=lambda row: row.get("candidate_cod_id") or ""
        )

    engine = _load_frozen_diffraction_engine()
    calibration = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    reference_records = _build_reference_values(calibration)
    db = get_database(database_name="rruff")

    sample_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    final_counts: Counter[str] = Counter()

    for sample_id in target_ids:
        source_candidates = candidates_by_sample[sample_id]
        profile = _pick_experimental_xy(db, sample_id)
        dif = db.dif.find_one({"sample_id": sample_id})
        candidate_results: list[dict[str, Any]] = []

        if profile.get("available") and dif is not None:
            raw_x = profile["x"]
            raw_y = engine["normalize"](profile["y"])
            experimental_peaks = engine["detect_experimental_peaks"](raw_x, raw_y)
            radiation = engine["derive_validation_wavelength"](dif)
        else:
            experimental_peaks = []
            radiation = {}

        for source in source_candidates:
            item: dict[str, Any] = {
                "sample_id": sample_id,
                "candidate_cod_id": source.get("candidate_cod_id"),
                "candidate_mineral_name": source.get("candidate_mineral_name"),
                "candidate_formula": source.get("candidate_formula"),
                "cif_file_path": source.get("cif_file_path"),
                "prior_structure_status": source.get("final_status"),
                "prior_chemistry_status": source.get("chemistry_status"),
                "prior_space_group_status": source.get("space_group_status"),
                "prior_cell_status": source.get("cell_status"),
                "xy_available": str(bool(profile.get("available"))).lower(),
                "xy_source_collection": profile.get("collection") or "",
                "measurement_id": profile.get("measurement_id") or "",
                "experimental_description": profile.get("description") or "",
                "experimental_point_count": profile.get("point_count") or 0,
                "experimental_peak_count": len(experimental_peaks),
                "raw_profile_count": profile.get("raw_profile_count") or 0,
                "processed_profile_count": profile.get("processed_profile_count") or 0,
                "dif_available": str(dif is not None).lower(),
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
                "candidate_diffraction_status": "not_evaluated",
                "candidate_evaluation_error": "",
                "_theoretical": None,
                "metrics": None,
            }

            if profile.get("available") and dif is not None:
                try:
                    cif_path = PROJECT_ROOT / str(
                        source.get("cif_file_path") or ""
                    ).replace("/", "\\")
                    calculated = engine["calculate_reflections"](
                        cif_path,
                        radiation["validation_wavelength"],
                        profile["x"][0],
                        profile["x"][-1],
                    )
                    theoretical = calculated["top_reflections"]
                    metrics = engine["summarize_candidate"](
                        theoretical,
                        experimental_peaks,
                    )
                    compatibility = _compatibility_annotation(
                        metrics,
                        radiation["radiation_class"],
                        reference_records,
                    )
                    candidate_status = _candidate_status(
                        metrics,
                        compatibility,
                        None,
                    )
                    item.update(
                        {
                            "generated_reflection_count": calculated[
                                "total_reflection_count"
                            ],
                            "theoretical_peak_count": len(theoretical),
                            "matched_count": metrics.get("matched_count"),
                            "matched_fraction": metrics.get("matched_fraction"),
                            "median_abs_residual": metrics.get(
                                "median_abs_residual"
                            ),
                            "weighted_mean_abs_residual": metrics.get(
                                "weighted_mean_abs_residual"
                            ),
                            "max_abs_residual": metrics.get("max_abs_residual"),
                            "residual_slope": metrics.get("residual_slope"),
                            "zero_shift": metrics.get("zero_shift"),
                            "same_radiation_reference_n": compatibility[
                                "reference_n"
                            ],
                            "core_three_inside_p95": str(
                                compatibility["core_three_inside_p95"]
                            ).lower(),
                            "all_six_inside_p95": str(
                                compatibility["all_six_inside_p95"]
                            ).lower(),
                            "minimum_core_compatibility": compatibility[
                                "minimum_core_compatibility"
                            ],
                            "candidate_diffraction_status": candidate_status,
                            "_theoretical": theoretical,
                            "metrics": metrics,
                            "_compatibility": compatibility,
                        }
                    )
                except Exception as exc:
                    item["candidate_diffraction_status"] = "evaluation_error"
                    item["candidate_evaluation_error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )

            candidate_results.append(item)

        separability = _evaluate_separability(candidate_results, engine)
        final_status, reason = _sample_status(profile, candidate_results)
        final_counts[final_status] += 1
        compatible_count = sum(
            row.get("candidate_diffraction_status")
            == "diffraction_compatible"
            for row in candidate_results
        )
        evaluable_count = sum(
            row.get("metrics") is not None for row in candidate_results
        )
        candidate_ids = [
            str(row["candidate_cod_id"])
            for row in candidate_results
        ]
        sample_result = {
            "sample_id": sample_id,
            "candidate_cod_ids": ", ".join(candidate_ids),
            "xy_source_collection": profile.get("collection") or "",
            "candidate_count_evaluable": evaluable_count,
            "candidate_count_diffraction_compatible": compatible_count,
            "final_status": final_status,
            "reason": reason,
        }
        sample_rows.append(sample_result)

        for row in candidate_results:
            separation = separability.get("best_runner_up_separation") or {}
            output = {
                key: value
                for key, value in row.items()
                if not key.startswith("_") and key not in {"metrics"}
            }
            output.update(
                {
                    "candidate_separability_available": str(
                        separability["available"]
                    ).lower(),
                    "candidate_separability_pair_count": separability["pair_count"],
                    "best_candidate_cod_id": separability[
                        "best_candidate_cod_id"
                    ]
                    or "",
                    "runner_up_candidate_cod_id": separability[
                        "runner_up_candidate_cod_id"
                    ]
                    or "",
                    "weighted_residual_gap": separability[
                        "weighted_residual_gap"
                    ]
                    if separability["weighted_residual_gap"] is not None
                    else "",
                    "best_runner_up_separation_median_nearest_difference": separation.get(
                        "median_nearest_difference",
                        "",
                    ),
                    "best_runner_up_separation_bin": separability[
                        "best_runner_up_separation_bin"
                    ]
                    or "",
                    "candidate_count_total": len(candidate_results),
                    "candidate_count_evaluable": evaluable_count,
                    "candidate_count_diffraction_compatible": compatible_count,
                    "final_status": final_status,
                    "reason": reason,
                }
            )
            candidate_rows.append(output)

    _write_csv(candidate_rows)
    _write_markdown(sample_rows, candidate_rows, {
        "total": len(sample_rows),
        "with_usable_experimental_xy": sum(
            bool(row["xy_source_collection"]) for row in sample_rows
        ),
        "no_diffraction_available": final_counts[
            "no_diffraction_available"
        ],
        "diffraction_supported_rescue": final_counts[
            "diffraction_supported_rescue"
        ],
        "multiple_diffraction_compatible_candidates": final_counts[
            "multiple_diffraction_compatible_candidates"
        ],
        "diffraction_inconclusive": final_counts[
            "diffraction_inconclusive"
        ],
        "diffraction_incompatible": final_counts[
            "diffraction_incompatible"
        ],
    })

    if len(sample_rows) != 35:
        raise RuntimeError("Sample output does not contain 35 samples.")
    if len({row["sample_id"] for row in sample_rows}) != 35:
        raise RuntimeError("Sample output contains duplicate sample IDs.")
    print("35 total")
    print(
        "with_usable_experimental_xy = "
        f"{sum(bool(row['xy_source_collection']) for row in sample_rows)}"
    )
    for status in (
        "no_diffraction_available",
        "diffraction_supported_rescue",
        "multiple_diffraction_compatible_candidates",
        "diffraction_inconclusive",
        "diffraction_incompatible",
    ):
        print(f"{status} = {final_counts[status]}")
    print(f"candidate rows = {len(candidate_rows)}")
    print(f"CSV = {OUTPUT_CSV}")
    print(f"MD = {OUTPUT_MD}")


if __name__ == "__main__":
    main()
