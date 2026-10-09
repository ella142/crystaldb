# PowBase Production Integration v1

Integrated exactly the 44 validated PowBase X-ray records into production `crystaldb`. Conditional, unresolved, neutron, and metadata-conflict records were excluded.

## Backup

- Backup path: `D:\document\aiformaterials\crystaldb\backups\powbase_production_pre_integration_20261007_125659`
- Backup timestamp (UTC): `2026-10-07T04:57:02.224567+00:00`
- Backup complete: `true`
- Backup errors: 0

## Production Counts

| Collection | Before | Inserted | After | Delta |
| --- | ---: | ---: | ---: | ---: |
| sources | 5 | 1 | 6 | 1 |
| samples | 2888 | 44 | 2932 | 44 |
| measurements | 61922 | 44 | 61966 | 44 |
| patterns | 2975 | 44 | 3019 | 44 |
| structures | 62642 | 0 | 62642 | 0 |
| reflection_sets | 58947 | 0 | 58947 | 0 |
| relations | 65246 | 0 | 65246 | 0 |
| refinements | 0 | 0 | 0 | 0 |
| releases | 1 | 0 | 1 | 0 |

## Post-Write Validation

- PowBase source records: 1
- PowBase samples: 44
- PowBase measurements: 44
- PowBase patterns: 44
- Embedded XY payloads: 44
- PowBase relations: 0
- Known wavelengths: 6
- Unknown wavelengths: 38
- `phase_character=unknown`: 44
- Pattern source `POWBASE`: 44
- Orphans: 0
- Duplicate IDs: 0
- Validation errors: 0
- Integration passed: `true`

## Provenance And Review Signals

- PowBase entry IDs, raw index metadata, archive/member names and hashes, parsing method, and v1 decision remain in pattern provenance.
- `phase_character` remains `unknown`; no formulas, CIF links, structure records, or relations were added.
- Entries 66/67/68 and the LAB label matches for entries 10 and 159 were preserved as review signals; no label-based deduplication was performed.

## Included Entry IDs

4, 8, 10, 12, 13, 19, 38, 43, 45, 46, 58, 60, 66, 67, 68, 69, 71, 72, 73, 75, 76, 77, 78, 79, 80, 106, 111, 113, 116, 117, 124, 125, 126, 127, 128, 133, 140, 149, 157, 159, 160, 162, 163, 164

Archive hash verification: 170 archives checked; all byte-identical to inventory = `true`.

No conditional records were added. No COD/CIF matching, public release update, manuscript update, Git staging, commit, or push was performed.
