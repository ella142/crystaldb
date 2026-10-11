# CrystalDB data model

CrystalDB separates measured diffraction evidence, crystallographic structure
records, and the relationships proposed between them.

This separation allows provenance, ambiguity, missing metadata, and review
history to be preserved without forcing every experimental record into one
certain structural interpretation.

## Entities

### Sample

A sample identifies the material or specimen described by a source or
laboratory workflow.

A sample may contain:

- source-specific identifiers;
- labels or nominal composition information;
- sample descriptions;
- provenance metadata;
- links to one or more measurements.

A sample is not necessarily single phase. A sample-level record should not be
interpreted as proof that every associated measurement represents one pure
crystalline phase.

### Measurement

A measurement records an experimental observation and its acquisition context.

Measurement metadata may include:

- diffraction modality;
- source;
- instrument or laboratory information;
- wavelength or radiation metadata when available;
- links to the corresponding sample;
- provenance information.

The measurement is an evidence-bearing entity. It should not be replaced by an
inferred structure assignment.

Multiple measurements may be associated with the same physical sample.

### Pattern

A pattern represents an experimental powder diffraction pattern or profile
associated with a powder-diffraction measurement.

It is intentionally distinct from a single-crystal reflection set.

Pattern records may contain:

- diffraction axes;
- measured intensities;
- source-file references;
- acquisition metadata;
- provenance information.

Pattern metadata can be incomplete. Missing wavelength, radiation, scaling,
or phase-related metadata remains unknown unless supported by source evidence.

### Structure

A structure is a crystallographic structural record, commonly associated with a
source identifier and a CIF or equivalent crystallographic representation.

Structure records may contain:

- unit-cell parameters;
- symmetry information;
- atomic coordinates;
- composition-related metadata;
- source identifiers;
- file provenance.

A structure may be linked to experimental diffraction evidence without being
the uniquely confirmed identity of that measurement.

### Reflection set

A reflection set represents indexed or observed single-crystal reflection data.

It is intentionally distinct from a powder diffraction pattern.

A reflection set may contain:

- Miller indices;
- reflection intensities or related quantities;
- experimental metadata;
- source identifiers;
- provenance information.

A single-crystal measurement and a reflection set may be related, but they are
not interchangeable entities.

### Source

A source identifies the origin of a CrystalDB record.

A source may represent:

- an external scientific database;
- a published data collection;
- a laboratory collection;
- a source file or archive family;
- another identifiable provenance origin.

Source records allow entities from different collections to retain their own
identifiers, metadata conventions, and provenance.

### Relation

A relation records an explicit association between CrystalDB entities.

Relations are especially important for linking experimental diffraction
evidence to crystallographic structures.

Relations are stored separately from the entities themselves so that
provenance, evidence, uncertainty, alternative interpretations, and review
history can be preserved.

A relation may represent:

- a source-provided association;
- a curated structure link;
- a candidate structure relationship;
- a relationship supported by crystallographic or diffraction evidence;
- another provenance-bearing connection between records.

The existence of a relation does not by itself imply that a structure
assignment is unique or certain.

## Structure linkage and resolution

CrystalDB keeps structure-linkage interpretation separate from the underlying
sample, measurement, pattern, reflection-set, and structure records.

Evidence supporting a structure relationship may include:

- source metadata;
- crystallographic cell comparisons;
- chemical compatibility;
- diffraction comparisons;
- bibliographic context;
- file hashes;
- curated review decisions.

A candidate list or preferred candidate is not automatically equivalent to a
confirmed one-to-one structure assignment.

### Relation-level resolution

For workflows that resolve candidate structures, CrystalDB may represent the
resolution state using:

- `record`: one structure record is retained as the resolved representation;
- `group`: multiple near-equivalent or insufficiently separable structure
  records are retained together;
- `review`: the available evidence does not support a resolved record or group.

These values describe the outcome of structure-resolution logic.

### Pattern-level structure linkage

