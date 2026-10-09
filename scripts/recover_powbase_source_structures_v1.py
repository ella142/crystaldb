"""Read-only source-structure recovery dry-run for nine PowBase records.

This module parses only the cached PowBase source members and writes recovered
CIFs to an isolated staging directory.  It never connects to MongoDB, performs
external structure searches, or modifies source/canonical files.
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
from fractions import Fraction
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gemmi  # noqa: E402

from scripts.audit_powbase import find_intensity_header_and_block  # noqa: E402


DEFAULT_ARCHIVE_ROOT = (
    PROJECT_ROOT / "data" / "archive" / "powbase_20261006" / "archives"
)
DEFAULT_CANONICAL_VALIDATION = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_production_validation_v1.csv"
)
DEFAULT_METADATA_COMPLETENESS = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_metadata_completeness_v1.csv"
)
DEFAULT_INDEX_MANIFEST = (
    PROJECT_ROOT / "data" / "mappings" / "powbase_v1_inclusion_manifest.csv"
)
DEFAULT_STAGING_ROOT = PROJECT_ROOT / "data" / "staging" / "powbase_source_structures_v1"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "mappings"

TARGET_ENTRY_IDS = ["106", "113", "116", "117", "124", "125", "157", "159", "160"]

CSV_FIELDS = [
    "entry_id",
    "pattern_id",
    "source_member",
    "source_archive_path",
    "source_label_raw",
    "source_formula_status",
    "experimental_profile_present",
    "profile_header_raw",
    "profile_expected_point_count",
    "profile_observed_intensity_count",
    "profile_point_count_consistency",
    "wavelength_status",
    "wavelength_raw",
    "wavelength_values_angstrom",
    "refinement_model_format",
    "source_model_id",
    "model_name",
    "phase_id",
    "unit_cell_complete",
    "a",
    "b",
    "c",
    "alpha",
    "beta",
    "gamma",
    "space_group_raw",
    "atom_site_count",
    "occupancy_present",
    "displacement_parameter_present",
    "source_structure_model",
    "refinement_metadata",
    "model_parse_status",
    "cif_recoverable",
    "cif_validation_status",
    "cif_validation_notes",
    "proposed_linkage_status",
    "linkage_reason",
    "staging_cif_path",
    "source_archive_sha256",
    "source_member_sha256",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _json(value)
    return value


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(value or "")).strip()


def _strip_comment(line: str) -> str:
    return re.sub(r"^\s*[!#;]\s?", "", line).strip()


NUMBER_RE = r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[EeDd][+-]?\d+)?"


def _numbers(line: str) -> list[float]:
    return [
        float(token.replace("D", "E").replace("d", "e"))
        for token in re.findall(NUMBER_RE, _strip_comment(line))
    ]


def _exact_six_numbers(line: str) -> list[float] | None:
    values = _numbers(line)
    return values if len(values) == 6 else None


def _cell_values_from_line(line: str) -> list[float] | None:
    cleaned = _strip_comment(line)
    tokens = cleaned.split()
    values = _exact_six_numbers(line)
    if (
        values
        and len(tokens) == 6
        and all(_parse_scalar(token) is not None for token in tokens)
        and all(value > 0 for value in values[:3])
        and all(
        0 < value <= 180 for value in values[3:]
        )
    ):
        return values

    parts = tokens
    if len(parts) != 5:
        return None
    prefix = parts[:4]
    if any(_parse_scalar(token) is None for token in prefix):
        return None
    tail = parts[4]
    candidates: list[list[float]] = []
    for split in range(1, len(tail)):
        left, right = tail[:split], tail[split:]
        if not (
            re.fullmatch(r"[+-]?\d+\.\d{4}", left)
            and re.fullmatch(r"[+-]?\d+\.\d{4}", right)
        ):
            continue
        candidate = [float(token) for token in prefix] + [
            float(left),
            float(right),
        ]
        if all(value > 0 for value in candidate[:3]) and all(
            0 < value <= 180 for value in candidate[3:]
        ):
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _parse_scalar(value: str) -> float | None:
    value = value.strip().rstrip(";")
    value = value.lstrip("@=").strip()
    value = value.replace(" ", "")
    if re.fullmatch(NUMBER_RE, value):
        return float(value.replace("D", "E").replace("d", "e"))
    if re.fullmatch(r"[+-]?\d+\s*/\s*[+-]?\d+", value):
        return float(Fraction(value.replace(" ", "")))
    return None


def _parse_axis_expression(text: str) -> float | None:
    text = text.strip().rstrip(";")
    text = text.lstrip("@=").strip()
    text = text.replace(" ", "")
    return _parse_scalar(text)


def _element_from_type(type_raw: str, label: str) -> str:
    token = re.sub(r"[^A-Za-z]", "", type_raw or "")
    if not token:
        token = re.sub(r"[^A-Za-z]", "", label or "")
    if not token:
        return "?"
    if len(token) >= 2 and token[:2].casefold() in {
        "ba",
        "ca",
        "co",
        "cr",
        "fe",
        "li",
        "mg",
        "mn",
        "na",
        "nb",
        "si",
        "tb",
        "ti",
        "la",
        "al",
        "cu",
        "zn",
        "zr",
        "as",
        "pb",
        "hf",
        "ta",
        "mo",
        "ru",
        "rh",
        "sn",
        "cs",
        "sr",
        "y",
        "w",
        "v",
    }:
        return token[:2].capitalize()
    return token[:1].upper()


def _model_name_from_str(line: str) -> tuple[str, str]:
    match = re.search(r"(?i)\bSTR\(\s*([^)]*)\)", line)
    model_id = f"STR({match.group(1).strip()})" if match else "STR_UNKNOWN"
    model_name = ""
    if "'" in line:
        model_name = line.split("'", 1)[1].strip()
    return model_id, model_name


def _parse_fullprof_models(lines: list[str], entry_id: str) -> list[dict[str, Any]]:
    starts = [
        index
        for index, line in enumerate(lines)
        if re.search(r"(?i)\bdata\s+for\s+phase\s+number\s*:", line)
    ]
    models: list[dict[str, Any]] = []
    for position, start in enumerate(starts):
        stop = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:stop]
        header = lines[start]
        phase_match = re.search(r"(?i)\bdata\s+for\s+phase\s+number\s*:\s*(\d+)", header)
        phase_id = phase_match.group(1) if phase_match else str(position + 1)
        r_match = re.search(r"(?i)R_Bragg\s*:\s*([0-9.]+)", header)
        model_name = ""
        for line in block[1:12]:
            candidate = _strip_comment(line)
            if candidate and not candidate.startswith(("-", "Nat", "Irf")):
                if not re.search(r"(?i)number\s+of|space\s+group|atom\s+typ", candidate):
                    model_name = candidate
                    break
        space_group = None
        sg_index = None
        for index, line in enumerate(block):
            if re.search(r"(?i)space\s+group\s+symbol", line):
                sg_index = index
                space_group = _strip_comment(line).split("<--", 1)[0].strip()
                break
        cell = None
        for index, line in enumerate(block):
            if re.search(r"(?i)^\s*[!#]?\s*a\s+b\s+c\s+alpha\s+beta\s+gamma", line):
                for following in block[index + 1 : index + 4]:
                    values = _cell_values_from_line(following)
                    if values:
                        cell = dict(zip(("a", "b", "c", "alpha", "beta", "gamma"), values))
                        break
                if cell:
                    break
        atom_start = next(
            (
                index
                for index, line in enumerate(block)
                if re.search(r"(?i)atom\s+typ\s+.*\bx\b.*\by\b.*\bz\b", line)
            ),
            None,
        )
        atoms: list[dict[str, Any]] = []
        if atom_start is not None:
            for line in block[atom_start + 1 :]:
                plain = _strip_comment(line)
                if re.search(r"(?i)^(?:scale|u\s+v\s+w|a\s+b\s+c|pref)", plain):
                    break
                tokens = plain.split()
                if len(tokens) < 7:
                    continue
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", tokens[0]):
                    continue
                numeric = [_parse_scalar(token) for token in tokens[2:]]
                if len(numeric) < 5 or any(value is None for value in numeric[:5]):
                    continue
                atoms.append(
                    {
                        "label": tokens[0],
                        "type_raw": tokens[1],
                        "element": _element_from_type(tokens[1], tokens[0]),
                        "x": numeric[0],
                        "y": numeric[1],
                        "z": numeric[2],
                        "b_iso": numeric[3],
                        "occupancy": numeric[4],
                        "raw_line": line.strip(),
                    }
                )
        refined_match = next(
            (
                re.search(r"([0-9]+)\s+!Number of refined parameters", line)
                for line in lines[max(0, start - 12) : start]
                if re.search(r"(?i)number\s+of\s+refined\s+parameters", line)
            ),
            None,
        )
        models.append(
            {
                "entry_id": entry_id,
                "source_model_id": f"PHASE_{phase_id}",
                "phase_id": phase_id,
                "model_name": model_name,
                "space_group_raw": space_group,
                "cell": cell,
                "atoms": atoms,
                "refinement_metadata": {
                    "format": "FullProf",
                    "number_refined_parameters": (
                        int(refined_match.group(1)) if refined_match else None
                    ),
                    "r_bragg": float(r_match.group(1)) if r_match else None,
                    "raw_phase_header": header.strip(),
                },
                "source_evidence": [
                    header.strip(),
                    *(line.strip() for line in block if "space group symbol" in line.casefold()),
                ],
            }
        )
    return models


def _parse_sr5_model(lines: list[str], entry_id: str) -> list[dict[str, Any]]:
    sg_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(
                r"\s*!\s*[PCAFIR]\s+"
                r"[A-Za-z0-9]+(?:[/_-][A-Za-z0-9]+)?"
                r"(?:\s+[A-Za-z0-9_/-]+){0,4}\s*",
                line,
            )
        ),
        None,
    )
    if sg_index is None:
        return []
    name = _strip_comment(lines[sg_index - 2]) if sg_index >= 2 else ""
    space_group = _strip_comment(lines[sg_index])
    cell_index = next(
        (
            index
            for index in range(sg_index + 1, min(len(lines), sg_index + 40))
            if _cell_values_from_line(lines[index])
        ),
        None,
    )
    cell = None
    if cell_index is not None:
        values = _cell_values_from_line(lines[cell_index])
        if values:
            cell = dict(zip(("a", "b", "c", "alpha", "beta", "gamma"), values))
    atoms: list[dict[str, Any]] = []
    end = cell_index if cell_index is not None else len(lines)
    for line in lines[sg_index + 1 : end]:
        tokens = _strip_comment(line).split()
        if len(tokens) < 7 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", tokens[0]):
            continue
        numeric = [_parse_scalar(token) for token in tokens[2:]]
        if len(numeric) < 5 or any(value is None for value in numeric[:5]):
            continue
        atoms.append(
            {
                "label": tokens[0],
                "type_raw": tokens[1],
                "element": _element_from_type(tokens[1], tokens[0]),
                "x": numeric[0],
                "y": numeric[1],
                "z": numeric[2],
                "b_iso": numeric[3],
                "occupancy": numeric[4],
                "raw_line": line.strip(),
            }
        )
    return [
        {
            "entry_id": entry_id,
            "source_model_id": "SR5_PHASE_1",
            "phase_id": "1",
            "model_name": name,
            "space_group_raw": space_group,
            "cell": cell,
            "atoms": atoms,
            "refinement_metadata": {
                "format": "SR5",
                "raw_control_lines": [line.strip() for line in lines[:10]],
            },
            "source_evidence": [lines[sg_index].strip(), lines[cell_index].strip() if cell_index is not None else ""],
        }
    ]


def _parse_site_line(line: str) -> dict[str, Any] | None:
    plain = _strip_comment(line)
    match = re.match(
        r"(?i)^site\s+(\S+).*?\bx\s+(.+?)\s+y\s+(.+?)\s+z\s+(.+?)\s+"
        r"occ\s+(\S+)\s+(\S+).*?\bbeq\s+(?:@\s*)?(\S+)",
        plain,
    )
    if not match:
        return None
    label, x_raw, y_raw, z_raw, type_raw, occ_raw, b_raw = match.groups()
    x = _parse_axis_expression(x_raw.rstrip(";"))
    y = _parse_axis_expression(y_raw.rstrip(";"))
    z = _parse_axis_expression(z_raw.rstrip(";"))
    occupancy = _parse_scalar(occ_raw)
    b_iso = _parse_scalar(b_raw)
    if any(value is None for value in (x, y, z, occupancy, b_iso)):
        return None
    return {
        "label": label,
        "type_raw": type_raw,
        "element": _element_from_type(type_raw, label),
        "x": x,
        "y": y,
        "z": z,
        "b_iso": b_iso,
        "occupancy": occupancy,
        "raw_line": line.strip(),
    }


def _parse_koalariet_models(lines: list[str], entry_id: str) -> list[dict[str, Any]]:
    starts = [
        index for index, line in enumerate(lines) if re.search(r"(?i)\bSTR\(", line)
    ]
    models: list[dict[str, Any]] = []
    for position, start in enumerate(starts):
        stop = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:stop]
        model_id, model_name = _model_name_from_str(lines[start])
        sg_match = re.search(r"(?i)\bSTR\(\s*([^)]*)\)", lines[start])
        space_group = sg_match.group(1).strip() if sg_match else None
        cell_values: dict[str, float] = {}
        numeric_cell = next(
            (_cell_values_from_line(line) for line in block if _cell_values_from_line(line)),
            None,
        )
        if numeric_cell:
            cell_values = dict(
                zip(("a", "b", "c", "alpha", "beta", "gamma"), numeric_cell)
            )
        for line in block:
            plain = _strip_comment(line)
            match = re.match(r"(?i)^(a|b|c|al|be|ga)\b.*", plain)
            if not match:
                continue
            key = {"al": "alpha", "be": "beta", "ga": "gamma"}.get(
                match.group(1).casefold(), match.group(1).casefold()
            )
            tokens = plain.split()
            candidate = None
            if key in {"a", "b", "c", "alpha", "beta", "gamma"}:
                for token in tokens[1:]:
                    candidate = _parse_scalar(token)
                    if candidate is not None:
                        break
            if candidate is not None and key not in cell_values:
                cell_values[key] = candidate

        atoms: list[dict[str, Any]] = []
        numeric_atoms: list[dict[str, Any]] = []
        for line in block:
            plain = _strip_comment(line)
            tokens = plain.split()
            if len(tokens) >= 7 and re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", tokens[0]):
                numeric = [_parse_scalar(token) for token in tokens[2:]]
                if len(numeric) >= 5 and all(value is not None for value in numeric[:5]):
                    numeric_atoms.append(
                        {
                            "label": tokens[0],
                            "type_raw": tokens[1],
                            "element": _element_from_type(tokens[1], tokens[0]),
                            "x": numeric[0],
                            "y": numeric[1],
                            "z": numeric[2],
                            "b_iso": numeric[3],
                            "occupancy": numeric[4],
                            "raw_line": line.strip(),
                        }
                    )
        if numeric_atoms:
            atoms = numeric_atoms
        else:
            for line in block:
                site = _parse_site_line(line)
                if site:
                    atoms.append(site)

        refinement: dict[str, Any] = {
            "format": "Koalariet",
            "global_iters": None,
            "global_r_wp": None,
            "global_r_exp": None,
            "global_r_p_dash": None,
        }
        for line in block:
            for key in ("global_iters", "global_r_wp", "global_r_exp", "global_r_p_dash"):
                match = re.search(rf"(?i)\b{key}\s+({NUMBER_RE})", line)
                if match:
                    refinement[key] = float(match.group(1))
        models.append(
            {
                "entry_id": entry_id,
                "source_model_id": model_id,
                "phase_id": str(position + 1),
                "model_name": model_name,
                "space_group_raw": space_group,
                "cell": cell_values or None,
                "atoms": atoms,
                "refinement_metadata": refinement,
                "source_evidence": [lines[start].strip()],
            }
        )
    return models


def _parse_arit_model(lines: list[str], entry_id: str) -> list[dict[str, Any]]:
    first = _strip_comment(lines[0]) if lines else ""
    parts = first.split()
    space_group = " ".join(parts[1:]) if len(parts) > 1 else None
    model_name = _strip_comment(lines[2]) if len(lines) > 2 else ""
    cell_candidates = [
        index for index, line in enumerate(lines) if _cell_values_from_line(line)
    ]
    cell_index = max(cell_candidates) if cell_candidates else None
    cell = None
    if cell_index is not None:
        values = _cell_values_from_line(lines[cell_index])
        if values:
            cell = dict(zip(("a", "b", "c", "alpha", "beta", "gamma"), values))
    atoms: list[dict[str, Any]] = []
    for index, line in enumerate(lines[:cell_index] if cell_index is not None else lines):
        label_match = re.fullmatch(r"\s*[!#]\s*([A-Za-z][A-Za-z0-9]*)\s*", line)
        if not label_match or index + 1 >= len(lines):
            continue
        values = _numbers(lines[index + 1])
        if len(values) < 5:
            continue
        x, y, z, b_iso, occupancy = values[-5:]
        label = label_match.group(1)
        atoms.append(
            {
                "label": label,
                "type_raw": label,
                "element": _element_from_type(label, label),
                "x": x,
                "y": y,
                "z": z,
                "b_iso": b_iso,
                "occupancy": occupancy,
                "raw_line": f"{line.strip()} / {lines[index + 1].strip()}",
            }
        )
    return [
        {
            "entry_id": entry_id,
            "source_model_id": "ARIT_PHASE_1",
            "phase_id": "1",
            "model_name": model_name,
            "space_group_raw": space_group,
            "cell": cell,
            "atoms": atoms,
            "refinement_metadata": {"format": "old Arit-style source model"},
            "source_evidence": [lines[0].strip(), lines[cell_index].strip() if cell_index is not None else ""],
        }
    ]


def _parse_winmprof_model(lines: list[str], entry_id: str) -> list[dict[str, Any]]:
    sg_index = next(
        (
            index
            for index, line in enumerate(lines)
            if _strip_comment(line).casefold() == "fmmm"
        ),
        None,
    )
    cell_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "cell constants" in _strip_comment(line).casefold()
        ),
        None,
    )
    cell = None
    if cell_index is not None and cell_index + 1 < len(lines):
        values = _exact_six_numbers(lines[cell_index + 1])
        if values:
            cell = dict(zip(("a", "b", "c", "alpha", "beta", "gamma"), values))
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if "structural parameters" in _strip_comment(line).casefold()
        ),
        None,
    )
    atoms: list[dict[str, Any]] = []
    if start is not None:
        for line in lines[start + 1 :]:
            if "scale factors" in _strip_comment(line).casefold():
                break
            plain = _strip_comment(line)
            tokens = plain.split()
            if len(tokens) < 8 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", tokens[0]):
                continue
            numeric = [_parse_scalar(token) for token in tokens[1:]]
            if len(numeric) < 7 or any(value is None for value in numeric[:7]):
                continue
            atoms.append(
                {
                    "label": tokens[0],
                    "type_raw": tokens[0],
                    "element": _element_from_type(tokens[0], tokens[0]),
                    "x": numeric[2],
                    "y": numeric[3],
                    "z": numeric[4],
                    "b_iso": numeric[5],
                    "occupancy": None,
                    "raw_line": line.strip(),
                }
            )
    refinement: dict[str, Any] = {"format": "WinMProf"}
    for line in lines:
        if "R FACTORS" in line.upper():
            refinement["r_factors_raw"] = line.strip()
    return [
        {
            "entry_id": entry_id,
            "source_model_id": "WINMPROF_PHASE_1",
            "phase_id": "1",
            "model_name": "La2 Cu O4",
            "space_group_raw": _strip_comment(lines[sg_index]) if sg_index is not None else None,
            "cell": cell,
            "atoms": atoms,
            "refinement_metadata": refinement,
            "source_evidence": [
                lines[sg_index].strip() if sg_index is not None else "",
                lines[cell_index].strip() if cell_index is not None else "",
            ],
        }
    ]


def _parse_models(entry_id: str, text: str, raw_index_text: str) -> tuple[str, list[dict[str, Any]]]:
    lines = text.splitlines()
    index_lower = raw_index_text.casefold()
    if re.search(r"(?i)\bdata\s+for\s+phase\s+number", text):
        return "FullProf", _parse_fullprof_models(lines, entry_id)
    if "koalariet" in index_lower or re.search(r"(?i)\bSTR\(", text):
        return "Koalariet", _parse_koalariet_models(lines, entry_id)
    if "sr5" in index_lower:
        return "SR5", _parse_sr5_model(lines, entry_id)
    if entry_id == "159":
        return "old Arit-style", _parse_arit_model(lines, entry_id)
    if entry_id == "160":
        return "WinMProf", _parse_winmprof_model(lines, entry_id)
    return "source structural format", []


def _source_wavelength(raw_index_text: str, text: str) -> dict[str, Any]:
    explicit_lines: list[str] = []
    values: list[float] = []
    for line in text.splitlines():
        if re.search(
            r"(?i)(?:lambda1|alpha1|alpha2|wavelength|anode\s+cu)",
            line,
        ):
            explicit_lines.append(line.strip())
            nums = _numbers(line)
            if "alpha1" in line.casefold() or "lambda1" in line.casefold():
                values.extend(nums[:2])
            elif "wavelength" in line.casefold():
                values.extend(nums[:2])
    unique_values = list(dict.fromkeys(values))
    if explicit_lines and unique_values:
        return {
            "status": "explicit_source_wavelength",
            "raw": explicit_lines,
            "values_angstrom": unique_values,
        }
    return {
        "status": "not_explicitly_recovered",
        "raw": [],
        "values_angstrom": [],
    }


def _profile_info(text: str) -> dict[str, Any]:
    pattern = find_intensity_header_and_block(text)
    return {
        "present": bool(pattern.get("header_found")),
        "header_raw": pattern.get("header_raw_text"),
        "expected_point_count": pattern.get("expected_point_count"),
        "observed_intensity_count": pattern.get("observed_intensity_count"),
        "point_count_consistency": pattern.get("point_count_consistency"),
        "start_raw": pattern.get("two_theta_start_raw"),
        "step_raw": pattern.get("step_raw"),
        "end_raw": pattern.get("two_theta_end_raw"),
    }


def _source_formula_status(entry_id: str, metadata_rows: dict[str, dict[str, str]]) -> str:
    return metadata_rows[entry_id]["formula_status"]


def _space_group_for_cif(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = re.sub(r"_+", " ", raw).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _cif_quote(value: str) -> str:
    value = str(value).replace("'", "''")
    return f"'{value}'"


def _cif_value(value: Any) -> str:
    if value is None:
        return "."
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def _unquote_cif_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _cif_text(
    *,
    record: dict[str, Any],
    model: dict[str, Any],
) -> str:
    cell = model["cell"]
    data_name = f"POWBASE_{record['entry_id']}_{model['source_model_id']}"
    lines = [
        f"data_{re.sub(r'[^A-Za-z0-9_]', '_', data_name)}",
        "_audit_creation_method 'CrystalDB PowBase source-only recovery v1'",
        f"_powbase_source 'POWBASE'",
        f"_powbase_source_entry_id {_cif_quote(record['entry_id'])}",
        f"_powbase_source_member {_cif_quote(record['source_member'])}",
        f"_powbase_source_model_id {_cif_quote(model['source_model_id'])}",
        f"_powbase_source_structure_model {_cif_quote('true')}",
        f"_powbase_source_model_name {_cif_quote(model['model_name'] or 'unknown')}",
        f"_powbase_source_label_raw {_cif_quote(record['source_label_raw'])}",
        f"_powbase_recovery_method {_cif_quote('source_literal_structural_fields_only')}",
        f"_chemical_name_common {_cif_quote(model['model_name'] or record['source_label_raw'])}",
        f"_cell_length_a {_cif_value(cell['a'])}",
        f"_cell_length_b {_cif_value(cell['b'])}",
        f"_cell_length_c {_cif_value(cell['c'])}",
        f"_cell_angle_alpha {_cif_value(cell['alpha'])}",
        f"_cell_angle_beta {_cif_value(cell['beta'])}",
        f"_cell_angle_gamma {_cif_value(cell['gamma'])}",
        f"_space_group_name_H-M_alt {_cif_quote(_space_group_for_cif(model['space_group_raw']))}",
        f"_powbase_space_group_raw {_cif_quote(model['space_group_raw'])}",
        "",
        "loop_",
        "  _atom_site_label",
        "  _atom_site_type_symbol",
        "  _atom_site_fract_x",
        "  _atom_site_fract_y",
        "  _atom_site_fract_z",
        "  _atom_site_occupancy",
        "  _atom_site_B_iso_or_equiv",
    ]
    for atom in model["atoms"]:
        lines.append(
            "  "
            + " ".join(
                [
                    _cif_quote(atom["label"]),
                    _cif_quote(atom["element"]),
                    _cif_value(atom["x"]),
                    _cif_value(atom["y"]),
                    _cif_value(atom["z"]),
                    _cif_value(atom.get("occupancy")),
                    _cif_value(atom.get("b_iso")),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _validate_cif(path: Path, model: dict[str, Any]) -> dict[str, Any]:
    try:
        document = gemmi.cif.read_file(str(path))
        block = document.sole_block()
        required = {
            "a": "_cell_length_a",
            "b": "_cell_length_b",
            "c": "_cell_length_c",
            "alpha": "_cell_angle_alpha",
            "beta": "_cell_angle_beta",
            "gamma": "_cell_angle_gamma",
        }
        cell_values = {
            key: float(block.find_value(tag))
            for key, tag in required.items()
        }
        space_group = _unquote_cif_value(
            block.find_value("_space_group_name_H-M_alt")
        )
        atom_column = block.find_loop("_atom_site_label")
        if atom_column:
            atom_loop = atom_column.get_loop()
            tags = [str(tag) for tag in atom_loop.tags]
            values = list(atom_loop.values)
            width = atom_loop.width()
            tag_indexes = {tag: index for index, tag in enumerate(tags)}

            def column_values(tag: str) -> list[str]:
                column_index = tag_indexes[tag]
                return [
                    values[offset + column_index]
                    for offset in range(0, len(values), width)
                ]

            atom_count = atom_loop.length()
            occupancies = column_values("_atom_site_occupancy")
            coords = [
                column_values(tag)
                for tag in (
                    "_atom_site_fract_x",
                    "_atom_site_fract_y",
                    "_atom_site_fract_z",
                )
            ]
        else:
            atom_count = 0
            occupancies = []
            coords = [[], [], []]
        source_atom_count = len(model["atoms"])
        discrepancies: list[str] = []
        for key, expected in model["cell"].items():
            if abs(cell_values[key] - expected) > 1e-8:
                discrepancies.append(f"cell {key} changed: {expected} -> {cell_values[key]}")
        if space_group != _space_group_for_cif(model["space_group_raw"]):
            discrepancies.append("space group serialization differs from normalized source value")
        if atom_count != source_atom_count:
            discrepancies.append(
                f"atom count changed: {source_atom_count} -> {atom_count}"
            )
        if len(coords[0]) != source_atom_count:
            discrepancies.append("coordinate row count does not match source atom count")
        return {
            "status": "passed" if not discrepancies else "passed_with_discrepancies",
            "atom_site_count": atom_count,
            "occupancy_value_count": sum(value not in {".", "?"} for value in occupancies),
            "unit_cell_values": cell_values,
            "space_group": space_group,
            "discrepancies": discrepancies,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "atom_site_count": None,
            "occupancy_value_count": None,
            "unit_cell_values": None,
            "space_group": None,
            "discrepancies": [f"{type(exc).__name__}: {exc}"],
        }


def _linkage(entry_id: str, model_count: int) -> tuple[str, str]:
    if entry_id == "157":
        return (
            "source_link_ambiguous",
            "One experimental pattern contains five explicit STR models; the source does not establish which models are sample phases or how they map to the pattern.",
        )
    if model_count == 1:
        return (
            "source_link_supported",
            "The same PowBase source member contains one explicit structure model and the experimental diffraction profile.",
        )
    return (
        "source_link_ambiguous",
        "The same PowBase source member contains multiple explicit structure models/phases for one experimental pattern.",
    )


def _load_rows(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row[key]: row for row in csv.DictReader(handle)}


def build_audit(
    *,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    canonical_validation_path: Path = DEFAULT_CANONICAL_VALIDATION,
    metadata_completeness_path: Path = DEFAULT_METADATA_COMPLETENESS,
    index_manifest_path: Path = DEFAULT_INDEX_MANIFEST,
    staging_root: Path = DEFAULT_STAGING_ROOT,
) -> dict[str, Any]:
    canonical_rows = _load_rows(canonical_validation_path, "entry_id")
    metadata_rows = _load_rows(metadata_completeness_path, "powbase_entry")
    index_rows = _load_rows(index_manifest_path, "entry_id")
    records: list[dict[str, Any]] = []
    preflight: list[dict[str, Any]] = []
    for entry_id in TARGET_ENTRY_IDS:
        archive_path = archive_root / f"{entry_id}.zip"
        archive_bytes = archive_path.read_bytes()
        archive_sha256 = _sha256(archive_bytes)
        with zipfile.ZipFile(archive_path) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) != 1:
                raise AssertionError(f"entry {entry_id} expected one source member, found {members}")
            info = members[0]
            member_bytes = archive.read(info)
        text = member_bytes.decode("utf-8-sig", errors="replace")
        profile = _profile_info(text)
        format_name, models = _parse_models(
            entry_id, text, index_rows[entry_id]["raw_index_text"]
        )
        if not models:
            raise AssertionError(f"no structure model parsed for entry {entry_id}")
        wavelength = _source_wavelength(index_rows[entry_id]["raw_index_text"], text)
        link_status, link_reason = _linkage(entry_id, len(models))
        preflight.append(
            {
                "entry_id": entry_id,
                "pattern_id": canonical_rows[entry_id]["pattern_id"],
                "source_archive_path": str(archive_path.relative_to(PROJECT_ROOT)),
                "source_member_filenames": [item.filename for item in members],
                "source_label_raw": index_rows[entry_id]["source_label_raw"],
                "experimental_profile_present": profile["present"],
                "profile": profile,
                "wavelength": wavelength,
                "refinement_model_format": format_name,
                "explicit_structure_model_count": len(models),
                "profile_and_model_same_source_record": bool(
                    profile["present"] and info.filename and models
                ),
                "source_archive_sha256": archive_sha256,
                "source_member_sha256": _sha256(member_bytes),
                "proposed_linkage_status": link_status,
                "linkage_reason": link_reason,
            }
        )
        for model in models:
            cell = model.get("cell") or {}
            complete = bool(
                all(cell.get(key) is not None for key in ("a", "b", "c", "alpha", "beta", "gamma"))
            )
            occupancy_present = bool(
                model["atoms"] and all(atom.get("occupancy") is not None for atom in model["atoms"])
            )
            displacement_present = bool(
                model["atoms"] and all(atom.get("b_iso") is not None for atom in model["atoms"])
            )
            cif_recoverable = bool(
                complete
                and bool(model.get("space_group_raw"))
                and bool(model["atoms"])
            )
            staging_path = None
            validation = {
                "status": "not_attempted",
                "atom_site_count": None,
                "occupancy_value_count": None,
                "unit_cell_values": None,
                "space_group": None,
                "discrepancies": [],
            }
            model_parse_status = "parsed"
            if not complete:
                model_parse_status = "parsed_incomplete_unit_cell"
            if cif_recoverable:
                staging_root.mkdir(parents=True, exist_ok=True)
                filename = f"POWBASE_{entry_id}_{model['source_model_id'].replace('(', '_').replace(')', '').replace('/', '_')}.cif"
                cif_path = staging_root / filename
                cif_path.write_text(
                    _cif_text(
                        record={
                            "entry_id": entry_id,
                            "source_member": info.filename,
                            "source_label_raw": index_rows[entry_id]["source_label_raw"],
                        },
                        model=model,
                    ),
                    encoding="utf-8",
                )
                validation = _validate_cif(cif_path, model)
                staging_path = str(cif_path.relative_to(PROJECT_ROOT))
            if not cif_recoverable:
                validation["status"] = "not_recoverable_missing_complete_source_fields"
                validation["discrepancies"] = [
                    "source-only CIF recovery withheld because a complete unit cell, space group, and atom-site set were not all explicitly available"
                ]
            records.append(
                {
                    "entry_id": entry_id,
                    "pattern_id": canonical_rows[entry_id]["pattern_id"],
                    "source_member": info.filename,
                    "source_archive_path": str(archive_path.relative_to(PROJECT_ROOT)),
                    "source_label_raw": index_rows[entry_id]["source_label_raw"],
                    "source_formula_status": _source_formula_status(entry_id, metadata_rows),
                    "experimental_profile_present": profile["present"],
                    "profile_header_raw": profile["header_raw"],
                    "profile_expected_point_count": profile["expected_point_count"],
                    "profile_observed_intensity_count": profile["observed_intensity_count"],
                    "profile_point_count_consistency": profile["point_count_consistency"],
                    "wavelength_status": wavelength["status"],
                    "wavelength_raw": wavelength["raw"],
                    "wavelength_values_angstrom": wavelength["values_angstrom"],
                    "refinement_model_format": format_name,
                    "source_model_id": model["source_model_id"],
                    "model_name": model["model_name"],
                    "phase_id": model["phase_id"],
                    "unit_cell_complete": complete,
                    "a": cell.get("a"),
                    "b": cell.get("b"),
                    "c": cell.get("c"),
                    "alpha": cell.get("alpha"),
                    "beta": cell.get("beta"),
                    "gamma": cell.get("gamma"),
                    "space_group_raw": model["space_group_raw"],
                    "atom_site_count": len(model["atoms"]),
                    "occupancy_present": occupancy_present,
                    "displacement_parameter_present": displacement_present,
                    "source_structure_model": True,
                    "refinement_metadata": model["refinement_metadata"],
                    "model_parse_status": model_parse_status,
                    "cif_recoverable": cif_recoverable,
                    "cif_validation_status": validation["status"],
                    "cif_validation_notes": validation["discrepancies"],
                    "proposed_linkage_status": link_status,
                    "linkage_reason": link_reason,
                    "staging_cif_path": staging_path,
                    "source_archive_sha256": archive_sha256,
                    "source_member_sha256": _sha256(member_bytes),
                    "source_evidence": model["source_evidence"],
                    "atom_sites": model["atoms"],
                }
            )

    production_wavelength_rows = _load_rows(
        PROJECT_ROOT / "data" / "mappings" / "powbase_production_validation_v1.csv",
        "entry_id",
    )
    metadata_wavelength_ids = [
        entry_id
        for entry_id, row in metadata_rows.items()
        if json.loads(row["wavelength"])["present"]
    ]
    production_wavelength_ids = [
        entry_id
        for entry_id, row in production_wavelength_rows.items()
        if row.get("source") == "POWBASE" and row.get("wavelength_angstrom", "").strip()
    ]
    discrepancy_ids = sorted(
        set(metadata_wavelength_ids) - set(production_wavelength_ids),
        key=lambda value: int(value),
    )
    wavelength_discrepancy = {
        "metadata_completeness_count": len(metadata_wavelength_ids),
        "production_known_wavelength_count": len(production_wavelength_ids),
        "metadata_wavelength_entry_ids": metadata_wavelength_ids,
        "production_known_wavelength_entry_ids": production_wavelength_ids,
        "discrepancy_entry_ids": discrepancy_ids,
        "records": [
            {
                "entry_id": entry_id,
                "source_wavelength_representation": [
                    line.strip()
                    for line in (
                        json.loads(metadata_rows[entry_id]["wavelength"]).get("records")
                        or []
                    )
                    for line in [line.get("raw_line", "")]
                ],
                "parsed_numeric_wavelength_angstrom": json.loads(
                    metadata_rows[entry_id]["wavelength"]
                ).get("values_angstrom", []),
                "production_stored_value": production_wavelength_rows[entry_id].get(
                    "wavelength_angstrom"
                ),
                "reason": (
                    "The source explicitly labels Alpha1/Alpha2 wavelength values, "
                    "but the production integration left wavelength_angstrom blank "
                    "for this legacy SR5 source format."
                ),
            }
            for entry_id in discrepancy_ids
        ],
    }
    counts = {
        "patterns_evaluated": len(TARGET_ENTRY_IDS),
        "total_source_structure_models": len(records),
        "cifs_successfully_recovered": sum(
            record["cif_validation_status"] == "passed" for record in records
        ),
        "cifs_failed": sum(
            record["cif_validation_status"] in {"failed", "passed_with_discrepancies"}
            for record in records
        ),
        "patterns_with_clear_one_to_one_source_linkage": len(
            {
                record["entry_id"]
                for record in records
                if record["proposed_linkage_status"] == "source_link_supported"
            }
        ),
        "patterns_with_ambiguous_linkage": len(
            {
                record["entry_id"]
                for record in records
                if record["proposed_linkage_status"] == "source_link_ambiguous"
            }
        ),
        "patterns_with_not_supported_linkage": len(
            {
                record["entry_id"]
                for record in records
                if record["proposed_linkage_status"] == "source_link_not_supported"
            }
        ),
    }
    return {
        "schema_version": "powbase_source_structure_recovery_v1",
        "read_only": {
            "mongodb_writes": False,
            "production_canonical_modified": False,
            "source_archives_modified": False,
            "cod_search_or_matching_performed": False,
            "git_staged_committed_or_pushed": False,
        },
        "scope": {
            "entry_ids": TARGET_ENTRY_IDS,
            "pattern_count": len(TARGET_ENTRY_IDS),
            "records_are_production_powbase_xray": True,
        },
        "method": {
            "source_only": True,
            "formula_policy": (
                "Formula-like index labels and model names are preserved as labels; "
                "no explicit formula is assigned unless a source formula tag exists."
            ),
            "missing_value_policy": (
                "Missing unit-cell angles, occupancies, or other fields remain "
                "missing. No symmetry-based or external values are supplied."
            ),
            "cif_recovery_rule": (
                "Write one CIF per model only when the source provides a complete "
                "six-parameter unit cell, a space-group value, and atom-site "
                "coordinates. Each source model is kept separate."
            ),
        },
        "counts": counts,
        "preflight": preflight,
        "wavelength_discrepancy": wavelength_discrepancy,
        "records": records,
    }


def write_outputs(
    audit: dict[str, Any],
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "powbase_source_structure_recovery_v1.csv"
    json_path = output_dir / "powbase_source_structure_recovery_v1.json"
    summary_path = output_dir / "powbase_source_structure_recovery_v1_summary.md"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in audit["records"]:
            writer.writerow(
                {
                    field: _csv_value(record.get(field))
                    for field in CSV_FIELDS
                }
            )
    json_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    counts = audit["counts"]
    lines = [
        "# PowBase source structure recovery dry-run v1",
        "",
        "Read-only, staging-only recovery for the nine production PowBase X-ray patterns "
        "with source structure-model evidence.",
        "",
        "## Scope and safeguards",
        "",
        "- Entries: " + ", ".join(TARGET_ENTRY_IDS),
        "- No MongoDB writes, production canonical changes, source archive changes, COD searches, or Git operations were performed.",
        "- Source model values were copied only when explicitly present in the cached member.",
        "- Formula-like labels were not promoted to confirmed formulas.",
        "- Entry 157 models were kept separate and were not assigned as sample phases.",
        "",
        "## Counts",
        "",
        f"- Structure-bearing PowBase patterns evaluated: {counts['patterns_evaluated']}",
        f"- Total explicit source structure models: {counts['total_source_structure_models']}",
        f"- CIFs successfully recovered and Gemmi-validated: {counts['cifs_successfully_recovered']}",
        f"- CIFs failed validation: {counts['cifs_failed']}",
        f"- Patterns with clear one-to-one source linkage: {counts['patterns_with_clear_one_to_one_source_linkage']}",
        f"- Patterns with ambiguous linkage: {counts['patterns_with_ambiguous_linkage']}",
        f"- Patterns with linkage not supported: {counts['patterns_with_not_supported_linkage']}",
        "",
        "## Linkage decisions",
        "",
    ]
    for entry_id in TARGET_ENTRY_IDS:
        rows = [row for row in audit["records"] if row["entry_id"] == entry_id]
        lines.append(
            f"- Entry {entry_id} (`{rows[0]['pattern_id']}`): "
            f"`{rows[0]['proposed_linkage_status']}`. {rows[0]['linkage_reason']}"
        )
    lines.extend(["", "## Entry 157", ""])
    for row in [record for record in audit["records"] if record["entry_id"] == "157"]:
        lines.append(
            f"- `{row['source_model_id']}`: {row['model_name']}; "
            f"space group `{row['space_group_raw']}`; "
            f"unit cell complete `{row['unit_cell_complete']}`; "
            f"atom sites `{row['atom_site_count']}`; "
            f"CIF recoverable `{row['cif_recoverable']}`; "
            f"staging CIF `{row['staging_cif_path'] or 'none'}`."
        )
    lines.extend(
        [
            "",
            "Entry 157 contains five explicit `STR(...)` models: anatase, gibbsite, "
            "hematite, quartz, and kaolinite. The source does not establish that "
            "these five models are five phases of the bauxite pattern, so no "
            "pattern-to-model relation is assigned. Models with incomplete source "
            "unit-cell angles are retained in the audit but do not receive CIFs.",
            "",
            "## Wavelength 6 versus 7",
            "",
            f"The metadata completeness audit found {audit['wavelength_discrepancy']['metadata_completeness_count']} "
            f"records with explicit wavelength metadata, while production stored "
            f"numeric wavelengths for {audit['wavelength_discrepancy']['production_known_wavelength_count']}.",
        ]
    )
    for discrepancy in audit["wavelength_discrepancy"]["records"]:
        lines.append(
            f"- Entry {discrepancy['entry_id']}: source "
            f"{discrepancy['source_wavelength_representation']}; parsed "
            f"{discrepancy['parsed_numeric_wavelength_angstrom']} Å; production "
            f"value `{discrepancy['production_stored_value'] or 'null/unknown'}`. "
            f"{discrepancy['reason']}"
        )
    lines.extend(
        [
            "",
            "## Validation",
            "",
            "Recovered CIFs are written only under "
            "`data/staging/powbase_source_structures_v1/`. Validation checks "
            "CIF parsing, cell values, normalized space-group serialization, "
            "and atom-site count. Source occupancies are preserved where present; "
            "unknown occupancies remain missing.",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, json_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--canonical-validation", type=Path, default=DEFAULT_CANONICAL_VALIDATION)
    parser.add_argument("--metadata-completeness", type=Path, default=DEFAULT_METADATA_COMPLETENESS)
    parser.add_argument("--index-manifest", type=Path, default=DEFAULT_INDEX_MANIFEST)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    audit = build_audit(
        archive_root=args.archive_root,
        canonical_validation_path=args.canonical_validation,
        metadata_completeness_path=args.metadata_completeness,
        index_manifest_path=args.index_manifest,
        staging_root=args.staging_root,
    )
    paths = write_outputs(audit, output_dir=args.output_dir)
    print(
        json.dumps(
            {"counts": audit["counts"], "outputs": [str(path) for path in paths]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
