from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT / "data" / "multi-phase" / "rruff"
)
PILOT_OUTPUT_ROOT = (
    PROJECT_ROOT / "data" / "multi-phase" / "rruff_pilot"
)

MANIFEST_NAME = "rruff_multiphase_manifest_v1.csv"
REVIEW_NAME = "rruff_multiphase_review_v1.csv"
PILOT_MANIFEST_NAME = "rruff_multiphase_pilot_manifest_v1.csv"
PILOT_REVIEW_NAME = "rruff_multiphase_pilot_review_v1.csv"

CLASSIFICATION_METHOD = "deterministic_source_description_v1"
CLASSIFICATION_RULES = {
    "phase_character": [
        "Use only explicit source-language evidence in "
        "DIFFRACTION SAMPLE DESCRIPTION.",
        "Quantitative percentages, mixture/mixed/includes language, "
        "named secondary peaks, contamination, or explicit unknown/"
        "second-phase language classify as multi_phase.",
        "Do not infer multi_phase from mineral description, measured "
        "chemistry, locality, or crystal-structure metadata.",
    ],
    "profile_origin": [
        "calculated/simulated/computed wording classifies as calculated.",
        "A source description containing powder wording without "
        "calculated/simulated/computed wording classifies as experimental.",
        "Other descriptions are uncertain.",
    ],
    "measurement_identity": [
        "filename_sample_id is the measurement key.",
        "RAW is preferred over processed for the canonical export.",
        "A missing key or conflicting representations require review.",
    ],
}

CSV_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "measurement_id",
    "measurement_key",
    "mineral",
    "phase_character",
    "phase_components",
    "diffraction_sample_description",
    "profile_origin",
    "wavelength",
    "point_count",
    "source_collection",
    "source_document_id",
    "source_local_location",
    "source_zip_path",
    "original_representation",
    "canonical_filename",
    "canonical_relative_path",
    "canonical_sha256",
    "classification_method",
    "classification_rules",
    "review_required",
    "notes",
]

REVIEW_FIELDS = [
    "sample_id",
    "filename_sample_id",
    "measurement_id",
    "measurement_key",
    "mineral",
    "phase_character",
    "phase_components",
    "diffraction_sample_description",
    "profile_origin",
    "point_count",
    "xy_status",
    "review_reason",
    "source_collection",
    "source_document_id",
    "source_local_location",
    "original_representation",
    "classification_method",
    "classification_rules",
    "notes",
]

FLOAT_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
QUANTITATIVE_RE = re.compile(
    rf"(?P<approx>~|about|approximately|roughly)?\s*"
    rf"(?P<value>{FLOAT_RE})\s*"
    rf"(?P<unit>wt\s*%|%)\s*"
    rf"(?P<name>[A-Za-z][A-Za-z0-9()\-]*(?:\s+"
    rf"[A-Za-z][A-Za-z0-9()\-]*){{0,3}})",
    re.IGNORECASE,
)
SPELLED_QUANTITATIVE_RE = re.compile(
    r"\b(?:about|approximately|roughly)?\s*"
    r"(?P<word>ten|one|two|three|four|five)\s+percent"
    r".*?\bis\s+(?P<name>[A-Za-z][A-Za-z0-9()\-]*(?:\s+"
    r"[A-Za-z][A-Za-z0-9()\-]*){0,3})",
    re.IGNORECASE,
)

CALCULATED_RE = re.compile(
    r"\b(?:calculated|simulated|computed)\b",
    re.IGNORECASE,
)
POWDER_RE = re.compile(r"\bpowder\b", re.IGNORECASE)

UNKNOWN_PATTERNS = (
    re.compile(r"\bunknown\s+phases?\b", re.IGNORECASE),
    re.compile(r"\banother\s+phase\b", re.IGNORECASE),
    re.compile(r"\bsecond\s+(?:carbonate|garnet|unknown)?\s*phase\b", re.IGNORECASE),
    re.compile(r"\btwo\s+garnet\s+phases?\b", re.IGNORECASE),
    re.compile(r"\blight\s+and\s+dark\s+phases?\b", re.IGNORECASE),
)