At the powder-pattern level, `structure_linkage` summarizes the coverage or
certainty of the available structure association.

Values may include:

- `complete`;
- `ambiguous`;
- `partial`;
- `unlinked`.

These values describe pattern-level linkage and should not be interpreted as
relation-resolution states or phase-character values.

For example, a powder pattern may have a known single-phase interpretation
while still having an ambiguous structure link.

## Phase character

Phase character describes the best-supported interpretation of the crystalline
phase content represented by a powder diffraction record.

CrystalDB uses the formal values:

- `single_phase`;
- `multi_phase`;
- `unknown`.

`single_phase` means that the available source-supported interpretation
represents one crystalline phase.

`multi_phase` means that the available source-supported interpretation
indicates more than one crystalline phase.

`unknown` means that the available source evidence is insufficient for a
reliable phase-character assignment.

`unknown` should not be interpreted as evidence for a multiphase sample.

Phase character is independent of structure-linkage status.

For example:

- a `single_phase` pattern may have an `ambiguous` structure linkage;
- a `multi_phase` pattern may have only `partial` structure coverage;
- an `unknown` phase-character record may still retain source or candidate
  structure information.

Phase-character assignments retain provenance and should be interpreted
together with the underlying measurement and source metadata.

## Provenance

Provenance is retained throughout CrystalDB wherever source information is
available.

Provenance may include:

- source database or collection;
- source record identifiers;
- original filenames;
- file hashes;
- processing or conversion steps;
- generated manifests;
- validation reports;
- curation decisions;
- integration history.

Derived or curated metadata should remain distinguishable from values explicitly
provided by the source.

## Missing metadata

Unknown values are scientifically meaningful.

CrystalDB workflows do not silently insert a default wavelength, radiation
type, composition basis, phase fraction, structure assignment, or other
metadata merely to make a record appear complete.

Downstream code and users should distinguish among at least:

- values directly supported by source evidence;
- values inferred or curated with documented justification;
- unavailable or unknown values;
- values that are not applicable.

Missingness should therefore be preserved as part of the dataset rather than
treated automatically as an error.

## Measurement and structure are different objects

A central design principle of CrystalDB is that experimental diffraction
evidence and crystallographic structures are not the same object.

For powder diffraction:

```text
Sample
  |
  v
Measurement
  |
  v
Pattern
  |
  v
Relation / linkage
  |
  v
Structure candidate(s)
```

For single-crystal diffraction:

```text
Sample
  |
  v
Measurement
  |
  v
Reflection set
  |
  v
Relation / linkage
  |
  v
Structure
```

The relation between diffraction evidence and structure is therefore explicit
and inspectable rather than being assumed implicitly.

## Independent interpretation dimensions

Several CrystalDB fields describe different scientific questions and should not
be collapsed into one status.

### Diffraction modality

Describes the type of experimental diffraction evidence, for example:

- powder diffraction;
- single-crystal diffraction.

### Phase character

Describes how many crystalline phases are supported by the available source
evidence:

- `single_phase`;
- `multi_phase`;
- `unknown`.

### Structure resolution

Describes the outcome of structure-candidate resolution:

- `record`;
- `group`;
- `review`.

### Structure linkage

Describes pattern-level structure coverage or certainty:

- `complete`;
- `ambiguous`;
- `partial`;
- `unlinked`.

These dimensions answer different questions.

A record should not be assigned one value merely because of the state of
another dimension.

## API vocabulary

The API exposes fields and resources that make these distinctions queryable.

Examples include:

- `data_origin`;
- `modality`;
- `phase_character`;
- `dataset_role`;
- `structure_linkage`;
- provenance and source identifiers.

The current API contract is documented in:

[`api/CRYSTALDB_API_V0_1_2.md`](api/CRYSTALDB_API_V0_1_2.md)

The API representation should preserve the same distinction between measured
evidence, structures, provenance, phase interpretation, and linkage uncertainty
described in this document.