#!/usr/bin/env python3
"""Stage group laboratory powder-XRD ASC files as byte-identical TXT copies.

The script deliberately keeps source files outside the repository untouched.
It writes a CSV manifest and a JSON summary under data/staging/lab_xrd and
copies source files only when invoked with --stage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


DEFAULT_SOURCE_ROOT = Path(r"D:\document\aiformaterials\DATA")
DEFAULT_STAGING_ROOT = Path("data/staging/lab_xrd")
DEFAULT_MAPPING_PATH = Path("data/mappings/lab_xrd_label_overrides_v1.json")
MANIFEST_NAME = "lab_xrd_manifest_v1.csv"
SUMMARY_NAME = "lab_xrd_staging_summary_v1.json"
TXT_DIR_NAME = "txt"

MANIFEST_FIELDS = [
    "sample_id",
    "measurement_id",
    "source",
    "data_origin",
    "modality",
    "contributor",
    "source_series_label",
    "source_sample_label",
    "nominal_element_ratio",
    "phase_character",
    "original_filename",
    "original_relative_path",
    "original_absolute_path",
    "original_extension",
    "staged_filename",
    "staged_relative_path",
    "staged_extension",
    "file_size_bytes",
    "sha256",
    "staged_sha256",
    "hash_status",
    "parse_status",
    "parse_warnings",
    "measurement_date",
    "radiation",
    "filter",
    "wavelength",
    "scan_axis",
    "two_theta_start",
    "two_theta_end",
    "step_size",
    "voltage_kv",
    "current_ma",
    "point_count",
    "grouping_rule",
    "grouping_confidence",
    "notes",
]

KNOWN_CONTRIBUTORS = {
    "jl": "JL",
    "lx": "LX",
    "wzq": "WZQ",
    "lihong wang": "Lihong Wang",
}

# These are intentionally narrow.  A directory is not automatically a
# scientific series merely because it contains a chemical-looking name.
EXPLICIT_SERIES_LABELS = {
    "sn-p-se": "Sn-P-Se",
}

ELEMENT_SYMBOLS = {
    "Ac",
    "Ag",
    "Al",
    "Am",
    "Ar",
    "As",
    "At",
    "Au",
    "B",
    "Ba",
    "Be",
    "Bh",
    "Bi",
    "Bk",
    "Br",
    "C",
    "Ca",
    "Cd",
    "Ce",
    "Cf",
    "Cl",
    "Cm",
    "Cn",
    "Co",
    "Cr",
    "Cs",
    "Cu",
    "Ds",
    "Dy",
    "Er",
    "Es",
    "Eu",
    "F",
    "Fe",
    "Fl",
    "Fm",
    "Fr",
    "Ga",
    "Gd",
    "Ge",
    "H",
    "He",
    "Hf",
    "Hg",
    "Ho",
    "Hs",
    "I",
    "In",
    "Ir",
    "K",
    "Kr",
    "La",
    "Li",
    "Lr",
    "Lu",
    "Lv",
    "Mc",
    "Md",
    "Mg",
    "Mn",
    "Mo",
    "Mt",
    "N",
    "Na",
    "Nb",
    "Nd",
    "Ne",
    "Nh",
    "Ni",
    "No",
    "Np",
    "O",
    "Os",
    "P",
    "Pa",
    "Pb",
    "Pd",
    "Pm",
    "Po",
    "Pr",
    "Pt",
    "Ra",
    "Rb",
    "Re",
    "Rf",
    "Rg",
    "Rh",
    "Rn",
    "Ru",
    "S",
    "Sb",
    "Sc",
    "Se",
    "Sg",
    "Si",
    "Sm",
    "Sn",
    "Sr",
    "Ta",
    "Tb",
    "Tc",
    "Te",
    "Th",
    "Ti",
    "Tl",
    "Tm",
    "Ts",
    "U",
    "V",
    "W",
    "Xe",
    "Y",
    "Yb",
    "Zn",
    "Zr",
}

HEADER_KEY_RE = re.compile(
    rb"^\*(?P<key>[A-Z0-9_]+)[ \t]*=[ \t]*(?P<value>[^\r\n]*)",
    re.MULTILINE,
)
SIMPLE_REPEAT_RE = re.compile(r"^(?P<core>.+?)(?P<separator>[-_])(?P<number>[1-9])$")
PADDED_REPEAT_RE = re.compile(
    r"^(?P<core>.+?)(?P<separator>[-_])(?P<number>00[1-9])$"
)


@dataclass(frozen=True)
class SourceFile:
    path: Path
    relative_path: str
    relative_directory: str
    stem: str
    filename: str
    normalized_sort_key: tuple[str, str]


@dataclass(frozen=True)
class RepeatCandidate:
    core: str
    separator: str
    number: int
    padded: bool


def normalize_relative_path(path: Path) -> str:
    """Return a stable, portable path representation for manifest keys."""

    return PurePosixPath(*path.parts).as_posix()


def normalized_sort_key(relative_path: str) -> tuple[str, str]:
    return (relative_path.casefold(), relative_path)


def load_label_overrides(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Mapping file must contain a JSON object: {path}")
    result: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise ValueError(f"Invalid mapping entry in {path}: {key!r}")
        result[key] = {
            str(field): str(field_value)
            for field, field_value in value.items()
            if field_value is not None
        }
    return result


def discover_source_files(source_root: Path) -> list[SourceFile]:
    files: list[SourceFile] = []
    for path in source_root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() != ".asc":
            continue
        relative = normalize_relative_path(path.relative_to(source_root))
        relative_directory = str(PurePosixPath(relative).parent)
        if relative_directory == ".":
            relative_directory = ""
        files.append(
            SourceFile(
                path=path,
                relative_path=relative,
                relative_directory=relative_directory,
                stem=path.stem,
                filename=path.name,
                normalized_sort_key=normalized_sort_key(relative),
            )
        )
    return sorted(files, key=lambda item: item.normalized_sort_key)


def parse_repeat_candidate(stem: str) -> RepeatCandidate | None:
    match = SIMPLE_REPEAT_RE.fullmatch(stem)
    if match:
        return RepeatCandidate(
            core=match.group("core"),
            separator=match.group("separator"),
            number=int(match.group("number")),
            padded=False,
        )
    match = PADDED_REPEAT_RE.fullmatch(stem)
    if match:
        return RepeatCandidate(
            core=match.group("core"),
            separator=match.group("separator"),
            number=int(match.group("number")),
            padded=True,
        )
    return None


def build_group_assignments(
    source_files: Iterable[SourceFile],
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return sample keys, source labels, and grouping notes by relative path."""

    files = list(source_files)
    by_directory: dict[str, list[SourceFile]] = defaultdict(list)
    for source_file in files:
        by_directory[source_file.relative_directory.casefold()].append(source_file)

    sample_keys: dict[str, str] = {}
    source_labels: dict[str, str] = {}
    grouping_notes: dict[str, str] = {}

    for directory_key, directory_files in by_directory.items():
        exact_stems = {item.stem.casefold(): item for item in directory_files}
        candidates: dict[str, list[tuple[SourceFile, RepeatCandidate]]] = defaultdict(
            list
        )
        for item in directory_files:
            candidate = parse_repeat_candidate(item.stem)
            if candidate is not None:
                group_key = f"{candidate.core.casefold()}\0{candidate.separator}"
                candidates[group_key].append((item, candidate))

        repeat_groups: dict[str, set[str]] = {}
        repeat_group_cores: dict[str, str] = {}
        for candidate_key, members in candidates.items():
            first_candidate = members[0][1]
            core_key = first_candidate.core.casefold()
            separator = first_candidate.separator
            base_exists = core_key in exact_stems
            simple_members = [member for member in members if not member[1].padded]
            padded_members = [member for member in members if member[1].padded]
            suffix_numbers = sorted(member[1].number for member in members)
            directory_name = (
                PurePosixPath(directory_files[0].relative_directory).name.casefold()
                if directory_files[0].relative_directory
                else ""
            )
            directory_context_evidence = any(
                directory_name == member[0].stem.casefold() for member in members
            )
            formula_context_evidence = bool(infer_leading_formula(first_candidate.core))

            # A one-off "_001" is retained as part of its original label.  It
            # becomes a repeat only with a sibling base or repeat sequence.
            has_strong_simple_evidence = (
                base_exists
                or directory_context_evidence
                or (
                    len(simple_members) >= 2
                    and max(suffix_numbers, default=0) <= 3
                )
                or (
                    formula_context_evidence
                    and len(simple_members) >= 2
                    and suffix_numbers == list(range(1, max(suffix_numbers) + 1))
                    and max(suffix_numbers, default=0) <= 9
                )
            )
            has_strong_padded_evidence = (
                base_exists
                or directory_context_evidence
                or (
                    len(padded_members) >= 2
                    and max(suffix_numbers, default=0) <= 3
                )
            )
            if not (
                (separator == "-" and has_strong_simple_evidence)
                or (separator == "_" and (has_strong_simple_evidence or has_strong_padded_evidence))
            ):
                continue

            group_paths = {member[0].relative_path for member in members}
            if base_exists:
                group_paths.add(exact_stems[core_key].relative_path)
            repeat_groups[candidate_key] = group_paths
            repeat_group_cores[candidate_key] = first_candidate.core

        for item in directory_files:
            candidate = parse_repeat_candidate(item.stem)
            candidate_key = None
            if candidate is not None:
                candidate_key = f"{candidate.core.casefold()}\0{candidate.separator}"

            matched_repeat_key = candidate_key
            if matched_repeat_key is None:
                for repeat_key, group_paths in repeat_groups.items():
                    if item.relative_path in group_paths:
                        matched_repeat_key = repeat_key
                        break

            if matched_repeat_key in repeat_groups:
                group_paths = repeat_groups[matched_repeat_key]
                core = repeat_group_cores[matched_repeat_key]
                label = core
                sample_key = f"{directory_key}\0{core.casefold()}"
                sample_keys[item.relative_path] = sample_key
                source_labels[item.relative_path] = label
                grouping_notes[item.relative_path] = (
                    "repeat_suffix_removed"
                    if item.stem.casefold() != label.casefold()
                    else "repeat_group_base"
                )
                continue

            sample_key = f"{directory_key}\0{item.stem.casefold()}"
            sample_keys[item.relative_path] = sample_key
            source_labels[item.relative_path] = item.stem
            if candidate is not None:
                grouping_notes[item.relative_path] = (
                    "repeat_suffix_candidate_without_sibling_evidence; "
                    "retained_as_separate_sample"
                )
            else:
                grouping_notes[item.relative_path] = "single_file_sample"

    return sample_keys, source_labels, grouping_notes


