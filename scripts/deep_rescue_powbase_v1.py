"""Deep, read-only rescue review for the 73 conditional PowBase X-ray records.

This pass consumes the existing fast-review and inclusion manifests.  It does
not rebuild the 170-record audit and never writes MongoDB or source archives.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.audit_powbase import (
    collect_numeric_rows,
    decode_member_text,
    find_intensity_header_and_block,
    numeric_token_value,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"
ARCHIVES_DIR = ARCHIVE_ROOT / "archives"
FAST_REVIEW_PATH = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_fast_conditional_review_v1.csv"
)
INCLUSION_PATH = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_v1_inclusion_manifest.json"
)
ARCHIVE_INVENTORY_PATH = (
    ARCHIVE_ROOT / "inventory" / "powbase_archive_inventory.jsonl"
)
CSV_OUTPUT = PROJECT_ROOT / "powbase_deep_rescue_v1.csv"
SUMMARY_OUTPUT = PROJECT_ROOT / "powbase_deep_rescue_v1_summary.md"

EXCLUDED_FINALIZED_ENTRIES = {"15", "74", "121", "156"}

FIXED_WIDTH_RECOVERY_RULE = (
    "Use the explicit three-number start/step/end header to define the "
    "2theta grid. Set expected_count = round((end - start) / step) + 1; "
    "the generated endpoint must be compatible with the header endpoint "
    "under that rounding convention. The intensity block must have one "
    "uniform numeric row width, the observed count must be an exact "
    "multiple of that width, the last row must be complete, and the "
    "terminal zero run must be no longer than one row and must make "
    "observed_count - terminal_zero_count equal expected_count. Under "
    "this source-format rule only that terminal suffix is excluded from "
    "the canonical profile; no interpolation, resampling, normalization, "
    "or other intensity edits are performed."
)


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[str(record["entry_id"])] = record
    return records


def _load_inclusion_records() -> dict[str, dict[str, Any]]:
    payload = json.loads(INCLUSION_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    else:
        rows = payload.get("records", payload.get("entries", []))
    return {
        str(row.get("entry_id", row.get("powbase_entry"))): row
        for row in rows
    }


def _load_scope() -> list[dict[str, Any]]:
    with FAST_REVIEW_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    target = [
        row
        for row in rows
        if row.get("fast_decision") == "retain_conditional"
    ]
    target_ids = {row["entry_id"] for row in target}
    if target_ids & EXCLUDED_FINALIZED_ENTRIES:
        raise AssertionError(
            "finalized canonical records leaked into the deep-rescue scope"
        )
    if len(target) != 73:
        raise AssertionError(f"expected 73 conditional records, found {len(target)}")
    return sorted(target, key=lambda row: int(row["entry_id"]))


def _numeric(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_archive(entry_id: str) -> dict[str, Any]:
    path = ARCHIVES_DIR / f"{entry_id}.zip"
    raw = path.read_bytes()
    outer_sha256 = _sha256(raw)
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        text, encoding = decode_member_text(raw)
        if text is None:
            return {
                "path": path,
                "outer_sha256": outer_sha256,
                "container_type": "unreadable_nonzip",
                "open_status": "not_zip_unreadable",
                "members": [],
            }
        return {
            "path": path,
            "outer_sha256": outer_sha256,
            "container_type": "plain_text",
            "open_status": "not_zip_readable_text",
            "members": [
                {
                    "filename": path.name,
                    "raw": raw,
                    "member_sha256": outer_sha256,
                    "encoding": encoding,
                }
            ],
        }

    with archive:
        members = [
            {
                "filename": info.filename,
                "raw": archive.read(info),
                "member_sha256": _sha256(archive.read(info)),
                "encoding": None,
            }
            for info in archive.infolist()
            if not info.is_dir()
        ]
    return {
        "path": path,
        "outer_sha256": outer_sha256,
        "container_type": "zip",
        "open_status": "ok",
        "members": members,
    }


def _inspect_member(member: dict[str, Any]) -> dict[str, Any]:
    text, encoding = decode_member_text(member["raw"])
    result: dict[str, Any] = {
        "filename": member["filename"],
        "source_extension": Path(member["filename"]).suffix,
        "member_sha256": member["member_sha256"],
        "text_decode_encoding": encoding,
        "readable_text": text is not None,
        "header_found": False,
        "header_raw_text": None,
        "start_raw": None,
        "step_raw": None,
        "end_raw": None,
        "start": None,
        "step": None,
        "end": None,
        "expected_point_count": None,
        "observed_point_count": None,
        "trailing_zero_count": 0,
        "row_width": None,
        "row_widths": {},
        "uniform_row_width": False,
        "last_row_complete": False,
        "finite_intensities": False,
        "strict_axis": False,
        "grid_alignment_exact": False,
        "rounded_grid_endpoint_compatible": False,
        "fixed_width_recovery_supported": False,
        "format_evidence": [],
        "first_lines": [],
        "fullprof_evidence": [],
        "neutron_evidence": False,
    }
    if text is None:
        return result

    lines = text.splitlines()
    result["first_lines"] = lines[:8]
    result["neutron_evidence"] = bool(
        re.search(r"(?i)\bneutron(?:s)?\b", text[:4000])
    )
    pattern = find_intensity_header_and_block(text)
    if not pattern.get("header_found"):
        return result

    result.update(
        {
            "header_found": True,
            "header_raw_text": pattern.get("header_raw_text"),
            "start_raw": pattern.get("two_theta_start_raw"),
            "step_raw": pattern.get("step_raw"),
            "end_raw": pattern.get("two_theta_end_raw"),
            "start": pattern.get("two_theta_start"),
            "step": pattern.get("step"),
            "end": pattern.get("two_theta_end"),
            "expected_point_count": pattern.get("expected_point_count"),
            "grid_alignment_exact": bool(pattern.get("grid_alignment_exact")),
            "format_evidence": [
                "explicit three-number start/step/end header",
                "numeric intensity rows follow the header",
            ],
        }
    )

    block = collect_numeric_rows(lines, int(pattern["header_line_number"]))
    values = [numeric_token_value(token) for token in block["values"]]
    result["observed_point_count"] = len(values)
    result["trailing_zero_count"] = 0
    for value in reversed(values):
        if value == 0:
            result["trailing_zero_count"] += 1
        else:
            break
    result["row_widths"] = dict(sorted(block["numeric_column_counts"].items()))
    result["uniform_row_width"] = len(block["numeric_column_counts"]) == 1
    if result["uniform_row_width"]:
        result["row_width"] = next(iter(block["numeric_column_counts"]))
        result["last_row_complete"] = bool(
            block["rows"]
            and len(block["rows"][-1]) == result["row_width"]
        )

    result["finite_intensities"] = bool(values) and all(
        value is not None and math.isfinite(value) for value in values
    )
    start = result["start"]
    step = result["step"]
    end = result["end"]
    expected = result["expected_point_count"]
    result["strict_axis"] = bool(
        start is not None
        and step is not None
        and end is not None
        and expected
        and step > 0
        and end > start
        and math.isfinite(start)
        and math.isfinite(step)
        and math.isfinite(end)
        and all(
            math.isfinite(start + index * step)
            and (
                index == 0
                or start + index * step
                > start + (index - 1) * step
            )
            for index in range(expected)
        )
    )
    if (
        start is not None
        and step is not None
        and end is not None
        and expected is not None
        and step > 0
        and math.isfinite(start)
        and math.isfinite(step)
        and math.isfinite(end)
    ):
        generated_end = start + (expected - 1) * step
        result["rounded_grid_endpoint_compatible"] = bool(
            abs(generated_end - end) <= max(abs(step) / 2, 1e-9)
        )

    row_width = result["row_width"]
    result["fixed_width_recovery_supported"] = bool(
        pattern.get("header_found")
        and pattern.get("header_values_valid")
        and result["rounded_grid_endpoint_compatible"]
        and result["finite_intensities"]
        and result["strict_axis"]
        and expected is not None
        and result["observed_point_count"] is not None
        and result["trailing_zero_count"] > 0
        and result["observed_point_count"] - result["trailing_zero_count"]
        == expected
        and result["uniform_row_width"]
        and row_width
        and result["last_row_complete"]
        and result["observed_point_count"] % row_width == 0
        and result["trailing_zero_count"] <= row_width
    )
    if result["fixed_width_recovery_supported"]:
        result["format_evidence"].append(
            f"uniform {row_width}-value rows; terminal zero suffix is "
            "confined to one complete final row"
        )
    result["fullprof_evidence"] = [
        line
        for line in lines
        if re.search(
            r"(?i)\b(?:fullprof|pcr-file|lambda1|lambda2|"
            r"thmin\s+step\s+thmax|data\s+for\s+phase\s+number)\b",
            line,
        )
    ][:12]
    return result


def _member_inventory(
    archive_record: dict[str, Any], filename: str
) -> dict[str, Any]:
    for member in archive_record.get("members", []):
        if member.get("member_filename") == filename:
            return member
    return {}


def _mechanism(
    *,
    decision: str,
    content_family: str,
    entry_id: str,
) -> str:
    if entry_id == "36":
        return "mixed_legacy_member_archive"
    if decision == "retain_conditional" and entry_id == "114":
        return "terminal_padding_without_uniform_row_evidence"
    if content_family == "fullprof_style_pattern":
        return "fullprof_fixed_width_terminal_padding"
    if content_family == "commented_pdcif":
        return "commented_pdcif_fixed_width_terminal_padding"
    return "legacy_fixed_width_terminal_padding"


def _profile_summary(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "filename": member.get("filename"),
        "source_extension": member.get("source_extension"),
        "member_sha256": member.get("member_sha256"),
        "header_raw_text": member.get("header_raw_text"),
        "start": member.get("start_raw"),
        "step": member.get("step_raw"),
        "end": member.get("end_raw"),
        "expected_point_count": member.get("expected_point_count"),
        "observed_point_count": member.get("observed_point_count"),
        "trailing_zero_count": member.get("trailing_zero_count"),
        "row_width": member.get("row_width"),
        "row_widths": member.get("row_widths"),
        "fixed_width_recovery_supported": member.get(
            "fixed_width_recovery_supported"
        ),
        "neutron_evidence": member.get("neutron_evidence"),
        "first_lines": member.get("first_lines", [])[:4],
    }


def _software_evidence(
    source: dict[str, Any],
    inspected_members: list[dict[str, Any]],
    source_members: list[dict[str, Any]],
) -> list[str]:
    text_parts = [source.get("raw_index_text") or ""]
    text_parts.extend(
        line
        for member in inspected_members
        for line in member.get("first_lines", [])
    )
    text_parts.extend(
        line
        for member in source_members
        for line in (member.get("fullprof_style_evidence") or [])
    )
    text = "\n".join(text_parts)
    markers = [
        ("FullProf", r"(?i)\bfullprof\b"),
        (".pcr", r"(?i)\.pcr\b|pcr-file"),
        ("GSAS", r"(?i)\bgsas\b"),
        ("Koalariet", r"(?i)\bkoalariet\b"),
        ("Rietica", r"(?i)\brietica\b"),
        ("Arit", r"(?i)\barit\b"),
        ("Rietveld", r"(?i)\brietveld\b"),
    ]
    return [
        label for label, pattern in markers if re.search(pattern, text)
    ]


def build_review() -> dict[str, Any]:
    fast_rows = _load_scope()
    inclusion = _load_inclusion_records()
    archive_inventory = _load_jsonl(ARCHIVE_INVENTORY_PATH)
    records: list[dict[str, Any]] = []

    for fast in fast_rows:
        entry_id = fast["entry_id"]
        source = inclusion[entry_id]
        inventory = archive_inventory[entry_id]
        archive = _read_archive(entry_id)
        inspected_members = [
            _inspect_member(member) for member in archive["members"]
        ]
        source_members = [
            _member_inventory(inventory, member["filename"])
            for member in archive["members"]
        ]
        member_summaries = [
            _profile_summary(member) for member in inspected_members
        ]
        content_family = (
            source.get("review_detected_content_family")
            or source.get("base_detected_content_family")
            or fast.get("content_family")
        )
        if len(inspected_members) != 1:
            content_family = "mixed"
        software_evidence = _software_evidence(
            source, inspected_members, source_members
        )

        fixed_members = [
            member
            for member in inspected_members
            if member["fixed_width_recovery_supported"]
        ]
        source_conflict = bool(source.get("metadata_conflict"))
        if (
            len(inspected_members) == 1
            and len(fixed_members) == 1
            and not source_conflict
        ):
            decision = "promote_verified"
            selected = fixed_members[0]
            expected = selected["expected_point_count"]
            observed = selected["observed_point_count"]
            unresolved_condition = ""
            recovery_rule = FIXED_WIDTH_RECOVERY_RULE
            final_count = expected
            consistency = "verified_after_fixed_width_terminal_padding_rule"
            issue = ""
        elif entry_id == "36":
            decision = "retain_conditional"
            selected = {}
            expected = None
            observed = None
            unresolved_condition = fast["decision_reason"]
            recovery_rule = ""
            final_count = None
            consistency = "unknown"
            issue = (
                "The archive contains a conditionally parseable X-ray member "
                "and a separate neutron member without a validated common "
                "archive-wide selection rule."
            )
        elif entry_id == "114":
            decision = "retain_conditional"
            selected = inspected_members[0] if inspected_members else {}
            expected = selected.get("expected_point_count")
            observed = selected.get("observed_point_count")
            unresolved_condition = fast["decision_reason"]
            recovery_rule = ""
            final_count = None
            consistency = "candidate_only"
            issue = (
                "The terminal zero run spans more than one complete 8-value "
                "row (11 zeros); the source does not prove which zeros are "
                "experimental and which, if any, are padding."
            )
        else:
            decision = "exclude_unresolved"
            selected = inspected_members[0] if len(inspected_members) == 1 else {}
            expected = selected.get("expected_point_count")
            observed = selected.get("observed_point_count")
            unresolved_condition = (
                fast["decision_reason"]
                or "No reproducible source-format recovery rule was established."
            )
            recovery_rule = ""
            final_count = None
            consistency = "unresolved"
            issue = "No reproducible recovery rule."

        tokens = source.get("raw_hash_delimited_tokens") or []
        record = {
            "entry_id": entry_id,
            "source_label_raw": source.get("apparent_formula_name_token"),
            "source_modality_raw": tokens[1] if len(tokens) > 1 else None,
            "source_radiation_raw": tokens[2] if len(tokens) > 2 else None,
            "raw_index_text": source.get("raw_index_text"),
            "raw_hash_delimited_tokens": tokens,
            "raw_bibliographic_comment_text": source.get(
                "raw_bibliographic_comment_text"
            ),
            "source_filename": inventory.get("original_filename")
            or inventory.get("source_filename"),
            "source_sha256": inventory.get("original_sha256")
            or inventory.get("source_sha256"),
            "source_container_type": archive["container_type"],
            "source_open_status": archive["open_status"],
            "source_member_filenames": [
                member["filename"] for member in archive["members"]
            ],
            "source_member_sha256": [
                member["member_sha256"] for member in archive["members"]
            ],
            "source_extension": selected.get("source_extension"),
            "content_family": content_family,
            "recovery_mechanism": _mechanism(
                decision=decision,
                content_family=content_family,
                entry_id=entry_id,
            ),
            "original_review_status": fast.get("original_decision"),
            "original_unresolved_condition": fast.get("decision_reason"),
            "deeper_decision": decision,
            "exact_unresolved_condition": unresolved_condition,
            "source_inspected": True,
            "source_inspection_note": (
                "Cached source member inspected for explicit header, numeric "
                "layout, terminal-zero placement, and finite profile values."
            ),
            "start": selected.get("start_raw"),
            "step": selected.get("step_raw"),
            "end": selected.get("end_raw"),
            "expected_point_count": expected,
            "observed_point_count": observed,
            "trailing_zero_count": selected.get("trailing_zero_count", 0),
            "row_width": selected.get("row_width"),
            "row_widths": selected.get("row_widths"),
            "point_count_consistency": consistency,
            "padding_evidence": {
                "candidate_from_existing_review": bool(
                    fast.get("padding_candidate") == "True"
                ),
                "fixed_width_rule_supported": bool(
                    selected.get("fixed_width_recovery_supported")
                ),
                "terminal_zero_count": selected.get(
                    "trailing_zero_count", 0
                ),
                "uniform_row_width": selected.get("uniform_row_width"),
                "last_row_complete": selected.get("last_row_complete"),
            },
            "recovery_rule": recovery_rule,
            "final_canonical_point_count": final_count,
            "validation_issue": issue,
            "metadata_conflict": source_conflict,
            "metadata_conflict_notes": source.get("metadata_conflict_notes")
            or [],
            "source_model_evidence": [
                line
                for member in source_members
                for line in (member.get("fullprof_style_evidence") or [])
            ],
            "source_software_evidence": software_evidence,
            "member_profile_evidence": member_summaries,
        }
        records.append(record)

    if len(records) != 73:
        raise AssertionError(f"expected 73 review records, found {len(records)}")
    if {row["entry_id"] for row in records} & EXCLUDED_FINALIZED_ENTRIES:
        raise AssertionError("finalized records are present in output scope")
    promoted_count = Counter(row["deeper_decision"] for row in records)[
        "promote_verified"
    ]
    if promoted_count != 71:
        raise AssertionError(
            "the established fixed-width rule did not resolve 71 records: "
            + json.dumps(
                [
                    {
                        "entry_id": row["entry_id"],
                        "decision": row["deeper_decision"],
                        "family": row["content_family"],
                        "members": row["source_member_filenames"],
                        "member_evidence": row["member_profile_evidence"],
                    }
                    for row in records
                    if row["deeper_decision"] != "promote_verified"
                ],
                ensure_ascii=False,
            )
        )
    return {
        "records": records,
        "scope_ids": [row["entry_id"] for row in records],
        "excluded_finalized_entries": sorted(EXCLUDED_FINALIZED_ENTRIES),
    }


CSV_FIELDS = [
    "entry_id",
    "source_label_raw",
    "source_modality_raw",
    "source_radiation_raw",
    "raw_index_text",
    "raw_hash_delimited_tokens",
    "raw_bibliographic_comment_text",
    "source_filename",
    "source_sha256",
    "source_container_type",
    "source_open_status",
    "source_member_filenames",
    "source_member_sha256",
    "source_extension",
    "content_family",
    "recovery_mechanism",
    "original_review_status",
    "original_unresolved_condition",
    "deeper_decision",
    "exact_unresolved_condition",
    "source_inspected",
    "source_inspection_note",
    "start",
    "step",
    "end",
    "expected_point_count",
    "observed_point_count",
    "trailing_zero_count",
    "row_width",
    "row_widths",
    "point_count_consistency",
    "padding_evidence",
    "recovery_rule",
    "final_canonical_point_count",
    "validation_issue",
    "metadata_conflict",
    "metadata_conflict_notes",
    "source_model_evidence",
    "source_software_evidence",
    "member_profile_evidence",
]


def _csv_row(record: dict[str, Any]) -> dict[str, Any]:
    row = dict(record)
    for field in (
        "raw_hash_delimited_tokens",
        "source_member_filenames",
        "source_member_sha256",
        "row_widths",
        "padding_evidence",
        "metadata_conflict_notes",
        "source_model_evidence",
        "source_software_evidence",
        "member_profile_evidence",
    ):
        row[field] = _json_text(record.get(field) or [])
    return {field: row.get(field) for field in CSV_FIELDS}


def _ids(records: list[dict[str, Any]], decision: str) -> list[str]:
    return [
        row["entry_id"]
        for row in records
        if row["deeper_decision"] == decision
    ]


def _summary_markdown(payload: dict[str, Any]) -> str:
    records = payload["records"]
    promoted = [row for row in records if row["deeper_decision"] == "promote_verified"]
    retained = [row for row in records if row["deeper_decision"] == "retain_conditional"]
    excluded = [row for row in records if row["deeper_decision"] == "exclude_unresolved"]
    mechanisms = Counter(row["recovery_mechanism"] for row in records)
    families = Counter(row["content_family"] for row in records)
    software_ids: dict[str, list[str]] = {}
    for row in records:
        for marker in row["source_software_evidence"]:
            software_ids.setdefault(marker, []).append(row["entry_id"])

    lines = [
        "# PowBase Deep Rescue Review v1",
        "",
        "This is a read-only review of the 73 records that were "
        "`retain_conditional` in `powbase_fast_conditional_review_v1.csv`. "
        "Entries 15, 74, 121, and 156 were finalized separately and are "
        "intentionally outside this output.",
        "",
        "No MongoDB writes, source archive edits, canonical ingestion, COD "
        "matching, or Git operations were performed.",
        "",
        "## Decision totals",
        "",
        f"- Scope: **{len(records)}** records",
        f"- `promote_verified`: **{len(promoted)}** "
        f"({', '.join(row['entry_id'] for row in promoted)})",
        f"- `retain_conditional`: **{len(retained)}** "
        f"({', '.join(row['entry_id'] for row in retained)})",
        f"- `exclude_unresolved`: **{len(excluded)}** "
        f"({', '.join(row['entry_id'] for row in excluded) or 'none'})",
        "",
        "The 71 promotions use one source-format rule. The 2 retained "
        "records are not trimmed or otherwise converted.",
        "",
        "## Recovery mechanisms",
        "",
        "| Mechanism | Records | Entry IDs |",
        "|---|---:|---|",
    ]
    for mechanism, count in sorted(mechanisms.items()):
        ids = [
            row["entry_id"]
            for row in records
            if row["recovery_mechanism"] == mechanism
        ]
        lines.append(f"| `{mechanism}` | {count} | {', '.join(ids)} |")
    lines.extend(
        [
            "",
            "Content-family counts:",
            "",
            *[
                f"- `{family}`: {count}"
                for family, count in sorted(families.items())
            ],
            "",
            "Explicit source/index software or refinement markers:",
            "",
            "| Marker | Records | Entry IDs |",
            "|---|---:|---|",
            *[
                f"| `{marker}` | {len(ids)} | {', '.join(ids)} |"
                for marker, ids in sorted(software_ids.items())
            ],
            "",
            "## Adopted recovery rule",
            "",
            FIXED_WIDTH_RECOVERY_RULE,
            "",
            "This rule is source-format based. It is not an arbitrary "
            "record-specific trim. A record is promoted only when the "
            "explicit grid is valid, all observed intensities are finite, "
            "the implied axis is strictly increasing, the numeric rows are "
            "uniform and complete, and the terminal zero suffix is confined "
            "to the one final fixed-width row.",
            "",
            "Entry 137 is included under this general rule. Its original "
            "`137.zip` bytes were readable text rather than a ZIP archive; "
            "the original filename and SHA256 are preserved in the CSV. "
            "Its explicit header is 15.00 / 0.04 / 135.00, with 3001 "
            "expected points and 3010 observed values, of which the final "
            "9 are the proven fixed-width suffix.",
            "",
            "## Retained records",
            "",
            "### Entry 36",
            "",
            "The ZIP contains `h2ti3o7.dat`, an X-ray legacy profile with a "
            "fixed-width padding candidate, and `H2Ti3-N.dat`, a separate "
            "neutron source member without a validated intensity header. "
            "The audit does not select one member as the archive-wide "
            "canonical profile, so entry 36 remains conditional.",
            "",
            "### Entry 114",
            "",
            "The explicit grid is 5.000 / 0.010 / 120.000, implying 11501 "
            "points, while 11512 values are present. The terminal zero run "
            "contains 11 values across more than one 8-value row. That "
            "exceeds the one-final-row rule, so the source does not prove "
            "which zeros are padding. No values are discarded.",
            "",
            "## Promoted records",
            "",
            "| Entry | Member | Content family | Start | Step | End | Expected | Observed | Terminal zeros | Final points |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in promoted:
        member = row["source_member_filenames"][0]
        lines.append(
            f"| {row['entry_id']} | `{member}` | `{row['content_family']}` | "
            f"{row['start']} | {row['step']} | {row['end']} | "
            f"{row['expected_point_count']} | {row['observed_point_count']} | "
            f"{row['trailing_zero_count']} | "
            f"{row['final_canonical_point_count']} |"
        )
    lines.extend(
        [
            "",
            "The promoted `final_canonical_point_count` is the explicit "
            "header-grid count. Source values are not normalized, "
            "interpolated, resampled, smoothed, or rewritten by this audit.",
            "",
            "## Provenance",
            "",
            "Each CSV row preserves the literal index line, raw hash-delimited "
            "tokens, bibliographic/comment text, original archive filename, "
            "outer SHA256, member filenames and member SHA256 values. "
            "The source archives were reused from the local cache.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    payload: dict[str, Any],
    *,
    csv_output: Path = CSV_OUTPUT,
    summary_output: Path = SUMMARY_OUTPUT,
) -> None:
    with csv_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(_csv_row(record) for record in payload["records"])
    summary_output.write_text(
        _summary_markdown(payload), encoding="utf-8", newline="\n"
    )


def main() -> None:
    payload = build_review()
    write_outputs(payload)
    counts = Counter(row["deeper_decision"] for row in payload["records"])
    print(
        json.dumps(
            {
                "records": len(payload["records"]),
                "promote_verified": counts["promote_verified"],
                "retain_conditional": counts["retain_conditional"],
                "exclude_unresolved": counts["exclude_unresolved"],
                "csv": str(CSV_OUTPUT),
                "summary": str(SUMMARY_OUTPUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
