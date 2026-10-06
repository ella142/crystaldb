"""Build the local-first COD CIF inventory used by RRUFF recovery v3.

The inventory deliberately scans both CrystalDB's raw COD directory and
existing RRUFF recovery workspaces.  It never contacts COD and never changes
any existing file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crystaldb.cif_parser import parse_cif
from crystaldb.sources.cod.single_crystal_parser import parse_cod_cif


DEFAULT_CRYSTALDB_ROOT = REPO_ROOT
DEFAULT_RRUFF_ROOT = Path(r"D:\document\aiformaterials\rruff")
DEFAULT_OUTPUT_ROOT = DEFAULT_RRUFF_ROOT / "cif_recovery_v3"

COD_ID_RE = re.compile(r"(?<!\d)(\d{6,10})(?!\d)")

FIELDNAMES = [
    "inventory_record_id",
    "cod_id",
    "file_path",
    "source_root",
    "source_workspace",
    "sha256",
    "normalized_content_sha256",
    "structure_fingerprint",
    "parse_status",
    "parse_warnings",
    "data_block",
    "mineral_name",
    "formula",
    "formula_reduced",
    "elements",
    "space_group",
    "space_group_number",
    "space_group_hall",
    "cell_a",
    "cell_b",
    "cell_c",
    "cell_alpha",
    "cell_beta",
    "cell_gamma",
    "cell_volume",
    "atom_count",
    "pub_authors",
    "pub_title",
    "pub_journal",
    "pub_year",
    "pub_volume",
    "pub_page_first",
    "pub_page_last",
    "duplicate_group_key",
    "duplicate_copy_class",
    "local_copy_count",
    "structure_copy_count",
    "canonical_file_path",
]


def _compact_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    if value in (None, "", ".", "?"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_number(value: Any, digits: int = 6) -> float | None:
    number = _number(value)
    return round(number, digits) if number is not None else None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalized_content_hash(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in text.split("\n"))
    return _sha256_bytes(normalized.encode("utf-8"))


def _derive_cod_id(path: Path, parsed_id: Any = None) -> str | None:
    if parsed_id is not None:
        value = str(parsed_id).strip()
        value = re.sub(r"^COD[_-]?", "", value, flags=re.IGNORECASE)
        if value.isdigit():
            return value

    match = COD_ID_RE.search(path.stem)
    return match.group(1) if match else None


def _space_group_text(cod_space_group: dict[str, Any], legacy: dict[str, Any]) -> str | None:
    return (
        _clean_text(cod_space_group.get("hm"))
        or _clean_text(legacy.get("space_group"))
    )


def _structure_fingerprint(
    cod_parsed: dict[str, Any] | None,
    legacy_parsed: dict[str, Any] | None,
) -> str | None:
    if cod_parsed is None and legacy_parsed is None:
        return None

    cod_parsed = cod_parsed or {}
    legacy_parsed = legacy_parsed or {}
    cod_sg = cod_parsed.get("space_group") or {}
    cell = cod_parsed.get("cell") or {}
    if not any(value is not None for value in cell.values()):
        cell = legacy_parsed.get("cell_parameters") or {}

    atom_rows = cod_parsed.get("atomic_sites") or legacy_parsed.get("atoms") or []
    atoms = []
    for row in atom_rows:
        atoms.append(
            {
                "element": _clean_text(row.get("element")),
                "label": _clean_text(row.get("label")),
                "x": _round_number(row.get("fract_x")),
                "y": _round_number(row.get("fract_y")),
                "z": _round_number(row.get("fract_z")),
                "occupancy": _round_number(row.get("occupancy")),
            }
        )
    atoms.sort(
        key=lambda item: (
            item.get("element") or "",
            item.get("label") or "",
            item.get("x") if item.get("x") is not None else 999.0,
            item.get("y") if item.get("y") is not None else 999.0,
            item.get("z") if item.get("z") is not None else 999.0,
        )
    )

    formula = _clean_text(
        cod_parsed.get("formula")
        or legacy_parsed.get("formula")
    )
    payload = {
        # Parsed CIF values can retain embedded CR/LF from quoted or wrapped
        # formula fields.  Normalize all whitespace so line-ending-only
        # copies receive the same crystallographic fingerprint.
        "formula": " ".join(formula.split()) if formula else None,
        "space_group_number": cod_sg.get("number"),
        "space_group_hm": _clean_text(
            cod_sg.get("hm")
            or legacy_parsed.get("space_group")
        ),
        "cell": {
            key: _round_number(cell.get(key))
            for key in ("a", "b", "c", "alpha", "beta", "gamma")
        },
        "atoms": atoms,
    }
    return _sha256_bytes(_compact_json(payload).encode("utf-8"))


def _discover_files(
    crystaldb_root: Path,
    rruff_root: Path,
    output_root: Path,
) -> list[tuple[Path, str, str]]:
    discovered: dict[str, tuple[Path, str, str]] = {}

    raw_cod = crystaldb_root / "data" / "raw" / "cod"
    if raw_cod.exists():
        for path in raw_cod.rglob("*.cif"):
            key = str(path.resolve()).lower()
            discovered[key] = (path, str(raw_cod), "crystaldb:data/raw/cod")

    if rruff_root.exists():
        for workspace in sorted(rruff_root.glob("cif_recovery*")):
            try:
                if workspace.resolve() == output_root.resolve():
                    continue
            except FileNotFoundError:
                pass
            for path in workspace.rglob("*.cif"):
                key = str(path.resolve()).lower()
                discovered[key] = (
                    path,
                    str(workspace),
                    f"rruff:{workspace.name}",
                )

    return [
        discovered[key]
        for key in sorted(discovered)
    ]


def _parse_one(path: Path, source_root: str, source_workspace: str) -> dict[str, Any]:
    raw = path.read_bytes()
    sha256 = _sha256_bytes(raw)
    normalized_hash = _normalized_content_hash(raw)

    cod_parsed: dict[str, Any] | None = None
    legacy_parsed: dict[str, Any] | None = None
    warnings: list[str] = []

    try:
        cod_parsed = parse_cod_cif(path)
    except Exception as exc:
        warnings.append(f"cod_parser:{type(exc).__name__}:{exc}")

    try:
        legacy_parsed = parse_cif(path)
    except Exception as exc:
        warnings.append(f"legacy_parser:{type(exc).__name__}:{exc}")

    cod_parsed = cod_parsed or {}
    legacy_parsed = legacy_parsed or {}
    cod_space_group = cod_parsed.get("space_group") or {}
    cod_cell = cod_parsed.get("cell") or {}
    legacy_cell = legacy_parsed.get("cell_parameters") or {}
    publication = legacy_parsed.get("publication") or {}

    parse_status = cod_parsed.get("parse_status")
    if not parse_status:
        parse_status = "ok" if legacy_parsed else "failed"
    if cod_parsed and warnings:
        parse_status = "partial"

    cod_id = _derive_cod_id(path, cod_parsed.get("source_id"))
    structure_fingerprint = _structure_fingerprint(
        cod_parsed,
        legacy_parsed,
    )

    formula = _clean_text(
        cod_parsed.get("formula")
        or legacy_parsed.get("formula")
    )
    elements = cod_parsed.get("elements") or []
    if not elements:
        elements = sorted(
            {
                match.group(1)
                for match in re.finditer(
                    r"([A-Z][a-z]?)",
                    formula or "",
                )
            }
        )

    cell = {}
    for key in ("a", "b", "c", "alpha", "beta", "gamma", "volume"):
        cell[key] = _number(cod_cell.get(key))
        if cell[key] is None:
            cell[key] = _number(legacy_cell.get(key))

    record = {
        "cod_id": cod_id,
        "file_path": str(path.resolve()),
        "source_root": source_root,
        "source_workspace": source_workspace,
        "sha256": sha256,
        "normalized_content_sha256": normalized_hash,
        "structure_fingerprint": structure_fingerprint,
        "parse_status": parse_status,
        "parse_warnings": sorted(set(warnings + (cod_parsed.get("parse_warnings") or []))),
        "data_block": _clean_text(
            cod_parsed.get("data_block")
            or legacy_parsed.get("data_block")
        ),
        "mineral_name": _clean_text(legacy_parsed.get("mineral_name")),
        "formula": formula,
        "formula_reduced": _clean_text(cod_parsed.get("formula_reduced")),
        "elements": sorted(elements),
        "space_group": _space_group_text(cod_space_group, legacy_parsed),
        "space_group_number": cod_space_group.get("number"),
        "space_group_hall": _clean_text(cod_space_group.get("hall")),
        "cell_a": cell["a"],
        "cell_b": cell["b"],
        "cell_c": cell["c"],
        "cell_alpha": cell["alpha"],
        "cell_beta": cell["beta"],
        "cell_gamma": cell["gamma"],
        "cell_volume": cell["volume"],
        "atom_count": cod_parsed.get("atom_count") or legacy_parsed.get("atom_count") or 0,
        "pub_authors": publication.get("authors") or [],
        "pub_title": _clean_text(publication.get("title")),
        "pub_journal": _clean_text(publication.get("journal")),
        "pub_year": _clean_text(publication.get("year")),
        "pub_volume": _clean_text(publication.get("volume")),
        "pub_page_first": _clean_text(publication.get("page_first")),
        "pub_page_last": _clean_text(publication.get("page_last")),
    }
    return record


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ("parse_warnings", "elements", "pub_authors"):
                row[key] = _compact_json(row.get(key) or [])
            writer.writerow(row)


def build_inventory(
    crystaldb_root: Path,
    rruff_root: Path,
    output_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = _discover_files(crystaldb_root, rruff_root, output_root)
    records: list[dict[str, Any]] = []

    for index, (path, source_root, workspace) in enumerate(files, start=1):
        if index == 1 or index % 500 == 0 or index == len(files):
            print(f"[inventory] parsing {index}/{len(files)}: {path.name}")
        try:
            record = _parse_one(path, source_root, workspace)
        except Exception as exc:
            record = {
                "cod_id": _derive_cod_id(path),
                "file_path": str(path.resolve()),
                "source_root": source_root,
                "source_workspace": workspace,
                "sha256": _sha256_bytes(path.read_bytes()),
                "normalized_content_sha256": None,
                "structure_fingerprint": None,
                "parse_status": "failed",
                "parse_warnings": [f"inventory:{type(exc).__name__}:{exc}"],
                "data_block": None,
                "mineral_name": None,
                "formula": None,
                "formula_reduced": None,
                "elements": [],
                "space_group": None,
                "space_group_number": None,
                "space_group_hall": None,
                "cell_a": None,
                "cell_b": None,
                "cell_c": None,
                "cell_alpha": None,
                "cell_beta": None,
                "cell_gamma": None,
                "cell_volume": None,
                "atom_count": 0,
                "pub_authors": [],
                "pub_title": None,
                "pub_journal": None,
                "pub_year": None,
                "pub_volume": None,
                "pub_page_first": None,
                "pub_page_last": None,
            }
        records.append(record)

    by_cod_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("cod_id"):
            by_cod_id[str(record["cod_id"])].append(record)

    for index, record in enumerate(records, start=1):
        cod_id = record.get("cod_id")
        copies = by_cod_id.get(str(cod_id), []) if cod_id else []
        structure_groups = {
            item.get("structure_fingerprint")
            for item in copies
            if item.get("structure_fingerprint")
        }
        record["inventory_record_id"] = f"inv_{index:07d}"
        record["local_copy_count"] = len(copies) or 1
        record["structure_copy_count"] = len(structure_groups) or 1
        record["duplicate_group_key"] = (
            f"{cod_id}:{record.get('structure_fingerprint')[:16]}"
            if cod_id and record.get("structure_fingerprint")
            else None
        )

        same_sha = any(
            item.get("sha256") == record.get("sha256")
            and item is not record
            for item in copies
        )
        same_normalized = any(
            item.get("normalized_content_sha256")
            == record.get("normalized_content_sha256")
            and item is not record
            for item in copies
        )
        same_structure = any(
            item.get("structure_fingerprint")
            == record.get("structure_fingerprint")
            and item is not record
            for item in copies
        )
        if not cod_id or len(copies) <= 1:
            copy_class = "unique_local_copy"
        elif same_sha:
            copy_class = "byte_identical_copy"
        elif same_normalized:
            copy_class = "line_ending_or_whitespace_only"
        elif same_structure:
            copy_class = "crystallographically_equivalent_copy"
        else:
            copy_class = "distinct_structure_content"
        record["duplicate_copy_class"] = copy_class

    for cod_id, copies in by_cod_id.items():
        valid = [
            item
            for item in copies
            if item.get("parse_status") in {"ok", "partial"}
        ]
        preferred = sorted(
            valid or copies,
            key=lambda item: (
                0 if "data\\raw\\cod" in item["file_path"].lower() else 1,
                len(item["file_path"]),
                item["file_path"].lower(),
            ),
        )[0]
        for item in copies:
            item["canonical_file_path"] = preferred["file_path"]

    summary = {
        "inventory_version": "v3",
        "file_count": len(records),
        "cod_id_count": len(by_cod_id),
        "parse_status_counts": dict(Counter(record.get("parse_status") for record in records)),
        "source_workspace_counts": dict(Counter(record.get("source_workspace") for record in records)),
        "duplicate_cod_id_count": sum(1 for copies in by_cod_id.values() if len(copies) > 1),
        "distinct_structure_duplicate_id_count": sum(
            1
            for copies in by_cod_id.values()
            if len(
                {
                    item.get("structure_fingerprint")
                    for item in copies
                    if item.get("structure_fingerprint")
                }
            )
            > 1
        ),
        "missing_cod_id_count": sum(1 for record in records if not record.get("cod_id")),
        "created_from": {
            "crystaldb_cod_root": str(crystaldb_root / "data" / "raw" / "cod"),
            "rruff_root": str(rruff_root),
        },
    }
    return records, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crystaldb-root", type=Path, default=DEFAULT_CRYSTALDB_ROOT)
    parser.add_argument("--rruff-root", type=Path, default=DEFAULT_RRUFF_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    records, summary = build_inventory(
        args.crystaldb_root.resolve(),
        args.rruff_root.resolve(),
        args.output_root.resolve(),
    )

    inventory_path = args.output_root / "cod_local_inventory_v3.csv"
    manifest_path = args.output_root / "manifests" / "cod_local_inventory_v3.csv"
    _write_csv(inventory_path, records)
    _write_csv(manifest_path, records)

    summary_path = args.output_root / "reports" / "inventory_summary_v3.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[inventory] wrote {inventory_path}")


if __name__ == "__main__":
    main()
