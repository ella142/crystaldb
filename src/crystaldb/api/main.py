"""FastAPI application entry point for CrystalDB API v0.1.2."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crystaldb.api.config import get_settings
from crystaldb.api.routers import (
    health,
    measurements,
    patterns,
    reflections,
    releases,
    samples,
    search,
    sources,
    stats,
    structures,
)

settings = get_settings()

app = FastAPI(
    title="CrystalDB API",
    version=settings.api_release,
    description=(
        "Programmatic access to provenance-aware experimental diffraction data "
        "and crystal-structure linkages."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

api_prefix = "/api/v1"
app.include_router(health.router, prefix=api_prefix)
app.include_router(patterns.router, prefix=api_prefix)
app.include_router(structures.router, prefix=api_prefix)
app.include_router(measurements.router, prefix=api_prefix)
app.include_router(samples.router, prefix=api_prefix)
app.include_router(reflections.router, prefix=api_prefix)
app.include_router(sources.router, prefix=api_prefix)
app.include_router(search.router, prefix=api_prefix)
app.include_router(stats.router, prefix=api_prefix)
app.include_router(releases.router, prefix=api_prefix)

