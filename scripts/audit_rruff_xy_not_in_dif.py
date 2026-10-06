"""Audit RRUFF XY measurements whose sample_id is absent from DIF.

This script is read-only with respect to MongoDB. It writes only the two
requested local audit artifacts.
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
CSV_OUTPUT = PROJECT_ROOT / "data" / "mappings" / "rruff_xy_not_in_dif_audit.csv"
MD_OUTPUT = PROJECT_ROOT / "data" / "mappings" / "rruff_xy_not_in_dif_audit.md"

MONGO_URI = os.environ.get("CRYSTALDB_MONGO_URI", "mongodb://127.0.0.1:27017")
DATABASE_NAME = "rruff"

CALCULATED_RE = re.compile(r"\b(?:calculated|simulated|computed)\b", re.IGNORECASE)
POWDER_RE = re.compile(r"\bpowder\b", re.IGNORECASE)

CSV_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "has_raw",
    "has_processed",
    "raw_point_count",
    "processed_point_count",
    "mineral",
    "diffraction_sample_description",
    "filetype",
    "profile_origin",
]


def profile_origin(description: Any) -> str:
    """Classify only from the RRUFF source description metadata."""

    text = str(description or "").strip()
    if not text:
        return "uncertain"
    if CALCULATED_RE.search(text):
        return "calculated"
    if POWDER_RE.search(text):
        return "experimental"
    return "uncertain"


def point_count(document: dict[str, Any] | None) -> int | str:
    if document is None:
        return ""
    xrd = document.get("xrd") or {}
    stored_count = xrd.get("point_count")
    if stored_count is not None:
        return int(stored_count)
    return len(xrd.get("two_theta") or [])


def metadata_value(document: dict[str, Any] | None, key: str) -> Any:
    if document is None:
        return None
    metadata = document.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    return metadata.get(key)


def preferred_value(bundle: dict[str, dict[str, Any] | None], getter) -> Any:
    for representation in ("raw", "processed"):
        document = bundle.get(representation)
        value = getter(document)
        if value not in (None, ""):
            return value
    return None


def load_measurements(database) -> dict[str, dict[str, dict[str, Any] | None]]:
    measurements: dict[str, dict[str, dict[str, Any] | None]] = defaultdict(
        lambda: {"raw": None, "processed": None}
    )

    for representation, collection_name in (
        ("raw", "xy_raw"),
        ("processed", "xy_processed"),
    ):
        projection = {
            "_id": 0,
            "sample_id": 1,
            "filename_sample_id": 1,
            "mineral": 1,
            "metadata": 1,
            "xrd.point_count": 1,
        }
        for document in database[collection_name].find({}, projection):
            key = document.get("filename_sample_id")
            if not key:
                raise RuntimeError(
                    f"{collection_name} contains a record without filename_sample_id"
                )
            if measurements[key][representation] is not None:
                raise RuntimeError(
                    f"Duplicate {representation} filename_sample_id: {key}"
                )
            measurements[key][representation] = document

    return measurements


def build_rows(database) -> list[dict[str, Any]]:
    dif_sample_ids = {
        document.get("sample_id")
        for document in database.dif.find({}, {"_id": 0, "sample_id": 1})
        if document.get("sample_id") not in (None, "")
    }
    measurements = load_measurements(database)
    rows = []

    for filename_sample_id in sorted(measurements):
        bundle = measurements[filename_sample_id]
        raw = bundle["raw"]
        processed = bundle["processed"]
        sample_id = preferred_value(bundle, lambda document: (document or {}).get("sample_id"))
        if sample_id in dif_sample_ids:
            continue

        description = preferred_value(
            bundle,
            lambda document: metadata_value(
                document, "DIFFRACTION SAMPLE DESCRIPTION"
            ),
        )
        rows.append(
            {
                "sample_id": sample_id or "",
                "filename_sample_id": filename_sample_id,
                "has_raw": raw is not None,
                "has_processed": processed is not None,
                "raw_point_count": point_count(raw),
                "processed_point_count": point_count(processed),
                "mineral": preferred_value(
                    bundle, lambda document: (document or {}).get("mineral")
                )
                or "",
                "diffraction_sample_description": description or "",
                "filetype": preferred_value(
                    bundle,
                    lambda document: metadata_value(document, "FILETYPE"),
                )
                or "",
                "profile_origin": profile_origin(description),
            }
        )

    return rows


def write_outputs(rows: list[dict[str, Any]]) -> None:
    CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    raw_only = sum(row["has_raw"] and not row["has_processed"] for row in rows)
    processed_only = sum(
        not row["has_raw"] and row["has_processed"] for row in rows
    )
    raw_and_processed = sum(
        row["has_raw"] and row["has_processed"] for row in rows
    )
    origin_counts = {
        origin: sum(row["profile_origin"] == origin for row in rows)
        for origin in ("experimental", "calculated", "uncertain")
    }

    summary_lines = [
        f"unique measurements outside DIF = {len(rows)}",
        f"unique sample_ids outside DIF = {len({row['sample_id'] for row in rows})}",
        f"raw only = {raw_only}",
        f"processed only = {processed_only}",
        f"raw + processed = {raw_and_processed}",
        f"experimental = {origin_counts['experimental']}",
        f"calculated = {origin_counts['calculated']}",
        f"uncertain = {origin_counts['uncertain']}",
    ]

    markdown = "\n".join(
        [
            "# RRUFF XY Outside DIF Audit",
            "",
            "Read-only audit of `rruff.dif`, `rruff.xy_raw`, and `rruff.xy_processed`.",
            "No MongoDB source collection, pipeline output, curated dataset, v2/v3, or formal CrystalDB data was modified.",
            "",
            "## Summary",
            "",
            *summary_lines,
            "",
            "## Method",
            "",
            "- The DIF universe is the set of unique `sample_id` values read from `rruff.dif`.",
            "- XY records are scanned from both collections and merged by `filename_sample_id`.",
            "- A merged measurement is included when its `sample_id` is absent from the DIF universe.",
            "- For shared measurements, raw metadata is preferred for shared fields; processed metadata is used when raw is absent.",
            "- `profile_origin` uses only `metadata[\"DIFFRACTION SAMPLE DESCRIPTION\"]`: calculated/simulated/computed wording is `calculated`; powder wording without those terms is `experimental`; all other descriptions are `uncertain`.",
            "- `raw_point_count` and `processed_point_count` come from the source document `xrd.point_count`.",
            "",
        ]
    )
    MD_OUTPUT.write_text(markdown, encoding="utf-8", newline="\n")

    print("unique measurements outside DIF =", len(rows))
    print("unique sample_ids outside DIF =", len({row["sample_id"] for row in rows}))
    print("raw only =", raw_only)
    print("processed only =", processed_only)
    print("raw + processed =", raw_and_processed)
    print("experimental =", origin_counts["experimental"])
    print("calculated =", origin_counts["calculated"])
    print("uncertain =", origin_counts["uncertain"])
    print("CSV:", CSV_OUTPUT)
    print("MD:", MD_OUTPUT)


def main() -> None:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        rows = build_rows(client[DATABASE_NAME])
        write_outputs(rows)
    finally:
        client.close()


if __name__ == "__main__":
    main()
