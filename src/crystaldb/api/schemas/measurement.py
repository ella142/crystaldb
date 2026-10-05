"""Measurement response models."""

from __future__ import annotations

from pydantic import Field

from .common import PublicModel, SourceRef


class MeasurementConditions(PublicModel):
    anode: str | None = None
    radiation: str | None = None
    wavelength_angstrom: float | None = None
    scan_range: list[float] | None = None
    step_size: float | None = None
    counting_time_seconds: float | None = None
    scan_program: str | None = None


class Measurement(PublicModel):
    measurement_id: str
    sample_id: str | None = None
    source: SourceRef
    modality: str
    conditions: MeasurementConditions = Field(default_factory=MeasurementConditions)
    source_file: str | None = None

