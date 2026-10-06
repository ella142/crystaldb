"""Validate existing CIF candidates against the 107 outside-DIF XY measurements.

The candidate population is the union of the existing 177-row local-index
result and the existing 118-row COD rescue result. No COD search or CIF
download is performed here. The diffraction functions are loaded from the
frozen group annotation engine and the existing calibration annotation code.
"""

from __future__ import annotations

import ast
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import gemmi
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
for import_root in (SRC_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from review_high_priority_35_diffraction_v1 import (  # noqa: E402
    _build_reference_values,
    _candidate_status,
    _compatibility_annotation,
    _evaluate_separability,
)


LOCAL_CANDIDATES = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_xy_not_in_dif_experimental_cod_candidates.csv"
)
RESCUE_CANDIDATES = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_xy_not_in_dif_cod_rescue_candidates.csv"
)
AUDIT_INPUT = PROJECT_ROOT / "data" / "mappings" / "rruff_xy_not_in_dif_audit.csv"
COD_INDEX = PROJECT_ROOT / "data" / "mappings" / "cif_index.json"
CALIBRATION_FILE = (
    PROJECT_ROOT / "data" / "mappings" / "rruff_diffraction_calibration_v1.json"
)
FROZEN_ENGINE_FILE = PROJECT_ROOT / "scripts" / "annotate_rruff_group_diffraction_v1.py"
STAGED_CIF_ROOT = (
    PROJECT_ROOT
    / "data"
    / "staging"
    / "rruff_xy_not_in_dif_cod_rescue_v1"
    / "cif"
)
OUTPUT_ROOT = PROJECT_ROOT / "data" / "mappings" / "dif_outside_experimental_v1"
OUTPUT_CSV = OUTPUT_ROOT / "rruff_107_diffraction_validation.csv"
OUTPUT_MD = OUTPUT_ROOT / "rruff_107_diffraction_validation.md"

MONGO_URI = "mongodb://127.0.0.1:27017"
DATABASE_NAME = "rruff"

EXPECTED_TOTAL = 107
EXPECTED_PRIOR_GROUPS = {
    "single_strong_candidate": 17,
    "multiple_valid_candidates": 69,
    "weak_candidate": 21,
}

CSV_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "mineral",
    "prior_candidate_group",
    "candidate_cod_id",
    "cif_file_path",
    "cif_source",
    "cif_parse_status",
    "xy_source_collection",
    "measurement_id",
    "experimental_description",
    "experimental_point_count",
    "experimental_peak_count",
    "raw_profile_count",
    "processed_profile_count",
    "radiation_class",
    "radiation_source",
    "validation_wavelength",
    "generated_reflection_count",
    "theoretical_peak_count",
    "matched_count",
    "median_residual",
    "weighted_residual",
    "max_residual",
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
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_frozen_engine() -> dict[str, Any]:
    """Load only frozen engine definitions; never execute its batch body."""

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
        elif isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & constants:
                nodes.append(node)
    namespace: dict[str, Any] = {"__name__": "_frozen_diffraction_engine"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(FROZEN_ENGINE_FILE), "exec"), namespace)
    required = {
        "normalize",
        "detect_experimental_peaks",
        "calculate_reflections",
        "summarize_candidate",
        "theoretical_separation",
        "separation_bin",
    }
    missing = sorted(name for name in required if name not in namespace)
    if missing:
        raise RuntimeError("Frozen diffraction engine missing: " + ", ".join(missing))
    return namespace


def prior_group(row: dict[str, str], source: str) -> str:
    count = int(row["candidate_count"])
    if count > 1:
        return "multiple_valid_candidates"
    if source == "local" and row.get("evidence_level") == "strong_candidate":
        return "single_strong_candidate"
    if source == "rescue" and row.get("final_status") == "single_strong_candidate":
        return "single_strong_candidate"
    return "weak_candidate"


