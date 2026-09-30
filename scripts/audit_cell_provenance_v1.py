import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESOLUTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_experimental_resolution_v1.json"
)

ANNOTATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_group_diffraction_annotation_v1.json"
)


# ============================================================
# Load frozen files
# ============================================================

resolution_data = json.loads(
    RESOLUTION_FILE.read_text(
        encoding="utf-8"
    )
)

annotation_data = json.loads(
    ANNOTATION_FILE.read_text(
        encoding="utf-8"
    )
)

resolution_by_sample = {
    record["sample_id"]: record
    for record in resolution_data["records"]
}


# ============================================================
# Rebuild the same 33 replicate clusters / 93 records
# ============================================================

clusters = defaultdict(list)

for group in annotation_data["groups"]:

    mineral = (
        str(
            group.get("mineral") or ""
        )
        .strip()
        .lower()
    )

    candidate_set = tuple(
        sorted(
            str(
                candidate["source_id"]
            )
            for candidate
            in group["candidate_results"]
        )
    )

    clusters[
        (
            mineral,
            candidate_set,
        )
    ].append(
        group
    )


replicate_groups = []

for key, records in clusters.items():

    if len(records) < 2:
        continue

    replicate_groups.extend(
        records
    )


# ============================================================
# Mongo
# ============================================================

db = MongoClient(
    "mongodb://localhost:27017"
)["rruff"]


# ============================================================
# Cell concordance helper
# ============================================================

def cell_evidence(sample_id):

    record = resolution_by_sample[
        sample_id
    ]

    candidates = (
        record[
            "structure_resolution"
        ][
            "bibliographic_candidates"
        ]
    )

    usable = []

    for candidate in candidates:

        evidence = candidate.get(
            "evidence",
            {},
        )

        length_diff = evidence.get(
            "max_length_relative_difference"
        )

        angle_diff = evidence.get(
            "max_angle_difference"
        )

        if (
            length_diff is None
            or angle_diff is None
        ):
            continue

        usable.append(
            {
                "source_id":
                    str(
                        candidate[
                            "source_id"
                        ]
                    ),

                "length_diff":
                    float(
                        length_diff
                    ),

                "angle_diff":
                    float(
                        angle_diff
                    ),
            }
        )

    if not usable:
        return None

    min_length = min(
        item["length_diff"]
        for item in usable
    )

    length_best = {
        item["source_id"]
        for item in usable
        if item["length_diff"]
        == min_length
    }

    pareto = set()

    for candidate in usable:

        dominated = False

        for other in usable:

            if (
                other["source_id"]
                == candidate["source_id"]
            ):
                continue

            at_least_as_good = (
                other["length_diff"]
                <= candidate["length_diff"]
                and
                other["angle_diff"]
                <= candidate["angle_diff"]
            )

            strictly_better = (
                other["length_diff"]
                < candidate["length_diff"]
                or
                other["angle_diff"]
                < candidate["angle_diff"]
            )

            if (
                at_least_as_good
                and strictly_better
            ):
                dominated = True
                break

        if not dominated:

            pareto.add(
                candidate["source_id"]
            )

    return {
        "length_best":
            length_best,

        "pareto":
            pareto,
    }


# ============================================================
# Description normalization
# ============================================================

def description_category(
    description,
):

    text = (
        str(description or "")
        .strip()
        .lower()
    )

    if not text:
        return "missing"

    if (
        "single crystal"
        in text
        and
        "profile is calculated"
        in text
    ):
        return (
            "single_crystal_calculated_profile"
        )

    if (
        "cell parameters are from single crystal"
        in text
    ):
        return (
            "powder_cell_from_single_crystal"
        )

    if "mo radiation" in text:

        return "powder_mo"

    if "cu radiation" in text:

        return "powder_cu"

    if text == "powder":

        return "powder"

    return "other"


# ============================================================
# Reference keyword audit
# ============================================================

def reference_flags(
    references,
):

    text = " ".join(
        str(value)
        for value in (
            references
            or []
        )
    ).lower()

    return {
        "mentions_pressure":
            bool(
                re.search(
                    r"\bgpa\b|\bkbar\b|\bpressure\b",
                    text,
                )
            ),

        "mentions_temperature":
            bool(
                re.search(
                    r"\btemperature\b|\bkelvin\b|\b[0-9]+\s*k\b",
                    text,
                )
            ),

        "mentions_refinement":
            "refinement"
            in text,

        "mentions_sample_in_air":
            "sample in air"
            in text,
    }


# ============================================================
# Build 93-record audit
# ============================================================

rows = []


