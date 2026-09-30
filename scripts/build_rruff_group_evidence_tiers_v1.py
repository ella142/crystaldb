import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GROUP_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_group_diffraction_annotation_v1.json"
)

ABSOLUTE_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_group_absolute_compatibility_v1.json"
)

RESOLUTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_experimental_resolution_v1.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_group_evidence_tiers_v1.json"
)


# ============================================================
# Load frozen inputs
# ============================================================

group_data = json.loads(
    GROUP_FILE.read_text(
        encoding="utf-8"
    )
)

absolute_data = json.loads(
    ABSOLUTE_FILE.read_text(
        encoding="utf-8"
    )
)

resolution_data = json.loads(
    RESOLUTION_FILE.read_text(
        encoding="utf-8"
    )
)


absolute_by_sample = {
    item["sample_id"]: item
    for item in absolute_data["groups"]
}

resolution_by_sample = {
    item["sample_id"]: item
    for item in resolution_data["records"]
}


# ============================================================
# Cell evidence
# ============================================================

def cell_pareto_annotation(
    sample_id,
    best_source_id,
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

        return {
            "available":
                False,

            "pareto_front_candidates":
                [],

            "best_on_cell_pareto":
                None,

            "minimum_length_candidates":
                [],

            "best_is_minimum_length":
                None,
        }


    minimum_length = min(
        item[
            "length_diff"
        ]
        for item in usable
    )

    minimum_length_candidates = [
        item[
            "source_id"
        ]
        for item in usable

        if item[
            "length_diff"
        ]
        == minimum_length
    ]


    pareto = []

    for candidate in usable:

        dominated = False

        for other in usable:

            if (
                other[
                    "source_id"
                ]
                == candidate[
                    "source_id"
                ]
            ):
                continue

            at_least_as_good = (
                other[
                    "length_diff"
                ]
                <= candidate[
                    "length_diff"
                ]
                and
                other[
                    "angle_diff"
                ]
                <= candidate[
                    "angle_diff"
                ]
            )

            strictly_better = (
                other[
                    "length_diff"
                ]
                < candidate[
                    "length_diff"
                ]
                or
                other[
                    "angle_diff"
                ]
                < candidate[
                    "angle_diff"
                ]
            )

            if (
                at_least_as_good
                and strictly_better
            ):
                dominated = True
                break

        if not dominated:

            pareto.append(
                candidate[
                    "source_id"
                ]
            )


    return {
        "available":
            True,

        "pareto_front_candidates":
            pareto,

        "best_on_cell_pareto":
            (
                best_source_id
                in pareto
            ),

        "minimum_length_candidates":
            minimum_length_candidates,

        "best_is_minimum_length":
            (
                best_source_id
                in minimum_length_candidates
            ),
    }


# ============================================================
# Tier assignment
#
# IMPORTANT:
# Evidence tiers describe diffraction support.
# They do NOT replace bibliography-supported group identity
# and do NOT automatically promote a group to a unique record.
# ============================================================

def assign_tier(
    radiation_class,
    core_inside,
    separation,
    unique_diffraction_pareto,
    cell_available,
    best_on_cell_pareto,
):

    # Mo calibration is too sparse for calibrated tiers.
    if radiation_class != "Cu-like":

        return (
            "sparse_calibration",
            "same-radiation positive-reference calibration is too small"
        )


    # Absolute fit itself is outside the empirical positive
    # reference envelope.
    if not core_inside:

        return (
            "poor_absolute_compatibility",
            "best candidate is outside the empirical P95 envelope on at least one core metric"
        )


    if separation is None:

        return (
            "insufficient_relative_evidence",
            "best-vs-runner theoretical separation is unavailable"
        )


    # Essentially non-discriminating candidate records.
    if separation <= 0.05:

        return (
            "non_discriminating",
            "best and runner-up theoretical PXRD patterns are weakly separable"
        )


    # Intermediate zone from the frozen descriptive strata.
    if separation <= 0.10:

        return (
            "intermediate_ambiguity",
            "candidate separability is intermediate"
        )


    # separation > 0.10 from here onward

    if not unique_diffraction_pareto:

        return (
            "limited_diffraction_support",
            "patterns are separable but diffraction Pareto evidence is not unique"
        )


    if (
        cell_available
        and best_on_cell_pareto
    ):

        return (
            "high_diffraction_support",
            "absolute compatibility, separability, unique diffraction Pareto status, and cell concordance align"
        )


    return (
        "moderate_diffraction_support",
        "absolute compatibility, separability, and unique diffraction Pareto status align, but cell concordance is absent"
    )


# ============================================================
# Build tiered records
# ============================================================

records = []


for group in group_data["groups"]:

    sample_id = (
        group[
            "sample_id"
        ]
    )

    absolute = (
        absolute_by_sample[
            sample_id
        ]
    )

    best_source_id = str(
        group[
            "lowest_weighted_residual_candidate"
        ]
    )

    radiation_class = (
        group[
            "radiation"
        ][
            "radiation_class"
        ]
    )

    envelope = (
        absolute[
            "descriptive_primary_same_radiation_p95_envelope"
        ]
    )

    core_inside = (
        envelope[
            "core_three_inside"
        ]
    )

    separation_object = (
        group.get(
            "best_vs_runner_up_separation"
        )
    )

    separation = (
        separation_object.get(
            "median_nearest_difference"
        )
        if separation_object
        else None
    )

    unique_diffraction_pareto = (
        group[
            "pareto_front_size"
        ]
        == 1

        and

        best_source_id
        in group[
            "pareto_front_candidates"
        ]
    )

    cell = (
        cell_pareto_annotation(
            sample_id,
            best_source_id,
        )
    )

    tier, reason = assign_tier(
        radiation_class=
            radiation_class,

        core_inside=
            core_inside,

        separation=
            separation,

        unique_diffraction_pareto=
            unique_diffraction_pareto,

        cell_available=
            cell[
                "available"
            ],

        best_on_cell_pareto=
            cell[
                "best_on_cell_pareto"
            ],
    )


    records.append(
        {
            "sample_id":
                sample_id,

            "mineral":
                group.get(
                    "mineral"
                ),

            "measurement_id":
                group[
                    "measurement_id"
                ],

            "original_resolution_level":
                "group",

            "bibliographic_candidate_count":
                group[
                    "bibliographic_candidate_count"
                ],

            "best_diffraction_candidate":
                best_source_id,

            "runner_up_diffraction_candidate":
                group.get(
                    "runner_up_weighted_residual_candidate"
                ),

            "radiation_class":
                radiation_class,

            "evidence_tier":
                tier,

            "tier_reason":
                reason,

            "absolute_compatibility": {
                "core_three_inside_empirical_p95":
                    core_inside,

                "all_six_inside_empirical_p95":
                    envelope[
                        "all_six_inside"
                    ],

                "reference_set":
                    envelope[
                        "reference_set"
                    ],

                "reference_n":
                    envelope[
                        "reference_n"
                    ],
            },

            "relative_diffraction": {
                "weighted_residual_gap":
                    group.get(
                        "weighted_residual_gap"
                    ),

                "best_runner_median_peak_separation":
                    separation,

                "separability_bin":
                    (
                        separation_object.get(
                            "separability_bin"
                        )
                        if separation_object
                        else None
                    ),

                "diffraction_pareto_front":
                    group[
                        "pareto_front_candidates"
                    ],

                "diffraction_pareto_front_size":
                    group[
                        "pareto_front_size"
                    ],

                "best_is_unique_diffraction_pareto":
                    unique_diffraction_pareto,
            },

            "cell_concordance":
                cell,

            "important_note":
                (
                    "Evidence tier describes support for "
                    "the diffraction-preferred candidate. "
                    "It does not automatically convert "
                    "the bibliography-supported candidate "
                    "group into a unique ground-truth record."
                ),
        }
    )


# ============================================================
# Summary
# ============================================================

tier_counts = Counter(
    record[
        "evidence_tier"
    ]
    for record in records
)


print()
print("=" * 112)
print(
    "RRUFF GROUP EVIDENCE TIERS V1"
)
print("=" * 112)

print(
    "Group records:",
    len(records),
)

print()

print(
    f"{'Evidence tier':<38}"
    f"{'N':>8}"
    f"{'Fraction':>14}"
)


tier_order = [
    "high_diffraction_support",
    "moderate_diffraction_support",
    "limited_diffraction_support",
    "intermediate_ambiguity",
    "non_discriminating",
    "poor_absolute_compatibility",
    "insufficient_relative_evidence",
    "sparse_calibration",
]


for tier in tier_order:

    count = (
        tier_counts.get(
            tier,
            0,
        )
    )

    print(
        f"{tier:<38}"
        f"{count:>8d}"
        f"{count / len(records):>14.3f}"
    )


# ============================================================
# High-support examples
# ============================================================

print()
print("=" * 112)
print(
    "HIGH DIFFRACTION SUPPORT EXAMPLES"
)
print("=" * 112)

print(
    f"{'sample':<12}"
    f"{'mineral':<24}"
    f"{'best':<12}"
    f"{'runner':<12}"
    f"{'sep':>12}"
    f"{'gap':>12}"
)


high_records = [
    record
    for record in records

    if record[
        "evidence_tier"
    ]
    == "high_diffraction_support"
]


high_records.sort(
    key=lambda record:
        (
            -record[
                "relative_diffraction"
            ][
                "best_runner_median_peak_separation"
            ],
            -record[
                "relative_diffraction"
            ][
                "weighted_residual_gap"
            ],
        )
)


for record in high_records[:20]:

    print(
        f"{record['sample_id']:<12}"
        f"{str(record.get('mineral'))[:22]:<24}"
        f"{record['best_diffraction_candidate']:<12}"
        f"{str(record['runner_up_diffraction_candidate']):<12}"
        f"{record['relative_diffraction']['best_runner_median_peak_separation']:>12.5f}"
        f"{record['relative_diffraction']['weighted_residual_gap']:>12.5f}"
    )


# ============================================================
# Save
# ============================================================

output = {
    "version":
        "1.0",

    "purpose":
        (
            "Calibrated diffraction-evidence tiers "
            "for 188 bibliography-supported RRUFF "
            "candidate groups."
        ),

    "important_note":
        (
            "These tiers annotate evidence strength. "
            "They do not automatically collapse a "
            "candidate group to a unique ground-truth CIF."
        ),

    "calibration_basis": {
        "blind_joint_evidence":
            "data/mappings/"
            "rruff_blind_joint_evidence_calibration_v1.json",

        "group_diffraction_annotation":
            "data/mappings/"
            "rruff_group_diffraction_annotation_v1.json",

        "absolute_compatibility":
            "data/mappings/"
            "rruff_group_absolute_compatibility_v1.json",
    },

    "tier_definition_notes": {
        "high_diffraction_support":
            (
                "Cu-like; core three absolute metrics "
                "inside empirical P95; best-runner "
                "separation >0.10 deg; unique diffraction "
                "Pareto candidate; best candidate lies "
                "on cell Pareto front."
            ),

        "moderate_diffraction_support":
            (
                "Same as high support through unique "
                "diffraction Pareto status, but without "
                "cell-Pareto concordance."
            ),

        "limited_diffraction_support":
            (
                "Absolute compatibility and >0.10 deg "
                "separability, but diffraction Pareto "
                "front remains non-unique."
            ),

        "intermediate_ambiguity":
            (
                "Best-runner separation >0.05 and "
                "<=0.10 deg."
            ),

        "non_discriminating":
            (
                "Best-runner separation <=0.05 deg."
            ),

        "poor_absolute_compatibility":
            (
                "Best candidate falls outside the "
                "descriptive empirical P95 envelope "
                "on at least one core metric."
            ),

        "sparse_calibration":
            (
                "Same-radiation calibration support "
                "is sparse; currently applies to "
                "Mo-like groups."
            ),
    },

    "counts": {
        "groups":
            len(records),

        "tiers":
            dict(
                tier_counts
            ),
    },

    "records":
        records,
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
    "GROUP EVIDENCE TIERS V1 COMPLETE"
)
print("=" * 112)

