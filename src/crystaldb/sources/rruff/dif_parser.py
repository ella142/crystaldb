from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient, ReplaceOne


DEFAULT_ZIP_PATH = Path(r"D:\document\aiformaterials\rruff\data\DIF.zip")
DEFAULT_MONGO_URI = "mongodb://127.0.0.1:27017"
DEFAULT_DATABASE = "rruff"
DEFAULT_COLLECTION = "dif"
DATASET_NAME = "DIF"
PARSER_VERSION = "1.0.1"
BATCH_SIZE = 100

FILENAME_RE = re.compile(
    r"^(?P<mineral>.+?)__"
    r"(?P<sample_id>[^_]+)__"
    r"(?P<sample_form>[^_]+)__"
    r"(?P<data_kind>DIF_File)__"
    r"(?P<content_hash>[0-9a-f]+)\.(?P<extension>txt|rtf)$",
    re.IGNORECASE,
)

FLOAT_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"
CELL_RE = re.compile(
    rf"CELL PARAMETERS:\s*({FLOAT_RE})\s+({FLOAT_RE})\s+({FLOAT_RE})"
    rf"\s+({FLOAT_RE})\s+({FLOAT_RE})\s+({FLOAT_RE})",
    re.IGNORECASE,
)
WAVELENGTH_RE = re.compile(
    rf"X-RAY WAVELENGTH:\s*({FLOAT_RE})",
    re.IGNORECASE,
)
BOUNDS_RE = re.compile(
    rf"BOUNDS ON TWO THETA:\s*({FLOAT_RE})\s+({FLOAT_RE})",
    re.IGNORECASE,
)
LIMITS_RE = re.compile(
    r"LIMITS IMPOSED ON THE INDICES ARE:\s*(.*)$",
    re.IGNORECASE,
)
MAX_INTENSITY_RE = re.compile(
    rf"MAX\. ABS\. INTENSITY / VOLUME\*\*2:\s*({FLOAT_RE})",
    re.IGNORECASE,
)
CUTOFF_RE = re.compile(
    rf"INTENSITY cut off value is\s*({FLOAT_RE})",
    re.IGNORECASE,
)
ATOM_HEADER_RE = re.compile(
    r"ATOM\s+X\s+Y\s+Z\s+OCCUPANCY\s+ISO\(B\)",
    re.IGNORECASE,
)
PEAK_HEADER_RE = re.compile(
    r"2-THETA\s+INTENSITY\s+D-SPACING\s+H\s+K\s+L",
    re.IGNORECASE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rtf_to_text(value: str) -> str:
    for marker in (r"\fonttbl", r"\*\generator", r"\colortbl"):
        while marker in value:
            marker_position = value.find(marker)
            group_start = value.rfind("{", 0, marker_position)
            if group_start < 0:
                break

            depth = 0
            group_end = None
            for index in range(group_start, len(value)):
                if value[index] == "{":
                    depth += 1
                elif value[index] == "}":
                    depth -= 1
                    if depth == 0:
                        group_end = index
                        break

            if group_end is None:
                break
            value = value[:group_start] + value[group_end + 1 :]

    value = re.sub(r"\\par[d]?", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\\line", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\\tab", "\t", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\\'([0-9a-fA-F]{2})",
        lambda match: bytes.fromhex(match.group(1)).decode(
            "cp1252", errors="replace"
        ),
        value,
    )
    value = re.sub(
        r"\\u(-?\d+)\??",
        lambda match: chr(int(match.group(1)) % 65536),
        value,
    )
    value = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", value)
    value = value.replace("{", "").replace("}", "")
    return value.replace("\r\n", "\n").replace("\r", "\n")


def normalize_sample_id(value: str) -> str:
    match = re.match(r"^([A-Za-z]\d+)", value)
    return match.group(1) if match else value


def parse_limits(raw: str) -> list[float]:
    values = re.findall(FLOAT_RE, raw)
    return [float(value) for value in values]


def parse_atom_line(line: str) -> dict[str, Any] | None:
    parts = line.split()
    if len(parts) != 6:
        return None

    try:
        return {
            "element": parts[0],
            "x": float(parts[1]),
            "y": float(parts[2]),
            "z": float(parts[3]),
            "occupancy": float(parts[4]),
            "iso_b": float(parts[5]),
        }
    except ValueError:
        return None


def parse_peak_line(line: str) -> dict[str, Any] | None:
    parts = line.split()
    if len(parts) != 6:
        return None

    try:
        return {
            "two_theta": float(parts[0]),
            "intensity": float(parts[1]),
            "d_spacing": float(parts[2]),
            "h": int(parts[3]),
            "k": int(parts[4]),
            "l": int(parts[5]),
        }
    except ValueError:
        return None


def parse_dif(entry_name: str, text: str) -> dict[str, Any]:
    filename_match = FILENAME_RE.match(entry_name)
    if not filename_match:
        raise ValueError(f"Unexpected filename format: {entry_name}")

    filename_data = filename_match.groupdict()
    
    lines = text.splitlines()

    nonempty = [
        line.strip()
        for line in lines
        if line.strip()
    ]

    first_nonempty = (
        nonempty[0]
        if nonempty
        else None
    )

    structure_headers = (
        "CELL PARAMETERS",
        "SPACE GROUP",
        "ATOM",
        "X-RAY WAVELENGTH",
        "BOUNDS ON TWO THETA",
        "LIMITS IMPOSED",
        "MAX. ABS. INTENSITY",
        "THE INTENSITY",
        "2-THETA",
    )

    if (
        first_nonempty
        and not first_nonempty.upper().startswith(
            structure_headers
        )
    ):
        mineral_from_body = first_nonempty
    else:
        mineral_from_body = None

    cell_parameters: dict[str, float] = {}
    space_group = None
    wavelength = None
    two_theta_bounds: list[float] = []
    index_limits: list[float] = []
    max_abs_intensity_volume_squared = None
    intensity_cutoff = None
    locality = None
    atoms: list[dict[str, Any]] = []
    peaks: list[dict[str, Any]] = []
    references: list[str] = []
    skipped_atom_lines: list[dict[str, Any]] = []
    skipped_peak_lines: list[dict[str, Any]] = []
    in_atoms = False
    in_peaks = False

    for line_number, original_line in enumerate(lines, start=1):
        stripped = original_line.strip()
        if not stripped:
            continue

        if ATOM_HEADER_RE.search(stripped):
            in_atoms = True
            in_peaks = False
            continue

        if PEAK_HEADER_RE.search(stripped):
            in_peaks = True
            in_atoms = False
            continue

        cell_match = CELL_RE.search(stripped)
        if cell_match:
            values = [float(value) for value in cell_match.groups()]
            cell_parameters = dict(
                zip(
                    ["a", "b", "c", "alpha", "beta", "gamma"],
                    values,
                )
            )
            continue

        wavelength_match = WAVELENGTH_RE.search(stripped)
        if wavelength_match:
            wavelength = float(wavelength_match.group(1))
            continue

        bounds_match = BOUNDS_RE.search(stripped)
        if bounds_match:
            two_theta_bounds = [
                float(bounds_match.group(1)),
                float(bounds_match.group(2)),
            ]
            continue

        limits_match = LIMITS_RE.search(stripped)
        if limits_match:
            index_limits = parse_limits(limits_match.group(1))
            continue

        max_intensity_match = MAX_INTENSITY_RE.search(stripped)
        if max_intensity_match:
            max_abs_intensity_volume_squared = float(
                max_intensity_match.group(1)
            )
            continue

        cutoff_match = CUTOFF_RE.search(stripped)
        if cutoff_match:
            intensity_cutoff = float(cutoff_match.group(1))
            continue

        if stripped.lower().startswith("locality:"):
            locality = stripped.split(":", 1)[1].strip()
            continue

        if stripped.upper().startswith("SPACE GROUP:"):
            space_group = stripped.split(":", 1)[1].strip()
            continue

        if in_atoms:
            atom = parse_atom_line(stripped)
            if atom:
                atoms.append(atom)
            elif not stripped.upper().startswith("X-RAY"):
                skipped_atom_lines.append(
                    {"line": line_number, "text": stripped}
                )
            continue

        if in_peaks:
            peak = parse_peak_line(stripped)
            if peak:
                peaks.append(peak)
            elif not stripped.upper().startswith("THE INTENSITY"):
                skipped_peak_lines.append(
                    {"line": line_number, "text": stripped}
                )
            continue

        if (
            len(references) < 20
            and stripped
            and not stripped.startswith("Diffraction data computed")
            and not stripped.startswith("along with the cell parameters")
            and not stripped.upper().startswith("CELL PARAMETERS")
            and not stripped.upper().startswith("SPACE GROUP")
        ):
            references.append(stripped)

    return {
        "source": "RRUFF",
        "dataset": DATASET_NAME,
        "sample_id": normalize_sample_id(filename_data["sample_id"]),
        "mineral": mineral_from_body,
        "filename_mineral": filename_data["mineral"],
        "sample_form": filename_data["sample_form"],
        "data_kind": filename_data["data_kind"],
        "source_format": filename_data["extension"].lower(),
        "content_hash_from_filename": filename_data["content_hash"],
        "locality": locality,
        "references": references,
        "crystal_structure": {
            "cell_parameters": cell_parameters,
            "space_group": space_group,
            "atoms": atoms,
            "atom_count": len(atoms),
        },
        "diffraction": {
            "x_ray_wavelength": wavelength,
            "two_theta_bounds": two_theta_bounds,
            "index_limits": index_limits,
            "max_abs_intensity_volume_squared": (
                max_abs_intensity_volume_squared
            ),
            "intensity_cutoff": intensity_cutoff,
            "peaks": peaks,
            "peak_count": len(peaks),
        },
        "parse_warnings": {
            "skipped_atom_line_count": len(skipped_atom_lines),
            "skipped_atom_lines": skipped_atom_lines[:20],
            "skipped_peak_line_count": len(skipped_peak_lines),
            "skipped_peak_lines": skipped_peak_lines[:20],
        },
    }


def document_for_entry(
    zip_path: Path,
    zip_hash: str,
    entry: zipfile.ZipInfo,
    content: bytes,
) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    source_format = Path(entry.filename).suffix.lower().lstrip(".")
    normalized_text = rtf_to_text(text) if source_format == "rtf" else text
    document = parse_dif(entry.filename, normalized_text)
    document["import_meta"] = {
        "zip_path": str(zip_path.resolve()),
        "zip_sha256": zip_hash,
        "inner_file": entry.filename,
        "entry_sha256": sha256_bytes(content),
        "entry_size_bytes": entry.file_size,
        "entry_compressed_size_bytes": entry.compress_size,
        "entry_crc": entry.CRC,
        "parser_version": PARSER_VERSION,
        "parsed_at": utc_now(),
    }
    return document


def ensure_indexes(collection) -> None:
    collection.create_index(
        [("import_meta.zip_path", 1), ("import_meta.inner_file", 1)],
        unique=True,
        name="unique_zip_inner_file",
    )
    collection.create_index("sample_id", name="sample_id")
    collection.create_index("mineral", name="mineral")
    collection.create_index("dataset", name="dataset")
    collection.create_index("source_format", name="source_format")
    collection.create_index("crystal_structure.space_group", name="space_group")


def flush(collection, operations: list[ReplaceOne]) -> None:
    if operations:
        collection.bulk_write(operations, ordered=False)
        operations.clear()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse RRUFF DIF files and optionally write them to MongoDB."
    )
    parser.add_argument("--zip", default=str(DEFAULT_ZIP_PATH))
    parser.add_argument("--uri", default=DEFAULT_MONGO_URI)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--hash-zip", action="store_true")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be zero or positive")

    zip_path = Path(args.zip)
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP file does not exist: {zip_path}")

    zip_hash = sha256_file(zip_path) if args.write or args.hash_zip else ""
    stats: Counter[str] = Counter()
    errors: list[str] = []
    peak_counts: list[int] = []
    atom_counts: list[int] = []
    operations: list[ReplaceOne] = []
    client = None
    collection = None

    if args.write:
        client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        collection = client[args.database][args.collection]
        ensure_indexes(collection)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            entries = sorted(
                [entry for entry in archive.infolist() if not entry.is_dir()],
                key=lambda entry: entry.filename.lower(),
            )
            for entry in entries:
                if args.limit and stats["entries_seen"] >= args.limit:
                    break
                stats["entries_seen"] += 1
                try:
                    document = document_for_entry(
                        zip_path,
                        zip_hash,
                        entry,
                        archive.read(entry),
                    )
                    peak_counts.append(document["diffraction"]["peak_count"])
                    atom_counts.append(
                        document["crystal_structure"]["atom_count"]
                    )
                    stats[f"format_{document['source_format']}"] += 1
                    if document["diffraction"]["peak_count"] == 0:
                        stats["missing_peaks"] += 1
                    if not document["crystal_structure"]["atoms"]:
                        stats["missing_atoms"] += 1

                    if args.write:
                        operations.append(
                            ReplaceOne(
                                {
                                    "import_meta.zip_path": str(
                                        zip_path.resolve()
                                    ),
                                    "import_meta.inner_file": entry.filename,
                                },
                                document,
                                upsert=True,
                            )
                        )
                        if len(operations) >= BATCH_SIZE:
                            flush(collection, operations)
                    stats["documents_prepared"] += 1
                except Exception as exc:
                    errors.append(f"{entry.filename}: {exc}")
                    stats["errors"] += 1

                if stats["entries_seen"] % 500 == 0:
                    print(
                        f"Processed {stats['entries_seen']} entries; "
                        f"prepared {stats['documents_prepared']}; "
                        f"errors {stats['errors']}"
                    )

            if args.write:
                flush(collection, operations)
    finally:
        if client is not None:
            client.close()

    print("Import mode:", "WRITE" if args.write else "DRY-RUN")
    print(f"ZIP: {zip_path}")
    print(f"Database: {args.database}")
    print(f"Collection: {args.collection}")
    print(f"Entries seen: {stats['entries_seen']}")
    print(f"Documents prepared: {stats['documents_prepared']}")
    print(f"Errors: {stats['errors']}")
    print(f"Formats: txt={stats['format_txt']} rtf={stats['format_rtf']}")
    print(f"Missing peaks: {stats['missing_peaks']}")
    print(f"Missing atoms: {stats['missing_atoms']}")
    if peak_counts:
        print(f"Peak count min/max/avg: {min(peak_counts)} / {max(peak_counts)} / {sum(peak_counts) / len(peak_counts):.2f}")
    if atom_counts:
        print(f"Atom count min/max/avg: {min(atom_counts)} / {max(atom_counts)} / {sum(atom_counts) / len(atom_counts):.2f}")
    if errors:
        print("\nFirst errors:")
        for error in errors[:10]:
            print(f"- {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
