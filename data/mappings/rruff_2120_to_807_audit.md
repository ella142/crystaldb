# RRUFF Original Frozen Experimental Curation Audit

Audit date: 2026-10-05. This is a read-only historical audit. No CIF retrieval, diffraction matching, MongoDB writes, old mapping edits, or manuscript edits were performed.

===== FUNNEL =====

| Stage | Count | Definition |
|---|---:|---|
| DIF records | 3013 | `rruff.dif` documents; matches coverage file length 3013 |
| Sample-structure candidate available | 2211 | Frozen coverage status exactly `sample_structure_found` |
| Valid XY universe | 2120 | Valid `xy_raw` record plus `sample_structure_found` coverage |
| Unique measurements | 2120 | Unique `filename_sample_id` within the valid XY universe |
| Curated experimental profiles | 807 | Frozen `rruff_experimental_resolution_v1.json` records |

The remembered `2120` and `807` are exact in the current frozen data, not merely approximate. `807` is directly materialized in the frozen resolution JSON. No standalone historical file containing a `2120` list was found; the `2120` membership is therefore reconstructed from the frozen coverage status plus the historical RAW-validity rule, and the CSV marks those reconstructed rows explicitly.

The first funnel loss is `3013 - 2211 = 802` records without `sample_structure_found`: 802. The second is `2211 - 2120 = 91` records with a frozen sample-structure candidate but no usable `xy_raw` record. All 91 are missing a RAW record; none are an invalid RAW array in this stage. The final loss is `2120 - 807 = 1313` records excluded by the exact clean experimental description rule.

Coverage-status breakdown for the first loss:

| `needs_review_only` | 240 |
| `no_cod_candidates` | 207 |
| `no_finder_candidate` | 102 |
| `reference_structure_only` | 64 |
| `retrieval_too_broad` | 189 |
| `sample_structure_found` | 2211 |

===== 2120 → 807 EXCLUSIONS =====

The frozen v1 script has one historical primary rule at this step: `DIFFRACTION SAMPLE DESCRIPTION` must be exactly one of four strings: `Powder`; `Powder, using Mo radiation`; `Powder, cell parameters are from single crystal`; `Powder using Cu radiation`. Therefore the historically confirmed primary exclusion count is:

| Historical primary exclusion | Count |
|---|---:|
| `description_not_in_clean_experimental_allowlist` | 1313 |
| Curated by the allow-list | 807 |

A descriptive audit of those 1313 excluded valid-XY records gives this mutually exclusive breakdown:

| Reconstructed semantic reason | Count |
|---|---:|
| Calculated/simulated powder profile | 1284 |
| Noncanonical experimental description, mainly mixed/impure/extra-phase wording | 28 |
| Origin uncertain or metadata insufficient | 1 |
| Total | 1313 |

The exact historical selection rule is confirmed; the semantic labels above are audit annotations, not replacement historical rules.

Examples:
- no sample-structure candidate / coverage exclusion: `R040002` (`Powder`; no `sample_structure_found`), `R040009` (`Powder`; no `sample_structure_found`), `R040018` (`Powder`; no `sample_structure_found`), `R040027` (`Powder`; no `sample_structure_found`), `R040029` (`Powder`; no `sample_structure_found`)
- candidate available but no RAW XY: `R040140` (no usable `xy_raw` record), `R040155` (no usable `xy_raw` record), `R040164` (no usable `xy_raw` record), `R050147` (no usable `xy_raw` record), `R050151` (no usable `xy_raw` record)
- calculated profile: `R040163` (`Single crystal, powder profile is calculated`), `R040177` (`Single crystal, powder profile is calculated`), `R040180` (`Single crystal, powder profile is calculated`), `R050018` (`Single crystal, powder profile is calculated`), `R050088` (`Single crystal, powder profile is calculated`)
- noncanonical experimental / mixed description: `R040063` (`Powder, ~ 52% actinolite, 45% talc, 3% chlorite`), `R040064` (`Powder, ~96% actinolite, 4% chlorite`), `R040067` (`Powder, mixed with ~14 wt % wavellite`), `R050028` (`Powder, mixed with adamite`), `R050079` (`Powder, the (00l) peaks of muscovite are also present`)
- origin uncertain: `R210019` (`Single crystal`)
- invalid RAW XY: `R060379` / `R060379-9` (`Powder, using Mo radiation`; empty XY arrays)

These exclusions do not imply poor data quality. The largest class, 1284 records, has valid XY arrays but describes calculated powder profiles rather than measured experimental profiles. Mixed or extra-phase descriptions are also valid measurements, but they are outside the single clean experimental resolution subset. The one uncertain-origin case is excluded conservatively.

===== RAW / PROCESSED =====

Across the complete MongoDB XY inventory:

