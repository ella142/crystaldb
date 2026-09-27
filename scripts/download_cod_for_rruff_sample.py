from pathlib import Path
import argparse

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


def get_rruff_sample_mineral(
    rruff_db,
    sample_id,
):
    """
    Get the sample mineral name from RRUFF DIF.
    """

    dif_doc = rruff_db.dif.find_one(
        {"sample_id": sample_id},
        {
            "_id": 0,
            "sample_id": 1,
            "filename_mineral": 1,
            "mineral": 1,
        },
    )

    if dif_doc is None:
        raise ValueError(
            f"RRUFF DIF not found: {sample_id}"
        )

    sample_mineral = dif_doc.get(
        "filename_mineral"
    )

    if not sample_mineral:
        raise ValueError(
            f"RRUFF sample mineral missing: "
            f"{sample_id}"
        )

    return sample_mineral


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "sample_id",
        help="RRUFF sample ID, e.g. R050336",
    )

    args = parser.parse_args()

    sample_id = args.sample_id

    rruff_db = get_database(
        database_name="rruff"
    )

    # --------------------------------
    # 1. Get RRUFF mineral name
    # --------------------------------

    mineral = get_rruff_sample_mineral(
        rruff_db,
        sample_id,
    )

    print(
        f"RRUFF sample: {sample_id}"
    )

    print(
        f"Mineral: {mineral}"
    )

    # --------------------------------
    # 2. Search COD
    # --------------------------------

    cod_ids = search_cod_by_text(
        mineral
    )

    print(
        f"COD candidates found: "
        f"{len(cod_ids)}"
    )

    # --------------------------------
    # 3. Download missing CIF files
    # --------------------------------

    already_exists = 0
    downloaded = 0
    errors = 0

    for cod_id in cod_ids:

        expected_path = (
            COD_DIR
            / f"{cod_id}.cif"
        )

        existed_before = (
            expected_path.exists()
        )

        try:
            path = download_cod_cif(
                cod_id,
                COD_DIR,
            )

            if existed_before:
                print(
                    f"EXISTS  {cod_id}"
                )

                already_exists += 1

            else:
                print(
                    f"DOWNLOADED  "
                    f"{cod_id} -> {path.name}"
                )

                downloaded += 1

        except Exception as exc:
            print(
                f"ERROR  {cod_id}: {exc}"
            )

            errors += 1

    # --------------------------------
    # Summary
    # --------------------------------

    print(
        "\n------------------------------"
    )

    print(
        f"RRUFF sample:       {sample_id}"
    )

    print(
        f"Mineral:            {mineral}"
    )

    print(
        f"COD candidates:     {len(cod_ids)}"
    )

    print(
        f"Already existed:    {already_exists}"
    )

    print(
        f"Newly downloaded:   {downloaded}"
    )

    print(
        f"Errors:             {errors}"
    )


if __name__ == "__main__":
    main()