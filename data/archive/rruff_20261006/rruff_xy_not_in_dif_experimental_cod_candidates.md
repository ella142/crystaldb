# RRUFF Outside-DIF Experimental COD Candidate Audit

This audit processes only the 177 rows already classified as `experimental` in `rruff_xy_not_in_dif_audit.csv`.
No RRUFF collection, curated dataset, v2/v3 output, or formal CrystalDB data was modified.

## Summary

177 total = 177
with_cell = 88
without_cell = 89
strong_candidate = 42
multiple_candidates = 38
weak_evidence = 17
no_candidate = 118

## Rules

- Name support uses the RRUFF `mineral` value and normalized exact matching against parsed COD `_chemical_name_mineral`.
- RRUFF chemistry uses `metadata["IDEAL CHEMISTRY"]` when present; missing chemistry does not exclude a name candidate.
- Complete source cells use `metadata["CELL PARAMETERS"]` with `a,b,c,alpha,beta,gamma`; candidates require all six CIF cell values and pass 5% length / 2 degree angle thresholds.
- No RRUFF space group is required or inferred. Candidate space groups are not used to populate RRUFF fields.
- Chemistry only rejects a candidate when the parsed element sets are completely disjoint. Complex formulas and overlapping-element ratio differences are retained as unresolved or solid-solution/ratio possibilities.
- Multiple retained COD IDs are listed together in the CSV; no candidate is selected.
- Candidate source is the existing parsed local COD index `data/mappings/cif_index.json`; no remote retrieval or old pipeline rerun was performed.

## Output

- Detail CSV: `D:\document\aiformaterials\crystaldb\data\mappings\rruff_xy_not_in_dif_experimental_cod_candidates.csv`
- Candidate IDs in `candidate_cod_ids` are JSON arrays.
