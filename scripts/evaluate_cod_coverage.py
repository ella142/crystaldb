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

MANIFEST_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_search_manifest.json"
)

CIF_INDEX_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cif_index.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_coverage_results.json"
)


def main():
    rruff_db = get_database(
        database_name="rruff"
    )

    # --------------------------------
    # 1. Load COD search manifest
    # --------------------------------

    with MANIFEST_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        manifest = json.load(f)

    # --------------------------------
    # 2. Load local CIF index
    # --------------------------------

    with CIF_INDEX_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        cif_index = json.load(f)

    # Fast lookup:
    # COD ID -> CIF index record
    cod_index_by_id = {
        record["source_id"]: record
        for record in cif_index
        if (
            record.get("source") == "COD"
            and record.get("parse_status") == "ok"
        )
    }

    mineral_names = list(
        manifest.keys()
    )

    # --------------------------------
    # 3. Get all RRUFF DIF records
    #    belonging to these minerals
    # --------------------------------

    dif_docs = list(
        rruff_db.dif.find(
            {
                "filename_mineral": {
                    "$in": mineral_names
                }
            }
        ).sort("sample_id", 1)
    )

    print(
        f"RRUFF DIF samples to test: "
        f"{len(dif_docs)}"
    )

    results = []

    # --------------------------------
    # 4. Evaluate sample by sample
    # --------------------------------

    for index, dif_doc in enumerate(
        dif_docs,
        start=1,
    ):
        sample_id = dif_doc.get(
            "sample_id"
        )

        mineral = dif_doc.get(
            "filename_mineral"
        )

        print(
            "\n================================"
        )

        print(
            f"[{index}/{len(dif_docs)}] "
            f"{sample_id} / {mineral}"
        )

        print(
            "================================"
        )

        try:
            ideal_chemistry = (
                get_rruff_ideal_chemistry(
                    rruff_db,
                    sample_id,
                )
            )

            signature = build_rruff_signature(
                dif_doc,
                ideal_chemistry=ideal_chemistry,
            )

            # --------------------------------
            # Only use COD IDs retrieved for
            # this mineral.
            # --------------------------------

            cod_ids = (
                manifest
                .get(mineral, {})
                .get("cod_ids", [])
            )

            local_candidates = [
                cod_index_by_id[cod_id]
                for cod_id in cod_ids
                if cod_id in cod_index_by_id
            ]

            candidates = find_candidates(
                signature,
                local_candidates,
            )

            match_results = []

            for candidate in candidates:
                cif_path = (
                    PROJECT_ROOT
                    / candidate["file_path"]
                )

                match_result = (
                    match_rruff_to_cif(
                        sample_id=sample_id,
                        cif_path=cif_path,
                    )
                )

                classification = (
                    match_result[
                        "classification"
                    ]
                )

                match_results.append(
                    {
                        "source":
                            candidate["source"],

                        "source_id":
                            candidate["source_id"],

                        "file_path":
                            candidate["file_path"],

                        "candidate_type":
                            candidate[
                                "candidate_type"
                            ],

                        "status":
                            classification[
                                "status"
                            ],

                        "relation_type":
                            classification.get(
                                "relation_type"
                            ),

                        "evidence":
                            classification[
                                "evidence"
                            ],
                    }
                )

            # --------------------------------
            # Sample-level summary
            # --------------------------------

            sample_structure_matches = [
                item
                for item in match_results
                if item["relation_type"]
                == "sample_structure"
            ]

            reference_structure_matches = [
                item
                for item in match_results
                if item["relation_type"]
                == "reference_structure"
            ]

            strong_sample_matches = [
                item
                for item
                in sample_structure_matches
                if item["status"]
                == "strong_match"
            ]

            print(
                f"COD searched: "
                f"{len(cod_ids)}"
            )

            print(
                f"Finder candidates: "
                f"{len(candidates)}"
            )

            print(
                f"Sample structure: "
                f"{len(sample_structure_matches)}"
            )

            print(
                f"Strong sample matches: "
                f"{len(strong_sample_matches)}"
            )

            print(
                f"Reference structure: "
                f"{len(reference_structure_matches)}"
            )

            results.append(
                {
                    "rruff_sample_id":
                        sample_id,

                    "mineral":
                        mineral,

                    "ideal_chemistry":
                        ideal_chemistry,

                    "cod_search_count":
                        len(cod_ids),

                    "finder_candidate_count":
                        len(candidates),

                    "sample_structure_count":
                        len(
                            sample_structure_matches
                        ),

                    "strong_sample_match_count":
                        len(
                            strong_sample_matches
                        ),

                    "reference_structure_count":
                        len(
                            reference_structure_matches
                        ),

                    "matches":
                        match_results,

                    "status":
                        (
                            "sample_structure_found"
                            if sample_structure_matches
                            else (
                                "reference_structure_only"
                                if reference_structure_matches
                                else (
                                    "needs_review_only"
                                    if match_results
                                    else "no_finder_candidate"
                                )
                            )
                        ),                        
                }
            )

        except Exception as exc:
            print(
                f"ERROR: {exc}"
            )

            results.append(
                {
                    "rruff_sample_id":
                        sample_id,

                    "mineral":
                        mineral,

                    "status":
                        "error",

                    "error":
                        str(exc),
                }
            )

    # --------------------------------
    # 5. Save detailed results
    # --------------------------------

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

    # --------------------------------
    # 6. Coverage summary
    # --------------------------------

    sample_structure_found = sum(
        1
        for item in results
        if item.get("status")
        == "sample_structure_found"
    )

    strong_sample_found = sum(
        1
        for item in results
        if item.get(
            "strong_sample_match_count",
            0,
        ) > 0
    )

    reference_only = sum(
        1
        for item in results
        if item.get("status")
        == "reference_structure_only"
    )

    needs_review_only = sum(
        1
        for item in results
        if item.get("status")
        == "needs_review_only"
    )

    no_finder_candidate = sum(
        1
        for item in results
        if item.get("status")
        == "no_finder_candidate"
    )
    errors = sum(
        1
        for item in results
        if item.get("status")
        == "error"
    )

    print(
        "\n================================"
    )

    print(
        "COD coverage evaluation complete"
    )

    print(
        "================================"
    )

    print(
        f"RRUFF samples tested:       "
        f"{len(results)}"
    )

    print(
        f"Sample structure found:     "
        f"{sample_structure_found}"
    )

    print(
        f"Strong sample match found:  "
        f"{strong_sample_found}"
    )

    print(
        f"Reference structure only:   "
        f"{reference_only}"
    )

    print(
        f"Needs review only:          "
        f"{needs_review_only}"
    )

    print(
        f"No finder candidate:        "
        f"{no_finder_candidate}"
    )
    print(
        f"Errors:                     "
        f"{errors}"
    )

    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()