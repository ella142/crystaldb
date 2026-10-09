"""Read-only rescue audit for the 30 unresolved PowBase X-ray records.

The audit deliberately keeps source bytes and scientific values untouched.  It
uses content evidence to recover legacy text files that the base audit could
not decode, but it only calls a profile safely recoverable when the source
header and raw intensity count agree exactly.  Terminal zeros and fixed-width
row candidates are reported as evidence only; no values are trimmed or padded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_powbase import (  # noqa: E402
    collect_fullprof_metadata,
    collect_text_metadata,
    decode_member_text,
    find_intensity_header_and_block,
    inspect_numeric_array,
)


DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "mappings" / "powbase_v1_inclusion_manifest.csv"
DEFAULT_ARCHIVE_ROOT = (
    PROJECT_ROOT / "data" / "archive" / "powbase_20261006" / "archives"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "mappings"

RESCUE_ENTRY_IDS = [
    "1",
    "20",
    "22",
    "26",
    "28",
    "32",
    "33",
    "34",
    "37",
    "44",
    "54",
    "55",
    "57",
    "59",
    "62",
    "70",
    "81",
    "88",
    "90",
    "98",
    "103",
    "104",
    "112",
    "121",
    "144",
    "155",
    "156",
    "158",
    "161",
    "165",
]

CLASSIFICATIONS = (
    "A_model_and_profile_recoverable",
    "B_model_present_profile_unresolved",
    "C_profile_recoverable_without_model",
    "D_still_unresolved",
)

REFERENCE_PATTERNS = {
    "fullprof": re.compile(r"(?i)\bfullprof\b"),
    "pcr": re.compile(r"(?i)(?:^|[\s;,(])\.pcr\b|pcr[- ]?file"),
    "cif": re.compile(r"(?i)\b(?:pd)?cif\b|_pd_|_diffrn_|gsas2cif"),
    "rietveld": re.compile(r"(?i)\brietveld\b"),
    "gsas": re.compile(r"(?i)\bgsas(?:2cif)?\b"),
    "koalariet": re.compile(r"(?i)\bkoalariet\b|koalarie|riet\.hlp"),
    "rietica": re.compile(r"(?i)\brietica\b"),
    "arit": re.compile(r"(?i)\barit\d*\b|\barit\b"),
    "other_refinement_or_model": re.compile(
        r"(?i)\b(?:refin(?:e|ement|ed|ing)?|model|structure\s+factor|ab\s+initio)\b"
    ),
}

MODEL_CONTENT_PATTERNS = {
    "fullprof_phase_block": re.compile(r"(?i)\bdata\s+for\s+phase\s+number\s*:"),
    "fullprof_space_group": re.compile(r"(?i)space\s+group\s+symbol"),
    "fullprof_atom_coordinates": re.compile(
        r"(?i)\batom\s+typ\b|\b(?:atom|site)\b.*\b(?:x|xyz)\b"
    ),
    "koalariet_structure_block": re.compile(r"(?i)!\s*str\s*\("),
    "koalariet_site_coordinates": re.compile(r"(?i)!\s*site\s+\S+"),
    "legacy_arit_structure_block": re.compile(
        r"(?i)!\s*(?:.*\b(?:arit\d*|cmmm|p\s*4/n)\b)"
    ),
}

MAX_EVIDENCE_LINES = 24


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value or ""))).strip()


def _read_manifest(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = {row["entry_id"]: row for row in csv.DictReader(handle)}
    missing = [entry_id for entry_id in RESCUE_ENTRY_IDS if entry_id not in rows]
    if missing:
        raise AssertionError(f"manifest is missing rescue entries: {missing}")
    return rows


def _evidence_lines(text: str, pattern: re.Pattern[str]) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines() if pattern.search(line)]
    return list(dict.fromkeys(lines))[:MAX_EVIDENCE_LINES]


def _decode_for_rescue(raw: bytes) -> tuple[str | None, str | None, int, str | None]:
    """Decode text while recording, but not changing, embedded NUL bytes."""

    text, encoding = decode_member_text(raw)
    if text is not None:
        return text, encoding, text.count("\x00"), None

    sample = raw[: min(len(raw), 65536)]
    control_count = sum(
        1 for byte in sample if byte < 32 and byte not in (0, 9, 10, 13)
    )
    printable_count = sum(
        1
        for byte in sample
        if byte in (9, 10, 13) or 32 <= byte <= 126 or byte >= 128
    )
    if not sample or printable_count / len(sample) < 0.85:
        return None, None, 0, "member is not readable text under the rescue decoder"
    if control_count == 0 and b"\x00" not in sample:
        return None, None, 0, "member could not be decoded as supported text"

    for candidate_encoding in ("utf-8-sig", "cp1252", "iso-8859-1"):
        try:
            decoded = raw.decode(candidate_encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        decoded = raw.decode("iso-8859-1")

    nul_count = decoded.count("\x00")
    normalized = decoded.replace("\x00", " ")
    return (
        normalized,
        f"rescue-{candidate_encoding}",
        nul_count,
        "embedded NUL bytes replaced with spaces for parsing only; source bytes preserved",
    )


def _reference_flags(raw_index_text: str, text: str) -> dict[str, dict[str, Any]]:
    index_text = html.unescape(raw_index_text or "")
    combined = f"{index_text}\n{text}"
    result: dict[str, dict[str, Any]] = {}
    for name, pattern in REFERENCE_PATTERNS.items():
        index_lines = _evidence_lines(index_text, pattern)
        content_lines = _evidence_lines(text, pattern)
        result[name] = {
            "present": bool(index_lines or content_lines),
            "index_present": bool(index_lines),
            "content_present": bool(content_lines),
            "index_evidence": index_lines,
            "content_evidence": content_lines,
        }
    return result


def _model_content_evidence(text: str) -> dict[str, Any]:
    evidence: dict[str, list[str]] = {}
    for name, pattern in MODEL_CONTENT_PATTERNS.items():
        hits = _evidence_lines(text, pattern)
        if hits:
            evidence[name] = hits

    fullprof_phase_count = len(
        {
            match.group(1)
            for match in re.finditer(
                r"(?i)\bdata\s+for\s+phase\s+number\s*:\s*(\d+)", text
            )
        }
    )
    koalariet_phase_names = []
    for match in re.finditer(
        r"(?im)^\s*!\s*STR\([^)]*\)\s*'\s*(.*?)\s*$", text
    ):
        name = match.group(1).strip()
        if name:
            koalariet_phase_names.append(name)
    koalariet_structure_block_count = len(
        re.findall(r"(?im)^\s*!\s*STR\([^)]*\)", text)
    )
    legacy_arit_phase_names = []
    for line in text.splitlines()[:8]:
        candidate = line.lstrip(" !\t")
        if re.search(r"(?i)\b(?:ARIT\d*|P\s*4/N|CMMM)\b", candidate):
            name = re.split(r"(?i)\s+(?:ARIT\d*|P\s*4/N|CMMM)\b", candidate)[0]
            if name.strip():
                legacy_arit_phase_names.append(name.strip())
                break
    legacy_arit_model_block_count = int(
        bool(evidence.get("legacy_arit_structure_block"))
    )
    koalariet_site_count = len(
        re.findall(r"(?im)^\s*!\s*site\s+\S+", text)
    )
    return {
        "present": bool(evidence),
        "evidence": evidence,
        "fullprof_phase_count": fullprof_phase_count,
        "koalariet_structure_block_count": koalariet_structure_block_count,
        "koalariet_phase_names": list(dict.fromkeys(koalariet_phase_names)),
        "legacy_arit_model_block_count": legacy_arit_model_block_count,
        "legacy_arit_phase_names": list(dict.fromkeys(legacy_arit_phase_names)),
        "koalariet_site_count": koalariet_site_count,
    }


def _content_family(
    text: str,
    metadata: dict[str, Any],
    fullprof: dict[str, Any],
    pattern: dict[str, Any],
    model_content: dict[str, Any],
) -> str:
    if fullprof.get("is_fullprof_style"):
        return "fullprof_style_pattern"
    if metadata.get("cif_tag_tokens") or metadata.get("cif_data_block_names"):
        return "commented_pdcif"
    if re.search(r"(?i)!\s*(?:include|xdd|str\s*\(|site\s+)", text):
        return "koalariet_style_pattern"
    if model_content.get("evidence", {}).get("legacy_arit_structure_block"):
        return "arit_style_pattern"
    if pattern.get("header_found"):
        return "legacy_intensity_array"
    if inspect_numeric_array(text).get("numeric_array_present"):
        return "numeric_unknown"
    return "other"


def _profile_audit(text: str | None) -> dict[str, Any]:
    if text is None:
        return {
            "header_found": False,
            "expected_point_count": None,
            "observed_intensity_count": None,
            "point_count_consistency": None,
            "profile_safely_recoverable": False,
            "profile_recovery_rule": None,
            "profile_failure_reason": "no readable text profile was available",
            "padding_evidence": {},
        }

    pattern = find_intensity_header_and_block(text)
    expected = pattern.get("expected_point_count")
    observed = pattern.get("observed_intensity_count")
    raw_consistent = bool(
        pattern.get("header_found")
        and pattern.get("header_values_valid")
        and pattern.get("grid_alignment_exact")
        and expected is not None
        and observed == expected
    )
    if raw_consistent:
        recovery_rule = (
            "Use the source three-number 2theta header exactly as written and "
            "retain all raw intensity values because observed count equals "
            "round((end-start)/step)+1."
        )
        failure_reason = None
    elif not pattern.get("header_found"):
        recovery_rule = None
        failure_reason = "; ".join(
            pattern.get("point_count_review_reasons")
            or ["no three-number header followed by numeric rows was found"]
        )
    else:
        recovery_rule = None
        failure_reason = "; ".join(
            pattern.get("point_count_review_reasons")
            or [
                "source header or implied grid is not internally valid",
                "no trimming or padding rule was adopted",
            ]
        )

    return {
        "header_found": bool(pattern.get("header_found")),
        "header_line_number": pattern.get("header_line_number"),
        "header_raw_text": pattern.get("header_raw_text"),
        "two_theta_start_raw": pattern.get("two_theta_start_raw"),
        "step_raw": pattern.get("step_raw"),
        "two_theta_end_raw": pattern.get("two_theta_end_raw"),
        "header_values_valid": pattern.get("header_values_valid"),
        "grid_alignment_exact": pattern.get("grid_alignment_exact"),
        "expected_point_count": expected,
        "observed_intensity_count": observed,
        "raw_numeric_value_count": pattern.get("raw_numeric_value_count"),
        "point_count_consistency": raw_consistent,
        "profile_safely_recoverable": raw_consistent,
        "profile_recovery_rule": recovery_rule,
        "profile_failure_reason": failure_reason,
        "padding_evidence": {
            "trailing_zero_padding_count": pattern.get("trailing_zero_padding_count", 0),
            "trailing_zero_padding_candidate": bool(
                pattern.get("trailing_zero_padding_candidate")
            ),
            "fixed_width_padding_candidate": bool(
                pattern.get("fixed_width_padding_candidate")
            ),
            "observed_count_excluding_trailing_zero_padding": pattern.get(
                "observed_intensity_count_excluding_trailing_zero_padding"
            ),
            "dominant_data_column_count": pattern.get(
                "dominant_data_column_count"
            ),
            "review_reason": pattern.get("trailing_zero_padding_review_reason"),
            "policy": (
                "candidate only; values are retained and no trimming or padding "
                "is performed"
            ),
        },
        "data_column_counts": pattern.get("data_column_counts") or {},
    }


def _classify(
    *,
    model_content_present: bool,
    model_evidence_present: bool,
    profile_safely_recoverable: bool,
) -> tuple[str, str]:
    if profile_safely_recoverable and model_content_present:
        return (
            "A_model_and_profile_recoverable",
            "Embedded model evidence and an exact source-header/profile point-count match are present.",
        )
    if profile_safely_recoverable and not model_evidence_present:
        return (
            "C_profile_recoverable_without_model",
            "The source profile is exactly reconstructable from its header and raw count, but no refinement/model evidence was found.",
        )
    if model_evidence_present:
        return (
            "B_model_present_profile_unresolved",
            "Refinement/model evidence is present, but the experimental profile remains unresolved because the raw count does not match the implied grid or the source profile cannot be validated.",
        )
    return (
        "D_still_unresolved",
        "No qualifying refinement/model evidence was found and the experimental profile is not safely recoverable under the exact-count rule.",
    )


def build_audit(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
) -> dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    records: list[dict[str, Any]] = []

    for entry_id in RESCUE_ENTRY_IDS:
        source = manifest[entry_id]
        archive_path = archive_root / f"{entry_id}.zip"
        archive_bytes = archive_path.read_bytes()
        archive_sha256 = _sha256_bytes(archive_bytes)

        try:
            with zipfile.ZipFile(archive_path) as archive:
                infos = archive.infolist()
                member_names = [info.filename for info in infos]
                non_directory_infos = [info for info in infos if not info.is_dir()]
                if not non_directory_infos:
                    raise ValueError("archive contains no non-directory member")
                info = non_directory_infos[0]
                raw = archive.read(info)
        except (zipfile.BadZipFile, ValueError) as exc:
            member_names = []
            info = None
            raw = b""
            archive_error = str(exc)
        else:
            archive_error = None

        text, text_encoding, nul_count, decode_note = _decode_for_rescue(raw)
        metadata = collect_text_metadata(text) if text is not None else {}
        fullprof = collect_fullprof_metadata(text) if text is not None else {}
        pattern = (
            find_intensity_header_and_block(text) if text is not None else {}
        )
        model_content = (
            _model_content_evidence(text) if text is not None else {
                "present": False,
                "evidence": {},
                "fullprof_phase_count": 0,
                "koalariet_structure_block_count": 0,
                "koalariet_phase_names": [],
                "legacy_arit_model_block_count": 0,
                "legacy_arit_phase_names": [],
                "koalariet_site_count": 0,
            }
        )
        references = _reference_flags(source["raw_index_text"], text or "")
        model_reference_present = any(
            references[name]["present"]
            for name in (
                "fullprof",
                "pcr",
                "rietveld",
                "gsas",
                "koalariet",
                "rietica",
                "arit",
            )
        )
        model_evidence_present = bool(
            model_reference_present or model_content["present"]
        )
        profile = _profile_audit(text)
        classification, classification_reason = _classify(
            model_content_present=bool(model_content["present"]),
            model_evidence_present=model_evidence_present,
            profile_safely_recoverable=bool(
                profile["profile_safely_recoverable"]
            ),
        )

        if classification == "B_model_present_profile_unresolved":
            if model_content["present"]:
                classification_reason += (
                    " Embedded model evidence: "
                    + ", ".join(model_content["evidence"].keys())
                    + "."
                )
            if model_reference_present:
                classification_reason += (
                    " Source reference evidence: "
                    + ", ".join(
                        name
                        for name, evidence in references.items()
                        if evidence["present"]
                        and name
                        in {
                            "fullprof",
                            "pcr",
                            "rietveld",
                            "gsas",
                            "koalariet",
                            "rietica",
                            "arit",
                        }
                    )
                    + "."
                )

        member_sha256 = _sha256_bytes(raw) if info is not None else None
        source_sha256_match = bool(
            member_sha256 and source.get("source_sha256") == archive_sha256
        )
        record = {
            "entry_id": entry_id,
            "source_label_raw": source["source_label_raw"],
            "source_label_text": _clean_label(source["source_label_raw"]),
            "source_modality_raw": source["source_modality_raw"],
            "source_modality_class": source["source_modality_class"],
            "raw_index_text": source["raw_index_text"],
            "raw_hash_delimited_tokens": source["raw_hash_delimited_tokens"],
            "raw_bibliographic_comment_text": source[
                "raw_bibliographic_comment_text"
            ],
            "archive_filename": archive_path.name,
            "archive_sha256": archive_sha256,
            "archive_sha256_matches_manifest": archive_sha256
            == source.get("source_sha256"),
            "archive_error": archive_error,
            "archive_member_filenames": member_names,
            "archive_member_count": len(member_names),
            "member_filename": info.filename if info is not None else None,
            "member_source_extension": (
                Path(info.filename).suffix if info is not None else None
            ),
            "member_sha256": member_sha256,
            "member_size_bytes": len(raw) if info is not None else None,
            "text_decode_encoding": text_encoding,
            "text_nul_byte_count": nul_count,
            "text_decode_note": decode_note,
            "detected_content_family": _content_family(
                text or "", metadata, fullprof, pattern, model_content
            ),
            "numeric_array_present": (
                inspect_numeric_array(text).get("numeric_array_present")
                if text is not None
                else None
            ),
            "fullprof_content_evidence": fullprof.get(
                "fullprof_style_evidence", []
            ),
            "fullprof_phase_block_identifiers": fullprof.get(
                "fullprof_phase_block_identifiers", []
            ),
            "fullprof_phase_names": fullprof.get("fullprof_phase_names", []),
            "reference_flags": references,
            "model_reference_present": model_reference_present,
            "model_content_present": bool(model_content["present"]),
            "model_evidence_present": model_evidence_present,
            "model_content_evidence": model_content["evidence"],
            "embedded_fullprof_phase_count": model_content[
                "fullprof_phase_count"
            ],
            "embedded_koalariet_structure_block_count": model_content[
                "koalariet_structure_block_count"
            ],
            "embedded_legacy_arit_model_block_count": model_content[
                "legacy_arit_model_block_count"
            ],
            "embedded_koalariet_site_count": model_content[
                "koalariet_site_count"
            ],
            "explicit_phase_block_count": max(
                int(model_content["fullprof_phase_count"]),
                int(model_content["koalariet_structure_block_count"]),
                int(model_content["legacy_arit_model_block_count"]),
                len(fullprof.get("fullprof_phase_block_identifiers", [])),
                len(metadata.get("phase_block_identifiers", [])),
            ),
            "source_phase_names": list(
                dict.fromkeys(
                    (fullprof.get("fullprof_phase_names") or [])
                    + (metadata.get("source_phase_names") or [])
                    + (model_content.get("koalariet_phase_names") or [])
                    + (model_content.get("legacy_arit_phase_names") or [])
                )
            ),
            "profile": profile,
            "classification": classification,
            "classification_reason": classification_reason,
            "source_sha256": source.get("source_sha256"),
        }
        records.append(record)

    counts = {
        "total_records": len(records),
        "fullprof_evidence": sum(
            1 for row in records if row["reference_flags"]["fullprof"]["present"]
        ),
        "cif_evidence": sum(
            1 for row in records if row["reference_flags"]["cif"]["present"]
        ),
        "any_refinement_or_model_evidence": sum(
            1 for row in records if row["model_evidence_present"]
        ),
        "embedded_model_content": sum(
            1 for row in records if row["model_content_present"]
        ),
        "profile_safely_recoverable": sum(
            1 for row in records if row["profile"]["profile_safely_recoverable"]
        ),
        "still_unresolved": sum(
            1
            for row in records
            if row["classification"]
            in {
                "B_model_present_profile_unresolved",
                "D_still_unresolved",
            }
        ),
    }
    by_classification = {
        classification: [
            row["entry_id"]
            for row in records
            if row["classification"] == classification
        ]
        for classification in CLASSIFICATIONS
    }
    return {
        "scope": {
            "entry_ids": RESCUE_ENTRY_IDS,
            "record_count": len(records),
            "source_manifest": str(manifest_path),
            "archive_root": str(archive_root),
        },
        "method": {
            "profile_recovery_rule": (
                "Recover only when a valid source three-number start/step/end "
                "header exists, its implied grid is aligned, and the raw "
                "observed intensity count equals round((end-start)/step)+1."
            ),
            "padding_policy": (
                "Terminal zeros and fixed-width row candidates are reported "
                "only. No source value is trimmed, padded, interpolated, "
                "resampled, or normalized."
            ),
            "fallback_text_policy": (
                "If the base decoder rejects a member but the bytes are "
                "readable legacy text, decode for audit parsing and replace "
                "embedded NUL bytes with spaces in the analysis string only. "
                "The original member bytes and SHA256 are preserved."
            ),
        },
        "counts": counts,
        "by_classification": by_classification,
        "records": records,
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _json(value)
    return value


def write_outputs(
    audit: dict[str, Any],
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "powbase_unresolved_rescue_audit_v1.csv"
    json_path = output_dir / "powbase_unresolved_rescue_audit_v1.json"
    summary_path = output_dir / "powbase_unresolved_rescue_audit_v1_summary.md"

    columns = [
        "entry_id",
        "source_label_raw",
        "source_label_text",
        "source_modality_raw",
        "source_modality_class",
        "raw_index_text",
        "raw_hash_delimited_tokens",
        "raw_bibliographic_comment_text",
        "archive_filename",
        "archive_sha256",
        "archive_sha256_matches_manifest",
        "archive_error",
        "archive_member_filenames",
        "archive_member_count",
        "member_filename",
        "member_source_extension",
        "member_sha256",
        "member_size_bytes",
        "text_decode_encoding",
        "text_nul_byte_count",
        "text_decode_note",
        "detected_content_family",
        "fullprof_content_evidence",
        "fullprof_phase_block_identifiers",
        "fullprof_phase_names",
        "reference_flags",
        "model_reference_present",
        "model_content_present",
        "model_evidence_present",
        "model_content_evidence",
        "embedded_fullprof_phase_count",
        "embedded_koalariet_structure_block_count",
        "embedded_legacy_arit_model_block_count",
        "embedded_koalariet_site_count",
        "explicit_phase_block_count",
        "source_phase_names",
        "profile",
        "classification",
        "classification_reason",
        "source_sha256",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in audit["records"]:
            writer.writerow({column: _csv_value(record.get(column)) for column in columns})

    json_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    counts = audit["counts"]
    by_classification = audit["by_classification"]
    lines = [
        "# PowBase unresolved rescue audit v1",
        "",
        "Read-only audit of the 30 X-ray records currently classified as "
        "`exclude_unresolved`.",
        "",
        "## Method",
        "",
        "- A profile is safely recoverable only when the source three-number "
        "start/step/end header is valid, grid-aligned, and the raw intensity "
        "count equals `round((end-start)/step)+1`.",
        "- Terminal zero runs and fixed-width row candidates are retained as "
        "review evidence. No values were trimmed or padded.",
        "- Readable legacy text containing NUL padding was decoded for parsing "
        "only. Original archive bytes and SHA256 values were preserved.",
        "",
        "## Counts",
        "",
        f"- Records audited: {counts['total_records']}",
        f"- Records with FullProf evidence: {counts['fullprof_evidence']}",
        f"- Records with CIF evidence: {counts['cif_evidence']}",
        f"- Records with any refinement/model evidence: "
        f"{counts['any_refinement_or_model_evidence']}",
        f"- Records with embedded model content: {counts['embedded_model_content']}",
        f"- Profiles safely recoverable: {counts['profile_safely_recoverable']}",
        f"- Still unresolved: {counts['still_unresolved']}",
        "",
        "## Classification",
        "",
    ]
    for classification in CLASSIFICATIONS:
        ids = by_classification[classification]
        lines.append(f"- `{classification}` ({len(ids)}): {', '.join(ids) or 'none'}")

    lines.extend(
        [
            "",
            "## Model and format evidence",
            "",
            "- FullProf evidence includes explicit index references or embedded "
            "FullProf markers such as phase blocks and `R_Bragg`.",
            "- CIF evidence includes explicit CIF/pdCIF/GSAS2CIF markers or "
            "comment-prefixed CIF tags.",
            "- A model/reference flag does not imply that an external model file "
            "was present in the downloaded archive.",
            "",
        ]
    )
    for record in audit["records"]:
        if record["model_evidence_present"]:
            references = [
                name
                for name, evidence in record["reference_flags"].items()
                if evidence["present"]
            ]
            lines.append(
                f"- Entry {record['entry_id']}: content family "
                f"`{record['detected_content_family']}`; references "
                f"{', '.join(references) or 'none'}; embedded model content "
                f"{'yes' if record['model_content_present'] else 'no'}; "
                f"phases {record['explicit_phase_block_count']}."
            )

    lines.extend(
        [
            "",
            "## Profile review",
            "",
            "Entries 121 and 156 are safely recoverable under the exact-count "
            "rule. Their `.dat` members are Koalariet input files with embedded "
            "model text and a valid 23.000/0.020/140.000 profile header followed "
            "by exactly 5,851 raw intensity values.",
            "",
            "The remaining records retain their complete raw arrays. A mismatch "
            "is not repaired by removing terminal zeros, repeated rows, or other "
            "candidate padding.",
            "",
            "No MongoDB, source archive, canonical record, or Git state was modified.",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, json_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    audit = build_audit(
        manifest_path=args.manifest,
        archive_root=args.archive_root,
    )
    paths = write_outputs(audit, output_dir=args.output_dir)
    print(json.dumps({"counts": audit["counts"], "outputs": [str(path) for path in paths]}, indent=2))


if __name__ == "__main__":
    main()
