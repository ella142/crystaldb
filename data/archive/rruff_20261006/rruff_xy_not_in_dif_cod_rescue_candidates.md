# RRUFF outside-DIF COD rescue audit

This artifact processes only the 118 rows already classified as `no_candidate` in the existing local-index result.
It does not modify MongoDB, the 807 dataset, 304 rescue/review outputs, v2/v3, or formal CrystalDB data.

## Summary

118 total = 118
candidate_found = 48
single_strong_candidate = 6
multiple_valid_candidates = 31
weak_candidate = 11
still_no_candidate = 70

## Rules

- COD was queried by each distinct RRUFF mineral name using the COD JSON metadata endpoint; retained records also require an exact normalized match in COD `mineral` or `commonname` metadata.
- The RRUFF formula was used when present; missing formula did not exclude a candidate.
- Completely disjoint element sets were rejected. Overlapping-element ratio differences and solid-solution notation were retained.
- Complete RRUFF cells were compared directly on a,b,c,alpha,beta,gamma using 5% length and 2 degree angle tolerances.
- RRUFF space group was not required or inferred; COD space group was ignored for sample classification.
- Multiple retained COD IDs are all listed; no candidate was selected.
- Only final-shortlist COD IDs missing from the local index were downloaded: 241 CIF files.

## Artifacts

- Detail CSV: `D:\document\aiformaterials\crystaldb\data\mappings\rruff_xy_not_in_dif_cod_rescue_candidates.csv`
- Query metadata cache: `D:\document\aiformaterials\crystaldb\data\staging\rruff_xy_not_in_dif_cod_rescue_v1\cod_name_query_metadata.json`
- Missing shortlist CIF staging directory: `D:\document\aiformaterials\crystaldb\data\staging\rruff_xy_not_in_dif_cod_rescue_v1\cif`
