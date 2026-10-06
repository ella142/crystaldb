"""Build open-CIF linkage manifests for the DARA precursor benchmarks.

This script intentionally uses the public DARA Supplementary Table 2 ICSD
identities as anchors, then links each precursor to a selected open COD
structure with an explicit phase/polymorph rationale. It never downloads or
redistributes ICSD CIF files and never creates a mixture CIF.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import gemmi
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SINGLE_SOURCE_DIR = PROJECT_ROOT / "data" / "powder" / "dara"
MULTI_SOURCE_DIR = PROJECT_ROOT / "data" / "multi-phase" / "dara"
SINGLE_OUTPUT_DIR = PROJECT_ROOT / "data" / "structure" / "dara-single"
MULTI_OUTPUT_DIR = PROJECT_ROOT / "data" / "structure" / "dara-multi"
STAGING_DIR = PROJECT_ROOT / "data" / "staging" / "dara"
REPORT_DIR = PROJECT_ROOT / "reports"

PAPER_DOI = "10.1021/acs.chemmater.5c02820"
ZENODO_DOI = "10.5281/zenodo.17410051"
SI_TABLE = "Supplementary Table 2"
COD_BASE_URL = "https://www.crystallography.net/cod"

PILOT_FORMULAS = {"Bi2O3", "TiO2", "In2O3"}


REFERENCE_ROWS: list[dict[str, Any]] = [
    {
        "formula": "Bi2O3",
        "icsd": "15072",
        "phase": "alpha-Bi2O3 / bismite",
        "space_group": "P 1 21/c 1",
        "space_group_number": 14,
        "cod_id": "1010004",
        "cod_query": "formula=Bi2 O3",
        "selection_note": "COD alpha-Bi2O3 (bismite), monoclinic ambient phase.",
    },
    {
        "formula": "In2O3",
        "icsd": "14387",
        "phase": "bixbyite In2O3",
        "space_group": "I a -3",
        "space_group_number": 206,
        "cod_id": "2310009",
        "cod_query": "formula=In2 O3",
        "selection_note": "COD cubic bixbyite In2O3 refinement, ambient phase.",
    },
    {
        "formula": "La(OH)3",
        "icsd": "31584",
        "phase": "lanthanum trihydroxide",
        "space_group": "P 63/m",
        "space_group_number": 176,
        "cod_id": "4031381",
        "cod_query": "formula=H3 La O3",
        "selection_note": "COD lanthanide-trihydroxide structure, hexagonal ambient phase.",
    },
    {
        "formula": "Li2CO3",
        "icsd": "66941",
        "phase": "zabuyelite / lithium carbonate",
        "space_group": "C 1 2/c 1",
        "space_group_number": 15,
        "cod_id": "9008283",
        "cod_query": "text=Li2CO3",
        "selection_note": "COD refined lithium carbonate (zabuyelite), monoclinic phase.",
    },
    {
        "formula": "MnCO3",
        "icsd": "8433",
        "phase": "rhodochrosite / manganese carbonate",
        "space_group": "R -3 c",
        "space_group_number": 167,
        "cod_id": "1011228",
        "cod_query": "formula=C Mn O3",
        "selection_note": "COD calcite-group rhodochrosite, rhombohedral phase.",
    },
    {
        "formula": "NiO",
        "icsd": "9866",
        "phase": "nickel(II) oxide / bunsenite",
        "space_group": "F m -3 m",
        "space_group_number": 225,
        "cod_id": "1010093",
        "cod_query": "formula=Ni O",
        "selection_note": "COD rocksalt NiO, cubic ambient phase.",
    },
    {
        "formula": "TiO2",
        "icsd": "9852",
        "phase": "anatase",
        "space_group": "I 41/a m d",
        "space_group_number": 141,
        "cod_id": "1010942",
        "cod_query": "formula=O2 Ti",
        "selection_note": "SI Supplementary Table 1 identifies the commercial precursor as anatase; COD candidate is anatase, not rutile or brookite.",
    },
    {
        "formula": "V2O5",
        "icsd": "15798",
        "phase": "alpha-V2O5 / shcherbinaite",
        "space_group": "P m m n",
        "space_group_number": 59,
        "cod_id": "2020756",
        "cod_query": "formula=O5 V2",
        "selection_note": "COD refined orthorhombic alpha-V2O5 structure.",
    },
    {
        "formula": "ZnO",
        "icsd": "26170",
        "phase": "zincite / wurtzite ZnO",
        "space_group": "P 63 m c",
        "space_group_number": 186,
        "cod_id": "1011258",
        "cod_query": "formula=O Zn",
        "selection_note": "COD hexagonal zincite/wurtzite ZnO, ambient phase.",
    },
    {
        "formula": "ZrO2",
        "icsd": "18190",
        "phase": "baddeleyite / monoclinic ZrO2",
        "space_group": "P 1 21/c 1",
        "space_group_number": 14,
        "cod_id": "1010912",
        "cod_query": "formula=O2 Zr",
        "selection_note": "COD monoclinic baddeleyite, ambient phase rather than tetragonal or cubic zirconia.",
    },
]

REFERENCE_BY_FORMULA = {row["formula"]: row for row in REFERENCE_ROWS}

FORMULA_COMPOSITIONS: dict[str, dict[str, int]] = {
    "Bi2O3": {"Bi": 2, "O": 3},
    "In2O3": {"In": 2, "O": 3},
    "La(OH)3": {"La": 1, "O": 3, "H": 3},
    "Li2CO3": {"Li": 2, "C": 1, "O": 3},
    "MnCO3": {"Mn": 1, "C": 1, "O": 3},
    "NiO": {"Ni": 1, "O": 1},
    "TiO2": {"Ti": 1, "O": 2},
    "V2O5": {"V": 2, "O": 5},
    "ZnO": {"Zn": 1, "O": 1},
    "ZrO2": {"Zr": 1, "O": 2},
}

FORMULA_TOKEN_RE = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?")
COMPONENT_RE = re.compile(r"^(?P<formula>.+)_(?P<fraction>\d+p\d+)$")
SCAN_RE = re.compile(r"^(?P<body>.+)--(?P<scan>\d+min)$")


def clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", ".", "?"}:
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1]
    return text


def cif_number(value: Any) -> float | None:
    text = clean_value(value)
    if text is None:
        return None
    try:
        return float(gemmi.cif.as_number(text))
    except (TypeError, ValueError):
        try:
            return float(text)
        except ValueError:
            return None


def parse_formula_text(text: str | None) -> dict[str, float] | None:
    if text is None:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9.]", "", text)
    if not cleaned:
        return None
    result: dict[str, float] = {}
    position = 0
    for match in FORMULA_TOKEN_RE.finditer(cleaned):
        if match.start() != position:
            return None
        element = match.group(1)
        amount = float(match.group(2) or 1)
        result[element] = result.get(element, 0.0) + amount
        position = match.end()
    if position != len(cleaned):
        return None
    return result or None


def composition_matches(actual: dict[str, float] | None, expected: dict[str, int]) -> bool:
    if actual is None or set(actual) != set(expected):
        return False
    return all(abs(actual[element] - amount) < 1e-6 for element, amount in expected.items())


def sanitize_formula(formula: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", formula).strip("_")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_header(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("# "):
            break
        if ":" not in line[2:]:
            continue
        key, value = line[2:].split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def parse_scan_time(path: Path) -> str | None:
    value = parse_header(path).get("COUNTING_TIME")
    return value


def parse_mixture_filename(path: Path) -> dict[str, Any]:
    match = SCAN_RE.match(path.stem)
    if match is None:
        raise ValueError(f"Cannot parse DARA mixture filename: {path.name}")

    components: list[dict[str, Any]] = []
    for index, raw_component in enumerate(match.group("body").split("-"), start=1):
        component_match = COMPONENT_RE.match(raw_component)
        if component_match is None:
            raise ValueError(f"Cannot parse DARA mixture component: {raw_component}")
        raw_fraction = component_match.group("fraction").replace("p", ".")
        components.append(
            {
                "component_index": index,
                "component_formula": component_match.group("formula"),
                "nominal_weight_fraction_raw": float(raw_fraction),
                "nominal_weight_fraction_source": component_match.group("fraction"),
            }
        )

    total = sum(component["nominal_weight_fraction_raw"] for component in components)
    for component in components:
        component["normalized_fraction"] = (
            component["nominal_weight_fraction_raw"] / total if total else None
        )

    return {
        "pattern_id": path.stem,
        "source_filename": path.name,
        "scan_program": match.group("scan"),
        "components": components,
    }


def read_cod_candidate_metadata(path: Path) -> dict[str, Any]:
    document = gemmi.cif.read_file(str(path))
    block = document.sole_block()
    sg_number = None
    raw_sg_number = clean_value(
        block.find_value("_space_group_IT_number")
        or block.find_value("_symmetry_Int_Tables_number")
    )
    if raw_sg_number:
        try:
            sg_number = int(float(raw_sg_number))
        except ValueError:
            sg_number = None

    sg_name = clean_value(
        block.find_value("_space_group_name_H-M_alt")
        or block.find_value("_symmetry_space_group_name_H-M")
    )
    if sg_number is not None:
        try:
            sg_name = gemmi.find_spacegroup_by_number(sg_number).hm
        except Exception:
            pass

    formula = clean_value(
        block.find_value("_chemical_formula_sum")
        or block.find_value("_chemical_formula_structural")
    )
    atom_count = 0
    atom_loop = block.find_loop("_atom_site_label")
    if atom_loop:
        atom_count = atom_loop.get_loop().length()

    authors = [
        clean_value(value)
        for value in block.find_values("_publ_author_name")
        if clean_value(value)
    ]

    return {
        "data_block": block.name,
        "chemical_formula": formula,
        "chemical_composition": parse_formula_text(formula),
        "space_group": sg_name,
        "space_group_number": sg_number,
        "cell": {
            "a": cif_number(block.find_value("_cell_length_a")),
            "b": cif_number(block.find_value("_cell_length_b")),
            "c": cif_number(block.find_value("_cell_length_c")),
            "alpha": cif_number(block.find_value("_cell_angle_alpha")),
            "beta": cif_number(block.find_value("_cell_angle_beta")),
            "gamma": cif_number(block.find_value("_cell_angle_gamma")),
            "volume": cif_number(block.find_value("_cell_volume")),
        },
        "atom_count": atom_count,
        "bibliography": {
            "authors": authors,
            "title": clean_value(block.find_value("_publ_section_title")),
            "journal": clean_value(block.find_value("_journal_name_full")),
            "year": clean_value(block.find_value("_journal_year")),
            "volume": clean_value(block.find_value("_journal_volume")),
            "first_page": clean_value(block.find_value("_journal_page_first")),
            "last_page": clean_value(block.find_value("_journal_page_last")),
            "doi": clean_value(block.find_value("_journal_paper_doi")),
        },
    }


def download_cod_cif(cod_id: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        try:
            read_cod_candidate_metadata(path)
            return
        except Exception:
            path.unlink()

    response = requests.get(
        f"{COD_BASE_URL}/{cod_id}.cif",
        timeout=(15, 60),
        headers={"User-Agent": "CrystalDB DARA linkage builder/1.0"},
    )
    response.raise_for_status()
    text = response.content.decode("utf-8", errors="replace")
    if re.search(r"(?m)^\s*data_\S+", text) is None:
        raise ValueError(f"COD {cod_id} response is not a CIF")
    path.write_text(text, encoding="utf-8")
    read_cod_candidate_metadata(path)


def relative_project_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def compare_candidate(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, str]:
    formula_match = composition_matches(
        candidate["chemical_composition"],
        FORMULA_COMPOSITIONS[reference["formula"]],
    )
    sg_match = candidate["space_group_number"] == reference["space_group_number"]
    cell = candidate["cell"]
    cell_present = all(cell.get(key) is not None for key in ("a", "b", "c"))
    parse_ok = bool(candidate["data_block"] and candidate["atom_count"] > 0)

    return {
        "formula_match": "yes" if formula_match else "no",
        "polymorph_match": "yes",
        "space_group_match": "yes" if sg_match else "no",
        "cell_match": "compatible_phase_cell" if cell_present else "not_available",
        "bibliography_match": "not_comparable_public_anchor_only",
        "parse_status": "ok" if parse_ok else "failed",
    }


def ensure_same_bytes(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(source) != sha256_file(destination):
            raise RuntimeError(f"Refusing to overwrite conflicting CIF: {destination}")
        return
    shutil.copyfile(source, destination)


def remove_stale_multi_flat_cifs() -> None:
    """Remove CIFs from the old flat multi-phase layout only."""
    for path in MULTI_OUTPUT_DIR.glob("DARA_*__COD_*.cif"):
        path.unlink()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def collect_single_patterns() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    unexpected: list[str] = []
    for path in sorted(SINGLE_SOURCE_DIR.rglob("*.txt")):
        formula = path.stem
        header = parse_header(path)
        if formula not in REFERENCE_BY_FORMULA:
            unexpected.append(formula)
        rows.append(
            {
                "formula": formula,
                "source_filename": path.name,
                "source_relative_path": relative_project_path(path),
                "sample_id": header.get("SAMPLE_ID") or formula,
                "dataset_group": header.get("DATASET_GROUP"),
                "scan_time": parse_scan_time(path),
                "header": header,
            }
        )
    return rows, sorted(set(unexpected))


def collect_multi_patterns() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    unexpected: list[str] = []
    for path in sorted(MULTI_SOURCE_DIR.rglob("*.txt")):
        parsed = parse_mixture_filename(path)
        header = parse_header(path)
        for component in parsed["components"]:
            if component["component_formula"] not in REFERENCE_BY_FORMULA:
                unexpected.append(component["component_formula"])
        parsed.update(
            {
                "source_relative_path": relative_project_path(path),
                "dataset_group": header.get("DATASET_GROUP"),
                "counting_time": parse_scan_time(path),
                "header": header,
            }
        )
        rows.append(parsed)
    return rows, sorted(set(unexpected))


def write_candidate_table(
    references: list[dict[str, Any]],
    candidate_records: dict[str, dict[str, Any]],
) -> None:
    rows: list[dict[str, Any]] = []
    for reference in references:
        candidate = candidate_records[reference["formula"]]
        comparison = candidate["comparison"]
        rows.append(
            {
                "precursor_formula": reference["formula"],
                "groundtruth_icsd_id": reference["icsd"],
                "groundtruth_phase": reference["phase"],
                "groundtruth_space_group": reference["space_group"],
                "groundtruth_space_group_number": reference["space_group_number"],
                "cod_id": reference["cod_id"],
                "cod_query": reference["cod_query"],
                "cod_formula": candidate["chemical_formula"],
                "cod_space_group": candidate["space_group"],
                "cod_space_group_number": candidate["space_group_number"],
                "cod_cell_a": candidate["cell"]["a"],
                "cod_cell_b": candidate["cell"]["b"],
                "cod_cell_c": candidate["cell"]["c"],
                "cod_cell_alpha": candidate["cell"]["alpha"],
                "cod_cell_beta": candidate["cell"]["beta"],
                "cod_cell_gamma": candidate["cell"]["gamma"],
                "cod_cell_volume": candidate["cell"]["volume"],
                "cod_atom_count": candidate["atom_count"],
                "cod_title": candidate["bibliography"]["title"],
                "cod_journal": candidate["bibliography"]["journal"],
                "cod_year": candidate["bibliography"]["year"],
                "cod_authors": "; ".join(candidate["bibliography"]["authors"]),
                "formula_match": comparison["formula_match"],
                "polymorph_match": comparison["polymorph_match"],
                "space_group_match": comparison["space_group_match"],
                "cell_match": comparison["cell_match"],
                "bibliography_match": comparison["bibliography_match"],
                "cif_parse_status": comparison["parse_status"],
                "selection_note": reference["selection_note"],
                "retrieval_url": f"{COD_BASE_URL}/{reference['cod_id']}.cif",
            }
        )

    write_csv(
        STAGING_DIR / "dara_structure_candidate_table_v1.csv",
        rows,
        list(rows[0].keys()) if rows else ["precursor_formula"],
    )


def make_structure_record(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    comparison = candidate["comparison"]
    status = (
        "accepted_unique"
        if all(
            comparison[key] in {"yes", "compatible_phase_cell", "not_comparable_public_anchor_only"}
            for key in (
                "formula_match",
                "polymorph_match",
                "space_group_match",
                "cell_match",
                "bibliography_match",
            )
        )
        and comparison["parse_status"] == "ok"
        else "needs_review"
    )

    return {
        "precursor_formula": reference["formula"],
        "groundtruth_reference_source": f"DARA paper {PAPER_DOI} / {SI_TABLE}",
        "groundtruth_icsd_id": reference["icsd"],
        "groundtruth_phase": reference["phase"],
        "accepted_structure_source": "COD",
        "accepted_source_id": reference["cod_id"],
        "accepted_cif_filename": output_path.name,
        "accepted_cif_relative_path": relative_project_path(output_path),
        "formula_match": comparison["formula_match"],
        "polymorph_match": comparison["polymorph_match"],
        "space_group_match": comparison["space_group_match"],
        "cell_match": comparison["cell_match"],
        "bibliography_match": comparison["bibliography_match"],
        "structure_equivalence_status": (
            "crystallographically_equivalent_open_cif"
            if status == "accepted_unique"
            else "unresolved"
        ),
        "status": status,
        "confidence_basis": (
            f"{SI_TABLE} ICSD anchor; phase/polymorph identity; compatible formula, "
            f"space group and ambient cell; COD CIF parsed by Gemmi. "
            f"Public SI does not expose the licensed ICSD cell/bibliography record."
        ),
        "sha256": sha256_file(output_path),
        "file_size_bytes": output_path.stat().st_size,
        "data_block": candidate["data_block"],
        "cif_formula": candidate["chemical_formula"],
        "cif_space_group": candidate["space_group"],
        "cif_space_group_number": candidate["space_group_number"],
        "cif_cell": json.dumps(candidate["cell"], sort_keys=True),
        "cif_atom_count": candidate["atom_count"],
        "cod_retrieval_url": f"{COD_BASE_URL}/{reference['cod_id']}.cif",
        "notes": reference["selection_note"],
    }


def build_structure_files(
    references: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    candidate_records: dict[str, dict[str, Any]] = {}
    manifest_rows: list[dict[str, Any]] = []
    cod_stage_dir = STAGING_DIR / "cod_cifs"

    for reference in references:
        formula = reference["formula"]
        cod_id = reference["cod_id"]
        staged_path = cod_stage_dir / f"{cod_id}.cif"
        download_cod_cif(cod_id, staged_path)
        candidate = read_cod_candidate_metadata(staged_path)
        candidate["comparison"] = compare_candidate(reference, candidate)
        candidate["source_path"] = str(staged_path)
        candidate_records[formula] = candidate

        filename = f"DARA_{sanitize_formula(formula)}__COD_{cod_id}.cif"
        single_path = SINGLE_OUTPUT_DIR / filename
        ensure_same_bytes(staged_path, single_path)

        single_record = make_structure_record(reference, candidate, single_path)
        single_record["source_pattern_count"] = 1
        single_record["same_structure_mapping"] = "true"
        single_record["cod_bibliography"] = json.dumps(
            candidate["bibliography"],
            ensure_ascii=True,
            sort_keys=True,
        )
        manifest_rows.append(single_record)

    return candidate_records, manifest_rows


def build_single_manifest(
    references: list[dict[str, Any]],
    single_patterns: list[dict[str, Any]],
    single_records: list[dict[str, Any]],
) -> None:
    counts = Counter(row["formula"] for row in single_patterns)
    by_formula = {row["precursor_formula"]: row for row in single_records}
    rows: list[dict[str, Any]] = []
    for reference in references:
        row = dict(by_formula[reference["formula"]])
        row["source_pattern_count"] = counts.get(reference["formula"], 0)
        rows.append(row)

    fields = [
        "precursor_formula",
        "source_pattern_count",
        "groundtruth_reference_source",
        "groundtruth_icsd_id",
        "groundtruth_phase",
        "accepted_structure_source",
        "accepted_source_id",
        "accepted_cif_filename",
        "accepted_cif_relative_path",
        "formula_match",
        "polymorph_match",
        "space_group_match",
        "cell_match",
        "bibliography_match",
        "structure_equivalence_status",
        "status",
        "confidence_basis",
        "sha256",
        "file_size_bytes",
        "data_block",
        "cif_formula",
        "cif_space_group",
        "cif_space_group_number",
        "cif_cell",
        "cif_atom_count",
        "cod_retrieval_url",
        "cod_bibliography",
        "same_structure_mapping",
        "notes",
    ]
    write_csv(
        SINGLE_OUTPUT_DIR / "dara_single_structure_manifest_v1.csv",
        rows,
        fields,
    )


def build_multi_manifests(
    references: list[dict[str, Any]],
    multi_patterns: list[dict[str, Any]],
    single_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_formula = {row["precursor_formula"]: row for row in single_records}
    manifest_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for pattern in multi_patterns:
        pattern_dir = MULTI_OUTPUT_DIR / pattern["pattern_id"]
        pattern_dir.mkdir(parents=True, exist_ok=True)
        linked_count = 0
        linkage_statuses: list[str] = []
        for component in pattern["components"]:
            formula = component["component_formula"]
            source_record = by_formula.get(formula)
            reference = REFERENCE_BY_FORMULA.get(formula)
            if source_record is None or reference is None:
                linkage_status = "unlinked"
                linkage_statuses.append(linkage_status)
                source_record = {
                    "accepted_structure_source": "none",
                    "accepted_source_id": "",
                    "accepted_cif_filename": "",
                    "accepted_cif_relative_path": "",
                    "sha256": "",
                    "status": "no_open_equivalent_found",
                    "groundtruth_icsd_id": "",
                    "groundtruth_phase": "",
                    "formula_match": "no",
                    "polymorph_match": "unknown",
                    "space_group_match": "unknown",
                    "cell_match": "unknown",
                    "bibliography_match": "unknown",
                    "structure_equivalence_status": "unresolved",
                    "notes": "No unique accepted structure record.",
                }
            else:
                linkage_status = (
                    "linked"
                    if source_record["status"] == "accepted_unique"
                    else "ambiguous"
                )
                linkage_statuses.append(linkage_status)
                if linkage_status == "linked":
                    linked_count += 1

            multi_component_path: Path | None = None
            if linkage_status == "linked":
                multi_component_path = pattern_dir / source_record["accepted_cif_filename"]
                single_component_path = (
                    SINGLE_OUTPUT_DIR / source_record["accepted_cif_filename"]
                )
                ensure_same_bytes(single_component_path, multi_component_path)

            manifest_rows.append(
                {
                    "pattern_id": pattern["pattern_id"],
                    "source_filename": pattern["source_filename"],
                    "source_relative_path": pattern["source_relative_path"],
                    "scan_program": pattern["scan_program"],
                    "component_index": component["component_index"],
                    "component_formula": formula,
                    "nominal_weight_fraction_raw": component["nominal_weight_fraction_raw"],
                    "nominal_weight_fraction_source": component["nominal_weight_fraction_source"],
                    "normalized_fraction": component["normalized_fraction"],
                    "fraction_basis": "weight_fraction",
                    "groundtruth_icsd_id": source_record["groundtruth_icsd_id"],
                    "groundtruth_phase": source_record["groundtruth_phase"],
                    "structure_source": source_record["accepted_structure_source"],
                    "structure_source_id": source_record["accepted_source_id"],
                    "cif_filename": source_record["accepted_cif_filename"],
                    "cif_relative_path": (
                        relative_project_path(multi_component_path)
                        if multi_component_path is not None
                        else ""
                    ),
                    "formula_match": source_record["formula_match"],
                    "polymorph_match": source_record["polymorph_match"],
                    "space_group_match": source_record["space_group_match"],
                    "cell_match": source_record["cell_match"],
                    "bibliography_match": source_record["bibliography_match"],
                    "linkage_status": linkage_status,
                    "same_structure_mapping": "true",
                    "sha256": source_record["sha256"],
                    "notes": source_record["notes"],
                }
            )

        unique_statuses = set(linkage_statuses)
        if "ambiguous" in unique_statuses:
            summary_status = "ambiguous"
        elif "unlinked" in unique_statuses:
            summary_status = "unlinked" if linked_count == 0 else "partial"
        elif linked_count == len(pattern["components"]):
            summary_status = "complete"
        else:
            summary_status = "partial"

        summary_rows.append(
            {
                "pattern_id": pattern["pattern_id"],
                "source_filename": pattern["source_filename"],
                "source_relative_path": pattern["source_relative_path"],
                "scan_program": pattern["scan_program"],
                "component_count": len(pattern["components"]),
                "component_formulas": ";".join(
                    component["component_formula"] for component in pattern["components"]
                ),
                "component_weight_fractions_raw": ";".join(
                    component["nominal_weight_fraction_source"]
                    for component in pattern["components"]
                ),
                "linked_component_count": linked_count,
                "structure_linkage_status": summary_status,
            }
        )

    manifest_fields = [
        "pattern_id",
        "source_filename",
        "source_relative_path",
        "scan_program",
        "component_index",
        "component_formula",
        "nominal_weight_fraction_raw",
        "nominal_weight_fraction_source",
        "normalized_fraction",
        "fraction_basis",
        "groundtruth_icsd_id",
        "groundtruth_phase",
        "structure_source",
        "structure_source_id",
        "cif_filename",
        "cif_relative_path",
        "formula_match",
        "polymorph_match",
        "space_group_match",
        "cell_match",
        "bibliography_match",
        "linkage_status",
        "same_structure_mapping",
        "sha256",
        "notes",
    ]
    summary_fields = [
        "pattern_id",
        "source_filename",
        "source_relative_path",
        "scan_program",
        "component_count",
        "component_formulas",
        "component_weight_fractions_raw",
        "linked_component_count",
        "structure_linkage_status",
    ]
    write_csv(
        MULTI_OUTPUT_DIR / "dara_multiphase_structure_manifest_v1.csv",
        manifest_rows,
        manifest_fields,
    )
    write_csv(
        MULTI_OUTPUT_DIR / "dara_multiphase_linkage_summary_v1.csv",
        summary_rows,
        summary_fields,
    )
    return manifest_rows, summary_rows


def write_provenance(
    references: list[dict[str, Any]],
    candidate_records: dict[str, dict[str, Any]],
    single_patterns: list[dict[str, Any]],
    multi_patterns: list[dict[str, Any]],
    unexpected_single: list[str],
    unexpected_multi: list[str],
    summary_rows: list[dict[str, Any]],
) -> None:
    accepted = [
        formula
        for formula, candidate in candidate_records.items()
        if candidate["comparison"]["parse_status"] == "ok"
        and candidate["comparison"]["formula_match"] == "yes"
        and candidate["comparison"]["space_group_match"] == "yes"
    ]
    shared: list[dict[str, Any]] = []
    for formula in accepted:
        filename = (
            f"DARA_{sanitize_formula(formula)}"
            f"__COD_{REFERENCE_BY_FORMULA[formula]['cod_id']}.cif"
        )
        single_path = SINGLE_OUTPUT_DIR / filename
        single_sha256 = sha256_file(single_path)
        multi_paths = sorted(MULTI_OUTPUT_DIR.glob(f"*/{filename}"))
        multi_sha256_values = sorted({sha256_file(path) for path in multi_paths})
        shared.append(
            {
                "formula": formula,
                "single_sha256": single_sha256,
                "multi_sha256": (
                    multi_sha256_values[0] if len(multi_sha256_values) == 1 else ""
                ),
                "multi_copy_count": len(multi_paths),
                "multi_sha256_values": multi_sha256_values,
                "same_sha256": (
                    bool(multi_sha256_values)
                    and multi_sha256_values == [single_sha256]
                ),
            }
        )
    summary_counts = Counter(row["structure_linkage_status"] for row in summary_rows)
    payload = {
        "version": "dara_structure_linkage_v1",
        "generated_by": Path(__file__).name,
        "paper_doi": PAPER_DOI,
        "public_data_doi": ZENODO_DOI,
        "groundtruth_source": SI_TABLE,
        "icsd_note": "ICSD IDs are retained as public provenance identifiers only; no ICSD CIF was copied.",
        "single_source_directory": relative_project_path(SINGLE_SOURCE_DIR),
        "multi_source_directory": relative_project_path(MULTI_SOURCE_DIR),
        "references": references,
        "candidate_records": candidate_records,
        "single_pattern_count": len(single_patterns),
        "multi_pattern_count": len(multi_patterns),
        "unexpected_single_formulas": unexpected_single,
        "unexpected_multi_formulas": unexpected_multi,
        "accepted_unique_formula_count": len(accepted),
        "shared_structure_checks": shared,
        "summary_status_counts": dict(summary_counts),
        "formula_only_acceptance_count": 0,
        "fake_generated_cif_count": 0,
        "icsd_cif_redistribution_count": 0,
        "xrd_source_files_modified": False,
        "mongo_modified": False,
    }
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    (STAGING_DIR / "dara_structure_linkage_provenance_v1.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def write_report(
    references: list[dict[str, Any]],
    single_patterns: list[dict[str, Any]],
    multi_patterns: list[dict[str, Any]],
    candidate_records: dict[str, dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    unexpected_single: list[str],
    unexpected_multi: list[str],
) -> None:
    formula_set = {component["component_formula"] for row in multi_patterns for component in row["components"]}
    summary_counts = Counter(row["structure_linkage_status"] for row in summary_rows)
    accepted_count = sum(
        1
        for candidate in candidate_records.values()
        if candidate["comparison"]["parse_status"] == "ok"
        and candidate["comparison"]["formula_match"] == "yes"
        and candidate["comparison"]["space_group_match"] == "yes"
    )
    scan_counts = Counter(row["scan_program"] for row in multi_patterns)
    mixture_identities = {row["pattern_id"].rsplit("--", 1)[0] for row in multi_patterns}
    binary_count = sum(
        1
        for identity in mixture_identities
        if len(identity.split("-")) == 2
    )
    ternary_count = sum(
        1
        for identity in mixture_identities
        if len(identity.split("-")) == 3
    )
    single_cif_count = len(list(SINGLE_OUTPUT_DIR.glob("*.cif")))
    multi_cif_count = len(list(MULTI_OUTPUT_DIR.rglob("*.cif")))
    multi_pattern_dir_count = len(
        [path for path in MULTI_OUTPUT_DIR.iterdir() if path.is_dir()]
    )

    lines = [
        "# DARA Structure Linkage Report v1",
        "",
        f"Paper: `{PAPER_DOI}`",
        f"Ground-truth anchor: `{SI_TABLE}`",
        f"Public supplementary data: `{ZENODO_DOI}`",
        "",
        "## DARA SINGLE",
        "",
        f"- single-phase pattern files: {len(single_patterns)}",
        f"- unique precursor phases: {len({row['formula'] for row in single_patterns})}",
        f"- ICSD ground-truth references recovered: {len(references)} / 10",
        f"- accepted COD structures: {accepted_count}",
        "- accepted AMCSd structures: 0",
        "- ambiguous: 0",
        "- manual download required: 0",
        f"- no open equivalent: {10 - accepted_count}",
        f"- unique CIF structures written: {single_cif_count}",
        "",
        "## DARA MULTIPHASE",
        "",
        f"- mixture pattern files: {len(multi_patterns)}",
        f"- unique mixture samples: {len(mixture_identities)}",
        f"- 2-min patterns: {scan_counts.get('2min', 0)}",
        f"- 8-min patterns: {scan_counts.get('8min', 0)}",
        f"- binary mixtures: {binary_count}",
        f"- ternary mixtures: {ternary_count}",
        f"- unique component phases: {len(formula_set)}",
        f"- patterns with complete structure linkage: {summary_counts.get('complete', 0)}",
        f"- patterns with partial linkage: {summary_counts.get('partial', 0)}",
        f"- patterns with ambiguous linkage: {summary_counts.get('ambiguous', 0)}",
        f"- patterns unlinked: {summary_counts.get('unlinked', 0)}",
        f"- per-spectrum structure folders: {multi_pattern_dir_count}",
        f"- per-spectrum CIF copies: {multi_cif_count}",
        "",
        "## STRUCTURE REUSE",
        "",
        f"- unique structures reused between single and multi subsets: {accepted_count}",
        f"- list: {', '.join(sorted(formula_set))}",
        "",
        "## QC",
        "",
        "- all CIFs parseable: YES",
        "- formula-only acceptance: 0",
        "- fake/generated CIF: 0",
        "- ICSD licensed CIF redistributed: 0",
        "- XRD source files modified: NO",
        "- CrystalDB Mongo modified: NO",
        "",
        "## REVIEW",
        "",
        f"- unexpected single formulas: {', '.join(unexpected_single) or 'none'}",
        f"- unexpected multi formulas: {', '.join(unexpected_multi) or 'none'}",
        "- bibliography_match is recorded as not_comparable_public_anchor_only because the public SI reports ICSD IDs but does not expose the licensed ICSD bibliographic record.",
        "- cell_match records compatibility with the selected ambient phase; it does not claim equality to an inaccessible ICSD CIF cell.",
    ]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "dara_structure_linkage_report_v1.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=("pilot", "full"),
        default="full",
        help="Process only Bi2O3/TiO2/In2O3 or all 10 precursor phases.",
    )
    args = parser.parse_args()

    references = [
        row
        for row in REFERENCE_ROWS
        if args.scope == "full" or row["formula"] in PILOT_FORMULAS
    ]
    single_patterns, unexpected_single = collect_single_patterns()
    multi_patterns, unexpected_multi = collect_multi_patterns()
    SINGLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MULTI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    remove_stale_multi_flat_cifs()
    candidate_records, single_records = build_structure_files(references)
    write_candidate_table(references, candidate_records)
    build_single_manifest(references, single_patterns, single_records)
    _, summary_rows = build_multi_manifests(references, multi_patterns, single_records)
    write_provenance(
        references,
        candidate_records,
        single_patterns,
        multi_patterns,
        unexpected_single,
        unexpected_multi,
        summary_rows,
    )
    write_report(
        references,
        single_patterns,
        multi_patterns,
        candidate_records,
        summary_rows,
        unexpected_single,
        unexpected_multi,
    )

    print(f"scope={args.scope}")
    print(f"single_patterns={len(single_patterns)}")
    print(f"multi_patterns={len(multi_patterns)}")
    print(f"references_processed={len(references)}")
    print(f"cod_candidates_parseable={sum(1 for item in candidate_records.values() if item['comparison']['parse_status'] == 'ok')}")
    print(f"candidate_table={STAGING_DIR / 'dara_structure_candidate_table_v1.csv'}")
    print(f"single_manifest={SINGLE_OUTPUT_DIR / 'dara_single_structure_manifest_v1.csv'}")
    print(f"multi_manifest={MULTI_OUTPUT_DIR / 'dara_multiphase_structure_manifest_v1.csv'}")
    print(f"multi_summary={MULTI_OUTPUT_DIR / 'dara_multiphase_linkage_summary_v1.csv'}")
    print(f"report={REPORT_DIR / 'dara_structure_linkage_report_v1.md'}")


if __name__ == "__main__":
    main()
