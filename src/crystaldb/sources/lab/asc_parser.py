"""Parser for the laboratory powder-XRD ASC format used by CrystalDB.

The parser reads source bytes without modifying them.  It extracts reliable
header metadata, flattens the sequential integer count block, and reconstructs
the two-theta axis only when START/STOP/STEP/COUNT are internally consistent.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


KEY_VALUE_RE = re.compile(
    r"^\*(?P<key>[A-Z0-9_]+)[ \t]*=[ \t]*(?P<value>[^\r\n]*)$"
)
BEGIN_RE = re.compile(r"^\*BEGIN[ \t]*$")
END_RE = re.compile(r"^\*END[ \t]*$")
GROUP_RE = re.compile(r"^\*GROUP[ \t]*=")
INTEGER_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?$"
)

REQUIRED_SCAN_KEYS = ("START", "STOP", "STEP", "COUNT")
USEFUL_HEADER_KEYS = (
    "TYPE",
    "DATE",
    "GONIO",
    "FILTER",
    "COUNTER",
    "SCAN_AXIS",
    "MEAS_MODE",
    "XRAY_CHAR",
    "WAVE_LENGTH1",
    "WAVE_LENGTH2",
    "SCAN_MODE",
    "XUNIT",
    "YUNIT",
    "START",
    "STOP",
    "STEP",
    "SPEED",
    "KV",
    "MA",
    "COUNT",
    "GROUP_COUNT",
)


@dataclass(frozen=True)
class AscMetadata:
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
    gonio: str | None
    filter_name: str | None
    measurement_mode: str | None
    scan_mode: str | None
    speed: float | None
    group_count: int | None
    header_values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AscParseResult:
    path: Path
    metadata: AscMetadata
    intensities: tuple[int, ...]
    two_theta: tuple[float, ...]
    parse_status: str
    parse_warnings: tuple[str, ...]
    begin_count: int
    end_count: int
    group_marker_count: int
    count_match: bool | None
    axis_consistent: bool | None
    final_x_matches_stop: bool | None
    raw_bytes_sha256: str | None = None

    @property
    def canonicalizable(self) -> bool:
        return (
            self.parse_status in {"ok", "partial"}
            and self.count_match is True
            and self.axis_consistent is True
            and self.final_x_matches_stop is True
            and len(self.two_theta) == len(self.intensities)
        )


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    token = value.split(",", 1)[0].strip()
    if not FLOAT_RE.fullmatch(token):
        return None
    return float(token)


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    token = value.split(",", 1)[0].strip()
    if not INTEGER_RE.fullmatch(token):
        return None
    return int(token)


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    try:
        parsed = datetime.strptime(token, "%d-%b-%y %H:%M")
    except ValueError:
        return token
    return parsed.strftime("%Y-%m-%d %H:%M")


def _unit(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    if token.casefold() in {"deg.", "deg", "degree", "degrees"}:
        return "degree"
    return token


def _first_token(value: str | None) -> str | None:
    if not value:
        return None
    token = value.split(",", 1)[0].strip()
    return token or None


def _metadata(headers: dict[str, str]) -> AscMetadata:
    return AscMetadata(
        measurement_date=_parse_date(headers.get("DATE")),
        scan_axis=headers.get("SCAN_AXIS") or None,
        x_unit=_unit(headers.get("XUNIT")),
        y_unit=headers.get("YUNIT") or None,
        start_2theta_deg=_parse_float(headers.get("START")),
        stop_2theta_deg=_parse_float(headers.get("STOP")),
        step_2theta_deg=_parse_float(headers.get("STEP")),
        point_count=_parse_int(headers.get("COUNT")),
        radiation_characteristic=headers.get("XRAY_CHAR") or None,
        wavelength_kalpha1_angstrom=_parse_float(headers.get("WAVE_LENGTH1")),
        wavelength_kalpha2_angstrom=_parse_float(headers.get("WAVE_LENGTH2")),
        voltage_kv=_parse_float(headers.get("KV")),
        current_ma=_parse_float(headers.get("MA")),
        detector=_first_token(headers.get("COUNTER")),
        gonio=headers.get("GONIO") or None,
        filter_name=headers.get("FILTER") or None,
        measurement_mode=headers.get("MEAS_MODE") or None,
        scan_mode=headers.get("SCAN_MODE") or None,
        speed=_parse_float(headers.get("SPEED")),
        group_count=_parse_int(headers.get("GROUP_COUNT")),
        header_values=dict(headers),
    )


def _axis_check(
    metadata: AscMetadata,
    intensity_count: int,
) -> tuple[tuple[float, ...], bool | None, bool | None, list[str]]:
    warnings: list[str] = []
    axis_name = (metadata.scan_axis or "").casefold().replace(" ", "")
    if "2theta" not in axis_name:
        warnings.append("scan_axis_not_confirmed_2theta")
        return (), False, False, warnings
    if (metadata.x_unit or "").casefold() != "degree":
        warnings.append("x_unit_not_confirmed_degree")
        return (), False, False, warnings
    start = metadata.start_2theta_deg
    stop = metadata.stop_2theta_deg
    step = metadata.step_2theta_deg
    count = metadata.point_count
    if start is None or stop is None or step is None or count is None:
        missing = [
            key
            for key, value in (
                ("START", start),
                ("STOP", stop),
                ("STEP", step),
                ("COUNT", count),
            )
            if value is None
        ]
        warnings.append("missing_scan_fields:" + ",".join(missing))
        return (), None, None, warnings
    if step <= 0 or count <= 0:
        warnings.append("invalid_scan_axis_values")
        return (), False, False, warnings

    expected_count = round((stop - start) / step) + 1
    axis_consistent = expected_count == count
    if not axis_consistent:
        warnings.append(
            f"scan_count_inconsistent:expected={expected_count};declared={count}"
        )

    axis = tuple(start + index * step for index in range(count))
    final_x_matches_stop = math.isclose(
        axis[-1],
        stop,
        rel_tol=1e-9,
        abs_tol=1e-8,
    )
    if not final_x_matches_stop:
        warnings.append(
            f"scan_stop_mismatch:reconstructed={axis[-1]:.12g};declared={stop:.12g}"
        )
    if intensity_count != count:
        warnings.append(
            f"intensity_count_mismatch:parsed={intensity_count};declared={count}"
        )
    return axis, axis_consistent, final_x_matches_stop, warnings


def parse_asc(path: Path, raw_bytes_sha256: str | None = None) -> AscParseResult:
    """Parse one ASC file without changing its bytes."""

    warnings: list[str] = []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        metadata = _metadata({})
        return AscParseResult(
            path=path,
            metadata=metadata,
            intensities=(),
            two_theta=(),
            parse_status="failed",
            parse_warnings=(f"read_error:{exc}",),
            begin_count=0,
            end_count=0,
            group_marker_count=0,
            count_match=None,
            axis_consistent=None,
            final_x_matches_stop=None,
            raw_bytes_sha256=raw_bytes_sha256,
        )

    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        text = raw.decode("ascii", errors="replace")
        warnings.append(f"non_ascii_source:{exc}")

    lines = text.splitlines()
    headers: dict[str, str] = {}
    for line in lines:
        match = KEY_VALUE_RE.match(line)
        if match and match.group("key") in USEFUL_HEADER_KEYS:
            headers.setdefault(match.group("key"), match.group("value").strip())

    metadata = _metadata(headers)
    begin_indices = [index for index, line in enumerate(lines) if BEGIN_RE.match(line)]
    end_indices = [index for index, line in enumerate(lines) if END_RE.match(line)]
    group_indices = [
        index for index, line in enumerate(lines) if GROUP_RE.match(line)
    ]
    begin_count = len(begin_indices)
    end_count = len(end_indices)
    group_marker_count = len(group_indices)

    if begin_count != 1 or end_count != 1 or group_marker_count != 1:
        warnings.append(
            "multi_group_requires_review"
            if begin_count > 1 or end_count > 1 or group_marker_count > 1
            else "missing_or_ambiguous_group_markers"
        )
        return AscParseResult(
            path=path,
            metadata=metadata,
            intensities=(),
            two_theta=(),
            parse_status="failed",
            parse_warnings=tuple(warnings),
            begin_count=begin_count,
            end_count=end_count,
            group_marker_count=group_marker_count,
            count_match=None,
            axis_consistent=None,
            final_x_matches_stop=None,
            raw_bytes_sha256=raw_bytes_sha256,
        )

    if metadata.group_count is not None and metadata.group_count != 1:
        warnings.append(f"multi_group_requires_review:declared={metadata.group_count}")

    begin = begin_indices[0]
    end = end_indices[0]
    group = group_indices[0]
    if not (begin < group < end):
        warnings.append("group_markers_out_of_order")
        return AscParseResult(
            path=path,
            metadata=metadata,
            intensities=(),
            two_theta=(),
            parse_status="failed",
            parse_warnings=tuple(warnings),
            begin_count=begin_count,
            end_count=end_count,
            group_marker_count=group_marker_count,
            count_match=None,
            axis_consistent=None,
            final_x_matches_stop=None,
            raw_bytes_sha256=raw_bytes_sha256,
        )

    values: list[int] = []
    invalid_tokens: list[str] = []
    for line in lines[group + 1 : end]:
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        for token in line.split(","):
            token = token.strip()
            if not token:
                continue
            if INTEGER_RE.fullmatch(token):
                values.append(int(token))
            else:
                invalid_tokens.append(token)
    if invalid_tokens:
        warnings.append(
            "invalid_intensity_tokens:" + ",".join(invalid_tokens[:5])
        )

    axis, axis_consistent, final_x_matches_stop, axis_warnings = _axis_check(
        metadata,
        len(values),
    )
    warnings.extend(axis_warnings)
    count_match = (
        metadata.point_count is not None and len(values) == metadata.point_count
    )
    if not count_match and metadata.point_count is not None:
        count_match = False

    critical_failure = bool(invalid_tokens) or (
        metadata.point_count is None
        or axis_consistent is False
        or final_x_matches_stop is False
        or count_match is False
    )
    missing_useful_metadata = [
        key
        for key in REQUIRED_SCAN_KEYS
        if key not in headers or not headers[key].strip()
    ]
    if missing_useful_metadata and not critical_failure:
        warnings.append("missing_scan_header_fields:" + ",".join(missing_useful_metadata))

    if critical_failure:
        status = "failed"
    elif warnings:
        status = "partial"
    else:
        status = "ok"
    return AscParseResult(
        path=path,
        metadata=metadata,
        intensities=tuple(values),
        two_theta=axis,
        parse_status=status,
        parse_warnings=tuple(warnings),
        begin_count=begin_count,
        end_count=end_count,
        group_marker_count=group_marker_count,
        count_match=count_match,
        axis_consistent=axis_consistent,
        final_x_matches_stop=final_x_matches_stop,
        raw_bytes_sha256=raw_bytes_sha256,
    )
