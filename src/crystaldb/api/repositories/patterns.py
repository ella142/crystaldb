"""Pattern Mongo repository."""

from __future__ import annotations

from typing import Any

from .base import MongoRepository


class PatternRepository(MongoRepository):
    def list_filtered(
        self,
        *,
        source: str | None,
        modality: str | None,
        phase_character: str | None,
        component_formula: str | None,
        structure_linkage: str | None,
        structure_id: str | None,
        dataset_role: str | None,
        limit: int,
        after_id: str | None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if source:
            query["api_source_code"] = source.upper()
        if modality:
            query["modality"] = modality
        if phase_character:
            query["phase_character"] = phase_character
        if component_formula:
            query["phase_components.formula_normalized"] = component_formula
        if structure_linkage:
            query["structure_linkage.status"] = structure_linkage
        if structure_id:
            query["$or"] = [
                {"linked_structure_ids": structure_id},
                {"phase_components.structure.structure_id": structure_id},
                {"phase_components.structure.structure_ids": structure_id},
                {"structure_linkage.candidate_structure_ids": structure_id},
            ]
        if dataset_role:
            query["dataset_role"] = dataset_role
        return self.list(
            query,
            limit=limit,
            after_id=after_id,
            id_field="pattern_id",
            projection={"data": 0, "xrd": 0},
        )

