"""Shared public response models."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SourceRef(PublicModel):
    code: str
    source_id: str | None = None


class Links(PublicModel):
    self: str | None = None
    xy: str | None = None
    cif: str | None = None
    hkl: str | None = None
    patterns: str | None = None
    download: str | None = None


class PageMeta(PublicModel):
    count: int
    next_cursor: str | None = None


ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    meta: PageMeta


class APIError(BaseModel):
    detail: str
    code: str | None = None


class FractionValue(PublicModel):
    value: float | None = None
    basis: str | None = None


class Bibliography(PublicModel):
    authors: list[str] = Field(default_factory=list)
    title: str | None = None
    journal: str | None = None
    year: str | None = None
    volume: str | None = None
    page_first: str | None = None
    page_last: str | None = None


class StructureLinkage(PublicModel):
    status: Literal["complete", "partial", "ambiguous", "unlinked"]
    coverage: Literal["complete", "partial", "none"] = "none"
    certainty: Literal["resolved", "ambiguous", "unknown"] = "unknown"
    candidate_structure_ids: list[str] = Field(default_factory=list)


class Provenance(PublicModel):
    source: str | None = None
    source_id: str | None = None
    source_file: str | None = None
    label_type: str | None = None
    label_method: str | None = None
    evidence: str | None = None
    bibliography: Bibliography | None = None
    notes: list[str] = Field(default_factory=list)

