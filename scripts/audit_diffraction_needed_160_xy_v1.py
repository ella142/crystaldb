"""Audit experimental XY availability for the current 160 rescue samples.

The script is read-only with respect to MongoDB. It reads the current
rescue_review_v1 sample list and rruff.xy_raw / rruff.xy_processed, then
writes only the requested local CSV and Markdown audit outputs.
"""

from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = PROJECT_ROOT / "data" / "mappings" / "rescue_review_v1"
TARGET_FILE = REVIEW_DIR / "rruff_rescue_summary_v1.csv"
OUTPUT_CSV = REVIEW_DIR / "diffraction_needed_160_xy_audit.csv"
OUTPUT_MD = REVIEW_DIR / "diffraction_needed_160_xy_audit.md"

MONGO_URI = os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://127.0.0.1:27017")
DATABASE_NAME = os.environ.get("CRYSTALDB_MONGO_DATABASE", "rruff")

CALCULATED_RE = re.compile(
    r"\b(?:calculated|simulated|computed)\b",
    re.IGNORECASE,
)
POWDER_RE = re.compile(r"\bpowder\b", re.IGNORECASE)

CSV_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "has_raw",
    "has_processed",
    "raw_point_count",
    "processed_point_count",
    "diffraction_sample_description",
    "xy_origin_status",
    "reason",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_description(document: dict[str, Any] | None) -> str:
    if document is None:
        return ""
    metadata = document.get("metadata") or {}
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("DIFFRACTION SAMPLE DESCRIPTION") or "").strip()


def xy_arrays(document: dict[str, Any] | None) -> tuple[list[Any], list[Any]]:
    if document is None:
        return [], []
    xrd = document.get("xrd") or {}
    return xrd.get("two_theta") or [], xrd.get("intensity") or []


def valid_xy(document: dict[str, Any] | None) -> bool:
    two_theta, intensity = xy_arrays(document)
    return bool(two_theta) and bool(intensity) and len(two_theta) == len(intensity)


def point_count(document: dict[str, Any] | None) -> int | str:
    if document is None:
        return ""
    xrd = document.get("xrd") or {}
    stored_count = xrd.get("point_count")
    if stored_count is not None:
        return int(stored_count)
    two_theta, _ = xy_arrays(document)
    return len(two_theta)


def classify_description(description: str) -> str:
    """Classify origin using only the original source description."""

    if not description:
        return "uncertain_origin"
    if CALCULATED_RE.search(description):
        return "calculated_only"
    if POWDER_RE.search(description):
        return "experimental_xy_available"
    return "uncertain_origin"


def load_target_rows() -> list[dict[str, str]]:
    rows = [
        row
        for row in read_csv(TARGET_FILE)
        if row.get("rescue_category", "").strip()
        == "diffraction_validation_needed"
    ]
    sample_ids = [row.get("sample_id", "").strip() for row in rows]
    if len(rows) != 160:
        raise RuntimeError(
            f"Expected exactly 160 diffraction_validation_needed rows, found {len(rows)}"
        )
    if not all(sample_ids):
        raise RuntimeError("Target list contains a blank sample_id")
    if len(set(sample_ids)) != len(sample_ids):
        raise RuntimeError("Target list contains duplicate sample_id values")
    return rows


def load_xy_documents(
    database: Any,
    sample_ids: list[str],
) -> dict[str, dict[str, dict[str, list[dict[str, Any]]]]]:
    """Return sample -> filename_sample_id -> representation -> documents."""

    records: dict[
        str,
        dict[str, dict[str, list[dict[str, Any]]]],
    ] = defaultdict(lambda: defaultdict(lambda: {"raw": [], "processed": []}))

    projection = {
        "_id": 0,
        "sample_id": 1,
        "filename_sample_id": 1,
        "xrd.point_count": 1,
        "xrd.two_theta": 1,
        "xrd.intensity": 1,
        "metadata.DIFFRACTION SAMPLE DESCRIPTION": 1,
    }

    for representation, collection_name in (
        ("raw", "xy_raw"),
        ("processed", "xy_processed"),
    ):
        for document in database[collection_name].find(
            {"sample_id": {"$in": sample_ids}},
            projection,
        ):
            sample_id = str(document.get("sample_id") or "").strip()
            filename_sample_id = str(
                document.get("filename_sample_id") or ""
            ).strip()
            if not sample_id or not filename_sample_id:
                continue
            records[sample_id][filename_sample_id][representation].append(document)

    return records