def contributor_for(relative_path: str) -> str:
    first_component = relative_path.split("/", 1)[0]
    return KNOWN_CONTRIBUTORS.get(first_component.casefold(), "")


def series_for(relative_path: str) -> str:
    parts = relative_path.split("/")
    for component in parts[:-1]:
        label = EXPLICIT_SERIES_LABELS.get(component.casefold())
        if label:
            return label
        if "series" in component.casefold():
            return component
    return ""


def parse_formula_token(token: str) -> bool:
    """Validate a simple element-count formula without interpreting phase."""

    position = 0
    elements = 0
    while position < len(token):
        match = re.match(r"[A-Z][a-z]?", token[position:])
        if match is None:
            return False
        symbol = match.group(0)
        if symbol not in ELEMENT_SYMBOLS:
            return False
        elements += 1
        position += len(symbol)
        count_match = re.match(r"\d+", token[position:])
        if count_match:
            position += len(count_match.group(0))
    return elements >= 2


def infer_leading_formula(stem: str) -> str:
    match = re.match(r"(?P<token>[A-Za-z][A-Za-z0-9]*)", stem)
    if match is None:
        return ""
    token = match.group("token")
    next_character = stem[len(token) : len(token) + 1]
    if next_character in {".", "("}:
        return ""
    return token if parse_formula_token(token) else ""


