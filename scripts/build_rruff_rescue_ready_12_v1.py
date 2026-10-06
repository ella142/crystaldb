"""Build the confirmed 12-sample RRUFF rescue-link audit.

This script only selects and joins existing audit outputs. It does not search
COD, download CIFs, run diffraction, or modify historical mappings.
"""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = PROJECT_ROOT / "data" / "mappings" / "rescue_review_v1"

STRUCTURE_REVIEW = REVIEW_DIR / "high_priority_36_review.csv"
DIFFRACTION_REVIEW = REVIEW_DIR / "high_priority_35_diffraction_validation.csv"
CANDIDATE_DETAILS = REVIEW_DIR / "rruff_rescue_candidate_details_v1.csv"

OUTPUT_CSV = REVIEW_DIR / "rruff_rescue_ready_12_v1.csv"
OUTPUT_MD = REVIEW_DIR / "rruff_rescue_ready_12_v1.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("sample_id", "").strip(), row.get("candidate_cod_id", row.get("cod_id", "")).strip()


def require_single(rows: list[dict[str, str]], label: str) -> dict[str, str]:
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one {label}, found {len(rows)}")
    return rows[0]


def get_detail(
    details_by_key: dict[tuple[str, str], dict[str, str]],
    sample_id: str,
    cod_id: str,
) -> dict[str, str]:
    try:
        return details_by_key[(sample_id, cod_id)]
    except KeyError as exc:
        raise ValueError(f"Missing candidate detail for {sample_id} / {cod_id}") from exc


def normalize_cif_path(raw_path: str) -> Path:
    raw = raw_path.strip()
    if not raw:
        return Path()
    return PROJECT_ROOT / raw.replace("/", "\\")


def build_structure_only_row(
    source: dict[str, str],
    detail: dict[str, str],
) -> dict[str, str]:
    sample_id, cod_id = key(source)
    cif_path = source.get("cif_file_path", "").strip() or detail.get("cif_file_path", "").strip()
    return {
        "sample_id": sample_id,
        "candidate_cod_id": cod_id,
        "mineral_name": detail.get("sample_mineral", "").strip()
        or detail.get("reference_structure_name", "").strip(),
        "candidate_name": source.get("candidate_mineral_name", "").strip(),
        "chemistry_status": source.get("chemistry_status", "").strip(),
        "space_group_status": source.get("space_group_status", "").strip(),
        "cell_length_difference": source.get("max_length_relative_difference", "").strip(),
        "cell_angle_difference": source.get("max_angle_difference", "").strip(),
        "diffraction_status": "null",
        "matched_count": "null",
        "median_residual": "null",
        "weighted_residual": "null",
        "max_residual": "null",
        "zero_shift": "null",
        "rescue_basis": "structurally_ready_for_rescue",
        "source_files": ";".join(
            [
                STRUCTURE_REVIEW.relative_to(PROJECT_ROOT).as_posix(),
                CANDIDATE_DETAILS.relative_to(PROJECT_ROOT).as_posix(),
                cif_path,
            ]
        ),
        "candidate_formula": source.get("candidate_formula", "").strip(),
        "cif_file_path": cif_path,
        "local_cif_parse_status": source.get("local_cif_parse_status", "").strip()
        or detail.get("candidate_parse_status", "").strip(),
        "local_cif_exists": str(normalize_cif_path(cif_path).is_file()).lower(),
        "name_support": source.get("name_support", "").strip(),
        "cell_status": source.get("cell_status", "").strip(),
        "reason": source.get("reason", "").strip(),
    }


