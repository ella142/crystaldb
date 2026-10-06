# RRUFF Cleanup Candidates v1

Dry-run only. No file was deleted, moved, or archived.

The scan protects the original RRUFF source files, the complete `data/raw/cod` CIF library, all frozen manifests, rescue outputs, validation reports, provenance/audit files, and `cif_index.json`.

## Counts

- KEEP = 10833 files
- ARCHIVE = 10 files
- SAFE_TO_DELETE_AFTER_PROMOTION = 199 files
- DO_NOT_KNOW = 0 files

## Staging rescue CIFs

- scanned staging CIFs = 241
- already promoted and present in current index = 199
- these are marked `SAFE_TO_DELETE_AFTER_PROMOTION` only; none was deleted
- the 42 equivalent, non-promoted CIFs remain KEEP because they are not in `cif_index.json` and are registered as staging-local fallback files

## Archive candidates

ARCHIVE entries are superseded intermediate audit outputs only. This report does not move them. `DO_NOT_KNOW` entries require explicit human review before any action.

## Scope note

RRUFF MongoDB source collections are not files and were not modified or included as deletion candidates. The formal `crystaldb` database was not modified.
