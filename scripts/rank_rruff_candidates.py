from pathlib import Path
import json

from crystaldb.mongo import get_database

from crystaldb.matching.rruff_signature import (
    build_rruff_signature,
    get_rruff_ideal_chemistry,
)

from crystaldb.matching.candidate_finder import (
    find_candidates,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INDEX_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cif_index.json"
)


def main():
    sample_id = "R050336"

    rruff_db = get_database(
        database_name="rruff"
    )

    dif_doc = rruff_db.dif.find_one(
        {"sample_id": sample_id}
    )

    ideal_chemistry = get_rruff_ideal_chemistry(
        rruff_db,
        sample_id,
    )

    signature = build_rruff_signature(
        dif_doc,
        ideal_chemistry=ideal_chemistry,
    )

    with INDEX_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        cif_index = json.load(f)

    candidates = find_candidates(
        signature,
        cif_index,
    )

    # 只看“样品结构”候选
    sample_candidates = [
        item
        for item in candidates
        if item["candidate_type"].startswith(
            "sample_candidate"
        )
    ]

    sample_candidates.sort(
        key=lambda item: (
            item["evidence"][
                "max_length_relative_difference"
            ],
            item["evidence"][
                "max_angle_difference"
            ],
        )
    )

    print(
        f"\nRRUFF {sample_id}"
        f" / {signature['sample_mineral']}"
    )

    print(
        "------------------------------------------------------------"
    )

    print(
        f"{'Rank':<6}"
        f"{'Source':<8}"
        f"{'ID':<12}"
        f"{'Length diff':<16}"
        f"{'Angle diff':<14}"
        f"{'Name'}"
    )

    print(
        "------------------------------------------------------------"
    )

    for rank, item in enumerate(
        sample_candidates,
        start=1,
    ):
        evidence = item["evidence"]

        length_percent = (
            evidence[
                "max_length_relative_difference"
            ]
            * 100
        )

        angle_difference = evidence[
            "max_angle_difference"
        ]

        print(
            f"{rank:<6}"
            f"{item['source']:<8}"
            f"{item['source_id']:<12}"
            f"{length_percent:<16.4f}"
            f"{angle_difference:<14.4f}"
            f"{item['mineral_name']}"
        )


if __name__ == "__main__":
    main()