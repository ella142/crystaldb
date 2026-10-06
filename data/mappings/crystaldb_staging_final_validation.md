# CrystalDB staging final validation

- target database: `crystaldb_staging`
- build status: `PASS`
- API smoke test: `PASS`

## Actual final inputs

- RRUFF: `data/mappings/rruff_experimental_final_v1.csv` and frozen database `crystaldb_rruff_final_v1_staging`
- OPXRD: `data/powder/opxrd/opxrd_cod_pairs.csv` with 845 canonical JSON/CIF pairs
- DARA: `data/powder/dara/*.txt` and `data/multi-phase/dara/*.txt`
- LAB: `data/powder/lab/manifests/lab_xrd_manifest_v1.csv` and canonical TXT files
- COD: `data/mappings/cod_single_crystal_import_manifest_v1.json`, final CIF/HKL pairs, and `data/mappings/cif_index.json`

## Sources

- RRUFF: samples=1062, measurements=1064, patterns=1064, structures linked=2458
- OPXRD: samples=845, measurements=845, patterns=845
- DARA: samples=30, measurements=50, patterns=50
- LAB: samples=951, measurements=1016, patterns=1016
- COD: structures=58947, reflection_sets=58947 (global deduplicated structures=62642)

## Global

- samples=2888
- measurements=61922
- patterns=2975
- structures=62642
- reflection_sets=58947
- relations=65246
- refinements=0
- releases=1

## Integrity

- duplicate IDs=0
- broken pattern -> measurement=0
- broken measurement -> sample=0
- broken relation -> pattern=0
- broken relation -> structure=0
- missing referenced CIF=0
- missing referenced HKL=0
- XY length mismatch=0
- empty XY=0

## Cleanup audit retained

- KEEP=10833
- ARCHIVE=10
- SAFE_TO_DELETE_AFTER_PROMOTION=199
- DO_NOT_KNOW=0

- READY_FOR_FINAL_PROMOTION=YES
