# CrystalDB Phase-Character Inference v1

Dry-run only. No MongoDB writes, production updates, source-file changes, or release-statistic updates were performed.

## Scope and rule

The report evaluates 1,064 RRUFF final experimental records and the 44 PowBase records already admitted to the production X-ray set. Every record receives exactly one dry-run decision. Positive evidence is required for both phase classes.

RRUFF explicit source mixture, contamination, secondary-phase, quantitative-fraction, or secondary-peak annotations are retained as positive multiphase evidence. No RRUFF single-phase inference is made because the existing diffraction calibration describes candidate compatibility but does not define a validated phase-purity threshold. A unique structure linkage therefore remains insufficient.

PowBase entries 113 and 124 have one explicit FullProf phase block/name and no source warning for a second phase. Entry 106 has two FullProf phase blocks and an official index description of two allotropic forms, so it is classified as positive multiphase source evidence. Entry 89 is not in the 44-record production target; its PHASE_2 `Al2 O3` block remains an internal-standard edge case in the review notes.

## Results

| Source | Total | Infer single | Infer multi | Retain unknown |
|---|---:|---:|---:|---:|
| RRUFF | 1064 | 0 | 13 | 1051 |
| POWBASE | 44 | 2 | 1 | 41 |
| Total | 1108 | 2 | 14 | 1092 |

Inference routes:

- `POWBASE:diffraction_purity_rule_v1`: 2
- `POWBASE:source_annotation`: 1
- `RRUFF:source_annotation`: 13

## Hypothetical production distribution

This is a calculation only. It is not written to MongoDB.

| Phase character | Current | Hypothetical |
|---|---:|---:|
| single_phase | 855 | 857 |
| multi_phase | 40 | 54 |
| unknown | 2124 | 2108 |
| Total | 3019 | 3019 |

## Manual review samples

Strongest inferred single-phase records:

- `113`: FullProf content contains one explicit phase block and one phase name, with a validated experimental profile and no source text indicating an impurity, mixture, or internal standard.
- `124`: FullProf content contains one explicit phase block and one phase name, with a validated experimental profile and no source text indicating an impurity, mixture, or internal standard.

Strongest inferred multiphase records:

- `106` `LiNbWO6`: #LiNbWO6#X#Cu-Kalpha#disorder; line broadening#LiNbWO6, Crystal structure of its two allotropic forms. J. L. Fourquet, <A href="mailto:alb@cristal.org">A. Le Bail</A> and P. A. Gillet, Mat. Res. Bull., 23 (198) 1163-1170#1999
- `R040043-1` `Marialite`: Powder, 78% marialite, 22% calcite, by weight
- `R050092-1` `Siegenite`: Powder, mixed with chalcopyrite [a:5.2903(5), c: 10.432(1)]
- `R050244-1` `Mangano-mangani-ungarettiite`: Powder, appears to be a mix of ungarettiite and namansilite, cell parameters are from single crystal
- `R050510-1` `Anapaite`: Powder includes light and dark phases. Cell parameters from single crystal
- `R060112-1` `Burkeite`: Powder, mixed with thenardite
- `R060172-1` `Polylithionite`: Powder, with trace corundum contamination from the grinding process
- `R060215-1` `Polylithionite`: Powder, with trace corundum contamination from the grinding process

Unique linkage cases retained unknown:

- `R040036-1`
- `R040071-1`
- `R040166-1`
- `R050043-1`
- `R050087-1`
- `R050093-1`
- `R050279-1`
- `R050355-1`

Representative ambiguous/unknown cases:

- `10`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.
- `111`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.
- `116`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.
- `117`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.
- `12`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.
- `125`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.
- `126`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.
- `127`: The source index label and numeric profile do not provide positive phase-purity evidence under the v1 rule.

PowBase internal-standard edge case:

- Entry `89` is excluded from the 44-record target. Its PHASE_1 is `dimethyl-2,6-naphthalenedicarboxylate` and PHASE_2 is `Al2 O3`; no multiphase inference is promoted from this conditional record.

## Files and limitations

The CSV contains one row per evaluated pattern. JSON preserves the structured evidence and decision rationale. Raw source values are referenced but not rewritten. Residual and matched-fraction fields are blank where no existing calibration record is available. `unexplained_strong_peak_evidence` is `not_available_in_existing_curation` rather than a negative finding.
