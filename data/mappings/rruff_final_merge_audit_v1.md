# RRUFF final merge audit v1

This is a pre-merge identity and experimental-origin audit only. It reads existing frozen results and does not search COD, rerun diffraction, or modify the 807 curated set, the 177 DIF-outside final manifest, the 304 rescue final results, v2/v3, MongoDB, or formal CrystalDB.

## Category counts

| source group | total | experimental | already in 807 | already in 177 | new unique experimental |
|---|---:|---:|---:|---:|---:|
| rescue_ready | 24 | 23 | 0 | 0 | 23 |
| ambiguous | 48 | 48 | 0 | 0 | 48 |
| inconclusive | 9 | 9 | 0 | 0 | 9 |

## Final arithmetic

```text
base_807 = 807
dif_outside_177 = 177
rescue_new_unique_experimental = 80
cross_set_duplicates = 0
final_unique_experimental_total = 807 + 177 + 80 - 0 = 1064
validation = PASS
```

The 24 rescue-ready records contain 23 experimental measurements and one calculated-only XY record (`R080124-9`). The 48 ambiguous records and the 9 inconclusive records all have valid experimental XY in the frozen audit. Exact measurement identity uses `filename_sample_id` (with `sample_id` as the fallback identity when no filename is available), not mineral name.

The 9 inconclusive records are the existing 7 `diffraction_inconclusive` samples from `diffraction_needed_67_validation.csv` plus the existing 2 from `high_priority_35_diffraction_validation.csv`. No new structure conclusion is generated here.

## Source files

- `data/mappings/rruff_2120_to_807_audit.csv`
- `data/mappings/rruff_dif_outside_experimental_final_v1.csv`
- `data/mappings/rescue_review_v1/rruff_rescue_ready_24_v1.csv`
- `data/mappings/rescue_review_v1/rruff_ambiguous_48_v1.csv`
- `data/mappings/rescue_review_v1/diffraction_needed_67_validation.csv`
- `data/mappings/rescue_review_v1/high_priority_35_diffraction_validation.csv`
- `data/mappings/rescue_review_v1/rruff_rescue_summary_v1.csv`
- `data/mappings/rescue_review_v1/diffraction_needed_160_xy_audit.csv`
