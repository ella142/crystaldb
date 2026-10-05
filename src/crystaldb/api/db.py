"""Mongo connection helpers for the read-only API."""

from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from crystaldb.api.config import get_settings


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)


def get_database() -> Database:
    return get_client()[get_settings().mongo_db]