def infer_nominal_ratio(
    source_sample_label: str,
    stem: str,
    overrides: dict[str, dict[str, str]],
) -> tuple[str, str]:
    override = overrides.get(source_sample_label)
    if override and override.get("nominal_element_ratio"):
        return override["nominal_element_ratio"], "curated_nominal_element_ratio_mapping"

    if stem.casefold().find("co3s4") >= 0:
        return "Co3S4", "explicit_filename_tag_co3s4"

    formula = infer_leading_formula(stem)
    if formula:
        return formula, "leading_formula_like_filename_token"
    return "", ""


def extract_header_values(path: Path) -> tuple[dict[str, str], str, list[str]]:
    """Read only ASC header bytes and return parsed values plus status."""

    try:
        with path.open("rb") as handle:
            prefix = handle.read(64 * 1024)
    except OSError as exc:
        return {}, "unparsed", [f"read_error:{exc}"]

    try:
        text = prefix.decode("ascii")
    except UnicodeDecodeError:
        text = prefix.decode("ascii", errors="replace")

    raw_values: dict[str, str] = {}
    for match in HEADER_KEY_RE.finditer(prefix):
        key = match.group("key").decode("ascii", errors="replace")
        value = match.group("value").decode("ascii", errors="replace").strip()
        raw_values.setdefault(key, value)

    required_keys = [
        "DATE",
        "SCAN_AXIS",
        "WAVE_LENGTH1",
        "START",
        "STOP",
        "STEP",
        "KV",
        "MA",
        "COUNT",
    ]
    warnings: list[str] = []
    if b"*TYPE" not in prefix or b"*BEGIN" not in prefix:
        return raw_values, "unparsed", ["missing_asc_header_markers"]

    missing = [key for key in required_keys if not raw_values.get(key)]
    if missing:
        warnings.append("missing_header_fields:" + ",".join(missing))

    invalid_numeric: list[str] = []
    for key in ["WAVE_LENGTH1", "START", "STOP", "STEP", "KV", "MA", "COUNT"]:
        value = raw_values.get(key)
        if value:
            candidate = value.split(",", 1)[0].strip()
            try:
                float(candidate)
            except ValueError:
                invalid_numeric.append(key)
    if invalid_numeric:
        warnings.append("invalid_numeric_fields:" + ",".join(invalid_numeric))

    if missing or invalid_numeric:
        status = "partial"
    else:
        status = "ok"
    return raw_values, status, warnings


