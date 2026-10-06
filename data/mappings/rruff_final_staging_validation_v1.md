# RRUFF Final Staging Validation v1

- Target database: `crystaldb_rruff_final_v1_staging`
- Frozen input: `data/mappings/rruff_experimental_final_v1.csv`
- Validation: **PASS**
- API smoke test: **PASS**

## Database counts

| Collection | Count |
|---|---:|
| sources | 2 |
| samples | 1062 |
| measurements | 1064 |
| patterns | 1064 |
| structures | 2988 |
| relations | 5454 |
| releases | 1 |

Source groups: `curated_807 = 807`, `dif_outside_177 = 177`, `rescue_80 = 80`.

## Required checks

- patterns = 1064: **PASS**
- duplicate pattern_id = 0
- duplicate measurement_id = 0
- one filename_sample_id per measurement: **PASS**
- missing experimental XY = 0
- broken structure relation = 0
- missing referenced CIF = 0
- all patterns experimental: **PASS**
- resolved relations unique: **PASS**
- unlinked relations empty: **PASS**
- ambiguous/inconclusive candidate relations complete: **PASS**

## API smoke test

All requested v0.1.2 endpoints returned HTTP 200 against `crystaldb_rruff_final_v1_staging`: health, stats, patterns, one resolved pattern, one ambiguous pattern, one inconclusive pattern, one unlinked pattern, XY, structure, and CIF.

Smoke records: resolved `RRUFF_PAT_R040001_1`, ambiguous `RRUFF_PAT_R040014_1`, inconclusive `RRUFF_PAT_D120001_1`, unlinked `RRUFF_PAT_D120003_1`, structure `STR_COD_9000239`.

## Isolation

The formal `crystaldb` database was not written. Its post-task read-only snapshot is recorded in the JSON report. No COD search, diffraction rerun, CIF promotion, or `cif_index.json` rebuild was performed.
