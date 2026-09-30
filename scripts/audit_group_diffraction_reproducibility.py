import json
from collections import defaultdict
from pathlib import Path
from statistics import median


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_group_diffraction_annotation_v1.json"
)


data = json.loads(
    INPUT_FILE.read_text(
        encoding="utf-8"
    )
)

groups = data["groups"]


# ============================================================
# Build replicate clusters
#
# Same:
#   mineral name
#   exact bibliography-supported CIF set
#
# Different:
#   RRUFF sample / experimental measurement
# ============================================================

clusters = defaultdict(list)


for item in groups:

    mineral = (
        str(
            item.get("mineral") or ""
        )
        .strip()
        .lower()
    )

    candidate_set = tuple(
        sorted(
            str(candidate["source_id"])
            for candidate
            in item["candidate_results"]
        )
    )

    key = (
        mineral,
        candidate_set,
    )

    clusters[key].append(
        item
    )


replicate_clusters = {
    key: records

    for key, records
    in clusters.items()

    if len(records) >= 2
}


# ============================================================
# Summaries
# ============================================================

unanimous = []
non_unanimous = []

high_separation_clusters = []
high_separation_unanimous = []


for key, records in replicate_clusters.items():

    best_candidates = [
        str(
            record[
                "lowest_weighted_residual_candidate"
            ]
        )
        for record in records
    ]

    unique_best = set(
        best_candidates
    )

    separations = []

    for record in records:

        comparison = (
            record.get(
                "best_vs_runner_up_separation"
            )
        )

        if comparison is not None:

            separations.append(
                comparison[
                    "median_nearest_difference"
                ]
            )

    cluster = {
        "mineral":
            key[0],

        "candidate_set":
            key[1],

        "sample_count":
            len(records),

        "sample_ids": [
            record["sample_id"]
            for record in records
        ],

        "best_candidates":
            best_candidates,

        "unanimous":
            len(unique_best) == 1,

        "median_best_runner_separation":
            (
                median(separations)
                if separations
                else None
            ),
    }

    if cluster["unanimous"]:
        unanimous.append(
            cluster
        )
    else:
        non_unanimous.append(
            cluster
        )

    # Descriptive high-separation stratum,
    # inherited from earlier analysis.
    if (
        separations
        and all(
            value > 0.10
            for value in separations
        )
    ):

        high_separation_clusters.append(
            cluster
        )

        if cluster["unanimous"]:

            high_separation_unanimous.append(
                cluster
            )


# ============================================================
# Output
# ============================================================

print()
print("=" * 100)
print(
    "GROUP DIFFRACTION REPRODUCIBILITY AUDIT"
)
print("=" * 100)

print(
    "Group records:",
    len(groups),
)

print(
    "Repeated mineral + exact candidate-set clusters:",
    len(replicate_clusters),
)

print(
    "Records represented in replicate clusters:",
    sum(
        len(records)
        for records
        in replicate_clusters.values()
    ),
)

print(
    "Unanimous preferred-CIF clusters:",
    len(unanimous),
)

print(
    "Non-unanimous clusters:",
    len(non_unanimous),
)

if replicate_clusters:

    print(
        "Overall unanimity fraction:",
        f"{len(unanimous) / len(replicate_clusters):.3f}",
    )


print()
print("-" * 100)
print(
    "HIGH-SEPARATION REPLICATE CLUSTERS"
)
print("-" * 100)

print(
    "Definition here: every record in cluster "
    "has best-vs-runner theoretical separation > 0.10 deg."
)

print(
    "High-separation replicate clusters:",
    len(
        high_separation_clusters
    ),
)

print(
    "Unanimous high-separation clusters:",
    len(
        high_separation_unanimous
    ),
)

if high_separation_clusters:

    print(
        "High-separation unanimity fraction:",
        f"{len(high_separation_unanimous) / len(high_separation_clusters):.3f}",
    )


print()
print("=" * 100)
print(
    "UNANIMOUS EXAMPLES"
)
print("=" * 100)

for item in sorted(
    unanimous,
    key=lambda x:
        (
            -x["sample_count"],
            x["mineral"],
        ),
)[:15]:

    print(
        item[
            "mineral"
        ],
        "| samples =",
        item[
            "sample_ids"
        ],
        "| best =",
        item[
            "best_candidates"
        ][0],
        "| separation median =",
        (
            f"{item['median_best_runner_separation']:.5f}"
            if item[
                "median_best_runner_separation"
            ]
            is not None
            else "NA"
        ),
    )


print()
print("=" * 100)
print(
    "NON-UNANIMOUS EXAMPLES"
)
print("=" * 100)

for item in sorted(
    non_unanimous,
    key=lambda x:
        (
            -x["sample_count"],
            x["mineral"],
        ),
)[:15]:

    print(
        item[
            "mineral"
        ],
        "| samples =",
        item[
            "sample_ids"
        ],
        "| best =",
        item[
            "best_candidates"
        ],
        "| separation median =",
        (
            f"{item['median_best_runner_separation']:.5f}"
            if item[
                "median_best_runner_separation"
            ]
            is not None
            else "NA"
        ),
    )


print()
print("=" * 100)
print(
    "AUDIT COMPLETE"
)
print("=" * 100)

