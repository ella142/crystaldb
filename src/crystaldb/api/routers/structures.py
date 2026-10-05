"""Crystal-structure endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pymongo.database import Database

from crystaldb.api.config import get_settings
from crystaldb.api.db import get_database
from crystaldb.api.repositories.structures import StructureRepository
from crystaldb.api.schemas import PaginatedResponse, Structure
from crystaldb.api.services.files import resolve_registered_file
from crystaldb.api.services.mapping import structure_model
from crystaldb.api.services.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/structures", tags=["structures"])


@router.get("", response_model=PaginatedResponse[Structure])
def list_structures(
    source: str | None = Query(default=None),
    formula: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
    database: Database = Depends(get_database),
) -> PaginatedResponse[Structure]:
    try:
        after_id = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    query: dict[str, object] = {}
    if source:
        query["api_source_code"] = source.upper()
    if formula:
        query["formula_normalized"] = formula.replace(" ", "")
    documents = StructureRepository(database.structures).list(
        query,
        limit=limit + 1,
        after_id=after_id,
        id_field="structure_id",
    )
    has_next = len(documents) > limit
    documents = documents[:limit]
    next_cursor = encode_cursor(documents[-1]["structure_id"]) if has_next and documents else None
    return PaginatedResponse(
        items=[structure_model(document) for document in documents],
        meta={"count": len(documents), "next_cursor": next_cursor},
    )


@router.get("/{structure_id}", response_model=Structure)
def get_structure(structure_id: str, database: Database = Depends(get_database)) -> Structure:
    document = database.structures.find_one({"structure_id": structure_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="structure not found")
    return structure_model(document)


@router.get("/{structure_id}/cif")
def get_structure_cif(structure_id: str, database: Database = Depends(get_database)) -> FileResponse:
    document = database.structures.find_one({"structure_id": structure_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="structure not found")
    file_info = document.get("file") or {}
    file_key = file_info.get("key")
    if not file_key:
        raise HTTPException(status_code=404, detail="CIF not registered")
    try:
        path = resolve_registered_file(file_key, get_settings().data_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid registered CIF path") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="CIF file not found")
    return FileResponse(
        path,
        media_type="chemical/x-cif",
        filename=f"{structure_id}.cif",
    )

