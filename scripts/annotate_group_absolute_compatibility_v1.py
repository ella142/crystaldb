import json
from collections import Counter
from pathlib import Path
from statistics import median


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CALIBRATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_diffraction_calibration_v1.json"
)

GROUP_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_group_diffraction_annotation_v1.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_group_absolute_compatibility_v1.json"
)


# ============================================================
# Load
# ============================================================

calibration = json.loads(
    CALIBRATION_FILE.read_text(
        encoding="utf-8"
    )
)

group_data = json.loads(
    GROUP_FILE.read_text(
        encoding="utf-8"
    )
)

positive_records = (
    calibration["records"]
)

groups = (
    group_data["groups"]
)


# ============================================================
# Metric definitions
#
# compatibility percentile:
#
#   1.0 = candidate is as good as / better than
#         essentially all reference records
#
#   0.0 = candidate is worse than essentially
#         all reference records
#
# This is NOT probability of correctness.
# ============================================================

METRICS = {
    "matched_fraction":
        "higher",

    "median_abs_residual":
        "lower",

    "weighted_mean_abs_residual":
        "lower",

    "max_abs_residual":
        "lower",

    "abs_zero_shift":
        "lower",

    "abs_residual_slope":
        "lower",
}


def extract_metric(
    metrics,
    metric_name,
):

    if metric_name == "abs_zero_shift":

        value = metrics.get(
            "zero_shift"
        )

        if value is None:
            return None

        return abs(
            float(value)
        )

    if metric_name == "abs_residual_slope":

        value = metrics.get(
            "residual_slope"
        )

        if value is None:
            return None

        return abs(
            float(value)
        )

    value = metrics.get(
        metric_name
    )

    if value is None:
        return None

    return float(
        value
    )


def empirical_compatibility(
    value,
    reference_values,
    direction,
):

    if (
        value is None
        or not reference_values
    ):
        return None

    if direction == "higher":

        favorable_or_equal = sum(
            reference_value
            <= value

            for reference_value
            in reference_values
        )

    elif direction == "lower":

        favorable_or_equal = sum(
            reference_value
            >= value

            for reference_value
            in reference_values
        )

    else:

        raise ValueError(
            direction
        )

    return (
        favorable_or_equal
        / len(
            reference_values
        )
    )


def percentile(
    values,
    q,
):

    values = sorted(
        float(value)
        for value in values
    )

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = (
        (len(values) - 1)
        * q
    )

    lower = int(
        position
    )

    upper = min(
        lower + 1,
        len(values) - 1,
    )

    fraction = (
        position
        - lower
    )

    return (
        values[lower]
        * (
            1.0 - fraction
        )
        +
        values[upper]
        * fraction
    )


# ============================================================
# Build reference distributions
# ============================================================

primary_records = [
    record
    for record in positive_records

    if record.get(
        "resolution_status"
    )
    == "unique_bibliographic_match"
]

all_records = list(
    positive_records
)


def build_reference_set(
    records,
):

    output = {
        "n":
            len(records),

        "metrics":
            {},
    }

    for metric_name in METRICS:

        values = []

        for record in records:

            value = extract_metric(
                record[
                    "metrics"
                ],
                metric_name,
            )

            if value is not None:

                values.append(
                    value
                )

        output[
            "metrics"
        ][
            metric_name
        ] = values

    return output


def radiation_subset(
    records,
    radiation_class,
):

    return [
        record
        for record in records

        if (
            record.get(
                "radiation",
                {},
            ).get(
                "radiation_class"
            )
            == radiation_class
        )
    ]


radiation_classes = sorted(
    {
        record.get(
            "radiation",
            {},
        ).get(
            "radiation_class"
        )

        for record in positive_records

        if record.get(
            "radiation",
            {},
        ).get(
            "radiation_class"
        )
    }
)


reference_sets = {
    "primary_global":
        build_reference_set(
            primary_records
        ),

    "all560_global":
        build_reference_set(
            all_records
        ),
}


for radiation_class in radiation_classes:

    reference_sets[
        "primary_"
        + radiation_class
    ] = build_reference_set(
        radiation_subset(
            primary_records,
            radiation_class,
        )
    )

    reference_sets[
        "all560_"
        + radiation_class
    ] = build_reference_set(
        radiation_subset(
            all_records,
            radiation_class,
        )
    )


# ============================================================
# Candidate compatibility
# ============================================================

