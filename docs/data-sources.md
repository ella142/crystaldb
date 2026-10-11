# Data sources

CrystalDB integrates several diffraction and crystallographic source families.

The sources differ substantially in experimental modality, metadata
completeness, phase information, structure availability, and provenance
conventions. CrystalDB therefore does not assume that every source provides the
same type or level of information.

Source-specific identifiers and provenance are retained wherever possible, and
tracked mappings or manifests connect source records to CrystalDB entities.

This repository does not necessarily contain a complete mirror of each external
source collection. Large source datasets, raw files, and locally generated
scientific data may be stored separately from Git.

## RRUFF

RRUFF contributes mineralogical sample metadata, diffraction information,
crystallographic information, and bibliographic context used by CrystalDB
curation and structure-linkage workflows.

RRUFF source records include different diffraction origins. In particular,
source metadata distinguish experimentally measured powder diffraction records
from records for which a powder profile is described as calculated.

CrystalDB therefore does not treat every RRUFF diffraction record as an
experimental powder measurement.

RRUFF workflows in this repository include:

- source-record parsing;
- experimental powder-profile selection;
- metadata and phase-character curation;
- candidate structure retrieval;
- crystallographic compatibility checks;
- diffraction-based structure comparison;
- candidate-group resolution;
- rescue and review workflows;
- provenance and validation reporting.

RRUFF structure linkage is evidence-based.

A recovered, retrieved, or preferred CIF is not automatically interpreted as a
uniquely confirmed structure assignment. Candidate, grouped, and review states
are retained when the available evidence does not support a unique resolution.

## COD

The Crystallography Open Database (COD) is used primarily as a source of
crystallographic structure records.

COD workflows in CrystalDB include:

- CIF retrieval and import;
- source-ID mapping;
- crystallographic parsing;
- local structure indexing;
- duplicate and hash validation;
- candidate retrieval;
- provenance tracking.

Where available in the local source workflow, COD-associated single-crystal
reflection data may also be represented separately from crystallographic
structure records.

COD identifiers and CrystalDB internal identifiers remain distinct.

A COD structure record should not be interpreted as being linked to an
experimental CrystalDB measurement unless an explicit provenance-bearing
relation supports that association.

## opXRD

opXRD contributes experimental powder-diffraction records and associated source
metadata used by CrystalDB curation and integration workflows.

CrystalDB uses source-supported metadata to distinguish records and phase
information without assuming that every record in the complete external opXRD
collection is included in the local production database.

opXRD workflows include:

- source-record inventory;
- overlap checks against existing CrystalDB records;
- experimental-profile validation;
- phase-character assignment from source-supported phase information;
- canonical validation;
- integration of validated additional records;
- exclusion and audit reporting for records that cannot be deterministically
  reconstructed or validated.

Review, validation, exclusion, and production-integration outputs are kept
separate.

The presence of an opXRD mapping or integration report in this repository does
not imply that the entire external opXRD collection is redistributed through
CrystalDB.

## PowBase

PowBase contributes powder-diffraction records and heterogeneous
source-provided metadata.

CrystalDB workflows for PowBase include:

- source inventory and record review;
- experimental-profile reconstruction where source metadata support a
  deterministic interpretation;
- metadata completeness assessment;
- canonical validation;
- source-structure recovery;
- structure-linkage review;
- production-oriented integration;
- audit and rescue workflows for unresolved records.

Some PowBase records contain recoverable crystallographic or refinement-related
information, while others are primarily diffraction-profile records.

CrystalDB distinguishes source-provided information from structures or
annotations reconstructed during curation.

Audit, dry-run, rescue, validation, and integration artifacts represent
different workflow states and should not be interpreted as equivalent to one
another.

The repository is not intended to act as a complete mirror of the PowBase
source collection.

## DARA

DARA contributes experimental powder-diffraction data used in CrystalDB
multiphase and structure-linkage workflows.

The source contains diffraction records associated with precursor or mixture
interpretations, making it useful for representing cases in which one
experimental pattern may contain more than one crystalline phase.

CrystalDB retains DARA source identity and uses source-supported phase and
structure information when constructing local records and relationships.

The exact records used by a particular workflow should be determined from the
corresponding source manifest or integration report rather than inferred from a
generated filename.

## Laboratory XRD

Laboratory XRD represents locally acquired or supplied experimental powder
diffraction measurements.

Laboratory workflows may include:

- source-file inventory;
- format conversion;
- sample and measurement identification;
- repeated-measurement handling;
- pattern import;
- provenance mapping;
- metadata review.

A physical sample may have more than one measurement.

Filename-derived or laboratory-provided composition labels are preserved as
source or nominal-composition information and should not automatically be
interpreted as confirmed chemical formulas or phase identities.

Local laboratory data are environment-specific and are not assumed to be
available in a fresh Git checkout.

## Source roles in CrystalDB

The sources play different roles and should not be treated as interchangeable.

| Source | Primary role in CrystalDB |
| --- | --- |
| RRUFF | Mineralogical experimental powder diffraction, metadata, and evidence for structure linkage |
| COD | Crystallographic structures and associated crystallographic source records |
| opXRD | Experimental powder-diffraction records and source-supported phase information |
| PowBase | Powder-diffraction records with heterogeneous metadata and selected recoverable structural information |
| DARA | Experimental powder diffraction with precursor or multiphase context |
| Laboratory XRD | Locally acquired experimental powder-diffraction measurements |

A source may contribute more than one type of information, but the existence of
a structure record and the existence of an experimental measurement remain
conceptually separate.

## Experimental and structural data are separate

CrystalDB does not assume that a diffraction record and a crystallographic
structure are the same object.

For example:

```text
experimental measurement
        |
        v
pattern or reflection set

        separate from

crystallographic structure
```

When evidence supports an association, the connection is represented through a
provenance-bearing relation.

This design allows CrystalDB to retain:

- unresolved measurements;
- competing structure candidates;
- grouped candidate structures;
- incomplete structure coverage;
- missing metadata;
- source-specific uncertainty.

## Reading source mappings

The `data/mappings/` directory contains several classes of tracked artifacts,
including:

- external-to-CrystalDB identity maps;
- source inventories;
- candidate and recovery manifests;
- phase-character outputs;
- review records;
- validation reports;
- staging and integration summaries;
- release-related artifacts.

File names may contain terms such as:

- `audit`;
- `review`;
- `dryrun`;
- `rescue`;
- `validation`;
- `staging`;
- `integration`.

These terms describe workflow state.

They should not be interpreted as evidence that the corresponding records were
included in the production database.

Production status should be determined from the relevant manifest, validation
report, integration record, and database state.

## External source data

Many source collections are not distributed directly through this Git
repository.

Depending on the workflow, reproduction may require:

- separately obtained source datasets;
- local source archives;
- MongoDB databases;
- downloaded crystallographic files;
- laboratory data;
- network access to external scientific resources.

Historical paths stored in manifests should be interpreted as provenance
records rather than as portable filesystem locations.

See also:

- [Data model](data-model.md)
- [Curation workflow](curation-workflow.md)
- [Reproducibility](reproducibility.md)
- [Data directory](../data/README.md)