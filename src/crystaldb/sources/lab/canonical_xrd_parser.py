"""Parser and QC for canonical laboratory powder-XRD TXT files."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HEADER_RE = re.compile(
    r"^\s*#\s*(?P<key>[A-Za-z0-9_]+)\s*:\s*(?P<value>.*?)\s*$"
)
INTEGER_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?$"
)

IDENTITY_FIELDS = (
    "sample_id",
    "measurement_id",
    "pattern_id",
    "source",
    "data_origin",
    "modality",
)
OPTIONAL_METADATA_FIELDS = (
    "contributor",
    "source_series_label",
    "source_sample_label",
    "nominal_element_ratio",
    "phase_character",
    "original_filename",
    "original_relative_path",
    "original_sha256",
    "measurement_date",
    "scan_axis",
    "x_unit",
    "y_unit",
    "radiation_characteristic",
    "wavelength_kalpha1_angstrom",
    "wavelength_kalpha2_angstrom",
    "voltage_kv",
    "current_ma",
    "detector",
)


@dataclass(frozen=True)
class CanonicalXrdRecord:
    """All parsed metadata, data arrays, and QC results for one TXT file."""

    path: Path
    sample_id: str | None
    measurement_id: str | None
    pattern_id: str | None
    source: str | None
    data_origin: str | None
    modality: str | None
    contributor: str | None
    source_series_label: str | None
    source_sample_label: str | None
    nominal_element_ratio: str | None
    phase_character: str | None
    original_filename: str | None
    original_relative_path: str | None
    original_sha256: str | None
    measurement_date: str | None
    scan_axis: str | None
    x_unit: str | None
    y_unit: str | None
    start_2theta_deg: float | None
    stop_2theta_deg: float | None
    step_2theta_deg: float | None
    point_count: int | None
    radiation_characteristic: str | None
    wavelength_kalpha1_angstrom: float | None
    wavelength_kalpha2_angstrom: float | None
    voltage_kv: float | None
    current_ma: float | None
    detector: str | None
    two_theta: tuple[float, ...]
    intensity: tuple[int | float, ...]
    parse_status: str
    parse_warnings: tuple[str, ...]
    qc: dict[str, bool | None]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation used by tests and reports."""
        result = dict(self.__dict__)
        result["path"] = str(self.path)
        result["two_theta"] = list(self.two_theta)
        result["intensity"] = list(self.intensity)
        result["parse_warnings"] = list(self.parse_warnings)
        return result


def _empty_record(path: Path, warnings: list[str]) -> CanonicalXrdRecord:
    return CanonicalXrdRecord(
        path=path,
        sample_id=None,
        measurement_id=None,
        pattern_id=None,
        source=None,
        data_origin=None,
        modality=None,
        contributor=None,
        source_series_label=None,
        source_sample_label=None,
        nominal_element_ratio=None,
        phase_character=None,
        original_filename=None,
        original_relative_path=None,
        original_sha256=None,
        measurement_date=None,
        scan_axis=None,
        x_unit=None,
        y_unit=None,
        start_2theta_deg=None,
        stop_2theta_deg=None,
        step_2theta_deg=None,
        point_count=None,
        radiation_characteristic=None,
        wavelength_kalpha1_angstrom=None,
        wavelength_kalpha2_angstrom=None,
        voltage_kv=None,
        current_ma=None,
        detector=None,
        two_theta=(),
        intensity=(),
        parse_status="failed",
        parse_warnings=tuple(warnings),
        qc={
            "point_count_match": None,
            "axis_consistent": None,
            "start_match": None,
            "stop_match": None,
            "spacing_consistent": None,
        },
    )


def _header_value(value: str) -> str | None:
    value = value.strip()
    if not value or value.casefold() == "null":
        return None
    return value


def _parse_float(
    headers: dict[str, str | None],
    key: str,
    warnings: list[str],
    *,
    required: bool = False,
) -> float | None:
    value = headers.get(key)
    if value is None:
        if required:
            warnings.append(f"missing_required_metadata:{key}")
        return None
    if not FLOAT_RE.fullmatch(value):
        warnings.append(f"invalid_numeric_metadata:{key}:{value}")
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        warnings.append(f"non_finite_numeric_metadata:{key}")
        return None
    return parsed


def _parse_int(
    headers: dict[str, str | None],
    key: str,
    warnings: list[str],
    *,
    required: bool = False,
) -> int | None:
    value = headers.get(key)
    if value is None:
        if required:
            warnings.append(f"missing_required_metadata:{key}")
        return None
    if not INTEGER_RE.fullmatch(value):
        warnings.append(f"invalid_integer_metadata:{key}:{value}")
        return None
    return int(value)


def _parse_number(token: str) -> int | float:
    if INTEGER_RE.fullmatch(token):
        return int(token)
    if not FLOAT_RE.fullmatch(token):
        raise ValueError(token)
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(token)
    return value


