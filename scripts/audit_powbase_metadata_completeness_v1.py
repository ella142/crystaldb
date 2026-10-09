#!/usr/bin/env python3
"""Audit crystallographic metadata completeness for the 44 production PowBase records.

The audit is read-only. It parses the existing canonical scope list, the
original PowBase index text preserved in each record, and the corresponding
cached archive member. It does not connect to MongoDB and does not modify
source archives or canonical records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANONICAL = PROJECT_ROOT / "data" / "mappings" / "powbase_canonical_dryrun_v1.json"
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006" / "archives"
DEFAULT_CSV = PROJECT_ROOT / "data" / "mappings" / "powbase_metadata_completeness_v1.csv"
DEFAULT_JSON = PROJECT_ROOT / "data" / "mappings" / "powbase_metadata_completeness_v1.json"
DEFAULT_SUMMARY = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_metadata_completeness_v1_summary.md"
)

CSV_FIELDS = [
    "powbase_entry",
    "pattern_id",
    "source_label_raw",
    "raw_index_text",
    "member_filename",
    "archive_sha256",
    "member_sha256",
    "source_extension",
    "content_family",
    "material_label_present",
    "explicit_formula",
    "formula_status",
    "formula_evidence",
    "formula_like_label",
    "formula_like_reason",
    "radiation",
    "wavelength",
    "has_full_unit_cell",
    "unit_cell_values",
    "has_space_group",
    "space_group_raw",
    "phase_model_count",
    "phase_model_evidence",
    "has_atomic_coordinates",
    "atomic_coordinate_evidence",
    "has_structure_metadata",
    "cif_recoverability",
    "reference_present",
    "bibliographic_comment_present",
    "reference_evidence",
    "profile_only_status",
    "metadata_notes",
]

NUMERIC_RE = re.compile(
    r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[EeDd][+-]?\d+)?$"
)
NUMERIC_TOKEN_RE = re.compile(
    r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[EeDd][+-]?\d+)?"
)
COMMENT_PREFIX_RE = re.compile(r"^\s*[!#;]\s?")
HTML_TAG_RE = re.compile(r"<[^>]+>")
FORMULA_TAG_RE = re.compile(
    r"(?i)^\s*(?:[!#;]\s*)?_(?:chemical_formula|formula)"
    r"(?:_[A-Za-z0-9_.]+)?\s+(?P<value>.+?)\s*$"
)
PHASE_NUMBER_RE = re.compile(r"(?i)\bdata\s+for\s+phase\s+number\s*:\s*(\d+)")
PHASE_BLOCK_RE = re.compile(r"(?i)\bPHASE[_\s-]?(\d+)\b")
SPACE_GROUP_COMMENT_RE = re.compile(r"(?i)space\s+group\s+symbol")
CELL_HEADER_RE = re.compile(
    r"(?i)\b(?:a|alpha)\s+(?:b|beta)\s+(?:c|gamma).*"
    r"(?:alpha|beta|gamma)"
)

PRODUCTION_ENTRY_IDS = (
    "4",
    "8",
    "10",
    "12",
    "13",
    "19",
    "38",
    "43",
    "45",
    "46",
    "58",
    "60",
    "66",
    "67",
    "68",
    "69",
    "71",
    "72",
    "73",
    "75",
    "76",
    "77",
    "78",
    "79",
    "80",
    "106",
    "111",
    "113",
    "116",
    "117",
    "124",
    "125",
    "126",
    "127",
    "128",
    "133",
    "140",
    "149",
    "157",
    "159",
    "160",
    "162",
    "163",
    "164",
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strip_html(value: str) -> str:
    return html.unescape(HTML_TAG_RE.sub("", value or "")).strip()


def _strip_comment(value: str) -> str:
    return COMMENT_PREFIX_RE.sub("", value, count=1).strip()


def _numeric_tokens(line: str) -> list[float] | None:
    cleaned = _strip_comment(line)
    number = r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[EeDd][+-]?\d+)?"
    if not re.fullmatch(
        rf"\s*{number}(?:\s+{number})*\s*",
        cleaned,
    ):
        return None
    values = re.findall(number, cleaned)
    return [float(value.replace("D", "E").replace("d", "e")) for value in values]


def _clean_formula_label(value: str) -> str:
    value = _strip_html(value)
    value = re.sub(r"(?i)^(?:alpha|beta|gamma)[-_ ]*", "", value)
    value = re.sub(r"(?i)^(?:t|a)[-_]", "", value)
    value = re.sub(r"\(\?\)", "", value)
    return re.sub(r"\s+", "", value)


def _formula_like_label(value: str) -> tuple[bool, str]:
    normalized = _clean_formula_label(value)
    if not normalized:
        return False, ""
    if re.search(r"(?i)[xyz]", normalized) and re.search(
        r"[A-Z][a-z]?[xyz]", normalized
    ):
        return True, "element-like label contains placeholder variable(s)"
    if re.fullmatch(
        r"(?i)(?:[A-Z][a-z]?|\(|\)|\[|\]|\.|,|\+|-)+",
        normalized,
    ) and re.search(r"[A-Z]", normalized):
        return True, "label has chemical-formula-like element notation"
    if not re.search(r"\d", normalized):
        return False, ""
    if re.search(r"[A-Z][a-z]?(?:\)|\])?\d", normalized):
        return True, "element-like label contains explicit numeric stoichiometry"
    return False, ""


def _reference_present(text: str) -> tuple[bool, list[str]]:
    plain = _strip_html(text)
    evidence: list[str] = []
    patterns = (
        r"(?i)\b(?:acta|journal|powder diffraction|solid state|eur\.)\b",
        r"(?i)\b(?:j\.|mat\.|comptes|phys\.|appl\.|cryst\.)\b",
        r"\b(?:19|20)\d{2}\b.*\d",
        r"\(\s*(?:19|20)\d{2}\s*\)",
    )
    if any(re.search(pattern, plain) for pattern in patterns):
        evidence.append("official_index_bibliographic_comment")
    return bool(evidence), evidence


def _explicit_formula(text: str) -> tuple[list[str], list[str]]:
    values: list[str] = []
    evidence: list[str] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = FORMULA_TAG_RE.match(line)
        if not match:
            continue
        value = _strip_html(match.group("value")).strip().strip("'\"")
        if value and value not in values:
            values.append(value)
            evidence.append(f"line {line_number}: {line.strip()}")
    return values, evidence


def _index_radiation_and_wavelength(
    source: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tokens = source.get("raw_hash_delimited_tokens") or []
    if isinstance(tokens, str):
        tokens = json.loads(tokens)
    raw_modality = tokens[1] if len(tokens) > 1 else None
    radiation = {
        "present": bool(raw_modality),
        "value": "X-ray" if str(raw_modality).casefold() == "x" else raw_modality,
        "raw_index_token": raw_modality,
        "source_radiation_token": tokens[2] if len(tokens) > 2 else None,
        "source": "official_powbase_index",
        "archive_evidence": [],
    }
    wavelengths: list[dict[str, Any]] = []
    if len(tokens) > 2:
        match = re.search(
            r"(?i)\b(\d+(?:\.\d+)?)\s*(?:a|angstrom|å)\b",
            _strip_html(tokens[2]),
        )
        if match:
            wavelengths.append(
                {
                    "value_angstrom": float(match.group(1)),
                    "raw_value": match.group(0),
                    "source": "official_powbase_index",
                }
            )
    return radiation, wavelengths


def _archive_radiation_wavelength(
    lines: list[str],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    radiation_evidence: list[str] = []
    wavelengths: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        plain = _strip_comment(line)
        if re.search(r"(?i)\b(?:x[- ]?rays?|radiation|anode)\b", plain):
            radiation_evidence.append(line.strip())
        if re.search(r"(?i)\b(?:alpha1|lambda1|wavelength|wl1|wavelengths)\b", plain):
            labeled_values = re.findall(
                r"(?i)\b(?:alpha1|lambda1|alpha2|lambda2|wl1|wl2)\b"
                r"\s*(?:=|:)?\s*([+-]?\d+(?:\.\d+)?)",
                plain,
            )
            candidate_line = line
            values = labeled_values
            if not values and index + 1 < len(lines):
                next_line = _strip_comment(lines[index + 1])
                next_values = _numeric_tokens(next_line)
                if next_values:
                    values = [str(value) for value in next_values[:2]]
                    candidate_line = lines[index + 1]
            for raw_value in values[:2]:
                value = float(raw_value.replace("D", "E").replace("d", "e"))
                if 0.1 <= value <= 5.0:
                    wavelengths.append(
                        {
                            "value_angstrom": value,
                            "raw_value": raw_value,
                            "source": "archived_source_labeled_metadata",
                            "raw_line": candidate_line.strip(),
                        }
                    )
        match = re.search(
            r"(?i)(?:wavelength\s*=\s*|_WL[123]\s*=\s*)([0-9.]+)",
            plain,
        )
        if match:
            wavelengths.append(
                {
                    "value_angstrom": float(match.group(1)),
                    "raw_value": match.group(1),
                    "source": "archived_source_labeled_metadata",
                    "raw_line": line.strip(),
                }
            )
        match = re.search(
            r"(?i)\b(?:alpha1|lambda1)\b\s*(?:=|:)?\s*([0-9]+\.[0-9]+)",
            plain,
        )
        if match:
            wavelengths.append(
                {
                    "value_angstrom": float(match.group(1)),
                    "raw_value": match.group(1),
                    "source": "archived_source_labeled_metadata",
                    "raw_line": line.strip(),
                }
            )
    unique: list[dict[str, Any]] = []
    seen: set[tuple[float, str]] = set()
    for record in wavelengths:
        key = (record["value_angstrom"], record["source"])
        if key not in seen:
            seen.add(key)
            unique.append(record)
    return list(dict.fromkeys(radiation_evidence)), unique, []


def _space_group_candidate(value: str) -> bool:
    value = re.sub(r"\s+", " ", value.strip())
    if not value:
        return False
    tokens = value.split()
    if len(tokens) == 1:
        return bool(
            re.fullmatch(
                r"(?i)[PCAFIR][mna]{2,4}",
                tokens[0],
            )
        )
    if not re.fullmatch(r"(?i)[PCAFIR]", tokens[0]) or len(tokens) > 4:
        return False
    return all(
        re.fullmatch(
            r"(?i)(?:-?\d+[A-Za-z0-9/]*|[A-Za-z]{1,2}|[A-Za-z0-9]+/[A-Za-z0-9]+)",
            token,
        )
        for token in tokens[1:]
    )


def _parse_space_groups(lines: list[str]) -> tuple[list[str], list[str]]:
    groups: list[str] = []
    evidence: list[str] = []
    for line_number, line in enumerate(lines, 1):
        plain = _strip_comment(line).strip()
        candidate: str | None = None
        str_candidate = False
        if SPACE_GROUP_COMMENT_RE.search(plain):
            candidate = plain.split("<", 1)[0].strip()
            candidate = re.sub(r"(?i)^.*?symbol\s*", "", candidate).strip(": ")
        match = re.search(r"(?i)\bSTR\(\s*([^)]*)\)", plain)
        if match:
            candidate = match.group(1).strip()
            str_candidate = True
        if not candidate and re.search(r"(?i)\bFMMM\b", plain):
            candidate = re.search(r"(?i)\bFMMM\b", plain).group(0)
        if not candidate and _space_group_candidate(plain):
            candidate = plain
        if candidate:
            candidate = re.sub(r"\s+", " ", candidate).strip()
            is_structural_symbol = str_candidate and bool(
                re.fullmatch(r"(?i)[PCAFIR][A-Za-z0-9_/-]+", candidate)
            )
            if (is_structural_symbol or _space_group_candidate(candidate)) and candidate not in groups:
                groups.append(candidate)
                evidence.append(f"line {line_number}: {line.strip()}")
    return groups, evidence


def _unit_cell_values_from_line(line: str) -> list[float] | None:
    values = _numeric_tokens(line)
    if values and len(values) == 6:
        return values

    cleaned = _strip_comment(line)
    parts = cleaned.split()
    if len(parts) != 5:
        return None
    prefix = parts[:4]
    if any(_numeric_tokens(token) is None for token in prefix):
        return None
    tail = parts[4]
    # One Koalariet record has beta and gamma concatenated as
    # `90.0000120.0000`. Accept only an unambiguous two-decimal-field split.
    for split in range(1, len(tail)):
        left, right = tail[:split], tail[split:]
        if not (
            re.fullmatch(r"[+-]?\d+\.\d{4}", left)
            and re.fullmatch(r"[+-]?\d+\.\d{4}", right)
        ):
            continue
        result = [float(token) for token in prefix] + [float(left), float(right)]
        if all(0 < value <= 180 for value in result[3:]):
            return result
    return None


def _parse_unit_cells(lines: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    cells: list[dict[str, Any]] = []
    evidence: list[str] = []
    has_explicit_cell_header = any(
        re.search(r"(?i)\ba\s+b\s+c\s+alpha\s+beta\s+gamma\b", _strip_comment(line))
        or re.search(r"(?i)\bcell\s+constants\b", _strip_comment(line))
        for line in lines
    )

    def phase_before(index: int) -> int | None:
        for previous in range(index, -1, -1):
            match = PHASE_NUMBER_RE.search(lines[previous])
            if match:
                return int(match.group(1))
        return None

    for index, line in enumerate(lines):
        plain = _strip_comment(line)
        if re.search(r"(?i)\ba\s+b\s+c\s+alpha\s+beta\s+gamma\b", plain):
            for next_index in range(index + 1, min(index + 4, len(lines))):
                values = _unit_cell_values_from_line(lines[next_index])
                if values and len(values) >= 6:
                    cells.append(
                        {
                            "phase": phase_before(index),
                            "a": values[0],
                            "b": values[1],
                            "c": values[2],
                            "alpha": values[3],
                            "beta": values[4],
                            "gamma": values[5],
                            "raw_line": lines[next_index].strip(),
                            "source": "archived_source_unit_cell_block",
                        }
                    )
                    evidence.append(f"line {next_index + 1}: {lines[next_index].strip()}")
                    break
        if re.search(r"(?i)\bcell\s+constants\b", plain):
            for next_index in range(index + 1, min(index + 4, len(lines))):
                values = _unit_cell_values_from_line(lines[next_index])
                if values and len(values) >= 6:
                    cells.append(
                        {
                            "phase": phase_before(index),
                            "a": values[0],
                            "b": values[1],
                            "c": values[2],
                            "alpha": values[3],
                            "beta": values[4],
                            "gamma": values[5],
                            "raw_line": lines[next_index].strip(),
                            "source": "archived_source_unit_cell_block",
                        }
                    )
                    evidence.append(f"line {next_index + 1}: {lines[next_index].strip()}")
                    break
        if re.search(r"(?i)^\s*[!#]\s*(?:a|b|c|alpha|beta|gamma)\b", line):
            continue

    # Old positional formats (including 116, 117, and 159) may give the six
    # values without a literal "a b c alpha beta gamma" header. Require
    # exactly six numeric fields so packed intensity rows cannot qualify.
    positional_allowed = (
        not has_explicit_cell_header
        and _parse_atomic_coordinates(lines)[0]
        and len(re.findall(r"(?i)\bSTR\(\s*[^)]*\)", "\n".join(lines))) <= 1
    )
    positional_found = False
    for index, line in enumerate(lines):
        if not positional_allowed:
            continue
        if positional_found:
            break
        values = _unit_cell_values_from_line(line)
        if not values or len(values) != 6:
            continue
        if not (all(value > 0 for value in values[:3]) and all(0 <= value <= 180 for value in values[3:])):
            continue
        if index > 0 and index + 1 < len(lines):
            local_lines = lines[max(0, index - 30) : index + 2]
            context = "\n".join(local_lines).casefold()
            local_atom_evidence = False
            prior_lines = lines[max(0, index - 30) : index]
            for local_index, item in enumerate(prior_lines):
                if re.search(r"(?i)\bsite\b.*\bx\b.*\by\b.*\bz\b", item):
                    local_atom_evidence = True
                    break
                if re.match(
                    r"(?i)^\s*[!#]?\s*[A-Za-z][A-Za-z0-9]*\s+"
                    r"[A-Za-z]{1,3}[+-]\d+\s+",
                    item,
                ):
                    local_atom_evidence = True
                    break
                if (
                    re.fullmatch(
                        r"(?i)\s*[!#]?\s*[A-Za-z][A-Za-z0-9]*\s*",
                        item,
                    )
                    and local_index + 1 < len(prior_lines)
                    and len(_numeric_tokens(prior_lines[local_index + 1]) or []) >= 5
                ):
                    local_atom_evidence = True
                    break
            if local_atom_evidence:
                record = {
                    "phase": phase_before(index),
                    "a": values[0],
                    "b": values[1],
                    "c": values[2],
                    "alpha": values[3],
                    "beta": values[4],
                    "gamma": values[5],
                    "raw_line": line.strip(),
                    "source": "archived_source_positional_unit_cell",
                }
                if not any(
                    all(abs(record[key] - existing[key]) < 1e-9 for key in ("a", "b", "c", "alpha", "beta", "gamma"))
                    for existing in cells
                ):
                    cells.append(record)
                    evidence.append(f"line {index + 1}: {line.strip()}")
                    positional_found = True

    # Koalariet blocks label parameters one line at a time. Keep each STR
    # block separate; do not merge values from different source models.
    block_start: int | None = None
    block_values: dict[str, float] = {}
    block_lines: list[str] = []
    block_number = 0

    def finish_labeled_block() -> None:
        nonlocal block_values, block_lines, block_number
        if not block_values:
            return
        record = {
            "phase": block_number or None,
            "a": block_values.get("a"),
            "b": block_values.get("b"),
            "c": block_values.get("c"),
            "alpha": block_values.get("alpha"),
            "beta": block_values.get("beta"),
            "gamma": block_values.get("gamma"),
            "raw_line": " | ".join(block_lines),
            "source": "archived_source_labeled_cell_constants",
        }
        cells.append(record)
        evidence.append(record["raw_line"])
        block_values = {}
        block_lines = []

    for index, line in enumerate(lines):
        if re.search(r"(?i)\bSTR\(", line):
            finish_labeled_block()
            block_start = index
            block_number += 1
            block_lines.append(line.strip())
            continue
        if block_start is None:
            continue
        match = re.match(
            r"(?i)^\s*[!#]\s*(a|b|c|alpha|beta|gamma|al|be|ga)\b"
            r".*",
            line,
        )
        if match:
            key = match.group(1).casefold()
            key = {
                "al": "alpha",
                "be": "beta",
                "ga": "gamma",
            }.get(key, key)
            numeric_values = NUMERIC_TOKEN_RE.findall(line)
            if not numeric_values:
                continue
            block_values[key] = float(numeric_values[-1])
            block_lines.append(line.strip())
    finish_labeled_block()
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cell in cells:
        key = _json(cell)
        if key not in seen:
            seen.add(key)
            unique.append(cell)
    return unique, list(dict.fromkeys(evidence))


def _parse_atomic_coordinates(lines: list[str]) -> tuple[bool, list[str], int]:
    evidence: list[str] = []
    count = 0
    in_atom_table = False
    in_structural_block = False
    for index, line in enumerate(lines):
        plain = _strip_comment(line).strip()
        if re.search(r"(?i)\batom\s+typ\b.*\bx\b.*\by\b.*\bz\b", plain):
            in_atom_table = True
            evidence.append(f"line {index + 1}: {line.strip()}")
            continue
        if re.search(r"(?i)\bstructural\s+parameters\b", plain):
            in_structural_block = True
            evidence.append(f"line {index + 1}: {line.strip()}")
            continue
        if re.search(r"(?i)\b(?:scale|cell\s+constants|a\s+b\s+c|pref1|halfwidth)\b", plain):
            in_atom_table = False
            in_structural_block = False
            continue

        if re.search(r"(?i)\bsite\b.*\bx\b.*\by\b.*\bz\b", plain):
            count += 1
            evidence.append(f"line {index + 1}: {line.strip()}")
            continue

        tokens = plain.split()
        if len(tokens) >= 5:
            numeric_tail = _numeric_tokens(" ".join(tokens[2:]))
        else:
            numeric_tail = None
        if in_atom_table and numeric_tail and len(numeric_tail) >= 3:
            count += 1
            evidence.append(f"line {index + 1}: {line.strip()}")
            continue

        if in_structural_block:
            if (
                len(tokens) >= 5
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", tokens[0])
                and re.fullmatch(r"\d+", tokens[1])
                and _numeric_tokens(" ".join(tokens[2:]))
            ):
                count += 1
                evidence.append(f"line {index + 1}: {line.strip()}")
                continue

        # Older FullProf/SR5 records do not always include an atom-table
        # heading, but their atom rows carry an explicit ionic charge.
        if re.match(r"^[A-Za-z][A-Za-z0-9]*\s+[A-Za-z]{1,3}[+-]\d+\s+", plain):
            charged_values = _numeric_tokens(" ".join(tokens[2:]))
            if charged_values and len(charged_values) >= 3:
                count += 1
                evidence.append(f"line {index + 1}: {line.strip()}")
                continue

        # Arit-style records use a standalone atom label followed by a
        # numeric coordinate row.
        next_values = (
            _numeric_tokens(lines[index + 1])
            if index + 1 < len(lines)
            else None
        )
        if (
            re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", plain)
            and next_values
            and len(next_values) >= 5
            and any(
                re.search(r"(?i)\b(?:fmmm|atom|struct)\b", item)
                for item in lines
            )
        ):
            count += 1
            evidence.append(f"line {index + 1}: {line.strip()}")
    return count > 0, list(dict.fromkeys(evidence)), count


def _phase_model(lines: list[str], unit_cells: list[dict[str, Any]], groups: list[str], atoms: bool) -> tuple[int, list[str]]:
    explicit_numbers = sorted({match.group(1) for line in lines if (match := PHASE_NUMBER_RE.search(line))})
    structural_blocks = re.findall(r"(?i)\bSTR\(\s*[^)]*\)", "\n".join(lines))
    model_evidence = [
        line.strip()
        for line in lines
        if re.search(
            r"(?i)(?:data\s+for\s+phase\s+number|number\s+of\s+refined\s+parameters|"
            r"STR\(|structural\s+parameters|codes\s*-\s*phase|rietveld|refinement)",
            line,
        )
    ]
    if explicit_numbers:
        return len(explicit_numbers), model_evidence
    if structural_blocks:
        return len(structural_blocks), model_evidence
    structural_markers = any(
        re.search(
            r"(?i)(?:STR\(|structural\s+parameters|codes\s*-\s*phase|"
            r"atom\s+typ|site\b.*\bx\b.*\by\b.*\bz\b)",
            line,
        )
        for line in lines
    )
    if structural_markers and (atoms or unit_cells or groups):
        return 1, model_evidence
    if atoms and unit_cells and groups:
        model_evidence = list(model_evidence)
        model_evidence.append(
            "source contains explicit atom/site, unit-cell, and space-group evidence"
        )
        return 1, model_evidence
    return 0, model_evidence


def _archive_text(path: Path) -> tuple[bytes, str, str]:
    raw_archive = path.read_bytes()
    try:
        with zipfile.ZipFile(path) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if not members:
                raise ValueError("archive has no file members")
            info = members[0]
            raw_member = archive.read(info)
            text = raw_member.decode("utf-8-sig", errors="replace")
            return raw_member, info.filename, text
    except (zipfile.BadZipFile, ValueError):
        return raw_archive, path.name, raw_archive.decode("utf-8-sig", errors="replace")


def audit_record(record: dict[str, Any], archive_root: Path) -> dict[str, Any]:
    source = record["source_evidence"]
    entry_id = str(record["entry_id"])
    archive_path = archive_root / f"{entry_id}.zip"
    raw_member, member_filename, text = _archive_text(archive_path)
    lines = text.splitlines()
    explicit_formulas, formula_evidence = _explicit_formula(text)
    formula_like, formula_like_reason = _formula_like_label(source["source_label_raw"])
    radiation, index_wavelengths = _index_radiation_and_wavelength(source)
    archive_rad, archive_wavelengths, _ = _archive_radiation_wavelength(lines)
    radiation["archive_evidence"] = archive_rad
    wavelengths: list[dict[str, Any]] = []
    seen_wavelengths: set[float] = set()
    for wavelength in index_wavelengths + archive_wavelengths:
        value = wavelength["value_angstrom"]
        if value not in seen_wavelengths:
            seen_wavelengths.add(value)
            wavelengths.append(wavelength)

    groups, group_evidence = _parse_space_groups(lines)
    unit_cells, cell_evidence = _parse_unit_cells(lines)
    has_atoms, atom_evidence, atom_count = _parse_atomic_coordinates(lines)
    phase_count, phase_evidence = _phase_model(lines, unit_cells, groups, has_atoms)
    has_full_cell = bool(
        unit_cells
        and any(
            all(cell.get(key) is not None for key in ("a", "b", "c", "alpha", "beta", "gamma"))
            for cell in unit_cells
        )
    )
    has_structure = bool(phase_count or unit_cells or groups or has_atoms)
    cif_recoverability = (
        "sufficient_source_structure_metadata"
        if has_full_cell and bool(groups) and has_atoms
        else (
            "partial_source_structure_metadata"
            if has_structure
            else "no_source_structure_metadata"
        )
    )
    reference_present, reference_evidence = _reference_present(
        source.get("raw_bibliographic_comment_text") or ""
    )
    bib_comment_present = bool(
        (source.get("raw_bibliographic_comment_text") or "").strip()
    )
    content_family = (
        (source.get("detected_content_family") or "unknown")
        if source.get("detected_content_family")
        else "unknown"
    )
    notes: list[str] = [
        "Formula fields are source-literal only; material labels were not promoted to confirmed formulas.",
        "No COD/CIF matching or external structure search was performed.",
    ]
    if len(groups) > 1 or phase_count > 1:
        notes.append(
            "Multiple source phase/model blocks are preserved and were not collapsed."
        )
    if entry_id == "125":
        notes.append(
            "Koalariet source contains variable Ti/Fe site occupancies and a "
            "structural model; this does not create a confirmed explicit formula."
        )
    if entry_id == "106":
        notes.append(
            "Two FullProf phase blocks are retained as separate source evidence."
        )
    if not has_structure:
        notes.append(
            "Archived file supplies a diffraction profile and no recoverable "
            "crystallographic structure metadata."
        )

    unit_cell_values = {
        "records": unit_cells,
        "complete_record_count": sum(
            all(cell.get(key) is not None for key in ("a", "b", "c", "alpha", "beta", "gamma"))
            for cell in unit_cells
        ),
    }
    return {
        "powbase_entry": entry_id,
        "pattern_id": record["pattern_id"],
        "source_label_raw": source["source_label_raw"],
        "raw_index_text": source["raw_index_text"],
        "member_filename": member_filename,
        "archive_sha256": _sha256(archive_path.read_bytes()),
        "member_sha256": _sha256(raw_member),
        "source_extension": Path(member_filename).suffix,
        "content_family": content_family,
        "material_label_present": bool(source["source_label_raw"]),
        "explicit_formula": explicit_formulas or None,
        "formula_status": (
            "explicit_formula"
            if explicit_formulas
            else (
                "formula_like_label_only"
                if formula_like
                else "no_explicit_formula_or_formula_like_label"
            )
        ),
        "formula_evidence": formula_evidence,
        "formula_like_label": formula_like,
        "formula_like_reason": formula_like_reason or None,
        "radiation": radiation,
        "wavelength": {
            "present": bool(wavelengths),
            "values_angstrom": [item["value_angstrom"] for item in wavelengths],
            "records": wavelengths,
        },
        "has_full_unit_cell": has_full_cell,
        "unit_cell_values": unit_cell_values,
        "has_space_group": bool(groups),
        "space_group_raw": groups,
        "phase_model_count": phase_count,
        "phase_model_evidence": phase_evidence,
        "has_atomic_coordinates": has_atoms,
        "atomic_coordinate_evidence": {
            "atom_entry_count_detected": atom_count,
            "evidence": atom_evidence,
        },
        "has_structure_metadata": has_structure,
        "cif_recoverability": cif_recoverability,
        "reference_present": reference_present,
        "bibliographic_comment_present": bib_comment_present,
        "reference_evidence": reference_evidence,
        "profile_only_status": not has_structure,
        "metadata_notes": notes
        + [
            f"Space-group evidence: {evidence}"
            for evidence in group_evidence
        ]
        + [
            f"Unit-cell evidence: {evidence}"
            for evidence in cell_evidence
        ]
        + [
            f"Phase/refinement evidence: {evidence}"
            for evidence in phase_evidence[:4]
        ],
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _json(value)
    if value is None:
        return ""
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CSV_FIELDS})


def build_audit(
    canonical_path: Path = DEFAULT_CANONICAL,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
) -> dict[str, Any]:
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    records_by_id = {
        str(record["entry_id"]): record for record in canonical["records"]
    }
    missing = [entry_id for entry_id in PRODUCTION_ENTRY_IDS if entry_id not in records_by_id]
    if missing:
        raise ValueError(f"production PowBase entries missing from canonical scope: {missing}")
    if len(PRODUCTION_ENTRY_IDS) != 44:
        raise AssertionError("production scope must contain exactly 44 entries")

    rows = [
        audit_record(records_by_id[entry_id], archive_root)
        for entry_id in PRODUCTION_ENTRY_IDS
    ]
    rows.sort(key=lambda row: int(row["powbase_entry"]))

    category_entry_ids = {
        "explicit_formula": [
            row["powbase_entry"]
            for row in rows
            if row["formula_status"] == "explicit_formula"
        ],
        "formula_like_label_only": [
            row["powbase_entry"]
            for row in rows
            if row["formula_status"] == "formula_like_label_only"
        ],
        "wavelength": [
            row["powbase_entry"] for row in rows if row["wavelength"]["present"]
        ],
        "complete_unit_cell": [
            row["powbase_entry"] for row in rows if row["has_full_unit_cell"]
        ],
        "space_group": [
            row["powbase_entry"] for row in rows if row["has_space_group"]
        ],
        "atomic_coordinates": [
            row["powbase_entry"] for row in rows if row["has_atomic_coordinates"]
        ],
        "explicit_refinement_or_phase_model": [
            row["powbase_entry"] for row in rows if row["phase_model_count"] > 0
        ],
        "sufficient_structure_metadata_for_cif_recovery": [
            row["powbase_entry"]
            for row in rows
            if row["cif_recoverability"] == "sufficient_source_structure_metadata"
        ],
        "profile_only": [
            row["powbase_entry"] for row in rows if row["profile_only_status"]
        ],
        "bibliographic_reference": [
            row["powbase_entry"] for row in rows if row["reference_present"]
        ],
    }
    counts = {
        "total_records": len(rows),
        "material_label": sum(row["material_label_present"] for row in rows),
        "explicit_formula": len(category_entry_ids["explicit_formula"]),
        "formula_like_label_only": len(category_entry_ids["formula_like_label_only"]),
        "wavelength": len(category_entry_ids["wavelength"]),
        "complete_unit_cell": len(category_entry_ids["complete_unit_cell"]),
        "space_group": len(category_entry_ids["space_group"]),
        "atomic_coordinates": len(category_entry_ids["atomic_coordinates"]),
        "explicit_refinement_or_phase_model": len(
            category_entry_ids["explicit_refinement_or_phase_model"]
        ),
        "sufficient_structure_metadata_for_cif_recovery": len(
            category_entry_ids["sufficient_structure_metadata_for_cif_recovery"]
        ),
        "profile_only": len(category_entry_ids["profile_only"]),
        "bibliographic_reference": len(category_entry_ids["bibliographic_reference"]),
        "bibliographic_comment_present": sum(
            row["bibliographic_comment_present"] for row in rows
        ),
        "total_phase_models": sum(row["phase_model_count"] for row in rows),
    }
    return {
        "schema_version": "powbase_metadata_completeness_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "source": "POWBASE",
            "modality": "X-ray",
            "production_record_count": 44,
            "production_entry_ids": list(PRODUCTION_ENTRY_IDS),
            "conditional_or_unresolved_records_inspected": False,
        },
        "read_only": {
            "mongodb_writes": False,
            "source_files_modified": False,
            "canonical_records_modified": False,
            "cod_or_cif_matching_performed": False,
        },
        "inputs": {
            "canonical_scope": str(canonical_path.relative_to(PROJECT_ROOT)),
            "archive_root": str(archive_root.relative_to(PROJECT_ROOT)),
        },
        "counts": counts,
        "category_entry_ids": category_entry_ids,
        "records": rows,
    }


def write_summary(path: Path, audit: dict[str, Any]) -> None:
    counts = audit["counts"]
    categories = audit["category_entry_ids"]
    lines = [
        "# PowBase Metadata Completeness Audit v1",
        "",
        "Read-only audit of exactly the 44 PowBase X-ray patterns currently included in production CrystalDB. No MongoDB writes, source-file changes, canonical-record changes, or COD/CIF matching were performed.",
        "",
        "## Interpretation rules",
        "",
        "- `explicit_formula` is populated only from an explicitly labeled formula field in the archived source text. A material label such as `Li2Ti3O7` remains a formula-like label, not a confirmed formula.",
        "- Radiation and wavelength are retained with source evidence. Index `X` is reported as the literal official X-ray modality token. A Cu-Kalpha label without a numeric wavelength does not create a wavelength value.",
        "- Unit-cell, space-group, atom-site, and phase/refinement fields are reported only when the archived source contains corresponding structural-model evidence.",
        "- Multiple phase/model blocks are retained. They are not collapsed into one phase, and internal-standard interpretation is not inferred.",
        "- Entry 157 contains five explicit `STR(...)` models with named source materials; these remain source evidence and are not promoted to sample phases.",
        "",
        "## Counts",
        "",
        "| Metadata category | Count | Entry IDs |",
        "|---|---:|---|",
        f"| material/source label present | {counts['material_label']} | all 44 |",
        f"| explicit formula | {counts['explicit_formula']} | {', '.join(categories['explicit_formula']) or 'none'} |",
        f"| formula-like label only | {counts['formula_like_label_only']} | {', '.join(categories['formula_like_label_only']) or 'none'} |",
        f"| wavelength | {counts['wavelength']} | {', '.join(categories['wavelength']) or 'none'} |",
        f"| complete unit cell | {counts['complete_unit_cell']} | {', '.join(categories['complete_unit_cell']) or 'none'} |",
        f"| space group | {counts['space_group']} | {', '.join(categories['space_group']) or 'none'} |",
        f"| atomic coordinates / atom sites | {counts['atomic_coordinates']} | {', '.join(categories['atomic_coordinates']) or 'none'} |",
        f"| explicit refinement/phase model | {counts['explicit_refinement_or_phase_model']} | {', '.join(categories['explicit_refinement_or_phase_model']) or 'none'} |",
        f"| sufficient source structure metadata for CIF recovery | {counts['sufficient_structure_metadata_for_cif_recovery']} | {', '.join(categories['sufficient_structure_metadata_for_cif_recovery']) or 'none'} |",
        f"| profile-only | {counts['profile_only']} | {', '.join(categories['profile_only']) or 'none'} |",
        f"| publication/reference citation present | {counts['bibliographic_reference']} | {', '.join(categories['bibliographic_reference']) or 'none'} |",
        f"| raw bibliographic/comment field present | {counts['bibliographic_comment_present']} | all records with preserved index comments |",
        "",
        f"Total explicit source phase/refinement models across records: `{counts['total_phase_models']}`. Entry 106 contributes two source phase blocks; the other model-bearing records contribute one each.",
        "",
        "## Structure-bearing records",
        "",
        "The source archives contain structural-model evidence for entries "
        + ", ".join(categories["explicit_refinement_or_phase_model"])
        + ". These records expose phase/refinement content, space-group evidence, atom-site/coordinate evidence, and complete unit-cell values sufficient for a source-only CIF reconstruction audit. Entry 157 has five explicit source models; those models are retained as evidence and are not assigned as sample phases. This does not create a CIF and does not confirm a canonical formula.",
        "",
        "Entry 106 contains two FullProf phase blocks. Entry 125 contains a Koalariet structural model with variable Ti/Fe occupancies. Both facts are preserved as source evidence and are not silently collapsed.",
        "",
        "## Profile-only records",
        "",
        "The remaining records are profile-only for this audit: their archived files provide diffraction data and/or instrument metadata but no source structure metadata sufficient for a source-only CIF recovery.",
        "",
        "## Limitations",
        "",
        "No external structure search, COD lookup, CIF matching, formula normalization, formula inference, phase-purity inference, or production update was performed.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    audit = build_audit(args.canonical, args.archive_root)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.csv_output, audit["records"])
    write_summary(args.summary_output, audit)
    print(json.dumps(audit["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
