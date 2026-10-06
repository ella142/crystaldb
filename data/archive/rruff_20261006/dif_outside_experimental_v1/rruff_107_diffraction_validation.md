# DIF-outside experimental XY diffraction validation

## Scope

This audit processes only the 107 existing DIF-outside experimental measurements that already have CIF candidates.
It does not search COD, download CIFs, modify candidate data, run v2/v3, write MongoDB, or update formal CrystalDB.
The 70 `still_no_candidate` measurements are excluded.

## Input Integrity

- measurements: 107
- prior single_strong_candidate: 17
- prior multiple_valid_candidates: 69
- prior weak_candidate: 21
- candidate references: 591
- unique input CIFs: 512
- CIF parse status: {'ok': 512}
- usable XY profiles: 107/107
- output candidate rows: 591
- candidate diffraction statuses: {'not_evaluable': 9, 'diffraction_inconclusive': 196, 'diffraction_compatible': 379, 'evaluation_error': 7}
- candidate rows without metrics: 16

## Existing Diffraction Method

- CIF -> Gemmi theoretical reflections and structure factors
- existing XY normalization, smoothing, local-maxima peak detection, intensity and separation filters
- existing one-to-one peak assignment
- existing weighted-median zero-shift correction
- existing residual metrics: matched_count, median_residual, weighted_residual, max_residual, residual_slope, zero_shift
- existing candidate separability calculation for multi-candidate measurements
- existing calibration file and core three-metric P95 annotation logic; no threshold changes

Because these measurements are outside DIF, radiation is taken from the existing XY metadata when explicit. Mo uses the frozen Mo wavelength; non-Mo experimental descriptions use the frozen Cu reference. Co-radiation is not guessed and remains inconclusive.

## Final Summary

107 total = 107
resolved_candidate = 24
ambiguous_group = 51
diffraction_inconclusive = 32
diffraction_incompatible = 0

## Prior Group Breakdown

| prior group | resolved | ambiguous | inconclusive | incompatible | total |
|---|---:|---:|---:|---:|---:|
| single_strong_candidate | 9 | 0 | 8 | 0 | 17 |
| multiple_valid_candidates | 6 | 51 | 12 | 0 | 69 |
| weak_candidate | 9 | 0 | 12 | 0 | 21 |

## Measurement Results

