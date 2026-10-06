# RRUFF Rescue/Review Final v1

This is an organization-only manifest. It reads existing rescue/review outputs and
does not search COD, download CIF files, rerun diffraction, recalculate metrics, or
modify historical CrystalDB data.

## Final closure

| category | sample count |
|---|---:|
| `rescue_ready` | 24 |
| `ambiguous` | 48 |
| `inconclusive` | 9 |
| `no_experimental_validation` | 115 |
| `low_priority_review` | 56 |
| `not_rescuable` | 52 |
| **total** | **304** |

The six categories are checked as a disjoint union of the 304 unique RRUFF sample
IDs. `sum(category counts) = 304` and `union size = 304`.

`validation = PASS`

## Deliverables

- `rruff_rescue_ready_24_v1.csv`: 24 rows, consisting of the
  original 12 rescue-ready rows plus 12 existing `diffraction_supported_rescue`
  rows from the 67-sample validation output.
- `rruff_ambiguous_48_v1.csv`: 48 rows, one row per sample.
  No candidate is selected as a representative; `candidate_cod_ids`,
  `candidate_metrics_json`, and `candidate_evidence_json` retain all compatible
  candidates and their existing values.

The ready CSV preserves the original structure-only row with diffraction fields as
`null`. It also preserves the existing solid-solution/substitution status where
present. For ambiguous samples, scalar diffraction metric columns remain `null`
because selecting one candidate would reinterpret the result; all candidate-level
metrics are retained in `candidate_metrics_json`.

## Gemmi compatibility record

The initial diffraction run recorded 6 candidate-level runtime errors associated
with Gemmi 0.7.5 API compatibility:

- COD `1011221`: samples `R050035`, `R050056`, `R050233`, `R050489`, `R060532`
- COD `9017229`: sample `R060060`

The existing validation output was subsequently read after applying an in-memory
runtime compatibility wrapper for the frozen engine. The wrapper only supplied the
required explicit space-group setting/fallback at the API boundary. The diffraction
algorithm, calibration, and thresholds were not changed. This final organization
step did not rerun diffraction.

## Provenance

The exact input files used for the closure and manifests were:

- `data/mappings/rescue_review_v1/rruff_rescue_ready_12_v1.csv`
- `data/mappings/rescue_review_v1/diffraction_needed_67_validation.csv`
- `data/mappings/rescue_review_v1/rruff_rescue_candidate_details_v1.csv`
- `data/mappings/rescue_review_v1/rruff_rescue_summary_v1.csv`
- `data/mappings/rescue_review_v1/high_priority_35_diffraction_validation.csv`
- `data/mappings/rescue_review_v1/diffraction_needed_160_xy_audit.csv`

The historical 12-row ready manifest carries its own upstream provenance, including
the high-priority review and candidate-detail sources. The 304-row closure uses the
summary file for the low-priority and not-rescuable sets, the 67-row validation for
the new rescue-ready/ambiguous/inconclusive sets, the 35-row validation for the
remaining high-priority inconclusive/no-validation sets, and the 160-row XY audit
for the 93 calculated-only samples.

Protected artifacts were not modified: the original 807 curated data, the 177-row
DIF-outside final manifest, v2/v3 outputs, MongoDB, formal CrystalDB, and the paper.

## Final values

```text
rescue_ready_rows = 24
ambiguous_samples = 48
final_total = 304
validation = PASS
```
