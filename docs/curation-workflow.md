# Curation workflow

CrystalDB uses a staged curation workflow to transform heterogeneous source
records into provenance-aware experimental diffraction and crystallographic
data.

The stages are conceptually ordered, but individual source workflows may omit,
repeat, or specialize particular stages. RRUFF, OPXRD, PowBase, DARA,
laboratory XRD, and crystallographic structure sources do not necessarily
follow identical processing rules.

```text
source data
    |
    v
ingest
    |
    v
normalize and stage
    |
    v
curate and review
    |
    v
recover and link
    |
    v
validate
    |
    v
integrate
    |
    v
export or release
```

The purpose of the workflow is not to force every record into a complete or
certain interpretation. Provenance, missing metadata, ambiguity, alternative
structure candidates, and unresolved cases are retained where supported by the
source evidence.

## 1. Ingest

Source files, identifiers, measurements, and structure records are acquired
from external collections or laboratory workflows.

Ingestion should preserve source identity wherever possible, including:

- source database or collection;
- source record identifiers;
- original filenames;
- acquisition or measurement metadata;
- source-provided structure identifiers;
- file hashes where available;
- source or archive provenance.

Raw source material may remain outside the Git repository.

Tracked manifests and mappings are used where appropriate to document which
source records and files were used by a workflow.

## 2. Normalize and stage

Source-specific formats are converted into representations that can be inspected
and processed consistently by CrystalDB.

Examples include:

- parsing source metadata;
- converting diffraction files into common representations;
- creating source inventories;
- assigning internal identifiers;
- preparing source-to-record mappings;
- preparing candidate canonical records;
- staging records for validation.

Staging data are intermediate or pre-production artifacts.

A staging record should not automatically be interpreted as a canonical,
validated, or production database record.

## 3. Curate and review

Curation evaluates source records and determines how available evidence should
be represented without inventing unsupported information.

Curation may consider:

- source identifiers and labels;
- measurement modality;
- experimental versus calculated origin;
- phase character;
- missing or conflicting metadata;
- source-provided structural information;
- candidate structure relationships;
- data quality or parsing issues;
- inclusion or exclusion decisions.

Review workflows may generate:

- audit tables;
- candidate lists;
- inclusion manifests;
- exclusion reasons;
- source-specific annotations;
- explicit unresolved cases;
- validation-ready records.

Review outputs are part of the provenance record and should not be silently
discarded when a later integrated record is produced.

## Phase character

For powder diffraction records, CrystalDB represents phase character separately
from structure linkage.

The formal values are:

- `single_phase`;
- `multi_phase`;
- `unknown`.

`unknown` means that the available source evidence is insufficient for a
reliable phase-character assignment.

It should not be interpreted as evidence that the sample is multiphase.

Phase character is assigned using source-supported evidence and may therefore
use different source-specific curation rules.

For example, explicit second-phase, contamination, mixture, or multiple-phase
evidence can support `multi_phase`, while the absence of such evidence should
not automatically be generalized across all sources.

## 4. Recover and link structures

Some experimental diffraction records do not arrive with a directly usable
crystallographic structure.

Recovery and linkage workflows therefore identify, retrieve, compare, or
construct candidate associations between experimental evidence and structure
records.

Evidence may include:

- source-provided structure information;
- source identifiers;
- mineral or material labels;
- chemical compatibility;
- unit-cell compatibility;
- space-group information;
- diffraction compatibility;
- bibliographic context;
- file provenance;
- curated review decisions.

A candidate with the highest numerical score is not automatically a confirmed
structure assignment.

Structure relationships remain explicit data objects rather than being embedded
implicitly into the experimental measurement.

### Relation-level resolution

Where candidate structures are resolved, CrystalDB may represent the outcome
using:

- `record`: one structure record is retained as the resolved representation;
- `group`: multiple near-equivalent or insufficiently separable structures are
  retained together;
- `review`: the available evidence does not support a resolved record or group.

These values describe structure-resolution outcome.

### Pattern-level structure linkage

At the powder-pattern level, `structure_linkage` summarizes the available
coverage or certainty of structure association using values such as:

- `complete`;
- `ambiguous`;
- `partial`;
- `unlinked`.

