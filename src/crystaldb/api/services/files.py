"""Safe access to data-root-relative files."""

from __future__ import annotations

from pathlib import Path

from crystaldb.data_paths import resolve_data_path


def resolve_registered_file(file_key: str, data_root: Path) -> Path:
    return resolve_data_path(file_key, data_root)

