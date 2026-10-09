# RRUFF Phase-Character Inference v2 Dry Run

Dry-run only. MongoDB, canonical source files, and Git history were not modified.

## Inputs

- Final production RRUFF manifest: `data/mappings/rruff_experimental_final_v1.csv`
- Frozen RRUFF phase audit: `data/mappings/rruff_2120_to_807_audit.csv`
- Staging validation report: `data/mappings/rruff_final_staging_validation_v1.json`
- Validated production pattern count: 1064
- Source groups: curated_807=807, dif_outside_177=177, rescue_80=80

## Rules Applied

- `multi_phase`: assigned only from explicit source evidence for a second phase, mixture, contamination, additional-phase peaks, or multiple named phase fractions.
- `single_phase`: assigned to experimental RRUFF powder patterns with one target identity, no explicit multiphase evidence, and RRUFF/source or structure-linkage evidence supporting the identity.
- `unknown`: reserved for unresolved, conflicting, or insufficient evidence.
- Solid-solution and mixed-occupancy formula notation was not treated as multiphase evidence.
- Provenance assigned on every row: `phase_character_origin=inferred`, `phase_character_method=rruff_reference_powder_v2`.

## Summary

| phase_character | count |
|---|---:|
| single_phase | 1051 |
| multi_phase | 13 |
| unknown | 0 |
| total | 1064 |

Original production phase-character values are read from the final manifest when present. The current final RRUFF manifest has no phase-character column, so these default to `unknown`. The frozen audit label is preserved separately in the CSV as `audit_phase_label`.

| label source | single_phase | multi_phase | unknown |
|---|---:|---:|---:|
| original_phase_character | 0 | 0 | 1064 |
| audit_phase_label | 0 | 13 | 1051 |

Records containing solid-solution notation that remained `single_phase`: 55

## Multi-Phase Entries

| sample_id | filename_sample_id | mineral | evidence | source text |
|---|---|---|---|---|
| `R040043` | `R040043-1` | Marialite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Marialite; diffraction_sample_description=Powder, 78% marialite, 22% calcite, by weight; phase_evidence=quantitative_fraction; structure_status=ambiguous; candidate_count=17. |
| `R050244` | `R050244-1` | Mangano-mangani-ungarettiite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Mangano-mangani-ungarettiite; diffraction_sample_description=Powder, appears to be a mix of ungarettiite and namansilite, cell parameters are from single crystal; phase_evidence=mixture_language; structure_status=unlinked; candidate_count=0. |
| `R050510` | `R050510-1` | Anapaite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Anapaite; diffraction_sample_description=Powder includes light and dark phases. Cell parameters from single crystal; phase_evidence=mixture_language; unknown_phase; structure_status=ambiguous; candidate_count=2. |
| `R060112` | `R060112-1` | Burkeite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Burkeite; diffraction_sample_description=Powder, mixed with thenardite; phase_evidence=mixture_language; structure_status=inconclusive; candidate_count=6. |
| `R060172` | `R060172-1` | Polylithionite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Polylithionite; diffraction_sample_description=Powder, with trace corundum contamination from the grinding process; phase_evidence=named_secondary_phase; qualitative_impurity; structure_status=ambiguous; candidate_count=12. |
| `R070444` | `R070444-1` | Guyanaite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Guyanaite; diffraction_sample_description=Powder, mixture includes bracewellite, eskolaite and quartz; phase_evidence=mixture_language; structure_status=ambiguous; candidate_count=6. |
| `R070598` | `R070598-1` | Anorthite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Anorthite; diffraction_sample_description=Powder, with other plagioclase-series minerals; phase_evidence=named_secondary_phase; structure_status=ambiguous; candidate_count=13. |
| `R220002` | `R220002-1` | Schwertmannite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Schwertmannite; diffraction_sample_description=Powder, sharp peak is quartz; phase_evidence=secondary_peak; structure_status=ambiguous; candidate_count=2. |
| `R250050` | `R250050` | Elliottite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Elliottite; diffraction_sample_description=Powder, with contamination from minyulite; phase_evidence=named_secondary_phase; qualitative_impurity; structure_status=unlinked; candidate_count=0. |
| `R250123` | `R250123` | Shiranuiite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=dif_outside_177; profile_origin=experimental; mineral=Shiranuiite; diffraction_sample_description=Powder, presence of strong peaks of tulamenite and small peaks of unknown phases; phase_evidence=secondary_peak; unknown_phase; structure_status=unlinked; candidate_count=0. |
| `R050092` | `R050092-1` | Siegenite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=rescue_80; profile_origin=experimental; mineral=Siegenite; diffraction_sample_description=Powder, mixed with chalcopyrite [a:5.2903(5), c: 10.432(1)]; phase_evidence=mixture_language; structure_status=multiple_diffraction_compatible_candidates; candidate_count=2. |
| `R060215` | `R060215-1` | Polylithionite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=rescue_80; profile_origin=experimental; mineral=Polylithionite; diffraction_sample_description=Powder, with trace corundum contamination from the grinding process; phase_evidence=named_secondary_phase; qualitative_impurity; structure_status=multiple_diffraction_compatible_candidates; candidate_count=10. |
| `R061020` | `R061020-1` | Awaruite | multi_phase: explicit second-phase, mixture, contamination, additional peaks, or named phase-fraction evidence | RRUFF final manifest: source_group=rescue_80; profile_origin=experimental; mineral=Awaruite; diffraction_sample_description=Powder, mixed with andradite: a:12.0607(4); phase_evidence=mixture_language; structure_status=multiple_diffraction_compatible_candidates; candidate_count=3. |

## Unknown Entries

None.

## Output

- CSV: `data/mappings/rruff_phase_character_inference_v2.csv`
- Summary: `data/mappings/rruff_phase_character_inference_v2_summary.md`
