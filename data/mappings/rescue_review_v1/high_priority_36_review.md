# High-Priority Rescue Review: 36 RRUFF Samples

## Scope

This review is restricted to the 36 samples already labeled `high_priority_rescue` in `rruff_rescue_summary_v1.csv`.
It uses the existing rescue CSV files and local CIF files only.
No COD search, CIF download, diffraction matching, MongoDB write, or old mapping modification was performed.

The current structure test is:

- name support from the sample or reference name;
- chemistry clearly compatible, or explicitly retained for solid-solution/substitution review;
- equivalent space group;
- max cell-length difference <= 2%;
- max cell-angle difference <= 1°.

For `structurally_ready_for_rescue`, chemistry must be explicitly compatible. A null result from the existing chemistry comparator is not silently treated as compatible; only the exact formula equivalences listed in the CSV were manually promoted to `compatible`.

## Summary

| Metric | Samples |
|---|---:|
| 36 total | 36 |
| structurally_ready_for_rescue | 1 |
| multiple_valid_candidates | 0 |
| diffraction_validation_needed | 35 |
| not_rescuable | 0 |
| solid_solution_or_substitution_review | 23 |

The `solid_solution_or_substitution_review` count is a sample count. It includes samples with at least one candidate whose chemistry was not an exact composition match and therefore still needs solid-solution/substitution or manual chemistry review. It is a review flag, not a claim that every such sample has a confirmed solid solution.

The legacy comparator returned null for grouped or otherwise complex formulas. Fourteen exact formula equivalences were manually checked for this 36-sample scope and recorded in the CSV `chemistry_evidence` column; no general chemistry search or new candidate retrieval was performed.

## Sample Results

| sample_id | candidate_cod_id(s) | passing | final_status | chemistry review | reason |
|---|---|---:|---|---|---|
| R040166 | 9009514 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R050093 | 9005624 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R050223 | 9002827 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R050457 | 9009272 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R050475 | 9016161 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R050548 | 9009702 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060018 | 9008253 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060168 | 9009858 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060254 | 9004913 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060393 | 9004106 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060456 | 9004736 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060624 | 9011241 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060683 | 9017577 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060834 | 9004787 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R060904 | 9000949 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R070007 | 9017145 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R070093 | 9008075 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R070204 | 9000000 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R070607 | 9008134 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R070615 | 9012097 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R070713 | 9000944 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R080044 | 9000221 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R080097 | 9000212 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R080124 | 9004354 | 1 | `structurally_ready_for_rescue` | no | 1 candidate passes all current structure conditions. |
| R090038 | 9011792 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R090052 | 9004629 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R100004 | 9014374 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R110194 | 9004389 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R120112 | 9004394, 9014738 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R120155 | 9015768 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R130054 | 9009590 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R130121 | 9012868 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R130530 | 9012637 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R140328 | 9000944 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R140558 | 9007451 | 0 | `diffraction_validation_needed` | no | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |
| R141122 | 9017064 | 0 | `diffraction_validation_needed` | yes | No strict pass. At least one candidate retains name, equivalent-SG, broad-cell, and usable local-CIF support; experimental diffraction or chemistry review is needed. |

## Candidate-Level Notes

| sample_id | COD ID | name | chemistry | SG | cell | check |
|---|---|---|---|---|---|---|
| R040166 | 9009514 | reference_name | solid_solution_or_substitution_review | equivalent | pass | chemistry_review |
| R050093 | 9005624 | reference_name | solid_solution_or_substitution_review | equivalent | pass | chemistry_review |
| R050223 | 9002827 | sample_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R050457 | 9009272 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R050475 | 9016161 | sample_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R050548 | 9009702 | sample_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R060018 | 9008253 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R060168 | 9009858 | sample_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R060254 | 9004913 | sample_and_reference_name | compatible | equivalent | exceeds_angle_1deg | cell_threshold_failure |
| R060393 | 9004106 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_angle_1deg | chemistry_review_and_cell_threshold |
| R060456 | 9004736 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R060624 | 9011241 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R060683 | 9017577 | sample_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R060834 | 9004787 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_angle_1deg | chemistry_review_and_cell_threshold |
| R060904 | 9000949 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R070007 | 9017145 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct_and_angle_1deg | chemistry_review_and_cell_threshold |
| R070093 | 9008075 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R070204 | 9000000 | sample_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R070607 | 9008134 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R070615 | 9012097 | reference_name | solid_solution_or_substitution_review | equivalent | pass | chemistry_review |
| R070713 | 9000944 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_angle_1deg | chemistry_review_and_cell_threshold |
| R080044 | 9000221 | sample_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R080097 | 9000212 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R080124 | 9004354 | reference_name | compatible | equivalent | pass | passes_current_structure_conditions |
| R090038 | 9011792 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R090052 | 9004629 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R100004 | 9014374 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R110194 | 9004389 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R120112 | 9004394 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R120112 | 9014738 | sample_and_reference_name | solid_solution_or_substitution_review | mismatch | pass | space_group_mismatch |
| R120155 | 9015768 | sample_and_reference_name | compatible | equivalent | exceeds_length_2pct | cell_threshold_failure |
| R130054 | 9009590 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct | chemistry_review_and_cell_threshold |
| R130121 | 9012868 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_length_2pct_and_angle_1deg | chemistry_review_and_cell_threshold |
| R130530 | 9012637 | reference_name | solid_solution_or_substitution_review | equivalent | pass | chemistry_review |
| R140328 | 9000944 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_angle_1deg | chemistry_review_and_cell_threshold |
| R140558 | 9007451 | sample_and_reference_name | compatible | equivalent | exceeds_angle_1deg | cell_threshold_failure |
| R141122 | 9017064 | sample_and_reference_name | solid_solution_or_substitution_review | equivalent | exceeds_angle_1deg | chemistry_review_and_cell_threshold |

## Interpretation

`structurally_ready_for_rescue` only means that the existing structure evidence satisfies the stated checks; it does not promote a final record-level resolution or modify the original 807-profile dataset.

The CSV contains one row per existing sample-CIF candidate. `candidate_count_passing` is repeated for all rows belonging to the same sample and counts only strict passes with explicit chemistry compatibility.

Generated at 2026-10-05T10:46:58.678777+00:00.
