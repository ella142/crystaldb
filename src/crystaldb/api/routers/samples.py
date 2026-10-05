"""Sample endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from crystaldb.api.db import get_database
from crystaldb.api.schemas import Sample
from crystaldb.api.services.mapping import sample_model

router = APIRouter(prefix="/samples", tags=["samples"])


@router.get("/{sample_id}", response_model=Sample)
def get_sample(sample_id: str, database: Database = Depends(get_database)) -> Sample:
    document = database.samples.find_one({"sample_id": sample_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="sample not found")
    return sample_model(document)

