"""Environment-backed API configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from crystaldb.data_paths import get_data_root


class Settings(BaseModel):
    mongo_uri: str = Field(
        default_factory=lambda: os.environ.get(
            "CRYSTALDB_MONGO_URI", "mongodb://localhost:27017"
        )
    )
    mongo_db: str = Field(
        default_factory=lambda: os.environ.get(
            "CRYSTALDB_MONGO_DB",
            os.environ.get("CRYSTALDB_MONGO_DATABASE", "crystaldb_api_pilot"),
        )
    )
    data_root: Path = Field(
        default_factory=lambda: get_data_root(
            os.environ.get("CRYSTALDB_DATA_ROOT")
        )
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.environ.get(
                "CRYSTALDB_CORS_ORIGINS", "http://localhost:3000"
            ).split(",")
            if origin.strip()
        ]
    )
    api_version: str = "v1"
    api_release: str = "0.1.2"
    dataset_release: str = "crystaldb-api-pilot-v0.1.2"
    default_limit: int = 50
    max_limit: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()

