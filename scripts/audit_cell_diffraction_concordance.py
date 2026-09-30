import json
from collections import defaultdict
from pathlib import Path
from statistics import median


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


# ============================================================
# Index frozen resolution records
# ============================================================

resolution_by_sample = {
    record["sample_id"]: record
    for record in resolution_data["records"]
}


# ============================================================
# Rebuild exact replicate clusters
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
                candidate[
                    "source_id"
                ]
            )
            for candidate
            in group[
                "candidate_results"
            ]
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


replicate_clusters = {
    key: records
    for key, records
    in clusters.items()
    if len(records) >= 2
}


# ============================================================
# Cell evidence helpers
# ============================================================

def get_cell_evidence(
    sample_id,
):
    record = (
        resolution_by_sample[
            sample_id
        ]
    )

    candidates = (
        record[
            "structure_resolution"
        ][
            "bibliographic_candidates"
        ]
    )

    output = []

    for candidate in candidates:

        evidence = (
            candidate.get(
                "evidence",
                {},
            )
        )

        length_diff = (
            evidence.get(
                "max_length_relative_difference"
            )
        )

        angle_diff = (
            evidence.get(
                "max_angle_difference"
            )
        )

        if (
            length_diff is None
            or angle_diff is None
        ):
            continue

        output.append(
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

    return output


def cell_pareto_front(
    candidates,
):
    front = []

    for candidate in candidates:

        dominated = False

        for other in candidates:

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

            front.append(
                candidate[
                    "source_id"
                ]
            )

    return front


# ============================================================
# Record-level concordance
# ============================================================

records = []


for (
    mineral,
    candidate_set,
), cluster_records in replicate_clusters.items():

    for group in cluster_records:

        sample_id = (
            group[
                "sample_id"
            ]
        )

        diffraction_best = str(
            group[
                "lowest_weighted_residual_candidate"
            ]
        )

        cell_candidates = (
            get_cell_evidence(
                sample_id
            )
        )

        if not cell_candidates:
            continue

        minimum_length = min(
            item[
                "length_diff"
            ]
            for item
            in cell_candidates
        )

        length_best = [
            item[
                "source_id"
            ]
            for item
            in cell_candidates

            if item[
                "length_diff"
            ]
            == minimum_length
        ]

        pareto = (
            cell_pareto_front(
                cell_candidates
            )
        )

        diffraction_item = next(
            (
                item
                for item
                in cell_candidates

                if item[
                    "source_id"
                ]
                == diffraction_best
            ),
            None,
        )

        sorted_length = sorted(
            cell_candidates,
            key=lambda item:
                item[
                    "length_diff"
                ],
        )

        length_rank = next(
            (
                index
                for index, item
                in enumerate(
                    sorted_length,
                    start=1,
                )
                if item[
                    "source_id"
                ]
                == diffraction_best
            ),
            None,
        )

        records.append(
            {
                "sample_id":
                    sample_id,

                "mineral":
                    mineral,

                "candidate_set":
                    candidate_set,

                "diffraction_best":
                    diffraction_best,

                "length_best":
                    length_best,

                "cell_pareto_front":
                    pareto,

                "diffraction_equals_length_best":
                    (
                        diffraction_best
                        in length_best
                    ),

                "diffraction_on_cell_pareto":
                    (
                        diffraction_best
                        in pareto
                    ),

                "diffraction_length_rank":
                    length_rank,

                "diffraction_length_diff":
                    (
                        diffraction_item[
                            "length_diff"
                        ]
                        if diffraction_item
                        else None
                    ),

                "diffraction_angle_diff":
                    (
                        diffraction_item[
                            "angle_diff"
                        ]
                        if diffraction_item
                        else None
                    ),
            }
        )


# ============================================================
# Cluster-level interpretation
# ============================================================

records_by_cluster = defaultdict(list)


for record in records:

    key = (
        record["mineral"],
        record["candidate_set"],
    )

    records_by_cluster[key].append(
        record
    )


cluster_results = []


for key, cluster_records in (
    records_by_cluster.items()
):

    diffraction_preferences = set(
        record[
            "diffraction_best"
        ]
        for record in cluster_records
    )

    cell_preferences = set(
        candidate

        for record
        in cluster_records

        for candidate
        in record[
            "length_best"
        ]
    )

    diffraction_variable = (
        len(
            diffraction_preferences
        )
        > 1
    )

    cell_variable = (
        len(
            cell_preferences
        )
        > 1
    )

    exact_agreement_count = sum(
        record[
            "diffraction_equals_length_best"
        ]
        for record in cluster_records
    )

    pareto_agreement_count = sum(
        record[
            "diffraction_on_cell_pareto"
        ]
        for record in cluster_records
    )

    cluster_results.append(
        {
            "mineral":
                key[0],

            "candidate_set":
                key[1],

            "sample_count":
                len(
                    cluster_records
                ),

            "sample_ids": [
                record[
                    "sample_id"
                ]
                for record
                in cluster_records
            ],

            "diffraction_preferences":
                sorted(
                    diffraction_preferences
                ),

            "cell_preferences":
                sorted(
                    cell_preferences
                ),

            "diffraction_variable":
                diffraction_variable,

            "cell_variable":
                cell_variable,

            "exact_agreement_count":
                exact_agreement_count,

            "pareto_agreement_count":
                pareto_agreement_count,

            "exact_agreement_fraction":
                (
                    exact_agreement_count
                    / len(
                        cluster_records
                    )
                ),

            "pareto_agreement_fraction":
                (
                    pareto_agreement_count
                    / len(
                        cluster_records
                    )
                ),
        }
    )


# ============================================================
# Global output
# ============================================================

print()
print("=" * 108)
print(
    "CELL-DIFFRACTION CONCORDANCE AUDIT"
)
print("=" * 108)

print(
    "Replicate clusters:",
    len(
        records_by_cluster
    ),
)

print(
    "Replicate records:",
    len(records),
)

exact_count = sum(
    record[
        "diffraction_equals_length_best"
    ]
    for record in records
)

pareto_count = sum(
    record[
        "diffraction_on_cell_pareto"
    ]
    for record in records
)

print(
    "Diffraction best = minimum length-difference CIF:",
    exact_count,
    "/",
    len(records),
)

print(
    "Diffraction best lies on cell Pareto front:",
    pareto_count,
    "/",
    len(records),
)

if records:

    print(
        "Exact concordance fraction:",
        f"{exact_count / len(records):.3f}",
    )

    print(
        "Cell-Pareto concordance fraction:",
        f"{pareto_count / len(records):.3f}",
    )


# ============================================================
# Non-unanimous diffraction clusters
# ============================================================

non_unanimous = [
    item
    for item in cluster_results
    if item[
        "diffraction_variable"
    ]
]


print()
print("=" * 108)
print(
    "NON-UNANIMOUS DIFFRACTION CLUSTERS"
)
print("=" * 108)

print(
    "Clusters with variable diffraction preference:",
    len(non_unanimous),
)

print(
    "Of these, clusters also showing variable "
    "cell preference:",
    sum(
        item[
            "cell_variable"
        ]
        for item in non_unanimous
    ),
)

print()
print(
    f"{'Mineral':<24}"
    f"{'N':>4}"
    f"{'Exact':>10}"
    f"{'Pareto':>10}"
    f"{'Diff preferences':<30}"
    f"{'Cell preferences'}"
)


for item in sorted(
    non_unanimous,
    key=lambda x: (
        -x[
            "exact_agreement_fraction"
        ],
        -x[
            "sample_count"
        ],
        x[
            "mineral"
        ],
    )
):

    print(
        f"{item['mineral'][:22]:<24}"
        f"{item['sample_count']:>4d}"
        f"{item['exact_agreement_fraction']:>10.3f}"
        f"{item['pareto_agreement_fraction']:>10.3f}"
        f"{str(item['diffraction_preferences']):<30}"
        f"{item['cell_preferences']}"
    )


# ============================================================
# Pyrope details
# ============================================================

print()
print("=" * 108)
print(
    "PYROPE DETAIL"
)
print("=" * 108)


for record in records:

    if record[
        "mineral"
    ] != "pyrope":
        continue

    print(
        record[
            "sample_id"
        ],
        "| diffraction best =",
        record[
            "diffraction_best"
        ],
        "| length best =",
        record[
            "length_best"
        ],
        "| cell Pareto =",
        record[
            "cell_pareto_front"
        ],
        "| length rank =",
        record[
            "diffraction_length_rank"
        ],
    )


print()
print("=" * 108)
print(
    "AUDIT COMPLETE"
)
print("=" * 108)

