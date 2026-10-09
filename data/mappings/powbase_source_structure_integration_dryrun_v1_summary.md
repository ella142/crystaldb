# PowBase Source-Structure Integration Dry-Run v1

Read-only proposal generated from the existing recovery output. No MongoDB
write, source-archive modification, canonical-record modification, COD match,
commit, or push was performed.

## Proposal

- Structures to add: **10**
- Relations to add: **7**
- Entry 106: ambiguous review; two CIFs proposed, no unique relation.
- Entry 157: ambiguous review; one CIF proposed, four incomplete models kept as source evidence only.
- Entry 157 literal source value `51323`: preserved unchanged.
- Entry 116 explicit wavelengths: **1.54056 Å** and **1.54439 Å**.

## Validation

- Gemmi-validated CIFs: **10/10**
- Local duplicate structure IDs: **0**
- Local duplicate relation IDs: **0**
- Proposed orphan relations: **0**
- Provenance errors: **0**
- Read-only Mongo structure collisions: **0**
- Read-only Mongo relation collisions: **0**
- Dry-run passed: **True**

## Proposed Production Counts

| Collection | Current | Delta | Proposed |
|---|---:|---:|---:|
| sources | 6 | +0 | 6 |
| samples | 2932 | +0 | 2932 |
| measurements | 61966 | +0 | 61966 |
| patterns | 3019 | +0 | 3019 |
| structures | 62642 | +10 | 62652 |
| reflection_sets | 58947 | +0 | 58947 |
| relations | 65246 | +7 | 65253 |
| refinements | 0 | +0 | 0 |
| releases | 1 | +0 | 1 |

Entry 116's current canonical pattern/measurement wavelength fields were
blank. The proposal retains the source-labeled Kα1/Kα2 pair without changing
the existing canonical record.
