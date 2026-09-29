from pathlib import Path
import json

from crystaldb.cif_parser import parse_cif


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cif_index.json"
)
COD_MANIFEST_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_search_manifest.json"
)
CIF_SOURCES = [
    {
        "source": "COD",
        "directory": (
            PROJECT_ROOT
            / "data"
            / "raw"
            / "cod"
        ),
    },
    {
        "source": "AMCSD",
        "directory": (
            PROJECT_ROOT
            / "data"
            / "raw"
            / "amcsd"
        ),
    },
]

def build_index():
    records = []

    with COD_MANIFEST_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        cod_manifest = json.load(f)

    accepted_cod_ids = {
        cod_id
        for item in cod_manifest.values()
        if item.get("status") == "ok"
        for cod_id in item.get("cod_ids", [])
    }

    print(
        f"Accepted COD IDs from manifest: "
        f"{len(accepted_cod_ids)}"
    )
    for source_info in CIF_SOURCES:
        source = source_info["source"]
        directory = source_info["directory"]

        if not directory.exists():
            print(
                f"Skip missing directory: {directory}"
            )
            continue

        for cif_path in sorted(
            directory.rglob("*.cif")
        ):
            if (
                source == "COD"
                and cif_path.stem
                not in accepted_cod_ids
            ):
                continue            
            print(
                f"Parsing {source}: "
                f"{cif_path.name}"
            )

            relative_path = cif_path.relative_to(
                PROJECT_ROOT
            )

            try:
                parsed = parse_cif(cif_path)

                record = {
                    "source": source,

                    "source_id": cif_path.stem,

                    "file_path":
                        relative_path.as_posix(),

                    "data_block":
                        parsed.get("data_block"),

                    "mineral_name":
                        parsed.get("mineral_name"),

                    "formula":
                        parsed.get("formula"),

                    "space_group":
                        parsed.get("space_group"),

                    "cell_parameters":
                        parsed.get(
                            "cell_parameters"
                        ),

                    "atom_count":
                        parsed.get("atom_count"),

                    "parse_status": "ok",
                }

            except Exception as exc:
                record = {
                    "source": source,

                    "source_id": cif_path.stem,

                    "file_path":
                        relative_path.as_posix(),

                    "parse_status": "error",

                    "error": str(exc),
                }

            records.append(record)

    return records


def main():
    records = build_index()

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False,
        )

    ok_count = sum(
        1
        for record in records
        if record["parse_status"] == "ok"
    )

    error_count = sum(
        1
        for record in records
        if record["parse_status"] == "error"
    )

    print("\n------------------------------")
    print("CIF index complete")
    print(f"Total:  {len(records)}")
    print(f"OK:     {ok_count}")
    print(f"Errors: {error_count}")
    print(f"Saved:  {OUTPUT_FILE}")


if __name__ == "__main__":
    main()