def annotate_candidate(
    candidate,
    radiation_class,
):

    metrics = candidate[
        "metrics"
    ]

    extracted = {
        metric_name:
            extract_metric(
                metrics,
                metric_name,
            )

        for metric_name
        in METRICS
    }

    compatibility = {}

    relevant_reference_sets = [
        "primary_global",
        "all560_global",
        (
            "primary_"
            + radiation_class
        ),
        (
            "all560_"
            + radiation_class
        ),
    ]

    for reference_name in (
        relevant_reference_sets
    ):

        reference = (
            reference_sets.get(
                reference_name
            )
        )

        if (
            reference is None
            or reference[
                "n"
            ]
            == 0
        ):
            continue

        compatibility[
            reference_name
        ] = {
            "reference_n":
                reference[
                    "n"
                ],

            "metric_percentiles":
                {},
        }

        for (
            metric_name,
            direction,
        ) in METRICS.items():

            compatibility[
                reference_name
            ][
                "metric_percentiles"
            ][
                metric_name
            ] = (
                empirical_compatibility(
                    extracted[
                        metric_name
                    ],
                    reference[
                        "metrics"
                    ][
                        metric_name
                    ],
                    direction,
                )
            )

    return {
        "source_id":
            str(
                candidate[
                    "source_id"
                ]
            ),

        "file_path":
            candidate.get(
                "file_path"
            ),

        "metrics":
            metrics,

        "derived_metrics":
            {
                "abs_zero_shift":
                    extracted[
                        "abs_zero_shift"
                    ],

                "abs_residual_slope":
                    extracted[
                        "abs_residual_slope"
                    ],
            },

        "compatibility":
            compatibility,
    }


# ============================================================
# Group-level annotation
# ============================================================

annotated_groups = []


for group in groups:

    radiation_class = (
        group[
            "radiation"
        ][
            "radiation_class"
        ]
    )

    candidate_annotations = [
        annotate_candidate(
            candidate,
            radiation_class,
        )

        for candidate
        in group[
            "candidate_results"
        ]
    ]

    best_source_id = str(
        group[
            "lowest_weighted_residual_candidate"
        ]
    )

    best_annotation = next(
        candidate
        for candidate
        in candidate_annotations

        if candidate[
            "source_id"
        ]
        == best_source_id
    )

    same_radiation_reference = (
        "primary_"
        + radiation_class
    )

    same_radiation_profile = (
        best_annotation[
            "compatibility"
        ].get(
            same_radiation_reference
        )
    )

    # --------------------------------------------------------
    # Descriptive empirical P95 marginal envelope.
    #
    # compatibility >= 0.05 means the candidate is not
    # worse than ~95% of positive-reference records
    # on that single metric.
    #
    # NOT a pass/fail rule.
    # --------------------------------------------------------

    marginal_inside = {}

    if same_radiation_profile:

        metric_percentiles = (
            same_radiation_profile[
                "metric_percentiles"
            ]
        )

        for metric_name in METRICS:

            value = (
                metric_percentiles.get(
                    metric_name
                )
            )

            marginal_inside[
                metric_name
            ] = (
                value is not None
                and
                value >= 0.05
            )

    core_metrics = [
        "matched_fraction",
        "median_abs_residual",
        "weighted_mean_abs_residual",
    ]

    all_metrics = list(
        METRICS.keys()
    )

    core_inside = (
        bool(
            marginal_inside
        )
        and
        all(
            marginal_inside.get(
                metric,
                False,
            )
            for metric
            in core_metrics
        )
    )

    all_inside = (
        bool(
            marginal_inside
        )
        and
        all(
            marginal_inside.get(
                metric,
                False,
            )
            for metric
            in all_metrics
        )
    )

    annotated_groups.append(
        {
            "sample_id":
                group[
                    "sample_id"
                ],

            "mineral":
                group.get(
                    "mineral"
                ),

            "measurement_id":
                group[
                    "measurement_id"
                ],

            "radiation_class":
                radiation_class,

            "bibliographic_candidate_count":
                group[
                    "bibliographic_candidate_count"
                ],

            "best_source_id":
                best_source_id,

            "best_vs_runner_up_separation":
                group.get(
                    "best_vs_runner_up_separation"
                ),

            "weighted_residual_gap":
                group.get(
                    "weighted_residual_gap"
                ),

            "pareto_front_size":
                group.get(
                    "pareto_front_size"
                ),

            "candidate_annotations":
                candidate_annotations,

            "best_candidate":
                best_annotation,

            "descriptive_primary_same_radiation_p95_envelope":
                {
                    "reference_set":
                        same_radiation_reference,

                    "reference_n":
                        (
                            same_radiation_profile[
                                "reference_n"
                            ]
                            if same_radiation_profile
                            else 0
                        ),

                    "marginal_inside":
                        marginal_inside,

                    "core_three_inside":
                        core_inside,

                    "all_six_inside":
                        all_inside,

                    "important_note":
                        (
                            "Descriptive empirical "
                            "reference envelope only; "
                            "not a structure-resolution "
                            "threshold."
                        ),
                },
        }
    )


