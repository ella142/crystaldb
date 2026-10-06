#!/usr/bin/env python3
"""Build canonical experimental powder-XRD TXT files from group ASC sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from crystaldb.sources.lab.asc_parser import AscParseResult, parse_asc


DEFAULT_SOURCE_ROOT = Path(r"D:\document\aiformaterials\DATA")
CANONICAL_ROOT = REPOSITORY_ROOT / "data" / "powder" / "lab"
PATTERN_ROOT = CANONICAL_ROOT / "patterns"
MANIFEST_ROOT = CANONICAL_ROOT / "manifests"
ID_MAP_PATH = REPOSITORY_ROOT / "data" / "mappings" / "lab_xrd_id_map_v1.json"
OVERRIDE_PATH = REPOSITORY_ROOT / "data" / "mappings" / "lab_xrd_label_overrides_v1.json"
MANIFEST_FIELDS = [
    "sample_id",
    "measurement_id",
    "pattern_id",
    "source",
    "data_origin",
    "modality",
    "contributor",
    "source_series_label",
    "source_sample_label",
    "nominal_element_ratio",
    "phase_character",
    "original_filename",
    "original_relative_path",
    "original_absolute_path",
    "raw_sha256",
    "canonical_filename",
    "canonical_relative_path",
    "canonical_sha256",
    "measurement_date",
    "scan_axis",
    "x_unit",
    "y_unit",
    "start_2theta_deg",
    "stop_2theta_deg",
    "step_2theta_deg",
    "point_count",
    "radiation_characteristic",
    "wavelength_kalpha1_angstrom",
    "wavelength_kalpha2_angstrom",
    "voltage_kv",
    "current_ma",
    "detector",
    "parse_status",
    "parse_warnings",
    "grouping_rule",
    "grouping_confidence",
]
KNOWN_CONTRIBUTORS = {
    "jl": "JL",
    "lx": "LX",
    "wzq": "WZQ",
    "lihong wang": "Lihong Wang",
}
EXPLICIT_SERIES_LABELS = {"sn-p-se": "Sn-P-Se"}
FORMULA_TOKEN_RE = re.compile(r"^[A-Z][a-z]?(?:\d+(?:\.\d+)?)?(?:[A-Z][a-z]?(?:\d+(?:\.\d+)?)?)+$")
REPEAT_RE = re.compile(r"^(?P<core>.+?)(?P<sep>[-_])(?P<number>[1-9]\d*)$")
PADDED_REPEAT_RE = re.compile(r"^(?P<core>.+?)(?P<sep>[-_])(?P<number>00[1-9])$")
COPY_SUFFIX_RE = re.compile(r"(?i)(?:\s*-\s*copy(?:\s*\(\d+\))?|\s*\(\d+\)|\s+copy)$")

PILOT_PATHS = [
    "JL/Co-S-Se-Te/Co3S4-1100-1-20measure-CoS.asc",
    "JL/IrSb3.asc",
    "JL/MoCh2/Re-MoS2-20.asc",
    "JL/MoCh2/Re-MoS2-20-2.asc",
    "LX/2026/Sn-P-Se/113-20_001.asc",
    "WZQ/260624/Mo6Se8-1.asc",
    "WZQ/260624/Mo6Se8-2.asc",
    "WZQ/260624/Mo6Se8-3.asc",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_path(path: Path) -> str:
    return PurePosixPath(*path.parts).as_posix()


def normalized_sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def discover_asc(source_root: Path) -> list[tuple[Path, str]]:
    discovered = [
        (path, stable_path(path.relative_to(source_root)))
        for path in source_root.rglob("*")
        if path.is_file() and path.suffix.casefold() == ".asc"
    ]
    return sorted(discovered, key=lambda item: normalized_sort_key(item[1]))


def parse_repeat(stem: str) -> tuple[str, str, int, bool] | None:
    match = PADDED_REPEAT_RE.fullmatch(stem)
    if match:
        return (
            match.group("core"),
            match.group("sep"),
            int(match.group("number")),
            True,
        )
    match = REPEAT_RE.fullmatch(stem)
    if match:
        return (
            match.group("core"),
            match.group("sep"),
            int(match.group("number")),
            False,
        )
    return None


def is_formula_like(value: str) -> bool:
    token = re.match(r"[A-Za-z][A-Za-z0-9.]*", value)
    if token is None:
        return False
    candidate = token.group(0)
    return bool(FORMULA_TOKEN_RE.fullmatch(candidate)) and any(
        character.isdigit() for character in candidate
    )


def make_grouping(
    sources: list[tuple[Path, str]],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], set[str]]:
    by_directory: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for path, relative in sources:
        by_directory[stable_path(Path(relative).parent).casefold()].append(
            (path, relative)
        )

    group_keys: dict[str, str] = {}
    labels: dict[str, str] = {}
    rules: dict[str, str] = {}
    ambiguous: set[str] = set()
    for directory_key, members in by_directory.items():
        stems = {path.stem.casefold(): (path, relative) for path, relative in members}
        candidates: dict[tuple[str, str], list[tuple[Path, str, int, bool, str]]] = defaultdict(list)
        for path, relative in members:
            match = parse_repeat(path.stem)
            if match is None:
                continue
            core, separator, number, padded = match
            candidates[(core.casefold(), separator)].append(
                (path, relative, number, padded, core)
            )

        repeat_groups: dict[tuple[str, str], tuple[str, list[str], str]] = {}
        for identity, repeated in candidates.items():
            core_key, separator = identity
            core = repeated[0][4]
            base = stems.get(core_key)
            padded_members = [item for item in repeated if item[3]]
            plain_members = [item for item in repeated if not item[3]]
            numbers = sorted(item[2] for item in repeated)
            parent_label = PurePosixPath(members[0][1]).parent.name.casefold()
            directory_evidence = any(parent_label == item[0].stem.casefold() for item in repeated)
            simple_small_sequence = (
                len(plain_members) >= 2
                and numbers == list(range(1, max(numbers) + 1))
                and max(numbers) <= 3
            )
            formula_sequence = (
                is_formula_like(core)
                and len(plain_members) >= 2
                and numbers == list(range(1, max(numbers) + 1))
                and max(numbers) <= 9
            )
            padded_sequence = (
                len(padded_members) >= 2
                and numbers == list(range(1, max(numbers) + 1))
            )
            evidence = bool(base or directory_evidence or simple_small_sequence or formula_sequence or padded_sequence)

            # Copy-style suffixes are provenance, not repeat evidence.
            if COPY_SUFFIX_RE.search(core):
                evidence = False
            if not evidence:
                for item in repeated:
                    if not (item[3] and len(repeated) == 1):
                        ambiguous.add(item[1])
                continue

            paths = [item[1] for item in repeated]
            if base:
                paths.append(base[1])
            rule = (
                "same_directory_base_plus_repeat_suffix"
                if base
                else (
                    "same_directory_directory_context_plus_repeat_suffix"
                    if directory_evidence
                    else "same_directory_contiguous_repeat_sequence"
                )
            )
            repeat_groups[identity] = (core, paths, rule)

        for path, relative in members:
            match = parse_repeat(path.stem)
            identity = (match[0].casefold(), match[1]) if match else None
            selected = repeat_groups.get(identity) if identity else None
            if selected is None:
                # A base member belongs to an evidenced group if one selected
                # repeat group explicitly includes its original path.
                selected = next(
                    (value for value in repeat_groups.values() if relative in value[1]),
                    None,
                )
            if selected:
                core, _, rule = selected
                labels[relative] = core
                group_keys[relative] = f"{directory_key}\0{core.casefold()}"
                rules[relative] = rule
            else:
                labels[relative] = path.stem
                group_keys[relative] = f"{directory_key}\0{path.stem.casefold()}"
                rules[relative] = (
                    "same_directory_repeat_candidate_not_merged"
                    if relative in ambiguous
                    else "same_directory_single_file"
                )
    return group_keys, labels, rules, ambiguous


def contributor(relative: str) -> str:
    root_component = relative.split("/", 1)[0]
    return KNOWN_CONTRIBUTORS.get(root_component.casefold(), "")


def series_label(relative: str) -> str:
    parts = relative.split("/")
    for part in parts[:-1]:
        curated = EXPLICIT_SERIES_LABELS.get(part.casefold())
        if curated:
            return curated
        if "series" in part.casefold():
            return part
    return ""


def infer_nominal_ratio(
    stem: str,
    source_sample_label: str,
    overrides: dict[str, dict[str, Any]],
) -> str:
    mapped = overrides.get(source_sample_label, {}).get("nominal_element_ratio")
    if mapped:
        return str(mapped)
    match = re.match(r"[A-Za-z][A-Za-z0-9.]*", stem)
    if not match:
        return ""
    candidate = match.group(0)
    if candidate.casefold().startswith("co3s4"):
        return "Co3S4"
    return candidate if is_formula_like(candidate) else ""


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def id_value(prefix: str, number: int) -> str:
    return f"{prefix}_{number:06d}"


def id_number(value: str, prefix: str) -> int:
    match = re.fullmatch(re.escape(prefix) + r"_(\d+)", value or "")
    return int(match.group(1)) if match else 0


def assign_stable_ids(
    sources: list[tuple[Path, str]],
    group_keys: dict[str, str],
    raw_hashes: dict[str, str],
    existing_map: dict[str, Any],
) -> dict[str, dict[str, str]]:
    old_records = existing_map.get("records", {})
    if not isinstance(old_records, dict):
        old_records = {}
    groups: dict[str, list[str]] = defaultdict(list)
    for _, relative in sources:
        groups[group_keys[relative]].append(relative)

    max_sample = max(
        [id_number(item.get("sample_id", ""), "LAB_SAM") for item in old_records.values()]
        or [0]
    )
    max_measurement = max(
        [id_number(item.get("measurement_id", ""), "LAB_MEAS") for item in old_records.values()]
        or [0]
    )
    max_pattern = max(
        [id_number(item.get("pattern_id", ""), "LAB_PAT") for item in old_records.values()]
        or [0]
    )
    used_samples: set[str] = set()
    used_measurements: set[str] = set()
    used_patterns: set[str] = set()
    ids: dict[str, dict[str, str]] = {}

    sorted_groups = sorted(
        groups.items(),
        key=lambda item: min(normalized_sort_key(path) for path in item[1]),
    )
    for group_key, relatives in sorted_groups:
        prior_sample_ids = sorted(
            {
                str(old_records.get(relative, {}).get("sample_id", ""))
                for relative in relatives
                if old_records.get(relative, {}).get("sample_id")
            },
            key=lambda value: id_number(value, "LAB_SAM"),
        )
        sample_id = next(
            (value for value in prior_sample_ids if value not in used_samples),
            "",
        )
        if not sample_id:
            max_sample += 1
            sample_id = id_value("LAB_SAM", max_sample)
        used_samples.add(sample_id)

        for relative in sorted(relatives, key=normalized_sort_key):
            previous = old_records.get(relative, {})
            measurement_id = str(previous.get("measurement_id", ""))
            if not measurement_id or measurement_id in used_measurements:
                max_measurement += 1
                measurement_id = id_value("LAB_MEAS", max_measurement)
            used_measurements.add(measurement_id)

            pattern_id = str(previous.get("pattern_id", ""))
            if not pattern_id or pattern_id in used_patterns:
                max_pattern += 1
                pattern_id = id_value("LAB_PAT", max_pattern)
            used_patterns.add(pattern_id)
            ids[relative] = {
                "sample_id": sample_id,
                "measurement_id": measurement_id,
                "pattern_id": pattern_id,
                "grouping_key": group_key,
                "raw_sha256": raw_hashes[relative],
            }
    return ids


def _comment_value(value: Any) -> str:
    if value is None or value == "":
        return "null"
    return str(value).replace("\r", " ").replace("\n", " ")


def render_canonical_txt(
    identity: dict[str, str],
    metadata: Any,
    raw_hash: str,
    source_relative: str,
    source_filename: str,
    source_sample_label: str,
    ratio: str,
    contributor_value: str,
    series: str,
    result: AscParseResult,
) -> str:
    comments = [
        "# CrystalDB experimental powder XRD",
        "# format_version: 1.0",
        "#",
        f"# sample_id: {identity['sample_id']}",
        f"# measurement_id: {identity['measurement_id']}",
        f"# pattern_id: {identity['pattern_id']}",
        "#",
        "# source: lab",
        "# data_origin: experimental",
        "# modality: powder_xrd",
        "#",
        f"# contributor: {_comment_value(contributor_value)}",
        f"# source_series_label: {_comment_value(series)}",
        f"# source_sample_label: {_comment_value(source_sample_label)}",
        f"# nominal_element_ratio: {_comment_value(ratio)}",
        "# phase_character: unknown",
        "#",
        f"# original_filename: {source_filename}",
        f"# original_relative_path: {source_relative}",
        f"# original_sha256: {raw_hash}",
        f"# measurement_date: {_comment_value(metadata.measurement_date)}",
        "#",
        f"# scan_axis: {_comment_value(metadata.scan_axis)}",
        f"# x_unit: {_comment_value(metadata.x_unit)}",
        f"# y_unit: {_comment_value(metadata.y_unit)}",
        f"# start_2theta_deg: {_comment_value(metadata.start_2theta_deg)}",
        f"# stop_2theta_deg: {_comment_value(metadata.stop_2theta_deg)}",
        f"# step_2theta_deg: {_comment_value(metadata.step_2theta_deg)}",
        f"# point_count: {_comment_value(metadata.point_count)}",
        "#",
        f"# radiation_characteristic: {_comment_value(metadata.radiation_characteristic)}",
        f"# wavelength_kalpha1_angstrom: {_comment_value(metadata.wavelength_kalpha1_angstrom)}",
        f"# wavelength_kalpha2_angstrom: {_comment_value(metadata.wavelength_kalpha2_angstrom)}",
        f"# voltage_kv: {_comment_value(metadata.voltage_kv)}",
        f"# current_ma: {_comment_value(metadata.current_ma)}",
        f"# detector: {_comment_value(metadata.detector)}",
        "#",
        "# columns: two_theta_deg intensity_counts",
    ]
    body = [
        f"{two_theta:.6f}\t{intensity}"
        for two_theta, intensity in zip(result.two_theta, result.intensities)
    ]
    return "\n".join(comments + body) + "\n"


def _manifest_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def build_record(
    path: Path,
    relative: str,
    identity: dict[str, str],
    source_root: Path,
    result: AscParseResult,
    raw_hash: str,
    overrides: dict[str, dict[str, Any]],
) -> tuple[dict[str, str], str | None]:
    source_label = identity["source_sample_label"]
    ratio = infer_nominal_ratio(path.stem, source_label, overrides)
    contributor_value = contributor(relative)
    series = series_label(relative)
    canonical_filename = (
        f"{identity['sample_id']}_MEAS_{id_number(identity['measurement_id'], 'LAB_MEAS'):06d}.txt"
    )
    canonical_relative = f"powder/lab/patterns/{canonical_filename}"
    canonical_text: str | None = None
    canonical_hash = ""
    if result.canonicalizable:
        canonical_text = render_canonical_txt(
            identity,
            result.metadata,
            raw_hash,
            relative,
            path.name,
            source_label,
            ratio,
            contributor_value,
            series,
            result,
        )
        canonical_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    metadata = result.metadata
    row = {
        "sample_id": identity["sample_id"],
        "measurement_id": identity["measurement_id"],
        "pattern_id": identity["pattern_id"],
        "source": "lab",
        "data_origin": "experimental",
        "modality": "powder_xrd",
        "contributor": contributor_value,
        "source_series_label": series,
        "source_sample_label": source_label,
        "nominal_element_ratio": ratio,
        "phase_character": "unknown",
        "original_filename": path.name,
        "original_relative_path": relative,
        "original_absolute_path": str(path.resolve()),
        "raw_sha256": raw_hash,
        "canonical_filename": canonical_filename if canonical_text else "",
        "canonical_relative_path": canonical_relative if canonical_text else "",
        "canonical_sha256": canonical_hash,
        "measurement_date": _manifest_value(metadata.measurement_date),
        "scan_axis": _manifest_value(metadata.scan_axis),
        "x_unit": _manifest_value(metadata.x_unit),
        "y_unit": _manifest_value(metadata.y_unit),
        "start_2theta_deg": _manifest_value(metadata.start_2theta_deg),
        "stop_2theta_deg": _manifest_value(metadata.stop_2theta_deg),
        "step_2theta_deg": _manifest_value(metadata.step_2theta_deg),
        "point_count": _manifest_value(metadata.point_count),
        "radiation_characteristic": _manifest_value(metadata.radiation_characteristic),
        "wavelength_kalpha1_angstrom": _manifest_value(metadata.wavelength_kalpha1_angstrom),
        "wavelength_kalpha2_angstrom": _manifest_value(metadata.wavelength_kalpha2_angstrom),
        "voltage_kv": _manifest_value(metadata.voltage_kv),
        "current_ma": _manifest_value(metadata.current_ma),
        "detector": _manifest_value(metadata.detector),
        "parse_status": result.parse_status,
        "parse_warnings": "; ".join(result.parse_warnings),
        "grouping_rule": identity["grouping_rule"],
        "grouping_confidence": identity["grouping_confidence"],
    }
    return row, canonical_text


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=MANIFEST_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_managed_canonical_hashes() -> dict[str, set[str]]:
    managed: dict[str, set[str]] = defaultdict(set)
    for manifest_name in (
        "lab_xrd_pilot_manifest_v1.csv",
        "lab_xrd_manifest_v1.csv",
    ):
        manifest_path = MANIFEST_ROOT / manifest_name
        if not manifest_path.exists():
            continue
        with manifest_path.open("r", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                filename = row.get("canonical_filename", "")
                digest = row.get("canonical_sha256", "")
                if filename and digest:
                    managed[filename].add(digest)
    return managed


def scan_report(
    sources: list[tuple[Path, str]],
    source_root: Path,
    group_keys: dict[str, str],
    rules: dict[str, str],
) -> dict[str, Any]:
    contributors = Counter(contributor(relative) or "<unknown>" for _, relative in sources)
    directories = Counter(str(PurePosixPath(relative).parent) for _, relative in sources)
    group_members: dict[str, list[str]] = defaultdict(list)
    for _, relative in sources:
        group_members[group_keys[relative]].append(relative)
    repeated = [
        {"count": len(paths), "paths": paths}
        for _, paths in sorted(group_members.items())
        if len(paths) > 1
    ]
    group_counts = Counter()
    begin_counts = Counter()
    end_counts = Counter()
    for path, _ in sources:
        raw_text = path.read_bytes().decode("ascii", errors="replace")
        lines = raw_text.splitlines()
        for line in lines:
            match = re.fullmatch(r"\*GROUP_COUNT[ \t]*=[ \t]*(.*)", line)
            if match:
                group_counts[match.group(1).strip()] += 1
                break
        begin_counts[sum(line.strip() == "*BEGIN" for line in lines)] += 1
        end_counts[sum(line.strip() == "*END" for line in lines)] += 1
    return {
        "source_root": str(source_root.resolve()),
        "total_asc_files": len(sources),
        "contributors": dict(sorted(contributors.items())),
        "directory_count": len(directories),
        "directories_by_file_count": [
            {"directory": directory, "asc_count": count}
            for directory, count in directories.most_common()
        ],
        "potential_repeated_measurements": repeated,
        "group_count_variants": dict(sorted(group_counts.items())),
        "begin_marker_count_distribution": dict(sorted(begin_counts.items())),
        "end_marker_count_distribution": dict(sorted(end_counts.items())),
        "grouping_rule_counts": dict(sorted(Counter(rules.values()).items())),
    }


def _pilot_source_list(sources: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    source_by_relative = {relative: path for path, relative in sources}
    missing = [relative for relative in PILOT_PATHS if relative not in source_by_relative]
    if missing:
        raise ValueError("Pilot source files not found: " + ", ".join(missing))
    return [(source_by_relative[relative], relative) for relative in PILOT_PATHS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan, pilot, or fully build canonical lab powder-XRD TXT files."
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scan-only", action="store_true", help="Read and report source structure only.")
    mode.add_argument("--pilot", action="store_true", help="Build the fixed pilot subset (default).")
    mode.add_argument("--full", action="store_true", help="Build every discovered ASC.")
    parser.add_argument(
        "--refresh-ids",
        action="store_true",
        help="Rebuild IDs without using the existing ID map. Use only for initial pilot reset.",
    )
    args = parser.parse_args(argv)

    source_root = args.source_root.resolve()
    if not source_root.exists():
        print(f"ERROR: source root not found: {source_root}", file=sys.stderr)
        return 2
    sources = discover_asc(source_root)
    group_keys, labels, grouping_rules, ambiguous = make_grouping(sources)
    if args.scan_only:
        report = scan_report(sources, source_root, group_keys, grouping_rules)
        report["repeat_suffix_ambiguous_paths"] = sorted(ambiguous)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    pilot_mode = not args.full
    selected_sources = _pilot_source_list(sources) if pilot_mode else sources
    raw_hashes = {relative: sha256_file(path) for path, relative in sources}
    existing_map = {} if args.refresh_ids else load_json_object(ID_MAP_PATH)
    overrides = load_json_object(OVERRIDE_PATH)
    id_assignments = assign_stable_ids(
        sources,
        group_keys,
        raw_hashes,
        existing_map,
    )
    for _, relative in sources:
        id_assignments[relative]["source_sample_label"] = labels[relative]
        id_assignments[relative]["grouping_rule"] = grouping_rules[relative]
        id_assignments[relative]["grouping_confidence"] = (
            "ambiguous" if relative in ambiguous else (
                "high" if "repeat" in grouping_rules[relative] else "medium"
            )
        )

    selected_rows: list[dict[str, str]] = []
    selected_results: dict[str, AscParseResult] = {}
    canonical_texts: dict[str, str] = {}
    conflicts: list[dict[str, str]] = []
    for path, relative in selected_sources:
        result = parse_asc(path, raw_hashes[relative])
        selected_results[relative] = result
        identity = id_assignments[relative]
        row, canonical_text = build_record(
            path,
            relative,
            identity,
            source_root,
            result,
            raw_hashes[relative],
            overrides,
        )
        selected_rows.append(row)
        if canonical_text is not None:
            canonical_texts[relative] = canonical_text

    PATTERN_ROOT.mkdir(parents=True, exist_ok=True)
    previously_managed_hashes = load_managed_canonical_hashes()
    for row in selected_rows:
        if not row["canonical_filename"]:
            continue
        relative = row["original_relative_path"]
        output = PATTERN_ROOT / row["canonical_filename"]
        content = canonical_texts[relative]
        if output.exists():
            actual_hash = sha256_file(output)
            if actual_hash != row["canonical_sha256"]:
                if actual_hash not in previously_managed_hashes.get(
                    row["canonical_filename"], set()
                ):
                    conflicts.append(
                        {
                            "type": "canonical_output_conflict",
                            "canonical_relative_path": row["canonical_relative_path"],
                            "existing_sha256": actual_hash,
                            "expected_sha256": row["canonical_sha256"],
                            "message": "Existing canonical output is not a verified prior build; not overwritten.",
                        }
                    )
                    continue
                output.write_text(content, encoding="utf-8", newline="\n")
        else:
            output.write_text(content, encoding="utf-8", newline="\n")

    raw_modified_paths = [
        relative
        for path, relative in sources
        if not path.exists() or sha256_file(path) != raw_hashes[relative]
    ]
    if raw_modified_paths:
        conflicts.append(
            {
                "type": "raw_source_changed_during_build",
                "paths": raw_modified_paths,
                "message": "Source ASC hash changed during the canonical build.",
            }
        )

    id_map_records = dict(existing_map.get("records", {}))
    for _, relative in sources:
        id_map_records[relative] = {
            "sample_id": id_assignments[relative]["sample_id"],
            "measurement_id": id_assignments[relative]["measurement_id"],
            "pattern_id": id_assignments[relative]["pattern_id"],
            "grouping_key": id_assignments[relative]["grouping_key"],
            "grouping_rule": id_assignments[relative]["grouping_rule"],
            "source_sample_label": id_assignments[relative]["source_sample_label"],
            "raw_sha256": raw_hashes[relative],
        }
    write_json(
        ID_MAP_PATH,
        {
            "schema_version": "lab_xrd_id_map_v1",
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_root": str(source_root),
            "records": dict(sorted(id_map_records.items())),
        },
    )

    manifest_name = (
        "lab_xrd_pilot_manifest_v1.csv" if pilot_mode else "lab_xrd_manifest_v1.csv"
    )
    write_csv(MANIFEST_ROOT / manifest_name, selected_rows)
    summary = summarize(
        selected_rows,
        selected_results,
        conflicts,
        pilot_mode,
        sources,
        group_keys,
        raw_modified_paths,
    )
    summary_path = MANIFEST_ROOT / (
        "lab_xrd_pilot_summary_v1.json" if pilot_mode else "lab_xrd_summary_v1.json"
    )
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if pilot_mode:
        print("\nPILOT CANONICAL PREVIEWS\n")
        for relative in [
            "JL/Co-S-Se-Te/Co3S4-1100-1-20measure-CoS.asc",
            "LX/2026/Sn-P-Se/113-20_001.asc",
            "WZQ/260624/Mo6Se8-1.asc",
        ]:
            row = next(item for item in selected_rows if item["original_relative_path"] == relative)
            content = canonical_texts.get(relative)
            print(f"--- {row['canonical_filename'] or '<not generated>'} | {relative} ---")
            if content:
                preview_lines = content.splitlines()
                data_start = next(
                    (index for index, line in enumerate(preview_lines) if not line.startswith("#")),
                    len(preview_lines),
                )
                print("\n".join(preview_lines[:data_start + 10]))
            else:
                print("No canonical output: " + row["parse_warnings"])
            print()
        print("PILOT INTENSITY QC\n")
        for relative, result in selected_results.items():
            first_ten = list(result.intensities[:10])
            canonical_first_ten: list[int] = []
            if relative in canonical_texts:
                body = [
                    line for line in canonical_texts[relative].splitlines()
                    if line and not line.startswith("#")
                ]
                canonical_first_ten = [int(line.split()[1]) for line in body[:10]]
            print(
                f"{relative}: status={result.parse_status}; "
                f"START/STOP/STEP/COUNT={result.metadata.start_2theta_deg}/"
                f"{result.metadata.stop_2theta_deg}/{result.metadata.step_2theta_deg}/"
                f"{result.metadata.point_count}; intensity_count={len(result.intensities)}; "
                f"x_count={len(result.two_theta)}; first_x="
                f"{result.two_theta[0] if result.two_theta else None}; last_x="
                f"{result.two_theta[-1] if result.two_theta else None}; "
                f"raw_first10={first_ten}; canonical_first10={canonical_first_ten}"
            )
    print(f"\nManifest: {MANIFEST_ROOT / manifest_name}")
    print(f"Summary: {summary_path}")
    print(f"ID map: {ID_MAP_PATH}")
    return 1 if conflicts else 0


def summarize(
    rows: list[dict[str, str]],
    results: dict[str, AscParseResult],
    conflicts: list[dict[str, str]],
    pilot_mode: bool,
    all_sources: list[tuple[Path, str]],
    group_keys: dict[str, str],
    raw_modified_paths: list[str],
) -> dict[str, Any]:
    sample_counts = Counter(row["sample_id"] for row in rows)
    parse_counts = Counter(row["parse_status"] for row in rows)
    raw_paths = {row["original_relative_path"] for row in rows}
    group_count_variants = Counter(
        result.metadata.group_count
        for relative, result in results.items()
        if relative in raw_paths
    )
    multi_group_rows = [
        row["original_relative_path"]
        for row in rows
        if results[row["original_relative_path"]].begin_count != 1
        or results[row["original_relative_path"]].end_count != 1
        or results[row["original_relative_path"]].group_marker_count != 1
        or results[row["original_relative_path"]].metadata.group_count not in (None, 1)
    ]
    count_mismatch = [
        relative
        for relative, result in results.items()
        if result.count_match is False
    ]
    inconsistent = [
        relative
        for relative, result in results.items()
        if result.axis_consistent is False or result.final_x_matches_stop is False
    ]
    repeated_measurement_samples = [
        {
            "sample_id": sample_id,
            "measurement_count": count,
            "source_relative_paths": sorted(
                row["original_relative_path"]
                for row in rows
                if row["sample_id"] == sample_id
            ),
        }
        for sample_id, count in sorted(sample_counts.items())
        if count > 1
    ]
    parse_failed_paths = sorted(
        row["original_relative_path"]
        for row in rows
        if row["parse_status"] == "failed"
    )
    parse_partial_paths = sorted(
        row["original_relative_path"]
        for row in rows
        if row["parse_status"] == "partial"
    )
    return {
        "schema_version": "lab_xrd_canonical_summary_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "pilot" if pilot_mode else "full",
        "raw_asc_files": len(all_sources) if pilot_mode else len(rows),
        "records_in_manifest": len(rows),
        "canonical_txt_generated": sum(bool(row["canonical_filename"]) for row in rows),
        "unique_samples_in_manifest": len({row["sample_id"] for row in rows}),
        "unique_measurements_in_manifest": len({row["measurement_id"] for row in rows}),
        "unique_patterns_in_manifest": len({row["pattern_id"] for row in rows}),
        "repeated_measurement_samples_in_manifest": sum(
            count > 1 for count in sample_counts.values()
        ),
        "repeated_measurement_samples": repeated_measurement_samples,
        "parse_status_counts": {
            "ok": parse_counts.get("ok", 0),
            "partial": parse_counts.get("partial", 0),
            "failed": parse_counts.get("failed", 0),
        },
        "parse_failed_paths": parse_failed_paths,
        "parse_partial_paths": parse_partial_paths,
        "count_matched": sum(
            result.count_match is True for result in results.values()
        ),
        "count_mismatch": len(count_mismatch),
        "count_mismatch_paths": count_mismatch,
        "scan_metadata_consistent": len(inconsistent) == 0,
        "inconsistent_scan_paths": inconsistent,
        "single_group_files": len(rows) - len(multi_group_rows),
        "multi_group_files": multi_group_rows,
        "known_nominal_composition_count": sum(
            bool(row["nominal_element_ratio"]) for row in rows
        ),
        "unknown_nominal_composition_count": sum(
            not row["nominal_element_ratio"] for row in rows
        ),
        "missing_contributor_count": sum(not row["contributor"] for row in rows),
        "missing_series_label_count": sum(not row["source_series_label"] for row in rows),
        "duplicate_sample_ids": [
            value for value, count in Counter(row["sample_id"] for row in rows).items()
            if count > 1 and len({group_keys[row["original_relative_path"]] for row in rows if row["sample_id"] == value}) > 1
        ],
        "duplicate_measurement_ids": [
            value for value, count in Counter(row["measurement_id"] for row in rows).items()
            if count > 1
        ],
        "duplicate_pattern_ids": [
            value for value, count in Counter(row["pattern_id"] for row in rows).items()
            if count > 1
        ],
        "duplicate_canonical_filenames": [
            value for value, count in Counter(row["canonical_filename"] for row in rows if row["canonical_filename"]).items()
            if count > 1
        ],
        "raw_files_modified": len(raw_modified_paths),
        "raw_files_modified_paths": raw_modified_paths,
        "group_count_variants": {
            str(key): value for key, value in sorted(group_count_variants.items(), key=lambda item: str(item[0]))
        },
        "conflicts": conflicts,
    }


if __name__ == "__main__":
    raise SystemExit(main())
