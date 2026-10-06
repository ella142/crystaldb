"""RRUFF -> CIF structure recovery v3.

This workflow changes candidate retrieval/narrowing while preserving the
existing crystallographic and calibrated diffraction code.  It is local-first:

    local evidence
    -> targeted COD ID retrieval
    -> download only missing shortlisted IDs

The default mode is a 20-target pilot.  v2 manifests are read only for
reconciliation and category selection; they are never used as v3 candidates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for import_root in (SRC_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from build_cod_local_inventory_v3 import _parse_one
from crystaldb.matching.candidate_compare import compare_candidate, normalize_name
from crystaldb.matching.candidate_resolver import (
    bibliographic_match,
    build_cod_publication_fingerprint,
    extract_rruff_reference_fingerprints,
)
from crystaldb.matching.chemistry import compare_chemistry, extract_elements
from crystaldb.matching.rruff_signature import build_rruff_signature
from crystaldb.sources.cod import (
    build_cod_session,
    download_cod_cif,
    search_cod_targeted,
)


RRUFF_ROOT = Path(r"D:\document\aiformaterials\rruff")
OUTPUT_ROOT = RRUFF_ROOT / "cif_recovery_v3"
V2_ROOT = RRUFF_ROOT / "cif_recovery_v2"
TARGETS_V2 = V2_ROOT / "manifests" / "rruff_targets_v2.csv"
V2_LINKS = V2_ROOT / "manifests" / "rruff_cif_links_v2.csv"
V2_RECALL = V2_ROOT / "manifests" / "cod_recall_over_100_marks_v2.csv"
LOCAL_INVENTORY = OUTPUT_ROOT / "cod_local_inventory_v3.csv"
CONFLICT_INVENTORY = (
    OUTPUT_ROOT / "manifests" / "cod_local_conflict_inventory_v3.csv"
)
DIFFRACTION_CALIBRATION = (
    REPO_ROOT / "data" / "mappings" / "rruff_diffraction_calibration_v1.json"
)
GROUP_DIFFRACTION_ANNOTATION = (
    REPO_ROOT
    / "data"
    / "mappings"
    / "rruff_group_diffraction_annotation_v1.json"
)
EXPERIMENTAL_RESOLUTION = (
    REPO_ROOT / "data" / "mappings" / "rruff_experimental_resolution_v1.json"
)

COD_RECALL_THRESHOLD = 100
COD_REQUEST_DELAY_SECONDS = 0.25
STRICT_CELL_LENGTH_TOLERANCE = 0.05
STRICT_CELL_ANGLE_TOLERANCE = 2.0
RESCUE_CELL_LENGTH_TOLERANCE = 0.15
RESCUE_CELL_ANGLE_TOLERANCE = 5.0
MAX_LOCAL_CANDIDATES = 250
MAX_REMOTE_DOWNLOADS_PER_TARGET = 30

MANUAL_AMCSD_HOME = "https://rruff.info/AMS/"


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _parse_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _float(value: Any) -> float | None:
    if value in (None, "", ".", "?"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stable_key(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _same_name(left: Any, right: Any) -> bool:
    return (
        normalize_name(left) is not None
        and normalize_name(right) is not None
        and normalize_name(left) == normalize_name(right)
    )


def _formula_query(formula: Any) -> str:
    if not formula:
        return ""
    text = str(formula)
    text = re.sub(r"[\^_()\[\];]", " ", text)
    text = re.sub(r"[^\w.+-]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_reference_rows(value: Any) -> list[str]:
    parsed = _parse_json(value, None)
    if isinstance(parsed, list):
        return [str(item) for item in parsed if item not in (None, "")]
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return []


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json(row) + "\n")


def _load_targets(path: Path) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for raw in _read_csv(path):
        target_id = raw.get("target_id") or raw.get("sample_id")
        if not target_id:
            continue
        target = dict(raw)
        target["target_id"] = target_id
        target["references"] = _parse_reference_rows(raw.get("references"))
        target["cell_parameters"] = {
            "a": _float(raw.get("cell_a")),
            "b": _float(raw.get("cell_b")),
            "c": _float(raw.get("cell_c")),
            "alpha": _float(raw.get("cell_alpha")),
            "beta": _float(raw.get("cell_beta")),
            "gamma": _float(raw.get("cell_gamma")),
        }
        target["atom_count"] = int(_float(raw.get("atom_count")) or 0)
        targets[target_id] = target
    return targets


def _load_v2_comparison(root: Path) -> tuple[dict[str, dict[str, str]], set[str]]:
    links = {}
    for row in _read_csv(root / "manifests" / "rruff_cif_links_v2.csv"):
        target_id = row.get("target_id") or row.get("rruff_id")
        if target_id:
            links[target_id] = row
    broad = {
        row.get("rruff_id") or row.get("target_id")
        for row in _read_csv(root / "manifests" / "cod_recall_over_100_marks_v2.csv")
        if row.get("rruff_id") or row.get("target_id")
    }
    return links, {item for item in broad if item}


def _select_pilot_targets(
    targets: dict[str, dict[str, Any]],
    v2_links: dict[str, dict[str, str]],
    v2_broad: set[str],
) -> tuple[list[str], dict[str, list[str]]]:
    available = set(targets)
    selected: set[str] = set()
    categories: dict[str, list[str]] = {}

    def choose(category: str, predicate, preferred: Iterable[str] = ()) -> None:
        preferred_set = set(preferred)
        candidates = sorted(
            (
                target_id
                for target_id in available - selected
                if predicate(target_id)
            ),
            key=lambda target_id: (
                0 if target_id in preferred_set else 1,
                _stable_key(target_id),
            ),
        )
        picked = candidates[:5]
        categories[category] = picked
        selected.update(picked)

    choose(
        "broad_v2_recall",
        lambda target_id: target_id in v2_broad,
        preferred=("R040002", "R040009", "R040018"),
    )
    choose(
        "easy_same_name_citation",
        lambda target_id: (
            v2_links.get(target_id, {}).get("relation_status") == "accepted_unique"
            and int(_float(v2_links.get(target_id, {}).get("cod_recall_count")) or 999999) <= 5
            and _same_name(
                targets[target_id].get("sample_mineral"),
                targets[target_id].get("reference_structure_name"),
            )
        ),
    )
    choose(
        "name_mismatch",
        lambda target_id: not _same_name(
            targets[target_id].get("sample_mineral"),
            targets[target_id].get("reference_structure_name"),
        ),
    )
    choose(
        "ambiguous_or_review",
        lambda target_id: v2_links.get(target_id, {}).get("relation_status")
        in {"ambiguous_group", "needs_review", "candidate_only", "no_candidate"},
    )

    # Keep the pilot at 20 even when a historical category has fewer than five
    # usable members.
    remaining = sorted(available - selected, key=_stable_key)
    while sum(len(items) for items in categories.values()) < 20 and remaining:
        categories.setdefault("pilot_fill", [])
        target_id = remaining.pop(0)
        categories["pilot_fill"].append(target_id)
        selected.add(target_id)

    ordered = []
    for category in (
        "easy_same_name_citation",
        "name_mismatch",
        "broad_v2_recall",
        "ambiguous_or_review",
        "pilot_fill",
    ):
        ordered.extend(categories.get(category, []))
    return ordered[:20], categories


def _inventory_record_from_row(row: dict[str, str]) -> dict[str, Any]:
    result = dict(row)
    for key in (
        "cell_a",
        "cell_b",
        "cell_c",
        "cell_alpha",
        "cell_beta",
        "cell_gamma",
        "cell_volume",
        "atom_count",
        "space_group_number",
    ):
        result[key] = _float(row.get(key))
    result["elements"] = _parse_json(row.get("elements"), [])
    result["pub_authors"] = _parse_json(row.get("pub_authors"), [])
    result["parse_warnings"] = _parse_json(row.get("parse_warnings"), [])
    return result


def _load_inventory(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    copies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _read_csv(path):
        record = _inventory_record_from_row(row)
        cod_id = record.get("cod_id")
        if cod_id:
            copies[str(cod_id)].append(record)

    canonical: dict[str, dict[str, Any]] = {}
    for cod_id, rows in copies.items():
        valid = [
            row
            for row in rows
            if row.get("parse_status") in {"ok", "partial"}
        ]
        preferred = sorted(
            valid or rows,
            key=lambda row: (
                0 if row.get("file_path") == row.get("canonical_file_path") else 1,
                0 if "data\\raw\\cod" in row.get("file_path", "").lower() else 1,
                len(row.get("file_path", "")),
                row.get("file_path", "").lower(),
            ),
        )[0]
        canonical[cod_id] = preferred
    return canonical, copies


def _load_conflict_inventory(
    path: Path,
) -> dict[str, dict[str, Any]]:
    """Load same-COD-ID copy classifications for resolution gating."""

    conflicts: dict[str, dict[str, Any]] = {}
    for row in _read_csv(path):
        cod_id = _text(row.get("cod_id"))
        if not cod_id:
            continue
        existing = conflicts.setdefault(
            cod_id,
            {
                "difference_classes": set(),
                "review_statuses": set(),
                "rows": [],
            },
        )
        existing["difference_classes"].add(
            _text(row.get("difference_class")) or "uncertain"
        )
        existing["review_statuses"].add(
            _text(row.get("review_status")) or "review_required"
        )
        existing["rows"].append(dict(row))
    return conflicts


def _load_diffraction_history() -> dict[str, dict[str, dict[str, Any]]]:
    """Load already-calibrated diffraction metrics without reimplementing them."""

    by_target: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for path in (DIFFRACTION_CALIBRATION, GROUP_DIFFRACTION_ANNOTATION):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
        for item in payload.get("records", []) + payload.get("groups", []):
            target_id = _text(item.get("sample_id"))
            if not target_id:
                continue
            for candidate in item.get("candidate_results", []) or []:
                source_id = _text(
                    candidate.get("source_id") or candidate.get("cod_id")
                )
                if source_id and candidate.get("metrics"):
                    by_target[target_id][source_id] = {
                        "status": "historically_evaluated",
                        "source": str(path),
                        "resolution_status": item.get("resolution_status"),
                        "metrics": candidate.get("metrics") or {},
                    }
            selected = item.get("selected_source_id")
            if selected and item.get("metrics"):
                by_target[target_id].setdefault(
                    str(selected),
                    {
                        "status": "historically_evaluated",
                        "source": str(path),
                        "resolution_status": item.get("resolution_status"),
                        "metrics": item.get("metrics") or {},
                    },
                )
    return dict(by_target)


def _load_experimental_resolution_ids() -> set[str]:
    if not EXPERIMENTAL_RESOLUTION.exists():
        return set()
    try:
        payload = json.loads(EXPERIMENTAL_RESOLUTION.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return set()
    return {
        str(item.get("sample_id"))
        for item in payload.get("records", [])
        if item.get("sample_id")
    }


def _load_existing_pilot_selection(
    path: Path,
    targets: dict[str, dict[str, Any]],
) -> tuple[list[str], dict[str, list[str]]] | None:
    """Reuse the already audited offline pilot selection for the online pilot."""

    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    target_ids = [
        str(target_id)
        for target_id in payload.get("target_ids", [])
        if str(target_id) in targets
    ]
    if len(target_ids) != 20:
        return None
    categories = {
        str(category): [
            str(target_id)
            for target_id in items
            if str(target_id) in targets
        ]
        for category, items in (payload.get("categories") or {}).items()
    }
    return target_ids, categories


def _run_environment(
    *,
    mode: str,
    offline: bool,
    target_count: int,
    inventory_path: Path,
    conflict_path: Path,
) -> dict[str, Any]:
    return {
        "workflow": "RRUFF CIF recovery v3",
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "offline": offline,
        "target_count": target_count,
        "local_inventory": str(inventory_path),
        "conflict_inventory": str(conflict_path),
        "cod_request_delay_seconds": COD_REQUEST_DELAY_SECONDS,
        "http_client": "crystaldb.sources.cod.build_cod_session",
        "http_trust_env": False,
        "tls_verification_disabled": False,
        "amcsd_cif_retrieval_enabled": False,
        "v2_modified": False,
        "database_modified": False,
        "paper_modified": False,
        "environment_proxy_variables_present": sorted(
            key
            for key in os.environ
            if "proxy" in key.lower()
        ),
    }


def _candidate_structure(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "COD",
        "source_id": record.get("cod_id"),
        "file_path": record.get("file_path"),
        "mineral_name": record.get("mineral_name"),
        "formula": record.get("formula"),
        "space_group": record.get("space_group"),
        "cell_parameters": {
            key: record.get(f"cell_{key}")
            for key in ("a", "b", "c", "alpha", "beta", "gamma")
        },
        "publication": {
            "authors": record.get("pub_authors") or [],
            "title": record.get("pub_title"),
            "journal": record.get("pub_journal"),
            "year": record.get("pub_year"),
            "volume": record.get("pub_volume"),
            "page_first": record.get("pub_page_first"),
            "page_last": record.get("pub_page_last"),
        },
    }


def _target_signature(target: dict[str, Any]) -> dict[str, Any]:
    signature = build_rruff_signature(
        {
            "sample_id": target.get("sample_id") or target.get("target_id"),
            "filename_mineral": target.get("sample_mineral"),
            "mineral": target.get("reference_structure_name"),
            "crystal_structure": {
                "space_group": target.get("space_group"),
                "cell_parameters": target.get("cell_parameters") or {},
                "atom_count": target.get("atom_count") or 0,
            },
            "references": target.get("references") or [],
        },
        ideal_chemistry=target.get("ideal_chemistry"),
    )
    signature.update(
        {
            "rruff_id": target.get("target_id"),
            "sample_id": target.get("sample_id") or target.get("target_id"),
            "sample_mineral": target.get("sample_mineral"),
            "reference_structure_name": target.get("reference_structure_name"),
            "ideal_chemistry": target.get("ideal_chemistry"),
            "normalized_chemistry": target.get("normalized_chemistry")
            or target.get("ideal_chemistry"),
            "profile_origin": target.get("xy_origin"),
            "has_xy": target.get("has_xy"),
            "wavelength": target.get("wavelength"),
        }
    )
    return signature


def _chemistry_status(
    target_formula: Any,
    candidate_formula: Any,
) -> tuple[str, dict[str, Any]]:
    comparison = compare_chemistry(target_formula, candidate_formula)
    compatible = comparison.get("compatible")
    if compatible is True:
        return "compatible", comparison
    if compatible is False:
        return "incompatible", comparison

    target_elements = set(comparison.get("elements_a") or extract_elements(target_formula))
    candidate_elements = set(comparison.get("elements_b") or extract_elements(candidate_formula))
    if target_elements and candidate_elements and target_elements == candidate_elements:
        return "possibly_compatible", comparison
    if not target_elements or not candidate_elements:
        return "unknown", comparison
    return "incompatible", comparison


def _space_group_status(comparison: dict[str, Any]) -> str:
    equivalent = comparison.get("equivalent")
    same_number = comparison.get("same_number")
    if equivalent is True:
        return "equivalent"
    if same_number is True:
        return "same_number_setting_difference"
    if equivalent is False:
        return "incompatible"
    return "unknown"


def _cell_status(cell_comparison: dict[str, Any]) -> str:
    max_length = cell_comparison.get("max_length_relative_difference")
    max_angle = cell_comparison.get("max_angle_difference")
    if max_length is None and max_angle is None:
        return "unknown"
    if (
        max_length is not None
        and max_length <= STRICT_CELL_LENGTH_TOLERANCE
        and (max_angle is None or max_angle <= STRICT_CELL_ANGLE_TOLERANCE)
    ):
        return "compatible"
    if (
        max_length is not None
        and max_length <= RESCUE_CELL_LENGTH_TOLERANCE
        and (max_angle is None or max_angle <= RESCUE_CELL_ANGLE_TOLERANCE)
    ):
        return "possibly_compatible"
    return "incompatible"


def _bibliography_evidence(
    references: list[str],
    publication: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    rruff_fingerprints = extract_rruff_reference_fingerprints(references)
    cod_fingerprint = build_cod_publication_fingerprint(publication)
    if not rruff_fingerprints or not cod_fingerprint:
        return "unknown", {
            "rruff_fingerprints": rruff_fingerprints,
            "cod_fingerprint": cod_fingerprint,
        }
    if bibliographic_match(rruff_fingerprints, cod_fingerprint):
        return "strong", {
            "rruff_fingerprints": rruff_fingerprints,
            "cod_fingerprint": cod_fingerprint,
        }

    cod_year = cod_fingerprint.get("year")
    cod_first = cod_fingerprint.get("page_first")
    cod_last = cod_fingerprint.get("page_last")
    cod_authors = set(cod_fingerprint.get("authors") or [])
    for reference in rruff_fingerprints:
        same_pages = (
            cod_first
            and cod_last
            and reference.get("page_first") == cod_first
            and reference.get("page_last") == cod_last
        )
        same_year = cod_year and reference.get("year") == cod_year
        author_overlap = bool(
            cod_authors & set(reference.get("authors") or [])
        )
        if same_pages or (same_year and author_overlap):
            return "possible", {
                "rruff_fingerprints": rruff_fingerprints,
                "cod_fingerprint": cod_fingerprint,
            }
    return "none", {
        "rruff_fingerprints": rruff_fingerprints,
        "cod_fingerprint": cod_fingerprint,
    }


def _evaluate_candidate(
    target: dict[str, Any],
    record: dict[str, Any],
    query_kinds: list[str] | None = None,
    query_support_count: int = 0,
    query_urls: list[str] | None = None,
    local_reuse: bool = True,
    conflict_inventory: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    signature = _target_signature(target)
    candidate = _candidate_structure(record)
    comparison = compare_candidate(signature, candidate)

    chemistry_status, chemistry = _chemistry_status(
        target.get("ideal_chemistry"),
        record.get("formula"),
    )
    space_group = comparison.get("space_group") or {}
    space_group_status = _space_group_status(space_group)
    cell = comparison.get("cell") or {}
    cell_status = _cell_status(cell)
    bibliography_status, bibliography = _bibliography_evidence(
        target.get("references") or [],
        candidate.get("publication") or {},
    )

    sample_name = "match" if comparison.get("sample_name_match") else (
        "unknown" if not target.get("sample_mineral") or not record.get("mineral_name")
        else "mismatch"
    )
    reference_name = "match" if comparison.get("reference_name_match") else (
        "unknown"
        if not target.get("reference_structure_name") or not record.get("mineral_name")
        else "mismatch"
    )

    score = 0
    score += {"strong": 5, "possible": 2, "none": 0, "unknown": 0}.get(
        bibliography_status,
        0,
    )
    score += {"match": 3, "unknown": 0, "mismatch": 0}.get(reference_name, 0)
    score += {"match": 2, "unknown": 0, "mismatch": 0}.get(sample_name, 0)
    score += {"compatible": 4, "possibly_compatible": 2, "unknown": 0, "incompatible": -5}.get(
        chemistry_status,
        0,
    )
    score += {"equivalent": 4, "same_number_setting_difference": 2, "unknown": 0, "incompatible": -4}.get(
        space_group_status,
        0,
    )
    score += {"compatible": 4, "possibly_compatible": 2, "unknown": 0, "incompatible": -4}.get(
        cell_status,
        0,
    )
    score += min(query_support_count, 3)

    max_length = cell.get("max_length_relative_difference")
    max_angle = cell.get("max_angle_difference")
    structure_group = record.get("structure_fingerprint") or f"cod:{record.get('cod_id')}"
    conflict = (conflict_inventory or {}).get(str(record.get("cod_id")), {})
    difference_classes = sorted(conflict.get("difference_classes") or [])
    review_statuses = sorted(conflict.get("review_statuses") or [])
    version_conflict_review_required = (
        "review_required" in review_statuses
        or bool(
            set(difference_classes)
            & {"true_crystallographic_conflict", "uncertain"}
        )
    )

    return {
        "rruff_id": target.get("target_id"),
        "sample_id": target.get("sample_id") or target.get("target_id"),
        "sample_mineral": target.get("sample_mineral"),
        "reference_structure_name": target.get("reference_structure_name"),
        "source": "COD",
        "cod_id": record.get("cod_id"),
        "file_path": record.get("file_path"),
        "local_reuse": local_reuse,
        "retrieval_query_kinds": sorted(query_kinds or []),
        "retrieval_query_support_count": query_support_count,
        "query_urls": sorted(query_urls or []),
        "parse_status": record.get("parse_status"),
        "parse_warnings": record.get("parse_warnings") or [],
        "sample_name_status": sample_name,
        "reference_name_status": reference_name,
        "chemistry_status": chemistry_status,
        "chemistry_reason": chemistry.get("reason"),
        "chemistry_comparison": chemistry,
        "space_group_status": space_group_status,
        "space_group_comparison": space_group,
        "cell_status": cell_status,
        "cell_comparison": cell,
        "max_length_relative_difference": max_length,
        "max_angle_difference": max_angle,
        "bibliography_status": bibliography_status,
        "bibliography_evidence": bibliography,
        "rank_score": score,
        "structure_group_id": structure_group,
        "candidate_mineral_name": record.get("mineral_name"),
        "candidate_formula": record.get("formula"),
        "candidate_space_group": record.get("space_group"),
        "candidate_cell_a": record.get("cell_a"),
        "candidate_cell_b": record.get("cell_b"),
        "candidate_cell_c": record.get("cell_c"),
        "candidate_atom_count": record.get("atom_count"),
        "local_cod_difference_classes": difference_classes,
        "local_cod_review_statuses": review_statuses,
        "local_cod_version_conflict": version_conflict_review_required,
    }


def _is_local_plausible(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("reference_name_status") == "match"
        or evidence.get("sample_name_status") == "match"
        or evidence.get("bibliography_status") == "strong"
        or evidence.get("chemistry_status") in {"compatible", "possibly_compatible"}
        or evidence.get("space_group_status")
        in {"equivalent", "same_number_setting_difference"}
        or evidence.get("cell_status") in {"compatible", "possibly_compatible"}
    )


def _query_plan(target: dict[str, Any]) -> list[tuple[str, str]]:
    formula = _formula_query(target.get("ideal_chemistry"))
    reference_name = _text(target.get("reference_structure_name"))
    sample_name = _text(target.get("sample_mineral"))
    space_group = _text(target.get("space_group"))
    plan: list[tuple[str, str]] = []

    references = extract_rruff_reference_fingerprints(target.get("references") or [])
    for index, reference in enumerate(references[:2], start=1):
        authors = reference.get("authors") or []
        # COD's public text endpoint is unreliable for numeric-only strings
        # (some such requests are reset by the server).  An author anchor is
        # still a bibliography-stage query; exact year/volume/pages remain
        # evidence checked against parsed CIF metadata.
        citation = str(authors[0]).strip() if authors else ""
        if not citation:
            citation = _text(reference.get("citation_text")) or ""
        if citation:
            plan.append((f"A_bibliography_{index}", citation))

    if reference_name and formula:
        plan.append(("B_reference_name_chemistry", f"{reference_name} {formula}"))
    elif reference_name and space_group:
        plan.append(("B_reference_name_symmetry", f"{reference_name} {space_group}"))

    if sample_name and sample_name != reference_name and formula:
        plan.append(("B_sample_name_chemistry", f"{sample_name} {formula}"))
    elif sample_name and sample_name != reference_name and space_group:
        plan.append(("B_sample_name_symmetry", f"{sample_name} {space_group}"))

    if formula:
        plan.append(("C_chemistry", formula))

    if formula and space_group:
        plan.append(("D_space_group", f"{formula} {space_group}"))

    # A name-only query is deliberately never emitted.
    unique: list[tuple[str, str]] = []
    seen = set()
    for kind, query in plan:
        normalized = (kind, query.strip())
        if normalized[1] and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _run_targeted_queries(
    target: dict[str, Any],
    offline: bool = False,
    session=None,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, list[str]], bool]:
    traces: list[dict[str, Any]] = []
    support: Counter[str] = Counter()
    kinds: dict[str, list[str]] = defaultdict(list)
    broad = False

    for query_kind, query_text in _query_plan(target):
        trace = {
            "rruff_id": target.get("target_id"),
            "sample_id": target.get("sample_id") or target.get("target_id"),
            "query_kind": query_kind,
            "query_text": query_text,
            "status": "pending",
            "candidate_count": 0,
            "cod_ids": [],
            "url": None,
            "error": None,
        }
        if offline:
            trace.update(
                {
                    "status": "skipped_offline",
                    "error": "remote COD query disabled by --offline",
                }
            )
            traces.append(trace)
            continue
        try:
            result = search_cod_targeted(
                query_text,
                query_kind=query_kind,
                session=session,
                request_delay_seconds=COD_REQUEST_DELAY_SECONDS,
            )
            ids = [str(item) for item in result.get("cod_ids") or []]
            trace.update(
                {
                    "status": "ok",
                    "candidate_count": len(ids),
                    "cod_ids": ids,
                    "url": result.get("url"),
                }
            )
            if len(ids) > COD_RECALL_THRESHOLD:
                broad = True
            for cod_id in ids:
                support[cod_id] += 1
                kinds[cod_id].append(query_kind)
        except Exception as exc:
            trace.update(
                {
                    "status": "search_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        traces.append(trace)
    return traces, dict(support), dict(kinds), broad


def _download_shortlist(
    target: dict[str, Any],
    support: dict[str, int],
    query_kinds: dict[str, list[str]],
    query_traces: list[dict[str, Any]],
    broad: bool,
    output_root: Path,
    local_ids: set[str],
    session=None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query_urls = [
        trace.get("url")
        for trace in query_traces
        if trace.get("url")
    ]
    ranked_ids = sorted(
        (
            cod_id
            for cod_id in support
            if cod_id not in local_ids
            and (
                support[cod_id] >= 2
                or any(
                    kind.startswith("A_bibliography")
                    for kind in query_kinds.get(cod_id, [])
                )
            )
        ),
        key=lambda cod_id: (-support[cod_id], cod_id),
    )[:MAX_REMOTE_DOWNLOADS_PER_TARGET]

    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    cod_dir = output_root / "candidates" / "cod"

    for cod_id in ranked_ids:
        path = cod_dir / f"{cod_id}.cif"
        new_download = False
        try:
            if not path.exists():
                download_cod_cif(
                    cod_id,
                    cod_dir,
                    session=session,
                    request_delay_seconds=COD_REQUEST_DELAY_SECONDS,
                )
                new_download = True
            parsed = _parse_one(
                path,
                str(cod_dir),
                "rruff:cif_recovery_v3",
            )
            parsed["cod_id"] = cod_id
            downloaded.append(
                {
                    "record": parsed,
                    "cod_id": cod_id,
                    "query_kinds": query_kinds.get(cod_id, []),
                    "query_support_count": support.get(cod_id, 0),
                    "query_urls": query_urls,
                    "new_download": new_download,
                }
            )
        except Exception as exc:
            failures.append(
                {
                    "cod_id": cod_id,
                    "rruff_id": target.get("target_id"),
                    "error": f"{type(exc).__name__}: {exc}",
                    "manual_folder": str(output_root / "manual_downloads" / "cod"),
                }
            )
    return downloaded, failures


def _deduplicate_evidence(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        cod_id = str(row.get("cod_id"))
        existing = by_id.get(cod_id)
        if existing is None or row.get("rank_score", -999) > existing.get("rank_score", -999):
            by_id[cod_id] = row
        elif existing is not None:
            existing["retrieval_query_kinds"] = sorted(
                set(existing.get("retrieval_query_kinds") or [])
                | set(row.get("retrieval_query_kinds") or [])
            )
            existing["query_urls"] = sorted(
                set(existing.get("query_urls") or [])
                | set(row.get("query_urls") or [])
            )
            existing["retrieval_query_support_count"] = max(
                existing.get("retrieval_query_support_count", 0),
                row.get("retrieval_query_support_count", 0),
            )
    return list(by_id.values())


def _attach_diffraction_evidence(
    target_id: str,
    evidence_rows: list[dict[str, Any]],
    diffraction_history: dict[str, dict[str, dict[str, Any]]],
) -> int:
    history = diffraction_history.get(target_id, {})
    evaluated = 0
    for row in evidence_rows:
        item = history.get(str(row.get("cod_id")))
        if item:
            row["diffraction_status"] = item.get("status")
            row["diffraction_metrics"] = item.get("metrics") or {}
            row["diffraction_history_source"] = item.get("source")
            evaluated += 1
        else:
            row["diffraction_status"] = "not_historically_evaluated"
            row["diffraction_metrics"] = {}
            row["diffraction_history_source"] = None
    return evaluated


def _attach_retrieval_support(
    evidence_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Annotate and retain the staged set-intersection evidence."""

    kept: list[dict[str, Any]] = []
    for row in evidence_rows:
        support_sets = []
        if row.get("reference_name_status") == "match":
            support_sets.append("C_reference_name")
        if row.get("sample_name_status") == "match":
            support_sets.append("C_sample_name")
        if row.get("chemistry_status") in {
            "compatible",
            "possibly_compatible",
        }:
            support_sets.append("C_chemistry")
        if row.get("space_group_status") in {
            "equivalent",
            "same_number_setting_difference",
        }:
            support_sets.append("C_space_group")
        if row.get("cell_status") in {"compatible", "possibly_compatible"}:
            support_sets.append("C_cell")
        if row.get("bibliography_status") in {"strong", "possible"}:
            support_sets.append("C_bibliography")

        row["retrieval_support_sets"] = support_sets
        row["retrieval_support_count"] = len(support_sets)

        chemistry_ok = "C_chemistry" in support_sets
        space_group_ok = "C_space_group" in support_sets
        cell_ok = "C_cell" in support_sets
        bibliography_ok = "C_bibliography" in support_sets
        reference_name_ok = "C_reference_name" in support_sets
        structural_count = sum(
            value for value in (chemistry_ok, space_group_ok, cell_ok)
        )

        # Keep intersections supported by multiple independent dimensions.
        # A bibliography hit alone or a name/formula hit alone is never a
        # surviving v3 candidate.
        retain = (
            structural_count >= 3
            or (bibliography_ok and structural_count >= 1)
            or (
                reference_name_ok
                and chemistry_ok
                and space_group_ok
                and cell_ok
            )
        )
        if retain and not row.get("local_cod_version_conflict"):
            kept.append(row)
    return kept


