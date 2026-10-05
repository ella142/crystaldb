"""Single-crystal reflection-set endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pymongo.database import Database

from crystaldb.api.config import get_settings
from crystaldb.api.db import get_database
from crystaldb.api.repositories.generic import ReflectionRepository
from crystaldb.api.schemas import PaginatedResponse, ReflectionSet
from crystaldb.api.services.files import resolve_registered_file
from crystaldb.api.services.mapping import reflection_model
from crystaldb.api.services.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/reflection-sets", tags=["reflection-sets"])


@router.get("", response_model=PaginatedResponse[ReflectionSet])
def list_reflection_sets(
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
    database: Database = Depends(get_database),
) -> PaginatedResponse[ReflectionSet]:
    try:
        after_id = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    query: dict[str, object] = {}
    if source:
        query["api_source_code"] = source.upper()
    documents = ReflectionRepository(database.reflection_sets).list(
        query,
        limit=limit + 1,
        after_id=after_id,
        id_field="reflection_set_id",
    )
    has_next = len(documents) > limit
    documents = documents[:limit]
    next_cursor = encode_cursor(documents[-1]["reflection_set_id"]) if has_next and documents else None
    return PaginatedResponse(
        items=[reflection_model(document) for document in documents],
        meta={"count": len(documents), "next_cursor": next_cursor},
    )


@router.get("/{reflection_set_id}", response_model=ReflectionSet)
def get_reflection_set(
    reflection_set_id: str,
    database: Database = Depends(get_database),
) -> ReflectionSet:
    document = database.reflection_sets.find_one(
        {"reflection_set_id": reflection_set_id}, {"_id": 0}
    )
    if document is None:
        raise HTTPException(status_code=404, detail="reflection set not found")
    return reflection_model(document)


@router.get("/{reflection_set_id}/hkl")
def get_reflection_set_hkl(
    reflection_set_id: str,
    database: Database = Depends(get_database),
) -> FileResponse:
    document = database.reflection_sets.find_one(
        {"reflection_set_id": reflection_set_id}, {"_id": 0}
    )
    if document is None:
        raise HTTPException(status_code=404, detail="reflection set not found")
    file_key = (document.get("file") or {}).get("key")
    if not file_key:
        raise HTTPException(status_code=404, detail="HKL file not registered")
    try:
        path = resolve_registered_file(file_key, get_settings().data_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid registered HKL path") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="HKL file not found")
    return FileResponse(
        path,
        media_type="text/plain",
        filename=f"{reflection_set_id}.hkl",
    )

