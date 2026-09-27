from pathlib import Path

from crystaldb.cif_parser import parse_cif
from crystaldb.mongo import get_database

from crystaldb.matching.rruff_signature import (
    build_rruff_signature,
    get_rruff_ideal_chemistry,
)
from crystaldb.matching.candidate_compare import (
    compare_candidate,
)
from crystaldb.matching.rules import (
    classify_candidate,
)


def match_rruff_to_cif(
    sample_id,
    cif_path,
):
    """
    Match one RRUFF DIF record against one CIF candidate.
    """

    cif_path = Path(cif_path)

    # 1. Read RRUFF DIF
    rruff = get_database(
        database_name="rruff"
    )

    dif_doc = rruff.dif.find_one(
        {"sample_id": sample_id}
    )

    if dif_doc is None:
        raise ValueError(
            f"Cannot find RRUFF DIF for {sample_id}"
        )

    # 2. Build clean RRUFF signature
    ideal_chemistry = get_rruff_ideal_chemistry(
        rruff,
        sample_id,
    )

    signature = build_rruff_signature(
        dif_doc,
        ideal_chemistry=ideal_chemistry,
    )

    # 3. Parse candidate CIF
    candidate = parse_cif(
        cif_path
    )

    # 4. Compare candidate with RRUFF
    comparison = compare_candidate(
        signature,
        candidate,
    )

    # 5. Apply matching rules
    classification = classify_candidate(
        comparison
    )

    return {
        "rruff_sample_id": sample_id,

        "candidate": {
            "file_name": cif_path.name,
            "data_block": candidate["data_block"],
            "mineral_name": candidate["mineral_name"],
            "formula": candidate["formula"],
            "space_group": candidate["space_group"],
        },

        "comparison": comparison,

        "classification": classification,
    }