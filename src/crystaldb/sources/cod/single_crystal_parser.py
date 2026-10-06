"""COD single-crystal CIF parsing built on Gemmi."""

from __future__ import annotations

import math
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

import gemmi


_ELEMENT_RE = re.compile(r"^[A-Z][a-z]?$")
_FORMULA_TOKEN_RE = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", ".", "?"}:
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1]
    return text


def _to_float(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return float(gemmi.cif.as_number(text))
    except (TypeError, ValueError):
        try:
            return float(text)
        except ValueError:
            return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _first_value(block: gemmi.cif.Block, tags: Iterable[str]) -> Any:
    for tag in tags:
        value = block.find_value(tag)
        if _clean_text(value) is not None:
            return value
    return None


def _loop_rows(
    block: gemmi.cif.Block,
    anchor_tag: str,
) -> tuple[list[str], list[dict[str, str]]]:
    column = block.find_loop(anchor_tag)
    if not column:
        return [], []
    loop = column.get_loop()
    tags = [str(tag) for tag in loop.tags]
    width = loop.width()
    values = list(loop.values)
    rows = [
        dict(zip(tags, values[index : index + width]))
        for index in range(0, len(values), width)
    ]
    return tags, rows


def _element_from_label(label: str | None) -> str | None:
    if not label:
        return None
    match = re.match(r"([A-Z][a-z]?)", label)
    if not match:
        return None
    return match.group(1)


def _normalize_element(value: Any, label: str | None = None) -> str | None:
    text = _clean_text(value)
    if text:
        text = text[0].upper() + text[1:].lower()
        if _ELEMENT_RE.fullmatch(text):
            return text
    return _element_from_label(label)


def _parse_formula(formula: str | None) -> OrderedDict[str, float] | None:
    if formula is None:
        return None
    cleaned = formula.replace("_", "").replace(" ", "")
    if not cleaned or any(char in cleaned for char in "[]()^;"):
        return None
    result: OrderedDict[str, float] = OrderedDict()
    position = 0
    for match in _FORMULA_TOKEN_RE.finditer(cleaned):
        if match.start() != position:
            return None
        element = match.group(1)
        amount = float(match.group(2) or 1)
        result[element] = result.get(element, 0.0) + amount
        position = match.end()
    if position != len(cleaned) or not result:
        return None
    return result


def _reduced_formula(formula: str | None) -> str | None:
    composition = _parse_formula(formula)
    if composition is None:
        return None
    amounts = list(composition.values())
    rounded = [round(value) for value in amounts]
    if any(not math.isclose(value, integer, rel_tol=0, abs_tol=1e-6) for value, integer in zip(amounts, rounded)):
        return None
    divisor = 0
    for integer in rounded:
        divisor = math.gcd(divisor, integer)
    if divisor <= 0:
        return None
    parts: list[str] = []
    for element, integer in zip(composition, rounded):
        reduced = integer // divisor
        parts.append(element if reduced == 1 else f"{element}{reduced}")
    return "".join(parts)


def _space_group(block: gemmi.cif.Block, warnings: list[str]) -> dict[str, Any]:
    hm = _clean_text(
        _first_value(
            block,
            (
                "_space_group_name_H-M_alt",
                "_symmetry_space_group_name_H-M",
                "_cod_original_sg_symbol_H-M",
            ),
        )
    )
    hall = _clean_text(
        _first_value(
            block,
            (
                "_space_group_name_Hall",
                "_symmetry_space_group_name_Hall",
            ),
        )
    )
    number = _to_int(
        _first_value(
            block,
            (
                "_space_group_IT_number",
                "_symmetry_Int_Tables_number",
            ),
        )
    )
    space_group = None
    if number is not None:
        try:
            space_group = gemmi.find_spacegroup_by_number(number)
        except Exception:
            space_group = None
    if space_group is None and hm:
        try:
            space_group = gemmi.find_spacegroup_by_name(hm)
        except Exception:
            space_group = None
    if space_group is not None:
        if number is None:
            number = int(space_group.number)
        if hall is None:
            hall = _clean_text(space_group.hall)
        if hm is None:
            hm = _clean_text(space_group.hm)
    if hm is None and hall is None and number is None:
        warnings.append("space_group_missing")
    return {"hm": hm, "hall": hall, "number": number}


def _cell(block: gemmi.cif.Block, warnings: list[str]) -> dict[str, float | None]:
    cell = {
        "a": _to_float(block.find_value("_cell_length_a")),
        "b": _to_float(block.find_value("_cell_length_b")),
        "c": _to_float(block.find_value("_cell_length_c")),
        "alpha": _to_float(block.find_value("_cell_angle_alpha")),
        "beta": _to_float(block.find_value("_cell_angle_beta")),
        "gamma": _to_float(block.find_value("_cell_angle_gamma")),
        "volume": _to_float(block.find_value("_cell_volume")),
    }
    missing = [key for key, value in cell.items() if value is None]
    if missing:
        warnings.append("cell_fields_missing:" + ",".join(missing))
    return cell


def _experimental_conditions(
    block: gemmi.cif.Block,
) -> dict[str, Any]:
    return {
        "wavelength": _to_float(
            _first_value(
                block,
                (
                    "_diffrn_radiation_wavelength",
                    "_diffrn_radiation_wavelength_wavelength",
                ),
            )
        ),
        "radiation_type": _clean_text(
            _first_value(
                block,
                (
                    "_diffrn_radiation_type",
                    "_diffrn_radiation_probe",
                ),
            )
        ),
        "temperature": _to_float(
            _first_value(
                block,
                (
                    "_diffrn_ambient_temperature",
                    "_cell_measurement_temperature",
                ),
            )
        ),
        "diffractometer": _clean_text(
            _first_value(
                block,
                (
                    "_diffrn_measurement_device_type",
                    "_diffrn_measurement_device",
                ),
            )
        ),
    }


def parse_cod_cif(cif_path: str | Path, source_id: str | None = None) -> dict[str, Any]:
    """Parse one COD CIF into structure metadata."""
    path = Path(cif_path)
    warnings: list[str] = []
    document = gemmi.cif.read_file(str(path))
    block = document.sole_block()

    formula = _clean_text(
        _first_value(
            block,
            ("_chemical_formula_sum", "_chemical_formula_moiety"),
        )
    )
    tags, rows = _loop_rows(block, "_atom_site_label")
    required_atom_tags = {
        "_atom_site_label",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
    }
    if not required_atom_tags.issubset(tags):
        if rows:
            warnings.append("atom_site_required_fields_missing")
        else:
            warnings.append("atom_sites_missing")

    atomic_sites: list[dict[str, Any]] = []
    element_set: set[str] = set()
    for row in rows:
        label = _clean_text(row.get("_atom_site_label"))
        element = _normalize_element(row.get("_atom_site_type_symbol"), label)
        if element:
            element_set.add(element)
        atomic_sites.append(
            {
                "label": label,
                "element": element,
                "fract_x": _to_float(row.get("_atom_site_fract_x")),
                "fract_y": _to_float(row.get("_atom_site_fract_y")),
                "fract_z": _to_float(row.get("_atom_site_fract_z")),
                "occupancy": _to_float(row.get("_atom_site_occupancy")),
            }
        )

    if not element_set:
        composition = _parse_formula(formula)
        if composition:
            element_set.update(composition)
    if any(site["element"] is None for site in atomic_sites):
        warnings.append("atom_elements_partial")
    if any(
        site[key] is None
        for site in atomic_sites
        for key in ("fract_x", "fract_y", "fract_z")
    ):
        warnings.append("atom_coordinates_partial")

    cif_source_id = _clean_text(
        source_id
        or _first_value(
            block,
            ("_cod_database_code", "_cod_database_code_depnum_ccdc_archive"),
        )
    )
    if cif_source_id is None:
        warnings.append("cod_source_id_missing")

    return {
        "data_block": _clean_text(block.name),
        "formula": formula,
        "formula_reduced": _reduced_formula(formula),
        "elements": sorted(element_set),
        "space_group": _space_group(block, warnings),
        "cell": _cell(block, warnings),
        "atomic_sites": atomic_sites,
        "atom_count": len(atomic_sites),
        "experimental_conditions": _experimental_conditions(block),
        "source_id": cif_source_id,
        "parse_status": "partial" if warnings else "ok",
        "parse_warnings": sorted(set(warnings)),
    }