def _axis_qc(
    two_theta: tuple[float, ...],
    point_count: int | None,
    start: float | None,
    stop: float | None,
    step: float | None,
    scan_axis: str | None,
    x_unit: str | None,
) -> dict[str, bool | None]:
    point_count_match = (
        point_count is not None
        and len(two_theta) == point_count
    )
    if not two_theta or start is None or stop is None or step is None:
        return {
            "point_count_match": point_count_match,
            "axis_consistent": None,
            "start_match": None,
            "stop_match": None,
            "spacing_consistent": None,
        }

    scan_axis_ok = "2theta" in (scan_axis or "").casefold().replace(" ", "")
    x_unit_ok = (x_unit or "").casefold() == "degree"
    start_match = math.isclose(two_theta[0], start, rel_tol=1e-9, abs_tol=1e-8)
    stop_match = math.isclose(two_theta[-1], stop, rel_tol=1e-9, abs_tol=1e-8)
    spacing_consistent = all(
        math.isclose(
            current - previous,
            step,
            rel_tol=1e-9,
            abs_tol=1e-8,
        )
        for previous, current in zip(two_theta, two_theta[1:])
    )
    expected_count = round((stop - start) / step) + 1 if step != 0 else None
    declared_axis_count_match = expected_count == point_count
    axis_consistent = (
        step > 0
        and scan_axis_ok
        and x_unit_ok
        and declared_axis_count_match
        and start_match
        and stop_match
        and spacing_consistent
    )
    return {
        "point_count_match": point_count_match,
        "axis_consistent": axis_consistent,
        "start_match": start_match,
        "stop_match": stop_match,
        "spacing_consistent": spacing_consistent,
    }


def parse_canonical_xrd(path: Path) -> CanonicalXrdRecord:
    """Parse one canonical TXT without changing the source file."""

    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return _empty_record(path, [f"read_error:{exc}"])

    warnings: list[str] = []
    headers: dict[str, str | None] = {}
    duplicate_keys: set[str] = set()
    two_theta: list[float] = []
    intensity: list[int | float] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        header_match = HEADER_RE.match(line)
        if header_match:
            key = header_match.group("key")
            if key in headers:
                duplicate_keys.add(key)
            headers[key] = _header_value(header_match.group("value"))
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        tokens = stripped.split()
        if len(tokens) != 2:
            warnings.append(
                f"invalid_data_columns:line={line_number};count={len(tokens)}"
            )
            continue
        try:
            x_value = float(tokens[0])
            y_value = _parse_number(tokens[1])
        except ValueError:
            warnings.append(
                f"invalid_data_value:line={line_number};value={stripped}"
            )
            continue
        if not math.isfinite(x_value):
            warnings.append(f"non_finite_two_theta:line={line_number}")
            continue
        two_theta.append(x_value)
        intensity.append(y_value)

    warnings.extend(f"duplicate_header_key:{key}" for key in sorted(duplicate_keys))

    values: dict[str, Any] = {
        key: headers.get(key)
        for key in IDENTITY_FIELDS + OPTIONAL_METADATA_FIELDS
    }
    values["start_2theta_deg"] = _parse_float(
        headers,
        "start_2theta_deg",
        warnings,
        required=True,
    )
    values["stop_2theta_deg"] = _parse_float(
        headers,
        "stop_2theta_deg",
        warnings,
        required=True,
    )
    values["step_2theta_deg"] = _parse_float(
        headers,
        "step_2theta_deg",
        warnings,
        required=True,
    )
    values["point_count"] = _parse_int(
        headers,
        "point_count",
        warnings,
        required=True,
    )
    for key in (
        "wavelength_kalpha1_angstrom",
        "wavelength_kalpha2_angstrom",
        "voltage_kv",
        "current_ma",
    ):
        values[key] = _parse_float(headers, key, warnings)

    qc = _axis_qc(
        tuple(two_theta),
        values["point_count"],
        values["start_2theta_deg"],
        values["stop_2theta_deg"],
        values["step_2theta_deg"],
        values["scan_axis"],
        values["x_unit"],
    )

    for key in IDENTITY_FIELDS:
        if not values[key]:
            warnings.append(f"missing_required_metadata:{key}")

    if values["point_count"] is not None and values["point_count"] <= 0:
        warnings.append("invalid_point_count")
    if values["point_count"] is not None and not qc["point_count_match"]:
        warnings.append(
            "point_count_mismatch:"
            f"declared={values['point_count']};parsed={len(two_theta)}"
        )
    if qc["axis_consistent"] is False:
        warnings.append("axis_inconsistent")

    for key in OPTIONAL_METADATA_FIELDS:
        if values[key] is None:
            warnings.append(f"missing_metadata:{key}")

    critical_warning_prefixes = (
        "read_error:",
        "invalid_data_columns:",
        "invalid_data_value:",
        "non_finite_two_theta:",
        "missing_required_metadata:",
        "invalid_numeric_metadata:start_2theta_deg:",
        "invalid_numeric_metadata:stop_2theta_deg:",
        "invalid_numeric_metadata:step_2theta_deg:",
        "invalid_integer_metadata:point_count:",
        "missing_required_metadata:start_2theta_deg",
        "missing_required_metadata:stop_2theta_deg",
        "missing_required_metadata:step_2theta_deg",
        "missing_required_metadata:point_count",
        "invalid_point_count",
        "point_count_mismatch:",
        "axis_inconsistent",
    )
    critical_failure = any(
        warning.startswith(critical_warning_prefixes)
        for warning in warnings
    )
    if values["point_count"] is None:
        critical_failure = True
    if qc["axis_consistent"] is not True:
        critical_failure = True

    if critical_failure:
        status = "failed"
    elif warnings:
        status = "partial"
    else:
        status = "ok"

    return CanonicalXrdRecord(
        path=path,
        two_theta=tuple(two_theta),
        intensity=tuple(intensity),
        parse_status=status,
        parse_warnings=tuple(warnings),
        qc=qc,
        **values,
    )


__all__ = ["CanonicalXrdRecord", "parse_canonical_xrd"]
