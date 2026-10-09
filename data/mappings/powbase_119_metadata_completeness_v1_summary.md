# PowBase 119 Metadata Completeness v1

Read-only metadata completeness audit for the exact 119 PowBase X-ray patterns currently in production CrystalDB. No MongoDB writes, source archives, canonical records, website/manuscript files, or Git state were modified. The existing 44-record completeness audit was reused; only the 75 later-integrated records were read from cached archives for metadata not carried by the integration reports.

## Interpretation

- Formula values are counted only when an explicit formula field is present in the source. A formula-like sample label is kept separate and is not promoted to a confirmed formula.
- Wavelengths are source-explicit numeric values recovered from the preserved index/source metadata or production provenance. Multiple wavelengths means at least two distinct explicit numeric values.
- Unit-cell, space-group, atom-site, and refinement/model flags require literal source evidence. Comment-prefixed pdCIF/GSAS tags are treated as source metadata without rewriting the source file.
- Linked canonical CIF means an existing production pattern-to-structure relation points to a physical file under `data/canonical/structures/`.

## Counts

| Category | Count | Entry IDs |
|---|---:|---|
| source material/sample label | 119 | 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18, 19, 21, 23, 24, 25, 27, 29, 30, 35, 38, 39, 40, 41, 42, 43, 45, 46, 47, 48, 49, 52, 53, 56, 58, 60, 61, 63, 64, 65, 66, 67, 68, 69, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 82, 83, 84, 85, 87, 89, 91, 92, 93, 94, 99, 106, 107, 108, 109, 110, 111, 113, 116, 117, 119, 121, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 145, 146, 147, 148, 149, 150, 151, 152, 154, 156, 157, 159, 160, 162, 163, 164, 166, 167, 168, 169 |
| formula-like source label | 107 | 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18, 19, 21, 23, 24, 25, 27, 29, 30, 35, 38, 39, 40, 41, 42, 43, 45, 46, 47, 48, 49, 52, 53, 56, 58, 60, 61, 63, 64, 65, 66, 67, 68, 69, 72, 74, 75, 76, 78, 79, 82, 83, 84, 85, 87, 89, 91, 92, 93, 94, 99, 106, 116, 117, 119, 121, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 145, 146, 147, 148, 149, 150, 151, 152, 154, 156, 159, 160, 163, 164, 166, 167, 168, 169 |
| explicit chemical formula | 1 | 119 |
| explicit wavelength | 31 | 7, 10, 15, 18, 80, 82, 83, 84, 85, 87, 89, 91, 92, 93, 94, 99, 106, 107, 108, 109, 110, 113, 116, 119, 121, 124, 156, 160, 166, 168, 169 |
| multiple distinct explicit wavelengths | 22 | 15, 80, 82, 83, 84, 85, 87, 94, 106, 107, 108, 109, 110, 113, 116, 119, 121, 124, 156, 160, 166, 169 |
| complete unit cell | 24 | 82, 83, 84, 85, 87, 89, 94, 106, 107, 108, 109, 110, 113, 116, 117, 119, 124, 125, 157, 159, 160, 166, 168, 169 |
| space group | 28 | 82, 83, 84, 85, 87, 89, 94, 106, 107, 108, 109, 110, 113, 116, 117, 119, 121, 124, 125, 142, 156, 157, 159, 160, 166, 167, 168, 169 |
| atomic coordinates / atom sites | 24 | 82, 83, 84, 85, 87, 89, 94, 106, 107, 108, 109, 110, 113, 116, 117, 119, 124, 125, 156, 157, 159, 160, 168, 169 |
| source refinement/structure model | 29 | 82, 83, 84, 85, 87, 89, 94, 106, 107, 108, 109, 110, 113, 116, 117, 119, 121, 124, 125, 136, 142, 152, 156, 157, 159, 160, 166, 168, 169 |
| linked production structure | 7 | 113, 116, 117, 124, 125, 159, 160 |
| linked canonical CIF | 7 | 113, 116, 117, 124, 125, 159, 160 |
| bibliographic reference | 49 | 3, 4, 5, 6, 8, 10, 12, 13, 16, 19, 21, 23, 25, 27, 29, 30, 35, 38, 41, 52, 53, 61, 64, 65, 66, 67, 68, 69, 78, 79, 85, 87, 89, 91, 92, 93, 94, 99, 116, 119, 129, 130, 132, 148, 150, 152, 154, 164, 168 |
| profile-only status | 91 | 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18, 19, 21, 23, 24, 25, 27, 29, 30, 35, 38, 39, 40, 41, 42, 43, 45, 46, 47, 48, 49, 52, 53, 56, 58, 60, 61, 63, 64, 65, 66, 67, 68, 69, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 91, 92, 93, 99, 111, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 143, 145, 146, 147, 148, 149, 150, 151, 152, 154, 162, 163, 164 |

## Requested Entry Lists

- Complete crystallographic structure metadata (`cif_recoverability=sufficient_source_structure_metadata`): 82, 83, 84, 85, 87, 89, 94, 106, 107, 108, 109, 110, 113, 116, 117, 119, 124, 125, 157, 159, 160, 168, 169
- Linked canonical CIFs: 113, 116, 117, 124, 125, 159, 160
- Missing source material labels: none
- Explicit wavelengths: 7, 10, 15, 18, 80, 82, 83, 84, 85, 87, 89, 91, 92, 93, 94, 99, 106, 107, 108, 109, 110, 113, 116, 119, 121, 124, 156, 160, 166, 168, 169

## Provenance and Scope

- The 119 records are the disjoint union of the prior 44 verified production records and the later 75 final-validated production records.
- No formula, wavelength, unit cell, space group, structure model, or bibliography was inferred from material identity.
- Phase character remains outside this audit and is not promoted from source model evidence.
- Production structure links were checked read-only against the `relations` and `structures` collections; the seven linked canonical CIFs are entries 113, 116, 117, 124, 125, 159, and 160.
