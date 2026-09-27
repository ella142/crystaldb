from pathlib import Path
from pprint import pprint

from crystaldb.cif_parser import parse_cif
from crystaldb.mongo import get_database
from crystaldb.matching.rruff_signature import build_rruff_signature
from crystaldb.matching.candidate_compare import compare_candidate


PROJECT_ROOT = Path(
    r"D:\document\aiformaterials\crystaldb"
)


# 1. RRUFF
rruff = get_database(database_name="rruff")

dif_doc = rruff.dif.find_one(
    {"sample_id": "R080016"}
)

if dif_doc is None:
    raise RuntimeError("找不到 R080016 DIF")

signature = build_rruff_signature(dif_doc)


# 2. COD candidate
candidate = parse_cif(
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cod"
    / "9000253.cif"
)


# 3. Compare
result = compare_candidate(
    signature,
    candidate,
)

pprint(result)