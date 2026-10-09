"""Pattern endpoints."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pymongo.database import Database

from crystaldb.api.db import get_database
from crystaldb.api.repositories.patterns import PatternRepository
from crystaldb.api.schemas import PaginatedResponse, Pattern, PatternXY
from crystaldb.api.schemas.pattern import DatasetRole
from crystaldb.api.services.mapping import _pattern_arrays, pattern_model
from crystaldb.api.services.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/patterns", tags=["patterns"])


def _pattern_relations(
    database: Database,
    pattern_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not pattern_ids:
        return {}
    documents = database.relations.find(
        {
            "subject_type": "pattern",
            "subject_id": {"$in": pattern_ids},
            "object_type": "structure",
            "predicate": {"$in": ["has_structure_linkage", "has_structure_candidate"]},
            "status": {"$in": ["complete", "ambiguous", "inconclusive"]},
        },
        {
            "_id": 0,
            "subject_id": 1,
            "object_id": 1,
            "object_type": 1,
            "predicate": 1,
            "status": 1,
        },
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for document in documents:
        subject_id = document.get("subject_id")
        if subject_id:
            result.setdefault(str(subject_id), []).append(dict(document))
    return result


def _structure_relation_pattern_ids(
    database: Database,
    structure_id: str | None,
) -> list[str] | None:
    if not structure_id:
        return None
    return [
        str(value)
        for value in database.relations.distinct(
            "subject_id",
            {
                "subject_type": "pattern",
                "object_type": "structure",
                "object_id": structure_id,
                "predicate": {
                    "$in": ["has_structure_linkage", "has_structure_candidate"]
                },
                "status": {"$in": ["complete", "ambiguous", "inconclusive"]},
            },
        )
        if value
    ]


@router.get("", response_model=PaginatedResponse[Pattern])
def list_patterns(
    source: str | None = Query(default=None),
    modality: Literal["powder_xrd", "single_crystal_xrd"] | None = Query(default=None),
    phase_character: Literal["single_phase", "multi_phase", "unknown"] | None = Query(default=None),
    component_formula: str | None = Query(default=None),
    structure_linkage: Literal["complete", "partial", "ambiguous", "unlinked"] | None = Query(default=None),
    structure_id: str | None = Query(default=None),
    dataset_role: DatasetRole | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
    database: Database = Depends(get_database),
) -> PaginatedResponse[Pattern]:
    try:
        after_id = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repository = PatternRepository(database.patterns)
    relation_pattern_ids = _structure_relation_pattern_ids(database, structure_id)
    total_count = repository.count_filtered(
        source=source,
        modality=modality,
        phase_character=phase_character,
        component_formula=component_formula,
        structure_linkage=structure_linkage,
        structure_id=structure_id,
        dataset_role=dataset_role,
        relation_pattern_ids=relation_pattern_ids,
    )
    documents = repository.list_filtered(
        source=source,
        modality=modality,
        phase_character=phase_character,
        component_formula=component_formula,
        structure_linkage=structure_linkage,
        structure_id=structure_id,
        dataset_role=dataset_role,
        relation_pattern_ids=relation_pattern_ids,
        limit=limit + 1,
        after_id=after_id,
    )
    has_next = len(documents) > limit
    documents = documents[:limit]
    next_cursor = encode_cursor(documents[-1]["pattern_id"]) if has_next and documents else None
    relations = _pattern_relations(
        database,
        [document["pattern_id"] for document in documents],
    )
    return PaginatedResponse(
        items=[
            pattern_model(document, relations.get(document["pattern_id"], []))
            for document in documents
        ],
        meta={
            "count": len(documents),
            "total_count": total_count,
            "next_cursor": next_cursor,
        },
    )


@router.get("/{pattern_id}", response_model=Pattern)
def get_pattern(pattern_id: str, database: Database = Depends(get_database)) -> Pattern:
    document = database.patterns.find_one({"pattern_id": pattern_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="pattern not found")
    relations = _pattern_relations(database, [pattern_id])
    return pattern_model(document, relations.get(pattern_id, []))


@router.get("/{pattern_id}/xy", response_model=PatternXY)
def get_pattern_xy(
    pattern_id: str,
    format: Literal["json", "csv", "txt"] = Query(default="json"),
    database: Database = Depends(get_database),
) -> PatternXY | Response:
    document = database.patterns.find_one({"pattern_id": pattern_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="pattern not found")
    x_values, y_values = _pattern_arrays(document)
    if not x_values or not y_values or len(x_values) != len(y_values):
        raise HTTPException(status_code=404, detail="canonical XY data not available")
    if format == "json":
        return PatternXY(
            pattern_id=pattern_id,
            x={"name": "two_theta", "unit": "degree", "values": x_values},
            y={"name": "intensity", "unit": "counts", "values": y_values},
        )
    if format == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["two_theta", "intensity"])
        writer.writerows(zip(x_values, y_values))
        return Response(content=stream.getvalue(), media_type="text/csv")
    return Response(
        content="\n".join(f"{x}\t{y}" for x, y in zip(x_values, y_values)) + "\n",
        media_type="text/plain",
    )

