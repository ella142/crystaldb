# Original Frozen RRUFF Experimental Resolution Audit

This is a read-only audit of the frozen original experimental structure-resolution output. No candidate search, diffraction rerun, MongoDB write, source-file edit, mapping edit, v2/v3 replacement, or manuscript edit was performed.

## Primary Result

| Statistic | Exact value | Computation basis |
|---|---:|---|
| Clean experimental profiles | 807 | `records` length in `data/mappings/rruff_experimental_resolution_v1.json` |
| Record resolutions | 560 | `structure_resolution.resolution_level == "record"` |
| Group resolutions | 188 | `structure_resolution.resolution_level == "group"` |
| Review resolutions | 59 | `structure_resolution.resolution_level == "review"` |
| Profiles with >=1 usable CIF/COD candidate link | 807 | non-empty usable `all_sample_structure_candidates` |
| Profiles with no usable CIF link | 0 | clean profile total minus previous row |
| Total original CIF-link rows | 6410 | sum of usable COD rows in `all_sample_structure_candidates` |
| Distinct COD IDs across all original candidate links | 2351 | union of COD `source_id` values in `all_sample_structure_candidates` |
| Distinct COD IDs used by record-level resolutions | 391 | union of `selected_candidate.source_id` for record rows |
| Distinct COD IDs contained inside group-level resolutions | 524 | union of `bibliographic_candidates.source_id` for group rows |
| Review profiles with >=1 original CIF candidate | 59 / 59 | review rows with non-empty usable `all_sample_structure_candidates` |
| Review profiles with >=1 bibliographic CIF candidate | 0 / 59 | review rows with non-empty usable `bibliographic_candidates` |

The canonical resolution-level candidate-link rows are also retained as a separate audit quantity:

- record selected-candidate rows: `560`
- group bibliography-supported rows: `810`
- review retained-candidate rows: `480`
- canonical resolution-level rows total: `1850`
- canonical resolution-level distinct COD IDs: `1211`

This distinction is intentional. The requested total CIF-link count above is the full original candidate-link universe, while the canonical rows describe the evidence retained at each final resolution level. Neither count collapses group members.

## Group Cardinality

Group size is computed from `bibliographic_candidates`, because that is the candidate set explicitly retained by the original group resolution. Every group member remains listed in the audit CSV.

| Group size | Number of groups |
|---:|---:|
| 2 CIFs | 65 |
| 3 CIFs | 42 |
| 4+ CIFs | 81 |

Full group-size distribution: `{"2":65,"3":42,"4":28,"5":25,"6":7,"7":5,"8":1,"10":2,"11":1,"12":2,"13":1,"15":1,"16":2,"17":1,"18":3,"23":2}`

For reference only, the broader pre-bibliography `all_sample_structure_candidates` lists in group profiles contain more rows than the retained group sets. They are not used to collapse or reinterpret the original groups.

## Resolution Status Cross-check

| Resolution status | Count |
|---|---:|
| `bibliography_supported_candidate_group` | 188 |
| `no_bibliographic_match` | 58 |
| `single_candidate_after_filtering` | 248 |
| `unique_bibliographic_match` | 312 |
| `unparseable_reference` | 1 |

Independent checks against the frozen JSON summary: `{"summary_clean_profiles_matches":true,"summary_level_counts_match":true,"all_candidate_paths_exist":true,"canonical_link_rows_equal_parts":true}`

## Exact Source Files

1. `D:\document\aiformaterials\crystaldb\data\mappings\rruff_experimental_resolution_v1.json`
   - Primary frozen result file used for every profile, level, status, candidate-link, COD ID, selected-candidate, group-membership, and review-candidate statistic.
   - Fields used: `records`, `structure_resolution.resolution_level`, `structure_resolution.resolution_status`, `structure_resolution.all_sample_structure_candidates`, `structure_resolution.selected_candidate`, `structure_resolution.bibliographic_candidates`.
2. `D:\document\aiformaterials\crystaldb\scripts\build_rruff_experimental_resolution_v1.py`
   - Historical method/source definition inspected to verify the clean experimental population and original resolution policy. It was not executed.

No v2/v3 selected-structure output was used as a replacement or ground truth. No diffraction output was needed to compute this audit.

## Comparison With Remembered Summary

| Metric | Remembered | Actual frozen file | Difference |
|---|---:|---:|---:|
| Clean profiles | 807 | 807 | +0 |
| Record | 560 | 560 | +0 |
| Group | 188 | 188 | +0 |
| Review | 59 | 59 | +0 |

The remembered summary is exact for all four top-level counts. There is no discrepancy to explain from the frozen file.

## Original Curated Experimental RRUFF Dataset

clean profiles = 807
record = 560
group = 188
review = 59
profiles with >=1 CIF candidate/link = 807
distinct COD CIF IDs involved = 2351

Detail CSV: `D:\document\aiformaterials\crystaldb\rruff_original_resolution_audit.csv`
