# PowBase Canonical Dry-Run Preparation v1

This report prepares the 44 records marked `include_verified` in the PowBase CrystalDB v1 inclusion manifest. It does not write MongoDB, modify production CrystalDB, modify the cached PowBase source archives, or perform canonical ingestion.

## Scope and Mapping

- One source entry produces one stable PowBase sample, measurement, pattern, and XY payload.
- Stable identifiers are source-aware: `POWBASE_SAM_<entry_id>`, `POWBASE_MEAS_<entry_id>`, and `POWBASE_PAT_<entry_id>`.
- Source labels remain literal nominal labels. Confirmed formulas are not assigned.
- `phase_character` remains `unknown` for all records.
- `structure_linkage` is `unlinked` with no candidate CIF or structure IDs.
- Intensity arrays are copied as parsed numeric values. No smoothing, normalization, interpolation, background subtraction, zero-shift correction, or silent trimming is performed.

## Results

| Measure | Count |
| --- | ---: |
| Selected inclusion records | 44 |
| Successfully parsed profiles | 44 |
| Prepared samples | 44 |
| Prepared measurements | 44 |
| Prepared patterns | 44 |
| Prepared XY payloads | 44 |
| Failed or quarantined records | 0 |
| Missing explicit wavelength | 38 |
| Explicit primary wavelength available | 6 |
| Validation errors | 0 |
| Stable identifier collisions | 0 |

All 44 records ready for MongoDB staging after this dry-run: `true`.
This statement means local source parsing and validation passed. No MongoDB staging or write was performed.

## Validation

- The audit parser selected the verified three-number 2θ header and numeric intensity block for each record.
- An independent block parser re-read the same member bytes and matched the intensity count and numeric values.
- The reconstructed axis has the source start, step, end, expected point count, finite values, and strictly increasing values.
- Exact source member and archive SHA256 values are retained in every canonical document's provenance.

## Wavelength Handling

Wavelength values were retained only when explicitly stated by the official index token or labeled source metadata. Radiation text such as `Cu-Kalpha` remains source text and was not converted into an inferred numeric wavelength.

## Potential Duplicates

Potential duplicates are reported for review only. No record was deduplicated by material name, formula, or phase identity.

- Same-label PowBase groups: 1
- Existing local matches: 2

```json
{
  "same_source_label_groups": [
    {
      "normalized_label": "alphakalf4",
      "entry_ids": [
        "66",
        "67",
        "68"
      ]
    }
  ],
  "existing_local_matches": [
    {
      "powbase_entry_id": "10",
      "matches": [
        {
          "source": "LAB",
          "path": "D:\\document\\aiformaterials\\crystaldb\\data\\powder\\lab\\manifests\\lab_xrd_manifest_v1.csv",
          "source_sample_label": "Al2O3-0.5",
          "nominal_element_ratio": "Al2O3"
        },
        {
          "source": "LAB",
          "path": "D:\\document\\aiformaterials\\crystaldb\\data\\powder\\lab\\manifests\\lab_xrd_manifest_v1.csv",
          "source_sample_label": "Al2O3-20",
          "nominal_element_ratio": "Al2O3"
        }
      ]
    },
    {
      "powbase_entry_id": "159",
      "matches": [
        {
          "source": "LAB",
          "path": "D:\\document\\aiformaterials\\crystaldb\\data\\powder\\lab\\manifests\\lab_xrd_manifest_v1.csv",
          "source_sample_label": "CaCuO2",
          "nominal_element_ratio": "CaCuO2"
        }
      ]
    }
  ],
  "deduplicated": false,
  "notes": [
    "Same-label and existing-local matches are review candidates only.",
    "No record was removed or merged by material name, formula, or phase."
  ]
}
```

## Outputs

- Dry-run JSON: `D:\document\aiformaterials\crystaldb\data\mappings\powbase_canonical_dryrun_v1.json`
- Validation CSV: `D:\document\aiformaterials\crystaldb\data\mappings\powbase_canonical_validation_v1.csv`
- Isolated staging root: `D:\document\aiformaterials\crystaldb\data\staging\powbase_canonical_v1`

No MongoDB write, production modification, source archive rewrite, Git staging, commit, or push was performed.
