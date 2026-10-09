"""Produce a conservative review of the complete PowBase audit.

This module reads the existing audit inventory and locally cached source
archives.  It never writes MongoDB, canonical CrystalDB data, or source
archives.  The review layer can recognize a small number of explicitly
documented legacy formats that the base inventory intentionally leaves
unresolved, but it does not promote those records to canonical ingestion.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.audit_powbase import (
        collect_numeric_rows,
        decode_member_text,
        find_intensity_header_and_block,
        numeric_token_value,
    )
except ModuleNotFoundError:
    from audit_powbase import (
        collect_numeric_rows,
        decode_member_text,
        find_intensity_header_and_block,
        numeric_token_value,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"
DEFAULT_INVENTORY = DEFAULT_ROOT / "inventory" / "powbase_archive_inventory.jsonl"
DEFAULT_INDEX = DEFAULT_ROOT / "inventory" / "powbase_index_inventory.jsonl"
DEFAULT_OUTPUT = DEFAULT_ROOT / "review"

SUPPORTED_BASE_FAMILIES = {
    "legacy_intensity_array",
    "fullprof_style_pattern",
    "commented_pdcif",
}
VALID_ARCHIVE_STATUSES = {"ok", "crc_error", "not_zip_readable_text"}
NUMERIC_RE = (
    r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[EeDd][+-]?\d+)?"
)
HEADER_WITH_SUFFIX_RE = re.compile(
    rf"^\s*(?P<start>{NUMERIC_RE})\s+"
    rf"(?P<step>{NUMERIC_RE})\s+"
    rf"(?P<end>{NUMERIC_RE})\s+"
    rf"(?P<suffix>\S.*\S|\S)\s*$"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def first_number(value: str) -> float | None:
    match = re.search(NUMERIC_RE, value)
    if not match:
        return None
    try:
        return float(match.group(0).replace("D", "E").replace("d", "e"))
    except ValueError:
        return None


def trailing_zero_count(tokens: list[str]) -> int:
    count = 0
    for token in reversed(tokens):
        if numeric_token_value(token) == 0:
            count += 1
        else:
            break
    return count


def assess_numeric_block(
    *,
    start: float,
    step: float,
    end: float,
    block: dict[str, Any],
) -> dict[str, Any]:
    finite = all(
        math.isfinite(value) for value in (start, step, end)
    )
    ordered = bool(finite and step > 0 and end > start)
    expected = None
    grid_aligned = False
    if ordered:
        ratio = (end - start) / step
        expected = round(ratio) + 1
        grid_aligned = math.isclose(
            ratio,
            expected - 1,
            rel_tol=1e-9,
            abs_tol=1e-6,
        )
    raw_count = block["numeric_value_count"]
    zero_count = trailing_zero_count(block["values"])
    nonzero_trimmed_count = raw_count - zero_count
    exact = bool(ordered and expected == raw_count)
    padding_candidate = bool(
        ordered
        and expected == nonzero_trimmed_count
        and zero_count > 0
    )
    fixed_width_candidate = bool(
        padding_candidate
        and block["dominant_numeric_column_count"]
        and len(block["rows"]) > 0
        and len(block["rows"][-1])
        == block["dominant_numeric_column_count"]
        and len(block["numeric_column_counts"]) == 1
        and raw_count % block["dominant_numeric_column_count"] == 0
        and zero_count <= block["dominant_numeric_column_count"]
    )
    reasons: list[str] = []
    if not ordered:
        reasons.append("header range is not finite and ordered")
    if expected is not None and expected != raw_count:
        reasons.append(
            f"raw observed count {raw_count} differs from expected {expected}"
        )
    if padding_candidate:
        reasons.append(
            "terminal zero run matches the implied grid only as an "
            "audit candidate; values are not discarded"
        )
    return {
        "two_theta_start_raw": f"{start:g}",
        "step_raw": f"{step:g}",
        "two_theta_end_raw": f"{end:g}",
        "expected_point_count": expected,
        "raw_numeric_value_count": raw_count,
        "observed_intensity_count": raw_count,
        "observed_intensity_count_excluding_trailing_zero_padding": (
            nonzero_trimmed_count
        ),
        "trailing_zero_padding_count": zero_count,
        "trailing_zero_padding_candidate": padding_candidate,
        "fixed_width_padding_candidate": fixed_width_candidate,
        "grid_alignment_exact": grid_aligned,
        "point_count_consistency": bool(exact or padding_candidate),
        "point_count_review_reasons": reasons,
        "data_line_count": block["numeric_row_count"],
        "data_column_counts": block["numeric_column_counts"],
        "dominant_data_column_count": block[
            "dominant_numeric_column_count"
        ],
        "terminal_row_values": block["rows"][-1] if block["rows"] else [],
    }


def detect_header_with_suffix(text: str) -> dict[str, Any] | None:
    lines = text.splitlines()
    for index, line in enumerate(lines[:32]):
        match = HEADER_WITH_SUFFIX_RE.fullmatch(line)
        if not match:
            continue
        start = first_number(match.group("start"))
        step = first_number(match.group("step"))
        end = first_number(match.group("end"))
        if None in (start, step, end):
            continue
        block = collect_numeric_rows(lines, index + 1)
        if not block["values"]:
            continue
        return {
            "format_family": "legacy_intensity_array_with_source_suffix",
            "header_line_number": index + 1,
            "header_raw_text": line,
            "source_suffix": match.group("suffix"),
            "format_evidence": [
                "three numeric axis fields are followed by a nonnumeric "
                "source suffix on the same header line",
                "numeric intensity rows follow the header",
            ],
            **assess_numeric_block(
                start=start,
                step=step,
                end=end,
                block=block,
            ),
        }
    return None


def detect_uxd_style(text: str) -> dict[str, Any] | None:
    lines = text.splitlines()
    fields: dict[str, str] = {}
    counts_index = None
    for index, line in enumerate(lines):
        match = re.match(r"^\s*_(?P<key>[A-Za-z0-9+]+)\s*=\s*(?P<value>.*)$", line)
        if match:
            fields[match.group("key").upper()] = match.group("value").strip()
        if line.strip().upper() == "_COUNTS":
            counts_index = index
            break
    if counts_index is None:
        return None
    start = first_number(fields.get("START", ""))
    step = first_number(fields.get("STEPSIZE", ""))
    step_count_value = first_number(fields.get("STEPCOUNT", ""))
    if None in (start, step, step_count_value):
        return None
    block = collect_numeric_rows(lines, counts_index + 1)
    expected = int(round(step_count_value))
    observed = block["numeric_value_count"]
    grid_expected = (
        round((start + step * (expected - 1) - start) / step) + 1
        if step > 0
        else None
    )
    consistent = bool(
        step > 0
        and expected > 0
        and observed == expected
        and grid_expected == expected
    )
    reasons = [
        "UXD metadata explicitly supplies _START, _STEPSIZE, and _STEPCOUNT",
        "UXD _COUNTS section supplies the intensity values",
    ]
    if not consistent:
        reasons.append(
            f"UXD step count {expected} does not match observed "
            f"intensity count {observed}"
        )
    return {
        "format_family": "uxd_style_pattern",
        "header_line_number": counts_index + 1,
        "header_raw_text": "_COUNTS",
        "source_suffix": None,
        "format_evidence": reasons,
        "two_theta_start_raw": fields["START"].strip(),
        "step_raw": fields["STEPSIZE"].strip(),
        "two_theta_end_raw": None,
        "derived_two_theta_end": start + step * (expected - 1),
        "expected_point_count": expected,
        "raw_numeric_value_count": observed,
        "observed_intensity_count": observed,
        "observed_intensity_count_excluding_trailing_zero_padding": observed,
        "trailing_zero_padding_count": 0,
        "trailing_zero_padding_candidate": False,
        "fixed_width_padding_candidate": False,
        "grid_alignment_exact": consistent,
        "point_count_consistency": consistent,
        "point_count_review_reasons": [] if consistent else reasons,
        "data_line_count": block["numeric_row_count"],
        "data_column_counts": block["numeric_column_counts"],
        "dominant_data_column_count": block[
            "dominant_numeric_column_count"
        ],
        "terminal_row_values": block["rows"][-1] if block["rows"] else [],
        "uxd_fields": {
            key: fields[key]
            for key in ("ANODE", "WL1", "WL2", "WL3", "STEPCOUNT")
            if key in fields
        },
    }


def source_records(
    archive: dict[str, Any],
) -> Iterable[tuple[str, bytes, dict[str, Any]]]:
    base_members = {
        member["member_filename"]: member
        for member in archive.get("members") or []
    }
    if archive.get("archive_container_type") == "plain_text":
        path = Path(archive["zip_path"])
        yield (
            archive.get("payload_filename") or path.name,
            path.read_bytes(),
            archive.get("payload_record") or {},
        )
        return
    path = Path(archive["zip_path"])
    with zipfile.ZipFile(path) as source:
        for info in source.infolist():
            if info.is_dir():
                continue
            yield info.filename, source.read(info), base_members.get(
                info.filename,
                {},
            )


def radiation_evidence(
    index: dict[str, Any],
) -> tuple[str, str, bool, list[str]]:
    tokens = index.get("raw_hash_delimited_tokens") or []
    marker = tokens[1].strip() if len(tokens) > 1 else ""
    if marker == "X":
        radiation_class = "x-ray"
    elif marker == "N":
        radiation_class = "neutron"
    else:
        radiation_class = "unknown"
    notes = [
        f"official raw index token {marker!r}"
        if marker
        else "no explicit X/N index token"
    ]
    conflict = False
    third_token = tokens[2].casefold() if len(tokens) > 2 else ""
    if marker == "N" and (
        "kalpha" in third_token or "x-ray" in third_token
    ):
        conflict = True
        notes.append(
            "index radiation marker N coexists with explicit Cu-Kalpha/X-ray "
            "text in later raw index tokens"
        )
    return radiation_class, "; ".join(notes), conflict, notes


def member_review(
    *,
    filename: str,
    raw: bytes,
    base: dict[str, Any],
) -> dict[str, Any]:
    text, encoding = decode_member_text(raw)
    result: dict[str, Any] = {
        "filename": filename,
        "source_extension": Path(filename).suffix,
        "base_content_family": base.get("detected_content_family"),
        "base_diffraction_array": base.get("diffraction_array"),
        "base_point_count_consistency": base.get(
            "point_count_consistency"
        ),
        "base_metadata_conflict": base.get("metadata_conflict", False),
        "format_family": base.get("detected_content_family"),
        "format_evidence": [],
        "review_status": "unresolved",
        "review_reasons": [],
        "text_decode_encoding": encoding,
        "expected_point_count": base.get("expected_point_count"),
        "raw_numeric_value_count": base.get("raw_numeric_value_count"),
        "observed_intensity_count": base.get(
            "observed_intensity_count"
        ),
        "observed_intensity_count_excluding_trailing_zero_padding": base.get(
            "observed_intensity_count_excluding_trailing_zero_padding"
        ),
        "trailing_zero_padding_count": base.get(
            "trailing_zero_padding_count",
            0,
        ),
        "trailing_zero_padding_candidate": base.get(
            "trailing_zero_padding_candidate",
            False,
        ),
        "fixed_width_padding_candidate": base.get(
            "fixed_width_padding_candidate",
            False,
        ),
        "point_count_consistency": base.get("point_count_consistency"),
        "terminal_row_values": [],
    }
    if text is None:
        result["review_reasons"] = ["source member is opaque or binary"]
        return result

    if base.get("diffraction_array") is True:
        result["format_evidence"] = [
            "base audit validated a three-number start/step/end header"
        ]
        if base.get("trailing_zero_padding_candidate"):
            result["review_status"] = "conditionally_parseable"
            result["review_reasons"] = [
                "terminal zeros are retained as a padding candidate only",
            ]
        else:
            result["review_status"] = "verified"
        result["terminal_row_values"] = (
            find_intensity_header_and_block(text).get("data_column_counts")
            or {}
        )
        return result

    suffix = detect_header_with_suffix(text)
    if suffix and suffix.get("point_count_consistency"):
        result.update(suffix)
        result["review_status"] = "conditionally_parseable"
        result["review_reasons"] = [
            "base parser did not accept the source suffix, but the "
            "three-number header and exact intensity count are explicit",
        ]
        return result

    uxd = detect_uxd_style(text)
    if uxd and uxd.get("point_count_consistency"):
        result.update(uxd)
        result["review_status"] = "conditionally_parseable"
        result["review_reasons"] = [
            "UXD axis and count metadata are explicit, but this review "
            "does not rewrite the source into a different format",
        ]
        return result

    result["review_reasons"] = (
        base.get("point_count_review_reasons")
        or ["no supported, internally consistent format evidence"]
    )
    return result


def classify_archive(
    index: dict[str, Any],
    archive: dict[str, Any],
) -> dict[str, Any]:
    radiation_class, radiation_note, radiation_conflict, radiation_notes = (
        radiation_evidence(index)
    )
    member_reviews = [
        member_review(filename=filename, raw=raw, base=base)
        for filename, raw, base in source_records(archive)
    ]
    statuses = [item["review_status"] for item in member_reviews]
    if not statuses:
        entry_status = "unresolved"
    elif all(status == "verified" for status in statuses):
        entry_status = "verified"
    elif any(status in {"verified", "conditionally_parseable"} for status in statuses):
        entry_status = "conditionally_parseable"
    else:
        entry_status = "unresolved"

    reasons: list[str] = []
    for item in member_reviews:
        reasons.extend(item.get("review_reasons") or [])
        if item.get("base_point_count_consistency") is False:
            reasons.append("base audit reported a point-count mismatch")
        if item.get("trailing_zero_padding_count", 0):
            reasons.append(
                "terminal zero run requires explicit padding review; "
                "no values were discarded"
            )
    if len(member_reviews) > 1:
        reasons.append(
            "archive contains multiple data members; member-level results "
            "must not be collapsed into one canonical profile"
        )
    if archive.get("metadata_conflict"):
        reasons.extend(archive.get("metadata_conflict_notes") or [])
    if radiation_conflict:
        reasons.extend(radiation_notes[1:])
    if archive.get("archive_open_status") not in VALID_ARCHIVE_STATUSES:
        reasons.append(
            f"archive status is {archive.get('archive_open_status')!r}"
        )
    if archive.get("detected_content_family") in {
        "mixed",
        "numeric_unknown",
        "other",
    }:
        reasons.append(
            f"base content family remains {archive.get('detected_content_family')}"
        )

    parseable_members = [
        item
        for item in member_reviews
        if item["review_status"] in {"verified", "conditionally_parseable"}
    ]
    unresolved_members = [
        item for item in member_reviews if item["review_status"] == "unresolved"
    ]
    base_unknown = archive.get("diffraction_array") is None
    point_mismatch = any(
        item.get("base_point_count_consistency") is False
        or (
            item.get("expected_point_count") is not None
            and item.get("observed_intensity_count") is not None
            and item["expected_point_count"]
            != item["observed_intensity_count"]
        )
        for item in member_reviews
    )
    possible_padding = any(
        item.get("trailing_zero_padding_count", 0) > 0
        for item in member_reviews
    )
    failed_parsing = any(
        item.get("text_decode_encoding") is None
        or item.get("review_status") == "unresolved"
        and item.get("base_content_family") in {"other"}
        for item in member_reviews
    )
    uncertain_family = archive.get("detected_content_family") in {
        "mixed",
        "numeric_unknown",
        "other",
    }
    potentially_eligible = bool(
        entry_status == "verified"
        and len(member_reviews) == 1
        and not archive.get("metadata_conflict")
        and not radiation_conflict
        and not failed_parsing
        and archive.get("archive_usable_for_audit") is True
    )
    primary_review = member_reviews[0] if len(member_reviews) == 1 else {}

    def primary_value(field: str) -> Any:
        value = archive.get(field)
        return primary_review.get(field) if value is None else value

    return {
        "entry_id": archive["entry_id"],
        "apparent_formula_name_token": index.get(
            "apparent_formula_name_token"
        ),
        "raw_index_text": index.get("raw_index_text"),
        "raw_hash_delimited_tokens": index.get(
            "raw_hash_delimited_tokens"
        )
        or [],
        "raw_bibliographic_comment_text": index.get(
            "raw_bibliographic_comment_text"
        ),
        "zip_url": archive.get("zip_url"),
        "source_filename": archive.get("source_filename"),
        "source_sha256": archive.get("source_sha256"),
        "archive_open_status": archive.get("archive_open_status"),
        "archive_container_type": archive.get("archive_container_type"),
        "archive_content_status": archive.get("archive_content_status"),
        "archive_usable_for_audit": archive.get(
            "archive_usable_for_audit"
        ),
        "source_extension": archive.get("source_extension"),
        "base_detected_content_family": archive.get(
            "detected_content_family"
        ),
        "review_detected_content_family": (
            member_reviews[0].get("format_family")
            if len(member_reviews) == 1
            else "mixed"
        ),
        "radiation_evidence_class": radiation_class,
        "radiation_evidence_note": radiation_note,
        "radiation_conflict": radiation_conflict,
        "review_status": entry_status,
        "base_diffraction_array": (
            "true"
            if archive.get("diffraction_array") is True
            else (
                "false"
                if archive.get("diffraction_array") is False
                else "unknown"
            )
        ),
        "verified_diffraction_profile": entry_status == "verified",
        "conditionally_parseable_profile": (
            entry_status == "conditionally_parseable"
        ),
        "unresolved_profile": entry_status == "unresolved",
        "potentially_eligible_for_crystaldb_v1": potentially_eligible,
        "phase_character": "unknown",
        "explicit_phase_block_count": archive.get(
            "explicit_phase_block_count",
            0,
        ),
        "source_phase_names": archive.get("source_phase_names") or [],
        "two_theta_start_raw": primary_value("two_theta_start_raw"),
        "step_raw": primary_value("step_raw"),
        "two_theta_end_raw": primary_value("two_theta_end_raw"),
        "derived_two_theta_end": primary_review.get(
            "derived_two_theta_end"
        ),
        "expected_point_count": primary_value("expected_point_count"),
        "observed_intensity_count": primary_value(
            "observed_intensity_count"
        ),
        "observed_intensity_count_excluding_trailing_zero_padding": (
            primary_value(
                "observed_intensity_count_excluding_trailing_zero_padding"
            )
        ),
        "trailing_zero_padding_count": primary_value(
            "trailing_zero_padding_count"
        )
        or 0,
        "trailing_zero_padding_candidate": primary_value(
            "trailing_zero_padding_candidate"
        )
        or False,
        "fixed_width_padding_candidate": primary_value(
            "fixed_width_padding_candidate"
        )
        or False,
        "point_count_consistency": primary_value(
            "point_count_consistency"
        ),
        "metadata_conflict": bool(archive.get("metadata_conflict")),
        "metadata_conflict_notes": archive.get(
            "metadata_conflict_notes"
        )
        or [],
        "unknown_array_semantics": base_unknown,
        "point_count_mismatch": point_mismatch,
        "possible_terminal_padding": possible_padding,
        "uncertain_content_family": uncertain_family,
        "failed_parsing": failed_parsing,
        "review_reasons": list(dict.fromkeys(reasons)),
        "member_review": member_reviews,
        "member_count": len(member_reviews),
        "unresolved_member_count": len(unresolved_members),
        "parseable_member_count": len(parseable_members),
    }


CSV_FIELDS = [
    "entry_id",
    "apparent_formula_name_token",
    "raw_index_text",
    "raw_hash_delimited_tokens",
    "raw_bibliographic_comment_text",
    "source_filename",
    "source_sha256",
    "zip_url",
    "archive_open_status",
    "archive_container_type",
    "archive_content_status",
    "archive_usable_for_audit",
    "source_extension",
    "base_detected_content_family",
    "review_detected_content_family",
    "radiation_evidence_class",
    "radiation_evidence_note",
    "radiation_conflict",
    "review_status",
    "base_diffraction_array",
    "verified_diffraction_profile",
    "conditionally_parseable_profile",
    "unresolved_profile",
    "potentially_eligible_for_crystaldb_v1",
    "phase_character",
    "explicit_phase_block_count",
    "source_phase_names",
    "two_theta_start_raw",
    "step_raw",
    "two_theta_end_raw",
    "derived_two_theta_end",
    "expected_point_count",
    "observed_intensity_count",
    "observed_intensity_count_excluding_trailing_zero_padding",
    "trailing_zero_padding_count",
    "trailing_zero_padding_candidate",
    "fixed_width_padding_candidate",
    "point_count_consistency",
    "metadata_conflict",
    "metadata_conflict_notes",
    "unknown_array_semantics",
    "point_count_mismatch",
    "possible_terminal_padding",
    "uncertain_content_family",
    "failed_parsing",
    "review_reasons",
    "member_count",
    "unresolved_member_count",
    "parseable_member_count",
    "member_review",
]


def csv_row(record: dict[str, Any]) -> dict[str, Any]:
    row = dict(record)
    for field in (
        "raw_hash_delimited_tokens",
        "source_phase_names",
        "metadata_conflict_notes",
        "review_reasons",
        "member_review",
    ):
        row[field] = json_text(record.get(field) or [])
    return {field: row.get(field) for field in CSV_FIELDS}


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    group_fields = {
        "unknown_array_semantics": "unknown_array_semantics",
        "point_count_mismatch": "point_count_mismatch",
        "possible_terminal_padding": "possible_terminal_padding",
        "metadata_conflict": "metadata_conflict",
        "uncertain_content_family": "uncertain_content_family",
        "failed_parsing": "failed_parsing",
    }
    groups = {
        name: [
            record["entry_id"]
            for record in records
            if record[field]
        ]
        for name, field in group_fields.items()
    }
    radiation_counts = Counter(
        record["radiation_evidence_class"] for record in records
    )
    status_counts = Counter(record["review_status"] for record in records)
    return {
        "record_count": len(records),
        "xray_record_count": radiation_counts["x-ray"],
        "neutron_record_count": radiation_counts["neutron"],
        "unknown_radiation_record_count": radiation_counts["unknown"],
        "verified_diffraction_profile_count": status_counts["verified"],
        "conditionally_parseable_profile_count": status_counts[
            "conditionally_parseable"
        ],
        "unresolved_profile_count": status_counts["unresolved"],
        "metadata_conflict_count": sum(
            record["metadata_conflict"] for record in records
        ),
        "radiation_conflict_count": sum(
            record["radiation_conflict"] for record in records
        ),
        "potentially_eligible_for_crystaldb_v1_count": sum(
            record["potentially_eligible_for_crystaldb_v1"]
            for record in records
        ),
        "review_group_counts": {
            name: len(entry_ids) for name, entry_ids in groups.items()
        },
        "review_group_entry_ids": groups,
        "review_status_counts": dict(status_counts),
        "radiation_counts": dict(radiation_counts),
    }


def write_summary(
    path: Path,
    *,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
    inventory_path: Path,
) -> None:
    by_id = {record["entry_id"]: record for record in records}
    lines = [
        "# PowBase Review Summary v1",
        "",
        "This is a read-only scientific review layer over the complete "
        "170-entry PowBase audit. It does not ingest MongoDB, modify "
        "production CrystalDB, rewrite PowBase sources, or approve canonical "
        "ingestion.",
        "",
        "## Inputs and Preservation",
        "",
        f"- Full archive inventory: `{inventory_path.resolve()}`",
        "- Full audit record count: `170`",
        "- Cached archive files were reused; no valid archive was re-downloaded.",
        "- The prior entry-137-only artifacts remain preserved under "
        "`inventory/powbase_137_*`; the main inventory is again the complete "
        "170-entry audit.",
        "- `phase_character` is retained as `unknown` for every review row.",
        "- `diffraction_array=true` is evidence of a validated source array, "
        "not canonical-ingestion approval.",
        "",
        "## Counts",
        "",
        "| Measure | Count |",
        "| --- | ---: |",
        f"| X-ray records, based on literal official `#X` index token | "
        f"{summary['xray_record_count']} |",
        f"| Neutron records, based on literal official `#N` index token | "
        f"{summary['neutron_record_count']} |",
        f"| Radiation class unknown | {summary['unknown_radiation_record_count']} |",
        f"| Verified diffraction profiles | "
        f"{summary['verified_diffraction_profile_count']} |",
        f"| Conditionally parseable profiles | "
        f"{summary['conditionally_parseable_profile_count']} |",
        f"| Unresolved profiles | {summary['unresolved_profile_count']} |",
        f"| Metadata conflicts | {summary['metadata_conflict_count']} |",
        f"| Radiation evidence conflicts | {summary['radiation_conflict_count']} |",
        f"| Potentially eligible for CrystalDB v1 review | "
        f"{summary['potentially_eligible_for_crystaldb_v1_count']} |",
        "",
        "Verified means one supported source member has an internally "
        "consistent point grid without a terminal-padding candidate. "
        "Conditionally parseable includes explicit fixed-width padding "
        "candidates, explicitly recognized UXD/source-suffix formats, and "
        "mixed archives with at least one parseable member. Unresolved means "
        "no supported, internally consistent profile can be established.",
        "",
        "Potential v1 eligibility is only a review queue: one verified "
        "profile member, no metadata conflict, no radiation conflict, and "
        "an audit-usable source. It is not an ingestion decision.",
        "",
        "## Potential v1 Review Queue",
        "",
        ", ".join(
            record["entry_id"]
            for record in records
            if record["potentially_eligible_for_crystaldb_v1"]
        )
        or "None",
        "",
        "The one radiation-evidence conflict is entry 102. Metadata "
        "conflicts are entries 86 and 169b; all three are excluded from "
        "the potential v1 queue.",
        "",
        "## Review Groups",
        "",
    ]
    labels = {
        "unknown_array_semantics": "Base audit unknown array semantics",
        "point_count_mismatch": "Point-count mismatch",
        "possible_terminal_padding": "Possible terminal padding",
        "metadata_conflict": "Metadata conflict",
        "uncertain_content_family": "Uncertain content family",
        "failed_parsing": "Failed or opaque parsing",
    }
    for group, label in labels.items():
        ids = summary["review_group_entry_ids"][group]
        lines.append(f"### {label} ({len(ids)})")
        lines.append("")
        lines.append(", ".join(ids) if ids else "None")
        lines.append("")

    lines.extend(
        [
            "## Entries 1 and 2",
            "",
            f"- Entry 1: expected `{by_id['1']['expected_point_count']}`, "
            f"literal observed `{by_id['1']['observed_intensity_count']}`, "
            f"terminal zeros `{by_id['1']['trailing_zero_padding_count']}`. "
            "The nonzero terminal-trim count still does not match the "
            "expected grid, so it remains unresolved; no values are trimmed.",
            f"- Entry 2: expected `{by_id['2']['expected_point_count']}`, "
            f"literal observed `{by_id['2']['observed_intensity_count']}`, "
            f"terminal zeros `{by_id['2']['trailing_zero_padding_count']}`. "
            "The source layout does not provide enough evidence to explain "
            "the mismatch, so it remains unresolved.",
            "",
            "## Recovered Conditional Formats",
            "",
            "- Entry 15: UXD-style `_START`, `_STEPSIZE`, `_STEPCOUNT`, and "
            "`_COUNTS` metadata agree on 13,003 intensity values. It remains "
            "conditional because the base inventory did not classify UXD as "
            "a supported canonical family.",
            "- Entry 36: `h2ti3o7.dat` is conditionally parseable with a "
            "fixed-width padding candidate, while `H2Ti3-N.dat` remains "
            "unresolved. The archive is therefore not a single verified "
            "profile.",
            "- Entry 74: the first line contains a valid three-number header "
            "plus the explicit `CuKalpha` source suffix, followed by exactly "
            "4,001 values. It remains conditional because the suffix-bearing "
            "variant is handled only in this review layer.",
            "- Entry 137: the updated plain-text payload is conditionally "
            "parseable; its 3,010 literal values include a nine-zero "
            "fixed-width padding candidate for a 3,001-point grid.",
            "",
            "## Metadata and Phase Handling",
            "",
            "Metadata conflicts remain source evidence and are not resolved "
            "automatically. Explicit phase blocks and source phase names are "
            "retained in the CSV member evidence, but `phase_character` "
            "remains `unknown`.",
            "",
            "No record in this review is automatically approved for canonical "
            "CrystalDB ingestion.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_review(
    *,
    inventory_path: Path = DEFAULT_INVENTORY,
    index_path: Path = DEFAULT_INDEX,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    archives = read_jsonl(inventory_path)
    indexes = {
        record["entry_id"]: record
        for record in read_jsonl(index_path)
    }
    if len(archives) != 170:
        raise ValueError(
            "review requires the complete 170-entry archive inventory; "
            f"found {len(archives)} records at {inventory_path}"
        )
    records = [
        classify_archive(indexes[archive["entry_id"]], archive)
        for archive in archives
    ]
    summary = summarize(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "powbase_review_records_v1.csv"
    summary_path = output_dir / "powbase_review_summary_v1.md"
    write_csv(
        csv_path,
        [csv_row(record) for record in records],
        CSV_FIELDS,
    )
    write_summary(
        summary_path,
        summary=summary,
        records=records,
        inventory_path=inventory_path,
    )
    manifest = {
        "review_version": "powbase-review-v1",
        "inventory_path": str(inventory_path.resolve()),
        "index_path": str(index_path.resolve()),
        "record_count": len(records),
        "summary": summary,
        "outputs": {
            "summary": str(summary_path.resolve()),
            "records": str(csv_path.resolve()),
        },
        "constraints": {
            "mongodb_writes": False,
            "canonical_ingestion": False,
            "production_modified": False,
            "source_files_modified": False,
            "phase_character_promoted": False,
            "diffraction_array_as_ingestion_approval": False,
        },
    }
    (output_dir / "powbase_review_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review the complete local PowBase audit conservatively."
    )
    parser.add_argument("--inventory-path", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = run_review(
        inventory_path=args.inventory_path,
        index_path=args.index_path,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    print(f"Summary: {manifest['outputs']['summary']}")
    print(f"Records: {manifest['outputs']['records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