def build_diffraction_row(
    source: dict[str, str],
    detail: dict[str, str],
) -> dict[str, str]:
    sample_id, cod_id = key(source)
    cif_path = source.get("cif_file_path", "").strip() or detail.get("cif_file_path", "").strip()
    return {
        "sample_id": sample_id,
        "candidate_cod_id": cod_id,
        "mineral_name": detail.get("sample_mineral", "").strip()
        or detail.get("reference_structure_name", "").strip(),
        "candidate_name": source.get("candidate_mineral_name", "").strip(),
        "chemistry_status": source.get("prior_chemistry_status", "").strip(),
        "space_group_status": source.get("prior_space_group_status", "").strip(),
        "cell_length_difference": detail.get("max_length_relative_difference", "").strip(),
        "cell_angle_difference": detail.get("max_angle_difference", "").strip(),
        "diffraction_status": source.get("candidate_diffraction_status", "").strip(),
        "matched_count": source.get("matched_count", "").strip(),
        "median_residual": source.get("median_abs_residual", "").strip(),
        "weighted_residual": source.get("weighted_mean_abs_residual", "").strip(),
        "max_residual": source.get("max_abs_residual", "").strip(),
        "zero_shift": source.get("zero_shift", "").strip(),
        "rescue_basis": "diffraction_supported_rescue",
        "source_files": ";".join(
            [
                DIFFRACTION_REVIEW.relative_to(PROJECT_ROOT).as_posix(),
                STRUCTURE_REVIEW.relative_to(PROJECT_ROOT).as_posix(),
                CANDIDATE_DETAILS.relative_to(PROJECT_ROOT).as_posix(),
                cif_path,
            ]
        ),
        "candidate_formula": source.get("candidate_formula", "").strip(),
        "cif_file_path": cif_path,
        "local_cif_parse_status": detail.get("candidate_parse_status", "").strip(),
        "local_cif_exists": str(normalize_cif_path(cif_path).is_file()).lower(),
        "name_support": detail.get("name_support", "").strip(),
        "cell_status": detail.get("cell_status", "").strip(),
        "reason": source.get("reason", "").strip(),
    }


