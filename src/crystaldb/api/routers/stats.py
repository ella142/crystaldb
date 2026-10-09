"""Dynamic production-backed statistics."""

from fastapi import APIRouter, Depends
from pymongo.database import Database

from crystaldb.api.db import get_database
from crystaldb.api.schemas.common import APIStats

router = APIRouter(prefix="/stats", tags=["stats"])


def _powder_pattern_counts_by_source(database: Database) -> dict[str, int]:
    return {
        row["_id"]: row["count"]
        for row in database.patterns.aggregate(
            [
                {"$match": {"modality": "powder_xrd"}},
                {
                    "$group": {
                        "_id": "$api_source_code",
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
        if row.get("_id")
    }


def _phase_character_counts(database: Database) -> dict[str, int]:
    return {
        row["_id"]: row["count"]
        for row in database.patterns.aggregate(
            [
                {
                    "$group": {
                        "_id": {"$ifNull": ["$phase_character", "unknown"]},
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
        if row.get("_id")
    }


def _source_phase_counts(database: Database) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for row in database.patterns.aggregate(
        [
            {
                "$group": {
                    "_id": {
                        "source": "$api_source_code",
                        "phase": {"$ifNull": ["$phase_character", "unknown"]},
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.source": 1, "_id.phase": 1}},
        ]
    ):
        source = row.get("_id", {}).get("source")
        phase = row.get("_id", {}).get("phase")
        if source and phase:
            result.setdefault(source, {})[phase] = row["count"]
    return result


@router.get("")
def get_stats(database: Database = Depends(get_database)) -> APIStats:
    return APIStats(
        powder_pattern_count=database.patterns.count_documents({"modality": "powder_xrd"}),
        single_crystal_dataset_count=database.reflection_sets.count_documents(
            {"modality": "single_crystal_xrd"}
        ),
        multiphase_pattern_count=database.patterns.count_documents(
            {"phase_character": "multi_phase"}
        ),
        source_count=database.sources.count_documents({}),
        sample_count=database.samples.count_documents({}),
        measurement_count=database.measurements.count_documents({}),
        pattern_count=database.patterns.count_documents({}),
        structure_count=database.structures.count_documents({}),
        reflection_set_count=database.reflection_sets.count_documents({}),
        relation_count=database.relations.count_documents({}),
        powbase_xray_pattern_count=database.patterns.count_documents(
            {"api_source_code": "POWBASE", "modality": "powder_xrd"}
        ),
        powder_pattern_counts_by_source=_powder_pattern_counts_by_source(database),
        phase_character_counts=_phase_character_counts(database),
        source_phase_counts=_source_phase_counts(database),
    )

