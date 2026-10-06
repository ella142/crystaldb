#!/usr/bin/env python3
"""Collect standardized OPXRD JSON files with their explicit COD CIF files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


CRYSTALDB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AI4_ROOT = Path(r"D:\document\aiformaterials\ai4")
DEFAULT_OPXRD_DIR = (
    DEFAULT_AI4_ROOT
    / "downloads"
    / "opXRD_CNRS_COD_raw_unprocessed_retry_20260908_v2"
    / "standardized_json_strict_845"
)
DEFAULT_OUTPUT_DIR = CRYSTALDB_ROOT / "data" / "powder" / "opxrd"
DEFAULT_PROJECT_CIF_DIR = CRYSTALDB_ROOT / "data" / "raw" / "cod"

PAIR_FIELDS = [
    "pair_index",
    "cod_id",
    "opxrd_json_filename",
    "opxrd_json_source_path",
    "opxrd_json_relative_path",
    "opxrd_json_sha256",
    "cif_filename",
    "cif_source_path",
    "cif_relative_path",
    "cif_sha256",
    "pair_status",
    "notes",
]


@dataclass(frozen=True)
class CifCandidate:
    path: Path
    kind: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_cif_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def normalized_cif_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_cif_bytes(path)).hexdigest()


def normalized_cif_equal(left: Path, right: Path) -> bool:
    return normalized_cif_bytes(left) == normalized_cif_bytes(right)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run OPXRD JSON to COD CIF pairing by explicit COD ID. "
            "Use --copy to copy successful pairs."
        )
    )
    parser.add_argument(
        "--opxrd-dir",
        type=Path,
        default=DEFAULT_OPXRD_DIR,
        help="Directory containing standardized JSON files and standardized_manifest.csv.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest path; defaults to <opxrd-dir>/standardized_manifest.csv.",
    )
    parser.add_argument(
        "--ai4-root",
        type=Path,
        default=DEFAULT_AI4_ROOT,
        help="Existing AI4 data root to scan for exact <COD_ID>.cif files.",
    )
    parser.add_argument(
        "--project-cif-dir",
        type=Path,
        default=DEFAULT_PROJECT_CIF_DIR,
        help="Existing CrystalDB COD CIF directory to inspect.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory containing json/, cif/, and opxrd_cod_pairs.csv.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Perform copy2 for successful pairs and write the pair manifest.",
    )
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"json_file", "cod_id", "structure_cif"}
    missing = required.difference(rows[0].keys() if rows else set())
    if missing:
        raise ValueError(f"Manifest is missing required fields: {sorted(missing)}")
    return rows


def add_candidate(
    candidates: dict[str, dict[str, CifCandidate]],
    cod_id: str,
    path: Path,
    kind: str,
) -> None:
    if not path.is_file():
        return
    resolved = path.resolve()
    candidates[cod_id].setdefault(str(resolved).casefold(), CifCandidate(resolved, kind))


def discover_cif_candidates(
    rows: list[dict[str, str]],
    opxrd_dir: Path,
    ai4_root: Path,
    project_cif_dir: Path,
) -> dict[str, list[CifCandidate]]:
    ids = {row["cod_id"].strip() for row in rows}
    candidates: dict[str, dict[str, CifCandidate]] = defaultdict(dict)
    package_root = opxrd_dir.parent

    # The manifest's structure_cif is the primary provenance source.
    for row in rows:
        cod_id = row["cod_id"].strip()
        manifest_path = package_root / Path(row["structure_cif"])
        add_candidate(candidates, cod_id, manifest_path, "manifest_structure_cif")

    if ai4_root.is_dir():
        for path in ai4_root.rglob("*.cif"):
            if path.stem in ids:
                kind = "manifest_structure_cif" if any(
                    candidate.path == path.resolve()
                    and candidate.kind == "manifest_structure_cif"
                    for candidate in candidates[path.stem].values()
                ) else "ai4_scan"
                add_candidate(candidates, path.stem, path, kind)

    for cod_id in ids:
        add_candidate(
            candidates,
            cod_id,
            project_cif_dir / f"{cod_id}.cif",
            "project_raw_cod",
        )

    return {
        cod_id: sorted(
            paths.values(),
            key=lambda candidate: (candidate.kind != "manifest_structure_cif", str(candidate.path)),
        )
        for cod_id, paths in candidates.items()
    }


def unique_hashes(candidates: list[CifCandidate]) -> dict[str, list[CifCandidate]]:
    by_hash: dict[str, list[CifCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_hash[sha256_file(candidate.path)].append(candidate)
    return dict(by_hash)


def unique_normalized_hashes(
    candidates: list[CifCandidate],
) -> dict[str, list[CifCandidate]]:
    by_hash: dict[str, list[CifCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_hash[normalized_cif_sha256(candidate.path)].append(candidate)
    return dict(by_hash)


def json_relative_path(filename: str) -> str:
    return f"powder/opxrd/json/{filename}"


def cif_relative_path(filename: str) -> str:
    return f"powder/opxrd/cif/{filename}"


def format_candidate_note(candidates: list[CifCandidate]) -> str:
    return "|".join(str(candidate.path) for candidate in candidates)


def build_pair_rows(
    rows: list[dict[str, str]],
    opxrd_dir: Path,
    output_dir: Path,
    cif_candidates: dict[str, list[CifCandidate]],
    copy_files: bool,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    output_json_dir = output_dir / "json"
    output_cif_dir = output_dir / "cif"
    pair_rows: list[dict[str, str]] = []
    counts = defaultdict(int)

    for pair_index, source_row in enumerate(rows, start=1):
        cod_id = source_row["cod_id"].strip()
        json_filename = source_row["json_file"].strip()
        json_source = opxrd_dir / json_filename
        json_destination = output_json_dir / json_filename
        cif_filename = f"{cod_id}.cif"
        cif_destination = output_cif_dir / cif_filename
        notes: list[str] = []
        status = "paired"
        json_hash = ""
        cif_hash = ""
        cif_source = ""

        if json_source.is_file():
            json_hash = sha256_file(json_source)
        else:
            status = "missing_json"
            notes.append("OPXRD JSON source is missing")

        candidates = cif_candidates.get(cod_id, [])
        hash_groups = unique_hashes(candidates) if candidates else {}
        normalized_hash_groups = (
            unique_normalized_hashes(candidates) if candidates else {}
        )
        if not candidates:
            status = "missing_cif" if status == "paired" else status
            notes.append("No exact COD-ID CIF source was found")
        elif len(normalized_hash_groups) > 1:
            status = "duplicate_conflict"
            notes.append(
                "CIF content conflict after line-ending normalization across "
                f"{len(normalized_hash_groups)} unique normalized SHA256 values"
            )
            notes.append("CIF candidates=" + format_candidate_note(candidates))
        else:
            normalized_hash = next(iter(normalized_hash_groups))
            selected = next(
                (
                    candidate
                    for candidate in normalized_hash_groups[normalized_hash]
                    if candidate.kind == "manifest_structure_cif"
                ),
                normalized_hash_groups[normalized_hash][0],
            )
            cif_source = str(selected.path)
            cif_hash = sha256_file(selected.path)
            if len(hash_groups) > 1:
                notes.append(
                    "CIF source variants differ only by line endings; "
                    "selected manifest CIF"
                )
            elif len(candidates) > 1:
                notes.append(f"{len(candidates)} CIF source paths share this SHA256")

        if status == "paired":
            destination_conflicts: list[str] = []
            if json_destination.is_file():
                destination_hash = sha256_file(json_destination)
                if destination_hash == json_hash:
                    notes.append("JSON destination already matches; skip")
                elif normalized_cif_equal(json_destination, json_source):
                    notes.append(
                        "JSON destination differs only by line endings; skip"
                    )
                else:
                    destination_conflicts.append("JSON")
            if cif_destination.is_file():
                destination_hash = sha256_file(cif_destination)
                if destination_hash == cif_hash:
                    notes.append("CIF destination already matches; skip")
                elif normalized_cif_equal(cif_destination, Path(cif_source)):
                    notes.append(
                        "CIF destination differs only by line endings; skip"
                    )
                else:
                    destination_conflicts.append("CIF")
            if destination_conflicts:
                status = "duplicate_conflict"
                notes.append(
                    "Destination hash conflict; refused to overwrite "
                    + ", ".join(destination_conflicts)
                )
            elif copy_files:
                output_json_dir.mkdir(parents=True, exist_ok=True)
                output_cif_dir.mkdir(parents=True, exist_ok=True)
                if not json_destination.is_file():
                    shutil.copy2(json_source, json_destination)
                    counts["json_copied"] += 1
                if not cif_destination.is_file():
                    shutil.copy2(Path(cif_source), cif_destination)
                    counts["cif_copied"] += 1

        if status == "paired":
            counts["successful_pairs"] += 1
        elif status == "missing_cif":
            counts["missing_cif"] += 1
        elif status == "missing_json":
            counts["missing_json"] += 1
        elif status == "duplicate_conflict":
            counts["duplicate_conflicts"] += 1

        pair_rows.append(
            {
                "pair_index": str(pair_index),
                "cod_id": cod_id,
                "opxrd_json_filename": json_filename,
                "opxrd_json_source_path": str(json_source),
                "opxrd_json_relative_path": json_relative_path(json_filename),
                "opxrd_json_sha256": json_hash,
                "cif_filename": cif_filename,
                "cif_source_path": cif_source,
                "cif_relative_path": cif_relative_path(cif_filename),
                "cif_sha256": cif_hash,
                "pair_status": status,
                "notes": "; ".join(notes),
            }
        )

    return pair_rows, dict(counts)


def write_pair_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(
    source_json_count: int,
    manifest_count: int,
    unique_cod_ids: int,
    cif_found: int,
    cif_missing: int,
    counts: dict[str, int],
    copy_files: bool,
    output_dir: Path,
) -> None:
    print(f"Mode: {'copy' if copy_files else 'dry-run'}")
    print(f"OPXRD JSON count: {source_json_count}")
    print(f"Manifest count: {manifest_count}")
    print(f"Unique COD IDs: {unique_cod_ids}")
    print(f"CIF found: {cif_found}")
    print(f"CIF missing: {cif_missing}")
    print(f"Duplicate/hash conflict IDs: {counts.get('duplicate_conflicts', 0)}")
    print(f"Successful pairs: {counts.get('successful_pairs', 0)}")
    if copy_files:
        print(f"JSON copied: {counts.get('json_copied', 0)}")
        print(f"CIF copied: {counts.get('cif_copied', 0)}")
        final_json_count = len(list((output_dir / "json").glob("*.json")))
        final_cif_count = len(list((output_dir / "cif").glob("*.cif")))
        print(f"Final JSON files: {final_json_count}")
        print(f"Final CIF files: {final_cif_count}")
        print(f"Pair manifest: {output_dir / 'opxrd_cod_pairs.csv'}")


def main() -> None:
    args = parse_args()
    opxrd_dir = args.opxrd_dir.resolve()
    manifest = (args.manifest or opxrd_dir / "standardized_manifest.csv").resolve()
    output_dir = args.output_dir.resolve()
    rows = read_manifest(manifest)

    cod_ids = [row["cod_id"].strip() for row in rows]
    if any(not cod_id.isdigit() for cod_id in cod_ids):
        raise ValueError("Every manifest cod_id must be a numeric COD ID")

    json_files = {row["json_file"].strip() for row in rows}
    source_json_count = sum((opxrd_dir / filename).is_file() for filename in json_files)
    candidates = discover_cif_candidates(
        rows,
        opxrd_dir,
        args.ai4_root.resolve(),
        args.project_cif_dir.resolve(),
    )
    cif_found = sum(bool(candidates.get(cod_id)) for cod_id in set(cod_ids))
    cif_missing = len(set(cod_ids)) - cif_found

    pair_rows, counts = build_pair_rows(
        rows,
        opxrd_dir,
        output_dir,
        candidates,
        copy_files=args.copy,
    )
    print_summary(
        source_json_count=source_json_count,
        manifest_count=len(rows),
        unique_cod_ids=len(set(cod_ids)),
        cif_found=cif_found,
        cif_missing=cif_missing,
        counts=counts,
        copy_files=args.copy,
        output_dir=output_dir,
    )

    if args.copy:
        write_pair_manifest(output_dir / "opxrd_cod_pairs.csv", pair_rows)


if __name__ == "__main__":
    main()
