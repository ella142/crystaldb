"""Reflection-set response models."""

from __future__ import annotations

from pydantic import Field

from .common import Links, Provenance, PublicModel, SourceRef


class ReflectionSet(PublicModel):
    reflection_set_id: str
    measurement_id: str | None = None
    structure_id: str | None = None
    source: SourceRef
    data_origin: str = "experimental"
    modality: str = "single_crystal_xrd"
    reflection_count: int | None = None
    observed_quantity: str | None = None
    available_fields: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    links: Links = Field(default_factory=Links)

