from crystaldb.mongo import get_database


db = get_database()

structure = db.structures.find_one(
    {"structure_id": "STR_000001"},
    {
        "_id": 0,
        "structure_id": 1,
        "source_structure_name": 1,
        "cif_match": 1,
    },
)

print(structure)