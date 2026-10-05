"""Structure response models."""

from __future__ import annotations

from pydantic import Field

from .common import Links, Provenance, PublicModel, SourceRef


class SpaceGroup(PublicModel):
    hm: str | None = None
    number: int | None = None


class Cell(PublicModel):
    a: float | None = None
    b: float | None = None
    c: float | None = None
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None


class Structure(PublicModel):
    structure_id: str
    source: SourceRef
    formula: str | None = None
    formula_normalized: str | None = None
    mineral_name: str | None = None
    space_group: SpaceGroup = Field(default_factory=SpaceGroup)
    cell: Cell = Field(default_factory=Cell)
    atom_site_count: int | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    links: Links = Field(default_factory=Links)