| filename_sample_id | sample_id | prior group | candidate count | evaluable | compatible | final status | reason |
|---|---|---|---:|---:|---:|---|---|
| D120001-1 | XD120001 | weak_candidate | 1 | 0 | 0 | `diffraction_inconclusive` | no candidate produced evaluable diffraction metrics |
| D120007-1 | XD120007 | multiple_valid_candidates | 6 | 0 | 0 | `diffraction_inconclusive` | no candidate produced evaluable diffraction metrics |
| D120024-1 | XD120024 | weak_candidate | 1 | 0 | 0 | `diffraction_inconclusive` | no candidate produced evaluable diffraction metrics |
| D120025-1 | XD120025 | weak_candidate | 1 | 0 | 0 | `diffraction_inconclusive` | no candidate produced evaluable diffraction metrics |
| R040023-1 | R040023 | multiple_valid_candidates | 3 | 3 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R040043-1 | R040043 | multiple_valid_candidates | 17 | 17 | 16 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R040071-1 | R040071 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R040138-1 | R040138 | single_strong_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050037-1 | R050037 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R050043-1 | R050043 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R050087-1 | R050087 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R050123-1 | R050123 | multiple_valid_candidates | 17 | 17 | 16 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R050264-9 | R050264 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050429-1 | R050429 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R050432-1 | R050432 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R050437-1 | R050437 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R050451-1 | R050451 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R050452-9 | R050452 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050464-1 | R050464 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R050490-1 | R050490 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R050510-1 | R050510 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R050531-9 | R050531 | multiple_valid_candidates | 2 | 2 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050534-1 | R050534 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050546-1 | R050546 | multiple_valid_candidates | 2 | 2 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R050552-1 | R050552 | multiple_valid_candidates | 2 | 2 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R050560-9 | R050560 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050572-9 | R050572 | multiple_valid_candidates | 2 | 2 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050630 | R050630 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R050630-1 | R050630 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R050635-9 | R050635 | single_strong_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060007-9 | R060007 | single_strong_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060008-9 | R060008 | single_strong_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060014-1 | R060014 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060031-1 | R060031 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R060100-1 | R060100 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R060105-1 | R060105 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060109-1 | R060109 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060112-1 | R060112 | multiple_valid_candidates | 6 | 6 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060147-1 | R060147 | multiple_valid_candidates | 7 | 7 | 5 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060165-1 | R060165 | multiple_valid_candidates | 9 | 9 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060172-1 | R060172 | multiple_valid_candidates | 12 | 12 | 6 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060204-1 | R060204 | multiple_valid_candidates | 14 | 14 | 12 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060211-1 | R060211 | multiple_valid_candidates | 14 | 14 | 10 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060219-1 | R060219 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060222-1 | R060222 | multiple_valid_candidates | 82 | 82 | 48 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060224-1 | R060224 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060291-1 | R060291 | multiple_valid_candidates | 7 | 7 | 6 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060293-1 | R060293 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060297-1 | R060297 | multiple_valid_candidates | 17 | 17 | 16 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060312-1 | R060312 | multiple_valid_candidates | 5 | 5 | 5 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060343-1 | R060343 | multiple_valid_candidates | 2 | 2 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060353-1 | R060353 | multiple_valid_candidates | 4 | 4 | 4 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060363-1 | R060363 | multiple_valid_candidates | 17 | 17 | 17 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060382-1 | R060382 | multiple_valid_candidates | 43 | 43 | 27 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060383-1 | R060383 | multiple_valid_candidates | 3 | 3 | 3 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060389-1 | R060389 | single_strong_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060418-1 | R060418 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R060440-1 | R060440 | single_strong_candidate | 1 | 0 | 0 | `diffraction_inconclusive` | no candidate produced evaluable diffraction metrics |
| R060474-1 | R060474 | multiple_valid_candidates | 37 | 37 | 31 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060489-1 | R060489 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060494-1 | R060494 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060540-1 | R060540 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060551-1 | R060551 | multiple_valid_candidates | 3 | 3 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060613-1 | R060613 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R060680-1 | R060680 | multiple_valid_candidates | 3 | 3 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060688-9 | R060688 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060732-9 | R060732 | multiple_valid_candidates | 3 | 3 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R060747-1 | R060747 | multiple_valid_candidates | 3 | 3 | 3 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060856-1 | R060856 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R060886-1 | R060886 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R060994-1 | R060994 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R060999-1 | R060999 | multiple_valid_candidates | 7 | 7 | 3 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R061006-1 | R061006 | multiple_valid_candidates | 3 | 3 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R061080-1 | R061080 | multiple_valid_candidates | 14 | 14 | 3 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070088-1 | R070088 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070098-1 | R070098 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R070132-1 | R070132 | multiple_valid_candidates | 2 | 2 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R070162-1 | R070162 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R070227-1 | R070227 | multiple_valid_candidates | 4 | 4 | 3 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070286-1 | R070286 | multiple_valid_candidates | 3 | 3 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070319-1 | R070319 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070324-1 | R070324 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R070333-1 | R070333 | single_strong_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R070340-1 | R070340 | multiple_valid_candidates | 9 | 9 | 7 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070345-1 | R070345 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R070372-1 | R070372 | multiple_valid_candidates | 4 | 4 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R070444-1 | R070444 | multiple_valid_candidates | 6 | 6 | 6 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070505-9 | R070505 | weak_candidate | 1 | 0 | 0 | `diffraction_inconclusive` | no candidate produced evaluable diffraction metrics |
| R070598-1 | R070598 | multiple_valid_candidates | 13 | 13 | 13 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R070742-1 | R070742 | multiple_valid_candidates | 9 | 9 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R070750-1 | R070750 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R070755-1 | R070755 | multiple_valid_candidates | 3 | 3 | 3 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R080029-9 | R080029 | multiple_valid_candidates | 2 | 2 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R080032-9 | R080032 | weak_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R080048-9 | R080048 | multiple_valid_candidates | 3 | 3 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R080058-1 | R080058 | multiple_valid_candidates | 9 | 9 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R080092-1 | R080092 | weak_candidate | 1 | 1 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R090056-1 | R090056 | multiple_valid_candidates | 2 | 2 | 1 | `resolved_candidate` | exactly one candidate is inside the existing core diffraction envelope |
| R110052-1 | R110052 | multiple_valid_candidates | 8 | 6 | 4 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R110053-1 | R110053 | multiple_valid_candidates | 8 | 6 | 6 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R130003-1 | R130003 | single_strong_candidate | 1 | 1 | 0 | `diffraction_inconclusive` | no candidate met the existing core envelope and evidence is not uniformly incompatible |
| R140004-1 | R140004 | multiple_valid_candidates | 6 | 6 | 4 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R150020-1 | R150020 | multiple_valid_candidates | 12 | 12 | 9 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R150021-1 | R150021 | multiple_valid_candidates | 38 | 38 | 19 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R180024-1 | R180024 | multiple_valid_candidates | 8 | 8 | 6 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R220002-1 | R220002 | multiple_valid_candidates | 2 | 2 | 2 | `ambiguous_group` | multiple candidates are inside the existing core diffraction envelope |
| R220046 | R220046 | single_strong_candidate | 1 | 0 | 0 | `diffraction_inconclusive` | no candidate produced evaluable diffraction metrics |

## Candidate Metrics

The CSV contains one row per existing candidate, with the measurement-level final status repeated for audit joins.

## Output

- CSV: `D:\document\aiformaterials\crystaldb\data\mappings\dif_outside_experimental_v1\rruff_107_diffraction_validation.csv`
- MD: `D:\document\aiformaterials\crystaldb\data\mappings\dif_outside_experimental_v1\rruff_107_diffraction_validation.md`
