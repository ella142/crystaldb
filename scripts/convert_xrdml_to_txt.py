#!/usr/bin/env python3
"""Convert PANalytical/Malvern XRDML scans to provenance-preserving TXT files.

The converter only reads XRDML files. It does not modify source XML files,
Excel files, PDFs, images, or the source ZIP archive.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Iterable


GROUPS = (
    "pairwise_reactions_patterns",
    "precursor_mixture_patterns",
    "singple_phase_precursor_patterns",
)

REPORT_COLUMNS = (
    "original_file",
    "original_relative_path",
    "output_file",
    "dataset_group",
    "point_count",
    "two_theta_point_count",
    "intensity_point_count",
    "two_theta_min",
    "two_theta_max",
    "intensity_min",
    "intensity_max",
    "wavelength",
    "anode_material",
    "scan_mode",
    "counting_time",
    "position_source",
    "step_size",
    "intensity_source",
    "conversion_status",
    "warning",
)

_TOKEN_SPLIT = re.compile(r"\s+")


class ConversionError(Exception):
    """An error that prevents a trustworthy conversion for one source file."""


@dataclass
class ConvertedPattern:
    row: dict[str, str]
    points: list[tuple[str, str]]


def local_name(tag: str) -> str:
    """Return an XML tag name without its namespace URI."""

    return tag.rsplit("}", 1)[-1]


def clean_text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return " ".join(element.text.split())


def child_by_name(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for child in list(parent):
        if local_name(child.tag) == name:
            return child
    return None


def descendants_by_name(
    parent: ET.Element, name: str
) -> list[ET.Element]:
    return [element for element in parent.iter() if local_name(element.tag) == name]


def first_descendant(
    parent: ET.Element, name: str, **attributes: str
) -> ET.Element | None:
    for element in parent.iter():
        if local_name(element.tag) != name:
            continue
        if all(element.attrib.get(key) == value for key, value in attributes.items()):
            return element
    return None


def split_tokens(text: str) -> list[str]:
    normalized = text.strip()
    return [] if not normalized else _TOKEN_SPLIT.split(normalized)


def parse_decimal_tokens(tokens: Iterable[str], label: str) -> list[Decimal]:
    values: list[Decimal] = []
    for index, token in enumerate(tokens):
        try:
            value = Decimal(token)
        except InvalidOperation as exc:
            raise ConversionError(
                f"{label} contains a non-numeric token at index {index}: {token!r}"
            ) from exc
        if not value.is_finite():
            raise ConversionError(
                f"{label} contains a non-finite value at index {index}: {token!r}"
            )
        values.append(value)
    return values


def decimal_places(token: str) -> int:
    value = Decimal(token)
    return max(0, -value.as_tuple().exponent)


def format_decimal(value: Decimal, places: int | None = None) -> str:
    if places is not None:
        quantum = Decimal(1).scaleb(-places)
        with localcontext() as context:
            context.prec = max(50, len(value.as_tuple().digits) + places + 10)
            value = value.quantize(quantum)
        return format(value, "f")

    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def fraction_has_finite_decimal(fraction: Fraction) -> bool:
    denominator = abs(fraction.denominator)
    for factor in (2, 5):
        while denominator % factor == 0:
            denominator //= factor
    return denominator == 1


def fraction_decimal_places(fraction: Fraction) -> int:
    denominator = abs(fraction.denominator)
    twos = 0
    fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("fraction has a non-terminating decimal expansion")
    return max(twos, fives)


def fraction_to_decimal(fraction: Fraction, places: int) -> Decimal:
    with localcontext() as context:
        context.prec = max(
            80,
            len(str(abs(fraction.numerator))) + len(str(fraction.denominator)) + places + 10,
        )
        return (Decimal(fraction.numerator) / Decimal(fraction.denominator)).quantize(
            Decimal(1).scaleb(-places)
        )


def locate_data_points(root: ET.Element) -> ET.Element:
    containers = descendants_by_name(root, "dataPoints")
    if len(containers) != 1:
        raise ConversionError(
            f"expected exactly one dataPoints element, found {len(containers)}"
        )
    return containers[0]


def locate_intensity_element(data_points: ET.Element) -> ET.Element:
    candidates = [
        child
        for child in list(data_points)
        if local_name(child.tag) in {"counts", "intensities"}
    ]
    if len(candidates) != 1:
        raise ConversionError(
            "expected exactly one direct counts/intensities element under dataPoints, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def locate_two_theta_positions(data_points: ET.Element) -> ET.Element:
    candidates = [
        child
        for child in list(data_points)
        if local_name(child.tag) == "positions"
        and child.attrib.get("axis") == "2Theta"
    ]
    if len(candidates) != 1:
        raise ConversionError(
            "expected exactly one direct 2Theta positions element under dataPoints, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def build_two_theta_values(
    position_element: ET.Element, point_count: int
) -> tuple[list[str], list[Decimal], str, str, list[str]]:
    """Return text values, parsed values, source description, step, warnings."""

    warnings: list[str] = []
    list_position_element = child_by_name(position_element, "listPositions")
    if list_position_element is not None:
        raw_tokens = split_tokens(clean_text(list_position_element))
        if not raw_tokens:
            raise ConversionError("listPositions is empty")
        values = parse_decimal_tokens(raw_tokens, "2Theta listPositions")
        if len(values) != point_count:
            raise ConversionError(
                "2Theta listPositions point count does not match intensity count: "
                f"{len(values)} != {point_count}"
            )
        step_text = ""
        if len(values) > 1:
            differences = [values[i + 1] - values[i] for i in range(len(values) - 1)]
            if all(difference == differences[0] for difference in differences[1:]):
                step_text = format_decimal(differences[0])
            else:
                warnings.append("non_uniform_two_theta_spacing")
        return (
            raw_tokens,
            values,
            "listPositions",
            step_text,
            warnings,
        )

    start_element = child_by_name(position_element, "startPosition")
    end_element = child_by_name(position_element, "endPosition")
    start_raw = clean_text(start_element)
    end_raw = clean_text(end_element)
    if not start_raw or not end_raw:
        raise ConversionError(
            "2Theta positions contain neither listPositions nor both "
            "startPosition/endPosition"
        )
    start = parse_decimal_tokens([start_raw], "2Theta startPosition")[0]
    end = parse_decimal_tokens([end_raw], "2Theta endPosition")[0]

    if point_count == 0:
        raise ConversionError("intensity data is empty")
    if point_count == 1:
        if start != end:
            warnings.append("single_point_scan_start_and_end_differ")
        return (
            [start_raw],
            [start],
            "startPosition/endPosition (single point)",
            "",
            warnings,
        )

    start_fraction = Fraction(start)
    end_fraction = Fraction(end)
    step_fraction = (end_fraction - start_fraction) / (point_count - 1)

    if fraction_has_finite_decimal(step_fraction):
        step_places = fraction_decimal_places(step_fraction)
        position_places = max(
            decimal_places(start_raw),
            decimal_places(end_raw),
            step_places,
        )
        step = fraction_to_decimal(step_fraction, position_places)
        with localcontext() as context:
            context.prec = max(80, position_places + 30)
            values = [start + step * index for index in range(point_count)]
        values[-1] = end
        raw_tokens = [format_decimal(value, position_places) for value in values]
        raw_tokens[0] = start_raw
        raw_tokens[-1] = end_raw
        return (
            raw_tokens,
            values,
            "startPosition/endPosition linear interpolation",
            format_decimal(step, position_places),
            warnings,
        )

    # A repeating decimal step cannot be represented exactly in a finite TXT
    # coordinate. Keep a high but bounded precision and make the limitation
    # explicit in the report instead of hiding it.
    position_places = max(decimal_places(start_raw), decimal_places(end_raw), 15)
    with localcontext() as context:
        context.prec = position_places + 40
        step = Decimal(step_fraction.numerator) / Decimal(step_fraction.denominator)
        values = [start + step * index for index in range(point_count)]
    values[-1] = end
    raw_tokens = [format_decimal(value, position_places) for value in values]
    raw_tokens[0] = start_raw
    raw_tokens[-1] = end_raw
    warnings.append("non_terminating_derived_step_rounded_to_15_decimal_places")
    return (
        raw_tokens,
        values,
        "startPosition/endPosition linear interpolation",
        format_decimal(step, position_places),
        warnings,
    )


def dataset_group(relative_path: Path) -> str:
    parts = set(relative_path.parts)
    if "pairwise_reactions_patterns" in parts:
        return "pairwise_reactions_patterns"
    if "singple_phase_precursor_patterns" in parts:
        return "singple_phase_precursor_patterns"
    if "precursor_mixture_patterns" in parts:
        return "precursor_mixture_patterns"
    raise ConversionError(
        "source file is outside the expected dataset groups: "
        f"{relative_path.as_posix()}"
    )


def namespace_uri(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag.split("}", 1)[0][1:]
    return ""


def convert_one(
    source: Path,
    input_root: Path,
    output_root: Path,
    overwrite: bool,
) -> ConvertedPattern:
    relative_path = source.relative_to(input_root)
    group = dataset_group(relative_path)
    output_path = output_root / group / f"{source.stem}.txt"
    if output_path.exists() and not overwrite:
        raise ConversionError(
            f"output already exists; use --overwrite to replace generated output: "
            f"{output_path}"
        )

    try:
        root = ET.parse(source).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ConversionError(f"cannot parse XML: {exc}") from exc

    data_points = locate_data_points(root)
    intensity_element = locate_intensity_element(data_points)
    intensity_tokens = split_tokens(intensity_element.text or "")
    if not intensity_tokens:
        raise ConversionError("intensity data is empty")
    intensity_values = parse_decimal_tokens(
        intensity_tokens, local_name(intensity_element.tag)
    )

    position_element = locate_two_theta_positions(data_points)
    (
        two_theta_tokens,
        two_theta_values,
        position_source,
        step_size,
        warnings,
    ) = build_two_theta_values(position_element, len(intensity_tokens))

    if len(two_theta_tokens) != len(intensity_tokens):
        raise ConversionError(
            "two_theta/intensity point count mismatch: "
            f"{len(two_theta_tokens)} != {len(intensity_tokens)}"
        )

    monotonic = all(
        two_theta_values[index] < two_theta_values[index + 1]
        for index in range(len(two_theta_values) - 1)
    )
    if not monotonic:
        warnings.append("two_theta_not_strictly_increasing")

    all_zero = all(value == 0 for value in intensity_values)
    if all_zero:
        warnings.append("all_intensities_are_zero")

    sample = first_descendant(root, "sample")
    sample_id = clean_text(child_by_name(sample, "id"))
    sample_name = clean_text(child_by_name(sample, "name"))

    used_wavelength = first_descendant(root, "usedWavelength")
    k_alpha_1 = clean_text(child_by_name(used_wavelength, "kAlpha1"))
    k_alpha_2 = clean_text(child_by_name(used_wavelength, "kAlpha2"))
    k_beta = clean_text(child_by_name(used_wavelength, "kBeta"))
    ratio_k_alpha_2_k_alpha_1 = clean_text(
        child_by_name(used_wavelength, "ratioKAlpha2KAlpha1")
    )
    wavelength_unit = ""
    k_alpha_1_element = child_by_name(used_wavelength, "kAlpha1")
    if k_alpha_1_element is not None:
        wavelength_unit = k_alpha_1_element.attrib.get("unit", "")
    wavelength_intended = (
        used_wavelength.attrib.get("intended", "") if used_wavelength is not None else ""
    )

    xrd_measurement = first_descendant(root, "xrdMeasurement")
    scan = first_descendant(root, "scan")
    anode_element = first_descendant(root, "anodeMaterial")
    counting_element = first_descendant(root, "commonCountingTime")
    anode_material = clean_text(anode_element)
    counting_time = clean_text(counting_element)
    counting_time_unit = (
        counting_element.attrib.get("unit", "")
        if counting_element is not None
        else ""
    )
    scan_mode = scan.attrib.get("mode", "") if scan is not None else ""
    measurement_type = (
        xrd_measurement.attrib.get("measurementType", "")
        if xrd_measurement is not None
        else ""
    )
    sample_mode = (
        xrd_measurement.attrib.get("sampleMode", "")
        if xrd_measurement is not None
        else ""
    )

    two_theta_unit = position_element.attrib.get("unit", "")
    original_relative = relative_path.as_posix()
    output_relative = output_path.relative_to(output_root).as_posix()

    metadata_lines = [
        "# SOURCE_FORMAT: XRDML",
        f"# ORIGINAL_FILE: {source.name}",
        f"# ORIGINAL_RELATIVE_PATH: {original_relative}",
        f"# DATASET_GROUP: {group}",
    ]
    if sample_name:
        metadata_lines.append(f"# SAMPLE_NAME: {sample_name}")
    if sample_id:
        metadata_lines.append(f"# SAMPLE_ID: {sample_id}")
    if two_theta_unit:
        metadata_lines.append(f"# AXIS: 2Theta ({two_theta_unit})")
    start_position = clean_text(child_by_name(position_element, "startPosition"))
    end_position = clean_text(child_by_name(position_element, "endPosition"))
    if start_position:
        metadata_lines.append(
            f"# START_POSITION: {start_position}"
            f"{' ' + two_theta_unit if two_theta_unit else ''}"
        )
    if end_position:
        metadata_lines.append(
            f"# END_POSITION: {end_position}"
            f"{' ' + two_theta_unit if two_theta_unit else ''}"
        )
    if step_size:
        metadata_lines.append(
            f"# STEP_SIZE: {step_size}{' ' + two_theta_unit if two_theta_unit else ''}"
        )
        metadata_lines.append(f"# STEP_SIZE_SOURCE: {position_source}")
    metadata_lines.append(f"# POINT_COUNT: {len(intensity_tokens)}")
    metadata_lines.append(f"# POSITION_SOURCE: {position_source}")
    if k_alpha_1:
        metadata_lines.append(
            f"# WAVELENGTH: {k_alpha_1}"
            f"{' ' + wavelength_unit if wavelength_unit else ''}"
        )
        source_text = "usedWavelength/kAlpha1"
        if wavelength_intended:
            source_text += f" intended={wavelength_intended}"
        metadata_lines.append(f"# WAVELENGTH_SOURCE: {source_text}")
    if k_alpha_2:
        metadata_lines.append(
            f"# K_ALPHA_2: {k_alpha_2}"
            f"{' ' + wavelength_unit if wavelength_unit else ''}"
        )
    if k_beta:
        metadata_lines.append(
            f"# K_BETA: {k_beta}"
            f"{' ' + wavelength_unit if wavelength_unit else ''}"
        )
    if ratio_k_alpha_2_k_alpha_1:
        metadata_lines.append(
            f"# RATIO_KALPHA2_KALPHA1: {ratio_k_alpha_2_k_alpha_1}"
        )
    if anode_material:
        metadata_lines.append(f"# ANODE_MATERIAL: {anode_material}")
    if scan_mode:
        metadata_lines.append(f"# SCAN_MODE: {scan_mode}")
    if measurement_type:
        metadata_lines.append(f"# MEASUREMENT_TYPE: {measurement_type}")
    if sample_mode:
        metadata_lines.append(f"# SAMPLE_MODE: {sample_mode}")
    if counting_time:
        metadata_lines.append(
            f"# COUNTING_TIME: {counting_time}"
            f"{' ' + counting_time_unit if counting_time_unit else ''}"
        )
        metadata_lines.append(
            f"# COUNTING_TIME_SOURCE: {local_name(counting_element.tag)}"
        )
    metadata_lines.append(
        f"# XRDML_NAMESPACE: {namespace_uri(root) or 'none'}"
    )
    metadata_lines.append("# two_theta intensity")

    output_text = "\n".join(
        metadata_lines
        + [
            f"{two_theta}  {intensity}"
            for two_theta, intensity in zip(two_theta_tokens, intensity_tokens)
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".tmp")
    temporary_path.write_text(output_text + "\n", encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)

    row = {
        "original_file": source.name,
        "original_relative_path": original_relative,
        "output_file": output_relative,
        "dataset_group": group,
        "point_count": str(len(intensity_tokens)),
        "two_theta_point_count": str(len(two_theta_values)),
        "intensity_point_count": str(len(intensity_values)),
        "two_theta_min": format_decimal(min(two_theta_values)),
        "two_theta_max": format_decimal(max(two_theta_values)),
        "intensity_min": format_decimal(min(intensity_values)),
        "intensity_max": format_decimal(max(intensity_values)),
        "wavelength": (
            f"{k_alpha_1} {wavelength_unit}".strip() if k_alpha_1 else ""
        ),
        "anode_material": anode_material,
        "scan_mode": scan_mode,
        "counting_time": (
            f"{counting_time} {counting_time_unit}".strip()
            if counting_time
            else ""
        ),
        "position_source": position_source,
        "step_size": (
            f"{step_size} {two_theta_unit}".strip() if step_size else ""
        ),
        "intensity_source": local_name(intensity_element.tag),
        "conversion_status": "warning" if warnings else "success",
        "warning": "; ".join(warnings),
    }
    return ConvertedPattern(
        row=row,
        points=list(zip(two_theta_tokens, intensity_tokens)),
    )


def write_report(report_path: Path, rows: list[dict[str, str]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = report_path.with_name(report_path.name + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(report_path)


def select_preview_patterns(
    converted: list[ConvertedPattern], seed: int
) -> list[ConvertedPattern]:
    rng = random.Random(seed)
    selected: list[ConvertedPattern] = []
    for group in GROUPS:
        candidates = [
            item
            for item in converted
            if item.row["dataset_group"] == group
            and item.row["conversion_status"] != "failed"
        ]
        if candidates:
            selected.append(rng.choice(candidates))
    return selected


def print_preview_patterns(
    converted: list[ConvertedPattern], seed: int, preview_count: int
) -> None:
    print(f"\nRandom preview selection (seed={seed}):")
    for item in select_preview_patterns(converted, seed):
        print(
            f"\n[{item.row['dataset_group']}] "
            f"{item.row['original_relative_path']}"
        )
        for two_theta, intensity in item.points[:preview_count]:
            print(f"{two_theta}  {intensity}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert XRDML experiment scans to TXT without changing source files."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        required=True,
        help="Extracted dataset directory containing the XRDML files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Directory for grouped TXT files and conversion_report.csv.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite TXT/report files previously generated by this script.",
    )
    parser.add_argument(
        "--preview-count",
        type=int,
        default=10,
        help="Number of points to print for each random preview (default: 10).",
    )
    parser.add_argument(
        "--preview-seed",
        type=int,
        default=20261003,
        help="Seed for reproducible random preview selection.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    input_root = args.input_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    if not input_root.is_dir():
        print(f"ERROR: input root does not exist or is not a directory: {input_root}")
        return 2
    if args.preview_count < 0:
        print("ERROR: --preview-count must be non-negative")
        return 2

    sources = sorted(input_root.rglob("*.xrdml"))
    if not sources:
        print(f"ERROR: no .xrdml files found under {input_root}")
        return 2

    converted: list[ConvertedPattern] = []
    rows: list[dict[str, str]] = []
    failures: list[str] = []
    for source in sources:
        try:
            result = convert_one(
                source=source,
                input_root=input_root,
                output_root=output_root,
                overwrite=args.overwrite,
            )
            converted.append(result)
            rows.append(result.row)
        except (ConversionError, OSError, ValueError) as exc:
            relative = source.relative_to(input_root).as_posix()
            row = {column: "" for column in REPORT_COLUMNS}
            row.update(
                {
                    "original_file": source.name,
                    "original_relative_path": relative,
                    "dataset_group": (
                        dataset_group(Path(relative))
                        if any(group in Path(relative).parts for group in GROUPS)
                        else ""
                    ),
                    "conversion_status": "failed",
                    "warning": str(exc),
                }
            )
            rows.append(row)
            failures.append(f"{relative}: {exc}")
            print(f"FAILED: {relative}: {exc}", file=sys.stderr)

    report_path = output_root / "conversion_report.csv"
    try:
        write_report(report_path, sorted(rows, key=lambda row: row["original_relative_path"]))
    except OSError as exc:
        print(f"ERROR: cannot write report {report_path}: {exc}", file=sys.stderr)
        return 2

    print(f"Input root: {input_root}")
    print(f"Output root: {output_root}")
    print(f"XRDML files discovered: {len(sources)}")
    print(f"Converted successfully or with warnings: {len(converted)}")
    print(f"Failed: {len(failures)}")
    print(f"Conversion report: {report_path}")
    print_preview_patterns(converted, args.preview_seed, args.preview_count)

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
