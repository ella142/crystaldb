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
from crystaldb.matching.matcher import (
    match_rruff_to_cif,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INDEX_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cif_index.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_auto_match_results.json"
)


def main():
    rruff_db = get_database(
        database_name="rruff"
    )

    with INDEX_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        cif_index = json.load(f)

    results = []

    # 先只测试 50 条
    dif_docs = rruff_db.dif.find(
        {}
    ).sort(
        "sample_id", 1
    ).limit(50)

    for dif_doc in dif_docs:
        sample_id = dif_doc.get("sample_id")

        print(f"\nProcessing {sample_id}")

        try:
            ideal_chemistry = get_rruff_ideal_chemistry(
                rruff_db,
                sample_id,
            )

            signature = build_rruff_signature(
                dif_doc,
                ideal_chemistry=ideal_chemistry,
            )
            candidates = find_candidates(
                signature,
                cif_index,
            )

            candidate_results = []

            for candidate in candidates:
                cif_path = (
                    PROJECT_ROOT
                    / candidate["file_path"]
                )

                match_result = match_rruff_to_cif(
                    sample_id=sample_id,
                    cif_path=cif_path,
                )

                classification = (
                    match_result["classification"]
                )

                candidate_results.append(
                    {
                        "source":
                            candidate["source"],

                        "source_id":
                            candidate["source_id"],

                        "file_path":
                            candidate["file_path"],

                        "status":
                            classification["status"],
                        "relation_type":
                            classification.get("relation_type"),                            

                        "evidence":
                            classification["evidence"],
                    }
                )

            print(
                f"  candidates = "
                f"{len(candidate_results)}"
            )

            results.append(
                {
                    "rruff_sample_id":
                        sample_id,

                    "candidate_count":
                        len(candidate_results),

                    "candidates":
                        candidate_results,

                    "status":
                        (
                            "candidates_found"
                            if candidate_results
                            else "no_local_candidate"
                        ),
                }
            )

        except Exception as exc:
            print(f"  ERROR: {exc}")

            results.append(
                {
                    "rruff_sample_id":
                        sample_id,

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

    strong_count = 0
    candidate_count = 0
    no_local_count = 0
    error_count = 0

    for result in results:
        if result["status"] == "no_local_candidate":
            no_local_count += 1

        elif result["status"] == "error":
            error_count += 1

        for candidate in result.get(
            "candidates",
            [],
        ):
            if candidate["status"] == "strong_match":
                strong_count += 1

            elif candidate["status"] == "candidate":
                candidate_count += 1

    print("\n================================")
    print("Batch RRUFF matching complete")
    print("================================")
    print(f"Samples tested:     {len(results)}")
    print(f"Strong matches:     {strong_count}")
    print(f"Candidates:         {candidate_count}")
    print(f"No local candidate: {no_local_count}")
    print(f"Errors:             {error_count}")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()