def json_compact(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def source_description(doc: dict[str, Any]) -> str:
    return normalized_text(
        (doc.get("metadata") or {}).get(
            "DIFFRACTION SAMPLE DESCRIPTION"
        )
    )


def valid_xy_status(doc: dict[str, Any]) -> tuple[str, str, int]:
    xrd = doc.get("xrd") or {}
    two_theta = xrd.get("two_theta")
    intensity = xrd.get("intensity")

    if not isinstance(two_theta, (list, tuple)) or not two_theta:
        return "missing", "two_theta is missing or empty", 0
    if not isinstance(intensity, (list, tuple)) or not intensity:
        return "missing", "intensity is missing or empty", 0
    if len(two_theta) != len(intensity):
        return (
            "invalid",
            f"point-count mismatch: two_theta={len(two_theta)} "
            f"intensity={len(intensity)}",
            min(len(two_theta), len(intensity)),
        )

    try:
        for value in [*two_theta, *intensity]:
            if not math.isfinite(float(value)):
                raise ValueError("non-finite numeric value")
    except (TypeError, ValueError) as exc:
        return "invalid", f"non-numeric or non-finite XY value: {exc}", len(
            two_theta
        )

    return "valid", "", len(two_theta)


def classify_profile_origin(description: str) -> str:
    if not description:
        return "uncertain"
    if CALCULATED_RE.search(description):
        return "calculated"
    if POWDER_RE.search(description):
        return "experimental"
    return "uncertain"


def source_name(value: str) -> str:
    value = normalized_text(value)
    value = re.sub(
        rf"^~?\s*{FLOAT_RE}\s*(?:wt\s*%|%)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^contamination\s+from\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^(?:a|an|the|some|other|trace|minor)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^(?:minor\s+component\s+of|component\s+of|contamination\s+from)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.split(
        r"\s*(?:\(|\[|;|,)\s*|"
        r"\s+(?:from|by|a\s*[:=]|alpha\s*[:=]|beta\s*[:=]|"
        r"c\s*[:=]|V\s*[:=])\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    value = re.sub(
        r"\s+(?:contamination|peaks?|present|also)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+(?:are|is)\s+(?:also\s+)?present\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+(?:are|is)$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = normalized_text(value).strip(" .,:")
    if not value:
        return ""
    return value[0].upper() + value[1:]


def component_key(component: dict[str, Any]) -> str:
    if component.get("name"):
        return normalized_text(component["name"]).casefold()
    return f"label:{normalized_text(component.get('label'))}".casefold()


def add_component(
    components: list[dict[str, Any]],
    *,
    name: str | None = None,
    label: str | None = None,
    fraction: float | None = None,
    fraction_unit: str | None = None,
    fraction_description: str | None = None,
    role: str,
) -> None:
    if name:
        name = source_name(name)
    if label:
        label = normalized_text(label)
    if not name and not label:
        return

    component = {
        "name": name or None,
        "label": label,
        "fraction": fraction,
        "fraction_unit": fraction_unit,
        "fraction_description": fraction_description,
        "role": role,
    }
    key = component_key(component)
    for existing in components:
        if component_key(existing) != key:
            continue
        if existing.get("fraction") is None and fraction is not None:
            existing.update(
                {
                    "fraction": fraction,
                    "fraction_unit": fraction_unit,
                    "fraction_description": fraction_description,
                }
            )
        if existing.get("role") == "secondary" and role == "impurity":
            existing["role"] = role
        return
    components.append(component)


def numeric_word(value: str) -> float:
    return {
        "one": 1.0,
        "two": 2.0,
        "three": 3.0,
        "four": 4.0,
        "five": 5.0,
        "ten": 10.0,
    }[value.casefold()]


def clean_fragment(value: str) -> str:
    value = re.split(r"\s*[;(\[]", value, maxsplit=1)[0]
    value = re.split(
        r"\s+(?:cell\s+parameters|a\s*=|b\s*=|c\s*=|alpha\s*=|"
        r"beta\s*=|gamma\s*=|volume\s*=|V\s*=)",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .,:")


def split_phase_names(fragment: str) -> list[str]:
    fragment = clean_fragment(fragment)
    fragment = re.sub(
        r"^contamination\s+from\s+",
        "",
        fragment,
        flags=re.IGNORECASE,
    )
    fragment = re.sub(
        r"^(?:a|an|the|some|other|trace|minor)\s+",
        "",
        fragment,
        flags=re.IGNORECASE,
    )
    fragment = re.sub(
        r"^(?:minor\s+component\s+of|component\s+of)\s+",
        "",
        fragment,
        flags=re.IGNORECASE,
    )
    fragment = re.sub(
        r"\s+(?:contamination|contaminant)\b.*$",
        "",
        fragment,
        flags=re.IGNORECASE,
    )
    fragment = re.sub(
        r"^(?:contamination\s+from)\s+",
        "",
        fragment,
        flags=re.IGNORECASE,
    )
    fragment = re.sub(
        r"^(?:sharp\s+diffraction\s+peaks?\s+from|peaks?\s+from)\s+",
        "",
        fragment,
        flags=re.IGNORECASE,
    )

    parts = re.split(r"\s*,\s*|\s+\band\b\s+", fragment, flags=re.IGNORECASE)
    names: list[str] = []
    for part in parts:
        name = source_name(part)
        if not name:
            continue
        if name.casefold() in {
            "phase",
            "phases",
            "unknown phase",
            "unknown phases",
        }:
            continue
        names.append(name)
    return names


def parse_phase_components(
    description: str,
    mineral: str | None,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    lower = description.casefold()
    components: list[dict[str, Any]] = []
    evidence: list[str] = []

    quantitative: list[tuple[float, str, str | None]] = []
    for match in QUANTITATIVE_RE.finditer(description):
        name = source_name(clean_fragment(match.group("name")))
        if not name:
            continue
        quantitative.append(
            (
                float(match.group("value")),
                name,
                match.group("approx"),
            )
        )

    for match in SPELLED_QUANTITATIVE_RE.finditer(description):
        name = source_name(clean_fragment(match.group("name")))
        if name:
            quantitative.append(
                (numeric_word(match.group("word")), name, match.group("word"))
            )

    if quantitative:
        evidence.append("quantitative_fraction")

    quantitative_names = {name.casefold() for _, name, _ in quantitative}
    quantitative_has_weight = bool(
        re.search(r"(?:by\s+weight|wt\s*%)", lower)
    )
    for index, (fraction, name, approx) in enumerate(quantitative):
        description_bits = []
        if approx and approx.casefold() not in {
            "one",
            "two",
            "three",
            "four",
            "five",
            "ten",
        }:
            description_bits.append(str(approx))
        description_bits.append(f"{fraction:g}%")
        if "volume" in lower and "weight" not in lower:
            description_bits.append("of volume")
        add_component(
            components,
            name=name,
            fraction=fraction,
            fraction_unit=(
                "wt_percent"
                if quantitative_has_weight
                else "percent_unspecified"
            ),
            fraction_description=" ".join(description_bits),
            role="primary" if index == 0 else "secondary",
        )

    def add_named_fragment(
        fragment: str,
        *,
        role: str = "secondary",
        fraction_description: str | None = None,
    ) -> None:
        if any(pattern.search(fragment) for pattern in UNKNOWN_PATTERNS):
            return
        for name in split_phase_names(fragment):
            if name.casefold() in quantitative_names:
                continue
            add_component(
                components,
                name=name,
                fraction_description=fraction_description,
                role=role,
            )

    for match in re.finditer(
        r"\b(?:intimately\s+)?mixed\s+with\s+(.+?)(?=;|$)",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("mixture_language")
        add_named_fragment(match.group(1))

    for match in re.finditer(
        r"\b(?:appears\s+to\s+be\s+a\s+)?mix\s+of\s+(.+?)(?=;|,|$)",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("mixture_language")
        add_named_fragment(match.group(1))

    for match in re.finditer(
        r"\b(?:mixture\s+)?includes?\s+(.+?)(?=;|\.|$)",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("mixture_language")
        add_named_fragment(match.group(1))

    for match in re.finditer(
        r"\bwith\s+(.+?)(?=;|\.|$)",
        description,
        flags=re.IGNORECASE,
    ):
        fragment = match.group(1)
        if re.search(
            r"\b(?:another\s+phase|second\s+(?:carbonate|garnet|unknown)?"
            r"\s*phase|unknown\s+phases?|light\s+and\s+dark\s+phases?)\b",
            fragment,
            flags=re.IGNORECASE,
        ):
            evidence.append("unknown_phase")
            continue
        if re.match(
            r"(?:a\s+)?partially\s+metamic\b",
            normalized_text(fragment),
            flags=re.IGNORECASE,
        ):
            continue
        if re.search(
            r"\b(?:trace|minor|some|another|second|contamination|"
            r"quartz|phase|peaks?|minerals?|mixed)\b",
            fragment,
            flags=re.IGNORECASE,
        ):
            evidence.append("named_secondary_phase")
            role = (
                "impurity"
                if re.search(
                    r"\b(?:trace|minor|contamination)\b",
                    fragment,
                    flags=re.IGNORECASE,
                )
                else "secondary"
            )
            description_hint = None
            if role == "impurity":
                if re.search(r"\btrace\b", fragment, re.IGNORECASE):
                    description_hint = "trace"
                elif re.search(r"\bminor\b", fragment, re.IGNORECASE):
                    description_hint = "minor"
                else:
                    description_hint = "contamination"
            add_named_fragment(
                fragment,
                role=role,
                fraction_description=description_hint,
            )

    for match in re.finditer(
        r"\b(?:intimately\s+)?associated\s+with\s+(.+?)(?=;|\.|$)",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("named_secondary_phase")
        add_named_fragment(
            re.split(
                r",\s*(?:\d|a\s*=|b\s*=|c\s*=|alpha\s*=|beta\s*=|"
                r"gamma\s*=|V\s*=)",
                match.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
        )

    for match in re.finditer(
        r"\b(?:sharp\s+)?(?:diffraction\s+)?peaks?\s+"
        r"(?:of|from)\s+(.+?)(?=;|\.|$)",
        description,
        flags=re.IGNORECASE,
    ):
        fragment = match.group(1)
        fragment = re.split(
            r"\band\s+(?:small\s+)?peaks?\s+of\b",
            fragment,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        evidence.append("secondary_peak")
        add_named_fragment(fragment)

    for match in re.finditer(
        r"\bsharp\s+peak\s+is\s+(.+?)(?=;|\.|$)",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("secondary_peak")
        add_named_fragment(match.group(1))

    if re.search(
        r"\bpresence\s+of\s+.*?\bpeaks?\b",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("secondary_peak")

    named_second_phase = re.search(
        r"\bsecond\s+phase\s+is\s+"
        r"[A-Za-z][A-Za-z0-9()\-]*",
        description,
        flags=re.IGNORECASE,
    )
    if (
        re.search(
            r"\b(?:unknown|another)\s+phase|\bunknown\s+phases\b",
            description,
            flags=re.IGNORECASE,
        )
        or (
            re.search(r"\bsecond\s+phase\b", description, re.IGNORECASE)
            and named_second_phase is None
        )
    ):
        evidence.append("unknown_phase")
        label = "unknown phase"
        second_match = re.search(
            r"\bsecond\s+((?:carbonate|garnet)\s+phase)\b",
            description,
            flags=re.IGNORECASE,
        )
        if second_match:
            label = second_match.group(1).strip()
        add_component(
            components,
            label=label,
            role="unknown",
        )

    if re.search(
        r"\blight\s+and\s+dark\s+phases?\b",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("unknown_phase")
        add_component(components, label="light phase", role="unknown")
        add_component(components, label="dark phase", role="unknown")

    if re.search(
        r"\b(?:trace|minor|contamination)\b",
        description,
        flags=re.IGNORECASE,
    ):
        evidence.append("qualitative_impurity")

    second_garnet = re.search(
        r"\bsecond\s+phase\s+is\s+([A-Za-z][A-Za-z0-9()\-]*)",
        description,
        flags=re.IGNORECASE,
    )
    if second_garnet:
        evidence.append("named_secondary_phase")
        add_component(
            components,
            name=second_garnet.group(1),
            role="secondary",
        )

    if mineral:
        mineral_name = source_name(mineral)
        matching = next(
            (
                component
                for component in components
                if (component.get("name") or "").casefold()
                == mineral_name.casefold()
            ),
            None,
        )
        if matching is None:
            components.insert(
                0,
                {
                    "name": mineral_name,
                    "label": None,
                    "fraction": None,
                    "fraction_unit": None,
                    "fraction_description": None,
                    "role": "primary",
                },
            )
            for component in components[1:]:
                if component.get("role") == "primary":
                    component["role"] = "secondary"
        else:
            matching["role"] = "primary"
            for component in components:
                if component is not matching and component.get("role") == "primary":
                    component["role"] = "secondary"
            components.remove(matching)
            components.insert(0, matching)

    evidence = sorted(set(evidence))
    explicit = len(components) > 1 and bool(evidence)
    parse_suspicious = bool(evidence) and len(components) < 2
    return components, evidence, parse_suspicious if explicit else False


def classify_phase(
    description: str,
    mineral: str | None,
) -> tuple[str, list[dict[str, Any]], list[str], bool]:
    components, evidence, parse_suspicious = parse_phase_components(
        description,
        mineral,
    )
    if len(components) > 1 and evidence:
        return "multi_phase", components, evidence, parse_suspicious
    return "unknown", components, evidence, False


def measurement_key(doc: dict[str, Any]) -> str | None:
    value = normalized_text(doc.get("filename_sample_id"))
    return value or None


def source_id(doc: dict[str, Any]) -> str:
    return str(doc.get("_id", ""))


def collect_measurements(db) -> tuple[list[dict[str, Any]], int]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"raw": [], "processed": []}
    )
    records_scanned = 0

    for collection_name, group_name in (
        ("xy_raw", "raw"),
        ("xy_processed", "processed"),
    ):
        for doc in db[collection_name].find({}):
            records_scanned += 1
            key = measurement_key(doc)
            if key is None:
                key = f"__missing__:{collection_name}:{source_id(doc)}"
            grouped[key][group_name].append(
                {
                    "collection_name": collection_name,
                    "group_name": group_name,
                    "doc": doc,
                }
            )

    measurements: list[dict[str, Any]] = []
    for key, variants in grouped.items():
        all_variants = variants["raw"] + variants["processed"]
        chosen_pool = variants["raw"] or variants["processed"]
        chosen = sorted(
            chosen_pool,
            key=lambda item: source_id(item["doc"]),
        )[0]
        chosen_doc = chosen["doc"]

        sample_ids = {
            normalized_text(item["doc"].get("sample_id"))
            for item in all_variants
            if normalized_text(item["doc"].get("sample_id"))
        }
        descriptions = {
            source_description(item["doc"])
            for item in all_variants
            if source_description(item["doc"])
        }
        minerals = {
            normalized_text(item["doc"].get("mineral"))
            for item in all_variants
            if normalized_text(item["doc"].get("mineral"))
        }

        identity_reasons: list[str] = []
        if key.startswith("__missing__"):
            identity_reasons.append("filename_sample_id is missing")
        if len(variants["raw"]) > 1:
            identity_reasons.append("multiple RAW records share measurement key")
        if len(variants["processed"]) > 1:
            identity_reasons.append(
                "multiple processed records share measurement key"
            )
        if len(sample_ids) > 1:
            identity_reasons.append(
                "RAW/processed representations disagree on sample_id"
            )
        if len(descriptions) > 1:
            identity_reasons.append(
                "RAW/processed representations disagree on source description"
            )
        if len(minerals) > 1:
            identity_reasons.append(
                "RAW/processed representations disagree on mineral"
            )

        measurements.append(
            {
                "measurement_key": key,
                "chosen": chosen_doc,
                "variants": all_variants,
                "identity_reasons": identity_reasons,
            }
        )

    return measurements, records_scanned


def wavelength_from_doc(doc: dict[str, Any]) -> Any:
    metadata = doc.get("metadata") or {}
    for key in (
        "WAVELENGTH",
        "X-RAY WAVELENGTH",
        "WAVELENGTH ANGSTROM",
    ):
        value = metadata.get(key)
        if value not in (None, ""):
            return value
    return None


def build_record(item: dict[str, Any]) -> dict[str, Any]:
    doc = item["chosen"]
    metadata = doc.get("metadata") or {}
    description = source_description(doc)
    mineral = normalized_text(doc.get("mineral"))
    phase_character, components, evidence, parse_suspicious = classify_phase(
        description,
        mineral,
    )
    profile_origin = classify_profile_origin(description)
    xy_status, xy_reason, point_count = valid_xy_status(doc)

    reasons = list(item["identity_reasons"])
    if phase_character != "multi_phase":
        reasons = []
    if phase_character == "multi_phase" and profile_origin == "uncertain":
        reasons.append("profile origin is uncertain")
    if phase_character == "multi_phase" and xy_status == "missing":
        reasons.append(xy_reason)
    if phase_character == "multi_phase" and xy_status == "invalid":
        reasons.append(xy_reason)
    if phase_character == "multi_phase" and parse_suspicious:
        reasons.append("phase component parsing is suspicious")

    measurement_id = normalized_text(doc.get("filename_sample_id"))
    sample_id = normalized_text(doc.get("sample_id"))
    if not measurement_id:
        measurement_id = item["measurement_key"]

    safe_measurement_id = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        measurement_id,
    )
    canonical_filename = f"RRUFF_{safe_measurement_id}.txt"
    canonical_relative_path = (
        f"multi-phase/rruff/patterns/{canonical_filename}"
    )

    original_representation = (
        "raw" if item["chosen"].get("dataset") == "XY_RAW" else "processed"
    )
    import_meta = doc.get("import_meta") or {}
    notes: list[str] = []
    if original_representation == "raw":
        if any(
            variant["doc"].get("dataset") == "XY_Processed"
            for variant in item["variants"]
        ):
            notes.append("processed representation exists; RAW selected")
    else:
        notes.append("RAW representation unavailable; processed selected")
    if evidence:
        notes.append("evidence=" + ",".join(evidence))
    if reasons:
        notes.append("review=" + " | ".join(sorted(set(reasons))))

    return {
        "sample_id": sample_id,
        "filename_sample_id": normalized_text(doc.get("filename_sample_id")),
        "measurement_id": measurement_id,
        "measurement_key": item["measurement_key"],
        "mineral": mineral,
        "phase_character": phase_character,
        "phase_components": components,
        "phase_evidence": evidence,
        "diffraction_sample_description": description,
        "profile_origin": profile_origin,
        "wavelength": wavelength_from_doc(doc),
        "point_count": point_count,
        "xy_status": xy_status,
        "xy_reason": xy_reason,
        "source_collection": f"rruff.{item['chosen'].get('dataset', '').lower()}",
        "source_document_id": source_id(doc),
        "source_local_location": import_meta.get("inner_file", ""),
        "source_zip_path": import_meta.get("zip_path", ""),
        "original_representation": original_representation,
        "canonical_filename": canonical_filename,
        "canonical_relative_path": canonical_relative_path,
        "canonical_sha256": "",
        "classification_method": CLASSIFICATION_METHOD,
        "classification_rules": json_compact(CLASSIFICATION_RULES),
        "review_required": bool(reasons),
        "review_reason": " | ".join(sorted(set(reasons))),
        "notes": "; ".join(notes),
        "_source_doc": doc,
    }


def accepted(record: dict[str, Any]) -> bool:
    return (
        record["phase_character"] == "multi_phase"
        and record["profile_origin"] == "experimental"
        and record["xy_status"] == "valid"
        and not record["review_required"]
    )


def format_number(value: Any) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite number: {value!r}")
    return format(number, ".15g")


def component_header(component: dict[str, Any]) -> str:
    label = component.get("name") or component.get("label") or "unknown phase"
    fraction = component.get("fraction")
    if fraction is None:
        return label
    unit = component.get("fraction_unit") or "percent_unspecified"
    return f"{label} ({format_number(fraction)} {unit})"


def render_canonical_txt(record: dict[str, Any]) -> bytes:
    doc = record["_source_doc"]
    xrd = doc.get("xrd") or {}
    two_theta = xrd.get("two_theta") or []
    intensity = xrd.get("intensity") or []
    wavelength = (
        "unknown"
        if record["wavelength"] in (None, "")
        else normalized_text(record["wavelength"])
    )
    components = " | ".join(
        component_header(component)
        for component in record["phase_components"]
    )
    lines = [
        "# CrystalDB experimental multiphase powder XRD",
        "# format_version: 1.0",
        "#",
        "# source: RRUFF",
        f"# sample_id: {record['sample_id']}",
        f"# filename_sample_id: {record['filename_sample_id']}",
        f"# measurement_id: {record['measurement_id']}",
        f"# mineral: {record['mineral']}",
        f"# phase_character: {record['phase_character']}",
        f"# phase_components: {components}",
        "#",
        "# diffraction_sample_description: "
        + record["diffraction_sample_description"],
        f"# profile_origin: {record['profile_origin']}",
        f"# wavelength_angstrom: {wavelength}",
        f"# point_count: {record['point_count']}",
        "# columns: two_theta_deg intensity",
    ]
    for x_value, y_value in zip(two_theta, intensity):
        lines.append(
            f"{format_number(x_value)}    {format_number(y_value)}"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def manifest_row(record: dict[str, Any]) -> dict[str, str]:
    return {
        "sample_id": record["sample_id"],
        "filename_sample_id": record["filename_sample_id"],
        "measurement_id": record["measurement_id"],
        "measurement_key": record["measurement_key"],
        "mineral": record["mineral"],
        "phase_character": record["phase_character"],
        "phase_components": json_compact(record["phase_components"]),
        "diffraction_sample_description": record[
            "diffraction_sample_description"
        ],
        "profile_origin": record["profile_origin"],
        "wavelength": "" if record["wavelength"] is None else str(
            record["wavelength"]
        ),
        "point_count": str(record["point_count"]),
        "source_collection": record["source_collection"],
        "source_document_id": record["source_document_id"],
        "source_local_location": record["source_local_location"],
        "source_zip_path": record["source_zip_path"],
        "original_representation": record["original_representation"],
        "canonical_filename": record["canonical_filename"],
        "canonical_relative_path": record["canonical_relative_path"],
        "canonical_sha256": record["canonical_sha256"],
        "classification_method": record["classification_method"],
        "classification_rules": record["classification_rules"],
        "review_required": str(record["review_required"]).lower(),
        "notes": record["notes"],
    }


def review_row(record: dict[str, Any]) -> dict[str, str]:
    return {
        "sample_id": record["sample_id"],
        "filename_sample_id": record["filename_sample_id"],
        "measurement_id": record["measurement_id"],
        "measurement_key": record["measurement_key"],
        "mineral": record["mineral"],
        "phase_character": record["phase_character"],
        "phase_components": json_compact(record["phase_components"]),
        "diffraction_sample_description": record[
            "diffraction_sample_description"
        ],
        "profile_origin": record["profile_origin"],
        "point_count": str(record["point_count"]),
        "xy_status": record["xy_status"],
        "review_reason": record["review_reason"],
        "source_collection": record["source_collection"],
        "source_document_id": record["source_document_id"],
        "source_local_location": record["source_local_location"],
        "original_representation": record["original_representation"],
        "classification_method": record["classification_method"],
        "classification_rules": record["classification_rules"],
        "notes": record["notes"],
    }


def csv_bytes(rows: list[dict[str, str]], fields: list[str]) -> bytes:
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fields,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def write_if_unchanged(
    path: Path,
    content: bytes,
    conflicts: list[str],
    skipped: list[str],
) -> None:
    if path.exists():
        existing = path.read_bytes()
        if sha256_bytes(existing) == sha256_bytes(content):
            skipped.append(str(path))
        else:
            conflicts.append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def values_equal(left: Any, right: Any) -> bool:
    return float(left) == float(right)


def qc_export(
    records: list[dict[str, Any]],
    patterns_dir: Path,
) -> list[str]:
    errors: list[str] = []
    for record in records:
        path = patterns_dir / record["canonical_filename"]
        if not path.exists():
            errors.append(f"missing canonical TXT: {path}")
            continue
        rows: list[tuple[float, float]] = []
        for line_number, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2:
                errors.append(
                    f"{path.name}:{line_number}: expected two columns"
                )
                continue
            try:
                rows.append((float(parts[0]), float(parts[1])))
            except ValueError:
                errors.append(
                    f"{path.name}:{line_number}: non-numeric data row"
                )

        doc = record["_source_doc"]
        xrd = doc.get("xrd") or {}
        source_x = xrd.get("two_theta") or []
        source_y = xrd.get("intensity") or []
        if len(rows) != record["point_count"]:
            errors.append(
                f"{path.name}: row count {len(rows)} != "
                f"point_count {record['point_count']}"
            )
        if len(source_x) != len(source_y):
            errors.append(f"{path.name}: source XY length mismatch")
            continue
        if rows and source_x and source_y:
            for index in [0, 1, 2, 3, 4, -5, -4, -3, -2, -1]:
                if abs(index) > len(rows):
                    continue
                row = rows[index]
                source_index = index if index >= 0 else len(source_x) + index
                if not (
                    values_equal(row[0], source_x[source_index])
                    and values_equal(row[1], source_y[source_index])
                ):
                    errors.append(
                        f"{path.name}: source/export mismatch at index "
                        f"{source_index}"
                    )
                    break
    return errors


def pilot_categories(record: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    components = record["phase_components"]
    quantitative = [
        component
        for component in components
        if component.get("fraction") is not None
    ]
    if len(quantitative) == 2:
        categories.append("2-phase quantitative")
    if len(quantitative) == 3:
        categories.append("3-phase quantitative")
    if len(quantitative) >= 4:
        categories.append("4+-phase quantitative")
    if any(
        component.get("fraction_description") in {"trace", "minor", "contamination"}
        or component.get("role") == "impurity"
        for component in components
    ):
        categories.append("trace/minor impurity")
    if "secondary_peak" in record["phase_evidence"]:
        categories.append("secondary-phase peaks")
    if any(
        component.get("role") == "unknown"
        or not component.get("name")
        for component in components
    ):
        categories.append("unknown secondary phase")
    if re.search(
        r"\bmixed\s+with\s+quartz\b|\bwith\s+quartz\b",
        record["diffraction_sample_description"],
        flags=re.IGNORECASE,
    ):
        categories.append("mixed with quartz")
    return categories


def choose_pilot(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ordered = sorted(
        records,
        key=lambda record: (
            record["sample_id"],
            record["measurement_id"],
        ),
    )
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    wanted = [
        "2-phase quantitative",
        "3-phase quantitative",
        "trace/minor impurity",
        "secondary-phase peaks",
        "unknown secondary phase",
        "mixed with quartz",
    ]
    for category in wanted:
        candidate = next(
            (
                record
                for record in ordered
                if record["measurement_key"] not in selected_keys
                and category in pilot_categories(record)
            ),
            None,
        )
        if candidate is not None:
            selected.append(candidate)
            selected_keys.add(candidate["measurement_key"])
    for record in ordered:
        if len(selected) >= limit:
            break
        if record["measurement_key"] in selected_keys:
            continue
        selected.append(record)
        selected_keys.add(record["measurement_key"])
    return selected[:limit]


def print_summary(
    records: list[dict[str, Any]],
    records_scanned: int,
    unique_measurements: int,
) -> None:
    explicit = [
        record
        for record in records
        if record["phase_character"] == "multi_phase"
    ]
    exportable = [record for record in records if accepted(record)]
    origin_counts = Counter(record["profile_origin"] for record in explicit)
    export_counts = Counter()
    for record in exportable:
        count = len(record["phase_components"])
        if count == 2:
            export_counts["2-phase"] += 1
        elif count == 3:
            export_counts["3-phase"] += 1
        elif count >= 4:
            export_counts["4+-phase"] += 1
        if any(
            component.get("fraction") is not None
            for component in record["phase_components"]
        ):
            export_counts["with quantitative phase fractions"] += 1
        if any(
            component.get("role") == "impurity"
            for component in record["phase_components"]
        ):
            export_counts["with qualitative impurity"] += 1
        if any(
            component.get("role") == "unknown"
            or not component.get("name")
            for component in record["phase_components"]
        ):
            export_counts["with unknown secondary phase"] += 1

    print("===== SOURCE =====")
    print(f"RRUFF representation records scanned: {records_scanned}")
    print(f"unique measurements: {unique_measurements}")
    print()
    print("===== MULTIPHASE =====")
    print(f"explicit multi-phase: {len(explicit)}")
    print(f"experimental multi-phase: {origin_counts['experimental']}")
    print(f"calculated multi-phase: {origin_counts['calculated']}")
    print(f"uncertain-origin multi-phase: {origin_counts['uncertain']}")
    print()
    print("===== EXPORT =====")
    print(f"experimental multi-phase with valid XY: {len(exportable)}")
    print("TXT exported:", len(exportable))
    for key in (
        "2-phase",
        "3-phase",
        "4+-phase",
        "with quantitative phase fractions",
        "with qualitative impurity",
        "with unknown secondary phase",
    ):
        print(f"{key}: {export_counts[key]}")
    print()
    print("===== EXCLUDED =====")
    print(
        "calculated profiles:",
        sum(
            1
            for record in explicit
            if record["profile_origin"] == "calculated"
        ),
    )
    print(
        "uncertain-origin profiles:",
        sum(
            1
            for record in explicit
            if record["profile_origin"] == "uncertain"
        ),
    )
    print(
        "missing XY:",
        sum(
            1
            for record in explicit
            if record["xy_status"] == "missing"
        ),
    )
    print(
        "invalid XY:",
        sum(
            1
            for record in explicit
            if record["xy_status"] == "invalid"
        ),
    )
    print(
        "review required:",
        sum(1 for record in explicit if record["review_required"]),
    )
    print()
    print("===== ACCEPTED CANDIDATES =====")
    print("sample_id\tmineral\tdescription\tcomponents\tprofile_origin\tpoint_count")
    for record in sorted(
        exportable,
        key=lambda item: (item["sample_id"], item["measurement_id"]),
    )[:20]:
        components = " | ".join(
            component.get("name")
            or component.get("label")
            or "unknown phase"
            for component in record["phase_components"]
        )
        description = record["diffraction_sample_description"]
        if len(description) > 110:
            description = description[:107] + "..."
        print(
            f"{record['sample_id']}\t{record['mineral']}\t"
            f"{description}\t{components}\t"
            f"{record['profile_origin']}\t{record['point_count']}"
        )


def export_records(
    records: list[dict[str, Any]],
    output_root: Path,
    *,
    pilot: bool,
) -> int:
    records = sorted(
        records,
        key=lambda record: (
            record["sample_id"],
            record["measurement_id"],
        ),
    )
    patterns = output_root / "patterns"
    manifests = output_root / "manifests"
    review = output_root / "review"
    patterns.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)

    conflicts: list[str] = []
    skipped: list[str] = []
    for record in records:
        content = render_canonical_txt(record)
        record["canonical_sha256"] = sha256_bytes(content)
        write_if_unchanged(
            patterns / record["canonical_filename"],
            content,
            conflicts,
            skipped,
        )

    manifest_name = PILOT_MANIFEST_NAME if pilot else MANIFEST_NAME
    review_name = PILOT_REVIEW_NAME if pilot else REVIEW_NAME
    manifest_content = csv_bytes(
        [manifest_row(record) for record in records],
        CSV_FIELDS,
    )
    review_records = [
        record
        for record in records
        if record["review_required"]
    ]
    review_content = csv_bytes(
        [review_row(record) for record in review_records],
        REVIEW_FIELDS,
    )
    write_if_unchanged(
        manifests / manifest_name,
        manifest_content,
        conflicts,
        skipped,
    )
    write_if_unchanged(
        review / review_name,
        review_content,
        conflicts,
        skipped,
    )

    qc_errors = qc_export(records, patterns)
    print()
    print("===== EXPORT RUN =====")
    print(f"output root: {output_root}")
    print(f"patterns attempted: {len(records)}")
    print(f"same-content files skipped: {len(skipped)}")
    print(f"conflicts: {len(conflicts)}")
    for conflict in conflicts[:20]:
        print("CONFLICT:", conflict)
    print(f"QC errors: {len(qc_errors)}")
    for error in qc_errors[:20]:
        print("QC ERROR:", error)
    if not conflicts and not qc_errors:
        print("QC status: PASS")
    if conflicts or qc_errors:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run, pilot-export, or full-export of explicit "
            "experimental RRUFF multi-phase powder XRD."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="scan and report only; default mode",
    )
    mode.add_argument(
        "--pilot",
        action="store_true",
        help="export a deterministic ten-record pilot",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="export all accepted records",
    )
    parser.add_argument(
        "--uri",
        default="mongodb://127.0.0.1:27017",
    )
    parser.add_argument(
        "--database",
        default="rruff",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="override the pilot or full output root",
    )
    parser.add_argument(
        "--pilot-count",
        type=int,
        default=10,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.pilot_count <= 0:
        raise SystemExit("--pilot-count must be positive")

    client = None
    try:
        from pymongo import MongoClient

        client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[args.database]
        measurements, records_scanned = collect_measurements(db)
        records = [
            build_record(measurement)
            for measurement in measurements
        ]
    finally:
        if client is not None:
            client.close()

    print_summary(
        records,
        records_scanned,
        len(measurements),
    )

    if not args.pilot and not args.full:
        print()
        print("DRY-RUN: no export files were written.")
        return 0

    exportable = [
        record
        for record in records
        if accepted(record)
    ]
    pilot = bool(args.pilot)
    if pilot:
        exportable = choose_pilot(exportable, args.pilot_count)
        if len(exportable) < args.pilot_count:
            print(
                f"pilot candidates available: {len(exportable)} "
                f"(requested {args.pilot_count})"
            )
        print()
        print("===== PILOT COVERAGE =====")
        covered = Counter(
            category
            for record in exportable
            for category in pilot_categories(record)
        )
        for category in (
            "2-phase quantitative",
            "3-phase quantitative",
            "trace/minor impurity",
            "secondary-phase peaks",
            "unknown secondary phase",
            "mixed with quartz",
        ):
            print(f"{category}: {covered[category]}")

    output_root = Path(
        args.output_root
        or (PILOT_OUTPUT_ROOT if pilot else DEFAULT_OUTPUT_ROOT)
    )
    return export_records(
        exportable,
        output_root,
        pilot=pilot,
    )


if __name__ == "__main__":
    sys.exit(main())
