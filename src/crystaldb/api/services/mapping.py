"""Convert heterogeneous canonical documents into stable API models."""

from __future__ import annotations

import re
from typing import Any

from crystaldb.api.config import get_settings
from crystaldb.api.schemas import (
    Cell,
    FractionValue,
    Links,
    Measurement,
    MeasurementConditions,
    Pattern,
    PhaseComponent,
    PhaseStructure,
    Provenance,
    RadiationInfo,
    ReflectionSet,
    Sample,
    ScanInfo,
    SourceRef,
    SpaceGroup,
    Structure,
    StructureLinkage,
)


def _first(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "", [], {})), None)


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", ".", "?") else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "", ".", "?") else None
    except (TypeError, ValueError):
        return None


def _source_ref(document: dict[str, Any], *, source_key: str = "source") -> SourceRef:
    raw = document.get(source_key)
    if isinstance(raw, str):
        code = raw
        source_id = document.get("source_record_id") or document.get("source_id")
    else:
        raw = raw if isinstance(raw, dict) else {}
        code = _first(
            document.get("api_source_code"),
            raw.get("code"),
            raw.get("database"),
            raw.get("source"),
            document.get("source"),
            "UNKNOWN",
        )
        source_id = _first(
            document.get("api_source_id"),
            raw.get("source_id"),
            raw.get("source_record_id"),
            raw.get("source_sample_id"),
            raw.get("source_structure_id"),
            document.get("source_record_id"),
        )
    return SourceRef(code=str(code).upper(), source_id=str(source_id) if source_id else None)


def _api_url(path: str) -> str:
    return f"/api/v1{path}"


def _phase_components(document: dict[str, Any]) -> list[PhaseComponent]:
    raw = document.get("phase_components")
    if isinstance(raw, str):
        try:
            import json

            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = []
    if not isinstance(raw, list):
        raw = document.get("components", []) if isinstance(document.get("components"), list) else []
    result: list[PhaseComponent] = []
    for component in raw:
        if not isinstance(component, dict):
            continue
        fraction = component.get("fraction")
        if isinstance(fraction, dict):
            fraction_value = fraction.get("value")
            basis = fraction.get("basis")
        else:
            fraction_value = _first(fraction, component.get("weight_fraction"))
            basis = _first(
                component.get("basis"),
                component.get("fraction_unit"),
                "weight_fraction" if component.get("weight_fraction") is not None else None,
            )
        if basis == "wt_percent":
            basis = "weight_fraction"
            if fraction_value is not None:
                fraction_value = _float(fraction_value) / 100.0
        structure = component.get("structure")
        structure = structure if isinstance(structure, dict) else {}
        structure_ids = _first(
            structure.get("structure_ids"),
            structure.get("candidate_structure_ids"),
            component.get("structure_ids"),
        )
        if not isinstance(structure_ids, list):
            structure_ids = [structure_ids] if structure_ids else []
        structure_ids = [str(value) for value in structure_ids if value]
        status = structure.get("status")
        coverage = structure.get("coverage")
        certainty = structure.get("certainty")
        if len(structure_ids) > 1:
            status = status or "ambiguous"
            coverage = coverage or "partial"
            certainty = certainty or "ambiguous"
        structure_id = structure.get("structure_id")
        if (status == "ambiguous" or structure.get("certainty") == "ambiguous") and len(structure_ids) > 1:
            structure_id = None
        elif len(structure_ids) > 1:
            structure_id = None
        elif structure_id and structure_id not in structure_ids:
            structure_ids.insert(0, str(structure_id))
        formula = _first(
            component.get("formula"),
            component.get("chemical_formula"),
            component.get("chemical_composition"),
        )
        result.append(
            PhaseComponent(
                name=_first(component.get("name"), component.get("label")),
                formula=formula,
                fraction=FractionValue(value=_float(fraction_value), basis=basis),
                role=component.get("role"),
                structure=PhaseStructure(
                    structure_id=structure_id,
                    structure_ids=structure_ids,
                    status=status,
                    coverage=coverage,
                    certainty=certainty,
                ),
            )
        )
    return result


def _phase_character(document: dict[str, Any], components: list[PhaseComponent]) -> str:
    value = document.get("phase_character")
    if value in {"single_phase", "multi_phase", "unknown"}:
        return value
    if document.get("is_mixed_phase") is True or len(components) > 1:
        return "multi_phase"
    if document.get("phase_count") == 1 or document.get("mixture_type") == "single_phase":
        return "single_phase"
    return "unknown"


