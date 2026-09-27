from pymongo import MongoClient


def get_database(
    uri: str = "mongodb://localhost:27017",
    database_name: str = "crystaldb",
):
    client = MongoClient(uri)
    return client[database_name]