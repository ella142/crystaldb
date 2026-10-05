"""Portable paths for files stored below CRYSTALDB_DATA_ROOT."""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
DATA_ROOT_ENV = "CRYSTALDB_DATA_ROOT"


def get_data_root(data_root: str | os.PathLike[str] | None = None) -> Path:
    """Return the configured data root, falling back to this checkout."""
    if data_root is None:
        data_root = os.environ.get(DATA_ROOT_ENV)
    return Path(data_root) if data_root else DEFAULT_DATA_ROOT


def normalize_file_key(file_key: str) -> str:
    """Validate and normalize a Mongo file key to POSIX-relative form."""
    if not isinstance(file_key, str) or not file_key.strip():
        raise ValueError("file key must be a non-empty string")

    value = file_key.replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or path.drive or re.match(r"^[A-Za-z]:/", value):
        raise ValueError(f"file key must be relative: {file_key!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"file key contains an unsafe path component: {file_key!r}")
    return path.as_posix()


def resolve_data_path(
    file_key: str,
    data_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve a Mongo file key below the configured data root."""
    normalized = normalize_file_key(file_key)
    root = get_data_root(data_root).resolve()
    resolved = (root / Path(*PurePosixPath(normalized).parts)).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"resolved path escapes data root: {file_key!r}")
    return resolved


def make_file_key(relative_path: str | os.PathLike[str]) -> str:
    """Convert a data-root-relative path to a Mongo file key."""
    return normalize_file_key(Path(relative_path).as_posix())
