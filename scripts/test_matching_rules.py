from copy import deepcopy
from pathlib import Path
from pprint import pprint

from crystaldb.cif_parser import parse_cif
from crystaldb.mongo import get_database

from crystaldb.matching.rruff_signature import (
    build_rruff_signature,
)
from crystaldb.matching.candidate_compare import (
    compare_candidate,
)
from crystaldb.matching.rules import (
    classify_candidate,
)


PROJECT_ROOT = Path(
    r"D:\document\aiformaterials\crystaldb"
)


# =========================
# 1. Read RRUFF reference
# =========================

rruff = get_database(database_name="rruff")

dif_doc = rruff.dif.find_one(
    {"sample_id": "R080016"}
)

if dif_doc is None:
    raise RuntimeError("Cannot find R080016 DIF")

signature = build_rruff_signature(dif_doc)


# =========================
# 2. Read correct COD CIF
# =========================

candidate = parse_cif(
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cod"
    / "9000253.cif"
)


# =========================
# 3. Positive control
# =========================

positive_comparison = compare_candidate(
    signature,
    candidate,
)

positive_result = classify_candidate(
    positive_comparison
)

print("\n===== POSITIVE CONTROL =====")
pprint(positive_result)


# =========================
# 4. Create wrong candidate
# =========================

wrong_candidate = deepcopy(candidate)

wrong_candidate["mineral_name"] = "FakeMineral"

wrong_candidate["cell_parameters"]["a"] = (
    candidate["cell_parameters"]["a"] * 1.10
)


# =========================
# 5. Negative control
# =========================

negative_comparison = compare_candidate(
    signature,
    wrong_candidate,
)

negative_result = classify_candidate(
    negative_comparison
)

print("\n===== NEGATIVE CONTROL =====")
pprint(negative_result)