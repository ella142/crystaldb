# Data directory

The `data/` directory contains CrystalDB data manifests, source mappings,
curation outputs, validation records, and metadata used to document how
experimental diffraction measurements are linked to crystallographic
structures.

Large scientific source collections and generated working data are generally
not distributed through Git. Their provenance, identifiers, and processing
history are represented through tracked manifests, mappings, validation
reports, and documentation where appropriate.

## Directory overview

| Directory | Role |
| --- | --- |
| `mappings/` | Source identifiers, cross-source mappings, candidate structure links, curation manifests, validation outputs, and release-related records. |
| `raw/` | Raw or near-raw source material used during ingestion and curation. Usually stored locally and not tracked in Git. |
| `staging/` | Intermediate data prepared for review, validation, or integration. |
| `canonical/` | Canonicalized data products generated from source records for use in CrystalDB workflows. |
| `archive/` | Historical snapshots, frozen audit outputs, and rollback material. |
| `powder/` | Powder-diffraction-related local data products. |
| `single_crystal/` | Single-crystal diffraction and reflection-related local data products. |
| `multi-phase/` | Multiphase curation, review, or integration material. |
| `structure/` | Structure-oriented local data and derived crystallographic records. |

Not every directory is present in every checkout. Some directories may exist
only in local development or production environments and may contain files
that are intentionally excluded from Git.

## Tracked repository artifacts

The most important tracked data-facing artifacts are:

- source and identifier mappings;
- curation and inclusion manifests;
- structure-linkage and candidate-resolution records;
- phase-character annotations;
- validation and audit summaries;
- integration and release-related reports;
- documentation describing provenance and processing decisions.

These files document how CrystalDB records were obtained, transformed,
validated, and linked. Their presence does not imply that all referenced raw,
canonical, or source data are distributed through this repository.

## `data/mappings/`

The `data/mappings/` directory contains machine-readable records produced
during source integration and curation. These include:

- source identity and ID mappings;
- candidate and structure-linkage results;
- phase-character and review outputs;
- validation and calibration records;
- recovery and rescue results;
- staging and integration summaries;
- release-related manifests.

Some files represent intermediate or audit states, while others describe
production-oriented outputs. Source-specific context is documented in
[`docs/data-sources.md`](../docs/data-sources.md), and the overall curation
logic is described in
[`docs/curation-workflow.md`](../docs/curation-workflow.md).

## External and non-Git data

Some CrystalDB workflows depend on external source collections, local
scientific data stores, or MongoDB databases that are not distributed through
this Git repository.

Depending on the workflow, a local installation may require configuration such
as:

- `CRYSTALDB_DATA_ROOT`;
- MongoDB connection settings;
- source-specific input paths;
- locally obtained source datasets.

Paths recorded in historical manifests describe the environment in which those
records were generated and should not be assumed to be portable across
machines.

Raw, canonical, staging, archive, and other large scientific files should be
treated as source or generated data products rather than as Git-distributed
repository content.

## Provenance and interpretation

CrystalDB preserves provenance and uncertainty explicitly. A tracked mapping
or linkage record should not automatically be interpreted as a confirmed
one-to-one structure assignment.

Users should distinguish among:

- source provenance;
- diffraction measurements;
- crystallographic structures;
- candidate or resolved structure links;
- phase character;
- validation and review status.

See [`docs/data-model.md`](../docs/data-model.md) and
[`docs/curation-workflow.md`](../docs/curation-workflow.md) for the formal data
model and interpretation rules.