"""Measurement endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from crystaldb.api.db import get_database
from crystaldb.api.schemas import Measurement
from crystaldb.api.services.mapping import measurement_model

router = APIRouter(prefix="/measurements", tags=["measurements"])


@router.get("/{measurement_id}", response_model=Measurement)
def get_measurement(
    measurement_id: str,
    database: Database = Depends(get_database),
) -> Measurement:
    document = database.measurements.find_one({"measurement_id": measurement_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="measurement not found")
    return measurement_model(document)

