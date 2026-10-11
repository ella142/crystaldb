# Scripts

The `scripts/` directory contains the executable workflows used to ingest,
curate, recover, link, validate, integrate, and export CrystalDB data.

These scripts support the construction and validation of the database, but they
should not be interpreted as a single linear pipeline. Different data sources
and curation tasks use different subsets of the available workflows.

## Where should I start?

For most users, the following documentation provides a better starting point
than running individual scripts directly:

- API setup and usage: [`docs/api/README.md`](../docs/api/README.md)
- Data model: [`docs/data-model.md`](../docs/data-model.md)
- Curation workflow: [`docs/curation-workflow.md`](../docs/curation-workflow.md)
- Reproducibility: [`docs/reproducibility.md`](../docs/reproducibility.md)

The scripts in this directory are primarily workflow, curation, validation, and
provenance tools. A script should only be interpreted in the context of its
inputs, generated manifests, validation outputs, and source-specific
documentation.

## Workflow groups

| Stage | Typical responsibilities | Representative scripts |
| --- | --- | --- |
| Ingest and acquisition | Download, parse, import, or stage source records and diffraction measurements. | `download_cod_candidates.py`, `import_cod_cif.py`, `import_rruff_dif.py`, `import_lab_powder_xrd.py`, `stage_lab_xrd.py` |
| Curate and review | Inspect source metadata, assign review states, identify inclusion or exclusion cases, and prepare curation manifests. | `audit_powbase.py`, `review_powbase_v1.py`, `infer_phase_character_v1.py`, `review_high_priority_35_diffraction_v1.py` |
| Recover and link | Search for candidate structures, recover missing structure records, compare crystallographic evidence, and annotate measurement–structure relationships. | `rruff_cif_recovery_v3.py`, `rank_rruff_candidates.py`, `batch_auto_match_rruff.py`, `recover_powbase_source_structures_v1.py` |
| Validate | Check provenance, hashes, crystallographic consistency, diffraction compatibility, coverage, and reproducibility of derived results. | `validate_cod_duplicate_sha256.py`, `validate_powbase_candidate_canonical_v1.py`, `audit_cell_provenance_v1.py`, `cod_network_diagnostics_v3.py` |
| Integrate | Write validated and curated records into CrystalDB production or production-oriented database workflows. | `integrate_powbase_production_v1.py`, `integrate_powbase_source_structures_production_v1.py`, `integrate_opxrd_validated_additional_v1.py` |
| Stage and prepare | Prepare intermediate or pre-production records for review, canonicalization, or later database integration. | `prepare_powbase_canonical_v1.py`, `stage_powbase_mongodb_v1.py`, `dryrun_powbase_source_structure_integration_v1.py` |
| Export and release | Produce indexes, API artifacts, downloadable products, or release-oriented summaries. | `build_api_pilot_v01.py`, `build_cif_index.py`, `export_opxrd_multiphase_candidates_v1.py`, `export_rruff_multiphase_v1.py` |
| Maintenance and diagnostics | Inspect local inventories, investigate inconsistencies, maintain source-specific indexes, or diagnose network and data-access issues. | `build_cod_local_inventory_v3.py`, `build_cod_conflict_inventory_v3.py`, `collect_opxrd_cod_pairs.py`, `cod_network_diagnostics_v3.py` |

Pilot, rescue, audit, and exploratory scripts are also retained where they
provide useful provenance or document important curation decisions. They should
not be mistaken for the maintained pytest suite or for a guaranteed
end-to-end release command.

## Production versus intermediate workflows

Script names alone do not determine whether an output should be treated as a
production result.

In general:

- `integrate_*` scripts may participate directly in production database updates,
  but only when their associated inputs and validation results support the
  operation.
- release-oriented `export_*` and `build_*` scripts may generate artifacts used
  for distribution, indexing, or API access.
- `stage_*`, `prepare_*`, and `dryrun_*` scripts normally generate intermediate
  or pre-production data.
- `audit_*`, `review_*`, `calibrate_*`, `pilot_*`, `rescue_*`, and diagnostic
  scripts usually generate evidence for curation, validation, or investigation
  rather than final production records.
- a mapping, CSV, JSON file, or validation report does not by itself indicate
  that the corresponding records were written to the production database.

Production-oriented outputs should therefore be interpreted together with their
source manifests, validation reports, and integration records.

## Running scripts

Scripts are normally run from the repository root after installing the
CrystalDB package.

For scripts that expose command-line help:

```bash
python scripts/<script-name>.py --help
```

Not every historical workflow exposes the same command-line interface. Some
scripts depend on:

- local source datasets;
- MongoDB;
- network access;
- source-specific files outside the Git repository;
- environment variables or explicit input paths.

Before running a workflow, inspect the script's expected inputs and defaults and
refer to the relevant source or reproducibility documentation.

## Portability

Some older scripts and exploratory workflows were originally written against
machine-specific local paths or external source directories.

These scripts remain useful for provenance and historical reproducibility, but
they should not be treated as portable entry points unless their input paths
are supplied explicitly or replaced with environment-based configuration.

The long-term goal is to keep reusable CrystalDB logic inside `src/crystaldb/`
and use `scripts/` primarily as workflow entry points.

## Implementation note

The scripts are currently retained in a mostly flat directory because several
historical workflows, tests, and script-to-script imports depend on the existing
paths.

Future repository cleanup may group scripts by workflow stage, but such changes
should be made together with updates to imports, tests, documentation, and
hard-coded paths so that scientific results and reproducibility are not
affected.