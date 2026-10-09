# OPXRD Source-Label Overlap Check v1

- Production OPXRD experimental patterns: 845
- Source collection checked: `opxrd.patterns`
- Source-labeled OPXRD records checked: 2179
- Source-labeled records overlapping the existing 845: 845
- Source-labeled records outside the existing 845: 1334
- Outside records with valid experimental diffraction profiles: 1334
- Outside records without valid experimental diffraction profiles: 0
- Outside records that could be additional CrystalDB production candidates: 1334
- Duplicate source IDs observed in checked source-labeled records: 0
- Profile criterion: numeric source `xrd.two_theta` and `xrd.intensity` arrays,
  equal length, at least 2 points; records marked `is_simulated=true` would be excluded.
- Source-labeled criterion: source `phase_count >= 1`; `phase_count=0` records
  were excluded.

## Source Collections

```json
{
  "patterns": {
    "estimated_documents": 92552,
    "production_source_records_from_pair_manifest": 845,
    "source_labeled": 2179,
    "overlap_existing_845": 845,
    "outside_existing_845": 1334
  }
}
```

Exact outside source IDs are in the CSV `source_id` column; no production duplicate rows are included.

No MongoDB writes were performed. No CIF matching was performed.
