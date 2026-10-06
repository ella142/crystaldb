# RRUFF Experimental Final Merge v1

This manifest is a merge of frozen results only. No COD search, diffraction rerun, or structure-status re-evaluation was performed.

## Final counts

- final_rows = 1064
- curated_807 = 807
- dif_outside_177 = 177
- rescue_80 = 80
- duplicates = 0

## Frozen source handling

- The 807 curated rows retain the native resolution level/status and the complete original record/group/review JSON.
- The 177 DIF-outside rows retain the frozen resolved, ambiguous, inconclusive, and unlinked statuses and diffraction fields.
- The rescue section contains only the 80 rows selected by the frozen final merge audit as new unique experimental measurements.
- The one rescue-ready calculated-only record is excluded.
- Ambiguous and inconclusive rows retain candidate groups and evidence without selecting a COD ID.

## Validation

- duplicate filename_sample_id = 0
- profile_origin != experimental = 0
- missing source_group = 0
- source-group total = 807 + 177 + 80 = 1064
- validation = PASS
