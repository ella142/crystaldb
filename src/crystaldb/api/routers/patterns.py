"""Pattern endpoints."""

from __future__ import annotations

import csv
import io
import json
from typing import Literal

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
    documents = repository.list_filtered(
        source=source,
        modality=modality,
        phase_character=phase_character,
        component_formula=component_formula,
        structure_linkage=structure_linkage,
        structure_id=structure_id,
        dataset_role=dataset_role,
        limit=limit + 1,
        after_id=after_id,
    )
    has_next = len(documents) > limit
    documents = documents[:limit]
    next_cursor = encode_cursor(documents[-1]["pattern_id"]) if has_next and documents else None
    return PaginatedResponse(
        items=[pattern_model(document) for document in documents],
        meta={"count": len(documents), "next_cursor": next_cursor},
    )


@router.get("/{pattern_id}", response_model=Pattern)
def get_pattern(pattern_id: str, database: Database = Depends(get_database)) -> Pattern:
    document = database.patterns.find_one({"pattern_id": pattern_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="pattern not found")
    return pattern_model(document)


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

