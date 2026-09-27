from pathlib import Path
from pprint import pprint
import json

from crystaldb.mongo import get_database

from crystaldb.matching.rruff_signature import (
    build_rruff_signature,
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


def run_sample(sample_id):
    rruff_db = get_database(
        database_name="rruff"
    )

    dif_doc = rruff_db.dif.find_one(
        {"sample_id": sample_id}
    )

    if dif_doc is None:
        raise ValueError(
            f"RRUFF DIF not found: {sample_id}"
        )

    signature = build_rruff_signature(
        dif_doc
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

    print("\n================================")
    print(f"RRUFF sample: {sample_id}")
    print(f"Candidates found: {len(candidates)}")
    print("================================")

    final_results = []

    for candidate in candidates:
        cif_path = (
            PROJECT_ROOT
            / candidate["file_path"]
        )

        result = match_rruff_to_cif(
            sample_id=sample_id,
            cif_path=cif_path,
        )

        final_results.append(
            {
                "source":
                    candidate["source"],

                "source_id":
                    candidate["source_id"],

                "file_path":
                    candidate["file_path"],

                "status":
                    result[
                        "classification"
                    ]["status"],

                "evidence":
                    result[
                        "classification"
                    ]["evidence"],
            }
        )

    pprint(final_results)


run_sample("R080016")
run_sample("R050336")