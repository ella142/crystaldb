# PowBase Candidate Canonical Validation v1

Read-only validation of entries 15, 74, 121, and 156 using existing review rules and the existing PowBase canonical document builder.

| Entry | Result | Recovery rule | Canonical points | Wavelength | Issues |
|---:|---|---|---:|---|---|
| 15 | **PASS** | UXD _START/_STEPSIZE/_STEPCOUNT metadata plus the _COUNTS intensity block; end is reconstructed as start + step*(count-1). | 13003 | [1.54056, 1.54439, 1.39222] | none |
| 74 | **PASS** | Three numeric 2theta header fields followed by the literal CuKalpha suffix; retain all following numeric intensity values. | 4001 | unknown | none |
| 121 | **PASS** | Koalariet source text decoded with NUL bytes replaced only in the parsing view, then the explicit three-number 2theta header and exact raw intensity count are used; source bytes are preserved. | 5851 | unknown | none |
| 156 | **PASS** | Koalariet source text decoded with NUL bytes replaced only in the parsing view, then the explicit three-number 2theta header and exact raw intensity count are used; source bytes are preserved. | 5851 | unknown | none |

- PASS: **4**
- FAIL: **0**
- Proposed PowBase X-ray production count: **48**
- Proposed CrystalDB pattern count: **3023**
- MongoDB writes: **none**
- Source archives modified: **no**
- Entry 137 processed: **no**
- Other conditional records processed: **no**
