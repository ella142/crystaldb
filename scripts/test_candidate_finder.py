from pathlib import Path
from pprint import pprint
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


def test_sample(sample_id):
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

    print("\n============================")
    print(f"RRUFF sample: {sample_id}")
    print("============================")

    pprint(candidates)


test_sample("R080016")
test_sample("R050336")
test_sample("R040010")
test_sample("R040045")