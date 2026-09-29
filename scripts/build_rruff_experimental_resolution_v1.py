from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from crystaldb.mongo import get_database
from crystaldb.matching.candidate_resolver import (
    resolve_sample_candidates,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

COVERAGE_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "cod_coverage_results_full_v1.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_experimental_resolution_v1.json"
)


CLEAN_EXPERIMENTAL_DESCRIPTIONS = {
    "Powder",
    "Powder, using Mo radiation",
    "Powder, cell parameters are from single crystal",
    "Powder using Cu radiation",
}


def valid_xy(doc):
    xrd = doc.get("xrd", {})

    two_theta = (
        xrd.get("two_theta")
        or []
    )

    intensity = (
        xrd.get("intensity")
        or []
    )

    return (
        bool(two_theta)
        and bool(intensity)
        and len(two_theta)
        == len(intensity)
    )


def main():

    # ========================================================
    # Load frozen v1 coverage results
    # ========================================================

    coverage_results = json.loads(
        COVERAGE_FILE.read_text(
            encoding="utf-8"
        )
    )

    coverage_by_sample = {
        item["rruff_sample_id"]: item
        for item in coverage_results
    }


    # ========================================================
    # Load RRUFF
    # ========================================================

    db = get_database(
        database_name="rruff"
    )


    # ========================================================
    # Identify all valid clean experimental RAW measurements
    # that already have sample_structure candidates
    # ========================================================

    clean_raw_docs = []

    for doc in db.xy_raw.find({}):

        sample_id = doc.get(
            "sample_id"
        )

        filename_sample_id = doc.get(
            "filename_sample_id"
        )

        if not sample_id:
            continue

        if not filename_sample_id:
            continue

        coverage = coverage_by_sample.get(
            sample_id
        )

        if not coverage:
            continue

        if (
            coverage.get("status")
            != "sample_structure_found"
        ):
            continue

        description = (
            doc.get("metadata", {})
            .get(
                "DIFFRACTION SAMPLE DESCRIPTION"
            )
        )

        if (
            description
            not in
            CLEAN_EXPERIMENTAL_DESCRIPTIONS
        ):
            continue

        if not valid_xy(doc):
            continue

        clean_raw_docs.append(
            doc
        )


    # ========================================================
    # Integrity checks
    # ========================================================

    sample_ids = [
        doc["sample_id"]
        for doc in clean_raw_docs
    ]

    measurement_ids = [
        doc["filename_sample_id"]
        for doc in clean_raw_docs
    ]

    duplicate_samples = [
        key
        for key, count
        in Counter(
            sample_ids
        ).items()
        if count > 1
    ]

    duplicate_measurements = [
        key
        for key, count
        in Counter(
            measurement_ids
        ).items()
        if count > 1
    ]

    if duplicate_samples:
        raise RuntimeError(
            "Multiple clean experimental RAW "
            "measurements found for the same "
            "sample_id. Review required: "
            + repr(
                duplicate_samples[:20]
            )
        )

    if duplicate_measurements:
        raise RuntimeError(
            "Duplicate filename_sample_id "
            "values found. Review required: "
            + repr(
                duplicate_measurements[:20]
            )
        )


    # ========================================================
    # Determine exact RAW ↔ processed relationships
    # ========================================================

    processed_ids = set(
        db.xy_processed.distinct(
            "filename_sample_id",
            {
                "filename_sample_id": {
                    "$in":
                        measurement_ids
                }
            },
        )
    )


    # ========================================================
    # Resolve CIF candidates
    # ========================================================

    publication_cache = {}

    output_records = []

    for raw_doc in sorted(
        clean_raw_docs,
        key=lambda item:
            item["sample_id"],
    ):

        sample_id = raw_doc[
            "sample_id"
        ]

        measurement_id = raw_doc[
            "filename_sample_id"
        ]

        coverage = (
            coverage_by_sample[
                sample_id
            ]
        )

        dif_doc = db.dif.find_one(
            {
                "sample_id":
                    sample_id
            }
        )

        if dif_doc is None:
            raise RuntimeError(
                "Missing DIF record for "
                f"{sample_id}"
            )

        resolution = (
            resolve_sample_candidates(
                coverage_result=coverage,
                dif_doc=dif_doc,
                project_root=PROJECT_ROOT,
                publication_cache=
                    publication_cache,
            )
        )

        xrd = raw_doc.get(
            "xrd",
            {}
        )

        record = {
            "sample_id":
                sample_id,

            "mineral":
                coverage.get(
                    "mineral"
                ),

            "measurement": {
                "filename_sample_id":
                    measurement_id,

                "source_collection":
                    "rruff.xy_raw",

                "description":
                    raw_doc.get(
                        "metadata",
                        {},
                    ).get(
                        "DIFFRACTION SAMPLE DESCRIPTION"
                    ),

                "point_count":
                    len(
                        xrd.get(
                            "two_theta"
                        )
                        or []
                    ),

                "has_processed":
                    measurement_id
                    in processed_ids,
            },

            "structure_resolution":
                resolution,
        }

        output_records.append(
            record
        )


    # ========================================================
    # Resolution statistics
    # ========================================================

    level_counts = Counter(
        record[
            "structure_resolution"
        ][
            "resolution_level"
        ]
        for record
        in output_records
    )

    status_counts = Counter(
        record[
            "structure_resolution"
        ][
            "resolution_status"
        ]
        for record
        in output_records
    )

    raw_with_processed = sum(
        1
        for record
        in output_records
        if record[
            "measurement"
        ][
            "has_processed"
        ]
    )

    raw_without_processed = (
        len(output_records)
        - raw_with_processed
    )


    # ========================================================
    # Final invariants
    # ========================================================

    if (
        sum(level_counts.values())
        != len(output_records)
    ):
        raise RuntimeError(
            "Resolution-level counts "
            "do not sum to total records."
        )

    if (
        raw_with_processed
        + raw_without_processed
        != len(output_records)
    ):
        raise RuntimeError(
            "RAW/processed counts "
            "do not sum to total records."
        )


    # ========================================================
    # Final reproducible dataset
    # ========================================================

    output = {
        "schema_version":
            "1.0",

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source_coverage_file":
            str(
                COVERAGE_FILE.relative_to(
                    PROJECT_ROOT
                )
            ).replace("\\", "/"),

        "subset_definition": {
            "source":
                "RRUFF",

            "measurement_type":
                "experimental powder XRD",

            "requirements": [
                "coverage status is "
                "sample_structure_found",

                "XY_RAW record exists",

                "DIFFRACTION SAMPLE "
                "DESCRIPTION is in the "
                "conservative clean "
                "experimental allow-list",

                "two_theta and intensity "
                "arrays are non-empty and "
                "have equal length",
            ],
        },

        "resolution_policy": {
            "candidate_scope":
                "existing sample_structure "
                "matches from frozen v1 "
                "coverage results",

            "single_candidate":
                "record-level resolution",

            "bibliographic_match":
                "same year, first page, "
                "last page, at least one "
                "shared author surname; "
                "volume must agree when "
                "present in both sources",

            "title_matching":
                "not used as a hard "
                "condition",

            "multiple_bibliographic_hits":
                "retained as a "
                "bibliography-supported "
                "candidate group; no CIF "
                "is forced",

            "unresolved_cases":
                "retained for review",
        },

        "summary": {
            "clean_experimental_records":
                len(
                    output_records
                ),

            "raw_with_processed":
                raw_with_processed,

            "raw_without_processed":
                raw_without_processed,

            "resolution_levels":
                dict(
                    sorted(
                        level_counts.items()
                    )
                ),

            "resolution_statuses":
                dict(
                    sorted(
                        status_counts.items()
                    )
                ),
        },

        "records":
            output_records,
    }


    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    # ========================================================
    # Console summary
    # ========================================================

    print()
    print("=" * 72)
    print(
        "RRUFF EXPERIMENTAL "
        "RESOLUTION V1"
    )
    print("=" * 72)

    print(
        "Clean experimental records:   ",
        len(output_records),
    )

    print(
        "RAW with processed pair:       ",
        raw_with_processed,
    )

    print(
        "RAW without processed pair:    ",
        raw_without_processed,
    )

    print()
    print("Resolution levels:")

    for key, value in sorted(
        level_counts.items()
    ):
        print(
            f"  {key:<12} {value}"
        )

    print()
    print("Resolution statuses:")

    for key, value in sorted(
        status_counts.items()
    ):
        print(
            f"  {key:<42} {value}"
        )

    print()
    print(
        "Publication CIFs parsed/cache: ",
        len(publication_cache),
    )

    print()
    print(
        "Saved:",
        OUTPUT_FILE,
    )

    print("=" * 72)


if __name__ == "__main__":
    main()
