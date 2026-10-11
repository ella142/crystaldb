# CrystalDB

CrystalDB is a provenance-aware research database for experimental diffraction
measurements and crystallographic structures. It is designed to keep measured
evidence, source records, structure records, and the links between them
separate and inspectable.

The repository is intended for:

- researchers who need to inspect diffraction evidence and structure links;
- curators who need to review source records and unresolved assignments;
- developers who need to run the API, web interface, or curation workflows;
- reviewers who need to understand how data were obtained, transformed, and
  validated.

CrystalDB is not a claim that every measurement has one certain structure
assignment. Candidate links, unresolved cases, phase character, and missing
metadata are represented explicitly.

## Core data model

The main entities are:

- **Sample**: a material or specimen record, including source identifiers and
  sample-level metadata.
- **Measurement**: an experimental observation made for a sample, such as a
  powder or single-crystal diffraction measurement.
- **Pattern**: a powder diffraction pattern/profile associated with a powder
  measurement. It is distinct from a single-crystal reflection set.
- **Structure**: a crystallographic structure record, normally linked to a
  source identifier and a CIF or equivalent representation.
- **Reflection set**: indexed or observed single-crystal reflection data. It is
  distinct from a powder pattern.
- **Source**: an external collection, laboratory collection, file, or other
  origin from which a record was obtained.
- **Provenance and linkage**: source identifiers, file hashes, transformation
  steps, evidence, candidate relationships, and linkage status.

Important distinctions are preserved. A powder pattern is not a single-crystal
reflection set; a measurement does not automatically imply a single-phase
sample; and a candidate structure link is not the same as a confirmed
assignment.

## Main data sources

The current workflows cover the following source families:

- **RRUFF**: mineralogical sample, diffraction, and structure-linking workflows.
- **COD**: crystallographic structure records and, where available, observed
  single-crystal reflection data.
- **OPXRD**: experimental diffraction records used by the OPXRD curation and
  integration workflows.
- **PowBase**: powder-diffraction records and source-structure recovery
  workflows.
- **DARA**: records used by the repository's structure-linkage workflows.
- **Laboratory XRD**: locally acquired or supplied laboratory diffraction
  measurements.

Source-specific details, identifiers, and limitations are described in
[`docs/data-sources.md`](docs/data-sources.md).

## Repository layout

```text
.
├── data/                  Tracked manifests, mappings, and metadata
├── docs/                  Scientific, workflow, reproducibility, and API docs
├── paper/                 Manuscript and paper-related notes
├── scripts/               Ingest, curation, recovery, validation, and export
├── src/crystaldb/         Python package and API implementation
├── tests/                 Pytest tests for API and curation workflows
├── web/                   Next.js research browser
├── pyproject.toml         Python package and test configuration
└── .env.example           Example environment settings
```

The `data/` directory mainly contains tracked manifests, mappings, and metadata.
Large scientific collections, raw downloads, and local working data are
generally stored outside normal Git tracking.

The current working tree still contains a flat `scripts/` directory and
source-specific mapping files. They are documented by
[`scripts/README.md`](scripts/README.md) and
[`data/README.md`](data/README.md); no scientific files are moved by this
documentation phase.

## Python API

The project uses Python 3.11 or newer.

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

On POSIX shells:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Run the API from the repository root:

```bash
python -m uvicorn crystaldb.api.main:app --reload --host 127.0.0.1 --port 8000
```

The API reads the repository `data/` directory by default. Set
`CRYSTALDB_DATA_ROOT` when data are stored elsewhere. Database-backed workflows
may also require `CRYSTALDB_MONGO_URI` and
`CRYSTALDB_MONGO_DATABASE` (or `CRYSTALDB_MONGO_DB`). See
[`docs/api/README.md`](docs/api/README.md) and
[`docs/api/CRYSTALDB_API_V0_1_2.md`](docs/api/CRYSTALDB_API_V0_1_2.md).

## Web frontend

The browser is a separate Next.js application. Start the API first when using
data-backed pages.

```bash
cd web
pnpm install
pnpm dev
```

The frontend uses `http://127.0.0.1:8000` by default. To point it at another
API:

```bash
NEXT_PUBLIC_CRYSTALDB_API_URL=http://127.0.0.1:8000
```

For a production build:

```bash
pnpm lint
pnpm typecheck
pnpm build
```

## Tests

From the repository root:

```bash
python -m pytest
```

The committed `tests/` directory contains the maintained pytest suite. Some
older exploratory probes remain under `scripts/`; they may require local data,
MongoDB, or external source directories and are not equivalent to the default
test suite.

## Data, provenance, and uncertainty

CrystalDB keeps the following principles visible in its data and documentation:

- **Provenance**: source identifiers, file locations, hashes, transformation
  steps, and manifests should remain traceable.
- **Ambiguity**: candidate structures and unresolved assignments are retained
  as candidate or review states rather than silently converted into confirmed
  links.
- **Phase character**: production records use the formal values
  `single_phase`, `multi_phase`, and `unknown`. `unknown` means that the
  available source evidence is insufficient for a reliable phase-character
  assignment. Candidate, review, or unresolved linkage states are separate
  from the formal `phase_character` value.
- **Missing metadata**: absent wavelength, radiation, composition, fraction
  basis, or other metadata remains unknown unless supported by source evidence.
  The workflows do not silently infer a default value merely to complete a
  record.

The curation stages and their evidence are described in
[`docs/curation-workflow.md`](docs/curation-workflow.md).

## Data not stored in Git

Git is not the distribution mechanism for the full scientific source
collections. Raw downloads, large local stores, working staging areas, and
other generated or canonical data may be present in a local working copy but
are intentionally excluded from normal Git tracking. Tracked mappings,
manifests, validation reports, and documentation describe or reference those
materials; they are not a replacement for the original source collections.

The repository also contains some historical or audit artifacts. Their
presence does not mean that every underlying dataset is included or that a
hosted public dataset is available.

## Reproducibility and release status

Reproduction depends on the Python environment, optional MongoDB configuration,
external source data, local data-root settings, and the particular manifests
used by a workflow. Start with [`docs/reproducibility.md`](docs/reproducibility.md)
and keep generated reports separate from production-ready outputs.

CrystalDB is currently maintained as a repository containing documentation,
source code, mappings/manifests, and local API/web tooling. The GitHub
repository is private, and there is currently no DOI, formal hosted dataset
release, or public service endpoint.

## Further reading

- [Data model](docs/data-model.md)
- [Data sources](docs/data-sources.md)
- [Curation workflow](docs/curation-workflow.md)
- [Reproducibility](docs/reproducibility.md)
- [API documentation](docs/api/README.md)