# ============================================================
# Console summary
# ============================================================

print()
print("=" * 112)
print(
    "ABSOLUTE DIFFRACTION COMPATIBILITY V1"
)
print("=" * 112)

print(
    "Positive-reference records:",
    len(
        positive_records
    ),
)

print(
    "Primary unique-bibliographic records:",
    len(
        primary_records
    ),
)

print(
    "Groups analysed:",
    len(
        annotated_groups
    ),
)


print()
print("=" * 112)
print(
    "REFERENCE SET COUNTS"
)
print("=" * 112)

for name, reference in (
    reference_sets.items()
):

    print(
        f"{name:<32}"
        f"{reference['n']:>6}"
    )


# ============================================================
# Best-candidate empirical compatibility
# ============================================================

print()
print("=" * 112)
print(
    "BEST-CANDIDATE COMPATIBILITY "
    "AGAINST PRIMARY SAME-RADIATION REFERENCES"
)
print("=" * 112)

print(
    "Higher compatibility percentile = "
    "more favorable relative to positive references."
)

print(
    "This is NOT probability of correctness."
)

print()

print(
    f"{'Metric':<36}"
    f"{'P10':>12}"
    f"{'P25':>12}"
    f"{'P50':>12}"
    f"{'P75':>12}"
)


for metric_name in METRICS:

    values = []

    for group in annotated_groups:

        reference_name = (
            "primary_"
            + group[
                "radiation_class"
            ]
        )

        profile = (
            group[
                "best_candidate"
            ][
                "compatibility"
            ].get(
                reference_name
            )
        )

        if not profile:
            continue

        value = (
            profile[
                "metric_percentiles"
            ].get(
                metric_name
            )
        )

        if value is not None:

            values.append(
                value
            )

    print(
        f"{metric_name:<36}"
        f"{percentile(values, 0.10):>12.3f}"
        f"{percentile(values, 0.25):>12.3f}"
        f"{percentile(values, 0.50):>12.3f}"
        f"{percentile(values, 0.75):>12.3f}"
    )


# ============================================================
# Descriptive P95 marginal envelope
# ============================================================

print()
print("=" * 112)
print(
    "DESCRIPTIVE PRIMARY SAME-RADIATION "
    "P95 MARGINAL ENVELOPE"
)
print("=" * 112)

print(
    "NOTE: this is a descriptive tail audit, "
    "not a pass/fail threshold."
)

print()

for metric_name in METRICS:

    count = sum(
        group[
            "descriptive_primary_same_radiation_p95_envelope"
        ][
            "marginal_inside"
        ].get(
            metric_name,
            False,
        )

        for group in annotated_groups
    )

    print(
        f"{metric_name:<36}"
        f"{count:>5} / "
        f"{len(annotated_groups)}"
        f" = "
        f"{count / len(annotated_groups):.3f}"
    )


core_inside_count = sum(
    group[
        "descriptive_primary_same_radiation_p95_envelope"
    ][
        "core_three_inside"
    ]
    for group in annotated_groups
)

all_inside_count = sum(
    group[
        "descriptive_primary_same_radiation_p95_envelope"
    ][
        "all_six_inside"
    ]
    for group in annotated_groups
)


print()

print(
    "Core three metrics simultaneously inside:",
    core_inside_count,
    "/",
    len(
        annotated_groups
    ),
    "=",
    f"{core_inside_count / len(annotated_groups):.3f}",
)

print(
    "All six metrics simultaneously inside:  ",
    all_inside_count,
    "/",
    len(
        annotated_groups
    ),
    "=",
    f"{all_inside_count / len(annotated_groups):.3f}",
)


# ============================================================
# Radiation-specific summary
# ============================================================

print()
print("=" * 112)
print(
    "GROUP BEST-CANDIDATE SUMMARY BY RADIATION"
)
print("=" * 112)

group_radiation_counts = Counter(
    group[
        "radiation_class"
    ]
    for group in annotated_groups
)


for radiation_class, count in sorted(
    group_radiation_counts.items()
):

    subset = [
        group
        for group in annotated_groups

        if group[
            "radiation_class"
        ]
        == radiation_class
    ]

    core_count = sum(
        group[
            "descriptive_primary_same_radiation_p95_envelope"
        ][
            "core_three_inside"
        ]
        for group in subset
    )

    all_count = sum(
        group[
            "descriptive_primary_same_radiation_p95_envelope"
        ][
            "all_six_inside"
        ]
        for group in subset
    )

    reference_name = (
        "primary_"
        + radiation_class
    )

    reference_n = (
        reference_sets.get(
            reference_name,
            {},
        ).get(
            "n",
            0,
        )
    )

    print(
        radiation_class,
        "| groups =",
        count,
        "| primary reference n =",
        reference_n,
        "| core3 inside =",
        f"{core_count}/{count}",
        "| all6 inside =",
        f"{all_count}/{count}",
    )

    if reference_n < 20:

        print(
            "  WARNING: small same-radiation "
            "primary reference set; "
            "interpret empirical percentiles cautiously."
        )


