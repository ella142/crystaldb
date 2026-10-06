# High-Priority Rescue Diffraction Validation: 35 RRUFF Samples

## Scope

This audit is restricted to the 35 samples marked `diffraction_validation_needed` in `high_priority_36_review.csv`.
It uses existing raw/processed RRUFF XY, existing DIF records, and the already downloaded local CIF candidates only.
No COD search, CIF download, MongoDB write, 807-data modification, v2/v3 modification, or formal CrystalDB update was performed.

## Existing Pipeline Reused

The diffraction functions and fixed settings were loaded from the function definitions in `scripts/annotate_rruff_group_diffraction_v1.py`; the historical group batch body was not executed.

- theoretical reflections: CIF -> Gemmi structure factors
- experimental peaks: smoothing, local maxima, intensity and separation filters
- matching: one-to-one assignment
- zero shift: weighted median from the initial window
- final matching window: 0.15 degrees
- metrics: matched count, matched fraction, median/weighted/max residual, residual slope, zero shift
- candidate separability: existing theoretical peak nearest-difference calculation

The experimental XY allow-list is the same frozen clean allow-list used by `build_rruff_experimental_resolution_v1.py`. Profiles described as `Single crystal, powder profile is calculated` are not treated as experimental XY.

## Status Rule

For an evaluable candidate, `diffraction_compatible` means that all three existing core metrics are inside the existing same-radiation positive-reference P95 envelope: matched fraction, median absolute residual, and weighted mean absolute residual. This reproduces the existing `core_three_inside_p95` annotation logic. The envelope is descriptive calibration evidence, not a new scientific threshold.

- one compatible candidate: `diffraction_supported_rescue`
- more than one compatible candidate: `multiple_diffraction_compatible_candidates`
- metrics obtained but no compatible candidate and not all zero-match: `diffraction_inconclusive`
- all evaluable candidates have zero matches: `diffraction_incompatible`
- no clean experimental XY: `no_diffraction_available`

These statuses are audit labels only. They do not create a final record and do not alter the curated 807, v2/v3, MongoDB, or formal CrystalDB.

## Summary

| Metric | Samples |
|---|---:|
| 35 total | 35 |
| with_usable_experimental_xy | 13 |
| no_diffraction_available | 22 |
| diffraction_supported_rescue | 11 |
| multiple_diffraction_compatible_candidates | 0 |
| diffraction_inconclusive | 2 |
| diffraction_incompatible | 0 |

## Sample Results

| sample_id | candidate COD IDs | XY | evaluable | compatible | final status | reason |
|---|---|---|---:|---:|---|---|
| R040166 | 9009514 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050093 | 9005624 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050223 | 9002827 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R050457 | 9009272 | rruff.xy_raw | 1 | 0 | `diffraction_inconclusive` | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R050475 | 9016161 | rruff.xy_raw | 1 | 0 | `diffraction_inconclusive` | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R050548 | 9009702 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060018 | 9008253 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R060168 | 9009858 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060254 | 9004913 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R060393 | 9004106 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060456 | 9004736 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R060624 | 9011241 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R060683 | 9017577 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060834 | 9004787 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R060904 | 9000949 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R070007 | 9017145 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R070093 | 9008075 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R070204 | 9000000 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R070607 | 9008134 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R070615 | 9012097 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R070713 | 9000944 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R080044 | 9000221 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R080097 | 9000212 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R090038 | 9011792 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R090052 | 9004629 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R100004 | 9014374 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R110194 | 9004389 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R120112 | 9004394, 9014738 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R120155 | 9015768 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R130054 | 9009590 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R130121 | 9012868 | rruff.xy_raw | 1 | 1 | `diffraction_supported_rescue` | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R130530 | 9012637 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R140328 | 9000944 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R140558 | 9007451 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |
| R141122 | 9017064 | none | 0 | 0 | `no_diffraction_available` | XY exists but the profile description is calculated rather than a clean experimental powder profile. |

## Candidate Metrics

