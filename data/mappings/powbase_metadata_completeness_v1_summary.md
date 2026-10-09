# PowBase Metadata Completeness Audit v1

Read-only audit of exactly the 44 PowBase X-ray patterns currently included in production CrystalDB. No MongoDB writes, source-file changes, canonical-record changes, or COD/CIF matching were performed.

## Interpretation rules

- `explicit_formula` is populated only from an explicitly labeled formula field in the archived source text. A material label such as `Li2Ti3O7` remains a formula-like label, not a confirmed formula.
- Radiation and wavelength are retained with source evidence. Index `X` is reported as the literal official X-ray modality token. A Cu-Kalpha label without a numeric wavelength does not create a wavelength value.
- Unit-cell, space-group, atom-site, and phase/refinement fields are reported only when the archived source contains corresponding structural-model evidence.
- Multiple phase/model blocks are retained. They are not collapsed into one phase, and internal-standard interpretation is not inferred.
- Entry 157 contains five explicit `STR(...)` models with named source materials; these remain source evidence and are not promoted to sample phases.

## Counts

| Metadata category | Count | Entry IDs |
|---|---:|---|
| material/source label present | 44 | all 44 |
| explicit formula | 0 | none |
| formula-like label only | 36 | 4, 8, 10, 12, 13, 19, 38, 43, 45, 46, 58, 60, 66, 67, 68, 69, 72, 75, 76, 78, 79, 106, 116, 117, 124, 125, 126, 127, 128, 133, 140, 149, 159, 160, 163, 164 |
| wavelength | 7 | 10, 80, 106, 113, 116, 124, 160 |
| complete unit cell | 9 | 106, 113, 116, 117, 124, 125, 157, 159, 160 |
| space group | 9 | 106, 113, 116, 117, 124, 125, 157, 159, 160 |
| atomic coordinates / atom sites | 9 | 106, 113, 116, 117, 124, 125, 157, 159, 160 |
| explicit refinement/phase model | 9 | 106, 113, 116, 117, 124, 125, 157, 159, 160 |
| sufficient source structure metadata for CIF recovery | 9 | 106, 113, 116, 117, 124, 125, 157, 159, 160 |
| profile-only | 35 | 4, 8, 10, 12, 13, 19, 38, 43, 45, 46, 58, 60, 66, 67, 68, 69, 71, 72, 73, 75, 76, 77, 78, 79, 80, 111, 126, 127, 128, 133, 140, 149, 162, 163, 164 |
| publication/reference citation present | 15 | 4, 8, 10, 12, 13, 19, 38, 66, 67, 68, 69, 78, 79, 116, 164 |
| raw bibliographic/comment field present | 44 | all records with preserved index comments |

Total explicit source phase/refinement models across records: `14`. Entry 106 contributes two source phase blocks; the other model-bearing records contribute one each.

## Structure-bearing records

The source archives contain structural-model evidence for entries 106, 113, 116, 117, 124, 125, 157, 159, 160. These records expose phase/refinement content, space-group evidence, atom-site/coordinate evidence, and complete unit-cell values sufficient for a source-only CIF reconstruction audit. Entry 157 has five explicit source models; those models are retained as evidence and are not assigned as sample phases. This does not create a CIF and does not confirm a canonical formula.

Entry 106 contains two FullProf phase blocks. Entry 125 contains a Koalariet structural model with variable Ti/Fe occupancies. Both facts are preserved as source evidence and are not silently collapsed.

## Profile-only records

The remaining records are profile-only for this audit: their archived files provide diffraction data and/or instrument metadata but no source structure metadata sufficient for a source-only CIF recovery.

## Limitations

No external structure search, COD lookup, CIF matching, formula normalization, formula inference, phase-purity inference, or production update was performed.