def load_measurements() -> list[dict[str, Any]]:
    local_rows = [
        row
        for row in read_csv(LOCAL_CANDIDATES)
        if int(row["candidate_count"]) > 0
    ]
    rescue_rows = [
        row
        for row in read_csv(RESCUE_CANDIDATES)
        if int(row["candidate_count"]) > 0
    ]
    measurements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, rows in (("local", local_rows), ("rescue", rescue_rows)):
        for row in rows:
            key = row["filename_sample_id"]
            if key in seen:
                raise RuntimeError(f"Duplicate candidate input measurement: {key}")
            seen.add(key)
            ids = json.loads(row["candidate_cod_ids"])
            if len(ids) != int(row["candidate_count"]) or not ids:
                raise RuntimeError(f"Candidate count mismatch for {key}")
            measurements.append(
                {
                    "sample_id": row["sample_id"],
                    "filename_sample_id": key,
                    "mineral": row.get("mineral", ""),
                    "candidate_ids": [str(value) for value in ids],
                    "prior_candidate_group": prior_group(row, source),
                    "candidate_source": source,
                }
            )

    if len(measurements) != EXPECTED_TOTAL:
        raise RuntimeError(f"Expected {EXPECTED_TOTAL} candidate measurements, found {len(measurements)}")
    counts = Counter(item["prior_candidate_group"] for item in measurements)
    if dict(counts) != EXPECTED_PRIOR_GROUPS:
        raise RuntimeError(f"Unexpected prior candidate groups: {dict(counts)}")
    return sorted(measurements, key=lambda item: item["filename_sample_id"])


def validate_audit_scope(measurements: list[dict[str, Any]]) -> None:
    audit_rows = {
        row["filename_sample_id"]: row
        for row in read_csv(AUDIT_INPUT)
    }
    if len(audit_rows) != 259:
        raise RuntimeError(f"Unexpected audit input size: {len(audit_rows)}")
    for item in measurements:
        row = audit_rows.get(item["filename_sample_id"])
        if row is None or row.get("profile_origin") != "experimental":
            raise RuntimeError(f"Measurement is not experimental in audit: {item['filename_sample_id']}")


