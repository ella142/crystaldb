# PowBase unresolved rescue audit v1

Read-only audit of the 30 X-ray records currently classified as `exclude_unresolved`.

## Method

- A profile is safely recoverable only when the source three-number start/step/end header is valid, grid-aligned, and the raw intensity count equals `round((end-start)/step)+1`.
- Terminal zero runs and fixed-width row candidates are retained as review evidence. No values were trimmed or padded.
- Readable legacy text containing NUL padding was decoded for parsing only. Original archive bytes and SHA256 values were preserved.

## Counts

- Records audited: 30
- Records with FullProf evidence: 3
- Records with CIF evidence: 1
- Records with any refinement/model evidence: 8
- Records with embedded model content: 6
- Profiles safely recoverable: 2
- Still unresolved: 28

## Classification

- `A_model_and_profile_recoverable` (2): 121, 156
- `B_model_present_profile_unresolved` (6): 1, 81, 90, 112, 144, 155
- `C_profile_recoverable_without_model` (0): none
- `D_still_unresolved` (22): 20, 22, 26, 28, 32, 33, 34, 37, 44, 54, 55, 57, 59, 62, 70, 88, 98, 103, 104, 158, 161, 165

## Model and format evidence

- FullProf evidence includes explicit index references or embedded FullProf markers such as phase blocks and `R_Bragg`.
- CIF evidence includes explicit CIF/pdCIF/GSAS2CIF markers or comment-prefixed CIF tags.
- A model/reference flag does not imply that an external model file was present in the downloaded archive.

- Entry 1: content family `legacy_intensity_array`; references fullprof, pcr, other_refinement_or_model; embedded model content no; phases 0.
- Entry 81: content family `fullprof_style_pattern`; references fullprof, pcr, other_refinement_or_model; embedded model content yes; phases 1.
- Entry 90: content family `commented_pdcif`; references cif, gsas, other_refinement_or_model; embedded model content no; phases 0.
- Entry 112: content family `fullprof_style_pattern`; references fullprof, pcr, other_refinement_or_model; embedded model content yes; phases 1.
- Entry 121: content family `koalariet_style_pattern`; references koalariet; embedded model content yes; phases 1.
- Entry 144: content family `arit_style_pattern`; references arit; embedded model content yes; phases 1.
- Entry 155: content family `arit_style_pattern`; references none; embedded model content yes; phases 1.
- Entry 156: content family `koalariet_style_pattern`; references koalariet; embedded model content yes; phases 1.

## Profile review

Entries 121 and 156 are safely recoverable under the exact-count rule. Their `.dat` members are Koalariet input files with embedded model text and a valid 23.000/0.020/140.000 profile header followed by exactly 5,851 raw intensity values.

The remaining records retain their complete raw arrays. A mismatch is not repaired by removing terminal zeros, repeated rows, or other candidate padding.

No MongoDB, source archive, canonical record, or Git state was modified.
