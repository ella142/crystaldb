"""Summary parser for COD CIF-like reflection files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import gemmi


REQUIRED_REFLECTION_TAGS = (
    "_refln_index_h",
    "_refln_index_k",
    "_refln_index_l",
    "_refln_F_squared_calc",
    "_refln_F_squared_meas",
    "_refln_F_squared_sigma",
    "_refln_observed_status",
)

OPTIONAL_REFLECTION_TAGS = (
    "_refln_f_squared_weight",
)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", ".", "?"}:
        return None
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


def _loop_rows(
    block: gemmi.cif.Block,
) -> tuple[list[str], list[dict[str, str]]]:
    column = block.find_loop("_refln_index_h")
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


def _reflection_blocks(
    document: gemmi.cif.Document,
) -> list[tuple[gemmi.cif.Block, list[str], list[dict[str, str]]]]:
    blocks = []
    for block in document:
        tags, rows = _loop_rows(block)
        if tags:
            blocks.append((block, tags, rows))
    return blocks


def parse_cod_hkl(hkl_path: str | Path, source_id: str | None = None) -> dict[str, Any]:
    """Parse one COD HKL file without retaining reflection rows."""
    path = Path(hkl_path)
    warnings: list[str] = []
    document = gemmi.cif.read_file(str(path))
    reflection_blocks = _reflection_blocks(document)
    reflection_tags: list[str] = []
    rows: list[dict[str, str]] = []
    for _, block_tags, block_rows in reflection_blocks:
        for tag in block_tags:
            if tag not in reflection_tags:
                reflection_tags.append(tag)
        rows.extend(block_rows)

    source_record_id = _clean_text(source_id)
    if source_record_id is None:
        source_record_id = _clean_text(
            reflection_blocks[0][0].name if reflection_blocks else document[0].name
        )

    if not reflection_blocks:
        warnings.append("reflection_loop_missing")
    missing = [tag for tag in REQUIRED_REFLECTION_TAGS if tag not in reflection_tags]
    if missing:
        warnings.append("required_reflection_fields_missing:" + ",".join(missing))

    h_values: list[int] = []
    k_values: list[int] = []
    l_values: list[int] = []
    measured_values: list[float] = []
    for row in rows:
        for tag, target in (
            ("_refln_index_h", h_values),
            ("_refln_index_k", k_values),
            ("_refln_index_l", l_values),
        ):
            value = _clean_text(row.get(tag))
            if value is not None:
                try:
                    target.append(int(value))
                except ValueError:
                    warnings.append(f"invalid_index_value:{tag}")
        measured = _to_float(row.get("_refln_F_squared_meas"))
        if measured is not None:
            measured_values.append(measured)

    optional_fields = [
        tag for tag in OPTIONAL_REFLECTION_TAGS if tag in reflection_tags
    ]
    if len(h_values) != len(rows) or len(k_values) != len(rows) or len(l_values) != len(rows):
        warnings.append("reflection_index_values_partial")
    if len(measured_values) != len(rows):
        warnings.append("measured_f_squared_values_partial")

    result: dict[str, Any] = {
        "source_id": source_record_id,
        "reflection_count": len(rows),
        "reflection_tags": reflection_tags,
        "reflection_fields": reflection_tags,
        "has_index_h": "_refln_index_h" in reflection_tags,
        "has_index_k": "_refln_index_k" in reflection_tags,
        "has_index_l": "_refln_index_l" in reflection_tags,
        "has_hkl": all(
            tag in reflection_tags
            for tag in ("_refln_index_h", "_refln_index_k", "_refln_index_l")
        ),
        "has_f_squared_meas": "_refln_F_squared_meas" in reflection_tags,
        "has_measured_f_squared": "_refln_F_squared_meas" in reflection_tags,
        "has_f_squared_sigma": "_refln_F_squared_sigma" in reflection_tags,
        "has_calculated_f_squared": "_refln_F_squared_calc" in reflection_tags,
        "has_f_squared_calc": "_refln_F_squared_calc" in reflection_tags,
        "has_observed_status": "_refln_observed_status" in reflection_tags,
        "optional_fields": optional_fields,
        "parse_status": "partial" if warnings else "ok",
        "parse_warnings": sorted(set(warnings)),
    }
    if h_values:
        result.update({"h_min": min(h_values), "h_max": max(h_values)})
    else:
        result.update({"h_min": None, "h_max": None})
    if k_values:
        result.update({"k_min": min(k_values), "k_max": max(k_values)})
    else:
        result.update({"k_min": None, "k_max": None})
    if l_values:
        result.update({"l_min": min(l_values), "l_max": max(l_values)})
    else:
        result.update({"l_min": None, "l_max": None})
    if measured_values:
        result.update(
            {
                "measured_f_squared_min": min(measured_values),
                "measured_f_squared_max": max(measured_values),
            }
        )
    else:
        result.update(
            {
                "measured_f_squared_min": None,
                "measured_f_squared_max": None,
            }
        )
    return result
