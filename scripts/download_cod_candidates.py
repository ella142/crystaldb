from pathlib import Path

from crystaldb.sources.cod import (
    search_cod_by_text,
    download_cod_cif,
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cod"
)


def main():
    mineral = "Actinolite"

    cod_ids = search_cod_by_text(
        mineral
    )

    print(
        f"{mineral}: "
        f"{len(cod_ids)} COD candidates"
    )

    success = 0
    errors = 0

    for cod_id in cod_ids:
        try:
            path = download_cod_cif(
                cod_id,
                OUTPUT_DIR,
            )

            print(
                f"OK  {cod_id} -> {path.name}"
            )

            success += 1

        except Exception as exc:
            print(
                f"ERROR {cod_id}: {exc}"
            )

            errors += 1

    print("\n------------------------------")
    print(f"Found:      {len(cod_ids)}")
    print(f"Downloaded: {success}")
    print(f"Errors:     {errors}")


if __name__ == "__main__":
    main()