def metadata_from_headers(
    headers: dict[str, str], status: str, warnings: list[str]
) -> dict[str, str]:
    return {
        "parse_status": status,
        "parse_warnings": "; ".join(warnings),
        "measurement_date": headers.get("DATE", ""),
        "radiation": headers.get("XRAY_CHAR", ""),
        "filter": headers.get("FILTER", ""),
        "wavelength": headers.get("WAVE_LENGTH1", ""),
        "scan_axis": headers.get("SCAN_AXIS", ""),
        "two_theta_start": headers.get("START", ""),
        "two_theta_end": headers.get("STOP", ""),
        "step_size": headers.get("STEP", ""),
        "voltage_kv": headers.get("KV", ""),
        "current_ma": headers.get("MA", ""),
        "point_count": headers.get("COUNT", ""),
    }


def sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def load_previous_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            row.get("original_relative_path", ""): dict(row)
            for row in reader
            if row.get("original_relative_path")
        }


def numeric_id(prefix: str, value: int) -> str:
    return f"{prefix}_{value:06d}"


def id_number(identifier: str, prefix: str) -> int:
    match = re.fullmatch(re.escape(prefix) + r"_(\d{6})", identifier or "")
    return int(match.group(1)) if match else 0


def assign_ids(
    source_files: list[SourceFile],
    sample_keys: dict[str, str],
    previous_rows: dict[str, dict[str, str]],
) -> tuple[dict[str, str], dict[str, str]]:
    sample_ids: dict[str, str] = {}
    measurement_ids: dict[str, str] = {}
    next_sample = max(
        [id_number(row.get("sample_id", ""), "LAB_SAM") for row in previous_rows.values()]
        or [0]
    ) + 1
    next_measurement = max(
        [
            id_number(row.get("measurement_id", ""), "LAB_MEAS")
            for row in previous_rows.values()
        ]
        or [0]
    ) + 1

    groups: dict[str, list[SourceFile]] = defaultdict(list)
    for source_file in source_files:
        groups[sample_keys[source_file.relative_path]].append(source_file)

    for group_key, members in sorted(
        groups.items(),
        key=lambda item: min(member.normalized_sort_key for member in item[1]),
    ):
        prior_ids = {
            previous_rows[member.relative_path].get("sample_id", "")
            for member in members
            if member.relative_path in previous_rows
        }
        prior_ids.discard("")
        if prior_ids:
            available_prior_ids = sorted(
                prior_ids,
                key=lambda value: id_number(value, "LAB_SAM"),
            )
            sample_id = next(
                (
                    value
                    for value in available_prior_ids
                    if value not in sample_ids.values()
                ),
                "",
            )
            if not sample_id:
                sample_id = numeric_id("LAB_SAM", next_sample)
                next_sample += 1
        else:
            sample_id = numeric_id("LAB_SAM", next_sample)
            next_sample += 1
        for member in members:
            sample_ids[member.relative_path] = sample_id

    for source_file in source_files:
        previous_measurement = previous_rows.get(source_file.relative_path, {}).get(
            "measurement_id", ""
        )
        if previous_measurement:
            measurement_ids[source_file.relative_path] = previous_measurement
        else:
            measurement_ids[source_file.relative_path] = numeric_id(
                "LAB_MEAS", next_measurement
            )
            next_measurement += 1
    return sample_ids, measurement_ids