def choose_document(
    documents: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not documents:
        return None
    if len(documents) > 1:
        raise RuntimeError(
            "Duplicate documents for one representation and filename_sample_id: "
            + repr(
                (
                    documents[0].get("sample_id"),
                    documents[0].get("filename_sample_id"),
                )
            )
        )
    return documents[0]


def format_keys(keys: list[str]) -> str:
    return ";".join(keys)


def format_counts(
    keys: list[str],
    documents_by_key: dict[str, dict[str, dict[str, Any] | None]],
    representation: str,
) -> str:
    values: list[str] = []
    for key in keys:
        value = point_count(documents_by_key[key].get(representation))
        if value != "":
            values.append(str(value))
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ";".join(values)


def description_for_measurement(
    documents_by_key: dict[str, dict[str, dict[str, Any] | None]],
    key: str,
) -> str:
    raw_description = source_description(documents_by_key[key].get("raw"))
    processed_description = source_description(
        documents_by_key[key].get("processed")
    )
    descriptions = []
    for description in (raw_description, processed_description):
        if description and description not in descriptions:
            descriptions.append(description)
    return " | ".join(descriptions)


def audit_sample(
    target: dict[str, str],
    sample_records: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, str]:
    sample_id = target["sample_id"].strip()
    measurement_records = sample_records.get(sample_id, {})
    keys = sorted(measurement_records)

    documents_by_key: dict[str, dict[str, dict[str, Any] | None]] = {}
    for filename_sample_id in keys:
        bundle = measurement_records[filename_sample_id]
        documents_by_key[filename_sample_id] = {
            "raw": choose_document(bundle["raw"]),
            "processed": choose_document(bundle["processed"]),
        }

    usable_profiles: list[tuple[str, str, str]] = []
    descriptions: list[str] = []
    for filename_sample_id in keys:
        bundle = documents_by_key[filename_sample_id]
        for representation in ("raw", "processed"):
            document = bundle[representation]
            if document is None:
                continue
            description = source_description(document)
            if description and description not in descriptions:
                descriptions.append(description)
            if valid_xy(document):
                usable_profiles.append(
                    (
                        filename_sample_id,
                        representation,
                        classify_description(description),
                    )
                )

    origins = {item[2] for item in usable_profiles}
    if "experimental_xy_available" in origins:
        status = "experimental_xy_available"
        reason = (
            "Valid XY is present and the original description contains "
            "powder wording without calculated/simulated/computed wording."
        )
    elif "calculated_only" in origins:
        status = "calculated_only"
        reason = (
            "Valid XY is present, but all usable profiles are explicitly "
            "calculated/simulated/computed in the original description."
        )
    elif "uncertain_origin" in origins:
        status = "uncertain_origin"
        reason = (
            "Valid XY is present, but the original description does not "
            "reliably identify experimental powder or calculated/simulated origin."
        )
    else:
        status = "no_usable_xy"
        if not keys:
            reason = (
                "No rruff.xy_raw or rruff.xy_processed record with a "
                "filename_sample_id was found for this sample."
            )
        else:
            reason = (
                "XY records are present, but no non-empty equal-length "
                "two_theta/intensity arrays were found."
            )

    return {
        "sample_id": sample_id,
        "filename_sample_id": format_keys(keys),
        "has_raw": str(
            any(documents_by_key[key]["raw"] is not None for key in keys)
        ).lower(),
        "has_processed": str(
            any(documents_by_key[key]["processed"] is not None for key in keys)
        ).lower(),
        "raw_point_count": format_counts(keys, documents_by_key, "raw"),
        "processed_point_count": format_counts(
            keys,
            documents_by_key,
            "processed",
        ),
        "diffraction_sample_description": " | ".join(descriptions),
        "xy_origin_status": status,
        "reason": reason,
    }


def write_csv(rows: list[dict[str, str]]) -> None:
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CSV_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]]) -> None:
    counts = {
        status: sum(row["xy_origin_status"] == status for row in rows)
        for status in (
            "experimental_xy_available",
            "calculated_only",
            "uncertain_origin",
            "no_usable_xy",
        )
    }
    total = len(rows)
    total_check = sum(counts.values())

    lines = [
        "# Diffraction-Validation-Needed 160 XY Audit",
        "",
        "本审计只处理 `rescue_review_v1` 当前 160 条 "
        "`diffraction_validation_needed` 样品。",
        "未重新搜索 COD、下载 CIF、运行 diffraction matching，也未修改 "
        "807 curated、12 条 rescue-ready、177 条 DIF 外 final manifest、v2/v3、"
        "MongoDB 或正式 CrystalDB。",
        "",
        "## Summary",
        "",
        f"- 160 total = {total}",
        f"- experimental_xy_available = {counts['experimental_xy_available']}",
        f"- calculated_only = {counts['calculated_only']}",
        f"- uncertain_origin = {counts['uncertain_origin']}",
        f"- no_usable_xy = {counts['no_usable_xy']}",
        f"- four_class_sum = {total_check}",
        f"- four_class_sum_matches_160 = {'true' if total_check == 160 else 'false'}",
        "",
        "## Classification Rules",
        "",
        "- `experimental_xy_available`: valid non-empty equal-length XY arrays exist, and the original `DIFFRACTION SAMPLE DESCRIPTION` contains `Powder` without calculated/simulated/computed wording.",
        "- `calculated_only`: valid XY arrays exist, but all usable profiles explicitly contain calculated/simulated/computed wording.",
        "- `uncertain_origin`: valid XY arrays exist, but the description does not reliably identify either origin.",
        "- `no_usable_xy`: no valid non-empty equal-length `two_theta` and `intensity` arrays exist.",
        "",
        "raw and processed records were merged by `filename_sample_id`; the two representations of one measurement are not counted twice.",
        "For shared metadata, the original description values are preserved. The source description is not inferred from the presence of raw or processed data.",
        "",
        "## Audit Rows",
        "",
        "| sample_id | filename_sample_id | has_raw | has_processed | raw_point_count | processed_point_count | diffraction_sample_description | xy_origin_status | reason |",
        "|---|---|---|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        values = [
            row["sample_id"],
            row["filename_sample_id"],
            row["has_raw"],
            row["has_processed"],
            row["raw_point_count"] or "null",
            row["processed_point_count"] or "null",
            row["diffraction_sample_description"] or "null",
            row["xy_origin_status"],
            row["reason"],
        ]
        lines.append(
            "| "
            + " | ".join(value.replace("|", "\\|") for value in values)
            + " |"
        )

    lines.extend(
        [
            "",
            "## Exact Sources",
            "",
            f"- Target sample list: `{TARGET_FILE.relative_to(PROJECT_ROOT).as_posix()}` filtered by `rescue_category=diffraction_validation_needed`.",
            "- XY collections: MongoDB database `rruff`, collections `xy_raw` and `xy_processed`.",
            "- Source metadata field: `metadata[\"DIFFRACTION SAMPLE DESCRIPTION\"]`.",
            "- XY validity fields: `xrd.two_theta` and `xrd.intensity`, both non-empty and equal length.",
            "",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    target_rows = load_target_rows()
    sample_ids = [row["sample_id"].strip() for row in target_rows]

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        database = client[DATABASE_NAME]
        records = load_xy_documents(database, sample_ids)
    finally:
        client.close()

    audit_rows = [
        audit_sample(target, records)
        for target in sorted(target_rows, key=lambda row: row["sample_id"])
    ]

    if len(audit_rows) != 160:
        raise RuntimeError(f"Expected 160 output rows, found {len(audit_rows)}")
    if len({row["sample_id"] for row in audit_rows}) != 160:
        raise RuntimeError("Output contains duplicate sample_id values")

    counts = {
        status: sum(row["xy_origin_status"] == status for row in audit_rows)
        for status in (
            "experimental_xy_available",
            "calculated_only",
            "uncertain_origin",
            "no_usable_xy",
        )
    }
    if sum(counts.values()) != 160:
        raise RuntimeError(f"Four-class total is not 160: {counts}")

    write_csv(audit_rows)
    write_markdown(audit_rows)

    print(f"160 total = {len(audit_rows)}")
    for status in (
        "experimental_xy_available",
        "calculated_only",
        "uncertain_origin",
        "no_usable_xy",
    ):
        print(f"{status} = {counts[status]}")
    print(f"four_class_sum = {sum(counts.values())}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"MD: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
