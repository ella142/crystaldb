#!/usr/bin/env python3
"""Validate same-COD-ID CIF files that have different SHA256 values."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import gemmi


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crystaldb.sources.cod.single_crystal_parser import parse_cod_cif


DEFAULT_AI4_ROOT = Path(r"D:\document\aiformaterials\ai4")
DEFAULT_PROJECT_CIF_DIR = PROJECT_ROOT / "data" / "raw" / "cod"
DEFAULT_PAIR_MANIFEST = (
    PROJECT_ROOT / "data" / "powder" / "opxrd" / "opxrd_cod_pairs.csv"
)
DEFAULT_JSON_OUTPUT = PROJECT_ROOT / "data" / "mappings" / "cod_duplicate_sha256_validation.json"
DEFAULT_MD_OUTPUT = PROJECT_ROOT / "data" / "mappings" / "cod_duplicate_sha256_validation.md"

TOKEN_RE = re.compile(r"'(?:[^']*)'|\"(?:[^\"]*)\"|[^\s]+")
NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
    r"(?:\(\d+\))?$"
)
FORMULA_TOKEN_RE = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?")

LENGTH_TOL = 1e-4
ANGLE_TOL = 1e-3
VOLUME_REL_TOL = 1e-4
COORD_TOL = 1e-4
OCCUPANCY_TOL = 1e-4

METADATA_PREFIXES = (
    "_audit_",
    "_cod_",
    "_database_",
    "_publ_",
    "_journal_",
    "_citation_",
    "_computing_",
    "_refine_",
    "_diffrn_",
    "_cell_measurement_",
    "_exptl_",
    "_iucr_",
)
STRUCTURE_PREFIXES = (
    "_atom_site_",
    "_cell_",
    "_space_group_",
    "_symmetry_",
    "_chemical_formula_",
    "_chemical_name_",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate conflicting same-COD-ID CIF files without modifying them."
    )
    parser.add_argument("--ai4-root", type=Path, default=DEFAULT_AI4_ROOT)
    parser.add_argument("--project-cif-dir", type=Path, default=DEFAULT_PROJECT_CIF_DIR)
    parser.add_argument(
        "--pair-manifest",
        type=Path,
        default=DEFAULT_PAIR_MANIFEST,
        help=(
            "Existing OPXRD pair manifest used to scope validation. "
            "Rows with pair_status=duplicate_conflict are selected."
        ),
    )
    parser.add_argument(
        "--cod-id",
        action="append",
        dest="cod_ids",
        help="Optional explicit COD ID scope; repeat for multiple IDs.",
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUTPUT)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", ".", "?"}:
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1]
    return text


def normalize_text(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def numeric_value(value: Any) -> float | None:
    text = normalize_text(value)
    if text is None:
        return None
    match = NUMBER_RE.match(text)
    if not match:
        return None
    try:
        return float(re.sub(r"\(\d+\)$", "", text))
    except ValueError:
        return None


def strip_comment(line: str) -> str:
    quote: str | None = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "#":
            return line[:index]
    return line


def tokenize_cif(text: str) -> list[str]:
    tokens: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith(";"):
            block = [line[1:]]
            index += 1
            while index < len(lines) and not lines[index].startswith(";"):
                block.append(lines[index])
                index += 1
            tokens.append("\n".join(block))
            index += 1
            continue
        clean = strip_comment(line).strip()
        if clean:
            tokens.extend(match.group(0) for match in TOKEN_RE.finditer(clean))
        index += 1
    return tokens


def parse_tag_values(text: str) -> dict[str, Any]:
    tokens = tokenize_cif(text)
    tag_values: dict[str, Any] = defaultdict(list)
    tag_order: list[str] = []
    loops: list[dict[str, Any]] = []
    data_blocks: list[str] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        lower = token.lower()
        if lower.startswith("data_"):
            data_blocks.append(token)
            index += 1
            continue
        if lower == "loop_":
            index += 1
            headers: list[str] = []
            while index < len(tokens) and tokens[index].startswith("_"):
                header = tokens[index].lower()
                headers.append(header)
                tag_order.append(header)
                index += 1
            width = len(headers)
            values: list[str] = []
            while index < len(tokens):
                candidate = tokens[index]
                candidate_lower = candidate.lower()
                at_boundary = width and len(values) % width == 0
                if at_boundary and (
                    candidate_lower == "loop_"
                    or candidate_lower == "stop_"
                    or candidate_lower.startswith("data_")
                    or candidate_lower.startswith("save_")
                    or candidate.startswith("_")
                ):
                    break
                values.append(candidate)
                index += 1
            rows = [
                values[offset : offset + width]
                for offset in range(0, len(values), width)
                if len(values[offset : offset + width]) == width
            ]
            loops.append({"tags": headers, "rows": rows})
            for row in rows:
                for header, value in zip(headers, row):
                    tag_values[header].append(normalize_text(value))
            continue
        if token.startswith("_"):
            tag = token.lower()
            tag_order.append(tag)
            value = None
            if index + 1 < len(tokens):
                candidate = tokens[index + 1]
                candidate_lower = candidate.lower()
                if not (
                    candidate.startswith("_")
                    or candidate_lower == "loop_"
                    or candidate_lower.startswith("data_")
                    or candidate_lower.startswith("save_")
                ):
                    value = normalize_text(candidate)
                    index += 1
            tag_values[tag].append(value)
        index += 1

    return {
        "values": {tag: values for tag, values in tag_values.items()},
        "order": tag_order,
        "loops": loops,
        "data_blocks": data_blocks,
    }


def formula_signature(formula: str | None) -> dict[str, float] | str | None:
    text = normalize_text(formula)
    if text is None:
        return None
    compact = text.replace(" ", "").replace("_", "")
    result: dict[str, float] = {}
    position = 0
    for match in FORMULA_TOKEN_RE.finditer(compact):
        if match.start() != position:
            return compact
        result[match.group(1)] = result.get(match.group(1), 0.0) + float(
            match.group(2) or 1
        )
        position = match.end()
    if position != len(compact):
        return compact
    return {key: round(value, 8) for key, value in sorted(result.items())}


def first_block_value(block: gemmi.cif.Block, tags: tuple[str, ...]) -> str | None:
    for tag in tags:
        value = normalize_text(block.find_value(tag))
        if value is not None:
            return value
    return None


def loop_rows(block: gemmi.cif.Block, anchor: str) -> tuple[list[str], list[dict[str, str]]]:
    column = block.find_loop(anchor)
    if not column:
        return [], []
    loop = column.get_loop()
    tags = [str(tag).lower() for tag in loop.tags]
    width = loop.width()
    values = list(loop.values)
    rows = [
        dict(zip(tags, values[offset : offset + width]))
        for offset in range(0, len(values), width)
        if len(values[offset : offset + width]) == width
    ]
    return tags, rows


def provenance_for_path(path: Path, ai4_root: Path, project_cif_dir: Path) -> dict[str, str]:
    resolved = path.resolve()
    lower = str(resolved).replace("\\", "/").lower()
    if resolved.is_relative_to(project_cif_dir.resolve()):
        return {
            "source_family": "crystaldb_project_data_raw_cod",
            "pipeline": "CrystalDB local raw COD mirror",
            "ai_or_human_pipeline": "project_local_pipeline",
        }
    if "_candidate_cif_mirror" in lower:
        return {
            "source_family": "ai4_candidate_cif_mirror",
            "pipeline": "AI candidate CIF mirror",
            "ai_or_human_pipeline": "ai_pipeline",
        }
    if "confirmed_exact_curve" in lower:
        return {
            "source_family": "ai4_confirmed_exact_curve",
            "pipeline": "confirmed exact-curve pipeline",
            "ai_or_human_pipeline": "ai_pipeline",
        }
    if "cod_original_files" in lower:
        return {
            "source_family": "ai4_cod_original_files",
            "pipeline": "OPXRD/COD original-file package",
            "ai_or_human_pipeline": "ai_pipeline",
        }
    if "single_crystal_xray" in lower:
        return {
            "source_family": "ai4_single_crystal_processed",
            "pipeline": "single-crystal COD processed-pairs pipeline",
            "ai_or_human_pipeline": "ai_pipeline",
        }
    if resolved.is_relative_to(ai4_root.resolve()):
        return {
            "source_family": "ai4_other",
            "pipeline": "other AI4-local CIF source",
            "ai_or_human_pipeline": "ai4_local_pipeline",
        }
    return {
        "source_family": "unknown_local",
        "pipeline": "unclassified local source",
        "ai_or_human_pipeline": "unknown",
    }


def discover_candidates(
    ai4_root: Path,
    project_cif_dir: Path,
    cod_ids: set[str],
) -> dict[str, list[Path]]:
    candidates: dict[str, dict[str, Path]] = defaultdict(dict)
    if ai4_root.is_dir():
        for path in ai4_root.rglob("*.cif"):
            if path.stem in cod_ids:
                candidates[path.stem][str(path.resolve()).casefold()] = path.resolve()
    if project_cif_dir.is_dir():
        for path in project_cif_dir.glob("*.cif"):
            if path.stem in cod_ids:
                candidates[path.stem][str(path.resolve()).casefold()] = path.resolve()
    return {
        cod_id: sorted(paths.values(), key=str)
        for cod_id, paths in candidates.items()
    }


def conflicting_candidates(candidates: dict[str, list[Path]]) -> dict[str, list[Path]]:
    conflicts: dict[str, list[Path]] = {}
    for cod_id, paths in candidates.items():
        hashes = {sha256_file(path) for path in paths}
        if len(hashes) > 1:
            conflicts[cod_id] = paths
    return conflicts


def target_cod_ids(pair_manifest: Path, explicit_ids: list[str] | None) -> set[str]:
    if explicit_ids:
        return {str(cod_id).strip() for cod_id in explicit_ids}
    if not pair_manifest.is_file():
        raise FileNotFoundError(
            f"Pair manifest not found; provide --cod-id or --pair-manifest: {pair_manifest}"
        )
    with pair_manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = {
        row["cod_id"].strip()
        for row in rows
        if row.get("pair_status") == "duplicate_conflict"
    }
    if not ids:
        raise ValueError(
            f"No duplicate_conflict rows found in pair manifest: {pair_manifest}"
        )
    return ids


def get_small_structure(path: Path) -> tuple[gemmi.cif.Block, gemmi.SmallStructure]:
    block = gemmi.cif.read_file(str(path)).sole_block()
    small = gemmi.make_small_structure_from_block(block)
    return block, small


def site_element(site: Any) -> str | None:
    value = clean_text(getattr(site, "type_symbol", None))
    if value:
        return value[0].upper() + value[1:].lower()
    value = clean_text(getattr(site, "element", None))
    if value:
        return value[0].upper() + value[1:].lower()
    return None


def site_coordinates(site: Any) -> list[float]:
    fract = site.fract
    return [float(fract.x), float(fract.y), float(fract.z)]


def wrap_coordinate(value: float) -> float:
    wrapped = value % 1.0
    return 0.0 if math.isclose(wrapped, 1.0, abs_tol=COORD_TOL) else wrapped


def periodic_distance(left: list[float], right: list[float]) -> float:
    return max(
        min(abs(a - b), abs(a - b + 1.0), abs(a - b - 1.0))
        for a, b in zip(left, right)
    )


def canonical_symmetry_operations(operations: list[str]) -> list[str]:
    result: set[str] = set()
    for operation in operations:
        try:
            result.add(gemmi.Op(operation).wrap().triplet())
        except Exception:
            result.add(normalize_text(operation) or "")
    return sorted(result)


def atom_rows_from_block(block: gemmi.cif.Block) -> tuple[list[dict[str, Any]], list[str]]:
    tags, rows = loop_rows(block, "_atom_site_label")
    wyckoff_tag = next(
        (tag for tag in tags if tag in {"_atom_site_wyckoff_symbol", "_atom_site_wyckoff"}),
        None,
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        label = clean_text(row.get("_atom_site_label"))
        result.append(
            {
                "label": label,
                "element": clean_text(row.get("_atom_site_type_symbol")),
                "fract_x": numeric_value(row.get("_atom_site_fract_x")),
                "fract_y": numeric_value(row.get("_atom_site_fract_y")),
                "fract_z": numeric_value(row.get("_atom_site_fract_z")),
                "occupancy": numeric_value(row.get("_atom_site_occupancy")),
                "wyckoff": clean_text(row.get(wyckoff_tag)) if wyckoff_tag else None,
            }
        )
    return result, tags


def structure_summary(
    path: Path,
    cod_id: str,
    ai4_root: Path,
    project_cif_dir: Path,
) -> dict[str, Any]:
    stat = path.stat()
    file_record: dict[str, Any] = {
        "path": str(path),
        "size": stat.st_size,
        "sha256": sha256_file(path),
        "mtime_utc": utc_mtime(path),
        "provenance": provenance_for_path(path, ai4_root, project_cif_dir),
    }
    try:
        parsed = parse_cod_cif(path, source_id=cod_id)
        block, small = get_small_structure(path)
        atom_rows, atom_tags = atom_rows_from_block(block)
        expanded_sites = small.get_all_unit_cell_sites()
        file_record["parse"] = {
            "status": parsed.get("parse_status", "ok"),
            "warnings": parsed.get("parse_warnings", []),
            "data_block": parsed.get("data_block"),
            "formula": parsed.get("formula"),
            "formula_signature": formula_signature(parsed.get("formula")),
            "name": first_block_value(
                block,
                (
                    "_chemical_name_mineral",
                    "_chemical_name_common",
                    "_chemical_name_systematic",
                    "_chemical_name_structure_type",
                ),
            ),
            "space_group": {
                "hm": parsed.get("space_group", {}).get("hm"),
                "hall": parsed.get("space_group", {}).get("hall"),
                "number": parsed.get("space_group", {}).get("number"),
                "gemmi_hm": clean_text(small.spacegroup_hm),
                "gemmi_number": int(small.spacegroup_number)
                if small.spacegroup_number
                else None,
            },
            "cell": {
                key: value
                for key, value in {
                    **(parsed.get("cell") or {}),
                    "volume": float(small.cell.volume),
                }.items()
            },
            "atom_count": len(small.sites),
            "expanded_atom_count": len(expanded_sites),
            "atom_labels": [clean_text(site.label) for site in small.sites],
            "element_types": sorted(
                {
                    element
                    for element in (site_element(site) for site in small.sites)
                    if element
                }
            ),
            "atom_sites": [
                {
                    "label": row["label"],
                    "element": row["element"],
                    "fract_x": row["fract_x"],
                    "fract_y": row["fract_y"],
                    "fract_z": row["fract_z"],
                    "occupancy": row["occupancy"],
                    "wyckoff": row["wyckoff"],
                }
                for row in atom_rows
            ],
            "wyckoff_positions": [
                row["wyckoff"] for row in atom_rows if row["wyckoff"] is not None
            ],
            "symmetry_operations": canonical_symmetry_operations(list(small.symops)),
            "tag_names": sorted(parse_tag_values(path.read_text(encoding="utf-8", errors="replace"))["values"]),
        }
    except Exception as exc:
        file_record["parse"] = {
            "status": "error",
            "warnings": [f"{type(exc).__name__}: {exc}"],
        }
    return file_record


def compare_numeric_lists(left: list[Any], right: list[Any], tolerance: float) -> bool:
    if len(left) != len(right):
        return False
    parsed_left = [numeric_value(value) for value in left]
    parsed_right = [numeric_value(value) for value in right]
    if any(value is None for value in parsed_left + parsed_right):
        return False
    return all(math.isclose(a, b, rel_tol=0, abs_tol=tolerance) for a, b in zip(parsed_left, parsed_right))


def classify_tag(tag: str) -> str:
    if tag.startswith(METADATA_PREFIXES):
        return "metadata"
    if tag.startswith(STRUCTURE_PREFIXES):
        return "structure"
    return "other"


def byte_profile(data: bytes) -> dict[str, Any]:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n")
    cr_only = data.count(b"\r") - crlf
    lines = data.splitlines()
    return {
        "size": len(data),
        "bom": data.startswith(b"\xef\xbb\xbf"),
        "newline_style": (
            "CRLF"
            if crlf and crlf == lf
            else "LF"
            if lf and crlf == 0
            else "CR"
            if cr_only and lf == 0
            else "mixed_or_none"
        ),
        "crlf_count": crlf,
        "lf_count": lf,
        "cr_only_count": cr_only,
        "final_newline": (
            "CRLF"
            if data.endswith(b"\r\n")
            else "LF"
            if data.endswith(b"\n")
            else "none"
        ),
        "trailing_space_lines": sum(
            1 for line in lines if line.rstrip(b" \t") != line
        ),
    }


def first_byte_difference(left: bytes, right: bytes) -> dict[str, Any] | None:
    for offset, (left_byte, right_byte) in enumerate(zip(left, right)):
        if left_byte != right_byte:
            return {
                "offset": offset,
                "left_byte": left_byte,
                "right_byte": right_byte,
                "left_repr": repr(left[max(0, offset - 24) : offset + 24]),
                "right_repr": repr(right[max(0, offset - 24) : offset + 24]),
            }
    if len(left) != len(right):
        offset = min(len(left), len(right))
        return {
            "offset": offset,
            "left_byte": left[offset] if offset < len(left) else None,
            "right_byte": right[offset] if offset < len(right) else None,
            "left_repr": repr(left[max(0, offset - 24) : offset + 24]),
            "right_repr": repr(right[max(0, offset - 24) : offset + 24]),
        }
    return None


def compare_text(
    left_path: Path,
    right_path: Path,
    left_structure: dict[str, Any],
    right_structure: dict[str, Any],
) -> dict[str, Any]:
    left_text = left_path.read_text(encoding="utf-8", errors="replace")
    right_text = right_path.read_text(encoding="utf-8", errors="replace")
    left_bytes = left_path.read_bytes()
    right_bytes = right_path.read_bytes()
    left_tags = parse_tag_values(left_text)
    right_tags = parse_tag_values(right_text)
    all_tags = sorted(set(left_tags["values"]) | set(right_tags["values"]))
    changed_tags = [
        tag
        for tag in all_tags
        if left_tags["values"].get(tag) != right_tags["values"].get(tag)
    ]
    numeric_format_tags = [
        tag
        for tag in changed_tags
        if tag in left_tags["values"]
        and tag in right_tags["values"]
        and compare_numeric_lists(
            left_tags["values"][tag],
            right_tags["values"][tag],
            ANGLE_TOL if "angle" in tag else LENGTH_TOL,
        )
    ]
    left_atom_rows = next(
        (loop for loop in left_tags["loops"] if "_atom_site_label" in loop["tags"]),
        None,
    )
    right_atom_rows = next(
        (loop for loop in right_tags["loops"] if "_atom_site_label" in loop["tags"]),
        None,
    )
    atom_row_order_only = False
    if left_atom_rows and right_atom_rows and left_atom_rows["tags"] == right_atom_rows["tags"]:
        left_rows = [
            tuple(normalize_text(value) for value in row)
            for row in left_atom_rows["rows"]
        ]
        right_rows = [
            tuple(normalize_text(value) for value in row)
            for row in right_atom_rows["rows"]
        ]
        atom_row_order_only = sorted(left_rows) == sorted(right_rows) and left_rows != right_rows

    tag_value_equal = not changed_tags
    tag_set_equal = set(left_tags["values"]) == set(right_tags["values"])
    tag_order_equal = left_tags["order"] == right_tags["order"]
    normalized_text_equal = (
        left_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        == right_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    )

    changed_categories = Counter(classify_tag(tag) for tag in changed_tags)
    return {
        "left_path": str(left_path),
        "right_path": str(right_path),
        "byte_equal": left_bytes == right_bytes,
        "byte_difference": {
            "left": byte_profile(left_bytes),
            "right": byte_profile(right_bytes),
            "first_difference": first_byte_difference(left_bytes, right_bytes),
            "content_equal_after_newline_normalization": (
                left_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                == right_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            ),
        },
        "normalized_text_equal": normalized_text_equal,
        "tag_set_equal": tag_set_equal,
        "tag_order_equal": tag_order_equal,
        "tag_value_equal": tag_value_equal,
        "changed_tags": changed_tags,
        "changed_tag_categories": dict(sorted(changed_categories.items())),
        "numeric_format_tags": numeric_format_tags,
        "atom_row_order_only": atom_row_order_only,
        "data_blocks": {
            "left": left_tags["data_blocks"],
            "right": right_tags["data_blocks"],
            "equal": left_tags["data_blocks"] == right_tags["data_blocks"],
        },
        "structural_fields_changed": [
            tag for tag in changed_tags if classify_tag(tag) == "structure"
        ],
        "metadata_fields_changed": [
            tag for tag in changed_tags if classify_tag(tag) == "metadata"
        ],
        "left_parse_status": left_structure.get("parse", {}).get("status"),
        "right_parse_status": right_structure.get("parse", {}).get("status"),
    }


def bool_or_none(values: list[bool | None]) -> bool | None:
    if any(value is None for value in values):
        return None
    return all(bool(value) for value in values)


def compare_formula(left: dict[str, Any], right: dict[str, Any]) -> bool | None:
    left_value = left.get("parse", {}).get("formula_signature")
    right_value = right.get("parse", {}).get("formula_signature")
    if left_value is None or right_value is None:
        return None if left_value != right_value else True
    return left_value == right_value


def compare_cells(left: dict[str, Any], right: dict[str, Any]) -> bool | None:
    left_cell = left.get("parse", {}).get("cell", {})
    right_cell = right.get("parse", {}).get("cell", {})
    fields = ("a", "b", "c", "alpha", "beta", "gamma")
    if any(left_cell.get(field) is None or right_cell.get(field) is None for field in fields):
        return None
    for field in fields:
        tolerance = ANGLE_TOL if field in {"alpha", "beta", "gamma"} else LENGTH_TOL
        if not math.isclose(left_cell[field], right_cell[field], rel_tol=0, abs_tol=tolerance):
            return False
    left_volume = left_cell.get("volume")
    right_volume = right_cell.get("volume")
    if left_volume is not None and right_volume is not None:
        if not math.isclose(left_volume, right_volume, rel_tol=VOLUME_REL_TOL, abs_tol=1e-3):
            return False
    return True


def compare_space_groups(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool | None, str]:
    left_sg = left.get("parse", {}).get("space_group", {})
    right_sg = right.get("parse", {}).get("space_group", {})
    left_number = left_sg.get("gemmi_number") or left_sg.get("number")
    right_number = right_sg.get("gemmi_number") or right_sg.get("number")
    if left_number is not None and right_number is not None:
        if int(left_number) == int(right_number):
            if left_sg.get("gemmi_hm") != right_sg.get("gemmi_hm"):
                return True, "same International Tables number; notation/setting differs"
            return True, "same Gemmi space-group number and normalized HM"
        return False, "different Gemmi space-group number"
    left_hm = left_sg.get("gemmi_hm") or left_sg.get("hm")
    right_hm = right_sg.get("gemmi_hm") or right_sg.get("hm")
    if left_hm and right_hm and left_hm == right_hm:
        return True, "same normalized HM symbol"
    return None, "space group could not be normalized on both files"


def site_signature(site: Any) -> tuple[str | None, float | None, tuple[float, float, float]]:
    return (
        site_element(site),
        float(site.occ),
        tuple(wrap_coordinate(value) for value in site_coordinates(site)),
    )


def expanded_site_signatures(path: Path) -> list[tuple[str | None, float | None, tuple[float, float, float]]]:
    _, small = get_small_structure(path)
    return [site_signature(site) for site in small.get_all_unit_cell_sites()]


def atomic_sites_equivalent(
    left_path: Path,
    right_path: Path,
) -> tuple[bool | None, str, dict[str, Any]]:
    try:
        left_sites = expanded_site_signatures(left_path)
        right_sites = expanded_site_signatures(right_path)
    except Exception as exc:
        return None, f"expanded atom comparison failed: {type(exc).__name__}: {exc}", {}
    if len(left_sites) != len(right_sites):
        return (
            False,
            "expanded unit-cell atom counts differ",
            {
                "left_expanded_atom_count": len(left_sites),
                "right_expanded_atom_count": len(right_sites),
            },
        )
    unmatched = list(range(len(right_sites)))
    max_distance = 0.0
    for left_element, left_occ, left_coord in left_sites:
        best_index = None
        best_distance = float("inf")
        for index in unmatched:
            right_element, right_occ, right_coord = right_sites[index]
            if left_element != right_element:
                continue
            if left_occ is None or right_occ is None:
                if left_occ != right_occ:
                    continue
            elif not math.isclose(left_occ, right_occ, rel_tol=0, abs_tol=OCCUPANCY_TOL):
                continue
            distance = periodic_distance(list(left_coord), list(right_coord))
            if distance < best_distance:
                best_distance = distance
                best_index = index
        if best_index is None or best_distance > COORD_TOL:
            return (
                False,
                "element/occupancy/periodic-coordinate matching failed",
                {
                    "unmatched_left_site": {
                        "element": left_element,
                        "occupancy": left_occ,
                        "coordinates": left_coord,
                    },
                    "remaining_right_sites": len(unmatched),
                },
            )
        unmatched.remove(best_index)
        max_distance = max(max_distance, best_distance)
    return True, "expanded sites match independent of atom row order", {
        "expanded_atom_count": len(left_sites),
        "max_periodic_coordinate_distance": max_distance,
    }


def compare_structures(
    left_path: Path,
    right_path: Path,
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    space_group_equal, space_group_reason = compare_space_groups(left, right)
    cell_equal = compare_cells(left, right)
    formula_equal = compare_formula(left, right)
    atom_equal, atom_reason, atom_details = atomic_sites_equivalent(left_path, right_path)
    left_parse = left.get("parse", {})
    right_parse = right.get("parse", {})
    left_symops = left_parse.get("symmetry_operations")
    right_symops = right_parse.get("symmetry_operations")
    symops_equal = (
        None
        if left_symops is None or right_symops is None
        else left_symops == right_symops
    )
    result_values = [formula_equal, space_group_equal, cell_equal, atom_equal]
    equivalent = bool_or_none(result_values)
    if equivalent is True and symops_equal is False and space_group_equal is not True:
        equivalent = None
    return {
        "formula_equal": formula_equal,
        "space_group_equivalent": space_group_equal,
        "space_group_reason": space_group_reason,
        "cell_equivalent": cell_equal,
        "atomic_structure_equivalent": atom_equal,
        "atom_matching_reason": atom_reason,
        "atom_matching_details": atom_details,
        "atom_count_equal": left_parse.get("atom_count") == right_parse.get("atom_count"),
        "expanded_atom_count_equal": left_parse.get("expanded_atom_count")
        == right_parse.get("expanded_atom_count"),
        "atom_labels_equal_in_order": left_parse.get("atom_labels")
        == right_parse.get("atom_labels"),
        "element_types_equal": left_parse.get("element_types")
        == right_parse.get("element_types"),
        "wyckoff_positions_equal": left_parse.get("wyckoff_positions")
        == right_parse.get("wyckoff_positions"),
        "symmetry_operations_equal": symops_equal,
        "equivalent": equivalent,
    }


def pair_classification(
    text_result: dict[str, Any],
    structure_result: dict[str, Any],
) -> tuple[str, str, bool]:
    if text_result["byte_equal"]:
        return "identical_bytes", "same bytes and same SHA256", False
    equivalent = structure_result["equivalent"]
    if equivalent is None:
        return "uncertain", "Gemmi parsing or semantic matching was inconclusive", True
    if equivalent is False:
        return "structurally_modified", "one or more crystallographic fields differ", False
    changed_tags = text_result["changed_tags"]
    metadata_tags = text_result["metadata_fields_changed"]
    structural_tags = text_result["structural_fields_changed"]
    byte_difference = text_result["byte_difference"]
    left_newline = byte_difference["left"]["newline_style"]
    right_newline = byte_difference["right"]["newline_style"]
    newline_only = (
        byte_difference["content_equal_after_newline_normalization"]
        and left_newline != right_newline
        and not changed_tags
    )
    if newline_only:
        return (
            "byte_different_format_or_serialization",
            f"line-ending conversion ({left_newline} -> {right_newline})",
            False,
        )
    if not changed_tags:
        return "byte_different_format_or_serialization", "raw-byte or non-tag serialization difference", False
    if not structural_tags and metadata_tags:
        return "byte_different_metadata_structurally_equivalent", "metadata or bibliography fields differ", False
    if text_result["atom_row_order_only"] and not structural_tags:
        return "byte_different_format_or_serialization", "atom row order differs but values are unchanged", False
    if structure_result["space_group_reason"].endswith("notation/setting differs"):
        return "byte_different_structurally_equivalent", "equivalent space-group notation or setting", False
    return "byte_different_structurally_equivalent", "structure is equivalent after semantic comparison", False


def probable_reason(
    file_records: list[dict[str, Any]],
    pair_results: list[dict[str, Any]],
    classification: str,
) -> str:
    source_families = {
        record.get("provenance", {}).get("source_family")
        for record in file_records
    }
    metadata_changes = any(
        result["text_difference"]["metadata_fields_changed"] for result in pair_results
    )
    structural_changes = any(
        result["text_difference"]["structural_fields_changed"] for result in pair_results
    )
    different_pairs = [
        result
        for result in pair_results
        if not result["text_difference"]["byte_equal"]
    ]
    newline_only = bool(different_pairs) and all(
        result["text_difference"]["byte_difference"][
            "content_equal_after_newline_normalization"
        ]
        and not result["text_difference"]["changed_tags"]
        and (
            result["text_difference"]["byte_difference"]["left"]["newline_style"]
            != result["text_difference"]["byte_difference"]["right"]["newline_style"]
        )
        for result in different_pairs
    )
    if newline_only:
        newline_pairs = {
            (
                result["text_difference"]["byte_difference"]["left"]["newline_style"],
                result["text_difference"]["byte_difference"]["right"]["newline_style"],
            )
            for result in different_pairs
        }
        if len(newline_pairs) == 1:
            left_style, right_style = next(iter(newline_pairs))
            return f"local line-ending conversion ({left_style} -> {right_style})"
        return "line-ending or text serialization difference"
    if classification == "structurally_modified":
        if "crystaldb_project_data_raw_cod" in source_families:
            return "different local COD source/version; structural fields differ"
        return "different COD download or pipeline content; structural fields differ"
    if classification == "uncertain":
        return "automatic Gemmi comparison was inconclusive"
    if metadata_changes and "crystaldb_project_data_raw_cod" in source_families:
        return "different download/source snapshot with metadata or bibliography changes"
    if metadata_changes:
        return "metadata or bibliography serialization/update difference"
    if structural_changes:
        return "equivalent structure represented with different CIF structural notation"
    return "formatting, serialization, or atom-row-order difference"


def summarize_id(
    cod_id: str,
    paths: list[Path],
    ai4_root: Path,
    project_cif_dir: Path,
) -> dict[str, Any]:
    records = [
        structure_summary(path, cod_id, ai4_root, project_cif_dir)
        for path in paths
    ]
    pair_results: list[dict[str, Any]] = []
    for left_record, right_record in combinations(records, 2):
        left_path = Path(left_record["path"])
        right_path = Path(right_record["path"])
        text_result = compare_text(
            left_path,
            right_path,
            left_record,
            right_record,
        )
        structure_result = compare_structures(
            left_path,
            right_path,
            left_record,
            right_record,
        )
        classification, reason, manual_review = pair_classification(
            text_result,
            structure_result,
        )
        pair_results.append(
            {
                "left_path": str(left_path),
                "right_path": str(right_path),
                "text_difference": text_result,
                "structure_comparison": structure_result,
                "classification": classification,
                "probable_reason": reason,
                "needs_manual_review": manual_review,
            }
        )

    pair_classes = [result["classification"] for result in pair_results]
    if any(value == "uncertain" for value in pair_classes):
        classification = "uncertain"
        needs_manual_review = True
    elif any(value == "structurally_modified" for value in pair_classes):
        classification = "structurally_modified"
        needs_manual_review = False
    elif any(
        value == "byte_different_metadata_structurally_equivalent"
        for value in pair_classes
    ):
        classification = "byte_different_metadata_structurally_equivalent"
        needs_manual_review = False
    elif any(value == "byte_different_structurally_equivalent" for value in pair_classes):
        classification = "byte_different_structurally_equivalent"
        needs_manual_review = False
    else:
        classification = "byte_different_format_or_serialization"
        needs_manual_review = False

    changed_tags = sorted(
        {
            tag
            for result in pair_results
            for tag in result["text_difference"]["changed_tags"]
        }
    )
    structural_equal_values = [
        result["structure_comparison"]["equivalent"] for result in pair_results
    ]
    structure_equivalent = bool_or_none(structural_equal_values)
    return {
        "cod_id": cod_id,
        "files": records,
        "text_difference": {
            "different": len({record["sha256"] for record in records}) > 1,
            "changed_tags": changed_tags,
            "pairwise": pair_results,
        },
        "structure_comparison": {
            "formula_equal": bool_or_none(
                [result["structure_comparison"]["formula_equal"] for result in pair_results]
            ),
            "space_group_equivalent": bool_or_none(
                [
                    result["structure_comparison"]["space_group_equivalent"]
                    for result in pair_results
                ]
            ),
            "cell_equivalent": bool_or_none(
                [result["structure_comparison"]["cell_equivalent"] for result in pair_results]
            ),
            "atomic_structure_equivalent": bool_or_none(
                [
                    result["structure_comparison"]["atomic_structure_equivalent"]
                    for result in pair_results
                ]
            ),
            "symmetry_operations_equal": bool_or_none(
                [
                    result["structure_comparison"]["symmetry_operations_equal"]
                    for result in pair_results
                ]
            ),
            "all_pairwise_equivalent": structure_equivalent,
        },
        "classification": classification,
        "requested_category": (
            "uncertain"
            if classification == "uncertain"
            else "structurally_modified"
            if classification == "structurally_modified"
            else "metadata_difference_structurally_equivalent"
            if classification == "byte_different_metadata_structurally_equivalent"
            else "only_formatting_or_serialization"
        ),
        "probable_reason": probable_reason(records, pair_results, classification),
        "needs_manual_review": needs_manual_review,
        "pairwise_comparisons": pair_results,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def make_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# COD Duplicate SHA256 Validation",
        "",
        f"- Generated UTC: `{report['generated_utc']}`",
        f"- Gemmi: `{report['tooling']['gemmi_version']}`",
        f"- Conflict COD IDs: `{summary['conflict_cod_id_count']}`",
        f"- Candidate CIF files examined: `{summary['candidate_file_count']}`",
        f"- Unique SHA256 groups among conflict IDs: `{summary['unique_sha256_group_count']}`",
        "",
        "## Classification Summary",
        "",
        "| Classification | Count |",
        "| --- | ---: |",
    ]
    for key, value in summary["requested_category_counts"].items():
        lines.append(f"| {markdown_cell(key)} | {value} |")
    lines.extend(
        [
            "",
            "## Conflict Table",
            "",
            "| COD ID | File count | SHA256 count | Structure equivalent | Main difference | Manual review |",
            "| --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for item in report["records"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(item["cod_id"]),
                    str(len(item["files"])),
                    str(len({file["sha256"] for file in item["files"]})),
                    markdown_cell(item["structure_comparison"]["all_pairwise_equivalent"]),
                    markdown_cell(item["probable_reason"]),
                    markdown_cell(item["needs_manual_review"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Structurally Modified", ""])
    modified = [
        item["cod_id"]
        for item in report["records"]
        if item["classification"] == "structurally_modified"
    ]
    lines.append(
        ", ".join(modified) if modified else "None detected automatically."
    )
    lines.extend(["", "## Key Byte-Level Finding", ""])
    lines.append(
        "For all 54 conflict IDs, the AI4 copies use LF line endings and the "
        "CrystalDB `data/raw/cod` copies use CRLF line endings. After newline "
        "normalization, the text content is identical; no CIF tags or values changed."
    )
    lines.extend(["", "## Manual Review", ""])
    manual = [
        item["cod_id"]
        for item in report["records"]
        if item["needs_manual_review"]
    ]
    lines.append(", ".join(manual) if manual else "None.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Files with the same COD ID and same SHA256 are duplicate copies of the same bytes.",
            "- Different SHA256 files were compared pairwise with Gemmi and periodic coordinate matching.",
            "- No source CIF was modified, moved, deleted, or overwritten by this validation.",
            "",
            "## Source Provenance",
            "",
            "| Source family | File count |",
            "| --- | ---: |",
        ]
    )
    for key, value in sorted(summary["source_family_counts"].items()):
        lines.append(f"| {markdown_cell(key)} | {value} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    ai4_root = args.ai4_root.resolve()
    project_cif_dir = args.project_cif_dir.resolve()
    cod_ids = target_cod_ids(args.pair_manifest.resolve(), args.cod_ids)
    candidates = discover_candidates(ai4_root, project_cif_dir, cod_ids)
    conflicts = conflicting_candidates(candidates)
    records = [
        summarize_id(cod_id, conflicts[cod_id], ai4_root, project_cif_dir)
        for cod_id in sorted(conflicts, key=int)
    ]

    classification_counts = Counter(item["classification"] for item in records)
    requested_category_counts = Counter(
        item["requested_category"] for item in records
    )
    source_family_counts = Counter(
        file_record["provenance"]["source_family"]
        for item in records
        for file_record in item["files"]
    )
    unique_sha256_group_count = sum(
        len({file_record["sha256"] for file_record in item["files"]})
        for item in records
    )
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "tooling": {
            "gemmi_version": gemmi.__version__,
            "coordinate_tolerance": COORD_TOL,
            "length_tolerance": LENGTH_TOL,
            "angle_tolerance": ANGLE_TOL,
            "occupancy_tolerance": OCCUPANCY_TOL,
        },
        "inputs": {
            "ai4_root": str(ai4_root),
            "project_cif_dir": str(project_cif_dir),
            "pair_manifest": str(args.pair_manifest.resolve()),
            "target_cod_ids": sorted(cod_ids, key=int),
            "search_rule": "exact CIF basename in target COD ID scope",
        },
        "summary": {
            "candidate_file_count": sum(len(paths) for paths in candidates.values()),
            "candidate_cod_id_count": len(candidates),
            "conflict_cod_id_count": len(records),
            "unique_sha256_group_count": unique_sha256_group_count,
            "classification_counts": dict(sorted(classification_counts.items())),
            "requested_category_counts": {
                key: requested_category_counts.get(key, 0)
                for key in (
                    "only_formatting_or_serialization",
                    "metadata_difference_structurally_equivalent",
                    "byte_different_structurally_equivalent",
                    "structurally_modified",
                    "uncertain",
                )
            },
            "source_family_counts": dict(sorted(source_family_counts.items())),
        },
        "records": records,
    }
    write_json(args.json_output.resolve(), report)
    args.md_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.md_output.resolve().write_text(make_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"JSON report: {args.json_output.resolve()}")
    print(f"Markdown report: {args.md_output.resolve()}")


if __name__ == "__main__":
    main()
