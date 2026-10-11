# Reproducibility

CrystalDB workflows are reproducible only when the code, software environment,
source inputs, configuration, and generated workflow outputs are considered
together.

Running the repository tests, operating the API and web interface, and
reconstructing historical ingestion or curation workflows are different levels
of reproducibility and may require different data and software environments.

## Minimum setup

CrystalDB requires Python 3.11 or newer.

From the repository root, create and activate a virtual environment.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest
```

For Linux or macOS, activate the virtual environment with:

```bash
source .venv/bin/activate
```

The web application has separate Node.js and pnpm dependencies. See the root
`README.md` for frontend setup instructions.

## Levels of reproducibility

CrystalDB supports several levels of reproducibility.

### Repository-level reproducibility

A fresh clone of the repository is intended to support:

- inspection of the source code;
- inspection of the data model and documentation;
- inspection of tracked mappings, manifests, and validation records;
- execution of the maintained test suite;
- review of the curation and structure-linkage logic.

This level does not require the complete external scientific source
collections.

### Runtime reproducibility

Running the CrystalDB API and web interface requires the application code and
the configured production MongoDB database.

Depending on the enabled download features, selected scientific files
referenced by production records may also be required.

The production application does not necessarily require every source database,
raw source collection, staging database, archive, or historical working
directory used during dataset construction.

Runtime configuration may include:

- `CRYSTALDB_DATA_ROOT`;
- `CRYSTALDB_MONGO_URI`;
- `CRYSTALDB_MONGO_DATABASE` or `CRYSTALDB_MONGO_DB`;
- frontend API configuration.

### Full workflow reconstruction

Reproducing historical ingestion, recovery, curation, validation, or
integration workflows may additionally require:

- original or archived source datasets;
- source-specific MongoDB databases;
- local raw or canonical scientific files;
- network access to external resources;
- source-specific input paths;
- corresponding manifests and validation reports;
- manual review decisions recorded during curation.

These dependencies are not all distributed through Git.

A fresh clone may therefore support repository inspection and maintained tests
without being sufficient to reconstruct every historical source workflow.

## Data root and database configuration

The Python package uses the repository `data/` directory by default.

Use `CRYSTALDB_DATA_ROOT` when scientific data are stored separately from the
code repository.

Example for Windows PowerShell:

```powershell
$env:CRYSTALDB_DATA_ROOT = "D:\path\to\crystaldb-data"
$env:CRYSTALDB_MONGO_URI = "mongodb://127.0.0.1:27017"
$env:CRYSTALDB_MONGO_DATABASE = "crystaldb"
```

`CRYSTALDB_MONGO_DB` is also accepted by the API configuration.

Credentials and other secrets should not be stored in tracked files.

## Record workflow inputs

For curation, validation, staging, or integration runs, record the information
needed to reconstruct the result, including:

- the Git revision;
- the input datasets or manifests;
- important command options;
- generated validation or integration reports;
- whether the run was an audit, dry run, staging run, or production
  integration.

Files in `data/mappings/` often retain useful provenance and input/output
references.

Historical paths stored in manifests should be treated as provenance records,
not as portable commands that are expected to work on another machine.

## External and local inputs

The full raw source collections and many local canonical, staging, archive, or
working data stores are not distributed through Git.

Some workflows therefore depend on external resources such as:

- crystallographic source collections;
- experimental diffraction archives;
- laboratory diffraction data;
- source-specific MongoDB databases;
- downloaded CIF or reflection files;
- network resources used during candidate retrieval.

Some historical scripts may also contain source-specific paths or expect
external directories.

Before running a historical workflow, inspect its expected inputs, command-line
options, environment variables, and associated documentation.

## Production versus intermediate workflows

CrystalDB distinguishes operational workflow state from scientific
interpretation.

The following workflow states should remain separate:

- **Audit / review**  
  Investigates source records, identifies problems, or proposes candidate
  interpretations. These runs normally generate reports, mappings, or review
  records.

- **Dry run**  
  Exercises preparation, validation, or integration logic without committing a
  production update.

- **Staging**  
  Prepares intermediate or pre-production records for validation or later
  integration.

- **Production integration**  
  Writes or prepares validated records intended for the integrated CrystalDB
  dataset.

- **Export / release**  
  Produces indexes, API artifacts, download products, manifests, or other
  release-oriented outputs.

A report, CSV, JSON file, or mapping is not automatically evidence that the
corresponding records were written to the production database.

Likewise, an audit or validation result should not be described as a released
dataset.

The associated script, manifest, validation report, and database state should
be interpreted together.

## Scientific uncertainty

Reproducibility in CrystalDB does not require converting uncertain source
evidence into artificial certainty.

Where relevant, workflows preserve:

- unresolved structure assignments;
- competing structure candidates;
- source-specific provenance;
- phase character;
- missing wavelength or radiation metadata;
- incomplete structural metadata;
- manual review states;
- validation and compatibility evidence.

A reproducible workflow should preserve these states rather than silently
imputing missing information or collapsing ambiguous cases into a single
assignment.

## Reproducibility limits

Results may depend on:

- source availability;
- network responses;
- source version changes;
- local file layout;
- MongoDB state;
- parser and dependency versions;
- source-specific metadata quality;
- manual review decisions.

Where these dependencies materially affect an output, preserve the relevant
manifest and validation report and document which inputs were unavailable,
excluded, ambiguous, or unresolved.

Historical workflows should be interpreted in the context of the source data,
code revision, and review state used when they were produced.