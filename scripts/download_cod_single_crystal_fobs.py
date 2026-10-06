"""Download the current COD has_fobs=1 CIF/HKL target pool.

The download is resumable: non-empty target files are never downloaded again,
and each new file is first written to a sibling ``.part`` path before being
published.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CIF_DIR = Path(
    r"D:\document\aiformaterials\ai4\single_crystal_xray\cod\processed\pairs\cif"
)
DEFAULT_HKL_DIR = Path(
    r"D:\document\aiformaterials\ai4\single_crystal_xray\cod\processed\pairs\hkl"
)
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_single_crystal_download_manifest_v1.json"
)

COD_LIST_URL = "https://www.crystallography.net/cod/result"
COD_FILE_URL = "https://www.crystallography.net/cod/{cod_id}.{suffix}"
COD_ID_RE = re.compile(r"^\d+$")
DOWNLOAD_SUFFIXES = ("cif", "hkl")
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
USER_AGENT = "CrystalDB-COD-single-crystal-fobs/1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_session(max_retries: int) -> requests.Session:
    retry = Retry(
        total=max_retries,
        connect=max_retries,
        read=max_retries,
        status=max_retries,
        backoff_factor=1.0,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def parse_cod_ids(response_text: str) -> list[str]:
    """Parse one numeric COD ID per line without accepting HTML or metadata."""
    ids: list[str] = []
    seen: set[str] = set()
    ignored_lines: list[str] = []

    for raw_line in response_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if COD_ID_RE.fullmatch(line):
            if line not in seen:
                ids.append(line)
                seen.add(line)
            continue
        ignored_lines.append(line)

    if not ids:
        preview = response_text[:200].replace("\n", "\\n")
        raise RuntimeError(
            "COD has_fobs response contained no numeric IDs; "
            f"response preview={preview!r}"
        )
    if ignored_lines and any("<html" in line.lower() for line in ignored_lines[:5]):
        raise RuntimeError("COD has_fobs response appears to be HTML, not an ID list")
    return ids


def fetch_target_ids(
    session: requests.Session,
    timeout_seconds: float,
) -> list[str]:
    response = session.get(
        COD_LIST_URL,
        params={"has_fobs": "1", "format": "lst"},
        timeout=(timeout_seconds, timeout_seconds),
    )
    response.raise_for_status()
    return parse_cod_ids(response.text)


def is_nonempty(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def local_file_stats(directory: Path, suffix: str) -> dict[str, Any]:
    files = [
        path
        for path in directory.glob(f"*.{suffix}")
        if path.is_file()
    ]
    stem_counts = Counter(path.stem for path in files)
    nonempty_ids = {
        path.stem
        for path in files
        if is_nonempty(path)
    }
    zero_byte_files = [
        path.name
        for path in files
        if path.stat().st_size == 0
    ]
    duplicate_stems = sorted(
        stem
        for stem, count in stem_counts.items()
        if count > 1
    )
    return {
        "file_count": len(files),
        "unique_ids": len(stem_counts),
        "nonempty_unique_ids": len(nonempty_ids),
        "nonempty_ids": nonempty_ids,
        "zero_byte_count": len(zero_byte_files),
        "zero_byte_files": zero_byte_files,
        "duplicate_stems": duplicate_stems,
    }


def atomic_publish(part_path: Path, target_path: Path) -> bool:
    """Publish without replacing a concurrently-created non-empty target."""
    if is_nonempty(target_path):
        part_path.unlink(missing_ok=True)
        return False

    # On Windows, os.rename does not replace an existing file. If the target
    # is an empty stale file, os.replace is allowed to repair that invalid file.
    try:
        os.rename(part_path, target_path)
    except FileExistsError:
        if is_nonempty(target_path):
            part_path.unlink(missing_ok=True)
            return False
        os.replace(part_path, target_path)
    return True


def download_file(
    session: requests.Session,
    cod_id: str,
    suffix: str,
    target_path: Path,
    timeout_seconds: float,
) -> tuple[str, str | None]:
    """Return (status, error), with status in skip/downloaded/error."""
    if is_nonempty(target_path):
        return "skip", None

    target_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = target_path.with_name(target_path.name + ".part")
    part_path.unlink(missing_ok=True)

    try:
        url = COD_FILE_URL.format(cod_id=cod_id, suffix=suffix)
        byte_count = 0
        with session.get(
            url,
            stream=True,
            timeout=(timeout_seconds, timeout_seconds),
        ) as response:
            response.raise_for_status()
            with part_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        byte_count += len(chunk)

        if byte_count == 0:
            raise IOError(f"COD returned an empty {suffix.upper()} response")
        published = atomic_publish(part_path, target_path)
        if not published:
            return "skip", None
        if not is_nonempty(target_path):
            raise IOError(f"published {suffix.upper()} file is empty")
        return "downloaded", None
    except Exception as exc:
        part_path.unlink(missing_ok=True)
        return "error", f"{type(exc).__name__}: {exc}"


def select_processing_ids(
    target_ids: list[str],
    cif_dir: Path,
    hkl_dir: Path,
    explicit_ids: list[str] | None,
    only_missing: bool,
    limit: int | None,
) -> list[str]:
    selected = target_ids
    if explicit_ids:
        target_set = set(target_ids)
        unknown = sorted(set(explicit_ids) - target_set)
        if unknown:
            raise ValueError(
                "explicit IDs are not in the current COD has_fobs target: "
                + ", ".join(unknown)
            )
        explicit_set = set(explicit_ids)
        selected = [cod_id for cod_id in selected if cod_id in explicit_set]

    if only_missing:
        selected = [
            cod_id
            for cod_id in selected
            if not is_nonempty(cif_dir / f"{cod_id}.cif")
            or not is_nonempty(hkl_dir / f"{cod_id}.hkl")
        ]

    if limit is not None:
        selected = selected[:limit]
    return selected


def run_cif_parse_qc(
    target_ids: list[str],
    cif_dir: Path,
) -> dict[str, Any]:
    try:
        import gemmi
    except Exception as exc:
        return {
            "available": False,
            "parse_ok": 0,
            "parse_failed": 0,
            "parse_failed_items": [],
            "error": f"{type(exc).__name__}: {exc}",
        }

    parse_ok = 0
    parse_failed_items: list[dict[str, str]] = []
    for cod_id in target_ids:
        path = cif_dir / f"{cod_id}.cif"
        if not is_nonempty(path):
            continue
        try:
            gemmi.cif.read_file(str(path))
            parse_ok += 1
        except Exception as exc:
            parse_failed_items.append(
                {
                    "cod_id": cod_id,
                    "filepath": str(path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "available": True,
        "parse_ok": parse_ok,
        "parse_failed": len(parse_failed_items),
        "parse_failed_items": parse_failed_items,
    }


def run_hkl_qc(
    target_ids: list[str],
    hkl_dir: Path,
    sample_size: int,
    random_seed: int,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    readable_count = 0
    unreadable_items: list[dict[str, str]] = []
    readable_target_ids: list[str] = []
    sizes: list[int] = []

    for cod_id in target_ids:
        path = hkl_dir / f"{cod_id}.hkl"
        if not is_nonempty(path):
            continue
        try:
            with path.open("rb") as handle:
                while handle.read(1024 * 1024):
                    pass
            readable_count += 1
            readable_target_ids.append(cod_id)
            sizes.append(path.stat().st_size)
        except Exception as exc:
            unreadable_items.append(
                {
                    "cod_id": cod_id,
                    "filepath": str(path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    rng = random.Random(random_seed)
    sampled_ids = rng.sample(
        readable_target_ids,
        min(sample_size, len(readable_target_ids)),
    )
    samples: list[dict[str, Any]] = []
    for cod_id in sampled_ids:
        path = hkl_dir / f"{cod_id}.hkl"
        raw = path.read_bytes()[:512]
        samples.append(
            {
                "cod_id": cod_id,
                "filepath": str(path),
                "size_bytes": path.stat().st_size,
                "contains_nul_byte": b"\x00" in raw,
                "preview_text": raw.decode("utf-8", errors="replace"),
            }
        )

    qc = {
        "nonempty_target_files_readable": readable_count,
        "unreadable_count": len(unreadable_items),
        "sample_size_requested": sample_size,
        "random_seed": random_seed,
        "samples": samples,
        "size_bytes": {
            "total": sum(sizes),
            "min": min(sizes) if sizes else None,
            "max": max(sizes) if sizes else None,
        },
    }
    return qc, unreadable_items


def build_final_qc(
    target_ids: list[str],
    cif_dir: Path,
    hkl_dir: Path,
) -> dict[str, Any]:
    cif_stats = local_file_stats(cif_dir, "cif")
    hkl_stats = local_file_stats(hkl_dir, "hkl")
    cif_ids = cif_stats["nonempty_ids"]
    hkl_ids = hkl_stats["nonempty_ids"]
    target_set = set(target_ids)
    complete_pairs = cif_ids & hkl_ids
    cif_only = cif_ids - hkl_ids
    hkl_only = hkl_ids - cif_ids
    local_ids = cif_ids | hkl_ids

    return {
        "cif_count": len(cif_ids),
        "hkl_count": len(hkl_ids),
        "complete_pairs": len(complete_pairs),
        "cif_only": len(cif_only),
        "hkl_only": len(hkl_only),
        "target_ids_missing_cif": len(target_set - cif_ids),
        "target_ids_missing_hkl": len(target_set - hkl_ids),
        "local_ids_not_in_current_target": len(local_ids - target_set),
        "zero_byte_cif": cif_stats["zero_byte_count"],
        "zero_byte_hkl": hkl_stats["zero_byte_count"],
        "duplicate_cif_stems": len(cif_stats["duplicate_stems"]),
        "duplicate_hkl_stems": len(hkl_stats["duplicate_stems"]),
        "local_cif_ids_not_in_current_target": sorted(cif_ids - target_set),
        "local_hkl_ids_not_in_current_target": sorted(hkl_ids - target_set),
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".part")
    temp_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def print_final_report(
    target_ids: list[str],
    existing_before: dict[str, Any],
    download_results: Counter[str],
    final_qc: dict[str, Any],
    cif_parse_qc: dict[str, Any],
) -> None:
    print("\nFinal report")
    print(f"COD target IDs: {len(target_ids)}")
    print(f"CIF before: {existing_before['cif']['file_count']}")
    print(f"HKL before: {existing_before['hkl']['file_count']}")
    print(f"CIF downloaded: {download_results['cif_downloaded']}")
    print(f"HKL downloaded: {download_results['hkl_downloaded']}")
    print(f"CIF skipped: {download_results['cif_skipped']}")
    print(f"HKL skipped: {download_results['hkl_skipped']}")
    print(f"CIF failed: {download_results['cif_failed']}")
    print(f"HKL failed: {download_results['hkl_failed']}")
    print(f"Final CIF: {final_qc['cif_count']}")
    print(f"Final HKL: {final_qc['hkl_count']}")
    print(f"Complete pairs: {final_qc['complete_pairs']}")
    print(f"CIF only: {final_qc['cif_only']}")
    print(f"HKL only: {final_qc['hkl_only']}")
    print(f"CIF parse OK: {cif_parse_qc['parse_ok']}")
    print(f"CIF parse failed: {cif_parse_qc['parse_failed']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize COD has_fobs=1 CIF and HKL files."
    )
    parser.add_argument("--cif-dir", type=Path, default=DEFAULT_CIF_DIR)
    parser.add_argument("--hkl-dir", type=Path, default=DEFAULT_HKL_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument(
        "--ids",
        nargs="+",
        help="Process these current target IDs only; the API is still fetched.",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Limit processing to IDs missing a non-empty CIF or HKL.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many selected IDs; useful for smoke tests.",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Run download/QC without replacing the official manifest.",
    )
    parser.add_argument(
        "--hkl-sample-size",
        type=int,
        default=5,
        help="Number of random HKL files to sample during QC.",
    )
    parser.add_argument("--random-seed", type=int, default=20261002)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be >= 0")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.hkl_sample_size < 0:
        raise SystemExit("--hkl-sample-size must be >= 0")

    args.cif_dir.mkdir(parents=True, exist_ok=True)
    args.hkl_dir.mkdir(parents=True, exist_ok=True)
    existing_before = {
        "cif": local_file_stats(args.cif_dir, "cif"),
        "hkl": local_file_stats(args.hkl_dir, "hkl"),
    }

    session = build_session(args.max_retries)
    retrieval_timestamp = utc_now()
    try:
        target_ids = fetch_target_ids(session, args.timeout)
    except Exception as exc:
        print(
            f"FATAL: unable to fetch current COD has_fobs=1 target: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    processing_ids = select_processing_ids(
        target_ids=target_ids,
        cif_dir=args.cif_dir,
        hkl_dir=args.hkl_dir,
        explicit_ids=args.ids,
        only_missing=args.only_missing,
        limit=args.limit,
    )
    print(
        f"COD target IDs: {len(target_ids)}; "
        f"processing this run: {len(processing_ids)}"
    )

    download_results: Counter[str] = Counter()
    failed_items: list[dict[str, str]] = []
    total = len(processing_ids)
    for index, cod_id in enumerate(processing_ids, start=1):
        cif_status, cif_error = download_file(
            session,
            cod_id,
            "cif",
            args.cif_dir / f"{cod_id}.cif",
            args.timeout,
        )
        hkl_status, hkl_error = download_file(
            session,
            cod_id,
            "hkl",
            args.hkl_dir / f"{cod_id}.hkl",
            args.timeout,
        )
        cif_key = {
            "skip": "cif_skipped",
            "downloaded": "cif_downloaded",
            "error": "cif_failed",
        }[cif_status]
        hkl_key = {
            "skip": "hkl_skipped",
            "downloaded": "hkl_downloaded",
            "error": "hkl_failed",
        }[hkl_status]
        download_results[cif_key] += 1
        download_results[hkl_key] += 1
        if cif_error:
            failed_items.append(
                {
                    "stage": "cif_download",
                    "cod_id": cod_id,
                    "error": cif_error,
                }
            )
        if hkl_error:
            failed_items.append(
                {
                    "stage": "hkl_download",
                    "cod_id": cod_id,
                    "error": hkl_error,
                }
            )
        print(
            f"[{index}/{total}] {cod_id} "
            f"CIF={cif_status} HKL={hkl_status}",
            flush=True,
        )

    final_qc = build_final_qc(target_ids, args.cif_dir, args.hkl_dir)
    cif_parse_qc = run_cif_parse_qc(target_ids, args.cif_dir)
    hkl_qc, hkl_read_failures = run_hkl_qc(
        target_ids,
        args.hkl_dir,
        args.hkl_sample_size,
        args.random_seed,
    )
    failed_items.extend(
        {
            "stage": "cif_parse",
            "cod_id": item["cod_id"],
            "filepath": item["filepath"],
            "error": item["error"],
        }
        for item in cif_parse_qc["parse_failed_items"]
    )
    failed_items.extend(
        {
            "stage": "hkl_read",
            "cod_id": item["cod_id"],
            "filepath": item["filepath"],
            "error": item["error"],
        }
        for item in hkl_read_failures
    )

    manifest = {
        "source": "Crystallography Open Database",
        "selection": {"has_fobs": True},
        "retrieval_timestamp_utc": retrieval_timestamp,
        "current_cod_id_count": len(target_ids),
        "processing_id_count": len(processing_ids),
        "processing_scope": {
            "only_missing": args.only_missing,
            "explicit_ids": args.ids,
            "limit": args.limit,
        },
        "existing_before": {
            "cif": existing_before["cif"]["file_count"],
            "hkl": existing_before["hkl"]["file_count"],
            "complete_pairs": len(
                existing_before["cif"]["nonempty_ids"]
                & existing_before["hkl"]["nonempty_ids"]
            ),
        },
        "download_results": {
            "cif_skipped": download_results["cif_skipped"],
            "cif_downloaded": download_results["cif_downloaded"],
            "cif_failed": download_results["cif_failed"],
            "hkl_skipped": download_results["hkl_skipped"],
            "hkl_downloaded": download_results["hkl_downloaded"],
            "hkl_failed": download_results["hkl_failed"],
        },
        "final": final_qc,
        "cif_parse_qc": cif_parse_qc,
        "hkl_qc": hkl_qc,
        "failed_items": failed_items,
    }
    if not args.no_manifest:
        write_json_atomic(args.manifest, manifest)
        print(f"Manifest: {args.manifest}")

    print_final_report(
        target_ids,
        existing_before,
        download_results,
        final_qc,
        cif_parse_qc,
    )
    if failed_items:
        print("\nFailed items:")
        for item in failed_items:
            print(
                f"- {item.get('cod_id', '?')} "
                f"[{item.get('stage', 'unknown')}]: {item.get('error', '')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
