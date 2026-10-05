"""Health endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from crystaldb.api.config import get_settings
from crystaldb.api.db import get_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health(database: Database = Depends(get_database)) -> dict[str, str]:
    try:
        database.command("ping")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {
        "status": "ok",
        "api_version": get_settings().api_version,
        "database": get_settings().mongo_db,
    }

