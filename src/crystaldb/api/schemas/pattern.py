"""Pattern response models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import FractionValue, Links, Provenance, PublicModel, SourceRef, StructureLinkage


class PhaseStructure(PublicModel):
    structure_id: str | None = None
    structure_ids: list[str] = Field(default_factory=list)
    status: str | None = None
    coverage: Literal["complete", "partial", "none"] | None = None
    certainty: Literal["resolved", "ambiguous", "unknown"] | None = None


class PhaseComponent(PublicModel):
    name: str | None = None
    formula: str | None = None
    fraction: FractionValue = Field(default_factory=FractionValue)
    role: str | None = None
    structure: PhaseStructure = Field(default_factory=PhaseStructure)


class ScanInfo(PublicModel):
    axis: str | None = None
    two_theta_min_deg: float | None = None
    two_theta_max_deg: float | None = None
    point_count: int | None = None


class RadiationInfo(PublicModel):
    anode: str | None = None
    wavelength_angstrom: float | None = None
    wavelength_kalpha2_angstrom: float | None = None
    wavelengths_angstrom: list[float] = Field(default_factory=list)


DatasetRole = Literal[
    "raw",
    "canonical",
    "single_phase_precursor",
    "precursor_mixture_benchmark",
    "reaction_product_benchmark",
]


class Pattern(PublicModel):
    pattern_id: str
    measurement_id: str | None = None
    sample_id: str | None = None
    source: SourceRef
    data_origin: str = "experimental"
    modality: str
    dataset_role: DatasetRole | None = None
    phase_character: str = "unknown"
    material_label: str | None = None
    phase_components: list[PhaseComponent] = Field(default_factory=list)
    structure_linkage: StructureLinkage = Field(
        default_factory=lambda: StructureLinkage(status="unlinked")
    )
    scan: ScanInfo = Field(default_factory=ScanInfo)
    radiation: RadiationInfo = Field(default_factory=RadiationInfo)
    provenance: Provenance = Field(default_factory=Provenance)
    links: Links = Field(default_factory=Links)


class XYAxis(PublicModel):
    name: str
    unit: str
    values: list[float]


class PatternXY(PublicModel):
    pattern_id: str
    x: XYAxis
    y: XYAxis

