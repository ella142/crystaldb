from crystaldb.mongo import get_database


rruff = get_database(database_name="rruff")

doc = rruff.dif.find_one(
    {
        "$expr": {
            "$ne": [
                {"$toLower": {"$ifNull": ["$filename_mineral", ""]}},
                {"$toLower": {"$ifNull": ["$mineral", ""]}},
            ]
        },
        "crystal_structure.cell_parameters.a": {
            "$ne": None
        },
    },
    {
        "_id": 0,
        "sample_id": 1,
        "filename_mineral": 1,
        "mineral": 1,
        "crystal_structure.cell_parameters": 1,
        "crystal_structure.space_group": 1,
        "crystal_structure.atom_count": 1,
        "references": 1,
    },
)

print(doc)