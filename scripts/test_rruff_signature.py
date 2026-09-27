from pprint import pprint

from crystaldb.mongo import get_database
from crystaldb.matching.rruff_signature import build_rruff_signature


rruff = get_database(database_name="rruff")

dif_doc = rruff.dif.find_one(
    {"sample_id": "R080016"}
)

if dif_doc is None:
    raise RuntimeError("找不到 R080016 DIF")

signature = build_rruff_signature(dif_doc)

pprint(signature)