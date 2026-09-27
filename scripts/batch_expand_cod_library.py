from pathlib import Path
import json

from crystaldb.mongo import get_database
from crystaldb.sources.cod import (
    search_cod_by_text,
    download_cod_cif,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

COD_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cod"
)

MANIFEST_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_search_manifest.json"
)


def main():
    rruff_db = get_database(
        database_name="rruff"
    )

    # --------------------------------
    # Prepare directories
    # --------------------------------
    COD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    MANIFEST_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------
    # 1. Collect unique mineral names
    # --------------------------------
    minerals = sorted(
        name
        for name in rruff_db.dif.distinct(
            "filename_mineral"
        )
        if name
    )

    # Day 4 first batch:
    # only test 50unique minerals.
    minerals = minerals[:50]

    print(
        f"Unique minerals in this batch: "
        f"{len(minerals)}"
    )

    seen_cod_ids = set()

    search_manifest = {}

    total_downloaded = 0
    total_existing = 0
    total_errors = 0

    # --------------------------------
    # 2. Search COD mineral by mineral
    # --------------------------------
    for index, mineral in enumerate(
        minerals,
        start=1,
    ):
        print(
            "\n================================"
        )

        print(
            f"[{index}/{len(minerals)}] "
            f"{mineral}"
        )

        print(
            "================================"
        )

        try:
            cod_ids = search_cod_by_text(
                mineral
            )

        except Exception as exc:
            print(
                f"SEARCH ERROR: {exc}"
            )

            search_manifest[mineral] = {
                "query": mineral,
                "status": "error",
                "error": str(exc),
                "candidate_count": 0,
                "cod_ids": [],
            }

            total_errors += 1
            continue

        search_manifest[mineral] = {
            "query": mineral,
            "status": "ok",
            "candidate_count": len(cod_ids),
            "cod_ids": cod_ids,
        }

        print(
            f"COD candidates: {len(cod_ids)}"
        )

        # --------------------------------
        # 3. Download unique COD CIFs
        # --------------------------------
        for cod_id in cod_ids:

            # Same COD structure may appear
            # in searches for multiple minerals.
            if cod_id in seen_cod_ids:
                continue

            expected_path = (
                COD_DIR
                / f"{cod_id}.cif"
            )

            existed_before = (
                expected_path.exists()
            )

            try:
                download_cod_cif(
                    cod_id,
                    COD_DIR,
                )

                # Only mark as seen after the
                # download/check succeeded.
                seen_cod_ids.add(
                    cod_id
                )

                if existed_before:
                    total_existing += 1

                else:
                    total_downloaded += 1

            except Exception as exc:
                print(
                    f"ERROR {cod_id}: {exc}"
                )

                total_errors += 1

    # --------------------------------
    # 4. Save search manifest
    # --------------------------------
    with MANIFEST_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            search_manifest,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------
    # Summary
    # --------------------------------
    print(
        "\n================================"
    )

    print(
        "COD library expansion complete"
    )

    print(
        "================================"
    )

    print(
        f"Minerals searched:  "
        f"{len(minerals)}"
    )

    print(
        f"Unique COD IDs:      "
        f"{len(seen_cod_ids)}"
    )

    print(
        f"Already existed:     "
        f"{total_existing}"
    )

    print(
        f"Newly downloaded:    "
        f"{total_downloaded}"
    )

    print(
        f"Errors:              "
        f"{total_errors}"
    )

    print(
        f"Manifest:            "
        f"{MANIFEST_FILE}"
    )


if __name__ == "__main__":
    main()