def resolve_cifs(measurements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index_rows = json.loads(COD_INDEX.read_text(encoding="utf-8"))
    local_index = {
        str(row.get("source_id")): row
        for row in index_rows
        if row.get("source") == "COD" and row.get("source_id")
    }
    ids = sorted({cod_id for item in measurements for cod_id in item["candidate_ids"]})
    resolved: dict[str, dict[str, Any]] = {}
    for cod_id in ids:
        index_row = local_index.get(cod_id, {})
        path: Path | None = None
        source = ""
        indexed_path = index_row.get("file_path")
        if indexed_path:
            path = Path(str(indexed_path))
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if path.exists():
                source = "local_index"
            else:
                path = None
        staged_path = STAGED_CIF_ROOT / f"{cod_id}.cif"
        if path is None and staged_path.exists():
            path = staged_path
            source = "rescue_staging"

        parse_status = "missing"
        if path is not None:
            try:
                document = gemmi.cif.read_file(str(path))
                document.sole_block()
                parse_status = "ok"
            except Exception as exc:
                parse_status = f"error:{type(exc).__name__}"

        resolved[cod_id] = {
            "path": path,
            "source": source,
            "parse_status": parse_status,
            "mineral_name": index_row.get("mineral_name", ""),
            "formula": index_row.get("formula", ""),
        }

    missing = [cod_id for cod_id, item in resolved.items() if item["parse_status"] != "ok"]
    if missing:
        raise RuntimeError(f"Missing or unparsable input CIFs: {missing[:20]}")
    return resolved


def valid_xy(document: dict[str, Any]) -> bool:
    xrd = document.get("xrd") or {}
    x = xrd.get("two_theta") or []
    y = xrd.get("intensity") or []
    return bool(x) and bool(y) and len(x) == len(y)


def description(document: dict[str, Any]) -> str:
    return str((document.get("metadata") or {}).get("DIFFRACTION SAMPLE DESCRIPTION") or "").strip()


def load_xy_profiles(database, measurements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keys = [item["filename_sample_id"] for item in measurements]
    docs_by_key: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    projection = {
        "_id": 0,
        "sample_id": 1,
        "filename_sample_id": 1,
        "metadata": 1,
        "xrd": 1,
    }
    query = {"filename_sample_id": {"$in": keys}}
    for collection_name in ("xy_raw", "xy_processed"):
        for document in database[collection_name].find(query, projection):
            key = document.get("filename_sample_id")
            if key:
                docs_by_key[key][collection_name].append(document)

    profiles: dict[str, dict[str, Any]] = {}
    for key in keys:
        raw_docs = docs_by_key[key]["xy_raw"]
        processed_docs = docs_by_key[key]["xy_processed"]
        candidates = [("rruff.xy_raw", doc) for doc in raw_docs] + [
            ("rruff.xy_processed", doc) for doc in processed_docs
        ]
        chosen: tuple[str, dict[str, Any]] | None = None
        for collection_name, document in candidates:
            if valid_xy(document):
                chosen = (collection_name, document)
                if collection_name == "rruff.xy_raw":
                    break
        if chosen is None:
            profiles[key] = {
                "available": False,
                "collection": "",
                "measurement_id": key,
                "description": description(candidates[0][1]) if candidates else "",
                "point_count": 0,
                "x": [],
                "y": [],
                "raw_profile_count": len(raw_docs),
                "processed_profile_count": len(processed_docs),
            }
            continue
        collection_name, document = chosen
        xrd = document.get("xrd") or {}
        profiles[key] = {
            "available": True,
            "collection": collection_name,
            "measurement_id": document.get("filename_sample_id") or key,
            "description": description(document),
            "point_count": len(xrd.get("two_theta") or []),
            "x": [float(value) for value in xrd.get("two_theta") or []],
            "y": [float(value) for value in xrd.get("intensity") or []],
            "raw_profile_count": len(raw_docs),
            "processed_profile_count": len(processed_docs),
        }
    return profiles


def radiation_from_metadata(description_text: str, engine: dict[str, Any]) -> dict[str, Any]:
    lowered = description_text.casefold()
    if "co-radiation" in lowered or "cobalt" in lowered:
        return {
            "radiation_class": "Co-unsupported",
            "validation_wavelength": None,
            "radiation_source": "metadata explicitly reports Co; frozen engine has no Co wavelength",
        }
    if "mo" in lowered:
        return {
            "radiation_class": "Mo-like",
            "validation_wavelength": engine["MO_WAVELENGTH"],
            "radiation_source": "XY metadata: Mo",
        }
    return {
        "radiation_class": "Cu-like",
        "validation_wavelength": engine["CU_WAVELENGTH"],
        "radiation_source": "frozen Cu reference for non-Mo experimental XY",
    }


def relative_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def final_status(candidate_results: list[dict[str, Any]], profile: dict[str, Any]) -> tuple[str, str]:
    if not profile.get("available"):
        return "diffraction_inconclusive", "XY profile is unavailable or malformed"
    compatible = [
        item
        for item in candidate_results
        if item.get("candidate_diffraction_status") == "diffraction_compatible"
    ]
    if len(compatible) > 1:
        return "ambiguous_group", "multiple candidates are inside the existing core diffraction envelope"
    if len(compatible) == 1:
        all_evaluable = all(item.get("metrics") is not None for item in candidate_results)
        if all_evaluable:
            return "resolved_candidate", "exactly one candidate is inside the existing core diffraction envelope"
        return "diffraction_inconclusive", "one candidate is compatible but another candidate was not evaluable"

    evaluated = [
        item
        for item in candidate_results
        if item.get("candidate_diffraction_status") in {
            "diffraction_inconclusive",
            "diffraction_incompatible",
        }
    ]
    if evaluated and len(evaluated) == len(candidate_results) and all(
        item.get("candidate_diffraction_status") == "diffraction_incompatible"
        for item in evaluated
    ):
        return "diffraction_incompatible", "all evaluable candidates produced zero one-to-one matches"
    if not evaluated:
        return "diffraction_inconclusive", "no candidate produced evaluable diffraction metrics"
    return "diffraction_inconclusive", "no candidate met the existing core envelope and evidence is not uniformly incompatible"


def evaluate(
    measurements: list[dict[str, Any]],
    cif_records: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    engine: dict[str, Any],
    reference_records: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    measurement_rows: list[dict[str, Any]] = []
    reflection_cache: dict[tuple[str, float, float, float], dict[str, Any]] = {}

    for index, measurement in enumerate(measurements, start=1):
        key = measurement["filename_sample_id"]
        profile = profiles[key]
        radiation = radiation_from_metadata(profile["description"], engine)
        experimental_peaks: list[dict[str, Any]] = []
        peak_error = ""
        if profile.get("available"):
            try:
                normalized_y = engine["normalize"](profile["y"])
                experimental_peaks = engine["detect_experimental_peaks"](
                    profile["x"], normalized_y
                )
            except Exception as exc:
                peak_error = f"{type(exc).__name__}: {exc}"

        results: list[dict[str, Any]] = []
        for cod_id in measurement["candidate_ids"]:
            cif = cif_records[cod_id]
            result: dict[str, Any] = {
                "sample_id": measurement["sample_id"],
                "candidate_cod_id": cod_id,
                "_theoretical": None,
                "metrics": None,
                "candidate_diffraction_status": "evaluation_error",
                "candidate_evaluation_error": "",
            }
            if not profile.get("available"):
                result["candidate_diffraction_status"] = "not_evaluable"
                result["candidate_evaluation_error"] = "XY profile unavailable"
            elif radiation["validation_wavelength"] is None:
                result["candidate_diffraction_status"] = "not_evaluable"
                result["candidate_evaluation_error"] = radiation["radiation_source"]
            elif peak_error:
                result["candidate_diffraction_status"] = "not_evaluable"
                result["candidate_evaluation_error"] = peak_error
            elif not experimental_peaks:
                result["candidate_diffraction_status"] = "not_evaluable"
                result["candidate_evaluation_error"] = "No experimental peaks detected"
            elif cif["parse_status"] != "ok" or cif["path"] is None:
                result["candidate_evaluation_error"] = "CIF missing or unparsable"
            else:
                try:
                    cache_key = (
                        cod_id,
                        float(radiation["validation_wavelength"]),
                        float(profile["x"][0]),
                        float(profile["x"][-1]),
                    )
                    if cache_key not in reflection_cache:
                        reflection_cache[cache_key] = engine["calculate_reflections"](
                            cif["path"],
                            radiation["validation_wavelength"],
                            profile["x"][0],
                            profile["x"][-1],
                        )
                    calculated = reflection_cache[cache_key]
                    theoretical = calculated["top_reflections"]
                    metrics = engine["summarize_candidate"](theoretical, experimental_peaks)
                    compatibility = _compatibility_annotation(
                        metrics,
                        radiation["radiation_class"],
                        reference_records,
                    )
                    result.update(
                        {
                            "_theoretical": theoretical,
                            "metrics": metrics,
                            "calculated": calculated,
                            "compatibility": compatibility,
                            "candidate_diffraction_status": _candidate_status(
                                metrics, compatibility, None
                            ),
                        }
                    )
                except Exception as exc:
                    result["candidate_evaluation_error"] = f"{type(exc).__name__}: {exc}"
            results.append(result)

        separability = _evaluate_separability(results, engine)
        status, reason = final_status(results, profile)
        compatible_count = sum(
            item.get("candidate_diffraction_status") == "diffraction_compatible"
            for item in results
        )
        evaluable_count = sum(item.get("metrics") is not None for item in results)
        measurement_rows.append(
            {
                "sample_id": measurement["sample_id"],
                "filename_sample_id": key,
                "mineral": measurement["mineral"],
                "prior_candidate_group": measurement["prior_candidate_group"],
                "candidate_cod_ids": ", ".join(measurement["candidate_ids"]),
                "xy_source_collection": profile.get("collection", ""),
                "candidate_count_total": len(results),
                "candidate_count_evaluable": evaluable_count,
                "candidate_count_diffraction_compatible": compatible_count,
                "final_status": status,
                "reason": reason,
            }
        )
        for result in results:
            metrics = result.get("metrics") or {}
            compatibility = result.get("compatibility") or {}
            separation = separability.get("best_runner_up_separation") or {}
            candidate_rows.append(
                {
                    "sample_id": measurement["sample_id"],
                    "filename_sample_id": key,
                    "mineral": measurement["mineral"],
                    "prior_candidate_group": measurement["prior_candidate_group"],
                    "candidate_cod_id": result["candidate_cod_id"],
                    "cif_file_path": relative_path(cif_records[result["candidate_cod_id"]]["path"]),
                    "cif_source": cif_records[result["candidate_cod_id"]]["source"],
                    "cif_parse_status": cif_records[result["candidate_cod_id"]]["parse_status"],
                    "xy_source_collection": profile.get("collection", ""),
                    "measurement_id": profile.get("measurement_id", ""),
                    "experimental_description": profile.get("description", ""),
                    "experimental_point_count": profile.get("point_count", 0),
                    "experimental_peak_count": len(experimental_peaks),
                    "raw_profile_count": profile.get("raw_profile_count", 0),
                    "processed_profile_count": profile.get("processed_profile_count", 0),
                    "radiation_class": radiation["radiation_class"],
                    "radiation_source": radiation["radiation_source"],
                    "validation_wavelength": radiation["validation_wavelength"] or "",
                    "generated_reflection_count": (result.get("calculated") or {}).get("total_reflection_count", ""),
                    "theoretical_peak_count": len(result.get("_theoretical") or []),
                    "matched_count": metrics.get("matched_count", ""),
                    "median_residual": metrics.get("median_abs_residual", ""),
                    "weighted_residual": metrics.get("weighted_mean_abs_residual", ""),
                    "max_residual": metrics.get("max_abs_residual", ""),
                    "residual_slope": metrics.get("residual_slope", ""),
                    "zero_shift": metrics.get("zero_shift", ""),
                    "same_radiation_reference_n": compatibility.get("reference_n", ""),
                    "core_three_inside_p95": str(compatibility.get("core_three_inside_p95", "")).lower(),
                    "all_six_inside_p95": str(compatibility.get("all_six_inside_p95", "")).lower(),
                    "minimum_core_compatibility": compatibility.get("minimum_core_compatibility", ""),
                    "candidate_diffraction_status": result.get("candidate_diffraction_status", ""),
                    "candidate_evaluation_error": result.get("candidate_evaluation_error", ""),
                    "candidate_separability_available": str(separability["available"]).lower(),
                    "candidate_separability_pair_count": separability["pair_count"],
                    "best_candidate_cod_id": separability["best_candidate_cod_id"] or "",
                    "runner_up_candidate_cod_id": separability["runner_up_candidate_cod_id"] or "",
                    "weighted_residual_gap": separability["weighted_residual_gap"] if separability["weighted_residual_gap"] is not None else "",
                    "best_runner_up_separation_median_nearest_difference": separation.get("median_nearest_difference", ""),
                    "best_runner_up_separation_bin": separability["best_runner_up_separation_bin"] or "",
                    "candidate_count_total": len(results),
                    "candidate_count_evaluable": evaluable_count,
                    "candidate_count_diffraction_compatible": compatible_count,
                    "final_status": status,
                    "reason": reason,
                }
            )
        print(f"[{index}/{len(measurements)}] {key}: {status}", flush=True)

    return measurement_rows, candidate_rows


def write_outputs(
    measurements: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    cif_records: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidate_rows)

    final_counts = Counter(row["final_status"] for row in measurements)
    group_counts = {
        group: Counter(
            row["final_status"]
            for row in measurements
            if row["prior_candidate_group"] == group
        )
        for group in EXPECTED_PRIOR_GROUPS
    }
    parse_counts = Counter(item["parse_status"] for item in cif_records.values())
    xy_available = sum(bool(profile.get("available")) for profile in profiles.values())
    candidate_status_counts = Counter(
        row["candidate_diffraction_status"] for row in candidate_rows
    )
    lines = [
        "# DIF-outside experimental XY diffraction validation",
        "",
        "## Scope",
        "",
        "This audit processes only the 107 existing DIF-outside experimental measurements that already have CIF candidates.",
        "It does not search COD, download CIFs, modify candidate data, run v2/v3, write MongoDB, or update formal CrystalDB.",
        "The 70 `still_no_candidate` measurements are excluded.",
        "",
        "## Input Integrity",
        "",
        f"- measurements: {len(measurements)}",
        f"- prior single_strong_candidate: {sum(row['prior_candidate_group'] == 'single_strong_candidate' for row in measurements)}",
        f"- prior multiple_valid_candidates: {sum(row['prior_candidate_group'] == 'multiple_valid_candidates' for row in measurements)}",
        f"- prior weak_candidate: {sum(row['prior_candidate_group'] == 'weak_candidate' for row in measurements)}",
        f"- candidate references: {len(candidate_rows)}",
        f"- unique input CIFs: {len(cif_records)}",
        f"- CIF parse status: {dict(parse_counts)}",
        f"- usable XY profiles: {xy_available}/{len(profiles)}",
        f"- output candidate rows: {len(candidate_rows)}",
        f"- candidate diffraction statuses: {dict(candidate_status_counts)}",
        f"- candidate rows without metrics: {sum(row['candidate_diffraction_status'] in {'not_evaluable', 'evaluation_error'} for row in candidate_rows)}",
        "",
        "## Existing Diffraction Method",
        "",
        "- CIF -> Gemmi theoretical reflections and structure factors",
        "- existing XY normalization, smoothing, local-maxima peak detection, intensity and separation filters",
        "- existing one-to-one peak assignment",
        "- existing weighted-median zero-shift correction",
        "- existing residual metrics: matched_count, median_residual, weighted_residual, max_residual, residual_slope, zero_shift",
        "- existing candidate separability calculation for multi-candidate measurements",
        "- existing calibration file and core three-metric P95 annotation logic; no threshold changes",
        "",
        "Because these measurements are outside DIF, radiation is taken from the existing XY metadata when explicit. Mo uses the frozen Mo wavelength; non-Mo experimental descriptions use the frozen Cu reference. Co-radiation is not guessed and remains inconclusive.",
        "",
        "## Final Summary",
        "",
        f"107 total = {len(measurements)}",
        f"resolved_candidate = {final_counts['resolved_candidate']}",
        f"ambiguous_group = {final_counts['ambiguous_group']}",
        f"diffraction_inconclusive = {final_counts['diffraction_inconclusive']}",
        f"diffraction_incompatible = {final_counts['diffraction_incompatible']}",
        "",
        "## Prior Group Breakdown",
        "",
        "| prior group | resolved | ambiguous | inconclusive | incompatible | total |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for group in EXPECTED_PRIOR_GROUPS:
        counts = group_counts[group]
        lines.append(
            f"| {group} | {counts['resolved_candidate']} | {counts['ambiguous_group']} | "
            f"{counts['diffraction_inconclusive']} | {counts['diffraction_incompatible']} | "
            f"{sum(counts.values())} |"
        )
    lines.extend(
        [
            "",
            "## Measurement Results",
            "",
            "| filename_sample_id | sample_id | prior group | candidate count | evaluable | compatible | final status | reason |",
            "|---|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in measurements:
        lines.append(
            f"| {row['filename_sample_id']} | {row['sample_id']} | {row['prior_candidate_group']} | "
            f"{row['candidate_count_total']} | {row['candidate_count_evaluable']} | "
            f"{row['candidate_count_diffraction_compatible']} | `{row['final_status']}` | "
            f"{str(row['reason']).replace('|', '\\|')} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Metrics",
            "",
            "The CSV contains one row per existing candidate, with the measurement-level final status repeated for audit joins.",
            "",
            "## Output",
            "",
            f"- CSV: `{OUTPUT_CSV}`",
            f"- MD: `{OUTPUT_MD}`",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(f"107 total = {len(measurements)}")
    for status in (
        "resolved_candidate",
        "ambiguous_group",
        "diffraction_inconclusive",
        "diffraction_incompatible",
    ):
        print(f"{status} = {final_counts[status]}")
    for group in EXPECTED_PRIOR_GROUPS:
        counts = group_counts[group]
        print(f"{group}: resolved={counts['resolved_candidate']} ambiguous={counts['ambiguous_group']} inconclusive={counts['diffraction_inconclusive']} incompatible={counts['diffraction_incompatible']}")
    print(f"candidate rows = {len(candidate_rows)}")
    print(f"CSV = {OUTPUT_CSV}")
    print(f"MD = {OUTPUT_MD}")


def main() -> None:
    measurements = load_measurements()
    validate_audit_scope(measurements)
    cif_records = resolve_cifs(measurements)
    engine = load_frozen_engine()
    calibration = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    reference_records = _build_reference_values(calibration)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        profiles = load_xy_profiles(client[DATABASE_NAME], measurements)
        measurement_rows, candidate_rows = evaluate(
            measurements,
            cif_records,
            profiles,
            engine,
            reference_records,
        )
    finally:
        client.close()

    if len(measurement_rows) != EXPECTED_TOTAL:
        raise RuntimeError(f"Output measurement count mismatch: {len(measurement_rows)}")
    if len({row["filename_sample_id"] for row in measurement_rows}) != EXPECTED_TOTAL:
        raise RuntimeError("Output measurement IDs are not unique")
    if len(candidate_rows) != sum(len(item["candidate_ids"]) for item in measurements):
        raise RuntimeError("Output candidate row count mismatch")
    write_outputs(measurement_rows, candidate_rows, cif_records, profiles)


if __name__ == "__main__":
    main()