def _defensible_candidate(row: dict[str, Any]) -> bool:
    """Require combined evidence; formula/name alone is never sufficient."""

    if row.get("local_cod_version_conflict"):
        return False
    chemistry_ok = row.get("chemistry_status") in {
        "compatible",
        "possibly_compatible",
    }
    space_group_ok = row.get("space_group_status") in {
        "equivalent",
        "same_number_setting_difference",
    }
    cell_ok = row.get("cell_status") in {
        "compatible",
        "possibly_compatible",
    }
    strong_bibliography = (
        row.get("bibliography_status") == "strong"
        and chemistry_ok
        and (space_group_ok or cell_ok)
    )
    full_structural_match = (
        row.get("reference_name_status") == "match"
        and chemistry_ok
        and space_group_ok
        and cell_ok
    )
    return strong_bibliography or full_structural_match


def _propose_resolution(
    evidence_rows: list[dict[str, Any]],
    broad: bool,
    search_failed: bool,
    require_diffraction: bool = False,
) -> tuple[str, str, list[dict[str, Any]], list[list[str]]]:
    ranked = sorted(
        evidence_rows,
        key=lambda row: (
            -row.get("rank_score", -999),
            row.get("cod_id") or "",
        ),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank_position"] = index

    structurally_plausible = [
        row
        for row in ranked
        if row.get("chemistry_status") != "incompatible"
        and row.get("space_group_status") != "incompatible"
        and row.get("cell_status") != "incompatible"
        and not row.get("local_cod_version_conflict")
    ]
    plausible = [
        row
        for row in structurally_plausible
        if (
            not require_diffraction
            or row.get("diffraction_status") == "historically_evaluated"
        )
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plausible:
        groups[row.get("structure_group_id") or f"cod:{row.get('cod_id')}"].append(row)
    group_lists = [
        [row.get("cod_id") for row in items]
        for items in sorted(groups.values(), key=lambda items: str(items[0].get("cod_id")))
    ]

    if not ranked:
        status = "search_failed" if search_failed else "no_candidate"
        return "unlinked", status, ranked, group_lists
    if not structurally_plausible:
        if any(row.get("local_cod_version_conflict") for row in ranked):
            return "review", "local_cod_version_conflict_requires_review", ranked, group_lists
        return "unlinked", "all_candidates_conflict_with_structured_evidence", ranked, group_lists
    if not plausible:
        return "review", "diffraction_validation_unavailable", ranked, group_lists
    if len(groups) > 1:
        return "review", "multiple_distinct_supported_structure_groups", ranked, group_lists
    defensible = [row for row in plausible if _defensible_candidate(row)]
    if len(plausible) == 1 and len(defensible) == 1:
        return "record", "one_supported_candidate_record", ranked, group_lists
    if len(groups) == 1 and defensible:
        return "group", "one_supported_structure_group_multiple_records", ranked, group_lists
    if len(plausible) == 1:
        return "review", "single_candidate_lacks_combined_evidence", ranked, group_lists
    return "review", "multiple_plausible_records_require_human_review", ranked, group_lists


def _manual_priority(
    resolution: str,
    reason: str,
    broad: bool,
    download_failures: list[dict[str, Any]],
) -> str:
    if download_failures or reason == "search_failed":
        return "P1"
    if resolution == "unlinked":
        return "P1"
    if broad:
        return "P2"
    if resolution == "review":
        return "P2"
    if resolution == "group":
        return "P3"
    return "P4"


def _candidate_row_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    for key in (
        "retrieval_query_kinds",
        "query_urls",
        "parse_warnings",
        "chemistry_comparison",
        "space_group_comparison",
        "cell_comparison",
        "bibliography_evidence",
        "local_cod_difference_classes",
        "local_cod_review_statuses",
        "diffraction_metrics",
    ):
        output[key] = _json(output.get(key) or [])
    return output


def _manual_rows(
    target: dict[str, Any],
    ranked: list[dict[str, Any]],
    resolution: str,
    reason: str,
    broad: bool,
    broad_evidence_source: str,
    query_traces: list[dict[str, Any]],
    download_failures: list[dict[str, Any]],
    group_lists: list[list[str]],
    output_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    priority = _manual_priority(
        resolution,
        reason,
        broad,
        download_failures,
    )
    query_urls = sorted(
        {
            trace.get("url")
            for trace in query_traces
            if trace.get("url")
        }
    )
    candidate_ids = [row.get("cod_id") for row in ranked]
    manual_needed = (
        resolution != "record"
        or broad
        or bool(download_failures)
        or not ranked
    )
    queue_row = {
        "rruff_id": target.get("target_id"),
        "sample_id": target.get("sample_id") or target.get("target_id"),
        "filename_sample_id": target.get("filename_sample_id"),
        "sample_mineral": target.get("sample_mineral"),
        "reference_structure_name": target.get("reference_structure_name"),
        "ideal_chemistry": target.get("ideal_chemistry"),
        "space_group": target.get("space_group"),
        "cell_a": target.get("cell_parameters", {}).get("a"),
        "cell_b": target.get("cell_parameters", {}).get("b"),
        "cell_c": target.get("cell_parameters", {}).get("c"),
        "cell_alpha": target.get("cell_parameters", {}).get("alpha"),
        "cell_beta": target.get("cell_parameters", {}).get("beta"),
        "cell_gamma": target.get("cell_parameters", {}).get("gamma"),
        "resolution": resolution,
        "retrieval_status": "metadata_only_broad" if broad else (
            "download_failed" if download_failures else "evaluated"
        ),
        "manual_priority": priority,
        "manual_needed": manual_needed,
        "reason": reason,
        "cod_recall_over_100": broad,
        "cod_recall_evidence_source": broad_evidence_source,
        "candidate_cod_ids": _json(candidate_ids),
        "near_equivalent_candidate_groups": _json(group_lists),
        "cod_query_urls": _json(query_urls),
        "amcsd_search_url": MANUAL_AMCSD_HOME,
        "amcsd_url_status": "manual_homepage_only_not_record_verified",
        "manual_download_folder_cod": str(output_root / "manual_downloads" / "cod"),
        "manual_download_folder_amcsd": str(output_root / "manual_downloads" / "amcsd"),
        "download_failures": _json(download_failures),
        "rruff_references": _json(target.get("references") or []),
    }

    page_rows = []
    for row in ranked[:50]:
        for url in row.get("query_urls") or query_urls:
            page_rows.append(
                {
                    "rruff_id": target.get("target_id"),
                    "sample_id": target.get("sample_id") or target.get("target_id"),
                    "sample_mineral": target.get("sample_mineral"),
                    "reference_structure_name": target.get("reference_structure_name"),
                    "source": "COD",
                    "source_id": row.get("cod_id"),
                    "page_url": url,
                    "url_kind": "executed_cod_query",
                    "url_status": "verified_by_successful_cod_response",
                    "local_file_path": row.get("file_path"),
                    "manual_download_folder": str(output_root / "manual_downloads" / "cod"),
                }
            )
    if manual_needed:
        page_rows.append(
            {
                "rruff_id": target.get("target_id"),
                "sample_id": target.get("sample_id") or target.get("target_id"),
                "sample_mineral": target.get("sample_mineral"),
                "reference_structure_name": target.get("reference_structure_name"),
                "source": "AMCSd",
                "source_id": "",
                "page_url": MANUAL_AMCSD_HOME,
                "url_kind": "amcsd_manual_homepage",
                "url_status": "homepage_only_record_url_not_verified",
                "local_file_path": "",
                "manual_download_folder": str(output_root / "manual_downloads" / "amcsd"),
            }
        )
    return queue_row, page_rows


def _target_output_row(
    target: dict[str, Any],
    traces: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    resolution: str,
    reason: str,
    retrieval_status: str,
    broad: bool,
    broad_evidence_source: str,
    group_lists: list[list[str]],
    v2_row: dict[str, str],
) -> dict[str, Any]:
    top = ranked[0] if ranked else {}
    return {
        "target_id": target.get("target_id"),
        "sample_id": target.get("sample_id") or target.get("target_id"),
        "rruff_id": target.get("target_id"),
        "sample_mineral": target.get("sample_mineral"),
        "reference_structure_name": target.get("reference_structure_name"),
        "ideal_chemistry": target.get("ideal_chemistry"),
        "normalized_chemistry": target.get("normalized_chemistry")
        or target.get("ideal_chemistry"),
        "profile_origin": target.get("xy_origin"),
        "has_xy": target.get("has_xy"),
        "wavelength": target.get("wavelength"),
        "space_group": target.get("space_group"),
        "cell_parameters": _json(target.get("cell_parameters") or {}),
        "atom_count": target.get("atom_count"),
        "source_record_identity": target.get("source_record_identity"),
        "retrieval_status": retrieval_status,
        "resolution": resolution,
        "resolution_reason": reason,
        "candidate_count": len(ranked),
        "candidate_cod_ids": _json([row.get("cod_id") for row in ranked]),
        "candidate_structures": _json(
            [
                {
                    "source": row.get("source"),
                    "source_id": row.get("cod_id"),
                    "file_path": row.get("file_path"),
                    "rank_score": row.get("rank_score"),
                }
                for row in ranked
            ]
        ),
        "top_cod_id": top.get("cod_id"),
        "top_rank_score": top.get("rank_score"),
        "top_bibliography_status": top.get("bibliography_status"),
        "top_chemistry_status": top.get("chemistry_status"),
        "top_space_group_status": top.get("space_group_status"),
        "top_cell_status": top.get("cell_status"),
        "top_diffraction_status": top.get("diffraction_status"),
        "top_diffraction_metrics": _json(top.get("diffraction_metrics") or {}),
        "local_cod_version_conflict": bool(
            top.get("local_cod_version_conflict")
        ),
        "cod_recall_over_100": broad,
        "cod_recall_evidence_source": broad_evidence_source,
        "cod_cif_suppressed_for_raw_broad_results": broad,
        "cod_recall_counts": _json(
            {
                trace.get("query_kind"): trace.get("candidate_count")
                for trace in traces
            }
        ),
        "cod_query_urls": _json(
            sorted({trace.get("url") for trace in traces if trace.get("url")})
        ),
        "near_equivalent_candidate_group": _json(group_lists),
        "rruff_references": _json(target.get("references") or []),
        "v2_relation_status_comparison_only": v2_row.get("relation_status"),
        "v2_accepted_source_id_comparison_only": v2_row.get("accepted_source_id"),
        "v2_cod_recall_count_comparison_only": v2_row.get("cod_recall_count"),
        "diffraction_status": "deferred_to_existing_calibrated_pipeline",
        "diffraction_pipeline_reference": "scripts/annotate_rruff_group_diffraction_v1.py",
    }


def _write_pilot_report(
    output_root: Path,
    mode: str,
    target_ids: list[str],
    categories: dict[str, list[str]],
    target_rows: list[dict[str, Any]],
    query_traces: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    manual_rows: list[dict[str, Any]],
    inventory_summary: dict[str, Any] | None,
) -> None:
    report_path = output_root / "reports" / "pilot_report_v3.md"
    counts = Counter(row.get("resolution") for row in target_rows)
    retrieval_counts = Counter(row.get("retrieval_status") for row in target_rows)
    broad_ids = [
        row.get("target_id")
        for row in target_rows
        if row.get("cod_recall_over_100")
    ]
    query_status = Counter(trace.get("status") for trace in query_traces)
    lines = [
        "# RRUFF CIF Recovery v3 Pilot Report",
        "",
        f"- mode: `{mode}`",
        f"- target count: `{len(target_ids)}`",
        "- candidate source policy: local inventory first; targeted COD fallback only",
        "- old selected structures: comparison only, not v3 candidate input",
        "- AMCSd: manual URL/sample metadata only; no automatic CIF retrieval",
        "",
        "## Local Inventory",
        "",
        f"- inventory file: `{output_root / 'cod_local_inventory_v3.csv'}`",
        f"- inventory summary: `{inventory_summary or {}}`",
        "",
        "## Pilot Stratification",
        "",
    ]
    for category, items in categories.items():
        lines.append(f"- {category}: {', '.join(items) if items else '(none)'}")
    lines.extend(
        [
            "",
            "## Retrieval Trace",
            "",
            f"- query status counts: `{dict(query_status)}`",
            f"- broad recall targets (> {COD_RECALL_THRESHOLD}): "
            f"{', '.join(broad_ids) if broad_ids else '(none)'}",
            (
                "- offline pilot broad flags inherited from v2 are explicitly "
                "marked `v2_comparison_only_offline_placeholder`; an online "
                "rerun replaces them with v3 query counts."
            )
            if any(
                row.get("cod_recall_evidence_source")
                == "v2_comparison_only_offline_placeholder"
                for row in target_rows
            )
            else "",
            "- A: bibliography query; B: name plus chemistry/symmetry; "
            "C: chemistry plus space group; D: local cell-assisted rescue.",
            "- A name-only COD query is never emitted.",
            "",
            "## Proposed Resolution",
            "",
            f"- resolutions: `{dict(counts)}`",
            f"- retrieval statuses: `{dict(retrieval_counts)}`",
            f"- manual queue rows: `{len(manual_rows)}`",
            "",
            "| RRUFF ID | Resolution | Retrieval | Candidates | Broad | Top COD |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for row in target_rows:
        lines.append(
            "| {target_id} | {resolution} | {retrieval_status} | "
            "{candidate_count} | {broad} | {top_cod_id} |".format(
                target_id=row.get("target_id"),
                resolution=row.get("resolution"),
                retrieval_status=row.get("retrieval_status"),
                candidate_count=row.get("candidate_count"),
                broad=row.get("cod_recall_over_100"),
                top_cod_id=row.get("top_cod_id") or "",
            )
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- v2 manifests remain unchanged.",
            "- No accepted CIF directory is written by this pilot.",
            "- `rank_score` is an ordering aid, not a probability.",
            "- CIF diffraction validation is deliberately delegated to the existing "
            "calibrated pipeline and was not reimplemented here.",
            "- For broad COD recall, the RRUFF ID is marked and raw broad-result "
            "CIFs are not downloaded; only locally represented IDs or narrowed "
            "shortlists may be reused/downloaded.",
            "",
            "## Output Files",
            "",
            f"- targets: `{output_root / 'manifests' / 'rruff_targets_v3.csv'}`",
            f"- retrieval trace: `{output_root / 'manifests' / 'retrieval_trace_v3.jsonl'}`",
            f"- candidate evidence: `{output_root / 'manifests' / 'candidate_evidence_v3.jsonl'}`",
            f"- links/reconciliation: `{output_root / 'manifests' / 'rruff_cif_links_v3.csv'}`",
            f"- broad-recall marks: `{output_root / 'manifests' / 'cod_recall_over_100_marks_v3.csv'}`",
            f"- manual queue: `{output_root / 'manifests' / 'rruff_manual_resolution_queue_v3.csv'}`",
            f"- manual pages: `{output_root / 'manifests' / 'rruff_manual_candidate_pages_v3.csv'}`",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    mode: str,
    output_root: Path,
    targets_path: Path,
    v2_root: Path,
    inventory_path: Path,
    offline: bool = False,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    if mode == "full":
        gate_path = output_root / "reports" / "pilot_gate_v3.json"
        if not gate_path.exists():
            raise RuntimeError(
                "Full run is gated: pilot_gate_v3.json is missing. "
                "Run and pass the online pilot first."
            )
        try:
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Full run is gated: cannot parse {gate_path}"
            ) from exc
        if gate.get("pilot_pass") is not True:
            raise RuntimeError(
                "Full run is gated: the online pilot did not pass all gates."
            )
    targets = _load_targets(targets_path)
    v2_links, v2_broad = _load_v2_comparison(v2_root)
    if mode == "pilot":
        existing_selection = _load_existing_pilot_selection(
            output_root / "manifests" / "pilot_selection_v3.json",
            targets,
        )
        if existing_selection is not None:
            target_ids, categories = existing_selection
        else:
            target_ids, categories = _select_pilot_targets(
                targets,
                v2_links,
                v2_broad,
            )
    else:
        target_ids = sorted(targets, key=_stable_key)
        categories = {"full_run": target_ids}

    if not inventory_path.exists():
        raise FileNotFoundError(
            f"Local COD inventory is required before retrieval: {inventory_path}"
        )
    local_records, local_copies = _load_inventory(inventory_path)
    conflict_inventory = _load_conflict_inventory(CONFLICT_INVENTORY)
    diffraction_history = _load_diffraction_history()
    experimental_resolution_ids = _load_experimental_resolution_ids()
    session = None if offline else build_cod_session(trust_env=False)
    (output_root / "reports").mkdir(parents=True, exist_ok=True)
    (output_root / "reports" / "run_environment_v3.json").write_text(
        json.dumps(
            _run_environment(
                mode=mode,
                offline=offline,
                target_count=len(target_ids),
                inventory_path=inventory_path,
                conflict_path=CONFLICT_INVENTORY,
            ),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    selected_targets = [targets[target_id] for target_id in target_ids if target_id in targets]
    target_manifest_rows = []
    for target in selected_targets:
        row = dict(target)
        row["rruff_id"] = target["target_id"]
        row["normalized_chemistry"] = (
            target.get("normalized_chemistry")
            or target.get("ideal_chemistry")
        )
        row["profile_origin"] = target.get("xy_origin")
        row["pilot_category"] = next(
            (
                category
                for category, items in categories.items()
                if target["target_id"] in items
            ),
            "full_run",
        )
        row["references"] = _json(target.get("references") or [])
        row["cell_parameters"] = _json(target.get("cell_parameters") or {})
        target_manifest_rows.append(row)
    _write_csv(
        output_root / "manifests" / "rruff_targets_v3.csv",
        [
            "target_id",
            "rruff_id",
            "sample_id",
            "filename_sample_id",
            "sample_mineral",
            "reference_structure_name",
            "ideal_chemistry",
            "normalized_chemistry",
            "space_group",
            "cell_parameters",
            "atom_count",
            "references",
            "has_xy",
            "xy_origin",
            "profile_origin",
            "wavelength",
            "source_record_identity",
            "priority",
            "pilot_category",
        ],
        target_manifest_rows,
    )
    (output_root / "manifests" / "pilot_selection_v3.json").write_text(
        json.dumps(
            {
                "workflow": "RRUFF CIF recovery v3",
                "mode": mode,
                "selection_size": len(target_ids),
                "target_ids": target_ids,
                "categories": categories,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    all_traces: list[dict[str, Any]] = []
    all_candidate_evidence: list[dict[str, Any]] = []
    all_links: list[dict[str, Any]] = []
    all_manual_queue: list[dict[str, Any]] = []
    all_manual_pages: list[dict[str, Any]] = []
    broad_marks: list[dict[str, Any]] = []
    retrieval_summary_rows: list[dict[str, Any]] = []

    for index, target in enumerate(selected_targets, start=1):
        target_id = target["target_id"]
        print(f"[v3] processing {index}/{len(selected_targets)} {target_id}")
        historical_broad = target_id in v2_broad
        local_evidence: list[dict[str, Any]] = []

        # Local evidence is evaluated before any remote COD request.
        for record in local_records.values():
            if record.get("parse_status") not in {"ok", "partial"}:
                continue
            evidence = _evaluate_candidate(
                target,
                record,
                conflict_inventory=conflict_inventory,
            )
            if _is_local_plausible(evidence):
                local_evidence.append(evidence)
        local_evidence.sort(
            key=lambda row: (-row.get("rank_score", -999), row.get("cod_id") or "")
        )
        local_evidence = local_evidence[:MAX_LOCAL_CANDIDATES]

        local_cell_rescue = [
            evidence
            for evidence in local_evidence
            if evidence.get("cell_status")
            in {"compatible", "possibly_compatible"}
            and evidence.get("chemistry_status") != "incompatible"
            and evidence.get("space_group_status") != "incompatible"
        ]
        for evidence in local_cell_rescue:
            evidence["retrieval_query_kinds"] = sorted(
                set(evidence.get("retrieval_query_kinds") or [])
                | {"D_local_cell_assisted_rescue"}
            )
            evidence["retrieval_query_support_count"] = max(
                evidence.get("retrieval_query_support_count", 0),
                1,
            )
        local_trace = {
            "rruff_id": target_id,
            "sample_id": target.get("sample_id") or target_id,
            "query_kind": "D_local_cell_assisted_rescue",
            "query_text": "",
            "status": "local_inventory",
            "candidate_count": len(local_cell_rescue),
            "cod_ids": [
                evidence.get("cod_id")
                for evidence in local_cell_rescue
            ],
            "url": None,
            "error": None,
        }

        traces, support, query_kinds, v3_broad = _run_targeted_queries(
            target,
            offline=offline,
            session=session,
        )
        traces.insert(0, local_trace)
        broad = v3_broad or (offline and historical_broad)
        broad_evidence_source = (
            "v3_targeted_cod_query"
            if v3_broad
            else (
                "v2_comparison_only_offline_placeholder"
                if historical_broad and offline
                else "not_broad"
            )
        )
        all_traces.extend(traces)
        local_ids = set(local_records)

        downloaded, download_failures = _download_shortlist(
            target,
            support,
            query_kinds,
            traces,
            broad,
            output_root,
            local_ids,
            session=session,
        )
        for item in downloaded:
            record = item["record"]
            local_records[item["cod_id"]] = record
            local_copies.setdefault(item["cod_id"], []).append(record)
            local_evidence.append(
                _evaluate_candidate(
                    target,
                    record,
                    query_kinds=item["query_kinds"],
                    query_support_count=item["query_support_count"],
                    query_urls=item["query_urls"],
                    local_reuse=not item.get("new_download", False),
                    conflict_inventory=conflict_inventory,
                )
            )

        # Attach query support to already-local records, without downloading.
        enriched_local = []
        for evidence in local_evidence:
            cod_id = str(evidence.get("cod_id"))
            if cod_id in support:
                record = local_records.get(cod_id)
                if record:
                    evidence = _evaluate_candidate(
                        target,
                        record,
                        query_kinds=query_kinds.get(cod_id, []),
                        query_support_count=support.get(cod_id, 0),
                        query_urls=[
                            trace.get("url")
                            for trace in traces
                            if trace.get("url")
                            and trace.get("query_kind")
                            in query_kinds.get(cod_id, [])
                        ],
                        conflict_inventory=conflict_inventory,
                    )
            enriched_local.append(evidence)

        evidence_rows = _deduplicate_evidence(enriched_local)
        diffraction_evaluated_count = _attach_diffraction_evidence(
            target_id,
            evidence_rows,
            diffraction_history,
        )
        resolution, reason, ranked, group_lists = _propose_resolution(
            evidence_rows,
            broad,
            any(trace.get("status") == "search_failed" for trace in traces),
            require_diffraction=(
                not offline
                and str(target.get("has_xy") or "").strip().lower()
                in {"true", "1", "yes"}
            ),
        )
        for row in ranked:
            row["cod_recall_over_100"] = broad
            all_candidate_evidence.append(_candidate_row_for_csv(row))

        if broad:
            broad_marks.append(
                {
                    "rruff_id": target_id,
                    "sample_id": target.get("sample_id") or target_id,
                    "sample_mineral": target.get("sample_mineral"),
                    "cod_recall_over_100": True,
                    "cod_recall_evidence_source": broad_evidence_source,
                    "cod_recall_threshold": COD_RECALL_THRESHOLD,
                    "historical_v2_cod_recall_count": v2_links.get(target_id, {}).get(
                        "cod_recall_count"
                    ),
                    "max_query_candidate_count": max(
                        (
                            trace.get("candidate_count", 0)
                            for trace in traces
                            if trace.get("status") != "local_inventory"
                        ),
                        default=0,
                    ),
                    "query_counts": _json(
                        {
                            trace.get("query_kind"): trace.get("candidate_count")
                            for trace in traces
                        }
                    ),
                    "cod_cif_suppressed_for_raw_broad_results": True,
                    "cod_recall_action": "marked_rruff_id_and_narrowed_shortlist_only",
                }
            )

        query_statuses = [trace.get("status") for trace in traces]
        remote_query_statuses = [
            status
            for status in query_statuses
            if status != "local_inventory"
        ]
        remote_ids = {
            str(cod_id)
            for trace in traces
            if trace.get("status") == "ok"
            for cod_id in trace.get("cod_ids") or []
        }
        if offline or (
            remote_query_statuses
            and all(status == "skipped_offline" for status in remote_query_statuses)
        ):
            retrieval_status = "remote_search_unavailable"
        elif any(status == "search_failed" for status in remote_query_statuses):
            retrieval_status = "search_failed"
        elif download_failures:
            retrieval_status = "download_failed"
        elif not remote_ids and not local_evidence:
            retrieval_status = "no_remote_candidate"
        elif broad and len(ranked) > COD_RECALL_THRESHOLD:
            retrieval_status = "too_broad_after_refinement"
        else:
            retrieval_status = "ok"

        queue_row, page_rows = _manual_rows(
            target,
            ranked,
            resolution,
            reason,
            broad,
            broad_evidence_source,
            traces,
            download_failures,
            group_lists,
            output_root,
        )
        if queue_row["manual_needed"]:
            all_manual_queue.append(queue_row)
        all_manual_pages.extend(page_rows)

        def _max_query_count(prefixes: tuple[str, ...]) -> int:
            return max(
                (
                    int(trace.get("candidate_count") or 0)
                    for trace in traces
                    if any(
                        str(trace.get("query_kind") or "").startswith(prefix)
                        for prefix in prefixes
                    )
                ),
                default=0,
            )

        retrieval_summary_rows.append(
            {
                "rruff_id": target_id,
                "sample_mineral": target.get("sample_mineral"),
                "reference_structure_name": target.get(
                    "reference_structure_name"
                ),
                "local_candidate_count": len(
                    {str(row.get("cod_id")) for row in local_evidence}
                ),
                "remote_reference_name_count": _max_query_count(
                    ("B_reference_name",)
                ),
                "remote_sample_name_count": _max_query_count(
                    ("B_sample_name",)
                ),
                "remote_chemistry_count": _max_query_count(("C_chemistry",)),
                "remote_bibliography_count": _max_query_count(
                    ("A_bibliography",)
                ),
                "chemistry_supported_count": sum(
                    row.get("chemistry_status")
                    in {"compatible", "possibly_compatible"}
                    for row in evidence_rows
                ),
                "space_group_supported_count": sum(
                    row.get("space_group_status")
                    in {"equivalent", "same_number_setting_difference"}
                    for row in evidence_rows
                ),
                "cell_supported_count": sum(
                    row.get("cell_status")
                    in {"compatible", "possibly_compatible"}
                    for row in evidence_rows
                ),
                "bibliography_supported_count": sum(
                    row.get("bibliography_status") == "strong"
                    for row in evidence_rows
                ),
                "final_candidate_count": len(ranked),
                "structure_group_count": len(group_lists),
                "downloaded_new_cif_count": sum(
                    bool(item.get("new_download")) for item in downloaded
                ),
                "local_reused_cif_count": sum(
                    bool(row.get("local_reuse")) for row in evidence_rows
                ),
                "diffraction_evaluated_count": diffraction_evaluated_count,
                "v3_resolution": resolution,
                "manual_required": bool(queue_row.get("manual_needed")),
                "manual_reason": reason if queue_row.get("manual_needed") else "",
            }
        )

        all_links.append(
            _target_output_row(
                target,
                traces,
                ranked,
                resolution,
                reason,
                retrieval_status,
                broad,
                broad_evidence_source,
                group_lists,
                v2_links.get(target_id, {}),
            )
        )

    _write_jsonl(output_root / "manifests" / "retrieval_trace_v3.jsonl", all_traces)
    _write_jsonl(
        output_root / "manifests" / "candidate_evidence_v3.jsonl",
        all_candidate_evidence,
    )
    _write_csv(
        output_root / "manifests" / "retrieval_trace_v3.csv",
        [
            "rruff_id",
            "sample_id",
            "query_kind",
            "query_text",
            "status",
            "candidate_count",
            "cod_ids",
            "url",
            "error",
        ],
        [
            {
                **trace,
                "cod_ids": _json(trace.get("cod_ids") or []),
            }
            for trace in all_traces
        ],
    )
    _write_csv(
        output_root / "manifests" / "pilot_online_retrieval_trace_v3.csv",
        [
            "rruff_id",
            "sample_mineral",
            "reference_structure_name",
            "local_candidate_count",
            "remote_reference_name_count",
            "remote_sample_name_count",
            "remote_chemistry_count",
            "remote_bibliography_count",
            "chemistry_supported_count",
            "space_group_supported_count",
            "cell_supported_count",
            "bibliography_supported_count",
            "final_candidate_count",
            "structure_group_count",
            "downloaded_new_cif_count",
            "local_reused_cif_count",
            "diffraction_evaluated_count",
            "v3_resolution",
            "manual_required",
            "manual_reason",
        ],
        retrieval_summary_rows,
    )
    candidate_fields = [
        "rruff_id",
        "sample_id",
        "sample_mineral",
        "reference_structure_name",
        "source",
        "cod_id",
        "file_path",
        "local_reuse",
        "retrieval_query_kinds",
        "retrieval_query_support_count",
        "query_urls",
        "parse_status",
        "parse_warnings",
        "sample_name_status",
        "reference_name_status",
        "chemistry_status",
        "chemistry_reason",
        "chemistry_comparison",
        "space_group_status",
        "space_group_comparison",
        "cell_status",
        "cell_comparison",
        "max_length_relative_difference",
        "max_angle_difference",
        "bibliography_status",
        "bibliography_evidence",
        "rank_score",
        "rank_position",
        "structure_group_id",
        "candidate_mineral_name",
        "candidate_formula",
        "candidate_space_group",
        "candidate_cell_a",
        "candidate_cell_b",
        "candidate_cell_c",
        "candidate_atom_count",
        "local_cod_difference_classes",
        "local_cod_review_statuses",
        "local_cod_version_conflict",
        "diffraction_status",
        "diffraction_metrics",
        "diffraction_history_source",
        "cod_recall_over_100",
    ]
    _write_csv(
        output_root / "manifests" / "candidate_evidence_v3.csv",
        candidate_fields,
        all_candidate_evidence,
    )
    _write_csv(
        output_root / "manifests" / "rruff_cif_links_v3.csv",
        list(all_links[0].keys()) if all_links else ["target_id"],
        all_links,
    )
    _write_csv(
        output_root / "manifests" / "cod_recall_over_100_marks_v3.csv",
        [
            "rruff_id",
            "sample_id",
            "sample_mineral",
            "cod_recall_over_100",
            "cod_recall_threshold",
            "cod_recall_evidence_source",
            "historical_v2_cod_recall_count",
            "max_query_candidate_count",
            "query_counts",
            "cod_cif_suppressed_for_raw_broad_results",
            "cod_recall_action",
        ],
        broad_marks,
    )
    _write_csv(
        output_root / "manifests" / "rruff_manual_resolution_queue_v3.csv",
        list(all_manual_queue[0].keys()) if all_manual_queue else [
            "rruff_id",
            "sample_id",
            "manual_needed",
        ],
        all_manual_queue,
    )
    _write_csv(
        output_root / "manifests" / "rruff_manual_candidate_pages_v3.csv",
        list(all_manual_pages[0].keys()) if all_manual_pages else [
            "rruff_id",
            "source",
            "page_url",
        ],
        all_manual_pages,
    )

    amcsd_rows = [
        {
            "rruff_id": target.get("target_id"),
            "sample_id": target.get("sample_id") or target.get("target_id"),
            "sample_mineral": target.get("sample_mineral"),
            "reference_structure_name": target.get("reference_structure_name"),
            "ideal_chemistry": target.get("ideal_chemistry"),
            "space_group": target.get("space_group"),
            "amcsd_search_url": MANUAL_AMCSD_HOME,
            "amcsd_status": "manual_url_and_sample_metadata_only",
            "cif_retrieval": "disabled",
        }
        for target in selected_targets
    ]
    _write_csv(
        output_root / "manifests" / "amcsd_metadata_v3.csv",
        list(amcsd_rows[0].keys()) if amcsd_rows else ["rruff_id"],
        amcsd_rows,
    )

    inventory_summary = None
    summary_path = output_root / "reports" / "inventory_summary_v3.json"
    if summary_path.exists():
        inventory_summary = _parse_json(summary_path.read_text(encoding="utf-8"), {})
    _write_pilot_report(
        output_root,
        mode,
        target_ids,
        categories,
        all_links,
        all_traces,
        all_candidate_evidence,
        all_manual_queue,
        inventory_summary,
    )

    run_summary = {
        "workflow": "RRUFF CIF recovery v3",
        "mode": mode,
        "target_count": len(selected_targets),
        "candidate_evidence_rows": len(all_candidate_evidence),
        "query_count": len(all_traces),
        "query_status_counts": dict(Counter(trace.get("status") for trace in all_traces)),
        "resolution_counts": dict(Counter(row.get("resolution") for row in all_links)),
        "retrieval_status_counts": dict(
            Counter(row.get("retrieval_status") for row in all_links)
        ),
        "broad_recall_target_count": len(broad_marks),
        "manual_queue_count": len(all_manual_queue),
        "retrieval_trace_file": str(
            output_root / "manifests" / "pilot_online_retrieval_trace_v3.csv"
        ),
        "conflict_inventory": {
            "path": str(CONFLICT_INVENTORY),
            "cod_id_count": len(conflict_inventory),
            "review_required_cod_id_count": sum(
                any(
                    status == "review_required"
                    for status in item.get("review_statuses") or []
                )
                for item in conflict_inventory.values()
            ),
        },
        "diffraction_history": {
            "target_count": len(diffraction_history),
            "experimental_resolution_target_count": len(
                experimental_resolution_ids
            ),
            "candidate_metric_rows": sum(
                len(items) for items in diffraction_history.values()
            ),
        },
        "local_reuse": {
            "inventory_path": str(inventory_path),
            "new_remote_cif_files": sum(
                row.get("downloaded_new_cif_count", 0)
                for row in retrieval_summary_rows
            ),
            "local_reused_cif_records": sum(
                row.get("local_reused_cif_count", 0)
                for row in retrieval_summary_rows
            ),
        },
        "safety": {
            "v2_modified": False,
            "crystaldb_mongo_modified": False,
            "old_selected_structures_used_as_v3_candidates": False,
            "amcsd_cif_download_enabled": False,
            "diffraction_pipeline_reimplemented": False,
            "remote_queries_skipped_offline": offline,
            "tls_verification_disabled": False,
            "paper_modified": False,
        },
    }
    (output_root / "reports" / "rruff_cif_recovery_v3_summary.json").write_text(
        json.dumps(run_summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(run_summary, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--targets", type=Path, default=TARGETS_V2)
    parser.add_argument("--v2-root", type=Path, default=V2_ROOT)
    parser.add_argument("--inventory", type=Path, default=LOCAL_INVENTORY)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip remote COD queries and run the local-evidence pilot only.",
    )
    args = parser.parse_args()
    run(
        mode=args.mode,
        output_root=args.output_root.resolve(),
        targets_path=args.targets.resolve(),
        v2_root=args.v2_root.resolve(),
        inventory_path=args.inventory.resolve(),
        offline=args.offline,
    )


if __name__ == "__main__":
    main()
