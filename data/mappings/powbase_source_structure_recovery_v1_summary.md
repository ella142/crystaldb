# PowBase source structure recovery dry-run v1

Read-only, staging-only recovery for the nine production PowBase X-ray patterns with source structure-model evidence.

## Scope and safeguards

- Entries: 106, 113, 116, 117, 124, 125, 157, 159, 160
- No MongoDB writes, production canonical changes, source archive changes, COD searches, or Git operations were performed.
- Source model values were copied only when explicitly present in the cached member.
- Formula-like labels were not promoted to confirmed formulas.
- Entry 157 models were kept separate and were not assigned as sample phases.

## Counts

- Structure-bearing PowBase patterns evaluated: 9
- Total explicit source structure models: 14
- CIFs successfully recovered and Gemmi-validated: 10
- CIFs failed validation: 0
- Patterns with clear one-to-one source linkage: 7
- Patterns with ambiguous linkage: 2
- Patterns with linkage not supported: 0

## Linkage decisions

- Entry 106 (`POWBASE_PAT_106`): `source_link_ambiguous`. The same PowBase source member contains multiple explicit structure models/phases for one experimental pattern.
- Entry 113 (`POWBASE_PAT_113`): `source_link_supported`. The same PowBase source member contains one explicit structure model and the experimental diffraction profile.
- Entry 116 (`POWBASE_PAT_116`): `source_link_supported`. The same PowBase source member contains one explicit structure model and the experimental diffraction profile.
- Entry 117 (`POWBASE_PAT_117`): `source_link_supported`. The same PowBase source member contains one explicit structure model and the experimental diffraction profile.
- Entry 124 (`POWBASE_PAT_124`): `source_link_supported`. The same PowBase source member contains one explicit structure model and the experimental diffraction profile.
- Entry 125 (`POWBASE_PAT_125`): `source_link_supported`. The same PowBase source member contains one explicit structure model and the experimental diffraction profile.
- Entry 157 (`POWBASE_PAT_157`): `source_link_ambiguous`. One experimental pattern contains five explicit STR models; the source does not establish which models are sample phases or how they map to the pattern.
- Entry 159 (`POWBASE_PAT_159`): `source_link_supported`. The same PowBase source member contains one explicit structure model and the experimental diffraction profile.
- Entry 160 (`POWBASE_PAT_160`): `source_link_supported`. The same PowBase source member contains one explicit structure model and the experimental diffraction profile.

## Entry 157

- `STR(I_41/A_M_D_Z)`: ICSD Collection Code 202243,  Anatase Ti O2; space group `I_41/A_M_D_Z`; unit cell complete `False`; atom sites `2`; CIF recoverable `False`; staging CIF `none`.
- `STR(P_1_21/N_1)`: ICSD Collection Code 6162,  Gibbsite Al (O H)3; space group `P_1_21/N_1`; unit cell complete `False`; atom sites `14`; CIF recoverable `False`; staging CIF `none`.
- `STR(R_-3_C_H)`: ICSD Collection Code 66756,  Hematite Fe2 O3; space group `R_-3_C_H`; unit cell complete `False`; atom sites `2`; CIF recoverable `False`; staging CIF `none`.
- `STR(P_31_2_1)`: Quartz; space group `P_31_2_1`; unit cell complete `False`; atom sites `2`; CIF recoverable `False`; staging CIF `none`.
- `STR(C_1)`: Kaolinite Al4 (O H)8 (Si4 O10); space group `C_1`; unit cell complete `True`; atom sites `13`; CIF recoverable `True`; staging CIF `data\staging\powbase_source_structures_v1\POWBASE_157_STR_C_1.cif`.

Entry 157 contains five explicit `STR(...)` models: anatase, gibbsite, hematite, quartz, and kaolinite. The source does not establish that these five models are five phases of the bauxite pattern, so no pattern-to-model relation is assigned. Models with incomplete source unit-cell angles are retained in the audit but do not receive CIFs.

## Wavelength 6 versus 7

The metadata completeness audit found 7 records with explicit wavelength metadata, while production stored numeric wavelengths for 6.
- Entry 116: source ['!Anode Cu    Alpha1  1.54056    Alpha2  1.54439    Ratio  0.50000', '!Anode Cu    Alpha1  1.54056    Alpha2  1.54439    Ratio  0.50000']; parsed [1.54056, 1.54439] Å; production value `null/unknown`. The source explicitly labels Alpha1/Alpha2 wavelength values, but the production integration left wavelength_angstrom blank for this legacy SR5 source format.

## Validation

Recovered CIFs are written only under `data/staging/powbase_source_structures_v1/`. Validation checks CIF parsing, cell values, normalized space-group serialization, and atom-site count. Source occupancies are preserved where present; unknown occupancies remain missing.
