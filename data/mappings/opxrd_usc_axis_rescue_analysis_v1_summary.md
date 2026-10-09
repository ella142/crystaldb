# USC OPXRD Axis Rescue Analysis v1

- Scope: the 338 USC records marked `FAIL` in `opxrd_source_labeled_canonical_validation_v1.csv`.
- The 996 records already validated were not reprocessed.
- MongoDB writes: none.
- Sorting, point deletion, interpolation, resampling, and intensity edits: none.

## Classification

| classification | count |
|---|---:|
| safely_recoverable_by_USC_rule | 0 |
| still_unresolved | 338 |

No deterministic USC repair rule was found. The anomaly is structurally consistent with a block concatenation, but the retained source metadata do not identify the inserted block as invalid or specify which duplicate endpoint value is authoritative. A repair would require an undocumented point-selection rule, so no repair was applied.

## Axis Findings

- All 338 records use `xrd.two_theta` with 3,050 x values and 3,050 paired intensity values.
- Every record has exactly one backward step at zero-based diff index `1374`, between points `1374` and `1375`: `66.0851466 -> 64.98220287`, delta `-1.102943730000007`.
- Every record has exactly one duplicate step at zero-based diff index `1511`, between points `1511` and `1512`: `69.70313028 -> 69.70313028`, delta `0.0`.
- The interval from points `1375` through `1511` contains 137 points sampled at approximately `0.03471270154412309`, while the surrounding grid is approximately `0.026260565`.
- The first inserted-block intensity, at point `1375`, is `0.0` in all 338 records.
- The two intensities paired with the duplicated endpoint differ in 338 of 338 records, so the endpoint cannot be resolved by retaining a value based on x alone.
- Relative transition positions are constant: backward step `1374 / 3049 = 0.450639553952`; duplicate step `1511 / 3049 = 0.495572318793`.

### Axis precision variants

- Reference-grid exact: 333.
- Eight-decimal rounding variant: 5.
- The five rounding-variant records differ from `pattern_0` by at most `5.000001124244591e-08` in the axis values, but have the same anomaly indices and anomaly values.
- Rounding-variant IDs: OPXRD/USC/pattern_110.json, OPXRD/USC/pattern_147.json, OPXRD/USC/pattern_20.json, OPXRD/USC/pattern_48.json, OPXRD/USC/pattern_98.json.

## USC Source Formatting and Metadata

- The source root contains 338 files, all with extension `.json`; no USC `.csv`, `.txt`, `.dat`, or `.xy` source files were present at the retained source root.
- The retained JSON top-level fields are `intensities, label, metadata, two_theta_values`. No retained header, scan start/stop/step, block, or boundary field was found.
- All 338 Mongo source records report `metadata.original_file_format = csv (.csv)`, institution `University of Southern California`, contributor `Prof. Andrea Hodge`, `xrdpattern_version = 0.9.7`, and import parser version `1.0.0`.
- The public opXRD paper describes the USC contribution as a highly similar set of CuNi and CuAl alloy patterns, but does not document this axis-block convention: https://arxiv.org/abs/2503.05577

## Phase Counts

### 996 already validated

| effective_phase_count | phase_character | count |
|---:|---|---:|
| 1 | single_phase | 224 |
| 2 | multi_phase | 770 |
| 3 | multi_phase | 1 |
| 4 | multi_phase | 1 |
| **total** |  | **996** |

Passed records: single_phase `224`, multi_phase `772`, unknown `0`.

### 338 failed USC records

| effective_phase_count | phase_character | count |
|---:|---|---:|
| 2 | multi_phase | 338 |
| **total** |  | **338** |

Failed records: single_phase `0`, multi_phase `338`, unknown `0`.

## Candidate Rule Verification

Because no deterministic USC rule was found, no candidate transform was executed. XY pairing, repaired point count, and strict increase after repair are therefore `not_applicable`. The analysis made no changes to any intensity values.

Per-record evidence is in `opxrd_usc_axis_rescue_analysis_v1.csv`.