# ============================================================
# Lowest core compatibility examples
# ============================================================

def minimum_core_compatibility(
    group,
):

    reference_name = (
        "primary_"
        + group[
            "radiation_class"
        ]
    )

    profile = (
        group[
            "best_candidate"
        ][
            "compatibility"
        ].get(
            reference_name
        )
    )

    if not profile:
        return -1.0

    values = []

    for metric_name in [
        "matched_fraction",
        "median_abs_residual",
        "weighted_mean_abs_residual",
    ]:

        value = (
            profile[
                "metric_percentiles"
            ].get(
                metric_name
            )
        )

        if value is not None:

            values.append(
                value
            )

    if not values:
        return -1.0

    return min(
        values
    )


review_examples = sorted(
    annotated_groups,
    key=
        minimum_core_compatibility,
)


print()
print("=" * 112)
print(
    "15 LOWEST CORE-COMPATIBILITY "
    "BEST CANDIDATES"
)
print("=" * 112)

print(
    f"{'sample':<12}"
    f"{'mineral':<24}"
    f"{'best':<12}"
    f"{'radiation':<12}"
    f"{'min core':>12}"
    f"{'sep':>12}"
    f"{'gap':>12}"
)


for group in review_examples[:15]:

    separation = (
        group.get(
            "best_vs_runner_up_separation"
        )
        or {}
    ).get(
        "median_nearest_difference"
    )

    print(
        f"{group['sample_id']:<12}"
        f"{str(group.get('mineral'))[:22]:<24}"
        f"{group['best_source_id']:<12}"
        f"{group['radiation_class']:<12}"
        f"{minimum_core_compatibility(group):>12.3f}"
        f"{separation if separation is not None else float('nan'):>12.5f}"
        f"{group['weighted_residual_gap'] if group['weighted_residual_gap'] is not None else float('nan'):>12.5f}"
    )


# ============================================================
# Save
# ============================================================

reference_summary = {}


for name, reference in (
    reference_sets.items()
):

    reference_summary[
        name
    ] = {
        "n":
            reference[
                "n"
            ],

        "metric_percentiles": {},
    }

    for metric_name in METRICS:

        values = (
            reference[
                "metrics"
            ][
                metric_name
            ]
        )

        reference_summary[
            name
        ][
            "metric_percentiles"
        ][
            metric_name
        ] = {
            "p05":
                percentile(
                    values,
                    0.05,
                ),

            "p10":
                percentile(
                    values,
                    0.10,
                ),

            "p50":
                percentile(
                    values,
                    0.50,
                ),

            "p90":
                percentile(
                    values,
                    0.90,
                ),

            "p95":
                percentile(
                    values,
                    0.95,
                ),
        }


output = {
    "version":
        "1.0",

    "purpose":
        (
            "Absolute diffraction compatibility "
            "annotation for bibliography-supported "
            "RRUFF candidate groups, calibrated "
            "against positive-reference records."
        ),

    "important_note":
        (
            "Empirical compatibility percentiles "
            "describe position within the positive-"
            "reference distribution. They are not "
            "probabilities of correctness and are "
            "not automatic resolution thresholds."
        ),

    "inputs": {
        "positive_calibration":
            "data/mappings/"
            "rruff_diffraction_calibration_v1.json",

        "group_annotation":
            "data/mappings/"
            "rruff_group_diffraction_annotation_v1.json",
    },

    "metric_directions":
        METRICS,

    "reference_sets":
        reference_summary,

    "counts": {
        "positive_records":
            len(
                positive_records
            ),

        "primary_unique_bibliographic_records":
            len(
                primary_records
            ),

        "groups":
            len(
                annotated_groups
            ),

        "core_three_inside_descriptive_p95":
            core_inside_count,

        "all_six_inside_descriptive_p95":
            all_inside_count,
    },

    "groups":
        annotated_groups,
}


OUTPUT_FILE.write_text(
    json.dumps(
        output,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print()
print(
    "Saved:",
    OUTPUT_FILE,
)

print()
print("=" * 112)
print(
    "ABSOLUTE DIFFRACTION COMPATIBILITY V1 COMPLETE"
)
print("=" * 112)

