"""Dataset release endpoint."""

from fastapi import APIRouter, Depends
from pymongo.database import Database

from crystaldb.api.db import get_database

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("")
def list_releases(database: Database = Depends(get_database)) -> dict[str, object]:
    return {
        "items": [
            document
            for document in database.releases.find({}, {"_id": 0}).sort("release_id", 1)
        ]
    }