| sample_id | COD ID | matched | median residual | weighted residual | max residual | slope | zero shift | core P95 | candidate status |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| R040166 | 9009514 | 17 | 0.024878736118232325 | 0.03293851906119936 | 0.14096892659141957 | -0.0010182607451958224 | 0.028130883182051036 | true | `diffraction_compatible` |
| R050093 | 9005624 | 19 | 0.01626883725089101 | 0.016576627540929194 | 0.0948120151498415 | 0.0009584508491008839 | 0.040786909520765136 | true | `diffraction_compatible` |
| R050223 | 9002827 |  |  |  |  |  |  |  | `not_evaluated` |
| R050457 | 9009272 | 9 | 0.03961781592023783 | 0.022853583717887403 | 0.14097560502106177 | 0.0017320338779425238 | -0.07869499116341849 | false | `diffraction_inconclusive` |
| R050475 | 9016161 | 12 | 0.07416845744068823 | 0.03264255396952648 | 0.1458959364888699 | -0.0019479417857121413 | 0.0706136873371781 | false | `diffraction_inconclusive` |
| R050548 | 9009702 | 20 | 0.02099520337722538 | 0.021278251451717793 | 0.106055690697346 | 0.00029815392019784544 | 0.04783843027355772 | true | `diffraction_compatible` |
| R060018 | 9008253 |  |  |  |  |  |  |  | `not_evaluated` |
| R060168 | 9009858 | 20 | 0.04112754167507049 | 0.027491358841830286 | 0.1038545949996319 | 0.0008416797636931514 | 0.03474451572724124 | true | `diffraction_compatible` |
| R060254 | 9004913 |  |  |  |  |  |  |  | `not_evaluated` |
| R060393 | 9004106 | 15 | 0.047451773028548416 | 0.042965756485983254 | 0.14452411467592796 | -4.40718836142103e-05 | 0.003405937666300929 | true | `diffraction_compatible` |
| R060456 | 9004736 |  |  |  |  |  |  |  | `not_evaluated` |
| R060624 | 9011241 |  |  |  |  |  |  |  | `not_evaluated` |
| R060683 | 9017577 | 18 | 0.034310458970846724 | 0.035585665482228857 | 0.12101397974872441 | 0.0008503390938071238 | 0.13628749415807206 | true | `diffraction_compatible` |
| R060834 | 9004787 |  |  |  |  |  |  |  | `not_evaluated` |
| R060904 | 9000949 |  |  |  |  |  |  |  | `not_evaluated` |
| R070007 | 9017145 |  |  |  |  |  |  |  | `not_evaluated` |
| R070093 | 9008075 | 20 | 0.0286919137830548 | 0.03193947815021834 | 0.10735070250216694 | -0.0013818218903897724 | 0.027697064590000764 | true | `diffraction_compatible` |
| R070204 | 9000000 | 15 | 0.04364059296757716 | 0.030068384615122346 | 0.14328563722118304 | 0.0009176213999573023 | 0.03397708131456767 | true | `diffraction_compatible` |
| R070607 | 9008134 |  |  |  |  |  |  |  | `not_evaluated` |
| R070615 | 9012097 |  |  |  |  |  |  |  | `not_evaluated` |
| R070713 | 9000944 | 19 | 0.03335163431331267 | 0.04055579038702085 | 0.11680241856048923 | 0.0005421873857637674 | -0.001834930094714693 | true | `diffraction_compatible` |
| R080044 | 9000221 | 17 | 0.04789087761654187 | 0.0408459756551072 | 0.1246728740123757 | -0.0007460746805950752 | -0.01701846202095325 | true | `diffraction_compatible` |
| R080097 | 9000212 |  |  |  |  |  |  |  | `not_evaluated` |
| R090038 | 9011792 |  |  |  |  |  |  |  | `not_evaluated` |
| R090052 | 9004629 |  |  |  |  |  |  |  | `not_evaluated` |
| R100004 | 9014374 |  |  |  |  |  |  |  | `not_evaluated` |
| R110194 | 9004389 |  |  |  |  |  |  |  | `not_evaluated` |
| R120112 | 9004394 |  |  |  |  |  |  |  | `not_evaluated` |
| R120112 | 9014738 |  |  |  |  |  |  |  | `not_evaluated` |
| R120155 | 9015768 |  |  |  |  |  |  |  | `not_evaluated` |
| R130054 | 9009590 |  |  |  |  |  |  |  | `not_evaluated` |
| R130121 | 9012868 | 16 | 0.025161490442147993 | 0.03368167151715316 | 0.08987751303691738 | 0.0005109144930768114 | 0.058577248297794426 | true | `diffraction_compatible` |
| R130530 | 9012637 |  |  |  |  |  |  |  | `not_evaluated` |
| R140328 | 9000944 |  |  |  |  |  |  |  | `not_evaluated` |
| R140558 | 9007451 |  |  |  |  |  |  |  | `not_evaluated` |
| R141122 | 9017064 |  |  |  |  |  |  |  | `not_evaluated` |

## Provenance

- Candidate review input: `data/mappings/rescue_review_v1/high_priority_36_review.csv`
- Calibration input: `data/mappings/rruff_diffraction_calibration_v1.json`
- Frozen diffraction engine: `scripts/annotate_rruff_group_diffraction_v1.py`
- Experimental data: read-only `rruff.xy_raw`, then `rruff.xy_processed` fallback
- DIF data: read-only `rruff.dif`

Generated at 2026-10-05T11:11:40.851378+00:00.
