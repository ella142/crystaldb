from pprint import pprint

from crystaldb.mongo import get_database

from crystaldb.matching.rruff_signature import (
    build_rruff_signature,
    get_rruff_ideal_chemistry,
)


rruff_db = get_database(
    database_name="rruff"
)


for sample_id in [
    "R080016",
    "R050336",
    "R040010",
    "R040045",
]:
    dif_doc = rruff_db.dif.find_one(
        {"sample_id": sample_id}
    )

    chemistry = get_rruff_ideal_chemistry(
        rruff_db,
        sample_id,
    )

    signature = build_rruff_signature(
        dif_doc,
        ideal_chemistry=chemistry,
    )

    print("\n============================")
    print(sample_id)
    print("============================")

    pprint(
        {
            "sample_mineral":
                signature["sample_mineral"],

            "reference_structure_name":
                signature[
                    "reference_structure_name"
                ],

            "ideal_chemistry":
                signature["ideal_chemistry"],
        }
    )