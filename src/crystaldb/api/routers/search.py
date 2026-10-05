"""Finite-field global search."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from crystaldb.api.db import get_database
from crystaldb.api.schemas import Pattern, Sample, Structure
from crystaldb.api.services.mapping import pattern_model, sample_model, structure_model

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    database: Database = Depends(get_database),
) -> dict[str, object]:
    term = q.strip()
    if not term:
        raise HTTPException(status_code=422, detail="q must not be blank")
    regex = re.escape(term)
    patterns = database.patterns.find(
        {
            "$or": [
                {"pattern_id": {"$regex": regex, "$options": "i"}},
                {"api_source_id": {"$regex": regex, "$options": "i"}},
                {"provenance.evidence": {"$regex": regex, "$options": "i"}},
                {"phase_components.name": {"$regex": regex, "$options": "i"}},
                {"phase_components.formula": {"$regex": regex, "$options": "i"}},
            ]
        },
        {"_id": 0},
    ).sort("pattern_id", 1).limit(limit)
    structures = database.structures.find(
        {
            "$or": [
                {"structure_id": {"$regex": regex, "$options": "i"}},
                {"api_source_id": {"$regex": regex, "$options": "i"}},
                {"formula": {"$regex": regex, "$options": "i"}},
                {"mineral_name": {"$regex": regex, "$options": "i"}},
            ]
        },
        {"_id": 0},
    ).sort("structure_id", 1).limit(limit)
    samples = database.samples.find(
        {
            "$or": [
                {"sample_id": {"$regex": regex, "$options": "i"}},
                {"api_source_id": {"$regex": regex, "$options": "i"}},
                {"name": {"$regex": regex, "$options": "i"}},
                {"formula": {"$regex": regex, "$options": "i"}},
            ]
        },
        {"_id": 0},
    ).sort("sample_id", 1).limit(limit)
    return {
        "query": term,
        "patterns": [pattern_model(document) for document in patterns],
        "structures": [structure_model(document) for document in structures],
        "samples": [sample_model(document) for document in samples],
    }