def write_csv(rows: list[dict[str, str]]) -> None:
    fields = [
        "sample_id",
        "candidate_cod_id",
        "mineral_name",
        "candidate_name",
        "chemistry_status",
        "space_group_status",
        "cell_length_difference",
        "cell_angle_difference",
        "diffraction_status",
        "matched_count",
        "median_residual",
        "weighted_residual",
        "max_residual",
        "zero_shift",
        "rescue_basis",
        "source_files",
        "candidate_formula",
        "cif_file_path",
        "local_cif_parse_status",
        "local_cif_exists",
        "name_support",
        "cell_status",
        "reason",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def markdown_value(value: str) -> str:
    return value if value else "null"


def write_markdown(rows: list[dict[str, str]], missing_local_cif: int) -> None:
    structure_count = sum(row["rescue_basis"] == "structurally_ready_for_rescue" for row in rows)
    diffraction_count = sum(row["rescue_basis"] == "diffraction_supported_rescue" for row in rows)
    duplicate_sample_count = len(rows) - len({row["sample_id"] for row in rows})
    missing_cod_count = sum(not row["candidate_cod_id"] for row in rows)

    lines = [
        "# RRUFF Rescue-Ready 12 Audit",
        "",
        "本文件只整理现有审计结果中已经确认的 12 条 rescue-ready 样品。",
        "未重新检索 COD、下载 CIF、运行 diffraction，也未修改 807 curated、v2/v3、MongoDB 或正式 CrystalDB。",
        "",
        "## Summary",
        "",
        f"- total_rescue_ready = {len(rows)}",
        f"- structure_only_supported = {structure_count}",
        f"- diffraction_supported = {diffraction_count}",
        f"- duplicate_sample_id = {duplicate_sample_count}",
        f"- missing_cod_id = {missing_cod_count}",
        f"- missing_local_cif = {missing_local_cif}",
        "",
        "晶胞差异沿用 candidate details 中的原始字段：",
        "`cell_length_difference` 为相对长度差（fraction），`cell_angle_difference` 为角度差（degree）。",
        "没有 diffraction 的结构确认项，其 diffraction 相关字段均保留为 `null`。",
        "",
        "## Rescue Links",
        "",
        "| sample_id | COD ID | mineral_name | candidate_name | chemistry_status | space_group_status | cell_length_difference | cell_angle_difference | diffraction_status | matched_count | median_residual | weighted_residual | max_residual | zero_shift | rescue_basis |",
        "|---|---:|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|",
    ]

    for row in rows:
        values = [
            row["sample_id"],
            row["candidate_cod_id"],
            row["mineral_name"],
            row["candidate_name"],
            row["chemistry_status"],
            row["space_group_status"],
            markdown_value(row["cell_length_difference"]),
            markdown_value(row["cell_angle_difference"]),
            markdown_value(row["diffraction_status"]),
            markdown_value(row["matched_count"]),
            markdown_value(row["median_residual"]),
            markdown_value(row["weighted_residual"]),
            markdown_value(row["max_residual"]),
            markdown_value(row["zero_shift"]),
            row["rescue_basis"],
        ]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")

    lines.extend(
        [
            "",
            "## Required Mapping List",
            "",
        ]
    )
    for row in rows:
        lines.append(
            f"- {row['sample_id']} -> {row['candidate_cod_id']} -> {row['rescue_basis']}"
        )

    lines.extend(
        [
            "",
            "## Source Files",
            "",
            f"- `{STRUCTURE_REVIEW.relative_to(PROJECT_ROOT).as_posix()}`",
            f"- `{DIFFRACTION_REVIEW.relative_to(PROJECT_ROOT).as_posix()}`",
            f"- `{CANDIDATE_DETAILS.relative_to(PROJECT_ROOT).as_posix()}`",
            "- corresponding local CIF files listed in the CSV `cif_file_path` and `source_files` columns",
            "",
            "这些结果只是确认可补救的结构链接清单，不自动并入原 807，也不改变任何历史结果。",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    structure_rows = read_csv(STRUCTURE_REVIEW)
    diffraction_rows = read_csv(DIFFRACTION_REVIEW)
    detail_rows = read_csv(CANDIDATE_DETAILS)

    details_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in detail_rows:
        row_key = key(row)
        if row_key in details_by_key:
            raise ValueError(f"Duplicate candidate detail key: {row_key}")
        details_by_key[row_key] = row

    structure_source = require_single(
        [row for row in structure_rows if row.get("final_status", "").strip() == "structurally_ready_for_rescue"],
        "structurally_ready_for_rescue source row",
    )
    diffraction_sources = [
        row
        for row in diffraction_rows
        if row.get("final_status", "").strip() == "diffraction_supported_rescue"
    ]
    if len(diffraction_sources) != 11:
        raise ValueError(
            f"Expected exactly 11 diffraction_supported_rescue rows, found {len(diffraction_sources)}"
        )

    selected_keys = [key(structure_source)] + [key(row) for row in diffraction_sources]
    if len({sample_id for sample_id, _ in selected_keys}) != 12:
        raise ValueError("Selected rescue rows do not contain 12 unique sample IDs")
    if any(not cod_id for _, cod_id in selected_keys):
        raise ValueError("Selected rescue rows contain a missing COD ID")

    rows = [
        build_structure_only_row(
            structure_source,
            get_detail(details_by_key, *key(structure_source)),
        )
    ]
    rows.extend(
        build_diffraction_row(row, get_detail(details_by_key, *key(row)))
        for row in sorted(diffraction_sources, key=lambda item: key(item)[0])
    )

    missing_local_cif = sum(row["local_cif_exists"] != "true" for row in rows)
    if missing_local_cif:
        raise ValueError(f"Selected rescue rows have {missing_local_cif} missing local CIF files")

    write_csv(rows)
    write_markdown(rows, missing_local_cif)

    print(f"Wrote {OUTPUT_CSV}")
    print(f"Wrote {OUTPUT_MD}")
    print(f"Rows: {len(rows)}")
    print(f"Structure-only: {sum(row['rescue_basis'] == 'structurally_ready_for_rescue' for row in rows)}")
    print(f"Diffraction-supported: {sum(row['rescue_basis'] == 'diffraction_supported_rescue' for row in rows)}")
    print(f"Missing local CIF: {missing_local_cif}")


if __name__ == "__main__":
    main()
