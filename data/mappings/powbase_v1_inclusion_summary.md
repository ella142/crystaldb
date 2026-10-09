# PowBase CrystalDB v1 Inclusion Summary

This manifest is a decision artifact only. It does not write MongoDB, modify production CrystalDB, modify PowBase source files, or perform canonical ingestion.

## Source and Scope

- Input: complete 170-record conservative PowBase review.
- Review CSV: `D:\document\aiformaterials\crystaldb\data\archive\powbase_20261006\review\powbase_review_records_v1.csv`
- CrystalDB v1 scope: explicit X-ray records only.
- All neutron records remain preserved and receive `exclude_neutron_v1`.
- `phase_character` remains `unknown` for every entry.

## Modality × Review Status

| Modality | Verified | Verified conflicts | Conditional | Conditional conflicts | Unresolved | Unresolved conflicts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| xray | 45 | 1 | 76 | 1 | 30 | 0 |
| neutron | 3 | 0 | 0 | 0 | 16 | 0 |

## Final Decisions

| Decision | Count |
| --- | ---: |
| `include_verified` | 44 |
| `review_conditional` | 75 |
| `exclude_neutron_v1` | 19 |
| `exclude_unresolved` | 30 |
| `exclude_metadata_conflict` | 2 |
| `exclude_other` | 0 |

The 44 `include_verified` records are exactly the explicit X-ray, verified, conflict-free profiles. The 75 `review_conditional` records remain outside the initial release until their recorded rule is formally adopted or individually reviewed. The two metadata-conflict records, 86 and 169b, are excluded from inclusion regardless of profile parse status.

## Conditional Policy

- Fixed-width terminal-zero candidates remain conditional. No intensity values are silently removed.
- Entry 137 remains `review_conditional` until the terminal-padding policy is formally adopted as a source-format rule.
- UXD entry 15 and source-suffix entry 74 are reproducible conditional formats, but are not promoted to `include_verified` by this manifest.
- Entry 36 remains conditional because one member is parseable and a second neutron member remains unresolved.

## Previous 46-Record Queue

The previously reported “Potential CrystalDB v1 review candidates: 46” was not the final X-ray inclusion set. It was an audit review queue calculated as: verified status, one member, audit-usable source, no metadata conflict, and no radiation conflict. That earlier rule did not require X-ray modality, so it included neutron entries 115 and 120. It excluded 102 because of a radiation evidence conflict and 169b because of a metadata conflict. Applying the explicit X-ray-only v1 scope yields 44 `include_verified` records.

## Integrity Checks

- Input records: `170`
- Output records: `170`
- Unique entry IDs: `170`
- Decision total: `170`
- Every entry receives exactly one v1 decision.

No canonical ingestion was performed.
