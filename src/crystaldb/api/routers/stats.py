"""Dynamic pilot statistics."""

from fastapi import APIRouter, Depends
from pymongo.database import Database

from crystaldb.api.db import get_database

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
def get_stats(database: Database = Depends(get_database)) -> dict[str, int]:
    return {
        "powder_pattern_count": database.patterns.count_documents({"modality": "powder_xrd"}),
        "single_crystal_dataset_count": database.reflection_sets.count_documents(
            {"modality": "single_crystal_xrd"}
        ),
        "multiphase_pattern_count": database.patterns.count_documents(
            {"phase_character": "multi_phase"}
        ),
        "structure_count": database.structures.count_documents({}),
        "source_count": database.sources.count_documents({}),
    }

