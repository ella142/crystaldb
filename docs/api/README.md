# CrystalDB API v0.1.2

## Start locally

```powershell
conda activate crystaldb
cd D:\document\aiformaterials\crystaldb
$env:CRYSTALDB_MONGO_DB = "crystaldb_api_pilot"
python scripts\build_api_pilot_v01.py
python -m uvicorn crystaldb.api.main:app --reload
```

The package uses the repository `src` layout. If the package is not installed
in the active environment, run:

```powershell
$env:PYTHONPATH = "D:\document\aiformaterials\crystaldb\src"
python -m uvicorn crystaldb.api.main:app --reload
```

Open:

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/api/v1/health

The API is read-only in v0.1.2. The pilot builder rebuilds only
`crystaldb_api_pilot`; it reads source Mongo databases and canonical files
without modifying them.

