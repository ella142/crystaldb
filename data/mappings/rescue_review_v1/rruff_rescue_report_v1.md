# RRUFF Rescue/Review Analysis v1

## Scope

This is a read-only analysis of the frozen COD coverage output. It examines
only the 304 records with original status `needs_review_only` or
`reference_structure_only`.

| Population | Count |
|---|---:|
| Target samples | 304 |
| `needs_review_only` | 240 |
| `reference_structure_only` | 64 |
| Existing candidate comparison rows | 1361 |

The original statuses are preserved. No existing mapping, CIF, MongoDB
collection, source module, or diffraction result was modified. No new
diffraction simulation or matching was run.

## Evidence Sources

- `data/mappings/cod_coverage_results_full_v1.json`: original 3013-record
  coverage and candidate-level evidence.
- `data/mappings/cif_index.json`: COD candidate metadata and parse status.
- MongoDB database `rruff`, collections `dif`, `xy_raw`, and
  `xy_processed`: RRUFF sample metadata and crystallographic signatures.
- Existing comparison functions:
  `candidate_compare.compare_candidate`,
  `chemistry.compare_chemistry`, `space_group.compare_space_groups`,
  and `cell_compare.compare_cells`.

The candidate detail output keeps both the original stored evidence and the
reconstructed comparison object. `evidence_count` is the number of positive
signals among sample-name match, reference-name match, chemistry compatible,
space-group equivalent, and broad cell match.

## Failure Patterns

### Sample-level dominant failure reason

These labels are an audit grouping, not a replacement for the original
status.

| Failure pattern | Samples |
|---|---:|
| `multiple_plausible_or_near_equivalent_candidates` | 14 |
| `reference_candidate_chemistry_incompatible` | 49 |
| `space_group_mismatch` | 66 |
| `space_group_unknown_or_conflicting` | 135 |
| `threshold_borderline_cell` | 32 |
| `weak_evidence_across_candidates` | 8 |

### Candidate-level failure pattern

| Candidate pattern | Candidate rows |
|---|---:|
| `multiple_conflicting_evidence_types` | 1010 |
| `reference_structure_only_by_original_rule` | 116 |
| `space_group_mismatch` | 75 |
| `space_group_unknown` | 151 |
| `threshold_borderline_cell` | 9 |

The principal patterns are:

- `space_group_unknown`: name and cell evidence exist, but one or both
  space-group symbols could not be compared by the existing Gemmi-based
  logic.
- `space_group_mismatch`: the candidate cell/name evidence is supportive but
  the resolved space-group operations differ.
- `chemistry_uncertain`: one formula uses notation the current parser does
  not interpret exactly; this is not treated as chemistry incompatibility.
- `chemistry_incompatible`: parsed compositions or element sets disagree.
- `threshold_borderline_cell`: the candidate is inside the historical finder
  window of 5% / 2 degrees but outside the stricter candidate window of
  2% / 1 degree.
- `multiple_conflicting_evidence_types`: more than one major evidence type
  remains unresolved for the candidate.

### Non-mutually-exclusive sample-level signals

| Signal | Samples |
|---|---:|
| `chemistry_incompatible` | 57 |
| `chemistry_uncertain` | 213 |
| `multiple_candidate_rows` | 146 |
| `multiple_plausible_candidates` | 14 |
| `reference_name_without_sample_name` | 11 |
| `space_group_mismatch` | 69 |
| `space_group_unknown` | 138 |
| `threshold_borderline` | 41 |

These signal counts are intentionally non-mutually-exclusive. A single
sample can have chemistry uncertainty, an unknown space group, and multiple
candidate rows at the same time.

## Rescue Categories

| Provisional category | Samples |
|---|---:|
| `diffraction_validation_needed` | 160 |
| `high_priority_rescue` | 36 |
| `low_priority_review` | 56 |
| `not_rescuable_with_current_evidence` | 52 |

These categories are provisional review labels only:

- `high_priority_rescue`: one structurally persuasive candidate, usually
  needing a targeted check of a narrow threshold, formula notation, or the
  sample/reference-name distinction.
- `diffraction_validation_needed`: more than one plausible candidate or an
  unresolved symmetry choice where powder diffraction could discriminate.
- `equivalent_group_candidate`: several candidates are close enough to
  retain as a crystallographic candidate group rather than force one COD ID.
