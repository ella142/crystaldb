"""Sample response models."""

from __future__ import annotations

from .common import PublicModel, SourceRef


class Sample(PublicModel):
    sample_id: str
    source: SourceRef
    name: str | None = None
    formula: str | None = None
    phase_character: str = "unknown"

