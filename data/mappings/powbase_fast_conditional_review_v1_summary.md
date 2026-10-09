# PowBase FAST X-ray conditional review v1

Lightweight, read-only decision pass using the existing PowBase inclusion manifest and unresolved-rescue audit. No full 170-record re-audit, archive reparse, SHA256 sweep, canonical staging, MongoDB write, COD matching, or Git operation was performed.

## Part A: entries 121 and 156

- Entry 121: **PASS**. Explicit X-ray source token; source header `23.000 0.020 140.000`; expected and observed count `5851`; reconstructed grid is monotonic and grid-aligned; no trimming, padding, interpolation, or resampling. Decision: `promote_verified`.
- Entry 156: **PASS**. Explicit X-ray source token; source header `23.000 0.020 140.000`; expected and observed count `5851`; reconstructed grid is monotonic and grid-aligned; no trimming, padding, interpolation, or resampling. Decision: `promote_verified`.

## Part B: 75 existing conditional X-ray records

- Records reviewed: `75`.
- `ready_for_canonical_validation`: **2**.
- `retain_conditional`: **73**.
- `move_to_unresolved`: **0**.

### Decision groups

- `promote_candidate` (2): 15, 74
- `retain_conditional` (73): 3, 5, 6, 7, 9, 16, 17, 18, 21, 23, 24, 25, 27, 29, 30, 35, 36, 39, 40, 41, 42, 47, 48, 49, 52, 53, 56, 61, 63, 64, 65, 82, 83, 84, 85, 87, 89, 91, 92, 93, 94, 99, 107, 108, 109, 110, 114, 119, 129, 130, 131, 132, 134, 135, 136, 137, 138, 139, 141, 142, 143, 145, 146, 147, 148, 150, 151, 152, 154, 166, 167, 168, 169
- `move_to_unresolved` (0): none

### Conditional-reason groups

- `legacy_fixed_width_terminal_zero_padding_policy_review` (71): 3, 5, 6, 7, 9, 16, 17, 18, 21, 23, 24, 25, 27, 29, 30, 35, 39, 40, 41, 42, 47, 48, 49, 52, 53, 56, 61, 63, 64, 65, 82, 83, 84, 85, 87, 89, 91, 92, 93, 94, 99, 107, 108, 109, 110, 119, 129, 130, 131, 132, 134, 135, 136, 137, 138, 139, 141, 142, 143, 145, 146, 147, 148, 150, 151, 152, 154, 166, 167, 168, 169
- `legacy_header_with_explicit_source_suffix_review` (1): 74
- `mixed_member_archive_member_selection_and_review` (1): 36
- `terminal_zero_padding_review_without_uniform_row_evidence` (1): 114
- `uxd_explicit_axis_and_counts_review` (1): 15

### Ready candidates by recovery mechanism

- Explicit UXD axis/count rule: entry `15`.
- Explicit three-number header with source suffix rule: entry `74`.

Terminal-zero candidates, including entry `137`, remain conditional. The existing evidence documents candidate padding but does not adopt a trimming policy. No intensity values were discarded.

## Provisional upper bound

**PROVISIONAL COUNT — NOT YET PRODUCTION VALIDATED**

- Existing production PowBase X-ray records: `44`.
- Validated rescue records 121 and 156: `+2`.
- Fast-pass candidates ready for canonical validation: `+2`.
- Provisional upper bound: **48**.

This is not a production count and does not authorize canonical ingestion. The next task must perform canonical validation only for the ready candidate records and separately handle the rescued records.

## Testing

No parser or canonicalization code changed in this pass; related tests were skipped as permitted. Generation assertions confirmed exactly 75 conditional X-ray rows and exact-count rescue evidence for entries 121 and 156.
