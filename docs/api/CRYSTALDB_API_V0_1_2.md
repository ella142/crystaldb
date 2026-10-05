# CrystalDB API v0.1.2 Contract

## Scope

Base path: `/api/v1`

CrystalDB exposes stable scientific concepts rather than Mongo collection
names. The public resources are `patterns`, `structures`, `measurements`,
`samples`, `reflection-sets`, `sources`, `search`, `stats`, and `releases`.
The v0.1 API is read-only.

The API describes provenance-aware experimental diffraction data. It does not
turn every record into a forced structure match. Missing, ambiguous, and
partial relations remain explicit.

## Scientific semantics

- `data_origin` is `experimental` for the v1 data scope.
- `modality` is `powder_xrd` or `single_crystal_xrd`.
- `phase_character` is `single_phase`, `multi_phase`, or `unknown`.
- `dataset_role` uses `single_phase_precursor`,
  `precursor_mixture_benchmark`, `raw`, or `canonical` in this pilot.
  `reaction_product_benchmark` is reserved but is not populated.
- `structure_linkage.status` is `complete`, `partial`, `ambiguous`, or
  `unlinked`.
- `structure_linkage.coverage` is `complete`, `partial`, or `none`;
  `structure_linkage.certainty` is `resolved`, `ambiguous`, or `unknown`.
  These axes are independent: partial coverage can coexist with ambiguous
  candidate identity.
- Candidate structure matches are returned in
  `structure_linkage.candidate_structure_ids`. A phase component can expose
  multiple `structure.structure_ids`; `structure.structure_id` is null when
  the candidate identity is ambiguous.
- Wavelength and radiation are null unless established by source metadata.
- A powder pattern is not a single-crystal reflection set.
- A single-crystal measurement is not the same thing as a single-phase
  sample.
- A multiphase pattern can have multiple phase components and does not imply
  one mixture CIF.
- Unknown fraction basis is returned as `unknown`; it is never silently
  interpreted as weight fraction.

## Resources

### Pattern

`GET /api/v1/patterns`

Supported filters:

- `source`
- `modality`
- `phase_character`
- `component_formula`
- `structure_linkage`
- `dataset_role`
- `structure_id` (matches registered pattern and phase linkage data)
- `limit` (default 50, maximum 500)
- `cursor`

Response:

```json
{
  "items": [],
  "meta": {
    "count": 0,
    "next_cursor": null
  }
}
```

`GET /api/v1/patterns/{pattern_id}` returns metadata only. XY arrays are
served separately:

- `GET /api/v1/patterns/{pattern_id}/xy`
- `GET /api/v1/patterns/{pattern_id}/xy?format=csv`
- `GET /api/v1/patterns/{pattern_id}/xy?format=txt`

The XY endpoint returns canonical experimental values. It does not smooth,
normalize, resample, interpolate, or subtract background.

### Structure

- `GET /api/v1/structures`
- `GET /api/v1/structures/{structure_id}`
- `GET /api/v1/structures/{structure_id}/cif`

The CIF endpoint serves only a registered relative file key resolved below
`CRYSTALDB_DATA_ROOT`. It never generates a CIF during a request.

### Measurement and sample

- `GET /api/v1/measurements/{measurement_id}`
- `GET /api/v1/samples/{sample_id}`

A sample can have multiple measurements, and a measurement can have one or
more representations. DARA 2 minute and 8 minute scans of one precursor
mixture share one `sample_id`; each scan has its own `measurement_id` and
`pattern_id`. Canonical DARA single-phase precursor TXT records are also
included when their dataset provenance identifies them as single precursors.

DARA measurement `step_size` and `anode` values come from explicit canonical
source metadata when present. They are never inferred from point count or
wavelength.

### Reflection set

- `GET /api/v1/reflection-sets`
- `GET /api/v1/reflection-sets/{reflection_set_id}`
- `GET /api/v1/reflection-sets/{reflection_set_id}/hkl`

Reflection sets describe single-crystal HKL data. Complete HKL rows are not
embedded in metadata responses.

### Source, search, statistics, release

- `GET /api/v1/sources`
- `GET /api/v1/search?q=TiO2`
- `GET /api/v1/stats`
- `GET /api/v1/releases`

Search is a bounded-field Mongo text search over indexed or explicitly
selected metadata fields. Arbitrary Mongo queries are not accepted.

## Phase components

Each phase component may include:

```json
{
  "name": null,
  "formula": null,
  "fraction": {
    "value": null,
    "basis": "unknown"
  },
  "role": null,
  "structure": {
    "structure_id": null,
    "structure_ids": [],
    "status": null,
    "coverage": "none",
    "certainty": "unknown"
  }
}
```

Structure responses expose `atom_site_count`, defined as the number of rows in
the CIF `_atom_site` loop. It is not a unit-cell-expanded atom count.

The API keeps phase provenance alongside the scientific value. Typical
examples include `source_ground_truth` plus `known_precursor_mixture` for
DARA mixtures and `known_single_precursor` only for DARA records in the
dataset's single-phase precursor group, `source_annotation` plus
`diffraction_sample_description` for RRUFF, and `source_metadata` for OPXRD.

Structure provenance describes the structure source record and its registered
CIF/bibliography. Pattern-to-structure evidence is kept separately in the
`relations` collection and is not copied into structure provenance.

## IDs and pagination

IDs are source-aware and stable within the API contract, for example:

- `RRUFF_PAT_R040043_1`
- `DARA_PAT_In2O3_..._2min` and `DARA_PAT_In2O3_..._8min`
- `DARA_PAT_TiO2_SINGLE_PRECURSOR`
- `OPXRD_PAT_CNRS_pattern_0`
- `STR_COD_1100908`
- `REFL_COD_1100908`

Pagination is cursor-based and sorted by the public resource ID. Cursors are
opaque URL-safe values. Mongo `ObjectId` is not a public API identifier.

## Errors

- `200`: success
- `400`: invalid cursor or registered file key
- `404`: resource or registered file not found
- `422`: request validation error
- `503`: database unavailable
- `500`: unexpected server error

Production responses do not include filesystem paths, Mongo connection URIs,
or Python tracebacks.

## Configuration

- `CRYSTALDB_MONGO_URI`, default `mongodb://localhost:27017`
- `CRYSTALDB_MONGO_DB`, default `crystaldb_api_pilot`
- `CRYSTALDB_DATA_ROOT`, default repository `data` directory
- `CRYSTALDB_CORS_ORIGINS`, default `http://localhost:3000`