for group in replicate_groups:

    sample_id = group[
        "sample_id"
    ]

    resolution_record = (
        resolution_by_sample[
            sample_id
        ]
    )

    measurement_id = (
        resolution_record[
            "measurement"
        ][
            "filename_sample_id"
        ]
    )

    xy = db.xy_raw.find_one(
        {
            "filename_sample_id":
                measurement_id
        }
    )

    dif = db.dif.find_one(
        {
            "sample_id":
                sample_id
        }
    )

    metadata = (
        (xy or {})
        .get(
            "metadata",
            {},
        )
    )

    description = metadata.get(
        "DIFFRACTION SAMPLE DESCRIPTION"
    )

    xy_cell = metadata.get(
        "CELL PARAMETERS"
    )

    dif_cell = (
        (dif or {})
        .get(
            "crystal_structure",
            {},
        )
        .get(
            "cell_parameters"
        )
    )

    flags = reference_flags(
        (dif or {}).get(
            "references"
        )
    )

    evidence = cell_evidence(
        sample_id
    )

    diffraction_best = str(
        group[
            "lowest_weighted_residual_candidate"
        ]
    )

    rows.append(
        {
            "sample_id":
                sample_id,

            "mineral":
                group.get(
                    "mineral"
                ),

            "measurement_id":
                measurement_id,

            "description":
                description,

            "description_category":
                description_category(
                    description
                ),

            "xy_cell_present":
                bool(
                    xy_cell
                ),

            "dif_cell_present":
                bool(
                    dif_cell
                ),

            "xy_cell_equals_dif_cell_textually":
                (
                    bool(
                        xy_cell
                    )
                    and
                    bool(
                        dif_cell
                    )
                ),

            "diffraction_best":
                diffraction_best,

            "exact_cell_concordance":
                (
                    evidence is not None
                    and
                    diffraction_best
                    in evidence[
                        "length_best"
                    ]
                ),

            "cell_pareto_concordance":
                (
                    evidence is not None
                    and
                    diffraction_best
                    in evidence[
                        "pareto"
                    ]
                ),

            **flags,
        }
    )


# ============================================================
# Global summaries
# ============================================================

print()
print("=" * 112)
print(
    "CELL PROVENANCE AUDIT V1"
)
print("=" * 112)

print(
    "Replicate records:",
    len(rows),
)

print(
    "XY cell present:",
    sum(
        row[
            "xy_cell_present"
        ]
        for row in rows
    ),
)

print(
    "DIF cell present:",
    sum(
        row[
            "dif_cell_present"
        ]
        for row in rows
    ),
)


print()
print("=" * 112)
print(
    "DIFFRACTION SAMPLE DESCRIPTION"
)
print("=" * 112)

description_counts = Counter(
    row[
        "description_category"
    ]
    for row in rows
)

for category, count in (
    description_counts
    .most_common()
):

    print(
        f"{category:<40}"
        f"{count:>6}"
    )


print()
print("=" * 112)
print(
    "CELL-DIFFRACTION CONCORDANCE BY DESCRIPTION"
)
print("=" * 112)

print(
    f"{'Category':<40}"
    f"{'N':>6}"
    f"{'Exact':>10}"
    f"{'Exact %':>10}"
    f"{'Pareto':>10}"
    f"{'Pareto %':>10}"
)


for category in sorted(
    description_counts
):

    subset = [
        row
        for row in rows
        if row[
            "description_category"
        ]
        == category
    ]

    n = len(
        subset
    )

    exact = sum(
        row[
            "exact_cell_concordance"
        ]
        for row in subset
    )

    pareto = sum(
        row[
            "cell_pareto_concordance"
        ]
        for row in subset
    )

    print(
        f"{category:<40}"
        f"{n:>6d}"
        f"{exact:>10d}"
        f"{exact / n if n else 0:>10.3f}"
        f"{pareto:>10d}"
        f"{pareto / n if n else 0:>10.3f}"
    )


# ============================================================
# Reference-context flags
# ============================================================

print()
print("=" * 112)
print(
    "REFERENCE / CONDITION KEYWORDS"
)
print("=" * 112)

flag_names = [
    "mentions_pressure",
    "mentions_temperature",
    "mentions_refinement",
    "mentions_sample_in_air",
]


for flag in flag_names:

    subset = [
        row
        for row in rows
        if row[
            flag
        ]
    ]

    exact = sum(
        row[
            "exact_cell_concordance"
        ]
        for row in subset
    )

    pareto = sum(
        row[
            "cell_pareto_concordance"
        ]
        for row in subset
    )

    print(
        f"{flag:<32}"
        f"N={len(subset):>4}"
        f"  exact="
        f"{exact / len(subset) if subset else 0:.3f}"
        f"  pareto="
        f"{pareto / len(subset) if subset else 0:.3f}"
    )


# ============================================================
# Records with condition-specific references
# ============================================================

condition_specific = [
    row
    for row in rows
    if (
        row[
            "mentions_pressure"
        ]
        or
        row[
            "mentions_temperature"
        ]
    )
]


print()
print("=" * 112)
print(
    "CONDITION-SPECIFIC RECORDS"
)
print("=" * 112)

print(
    "Records:",
    len(
        condition_specific
    ),
)

for row in (
    condition_specific[:25]
):

    print(
        row[
            "sample_id"
        ],
        "|",
        row[
            "mineral"
        ],
        "|",
        row[
            "description_category"
        ],
        "| pressure=",
        row[
            "mentions_pressure"
        ],
        "| temperature=",
        row[
            "mentions_temperature"
        ],
        "| refinement=",
        row[
            "mentions_refinement"
        ],
        "| exact=",
        row[
            "exact_cell_concordance"
        ],
        "| pareto=",
        row[
            "cell_pareto_concordance"
        ],
    )


print()
print("=" * 112)
print(
    "AUDIT COMPLETE"
)
print("=" * 112)

