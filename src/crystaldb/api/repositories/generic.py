"""Repositories for the remaining canonical resources."""

from .base import MongoRepository


class MeasurementRepository(MongoRepository):
    pass


class SampleRepository(MongoRepository):
    pass


class ReflectionRepository(MongoRepository):
    pass

