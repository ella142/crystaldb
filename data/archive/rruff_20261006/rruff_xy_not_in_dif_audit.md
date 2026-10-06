# RRUFF XY Outside DIF Audit

Read-only audit of `rruff.dif`, `rruff.xy_raw`, and `rruff.xy_processed`.
No MongoDB source collection, pipeline output, curated dataset, v2/v3, or formal CrystalDB data was modified.

## Summary

unique measurements outside DIF = 259
unique sample_ids outside DIF = 257
raw only = 90
processed only = 41
raw + processed = 128
experimental = 177
calculated = 72
uncertain = 10

## Method

- The DIF universe is the set of unique `sample_id` values read from `rruff.dif`.
- XY records are scanned from both collections and merged by `filename_sample_id`.
- A merged measurement is included when its `sample_id` is absent from the DIF universe.
- For shared measurements, raw metadata is preferred for shared fields; processed metadata is used when raw is absent.
- `profile_origin` uses only `metadata["DIFFRACTION SAMPLE DESCRIPTION"]`: calculated/simulated/computed wording is `calculated`; powder wording without those terms is `experimental`; all other descriptions are `uncertain`.
- `raw_point_count` and `processed_point_count` come from the source document `xrd.point_count`.