def _structure_linkage(
    document: dict[str, Any],
    components: list[PhaseComponent],
) -> StructureLinkage:
    raw = document.get("structure_linkage")
    raw = raw if isinstance(raw, dict) else {}
    status = raw.get("status")
    if status not in {"complete", "partial", "ambiguous", "unlinked"}:
        statuses = [component.structure.status for component in components if component.structure.status]
        if statuses and all(value == "complete" for value in statuses):
            status = "complete"
        elif any(value == "ambiguous" for value in statuses):
            status = "ambiguous"
        elif statuses:
            status = "partial"
        elif _first(document.get("structure_id"), document.get("cif_match"), document.get("matched_cif")):
            status = "complete"
        else:
            status = "unlinked"

    coverage = raw.get("coverage")
    if coverage not in {"complete", "partial", "none"}:
        if status == "complete":
            coverage = "complete"
        elif status in {"partial", "ambiguous"}:
            coverage = "partial"
        else:
            coverage = "none"

    certainty = raw.get("certainty")
    if certainty not in {"resolved", "ambiguous", "unknown"}:
        if status in {"complete", "partial"}:
            certainty = "resolved"
        elif status == "ambiguous":
            certainty = "ambiguous"
        else:
            certainty = "unknown"

    candidate_structure_ids = _first(
        raw.get("candidate_structure_ids"),
        raw.get("structure_ids"),
        document.get("linked_structure_ids"),
    )
    if not isinstance(candidate_structure_ids, list):
        candidate_structure_ids = [candidate_structure_ids] if candidate_structure_ids else []
    candidate_structure_ids = [str(value) for value in candidate_structure_ids if value]
    for component in components:
        for structure_id in component.structure.structure_ids:
            if structure_id not in candidate_structure_ids:
                candidate_structure_ids.append(structure_id)

    return StructureLinkage(
        status=status,
        coverage=coverage,
        certainty=certainty,
        candidate_structure_ids=candidate_structure_ids,
    )


def _provenance(document: dict[str, Any], source: SourceRef) -> Provenance:
    raw = document.get("provenance")
    raw = raw if isinstance(raw, dict) else {}
    source_metadata = document.get("source_metadata")
    source_metadata = source_metadata if isinstance(source_metadata, dict) else {}
    return Provenance(
        source=source.code,
        source_id=source.source_id,
        source_file=raw.get("source_file"),
        label_type=_first(
            raw.get("phase_label_type"),
            raw.get("label_type"),
            document.get("phase_label_type"),
        ),
        label_method=_first(
            raw.get("phase_label_method"),
            raw.get("label_method"),
            document.get("phase_label_method"),
        ),
        evidence=_first(
            raw.get("evidence"),
            document.get("diffraction_sample_description"),
            source_metadata.get("diffraction_sample_description"),
            document.get("review_reason"),
        ),
        bibliography=raw.get("bibliography")
        if isinstance(raw.get("bibliography"), dict)
        else None,
        notes=[
            str(value)
            for value in (_first(raw.get("notes"), document.get("parse_warnings")) or [])
            if value
        ],
    )


def _pattern_arrays(document: dict[str, Any]) -> tuple[list[float], list[float]]:
    data = document.get("data") or document.get("xrd") or {}
    return (
        list(data.get("two_theta") or []),
        list(data.get("intensity") or []),
    )


def pattern_model(document: dict[str, Any]) -> Pattern:
    components = _phase_components(document)
    source = _source_ref(document)
    x_values, _ = _pattern_arrays(document)
    scan = document.get("scan") if isinstance(document.get("scan"), dict) else {}
    data = document.get("xrd") if isinstance(document.get("xrd"), dict) else {}
    scan_min = _first(
        scan.get("start_2theta_deg"),
        data.get("two_theta_min"),
        x_values[0] if x_values else None,
    )
    scan_max = _first(
        scan.get("stop_2theta_deg"),
        data.get("two_theta_max"),
        x_values[-1] if x_values else None,
    )
    source_raw = document.get("source")
    source_raw = source_raw if isinstance(source_raw, dict) else {}
    radiation = document.get("radiation")
    radiation = radiation if isinstance(radiation, dict) else {}
    wavelength = _first(
        radiation.get("wavelength_angstrom"),
        radiation.get("wavelength_kalpha1_angstrom"),
        document.get("wavelength"),
    )
    pattern_id = document["pattern_id"]
    return Pattern(
        pattern_id=pattern_id,
        measurement_id=document.get("measurement_id"),
        sample_id=document.get("sample_id"),
        source=source,
        data_origin=_first(document.get("data_origin"), document.get("pattern_origin"), "experimental"),
        modality=_first(document.get("modality"), document.get("acquisition_mode"), "powder_xrd"),
        dataset_role=_first(document.get("dataset_role"), document.get("representation")),
        phase_character=_phase_character(document, components),
        phase_components=components,
        structure_linkage=_structure_linkage(document, components),
        scan=ScanInfo(
            axis=_first(
                scan.get("axis"),
                scan.get("scan_axis"),
                document.get("axes", {}).get("x")
                if isinstance(document.get("axes"), dict)
                else None,
            ),
            two_theta_min_deg=_float(scan_min),
            two_theta_max_deg=_float(scan_max),
            point_count=_int(_first(scan.get("point_count"), data.get("point_count"), len(x_values) or None)),
        ),
        radiation=RadiationInfo(
            anode=_first(radiation.get("anode"), radiation.get("characteristic")),
            wavelength_angstrom=_float(wavelength),
        ),
        provenance=_provenance(document, source),
        links=Links(
            self=_api_url(f"/patterns/{pattern_id}"),
            xy=_api_url(f"/patterns/{pattern_id}/xy")
            if document.get("has_xy") or x_values
            else None,
        ),
    )


