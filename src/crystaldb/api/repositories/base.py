"""Small repository helpers with explicit query construction."""

from __future__ import annotations

from typing import Any

from pymongo.collection import Collection


def without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    document = dict(document)
    document.pop("_id", None)
    return document


class MongoRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def get(self, field: str, value: str) -> dict[str, Any] | None:
        return without_mongo_id(self.collection.find_one({field: value}))

    def list(
        self,
        query: dict[str, Any],
        *,
        limit: int,
        after_id: str | None = None,
        id_field: str,
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        bounded_query = dict(query)
        if after_id is not None:
            bounded_query[id_field] = {"$gt": after_id}
        fields = {"_id": 0, **(projection or {})}
        cursor = (
            self.collection.find(bounded_query, fields)
            .sort(id_field, 1)
            .limit(limit)
        )
        return [dict(item) for item in cursor]

