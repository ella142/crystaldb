"""Pattern Mongo repository."""

from __future__ import annotations

import re
from typing import Any

from .base import MongoRepository


class PatternRepository(MongoRepository):
    def _build_query(
        self,
        *,
        source: str | None,
        modality: str | None,
        phase_character: str | None,
        component_formula: str | None,
        structure_linkage: str | None,
        structure_id: str | None,
        dataset_role: str | None,
        relation_pattern_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if source:
            query["api_source_code"] = source.upper()
        if modality:
            query["modality"] = modality
        if phase_character:
            query["phase_character"] = phase_character
        if component_formula:
            normalized_formula = re.sub(r"[\s_]+", "", component_formula)
            formula_query = {
                "$or": [
                    {"phase_components.formula_normalized": normalized_formula},
                    {"phase_components.formula": component_formula},
                    {"phase_components.formula": normalized_formula},
                ]
            }
            if structure_id:
                structure_conditions = [
                    {"linked_structure_ids": structure_id},
                    {"phase_components.structure.structure_id": structure_id},
                    {"phase_components.structure.structure_ids": structure_id},
                    {"structure_linkage.candidate_structure_ids": structure_id},
                ]
                if relation_pattern_ids:
                    structure_conditions.append(
                        {"pattern_id": {"$in": relation_pattern_ids}}
                    )
                query["$and"] = [
                    formula_query,
                    {"$or": structure_conditions},
                ]
            else:
                query.update(formula_query)
        if structure_linkage:
            query["structure_linkage.status"] = structure_linkage
        if structure_id and "$and" not in query:
            query["$or"] = [
                {"linked_structure_ids": structure_id},
                {"phase_components.structure.structure_id": structure_id},
                {"phase_components.structure.structure_ids": structure_id},
                {"structure_linkage.candidate_structure_ids": structure_id},
                *(
                    [{"pattern_id": {"$in": relation_pattern_ids}}]
                    if relation_pattern_ids
                    else []
                ),
            ]
        if dataset_role:
            query["dataset_role"] = dataset_role
        return query

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
        relation_pattern_ids: list[str] | None = None,
        limit: int,
        after_id: str | None,
    ) -> list[dict[str, Any]]:
        query = self._build_query(
            source=source,
            modality=modality,
            phase_character=phase_character,
            component_formula=component_formula,
            structure_linkage=structure_linkage,
            structure_id=structure_id,
            dataset_role=dataset_role,
            relation_pattern_ids=relation_pattern_ids,
        )
        return self.list(
            query,
            limit=limit,
            after_id=after_id,
            id_field="pattern_id",
            projection={"data": 0, "xrd": 0},
        )

    def count_filtered(
        self,
        *,
        source: str | None,
        modality: str | None,
        phase_character: str | None,
        component_formula: str | None,
        structure_linkage: str | None,
        structure_id: str | None,
        dataset_role: str | None,
        relation_pattern_ids: list[str] | None = None,
    ) -> int:
        return self.collection.count_documents(
            self._build_query(
                source=source,
                modality=modality,
                phase_character=phase_character,
                component_formula=component_formula,
                structure_linkage=structure_linkage,
                structure_id=structure_id,
                dataset_role=dataset_role,
                relation_pattern_ids=relation_pattern_ids,
            )
        )