def build_rows(
    source_files: list[SourceFile],
    source_root: Path,
    staging_root: Path,
    overrides: dict[str, dict[str, str]],
    previous_rows: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    sample_keys, source_labels, grouping_notes = build_group_assignments(source_files)
    sample_ids, measurement_ids = assign_ids(source_files, sample_keys, previous_rows)

    rows: list[dict[str, str]] = []
    for source_file in source_files:
        relative_path = source_file.relative_path
        source_label = source_labels[relative_path]
        nominal_ratio, ratio_note = infer_nominal_ratio(
            source_label, source_file.stem, overrides
        )
        headers, parse_status, parse_warnings = extract_header_values(source_file.path)
        metadata = metadata_from_headers(headers, parse_status, parse_warnings)
        sample_id = sample_ids[relative_path]
        measurement_id = measurement_ids[relative_path]
        staged_filename = f"{sample_id}_{measurement_id}.txt"
        staged_relative_path = f"{TXT_DIR_NAME}/{staged_filename}"

        try:
            sha256, file_size = sha256_and_size(source_file.path)
        except OSError as exc:
            sha256, file_size = "", 0
            metadata["parse_warnings"] = (
                f"{metadata['parse_warnings']}; source_hash_error:{exc}".strip("; ")
            )

        notes = [grouping_notes[relative_path]]
        if ratio_note:
            notes.append(ratio_note)
        if not contributor_for(relative_path):
            notes.append("unknown_contributor_root")
        if not series_for(relative_path):
            notes.append("source_series_label_not_inferred")
        previous = previous_rows.get(relative_path, {})
        if previous.get("staged_filename") and previous["staged_filename"] != staged_filename:
            notes.append("previous_staged_filename_not_reused_because_id_pair_changed")

        row = {
            "sample_id": sample_id,
            "measurement_id": measurement_id,
            "source": "lab",
            "data_origin": "experimental",
            "modality": "powder_xrd",
            "contributor": contributor_for(relative_path),
            "source_series_label": series_for(relative_path),
            "source_sample_label": source_label,
            "nominal_element_ratio": nominal_ratio,
            "phase_character": "unknown",
            "original_filename": source_file.filename,
            "original_relative_path": relative_path,
            "original_absolute_path": str(source_file.path.resolve()),
            "original_extension": ".asc",
            "staged_filename": staged_filename,
            "staged_relative_path": staged_relative_path,
            "staged_extension": ".txt",
            "file_size_bytes": str(file_size),
            "sha256": sha256,
            "staged_sha256": "",
            "hash_status": "not_staged",
            "grouping_rule": (
                "same_directory_core_basename_repeat_suffix"
                if grouping_notes[relative_path] in {
                    "repeat_suffix_removed",
                    "repeat_group_base",
                }
                else (
                    "same_directory_repeat_candidate_without_evidence"
                    if "candidate_without_sibling" in grouping_notes[relative_path]
                    else "same_directory_single_file"
                )
            ),
            "grouping_confidence": (
                "high"
                if grouping_notes[relative_path] in {
                    "repeat_suffix_removed",
                    "repeat_group_base",
                }
                else (
                    "ambiguous"
                    if "candidate_without_sibling" in grouping_notes[relative_path]
                    else "medium"
                )
            ),
            "notes": "; ".join(notes),
            **metadata,
        }
        rows.append(row)
    return rows


def check_duplicate_values(rows: list[dict[str, str]], field: str) -> list[str]:
    values = Counter(row.get(field, "") for row in rows if row.get(field, ""))
    return sorted(value for value, count in values.items() if count > 1)


def stage_rows(
    rows: list[dict[str, str]],
    source_root: Path,
    staging_root: Path,
    do_stage: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    conflicts: list[dict[str, str]] = []
    txt_root = staging_root / TXT_DIR_NAME
    if do_stage:
        txt_root.mkdir(parents=True, exist_ok=True)

    for row in rows:
        source_path = source_root / Path(*row["original_relative_path"].split("/"))
        target_path = staging_root / Path(*row["staged_relative_path"].split("/"))
        expected_hash = row["sha256"]
        if not source_path.exists():
            conflicts.append(
                {
                    "type": "missing_original_asc",
                    "original_relative_path": row["original_relative_path"],
                    "message": "Original ASC disappeared after discovery.",
                }
            )
            row["hash_status"] = "conflict"
            continue

        if target_path.exists():
            if target_path.is_dir():
                conflicts.append(
                    {
                        "type": "staged_path_is_directory",
                        "staged_relative_path": row["staged_relative_path"],
                        "message": "Expected staged file path is a directory.",
                    }
                )
                row["hash_status"] = "conflict"
                continue
            try:
                staged_hash, _ = sha256_and_size(target_path)
            except OSError as exc:
                conflicts.append(
                    {
                        "type": "staged_hash_error",
                        "staged_relative_path": row["staged_relative_path"],
                        "message": str(exc),
                    }
                )
                row["hash_status"] = "conflict"
                continue
            if staged_hash != expected_hash:
                conflicts.append(
                    {
                        "type": "staged_hash_mismatch",
                        "original_relative_path": row["original_relative_path"],
                        "staged_relative_path": row["staged_relative_path"],
                        "expected_sha256": expected_hash,
                        "actual_sha256": staged_hash,
                        "message": "Existing staged TXT differs; it was not overwritten.",
                    }
                )
                row["staged_sha256"] = staged_hash
                row["hash_status"] = "mismatch"
                continue
            row["staged_sha256"] = staged_hash
            row["hash_status"] = "verified"
            continue

        if not do_stage:
            row["hash_status"] = "not_staged"
            continue

        try:
            shutil.copy2(source_path, target_path)
            staged_hash, _ = sha256_and_size(target_path)
        except OSError as exc:
            conflicts.append(
                {
                    "type": "staging_copy_error",
                    "original_relative_path": row["original_relative_path"],
                    "staged_relative_path": row["staged_relative_path"],
                    "message": str(exc),
                }
            )
            row["hash_status"] = "conflict"
            continue
        row["staged_sha256"] = staged_hash
        if staged_hash != expected_hash:
            conflicts.append(
                {
                    "type": "staged_hash_mismatch_after_copy",
                    "original_relative_path": row["original_relative_path"],
                    "staged_relative_path": row["staged_relative_path"],
                    "expected_sha256": expected_hash,
                    "actual_sha256": staged_hash,
                    "message": "Copied TXT failed byte-level hash verification.",
                }
            )
            row["hash_status"] = "mismatch"
        else:
            row["hash_status"] = "verified"
    return rows, conflicts


def prune_stale_staged_files(
    previous_rows: dict[str, dict[str, str]],
    rows: list[dict[str, str]],
    staging_root: Path,
) -> list[dict[str, str]]:
    """Remove only verified files from the immediately previous manifest.

    This is opt-in and is intended for reconciling a manifest after a
    grouping-rule correction.  It never scans or deletes arbitrary files.
    """

    current_paths = {row["staged_relative_path"] for row in rows}
    txt_root = (staging_root / TXT_DIR_NAME).resolve()
    conflicts: list[dict[str, str]] = []
    for previous_row in previous_rows.values():
        relative_path = previous_row.get("staged_relative_path", "")
        if not relative_path or relative_path in current_paths:
            continue
        target_path = staging_root / Path(*relative_path.split("/"))
        try:
            resolved_target = target_path.resolve()
            if resolved_target.parent != txt_root:
                conflicts.append(
                    {
                        "type": "stale_path_outside_txt_root",
                        "staged_relative_path": relative_path,
                        "message": "Stale path was not pruned because it is outside txt/.",
                    }
                )
                continue
            if not resolved_target.exists():
                continue
            expected_hash = previous_row.get("staged_sha256") or previous_row.get(
                "sha256", ""
            )
            actual_hash, _ = sha256_and_size(resolved_target)
            if not expected_hash or actual_hash != expected_hash:
                conflicts.append(
                    {
                        "type": "stale_hash_mismatch",
                        "staged_relative_path": relative_path,
                        "message": "Stale file was not pruned because its previous hash was not verified.",
                    }
                )
                continue
            resolved_target.unlink()
        except OSError as exc:
            conflicts.append(
                {
                    "type": "stale_prune_error",
                    "staged_relative_path": relative_path,
                    "message": str(exc),
                }
            )
    return conflicts


def build_summary(
    rows: list[dict[str, str]],
    source_root: Path,
    staging_root: Path,
    conflicts: list[dict[str, str]],
    dry_run: bool,
) -> dict[str, object]:
    sample_measurements: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        sample_measurements[row["sample_id"]].append(row)

    multi_measurements = []
    for sample_id, sample_rows in sorted(sample_measurements.items()):
        if len(sample_rows) <= 1:
            continue
        first = sample_rows[0]
        multi_measurements.append(
            {
                "sample_id": sample_id,
                "measurement_count": len(sample_rows),
                "source_sample_label": first["source_sample_label"],
                "contributor": first["contributor"],
                "source_series_label": first["source_series_label"],
                "measurements": [
                    {
                        "measurement_id": item["measurement_id"],
                        "original_relative_path": item["original_relative_path"],
                        "staged_filename": item["staged_filename"],
                    }
                    for item in sorted(
                        sample_rows, key=lambda item: normalized_sort_key(item["original_relative_path"])
                    )
                ],
            }
        )

    examples = [
        {
            "original_asc": row["original_relative_path"],
            "sample_id": row["sample_id"],
            "measurement_id": row["measurement_id"],
            "source_sample_label": row["source_sample_label"],
            "nominal_element_ratio": row["nominal_element_ratio"],
            "staged_txt": row["staged_relative_path"],
        }
        for row in rows[:10]
    ]

    duplicate_measurements = check_duplicate_values(rows, "measurement_id")
    duplicate_staged = check_duplicate_values(rows, "staged_filename")
    hash_mismatches = [
        row["original_relative_path"]
        for row in rows
        if row.get("hash_status") == "mismatch"
    ]
    hash_verified = sum(row.get("hash_status") == "verified" for row in rows)
    parse_counts = Counter(row["parse_status"] for row in rows)

    summary: dict[str, object] = {
        "schema_version": "lab_xrd_staging_summary_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if dry_run else "stage",
        "source_root": str(source_root.resolve()),
        "staging_root": str(staging_root.resolve()),
        "original_asc_files": len(rows),
        "manifest_records": len(rows),
        "staged_txt_files": sum(row.get("hash_status") == "verified" for row in rows),
        "unique_sample_ids": len({row["sample_id"] for row in rows}),
        "unique_measurement_ids": len({row["measurement_id"] for row in rows}),
        "samples_with_repeated_measurements": len(multi_measurements),
        "ambiguous_grouping_count": sum(
            row.get("grouping_confidence") == "ambiguous" for row in rows
        ),
        "unknown_nominal_ratio_count": sum(
            not row.get("nominal_element_ratio") for row in rows
        ),
        "unknown_contributor_count": sum(not row.get("contributor") for row in rows),
        "unknown_series_count": sum(not row.get("source_series_label") for row in rows),
        "contributors": dict(sorted(Counter(row["contributor"] for row in rows if row["contributor"]).items())),
        "series_labels": dict(
            sorted(
                Counter(
                    row["source_series_label"]
                    for row in rows
                    if row["source_series_label"]
                ).items()
            )
        ),
        "nominal_element_ratios": dict(
            sorted(
                Counter(
                    row["nominal_element_ratio"]
                    for row in rows
                    if row["nominal_element_ratio"]
                ).items()
            )
        ),
        "phase_character_counts": dict(
            sorted(Counter(row["phase_character"] for row in rows).items())
        ),
        "parse_status_counts": {
            "ok": parse_counts.get("ok", 0),
            "partial": parse_counts.get("partial", 0),
            "unparsed": parse_counts.get("unparsed", 0),
        },
        "hash_verified": hash_verified,
        "hash_mismatch": len(hash_mismatches),
        "missing_original_asc_files": sum(
            conflict["type"] == "missing_original_asc" for conflict in conflicts
        ),
        "missing_staged_txt_files": (
            0
            if dry_run
            else sum(row.get("hash_status") != "verified" for row in rows)
        ),
        "duplicate_measurement_ids": duplicate_measurements,
        "duplicate_staged_filenames": duplicate_staged,
        "hash_mismatch_paths": hash_mismatches,
        "conflicts": conflicts,
        "examples": examples,
        "multi_measurement_samples": multi_measurements,
    }
    return summary


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=MANIFEST_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def print_report(summary: dict[str, object]) -> None:
    print("CrystalDB laboratory powder-XRD staging")
    print(f"Mode: {summary['mode']}")
    print(f"Original ASC files: {summary['original_asc_files']}")
    print(f"Manifest records: {summary['manifest_records']}")
    print(f"Staged TXT files: {summary['staged_txt_files']}")
    print(f"Unique samples: {summary['unique_sample_ids']}")
    print(f"Unique measurements: {summary['unique_measurement_ids']}")
    print(
        "Samples with repeated measurements: "
        f"{summary['samples_with_repeated_measurements']}"
    )
    print(f"Known nominal ratios: {sum(summary['nominal_element_ratios'].values())}")
    print(f"Unknown nominal ratios: {summary['unknown_nominal_ratio_count']}")
    print(f"Contributors: {summary['contributors']}")
    print(f"Series labels: {summary['series_labels']}")
    print(f"Hash verified: {summary['hash_verified']}")
    print(f"Hash mismatch: {summary['hash_mismatch']}")
    print(f"Ambiguous grouping: {summary['ambiguous_grouping_count']}")
    parse_counts = summary["parse_status_counts"]
    print(f"Parse OK: {parse_counts.get('ok', 0)}")
    print(f"Parse partial: {parse_counts.get('partial', 0)}")
    print(f"Parse failed: {parse_counts.get('unparsed', 0)}")
    print()
    print("10 examples:")
    for example in summary["examples"]:
        print(
            f"{example['original_asc']} -> {example['sample_id']} -> "
            f"{example['measurement_id']} -> {example['source_sample_label']} -> "
            f"{example['nominal_element_ratio'] or '<unknown>'} -> "
            f"{example['staged_txt']}"
        )
    print()
    print("All multi-measurement samples:")
    for sample in summary["multi_measurement_samples"]:
        paths = ", ".join(
            item["original_relative_path"] for item in sample["measurements"]
        )
        print(
            f"{sample['sample_id']} ({sample['measurement_count']}): "
            f"{sample['source_sample_label']} -> {paths}"
        )
    if not summary["multi_measurement_samples"]:
        print("<none>")
    print()
    conflicts = summary["conflicts"]
    print(f"Conflicts / errors: {len(conflicts)}")
    for conflict in conflicts:
        print(json.dumps(conflict, ensure_ascii=False, sort_keys=True))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or stage laboratory powder-XRD ASC files."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help=f"Original ASC root (default: {DEFAULT_SOURCE_ROOT})",
    )
    parser.add_argument(
        "--staging-root",
        type=Path,
        default=DEFAULT_STAGING_ROOT,
        help=f"Staging root relative to repository (default: {DEFAULT_STAGING_ROOT})",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING_PATH,
        help=f"Curated mapping JSON (default: {DEFAULT_MAPPING_PATH})",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Write manifest and summary without copying TXT files.",
    )
    mode.add_argument(
        "--stage",
        action="store_true",
        help="Copy ASC bytes to TXT files and verify SHA256.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore an existing manifest when initializing a new staging run.",
    )
    parser.add_argument(
        "--prune-stale",
        action="store_true",
        help="Remove verified staged TXT files no longer referenced by the new manifest.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    source_root = args.source_root.resolve()
    staging_root = args.staging_root
    if not staging_root.is_absolute():
        staging_root = (Path(__file__).resolve().parents[1] / staging_root).resolve()
    mapping_path = args.mapping
    if not mapping_path.is_absolute():
        mapping_path = (Path(__file__).resolve().parents[1] / mapping_path).resolve()

    if not source_root.exists():
        print(f"ERROR: source root does not exist: {source_root}", file=sys.stderr)
        return 2

    dry_run = not args.stage
    try:
        overrides = load_label_overrides(mapping_path)
        source_files = discover_source_files(source_root)
        manifest_path = staging_root / MANIFEST_NAME
        previous_rows = {} if args.fresh else load_previous_manifest(manifest_path)
        rows = build_rows(
            source_files,
            source_root,
            staging_root,
            overrides,
            previous_rows,
        )
        prune_conflicts = (
            prune_stale_staged_files(previous_rows, rows, staging_root)
            if args.prune_stale and args.stage
            else []
        )
        rows, stage_conflicts = stage_rows(
            rows,
            source_root,
            staging_root,
            do_stage=not dry_run,
        )
        conflicts = prune_conflicts + stage_conflicts

        duplicate_measurements = check_duplicate_values(rows, "measurement_id")
        duplicate_staged = check_duplicate_values(rows, "staged_filename")
        for value in duplicate_measurements:
            conflicts.append(
                {
                    "type": "duplicate_measurement_id",
                    "value": value,
                    "message": "Measurement IDs must be unique.",
                }
            )
        for value in duplicate_staged:
            conflicts.append(
                {
                    "type": "duplicate_staged_filename",
                    "value": value,
                    "message": "Staged filenames must be unique.",
                }
            )

        summary = build_summary(
            rows,
            source_root,
            staging_root,
            conflicts,
            dry_run=dry_run,
        )
        write_manifest(manifest_path, rows)
        write_summary(staging_root / SUMMARY_NAME, summary)
        print_report(summary)
        print()
        print(f"Manifest: {manifest_path}")
        print(f"Summary: {staging_root / SUMMARY_NAME}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    return 1 if conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
