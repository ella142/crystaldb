from pathlib import Path
import json

from crystaldb.matching.matcher import match_rruff_to_cif


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MAPPING_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_structure_candidates.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_structure_match_results.json"
)


def main():
    with MAPPING_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        candidates = json.load(f)

    results = []

    for item in candidates:
        rruff_sample_id = item["rruff_sample_id"]

        structure_source = item[
            "structure_source"
        ]

        structure_source_id = item[
            "structure_source_id"
        ]

        relative_cif_path = Path(
            item["cif_path"]
        )

        cif_path = (
            PROJECT_ROOT
            / relative_cif_path
        )

        print(
            f"\nMatching {rruff_sample_id}"
            f" -> {structure_source}"
            f" {structure_source_id}"
        )

        if not cif_path.exists():
            print(
                f"  ERROR: CIF not found: "
                f"{relative_cif_path}"
            )

            results.append(
                {
                    **item,
                    "status": "file_missing",
                }
            )

            continue

        try:
            match_result = match_rruff_to_cif(
                sample_id=rruff_sample_id,
                cif_path=cif_path,
            )

            status = (
                match_result[
                    "classification"
                ]["status"]
            )

            print(
                f"  status = {status}"
            )

            results.append(
                {
                    **item,
                    "status": status,
                    "match_result": match_result,
                }
            )

        except Exception as exc:
            print(
                f"  ERROR: {exc}"
            )

            results.append(
                {
                    **item,
                    "status": "error",
                    "error": str(exc),
                }
            )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("\n------------------------------")
    print("Batch matching complete")
    print(f"Results saved to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()