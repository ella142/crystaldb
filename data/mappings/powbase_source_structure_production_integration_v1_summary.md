# PowBase Source-Structure Production Integration v1

Production integration was applied from the completed authoritative dry-run. No new PowBase patterns, COD matches, release changes, or source-archive changes were made.

## Write Set

- Structures inserted: **10**
- Relations inserted: **7**
- Entry-116 pattern wavelength update: **1**
- Entry-116 measurement wavelength update: **1**
- Entry 106: ambiguous/review; no relation added.
- Entry 157: ambiguous/review; four incomplete models were not registered.
- Entry 157 literal source value `51323`: preserved.

## Counts

| Collection | Before | After | Delta |
|---|---:|---:|---:|
| sources | 6 | 6 | +0 |
| samples | 2932 | 2932 | +0 |
| measurements | 61966 | 61966 | +0 |
| patterns | 3019 | 3019 | +0 |
| structures | 62642 | 62652 | +10 |
| reflection_sets | 58947 | 58947 | +0 |
| relations | 65246 | 65253 | +7 |
| refinements | 0 | 0 | +0 |
| releases | 1 | 1 | +0 |

## Validation

- Backup complete: **True**
- Structures increased by exactly 10: **True**
- Relations increased by exactly 7: **True**
- Pattern count unchanged: **True**
- Duplicate IDs: **0**
- Orphan relations: **0**
- Gemmi CIF parses: **10/10**
- Ambiguous relation guard: **True**
- Entry-157 literal preserved: **True**
- Four incomplete entry-157 models absent: **True**
- Idempotence preflight: **True**
- Integration passed: **True**

Backup: `D:\document\aiformaterials\crystaldb\backups\powbase_source_structure_pre_integration_20261007_181825`
