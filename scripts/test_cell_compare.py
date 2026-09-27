from pprint import pprint
from pathlib import Path

from crystaldb.mongo import get_database
from crystaldb.cif_parser import parse_cif
from crystaldb.matching.rruff_signature import build_rruff_signature
from crystaldb.matching.cell_compare import compare_cells


PROJECT_ROOT = Path(
    r"D:\document\aiformaterials\crystaldb"
)


# 1. 读取 RRUFF DIF
rruff = get_database(database_name="rruff")

dif_doc = rruff.dif.find_one(
    {"sample_id": "R080016"}
)

signature = build_rruff_signature(dif_doc)


# 2. 读取 COD CIF
cod = parse_cif(
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cod"
    / "9000253.cif"
)


# 3. 比较晶胞
comparison = compare_cells(
    signature["cell_parameters"],
    cod["cell_parameters"],
)


print("RRUFF cell:")
pprint(signature["cell_parameters"])

print("\nCOD cell:")
pprint(cod["cell_parameters"])

print("\nComparison:")
pprint(comparison)