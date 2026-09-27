from datetime import datetime, timezone
from pathlib import Path

from crystaldb.cif_parser import parse_cif
from crystaldb.mongo import get_database


PROJECT_ROOT = Path(r"D:\document\aiformaterials\crystaldb")

cif_relative_path = Path("data/raw/cod/9000253.cif")
cif_path = PROJECT_ROOT / cif_relative_path

structure_id = "STR_000001"
cod_id = "9000253"


# 1. 解析 CIF
parsed = parse_cif(cif_path)


# 2. 连接 MongoDB
db = get_database()


# 3. 更新对应 structure
result = db.structures.update_one(
    {"structure_id": structure_id},
    {
        "$set": {
            "matched_cif": {
                "database": "COD",
                "cod_id": cod_id,
                "file_path": cif_relative_path.as_posix(),

                "data_block": parsed["data_block"],
                "formula": parsed["formula"],
                "mineral_name": parsed["mineral_name"],
                "space_group": parsed["space_group"],

                "cell_parameters": parsed["cell_parameters"],

                "atoms": parsed["atoms"],
                "atom_count": parsed["atom_count"],

                "structure_completeness": "complete",
            },

            "cif_match.status": "matched",
            "cif_match.has_atomic_coordinates": (
                parsed["atom_count"] > 0
            ),

            "updated_at": datetime.now(timezone.utc),
        }
    },
)


print("matched_count:", result.matched_count)
print("modified_count:", result.modified_count)