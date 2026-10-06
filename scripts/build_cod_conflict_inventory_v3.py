"""Classify same-COD-ID local CIF copies for v3 review gating."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_INVENTORY = Path(
    r"D:\document\aiformaterials\rruff\cif_recovery_v3\cod_local_inventory_v3.csv"
)
DEFAULT_OUTPUT = Path(
    r"D:\document\aiformaterials\rruff\cif_recovery_v3\manifests"
    r"\cod_local_conflict_inventory_v3.csv"
)

FIELDS = [
    "cod_id",
    "file_path",
    "sha256",
    "file_size",
    "formula",
    "space_group",
    "cell_a",
    "cell_b",
    "cell_c",
    "cell_alpha",
    "cell_beta",
    "cell_gamma",
    "atom_count",
    "atomic_structure_signature",
    "content_group",
    "difference_class",
    "preferred_copy",
    "review_status",
    "notes",
]


def _float(value: Any) -> float | None:
    try:
        return None if value in (None, "", ".", "?") else float(value)
    except (TypeError, ValueError):
        return None


def _json(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _close(left: Any, right: Any, tolerance: float) -> bool:
    left = _float(left)
    right = _float(right)
    if left is None or right is None:
        return left == right
    return math.isclose(left, right, rel_tol=0, abs_tol=tolerance)


def _structural_same(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_formula = " ".join(str(left.get("formula") or "").split())
    right_formula = " ".join(str(right.get("formula") or "").split())
    if left_formula != right_formula:
        return False
    if (left.get("space_group_number") or "") != (right.get("space_group_number") or ""):
        return False
    if (left.get("atom_count") or "") != (right.get("atom_count") or ""):
        return False
    for key in ("cell_a", "cell_b", "cell_c"):
        if not _close(left.get(key), right.get(key), 1e-4):
            return False
    for key in ("cell_alpha", "cell_beta", "cell_gamma"):
        if not _close(left.get(key), right.get(key), 1e-3):
            return False
    return True


def _classify(rows: list[dict[str, Any]]) -> tuple[str, str]:
    normalized = {
        row.get("normalized_content_sha256")
        for row in rows
        if row.get("normalized_content_sha256")
    }
    structures = {
        row.get("structure_fingerprint")
        for row in rows
        if row.get("structure_fingerprint")
    }
    if len(normalized) <= 1:
        return "format_only", "line-ending/whitespace-normalized content agrees"
    if len(structures) == 1:
        structural_rows = all(
            _structural_same(rows[0], row)
            for row in rows[1:]
        )
        if structural_rows:
            exact_numeric = all(
                all(
                    _close(rows[0].get(key), row.get(key), 1e-8)
                    for key in ("cell_a", "cell_b", "cell_c")
                )
                and all(
                    _close(rows[0].get(key), row.get(key), 1e-7)
                    for key in ("cell_alpha", "cell_beta", "cell_gamma")
                )
                for row in rows[1:]
            )
            return (
                "metadata_only" if exact_numeric else "numerical_precision_only",
                "same parsed structure fingerprint",
            )
        return "structure_equivalent", "fingerprint agrees but parsed metadata is incomplete"
    if not all(row.get("structure_fingerprint") for row in rows):
        return "uncertain", "one or more copies lacks a structure fingerprint"
    if all(_structural_same(rows[0], row) for row in rows[1:]):
        return "numerical_precision_only", "structural fields agree within tolerance"
    return "true_crystallographic_conflict", "same COD ID has distinct structural content"


def build(inventory_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with inventory_path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        if row.get("cod_id"):
            parsed = dict(row)
            for key in (
                "cell_a",
                "cell_b",
                "cell_c",
                "cell_alpha",
                "cell_beta",
                "cell_gamma",
                "atom_count",
                "space_group_number",
            ):
                parsed[key] = _float(row.get(key))
            parsed["elements"] = _json(row.get("elements")) or []
            grouped[str(row["cod_id"])].append(parsed)

    output_rows: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    conflict_ids: list[str] = []
    for cod_id, rows in sorted(grouped.items()):
        structure_fingerprints = {
            row.get("structure_fingerprint")
            for row in rows
            if row.get("structure_fingerprint")
        }
        normalized_hashes = {
            row.get("normalized_content_sha256")
            for row in rows
            if row.get("normalized_content_sha256")
        }
        if len(structure_fingerprints) <= 1 and len(normalized_hashes) <= 1:
            continue

        difference_class, notes = _classify(rows)
        class_counts[difference_class] += 1
        if difference_class in {"true_crystallographic_conflict", "uncertain"}:
            conflict_ids.append(cod_id)

        preferred_path = sorted(
            rows,
            key=lambda row: (
                0 if row.get("parse_status") in {"ok", "partial"} else 1,
                0 if "data\\raw\\cod" in row.get("file_path", "").lower() else 1,
                len(row.get("file_path", "")),
                row.get("file_path", "").lower(),
            ),
        )[0].get("file_path")
        content_groups: dict[str, str] = {}
        for row in rows:
            fingerprint = (
                row.get("structure_fingerprint")
                or row.get("normalized_content_sha256")
                or row.get("sha256")
                or "unknown"
            )
            content_groups.setdefault(fingerprint, f"group_{len(content_groups) + 1:02d}")

        for row in rows:
            fingerprint = (
                row.get("structure_fingerprint")
                or row.get("normalized_content_sha256")
                or row.get("sha256")
                or "unknown"
            )
            output_rows.append(
                {
                    "cod_id": cod_id,
                    "file_path": row.get("file_path"),
                    "sha256": row.get("sha256"),
                    "file_size": Path(row.get("file_path")).stat().st_size
                    if row.get("file_path") and Path(row.get("file_path")).exists()
                    else None,
                    "formula": row.get("formula"),
                    "space_group": row.get("space_group"),
                    "cell_a": row.get("cell_a"),
                    "cell_b": row.get("cell_b"),
                    "cell_c": row.get("cell_c"),
                    "cell_alpha": row.get("cell_alpha"),
                    "cell_beta": row.get("cell_beta"),
                    "cell_gamma": row.get("cell_gamma"),
                    "atom_count": row.get("atom_count"),
                    "atomic_structure_signature": row.get("structure_fingerprint"),
                    "content_group": content_groups[fingerprint],
                    "difference_class": difference_class,
                    "preferred_copy": row.get("file_path") == preferred_path,
                    "review_status": (
                        "review_required"
                        if difference_class
                        in {"true_crystallographic_conflict", "uncertain"}
                        else "auto_classified"
                    ),
                    "notes": notes,
                }
            )

    summary = {
        "conflict_inventory_version": "v3",
        "source_inventory": str(inventory_path),
        "conflict_file_count": len(output_rows),
        "conflict_cod_id_count": len({row["cod_id"] for row in output_rows}),
        "review_required_cod_id_count": len(conflict_ids),
        "difference_class_counts": dict(class_counts),
        "review_required_cod_ids": conflict_ids,
    }
    return output_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows, summary = build(args.inventory.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