| Statistic | Count |
|---|---:|
| `xy_raw` documents | 3019 |
| `xy_processed` documents | 1484 |
| RAW and processed share `filename_sample_id` | 1230 |
| RAW-only measurement IDs | 1789 |
| Processed-only measurement IDs | 254 |
| Unique measurement IDs after representation collapse | 3273 |
| Representation rows collapsed | 1230 |
| Simple-valid RAW documents | 3018 |
| Invalid/empty RAW documents | 1 |

Thus RAW and processed are two representations of a measurement when their `filename_sample_id` is the same. They are not counted as two independent measurements. In the frozen 807 records, 786 have a processed representation and 21 do not.

===== PROFILE ORIGIN =====

Over the 2120 valid-XY universe, using the existing descriptive origin classifier only for audit:

| Profile origin | All 2120 | Entered 807 |
|---|---:|---:|
| experimental | 835 | 807 |
| calculated | 1284 | 0 |
| uncertain | 1 | 0 |

Calculated/simulated profiles therefore account for 1284 / 2120 = 60.57%. The frozen v1 pipeline did not run diffraction matching to decide this; it excluded them from the experimental subset by description metadata.

For context, across all simple-valid `xy_raw` documents, the same classifier gives experimental=1306, calculated=1702, uncertain=10. This broader inventory is not the 2120 universe.

===== PHASE CHARACTER =====

The original frozen resolution script did not assign a `single_phase` field. The existing phase parser can identify explicit multi-phase wording, but absence of that wording is not proof of single phase. Accordingly, the historically defensible counts are:

| Phase character | All 2120 | Entered 807 |
|---|---:|---:|
| single_phase | 0 | 0 |
| multi_phase | 27 | 0 |
| unknown | 2093 | 807 |

There are 27 explicit multi-phase records in the 2120 universe, and all 27 are absent from the 807. Of these, 26 are experimental mixed/extra-phase descriptions and one is also calculated. The remaining 2093 are not explicitly multi-phase; they should not be re-labeled as single phase without a new curation rule.

Therefore multiphase content was excluded in practice by the exact description allow-list, but the frozen pipeline did not implement a separate named `multiphase` exclusion step.

===== IMPORTANT INTERPRETATION =====

- `2120` is a count of unique RRUFF measurement keys (`filename_sample_id`) that have a valid RAW XY array and a frozen `sample_structure_found` status. It is not a count of COD CIFs, and it is not the count of all valid `xy_raw` documents.
- `807` is a count of RAW experimental measurement records retained by the frozen exact-description allow-list. It is not a count of unique CIFs.
- No diffraction residual, peak count, zero-shift, or candidate-separability threshold was applied in the 2120-to-807 curation step. Those belong to later validation layers and were not rerun here.
- The original script also requires nonempty/equal-length `two_theta` and `intensity`, requires `sample_id` and `filename_sample_id`, uses `xy_raw` as the source collection, and treats processed data only as a paired representation.
- The broad Mongo inventory contains one invalid/empty RAW record (`R060379` / `R060379-9`) and five simple-valid RAW records with a missing diffraction description. These are outside the 2120 universe; they are not hidden losses inside 2120→807.
- `refinement_data` (1175) and `refinement_output` (1176) were inspected as ancillary collections but are not inputs to the frozen 2120→807 definition.

===== RECONCILIATION =====

| Check | Result |
|---|---:|
| DIF/coverage records | 3013 |
| Minus no `sample_structure_found` | -802 |
| Sample-structure candidate records | 2211 |
| Minus candidate records without usable RAW XY | -91 |
| Valid XY universe | 2120 |
| Minus exact-description exclusions | -1313 |
| Frozen curated profiles | 807 |
| `2120 - 1313 = 807` | 807 |

All 807 frozen resolution records reconcile to the valid XY universe by `(sample_id, filename_sample_id)`, with no unresolved ID remainder.

Exact source records/files used:

1. `scripts/build_rruff_experimental_resolution_v1.py` for the frozen selection rules, exact four-description allow-list, valid XY predicate, RAW-only source, and RAW/processed pairing policy.
2. `data/mappings/rruff_experimental_resolution_v1.json` for the frozen 807 record set and the historical 786/21 representation summary.
3. `data/mappings/cod_coverage_results_full_v1.json` for the 3013 frozen coverage records and `sample_structure_found` status counts.
4. Read-only MongoDB database `rruff`, collections `dif`, `xy_raw`, and `xy_processed` for the source counts and representation inventory.
5. `scripts/export_rruff_multiphase_v1.py` only for descriptive origin/phase annotations in this audit; these annotations were not used to rewrite the frozen result.

Safety status: MongoDB modified NO; old frozen outputs modified NO; old mappings modified NO; candidate search rerun NO; diffraction matching rerun NO; manuscript modified NO.