Relation-level resolution and pattern-level linkage describe different aspects
of the structure-linking process.

They should also remain separate from `phase_character`.

## 5. Validate

Validation evaluates whether curated or recovered records satisfy the
requirements of a particular workflow.

Validation may include checks for:

- source identity;
- file hashes;
- required metadata;
- missing-value behavior;
- duplicate records;
- conflicting source information;
- crystallographic consistency;
- unit-cell compatibility;
- diffraction compatibility;
- candidate consistency;
- provenance completeness;
- input/output manifest consistency;
- reproducibility of generated reports.

Validation artifacts are evidence about the data.

They are not themselves equivalent to the production dataset.

A validation result should be interpreted together with the corresponding input
manifest, workflow version, and scientific context.

## 6. Integrate

Validated records may be integrated into the CrystalDB production database or
prepared for a production-oriented data product.

Integration may include:

- creation of samples;
- creation of measurements;
- creation of powder patterns;
- creation of reflection sets;
- registration of structures;
- creation of provenance-bearing relations;
- assignment of phase-character metadata;
- assignment of structure-linkage metadata.

Preparation, dry-run, and staging workflows may create records with a similar
shape without changing the production database.

Therefore, the presence of an output file does not by itself demonstrate that a
production database update occurred.

Production integration should be supported by the corresponding manifests,
validation results, and integration reports.

## 7. Export or release

Export workflows create artifacts intended for access, distribution, indexing,
or release preparation.

Examples include:

- API-accessible records;
- indexes;
- downloadable diffraction products;
- structure files;
- release manifests;
- validation summaries;
- source and provenance documentation.

Release-oriented artifacts should identify, where applicable:

- the source records used;
- relevant manifests;
- validation status;
- code or workflow version;
- external scientific data required for reproduction;
- known exclusions or unresolved cases.

GitHub is not necessarily the distribution location for all large scientific
source or canonical data.

Tracked code, manifests, mappings, and documentation may describe data that are
stored or distributed separately.

## Production versus intermediate artifacts

Operational state should be inferred from the workflow and its supporting
records rather than from a filename alone.

In general:

- `integrate_*` workflows may perform or prepare production database updates;
- release-oriented `export_*` and `build_*` workflows may create distribution
  or access artifacts;
- `stage_*`, `prepare_*`, and `dryrun_*` workflows normally create intermediate
  or pre-production artifacts;
- `audit_*`, `review_*`, `calibrate_*`, `pilot_*`, `rescue_*`, and diagnostic
  workflows normally produce curation, validation, or investigative evidence;
- validation reports document checks but are not the scientific data product
  themselves;
- archive material represents a historical or frozen state rather than the
  current production state.

A CSV, JSON file, Markdown summary, or mapping should therefore not be described
as a production dataset unless its corresponding integration state supports
that interpretation.

## Source-specific workflows

The common workflow provides a shared framework, but source-specific evidence
must be preserved.

Different sources may provide different combinations of:

- diffraction measurements;
- crystallographic structures;
- phase information;
- wavelength or radiation metadata;
- sample descriptions;
- bibliographic references;
- source identifiers;
- calculated versus experimental profiles.

CrystalDB does not force these heterogeneous sources to provide identical
metadata completeness.

Instead, source-specific evidence is normalized into a common data model while
retaining provenance, uncertainty, and missingness.

See [`data-sources.md`](data-sources.md) for source-specific context.

## Scientific interpretation

Three questions should remain conceptually separate during curation:

```text
What experimental evidence is present?
        |
        v
measurement / pattern / reflection set

How many crystalline phases are supported?
        |
        v
phase_character
single_phase / multi_phase / unknown

What structure relationship is supported?
        |
        v
relation-level resolution
record / group / review

        and

pattern-level structure_linkage
complete / ambiguous / partial / unlinked
```

One state should not be inferred automatically from another.

For example, a `single_phase` powder pattern may still have an `ambiguous`
structure linkage, and a `multi_phase` pattern may have only `partial` structure
coverage.

This separation is central to the CrystalDB curation model.

## Related documentation

- [Data model](data-model.md)
- [Data sources](data-sources.md)
- [Reproducibility](reproducibility.md)
- [API documentation](api/README.md)