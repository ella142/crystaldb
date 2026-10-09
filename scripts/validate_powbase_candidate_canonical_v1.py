"""Validate four previously reviewed PowBase candidates for canonical shape.

This is a narrow, read-only validation pass.  It consumes the existing fast
conditional review and unresolved-rescue outputs, reads only the four cached
source archives, and builds canonical documents in memory using the existing
PowBase document builder.  It does not write MongoDB, source archives, or
canonical staging records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_powbase import (
    collect_fullprof_metadata,
    collect_numeric_rows,
    collect_text_metadata,
    find_intensity_header_and_block,
    numeric_token_value,
)
from scripts.audit_powbase_unresolved_rescue_v1 import _decode_for_rescue
from scripts.prepare_powbase_canonical_v1 import (
    _independent_numeric_block,
    _numeric_value,
    axis_and_qc,
    build_documents,
    explicit_wavelengths,
    inspect_mongo_read_only,
    select_wavelength,
)
from scripts.review_powbase_v1 import detect_header_with_suffix, detect_uxd_style

DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"
DEFAULT_INCLUSION_MANIFEST = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_v1_inclusion_manifest.csv"
)
DEFAULT_FAST_REVIEW = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_fast_conditional_review_v1.csv"
)
DEFAULT_RESCUE_REVIEW = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_unresolved_rescue_audit_v1.csv"
)
DEFAULT_CANONICAL_DRYRUN = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "mappings"

CANDIDATE_ENTRY_IDS = ["15", "74", "121", "156"]
EXPECTED_PRODUCTION_PATTERN_COUNT = 3019
EXPECTED_PROPOSED_PATTERN_COUNT = 3023


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _read_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {row["entry_id"]: row for row in csv.DictReader(stream)}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _numeric_values(tokens: list[str]) -> list[int | float]:
    return [_numeric_value(token) for token in tokens]


def _float_values(tokens: list[str]) -> list[float]:
    values = [numeric_token_value(token) for token in tokens]
    if any(value is None or not math.isfinite(value) for value in values):
        raise ValueError("profile contains a non-finite numeric intensity")
    return [float(value) for value in values if value is not None]


def _archive_member(
    archive_path: Path,
) -> tuple[str, bytes, str, str]:
    archive_bytes = archive_path.read_bytes()
    archive_sha256 = _sha256_bytes(archive_bytes)
    with zipfile.ZipFile(archive_path) as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) != 1:
            raise ValueError(
                f"expected one non-directory member, found {len(members)}"
            )
        info = members[0]
        raw = archive.read(info)
    return info.filename, raw, archive_sha256, _sha256_bytes(raw)


def _parse_candidate_profile(
    entry_id: str,
    text: str,
    fast_row: dict[str, str] | None,
    rescue_row: dict[str, str] | None,
) -> dict[str, Any]:
    if entry_id == "15":
        detected = detect_uxd_style(text)
        if not detected or not detected.get("point_count_consistency"):
            raise ValueError("existing UXD review rule is not internally consistent")
        counts_line_index = int(detected["header_line_number"]) - 1
        block = collect_numeric_rows(text.splitlines(), counts_line_index + 1)
        start = float(detected["two_theta_start_raw"])
        step = float(detected["step_raw"])
        expected = int(detected["expected_point_count"])
        end = float(detected["derived_two_theta_end"])
        rule = (
            "UXD _START/_STEPSIZE/_STEPCOUNT metadata plus the _COUNTS "
            "intensity block; end is reconstructed as start + step*(count-1)."
        )
        explicit_end = False
        family = detected["format_family"]
        rule_evidence = detected
    elif entry_id == "74":
        detected = detect_header_with_suffix(text)
        if not detected or not detected.get("point_count_consistency"):
            raise ValueError("existing source-suffix review rule is not consistent")
        counts_line_index = int(detected["header_line_number"]) - 1
        block = collect_numeric_rows(text.splitlines(), counts_line_index + 1)
        start = float(detected["two_theta_start_raw"])
        step = float(detected["step_raw"])
        end = float(detected["two_theta_end_raw"])
        expected = int(detected["expected_point_count"])
        rule = (
            "Three numeric 2theta header fields followed by the literal "
            "CuKalpha suffix; retain all following numeric intensity values."
        )
        explicit_end = True
        family = detected["format_family"]
        rule_evidence = detected
    else:
        detected = find_intensity_header_and_block(text)
        if not detected or not detected.get("point_count_consistency"):
            raise ValueError("existing Koalariet exact-count rescue rule is not consistent")
        counts_line_index = int(detected["header_line_number"]) - 1
        block = collect_numeric_rows(text.splitlines(), counts_line_index + 1)
        start = float(detected["two_theta_start"])
        step = float(detected["step"])
        end = float(detected["two_theta_end"])
        expected = int(detected["expected_point_count"])
        rule = (
            "Koalariet source text decoded with NUL bytes replaced only in the "
            "parsing view, then the explicit three-number 2theta header and "
            "exact raw intensity count are used; source bytes are preserved."
        )
        explicit_end = True
        family = "koalariet_style_pattern"
        rule_evidence = detected

    tokens = list(block["values"])
    intensities = _numeric_values(tokens)
    independent = _independent_numeric_block(text.splitlines(), counts_line_index + 1)
    independent_values = _float_values(independent["tokens"])
    axis, qc, errors = axis_and_qc(
        start=start,
        step=step,
        end=end,
        expected_count=expected,
        intensities=intensities,
        independent_count=len(independent_values),
        independent_values=independent_values,
    )
    if errors:
        raise ValueError("axis/profile QC failed: " + ", ".join(errors))

    return {
        "recovery_rule": rule,
        "recovery_rule_evidence": rule_evidence,
        "detected_content_family": family,
        "start": start,
        "step": step,
        "end": end,
        "end_explicit_in_source": explicit_end,
        "expected_point_count": expected,
        "observed_point_count": len(intensities),
        "axis": axis,
        "intensities": intensities,
        "qc": qc,
        "independent_parser_count": len(independent_values),
        "intensity_tokens": tokens,
        "review_source": (
            "powbase_fast_conditional_review_v1"
            if fast_row is not None
            else "powbase_unresolved_rescue_audit_v1"
        ),
    }


def _validate_document_shape(
    documents: dict[str, Any],
    canonical_pattern_keys: set[str],
) -> list[str]:
    errors: list[str] = []
    sample = documents["sample"]
    measurement = documents["measurement"]
    pattern = documents["pattern"]
    xy = documents["pattern_xy"]
    required = {
        "sample": {"sample_id", "source", "name", "formula", "phase_character"},
        "measurement": {
            "measurement_id",
            "sample_id",
            "pattern_id",
            "source",
            "data_origin",
            "modality",
            "conditions",
        },
        "pattern": {
            "pattern_id",
            "measurement_id",
            "sample_id",
            "source",
            "data_origin",
            "modality",
            "phase_character",
            "structure_linkage",
            "xrd",
        },
        "pattern_xy": {"pattern_id", "point_count", "x", "y"},
    }
    for name, keys in required.items():
        actual = set(documents[name])
        missing = sorted(keys - actual)
        if missing:
            errors.append(f"{name} missing required fields: {missing}")

    if not canonical_pattern_keys.issuperset({"pattern_id", "measurement_id", "sample_id"}):
        errors.append("existing canonical pattern schema baseline is incomplete")
    if pattern["pattern_id"] != xy["pattern_id"]:
        errors.append("pattern and XY pattern_id differ")
    if measurement["pattern_id"] != pattern["pattern_id"]:
        errors.append("measurement and pattern IDs differ")
    if sample["sample_id"] != measurement["sample_id"]:
        errors.append("sample and measurement IDs differ")
    if pattern["sample_id"] != sample["sample_id"]:
        errors.append("sample and pattern IDs differ")
    if sample["formula"] is not None:
        errors.append("formula was inferred or populated")
    if pattern["phase_character"] != "unknown":
        errors.append("phase_character was promoted")
    if pattern["structure_linkage"]["status"] != "unlinked":
        errors.append("structure linkage was populated")

    xrd = pattern["xrd"]
    x_values = xrd["two_theta"]
    y_values = xrd["intensity"]
    if len(x_values) != len(y_values):
        errors.append("pattern xrd axis/intensity lengths differ")
    if xrd["point_count"] != len(x_values):
        errors.append("pattern xrd point_count differs from payload length")
    if xy["point_count"] != len(xy["x"]["values"]) or xy["point_count"] != len(
        xy["y"]["values"]
    ):
        errors.append("XY point_count differs from payload lengths")
    return errors


def _local_collisions(
    candidates: list[dict[str, Any]],
    canonical: dict[str, Any],
) -> dict[str, list[str]]:
    existing = {
        field: {
            record[field]
            for record in canonical.get("records", [])
            if record.get(field)
        }
        for field in ("sample_id", "measurement_id", "pattern_id")
    }
    proposed = {
        field: [record[field] for record in candidates]
        for field in ("sample_id", "measurement_id", "pattern_id")
    }
    result: dict[str, list[str]] = {}
    for field, values in proposed.items():
        duplicates = sorted({value for value in values if values.count(value) > 1})
        existing_hits = sorted(set(values) & existing[field])
        result[field] = sorted(set(duplicates + existing_hits))
    return result


def build_validation(
    *,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    inclusion_manifest: Path = DEFAULT_INCLUSION_MANIFEST,
    fast_review: Path = DEFAULT_FAST_REVIEW,
    rescue_review: Path = DEFAULT_RESCUE_REVIEW,
    canonical_dryrun: Path = DEFAULT_CANONICAL_DRYRUN,
    inspect_mongo: bool = True,
) -> dict[str, Any]:
    inclusion = _read_csv(inclusion_manifest)
    fast_rows = _read_csv(fast_review)
    rescue_rows = _read_csv(rescue_review)
    canonical = _read_json(canonical_dryrun)
    canonical_pattern_keys = set(canonical["records"][0]["pattern"].keys())

    records: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    archive_hashes_before: dict[str, str] = {}
    for entry_id in CANDIDATE_ENTRY_IDS:
        row = deepcopy(inclusion[entry_id])
        fast_row = fast_rows.get(entry_id)
        rescue_row = rescue_rows.get(entry_id)
        if fast_row is None and rescue_row is None:
            raise ValueError(f"entry {entry_id} is absent from both existing reviews")
        if fast_row is not None:
            if fast_row["fast_decision"] != "promote_candidate":
                raise ValueError(f"entry {entry_id} is not promoted by existing fast review")
        if rescue_row is not None:
            if rescue_row["classification"] != "A_model_and_profile_recoverable":
                raise ValueError(f"entry {entry_id} is not class A in existing rescue review")

        archive_path = archive_root / "archives" / row["source_filename"]
        archive_hashes_before[entry_id] = _sha256_bytes(archive_path.read_bytes())
        if archive_hashes_before[entry_id] != row["source_sha256"]:
            raise ValueError(f"entry {entry_id} archive SHA256 differs from manifest")
        member_filename, raw, archive_sha256, member_sha256 = _archive_member(
            archive_path
        )
        text, encoding, nul_count, decode_note = _decode_for_rescue(raw)
        if text is None:
            raise ValueError(f"entry {entry_id} member is not readable text")

        profile = _parse_candidate_profile(entry_id, text, fast_row, rescue_row)
        row["detected_content_family"] = profile["detected_content_family"]
        fullprof = collect_fullprof_metadata(text)
        text_metadata = collect_text_metadata(text)
        index_tokens = json.loads(row["raw_hash_delimited_tokens"])
        wavelength_records = explicit_wavelengths(
            index_tokens=index_tokens,
            text=text,
            fullprof=fullprof,
        )
        wavelength, wavelength_secondary, wavelength_notes = select_wavelength(
            wavelength_records
        )
        if wavelength_notes:
            raise ValueError(f"entry {entry_id} wavelength error: {wavelength_notes}")

        result = build_documents(
            row,
            archive_path=archive_path,
            member_filename=member_filename,
            archive_sha256=archive_sha256,
            member_sha256=member_sha256,
            text=text,
            axis=profile["axis"],
            intensities=profile["intensities"],
            start=profile["start"],
            step=profile["step"],
            end=profile["end"],
            expected_count=profile["expected_point_count"],
            qc=profile["qc"],
            wavelength_records=wavelength_records,
            wavelength=wavelength,
            wavelength_secondary=wavelength_secondary,
            fullprof=fullprof,
            text_metadata=text_metadata,
            independent_parser={
                "encoding": encoding,
                "nul_byte_count": nul_count,
                "decode_note": decode_note,
                "header_line_number": profile["recovery_rule_evidence"].get(
                    "header_line_number"
                ),
                "intensity_token_count": profile["independent_parser_count"],
            },
        )
        shape_errors = _validate_document_shape(result, canonical_pattern_keys)
        if shape_errors:
            raise ValueError(f"entry {entry_id} schema errors: {shape_errors}")

        explicit_wavelength_values = [
            record["value"] for record in wavelength_records
        ]
        records.append(
            {
                "entry_id": entry_id,
                "status": "PASS",
                "source_label_raw": row["source_label_raw"],
                "source_modality_raw": row["source_modality_raw"],
                "source_modality_class": row["source_modality_class"],
                "sample_id": result["sample_id"],
                "measurement_id": result["measurement_id"],
                "pattern_id": result["pattern_id"],
                "source_filename": row["source_filename"],
                "member_filename": member_filename,
                "source_archive_sha256": archive_sha256,
                "source_member_sha256": member_sha256,
                "source_extension": Path(member_filename).suffix,
                "detected_content_family": profile["detected_content_family"],
                "recovery_rule": profile["recovery_rule"],
                "start": profile["start"],
                "step": profile["step"],
                "end": profile["end"],
                "end_explicit_in_source": profile["end_explicit_in_source"],
                "expected_point_count": profile["expected_point_count"],
                "observed_point_count": profile["observed_point_count"],
                "canonical_point_count": result["pattern"]["xrd"]["point_count"],
                "monotonic_2theta": profile["qc"]["axis_strictly_increasing"],
                "finite_intensities": profile["qc"]["intensity_values_finite"],
                "wavelength_angstrom": wavelength,
                "wavelength_kalpha2_angstrom": wavelength_secondary,
                "explicit_wavelength_values_angstrom": explicit_wavelength_values,
                "wavelength_notes": wavelength_notes,
                "source_raw_index_text": row["raw_index_text"],
                "source_bibliographic_comment_text": row[
                    "raw_bibliographic_comment_text"
                ],
                "decode_encoding": encoding,
                "nul_byte_count": nul_count,
                "decode_note": decode_note,
                "validation_issues": [],
            }
        )
        documents.append(result)

    local_collision_map = _local_collisions(records, canonical)
    mongo_report = (
        inspect_mongo_read_only(CANDIDATE_ENTRY_IDS)
        if inspect_mongo
        else {"status": "skipped", "read_only": True}
    )
    mongo_candidate_collisions: dict[str, list[str]] = {
        "sample_id": [],
        "measurement_id": [],
        "pattern_id": [],
    }
    if mongo_report.get("status") == "ok":
        for collection, field in (
            ("samples", "sample_id"),
            ("measurements", "measurement_id"),
            ("patterns", "pattern_id"),
        ):
            values = {
                f"POWBASE_{field.split('_')[0].upper()}_{entry_id}"
                for entry_id in CANDIDATE_ENTRY_IDS
            }
            if field == "pattern_id":
                values = {f"POWBASE_PAT_{entry_id}" for entry_id in CANDIDATE_ENTRY_IDS}
            elif field == "measurement_id":
                values = {
                    f"POWBASE_MEAS_{entry_id}" for entry_id in CANDIDATE_ENTRY_IDS
                }
            else:
                values = {f"POWBASE_SAM_{entry_id}" for entry_id in CANDIDATE_ENTRY_IDS}
            mongo_candidate_collisions[field] = sorted(
                item[field]
                for item in mongo_report["collections"][collection]["id_collisions"]
                if item[field] in values
            )

    archive_hashes_after = {
        entry_id: _sha256_bytes(
            (archive_root / "archives" / inclusion[entry_id]["source_filename"]).read_bytes()
        )
        for entry_id in CANDIDATE_ENTRY_IDS
    }
    if archive_hashes_before != archive_hashes_after:
        raise ValueError("source archive bytes changed during validation")

    all_pass = all(record["status"] == "PASS" for record in records)
    all_pass = all_pass and not any(local_collision_map.values())
    all_pass = all_pass and not any(mongo_candidate_collisions.values())
    return {
        "schema_version": "powbase_candidate_canonical_validation_v1",
        "read_only": True,
        "scope": {
            "entry_ids": CANDIDATE_ENTRY_IDS,
            "existing_44_pattern_count": EXPECTED_PRODUCTION_PATTERN_COUNT,
            "proposed_pattern_count_if_all_pass": EXPECTED_PROPOSED_PATTERN_COUNT,
        },
        "records": records,
        "identifier_collision_check": {
            "local_against_existing_44": local_collision_map,
            "mongo_read_only": mongo_candidate_collisions,
            "mongo_report": mongo_report,
        },
        "source_archive_hash_check": {
            "unchanged": True,
            "before": archive_hashes_before,
            "after": archive_hashes_after,
        },
        "summary": {
            "candidate_count": len(records),
            "pass_count": sum(record["status"] == "PASS" for record in records),
            "fail_count": sum(record["status"] == "FAIL" for record in records),
            "all_pass": all_pass,
            "proposed_powbase_xray_production_count": (
                48 if all_pass else None
            ),
            "proposed_crystaldb_pattern_count": (
                EXPECTED_PROPOSED_PATTERN_COUNT if all_pass else None
            ),
            "mongodb_writes": False,
            "source_archives_modified": False,
            "canonical_records_modified": False,
            "entry_137_processed": False,
            "other_conditional_records_processed": False,
        },
    }


CSV_FIELDS = [
    "entry_id",
    "status",
    "source_label_raw",
    "sample_id",
    "measurement_id",
    "pattern_id",
    "detected_content_family",
    "recovery_rule",
    "start",
    "step",
    "end",
    "end_explicit_in_source",
    "expected_point_count",
    "observed_point_count",
    "canonical_point_count",
    "monotonic_2theta",
    "finite_intensities",
    "wavelength_angstrom",
    "wavelength_kalpha2_angstrom",
    "explicit_wavelength_values_angstrom",
    "source_archive_sha256",
    "source_member_sha256",
    "validation_issues",
]


def write_outputs(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "powbase_candidate_canonical_validation_v1.json"
    csv_path = output_dir / "powbase_candidate_canonical_validation_v1.csv"
    summary_path = output_dir / "powbase_candidate_canonical_validation_v1_summary.md"

    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in result["records"]:
            writer.writerow(
                {
                    field: _json(record[field])
                    if isinstance(record.get(field), (list, dict))
                    else record.get(field, "")
                    for field in CSV_FIELDS
                }
            )

    lines = [
        "# PowBase Candidate Canonical Validation v1",
        "",
        "Read-only validation of entries 15, 74, 121, and 156 using existing "
        "review rules and the existing PowBase canonical document builder.",
        "",
        "| Entry | Result | Recovery rule | Canonical points | Wavelength | Issues |",
        "|---:|---|---|---:|---|---|",
    ]
    for record in result["records"]:
        wavelengths = record["explicit_wavelength_values_angstrom"]
        wavelength_text = _json(wavelengths) if wavelengths else "unknown"
        issues = "; ".join(record["validation_issues"]) or "none"
        lines.append(
            f"| {record['entry_id']} | **{record['status']}** | "
            f"{record['recovery_rule']} | {record['canonical_point_count']} | "
            f"{wavelength_text} | {issues} |"
        )
    lines.extend(
        [
            "",
            f"- PASS: **{result['summary']['pass_count']}**",
            f"- FAIL: **{result['summary']['fail_count']}**",
            f"- Proposed PowBase X-ray production count: "
            f"**{result['summary']['proposed_powbase_xray_production_count']}**",
            f"- Proposed CrystalDB pattern count: "
            f"**{result['summary']['proposed_crystaldb_pattern_count']}**",
            "- MongoDB writes: **none**",
            "- Source archives modified: **no**",
            "- Entry 137 processed: **no**",
            "- Other conditional records processed: **no**",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return json_path, csv_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-mongo-check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = build_validation(inspect_mongo=not args.skip_mongo_check)
    outputs = write_outputs(result, args.output_dir)
    print(
        json.dumps(
            {"summary": result["summary"], "outputs": [str(path) for path in outputs]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
