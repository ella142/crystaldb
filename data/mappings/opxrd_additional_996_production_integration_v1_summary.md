# OPXRD Additional 996 Production Integration v1

- Run timestamp UTC: 2026-10-07T16:53:43.249429+00:00
- Production database: `crystaldb`
- Authoritative validation CSV: `D:\document\aiformaterials\crystaldb\data\mappings\opxrd_source_labeled_canonical_validation_v1.csv`
- Production backup: `D:\document\aiformaterials\crystaldb\data\archive\opxrd_additional_996_pre_integration_20261008_003953`
- Source database: `opxrd.patterns`
- Source group: `opxrd_source_labeled_validated_996`
- Phase method: `opxrd_effective_phase_count_v1`

## Write Scope

- PASS records integrated: 996
- USC unresolved records integrated: 0
- CIF matching: not performed
- Structures and relations added: 0

## Counts

- Total CrystalDB patterns: 4090
- OPXRD production patterns: 1841
- OPXRD single_phase: 1069
- OPXRD multi_phase: 772
- OPXRD unknown: 0
- New 996 orphan references: 0
- Existing out-of-scope orphan sample size: 20

## Write Result

- First pass: `{"measurements": {"matched": 996, "modified": 0, "upserted": 0}, "patterns": {"matched": 996, "modified": 0, "upserted": 0}, "samples": {"matched": 996, "modified": 0, "upserted": 0}}`
- Idempotence pass: `{"measurements": {"matched": 996, "modified": 0, "upserted": 0}, "patterns": {"matched": 996, "modified": 0, "upserted": 0}, "samples": {"matched": 996, "modified": 0, "upserted": 0}}`

## Verification

- total_pattern_count: True
- opxrd_pattern_count: True
- phase_distribution: True
- added_pattern_count: True
- failed_usc_absent: True
- record_payloads_preserved: True
- no_duplicate_ids: True
- no_orphan_records: True
- collection_deltas: True
- idempotence: True

## Collection Counts

- Before: `{"measurements": 63037, "patterns": 4090, "refinements": 0, "reflection_sets": 58947, "relations": 65253, "releases": 1, "samples": 4003, "sources": 6, "structures": 62652}`
- After: `{"measurements": 63037, "patterns": 4090, "refinements": 0, "reflection_sets": 58947, "relations": 65253, "releases": 1, "samples": 4003, "sources": 6, "structures": 62652}`

No XY data, source metadata, structures, relations, website, manuscript, release files, or Git history were modified outside the requested 996 sample/measurement/pattern records. Existing out-of-scope orphan references were not modified.