- `low_priority_review`: some evidence exists, but no defensible single
  rescue candidate is isolated.
- `not_rescuable_with_current_evidence`: no candidate has meaningful
  combined support under the available metadata.

## Reference-Structure-Only Review

There are 64 `reference_structure_only` samples. The
following counts describe their existing evidence; they do not promote any
candidate to a sample structure:

| Measure | Samples |
|---|---:|
| Structurally plausible reference candidate | 10 |
| `samples_with_any_cell_outside_candidate_window` | 2 |
| `samples_with_any_space_group_mismatch` | 6 |
| `samples_with_chemistry_incompatible` | 54 |
| `samples_with_chemistry_uncertain` | 10 |
| `samples_with_different_element_set` | 39 |
| `samples_with_possible_substitution_or_ratio_difference` | 20 |
| `samples_with_reference_name_match` | 64 |
| `samples_with_sample_name_match` | 55 |
| `samples_with_structurally_plausible_reference_candidate` | 10 |

A reference candidate is considered structurally plausible here when its
reference name matches, its space group is equivalent, its cell is in the
finder window, and chemistry is compatible or uncertain. A candidate with
chemistry incompatible remains a reference-only warning even when its cell
and symmetry agree. The original reference-only interpretation is retained:
the CIF may describe the bibliography/reference structure rather than the
measured sample.

## Threshold Effects

| Threshold diagnostic | Count |
|---|---:|
| `angle_over_candidate_threshold` | 78 |
| `candidate_window_borderline` | 214 |
| `length_over_candidate_threshold` | 148 |
| `sample_with_threshold_borderline` | 41 |

The analysis does not relax any threshold globally.

## Existing Diffraction Evidence

The output scan checked existing JSON mapping files for the 304 target IDs and
for diffraction-metric fields. It did not recalculate patterns. Details are
stored in `rruff_rescue_failure_counts_v1.json`.

## Representative Examples

- `R050223` (needs_review_only): `high_priority_rescue`, failure=`threshold_borderline_cell`, best COD=`9002827`
- `R050457` (needs_review_only): `high_priority_rescue`, failure=`threshold_borderline_cell`, best COD=`9009272`
- `R050475` (needs_review_only): `high_priority_rescue`, failure=`threshold_borderline_cell`, best COD=`9016161`
- `R050548` (needs_review_only): `high_priority_rescue`, failure=`threshold_borderline_cell`, best COD=`9009702`
- `R040160` (needs_review_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9009511`
- `R060272` (needs_review_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9009488`
- `R060516` (needs_review_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9007587`
- `R061076` (needs_review_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9011956`
- `R040029` (needs_review_only): `low_priority_review`, failure=`space_group_unknown_or_conflicting`, best COD=`9017313`
- `R040178` (needs_review_only): `low_priority_review`, failure=`space_group_unknown_or_conflicting`, best COD=`9004092`
- `R040183` (needs_review_only): `low_priority_review`, failure=`space_group_unknown_or_conflicting`, best COD=`9004092`
- `R050178` (needs_review_only): `low_priority_review`, failure=`space_group_unknown_or_conflicting`, best COD=`9001654`
- `R060246` (needs_review_only): `not_rescuable_with_current_evidence`, failure=`weak_evidence_across_candidates`, best COD=`9010613`
- `R100202` (needs_review_only): `not_rescuable_with_current_evidence`, failure=`weak_evidence_across_candidates`, best COD=`9016424`
- `R100203` (needs_review_only): `not_rescuable_with_current_evidence`, failure=`weak_evidence_across_candidates`, best COD=`9016424`
- `R040131` (reference_structure_only): `not_rescuable_with_current_evidence`, failure=`reference_candidate_chemistry_incompatible`, best COD=`9000609`
- `R050414` (reference_structure_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9000895`
- `R070229` (needs_review_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9001885`
- `R070426` (reference_structure_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9011377`
- `R070427` (reference_structure_only): `diffraction_validation_needed`, failure=`multiple_plausible_or_near_equivalent_candidates`, best COD=`9011896`

## Output Files

- `rruff_rescue_candidates_v1.json`
- `rruff_rescue_summary_v1.csv`
- `rruff_rescue_candidate_details_v1.csv`
- `rruff_rescue_failure_counts_v1.json`
- `rruff_rescue_report_v1.md`
