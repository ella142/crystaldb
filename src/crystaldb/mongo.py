import os

from pymongo import MongoClient


def get_database(
    uri: str | None = None,
    database_name: str | None = None,
):
    uri = uri or os.environ.get(
        "CRYSTALDB_MONGO_URI",
        "mongodb://localhost:27017",
    )
    database_name = database_name or os.environ.get(
        "CRYSTALDB_MONGO_DATABASE",
        "crystaldb",
    )
    client = MongoClient(uri)
    return client[database_name]
