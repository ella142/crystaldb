# PowBase MongoDB Staging Validation v1

This report stages only the 44 `include_verified` PowBase X-ray records into the isolated MongoDB database `crystaldb_powbase_staging_20261007`. Production `crystaldb` was not written.

## Database And Collections

- MongoDB database: `crystaldb_powbase_staging_20261007`
- Canonical collections: `sources`, `samples`, `measurements`, `patterns`, and `relations`.
- XY storage: embedded in `patterns.xrd` and `patterns.data`, matching the existing CrystalDB API contract. No new XY collection was invented.

| Collection | Count |
| --- | ---: |
| sources | 1 |
| samples | 44 |
| measurements | 44 |
| patterns | 44 |
| relations | 0 |
| pattern documents with XY | 44 |

## Validation

- Ready for production integration: `true`
- Validation errors: 0
- Missing required-field/reference checks: 0
- Orphan records: 0
- Duplicate primary IDs: 0
- All IDs trace to selected PowBase entries: `true`
- Known wavelengths: 6
- Unknown wavelengths: 38
- Source distribution: `{"POWBASE": 44}`
- Phase-character distribution: `{"unknown": 44}`

## Duplicate Review

Possible duplicates were preserved and not merged.
- PowBase entries 66/67/68 share a normalized source label.
- PowBase entry 10 has possible existing LAB label matches `Al2O3-0.5` and `Al2O3-20`.
- PowBase entry 159 has a possible existing LAB label match `CaCuO2`.
- Full duplicate evidence: `{"same_source_label_groups": [{"normalized_label": "alphakalf4", "entry_ids": ["66", "67", "68"]}], "existing_local_matches": [{"powbase_entry_id": "10", "matches": [{"source": "LAB", "path": "D:\\document\\aiformaterials\\crystaldb\\data\\powder\\lab\\manifests\\lab_xrd_manifest_v1.csv", "source_sample_label": "Al2O3-0.5", "nominal_element_ratio": "Al2O3"}, {"source": "LAB", "path": "D:\\document\\aiformaterials\\crystaldb\\data\\powder\\lab\\manifests\\lab_xrd_manifest_v1.csv", "source_sample_label": "Al2O3-20", "nominal_element_ratio": "Al2O3"}]}, {"powbase_entry_id": "159", "matches": [{"source": "LAB", "path": "D:\\document\\aiformaterials\\crystaldb\\data\\powder\\lab\\manifests\\lab_xrd_manifest_v1.csv", "source_sample_label": "CaCuO2", "nominal_element_ratio": "CaCuO2"}]}], "deduplicated": false, "notes": ["Same-label and existing-local matches are review candidates only.", "No record was removed or merged by material name, formula, or phase."]}`

## Scientific Constraints

- `source=POWBASE` and `data_origin=experimental` were validated after insertion.
- All staged records are X-ray source records with `modality=powder_xrd`.
- `phase_character=unknown` for all records.
- No formulas were inferred and no structure links or relations were created.
- Numeric arrays were revalidated after Mongo insertion for equal lengths, point counts, finite values, and strictly increasing 2theta.

No production copy or merge was performed. No source archive was modified, and no Git staging, commit, or push was performed.
