"""Source catalog endpoint."""

from fastapi import APIRouter, Depends
from pymongo.database import Database

from crystaldb.api.db import get_database

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources(database: Database = Depends(get_database)) -> dict[str, object]:
    return {
        "items": [
            document
            for document in database.sources.find({}, {"_id": 0}).sort("api_source_code", 1)
        ]
    }