def structure_model(document: dict[str, Any]) -> Structure:
    source = _source_ref(document)
    cell = document.get("cell") or document.get("cell_parameters") or {}
    space_group = document.get("space_group")
    if isinstance(space_group, str):
        space_group = {"hm": space_group}
    space_group = space_group if isinstance(space_group, dict) else {}
    canonical = document.get("canonical_cif") or {}
    return Structure(
        structure_id=document["structure_id"],
        source=source,
        formula=_first(document.get("formula"), canonical.get("formula")),
        formula_normalized=_first(document.get("formula_reduced"), document.get("formula_normalized")),
        mineral_name=_first(document.get("mineral_name"), document.get("source_structure_name"), canonical.get("mineral_name")),
        space_group=SpaceGroup(
            hm=space_group.get("hm"),
            number=_int(space_group.get("number")),
        ),
        cell=Cell(**{key: _float(cell.get(key)) for key in ("a", "b", "c", "alpha", "beta", "gamma")}),
        atom_site_count=_int(
            _first(
                document.get("atom_site_count"),
                document.get("atom_count"),
                len(document.get("atomic_sites", []))
                if isinstance(document.get("atomic_sites"), list)
                else None,
            )
        ),
        provenance=_provenance(document, source),
        links=Links(
            self=_api_url(f"/structures/{document['structure_id']}"),
            cif=_api_url(f"/structures/{document['structure_id']}/cif")
            if (document.get("file") or canonical.get("file_path") or canonical.get("status") == "ready")
            else None,
            patterns=_api_url(f"/patterns?structure_id={document['structure_id']}"),
        ),
    )


def measurement_model(document: dict[str, Any]) -> Measurement:
    source = _source_ref(document)
    radiation = document.get("radiation") if isinstance(document.get("radiation"), dict) else {}
    conditions = _first(document.get("conditions"), document.get("experimental_conditions"), {})
    conditions = conditions if isinstance(conditions, dict) else {}
    scan = document.get("scan") if isinstance(document.get("scan"), dict) else {}
    scan_range = _first(
        conditions.get("scan_range"),
        [scan.get("start_2theta_deg"), scan.get("stop_2theta_deg")]
        if scan.get("start_2theta_deg") is not None and scan.get("stop_2theta_deg") is not None
        else None,
    )
    return Measurement(
        measurement_id=document["measurement_id"],
        sample_id=document.get("sample_id"),
        source=source,
        modality=_first(document.get("modality"), document.get("measurement_type"), document.get("technique"), "unknown"),
        conditions=MeasurementConditions(
            anode=_first(conditions.get("anode"), radiation.get("anode")),
            radiation=_first(
                conditions.get("radiation"),
                radiation.get("characteristic"),
                conditions.get("radiation_type"),
            ),
            wavelength_angstrom=_float(
                _first(
                    conditions.get("wavelength_angstrom"),
                    radiation.get("wavelength_kalpha1_angstrom"),
                    radiation.get("wavelength"),
                    conditions.get("wavelength"),
                )
            ),
            scan_range=scan_range,
            step_size=_float(
                _first(conditions.get("step_size"), scan.get("step_2theta_deg"))
            ),
            counting_time_seconds=_float(
                _first(
                    conditions.get("counting_time_seconds"),
                    document.get("counting_time_seconds"),
                )
            ),
            scan_program=_first(
                conditions.get("scan_program"),
                document.get("scan_program"),
            ),
        ),
        source_file=(
            document.get("source_file")
            if isinstance(document.get("source_file"), str)
            else (document.get("file") or {}).get("key")
            if isinstance(document.get("file"), dict)
            else None
        ),
    )


def sample_model(document: dict[str, Any]) -> Sample:
    source = _source_ref(document)
    return Sample(
        sample_id=document["sample_id"],
        source=source,
        name=_first(document.get("name"), document.get("mineral_name"), document.get("source_sample_label")),
        formula=_first(document.get("formula"), document.get("nominal_element_ratio")),
        phase_character=document.get("phase_character") or "unknown",
    )


def reflection_model(document: dict[str, Any]) -> ReflectionSet:
    source = _source_ref(document)
    return ReflectionSet(
        reflection_set_id=document["reflection_set_id"],
        measurement_id=document.get("measurement_id"),
        structure_id=document.get("structure_id"),
        source=source,
        data_origin=document.get("data_origin") or "experimental",
        modality=document.get("modality") or "single_crystal_xrd",
        reflection_count=_int(document.get("reflection_count")),
        observed_quantity=document.get("observed_quantity"),
        available_fields=list(document.get("reflection_fields") or []),
        provenance=_provenance(document, source),
        links=Links(
            self=_api_url(f"/reflection-sets/{document['reflection_set_id']}"),
            hkl=_api_url(f"/reflection-sets/{document['reflection_set_id']}/hkl"),
        ),
    )

