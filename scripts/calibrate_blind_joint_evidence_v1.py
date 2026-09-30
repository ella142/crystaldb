import json
from collections import defaultdict
from math import asin, cos, degrees, radians, sin
from pathlib import Path

import gemmi
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONTRAST_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_candidate_contrast_calibration_v1.json"
)

RESOLUTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_experimental_resolution_v1.json"
)

POSITIVE_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_diffraction_calibration_v1.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_blind_joint_evidence_calibration_v1.json"
)


TOP_THEORETICAL = 20


# ============================================================
# Load
# ============================================================

contrast = json.loads(
    CONTRAST_FILE.read_text(
        encoding="utf-8"
    )
)

resolution_data = json.loads(
    RESOLUTION_FILE.read_text(
        encoding="utf-8"
    )
)

positive_data = json.loads(
    POSITIVE_FILE.read_text(
        encoding="utf-8"
    )
)


record_results = contrast[
    "record_results"
]

pair_results = contrast[
    "pair_results"
]


resolution_by_sample = {
    record["sample_id"]: record
    for record in resolution_data["records"]
}


positive_primary = [
    record
    for record in positive_data["records"]

    if record.get(
        "resolution_status"
    )
    == "unique_bibliographic_match"
]


pairs_by_sample = defaultdict(list)

for pair in pair_results:

    pairs_by_sample[
        pair["sample_id"]
    ].append(
        pair
    )


db = MongoClient(
    "mongodb://localhost:27017"
)["rruff"]


# ============================================================
# Generic helpers
# ============================================================

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
        position - lower
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


def separation_bin(
    value,
):

    if value is None:
        return "missing"

    if value <= 0.02:
        return "le_0.02"

    if value <= 0.05:
        return "0.02_to_0.05"

    if value <= 0.10:
        return "0.05_to_0.10"

    return "gt_0.10"


# ============================================================
# Diffraction calculation
# Only needed when blind best and runner-up are both
# alternatives, because selected-vs-alternative separation
# already exists in contrast v1.1.
# ============================================================

def two_theta_from_d(
    d_spacing,
    wavelength,
):

    argument = (
        wavelength
        / (
            2.0
            * float(d_spacing)
        )
    )

    if (
        argument <= 0
        or argument > 1
    ):
        return None

    return (
        2.0
        * degrees(
            asin(argument)
        )
    )


def multiplicity(
    spacegroup,
    hkl,
):

    equivalents = set()

    for operation in (
        spacegroup.operations()
    ):

        transformed = tuple(
            int(value)
            for value
            in operation.apply_to_hkl(
                hkl
            )
        )

        equivalents.add(
            transformed
        )

        equivalents.add(
            tuple(
                -value
                for value
                in transformed
            )
        )

    return len(
        equivalents
    )


def lorentz_polarization(
    two_theta,
):

    theta = radians(
        two_theta / 2.0
    )

    two_theta_rad = radians(
        two_theta
    )

    denominator = (
        sin(theta) ** 2
        * cos(theta)
    )

    if denominator <= 0:
        return 0.0

    return (
        1.0
        + cos(
            two_theta_rad
        ) ** 2
    ) / denominator


def calculate_top_reflections(
    cif_path,
    wavelength,
    raw_min,
    raw_max,
):

    document = gemmi.cif.read_file(
        str(cif_path)
    )

    structure = (
        gemmi.make_small_structure_from_block(
            document.sole_block()
        )
    )

    spacegroup = (
        structure.spacegroup
    )

    if spacegroup is None:

        structure.determine_and_set_spacegroup()

        spacegroup = (
            structure.spacegroup
        )

    if spacegroup is None:

        raise RuntimeError(
            "Unable to determine space group."
        )

    d_min = (
        wavelength
        / (
            2.0
            * sin(
                radians(
                    raw_max / 2.0
                )
            )
        )
    )

    d_max = (
        wavelength
        / (
            2.0
            * sin(
                radians(
                    raw_min / 2.0
                )
            )
        )
    )

    miller_array = (
        gemmi.make_miller_array(
            structure.cell,
            spacegroup,
            d_min,
            d_max,
            True,
        )
    )

    sf_calculator = (
        gemmi.StructureFactorCalculatorX(
            structure.cell
        )
    )

    reflections = []

    for hkl_array in miller_array:

        hkl = tuple(
            int(value)
            for value
            in hkl_array
        )

        if (
            spacegroup.operations()
            .is_systematically_absent(
                hkl
            )
        ):
            continue

        d_spacing = (
            structure.cell.calculate_d(
                hkl
            )
        )

        two_theta = (
            two_theta_from_d(
                d_spacing,
                wavelength,
            )
        )

        if (
            two_theta is None
            or not (
                raw_min
                <= two_theta
                <= raw_max
            )
        ):
            continue

        sf = (
            sf_calculator
            .calculate_sf_from_small_structure(
                structure,
                hkl,
            )
        )

        intensity = (
            abs(sf) ** 2
            * multiplicity(
                spacegroup,
                hkl,
            )
            * lorentz_polarization(
                two_theta
            )
        )

        reflections.append(
            {
                "two_theta":
                    two_theta,

                "intensity":
                    intensity,
            }
        )

    if not reflections:

        raise RuntimeError(
            "No theoretical reflections."
        )

    maximum = max(
        item["intensity"]
        for item in reflections
    )

    if maximum <= 0:

        raise RuntimeError(
            "Calculated intensities all zero."
        )

    for item in reflections:

        item[
            "relative_intensity"
        ] = (
            item["intensity"]
            / maximum
            * 100.0
        )

    return sorted(
        reflections,
        key=lambda item:
            item[
                "relative_intensity"
            ],
        reverse=True,
    )[:TOP_THEORETICAL]


def theoretical_separation(
    left,
    right,
):

    distances = []

    for source, target in [
        (
            left,
            right,
        ),
        (
            right,
            left,
        ),
    ]:

        for peak in source:

            nearest = min(
                abs(
                    peak[
                        "two_theta"
                    ]
                    -
                    other[
                        "two_theta"
                    ]
                )
                for other in target
            )

            distances.append(
                nearest
            )

    return {
        "median_nearest_difference":
            percentile(
                distances,
                0.50,
            ),

        "mean_nearest_difference":
            (
                sum(distances)
                / len(distances)
            ),

        "max_nearest_difference":
            max(
                distances
            ),

        "comparison_count":
            len(
                distances
            ),
    }


# ============================================================
# Candidate reconstruction
# ============================================================

def rebuild_candidates(
    record,
    sample_pairs,
):

    selected_id = str(
        record[
            "selected_source_id"
        ]
    )

    candidates = {
        selected_id: {
            "source_id":
                selected_id,

            "metrics":
                record[
                    "selected_metrics"
                ],
        }
    }

    for pair in sample_pairs:

        source_id = str(
            pair[
                "alternative_source_id"
            ]
        )

        candidates[
            source_id
        ] = {
            "source_id":
                source_id,

            "metrics":
                pair[
                    "alternative_metrics"
                ],
        }

    valid = [
        candidate
        for candidate
        in candidates.values()

        if candidate[
            "metrics"
        ].get(
            "weighted_mean_abs_residual"
        )
        is not None
    ]

    valid.sort(
        key=lambda candidate:
            candidate[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
    )

    return valid


# ============================================================
# Diffraction Pareto front
# ============================================================

def diffraction_pareto_front(
    candidates,
):

    front = []

    for candidate in candidates:

        candidate_fraction = (
            candidate[
                "metrics"
            ][
                "matched_fraction"
            ]
        )

        candidate_residual = (
            candidate[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
        )

        dominated = False

        for other in candidates:

            if (
                other[
                    "source_id"
                ]
                == candidate[
                    "source_id"
                ]
            ):
                continue

            other_fraction = (
                other[
                    "metrics"
                ][
                    "matched_fraction"
                ]
            )

            other_residual = (
                other[
                    "metrics"
                ][
                    "weighted_mean_abs_residual"
                ]
            )

            at_least_as_good = (
                other_fraction
                >= candidate_fraction
                and
                other_residual
                <= candidate_residual
            )

            strictly_better = (
                other_fraction
                > candidate_fraction
                or
                other_residual
                < candidate_residual
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
# Cell concordance
# ============================================================

def cell_annotation(
    sample_id,
    blind_best_id,
):

    resolution = (
        resolution_by_sample[
            sample_id
        ][
            "structure_resolution"
        ]
    )

    usable = []

    for candidate in (
        resolution[
            "all_sample_structure_candidates"
        ]
    ):

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
        }

    min_length = min(
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
        == min_length
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

        "minimum_length_candidates":
            minimum_length_candidates,

        "pareto_front_candidates":
            pareto,

        "blind_best_is_minimum_length":
            blind_best_id
            in minimum_length_candidates,

        "blind_best_on_cell_pareto":
            blind_best_id
            in pareto,
    }


# ============================================================
# Absolute compatibility:
# leave-one-out same-radiation positive reference
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

        return (
            abs(
                float(value)
            )
            if value is not None
            else None
        )

    if metric_name == "abs_residual_slope":

        value = metrics.get(
            "residual_slope"
        )

        return (
            abs(
                float(value)
            )
            if value is not None
            else None
        )

    value = metrics.get(
        metric_name
    )

    return (
        float(value)
        if value is not None
        else None
    )


def empirical_compatibility(
    value,
    references,
    direction,
):

    if (
        value is None
        or not references
    ):
        return None

    if direction == "higher":

        favorable = sum(
            reference
            <= value
            for reference
            in references
        )

    else:

        favorable = sum(
            reference
            >= value
            for reference
            in references
        )

    return (
        favorable
        / len(references)
    )


def absolute_compatibility(
    sample_id,
    radiation_class,
    metrics,
):

    # Leave the current sample out of its own
    # positive-reference distribution.

    reference_records = [
        record
        for record
        in positive_primary

        if (
            record[
                "sample_id"
            ]
            != sample_id

            and

            record.get(
                "radiation",
                {},
            ).get(
                "radiation_class"
            )
            == radiation_class
        )
    ]

    percentiles = {}

    for (
        metric_name,
        direction,
    ) in METRICS.items():

        value = extract_metric(
            metrics,
            metric_name,
        )

        reference_values = [
            extract_metric(
                record[
                    "metrics"
                ],
                metric_name,
            )

            for record
            in reference_records
        ]

        reference_values = [
            value
            for value
            in reference_values
            if value is not None
        ]

        percentiles[
            metric_name
        ] = empirical_compatibility(
            value,
            reference_values,
            direction,
        )

    core_names = [
        "matched_fraction",
        "median_abs_residual",
        "weighted_mean_abs_residual",
    ]

    core_values = [
        percentiles[
            name
        ]
        for name in core_names

        if percentiles[
            name
        ]
        is not None
    ]

    all_values = [
        value
        for value
        in percentiles.values()

        if value is not None
    ]

    return {
        "reference_n":
            len(
                reference_records
            ),

        "metric_percentiles":
            percentiles,

        "minimum_core_compatibility":
            (
                min(
                    core_values
                )
                if len(
                    core_values
                )
                == len(
                    core_names
                )
                else None
            ),

        "core_three_inside_p95":
            (
                len(
                    core_values
                )
                == len(
                    core_names
                )

                and

                all(
                    value >= 0.05
                    for value
                    in core_values
                )
            ),

        "all_six_inside_p95":
            (
                len(
                    all_values
                )
                == len(
                    METRICS
                )

                and

                all(
                    value >= 0.05
                    for value
                    in all_values
                )
            ),
    }


# ============================================================
# Candidate path helper
# ============================================================

def candidate_map(
    sample_id,
):

    resolution = (
        resolution_by_sample[
            sample_id
        ][
            "structure_resolution"
        ]
    )

    return {
        str(
            candidate[
                "source_id"
            ]
        ):
            candidate

        for candidate in (
            resolution[
                "all_sample_structure_candidates"
            ]
        )
    }


# ============================================================
# True blind-best vs blind-runner separation
# ============================================================

def best_runner_separation(
    record,
    sample_pairs,
    best_id,
    runner_id,
):

    selected_id = str(
        record[
            "selected_source_id"
        ]
    )

    # Reuse existing selected-vs-alternative
    # separation whenever possible.

    if (
        best_id == selected_id
        or runner_id == selected_id
    ):

        other_id = (
            runner_id
            if best_id
            == selected_id
            else best_id
        )

        pair = next(
            (
                item
                for item in sample_pairs

                if str(
                    item[
                        "alternative_source_id"
                    ]
                )
                == other_id
            ),
            None,
        )

        if pair is not None:

            return {
                **pair[
                    "theoretical_separation"
                ],

                "source":
                    "existing_selected_vs_alternative",
            }

    # Otherwise both best and runner are alternatives.
    # Calculate their actual theoretical separation.

    sample_id = (
        record[
            "sample_id"
        ]
    )

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

    raw = db.xy_raw.find_one(
        {
            "filename_sample_id":
                measurement_id
        }
    )

    if raw is None:

        raise RuntimeError(
            "Missing XY_RAW"
        )

    raw_x = [
        float(value)
        for value
        in raw[
            "xrd"
        ][
            "two_theta"
        ]
    ]

    wavelength = (
        record[
            "radiation"
        ][
            "validation_wavelength"
        ]
    )

    mapping = candidate_map(
        sample_id
    )

    left_candidate = (
        mapping[
            best_id
        ]
    )

    right_candidate = (
        mapping[
            runner_id
        ]
    )

    left = (
        calculate_top_reflections(
            PROJECT_ROOT
            / left_candidate[
                "file_path"
            ],
            wavelength,
            raw_x[0],
            raw_x[-1],
        )
    )

    right = (
        calculate_top_reflections(
            PROJECT_ROOT
            / right_candidate[
                "file_path"
            ],
            wavelength,
            raw_x[0],
            raw_x[-1],
        )
    )

    result = (
        theoretical_separation(
            left,
            right,
        )
    )

    result[
        "source"
    ] = (
        "recalculated_alternative_vs_alternative"
    )

    return result


# ============================================================
# Main calibration
# ============================================================

results = []
non_evaluable_records = []
errors = []


for index, record in enumerate(
    record_results,
    start=1,
):

    sample_id = (
        record[
            "sample_id"
        ]
    )

    sample_pairs = (
        pairs_by_sample[
            sample_id
        ]
    )

    try:

        candidates = (
            rebuild_candidates(
                record,
                sample_pairs,
            )
        )

        if len(candidates) < 2:

            selected_id = str(
                record[
                    "selected_source_id"
                ]
            )

            selected_metrics = (
                record[
                    "selected_metrics"
                ]
            )

            non_evaluable_records.append(
                {
                    "sample_id":
                        sample_id,

                    "mineral":
                        record.get(
                            "mineral"
                        ),

                    "status":
                        "insufficient_evaluable_candidates",

                    "reason":
                        (
                            "Fewer than two candidates "
                            "have a valid weighted residual."
                        ),

                    "bibliography_selected_source_id":
                        selected_id,

                    "valid_candidate_count":
                        len(
                            candidates
                        ),

                    "alternative_count":
                        record[
                            "alternative_count"
                        ],

                    "evaluable_alternative_count":
                        record[
                            "evaluable_alternative_count"
                        ],

                    "selected_metrics":
                        selected_metrics,

                    "alternative_evaluations": [
                        {
                            "source_id":
                                str(
                                    pair[
                                        "alternative_source_id"
                                    ]
                                ),

                            "matched_count":
                                pair[
                                    "alternative_metrics"
                                ].get(
                                    "matched_count"
                                ),

                            "matched_fraction":
                                pair[
                                    "alternative_metrics"
                                ].get(
                                    "matched_fraction"
                                ),

                            "weighted_mean_abs_residual":
                                pair[
                                    "alternative_metrics"
                                ].get(
                                    "weighted_mean_abs_residual"
                                ),
                        }

                        for pair in sample_pairs
                    ],
                }
            )

            continue
        blind_best = (
            candidates[0]
        )

        blind_runner = (
            candidates[1]
        )

        best_id = (
            blind_best[
                "source_id"
            ]
        )

        runner_id = (
            blind_runner[
                "source_id"
            ]
        )

        selected_id = str(
            record[
                "selected_source_id"
            ]
        )

        recovered = (
            best_id
            == selected_id
        )

        gap = (
            blind_runner[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
            -
            blind_best[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
        )

        separation = (
            best_runner_separation(
                record,
                sample_pairs,
                best_id,
                runner_id,
            )
        )

        pareto = (
            diffraction_pareto_front(
                candidates
            )
        )

        cell = (
            cell_annotation(
                sample_id,
                best_id,
            )
        )

        radiation_class = (
            record[
                "radiation"
            ][
                "radiation_class"
            ]
        )

        absolute = (
            absolute_compatibility(
                sample_id,
                radiation_class,
                blind_best[
                    "metrics"
                ],
            )
        )

        results.append(
            {
                "sample_id":
                    sample_id,

                "mineral":
                    record.get(
                        "mineral"
                    ),

                "radiation_class":
                    radiation_class,

                "bibliography_selected_source_id":
                    selected_id,

                "blind_best_source_id":
                    best_id,

                "blind_runner_source_id":
                    runner_id,

                "bibliography_agreement":
                    recovered,

                "candidate_count":
                    len(
                        candidates
                    ),

                "weighted_residual_gap":
                    gap,

                "best_runner_separation":
                    separation,

                "best_runner_separation_bin":
                    separation_bin(
                        separation[
                            "median_nearest_difference"
                        ]
                    ),

                "diffraction_pareto_front":
                    pareto,

                "diffraction_pareto_front_size":
                    len(
                        pareto
                    ),

                "blind_best_is_unique_diffraction_pareto":
                    (
                        len(
                            pareto
                        )
                        == 1
                        and
                        best_id
                        in pareto
                    ),

                "cell":
                    cell,

                "absolute_compatibility":
                    absolute,

                "blind_best_metrics":
                    blind_best[
                        "metrics"
                    ],

                "all_alternatives_evaluable":
                    record[
                        "all_alternatives_evaluable"
                    ],
            }
        )

    except Exception as exc:

        errors.append(
            {
                "sample_id":
                    sample_id,

                "mineral":
                    record.get(
                        "mineral"
                    ),

                "error":
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
            }
        )

    if (
        index % 25 == 0
        or index
        == len(
            record_results
        )
    ):

        print(
            f"[{index:>3}/"
            f"{len(record_results)}] "
            f"ok={len(results)} "
            f"errors={len(errors)}"
        )


# ============================================================
# Summary helpers
# ============================================================

def agreement_summary(
    subset,
):

    n = len(
        subset
    )

    agreement = sum(
        item[
            "bibliography_agreement"
        ]
        for item in subset
    )

    return (
        n,
        agreement,
        (
            agreement / n
            if n
            else None
        ),
    )


def print_agreement_row(
    label,
    subset,
):

    n, agreement, fraction = (
        agreement_summary(
            subset
        )
    )

    print(
        f"{label:<48}"
        f"{n:>8}"
        f"{agreement:>12}"
        f"{fraction if fraction is not None else float('nan'):>14.3f}"
    )


# ============================================================
# Overall
# ============================================================

print()
print("=" * 118)
print(
    "BLIND JOINT-EVIDENCE CALIBRATION V1"
)
print("=" * 118)

print(
    "Records requested:",
    len(
        record_results
    ),
)

print(
    "Records joint-evidence evaluable:",
    len(
        results
    ),
)

print(
    "Records non-evaluable:",
    len(
        non_evaluable_records
    ),
)

print(
    "Errors:",
    len(
        errors
    ),
)

print(
    "Bibliography agreement:",
    sum(
        item[
            "bibliography_agreement"
        ]
        for item in results
    ),
    "/",
    len(
        results
    ),
    "=",
    f"{sum(item['bibliography_agreement'] for item in results) / len(results):.3f}",
)


# ============================================================
# Separation source completeness
# ============================================================

print()
print("=" * 118)
print(
    "BEST-vs-RUNNER THEORETICAL SEPARATION"
)
print("=" * 118)

source_counts = defaultdict(
    int
)

for item in results:

    source_counts[
        item[
            "best_runner_separation"
        ][
            "source"
        ]
    ] += 1


for source, count in sorted(
    source_counts.items()
):

    print(
        source,
        "=",
        count,
    )


# ============================================================
# Agreement by true best-runner separation
# ============================================================

print()
print("=" * 118)
print(
    "BIBLIOGRAPHY AGREEMENT BY TRUE "
    "BLIND-BEST-vs-RUNNER SEPARABILITY"
)
print("=" * 118)

print(
    f"{'Stratum':<48}"
    f"{'N':>8}"
    f"{'Agree':>12}"
    f"{'Fraction':>14}"
)


for stratum in [
    "le_0.02",
    "0.02_to_0.05",
    "0.05_to_0.10",
    "gt_0.10",
]:

    subset = [
        item
        for item in results

        if item[
            "best_runner_separation_bin"
        ]
        == stratum
    ]

    print_agreement_row(
        stratum,
        subset,
    )


# ============================================================
# Agreement by residual-gap quartile
# ============================================================

gaps = [
    item[
        "weighted_residual_gap"
    ]
    for item in results
]


gap_p25 = percentile(
    gaps,
    0.25,
)

gap_p50 = percentile(
    gaps,
    0.50,
)

gap_p75 = percentile(
    gaps,
    0.75,
)


print()
print("=" * 118)
print(
    "BIBLIOGRAPHY AGREEMENT BY "
    "BLIND BEST-vs-RUNNER RESIDUAL GAP"
)
print("=" * 118)

print(
    "Gap quartiles are descriptive and derived "
    "from this calibration set."
)

print(
    "P25 =",
    f"{gap_p25:.5f}",
    " P50 =",
    f"{gap_p50:.5f}",
    " P75 =",
    f"{gap_p75:.5f}",
)

print()

print(
    f"{'Gap stratum':<48}"
    f"{'N':>8}"
    f"{'Agree':>12}"
    f"{'Fraction':>14}"
)


gap_subsets = [
    (
        "<= P25",
        [
            item
            for item in results
            if item[
                "weighted_residual_gap"
            ]
            <= gap_p25
        ],
    ),
    (
        "P25-P50",
        [
            item
            for item in results
            if (
                item[
                    "weighted_residual_gap"
                ]
                > gap_p25

                and

                item[
                    "weighted_residual_gap"
                ]
                <= gap_p50
            )
        ],
    ),
    (
        "P50-P75",
        [
            item
            for item in results
            if (
                item[
                    "weighted_residual_gap"
                ]
                > gap_p50

                and

                item[
                    "weighted_residual_gap"
                ]
                <= gap_p75
            )
        ],
    ),
    (
        "> P75",
        [
            item
            for item in results
            if item[
                "weighted_residual_gap"
            ]
            > gap_p75
        ],
    ),
]


for label, subset in gap_subsets:

    print_agreement_row(
        label,
        subset,
    )


# ============================================================
# Absolute compatibility
# ============================================================

print()
print("=" * 118)
print(
    "BIBLIOGRAPHY AGREEMENT BY "
    "ABSOLUTE DIFFRACTION COMPATIBILITY"
)
print("=" * 118)

print(
    f"{'Condition':<48}"
    f"{'N':>8}"
    f"{'Agree':>12}"
    f"{'Fraction':>14}"
)


inside_core = [
    item
    for item in results

    if item[
        "absolute_compatibility"
    ][
        "core_three_inside_p95"
    ]
]


outside_core = [
    item
    for item in results

    if not item[
        "absolute_compatibility"
    ][
        "core_three_inside_p95"
    ]
]


print_agreement_row(
    "core three inside empirical P95 envelope",
    inside_core,
)

print_agreement_row(
    "core three outside empirical P95 envelope",
    outside_core,
)


# ============================================================
# Diffraction Pareto
# ============================================================

print()
print("=" * 118)
print(
    "BIBLIOGRAPHY AGREEMENT BY "
    "DIFFRACTION PARETO STATUS"
)
print("=" * 118)

print(
    f"{'Condition':<48}"
    f"{'N':>8}"
    f"{'Agree':>12}"
    f"{'Fraction':>14}"
)


unique_pareto = [
    item
    for item in results

    if item[
        "blind_best_is_unique_diffraction_pareto"
    ]
]


nonunique_pareto = [
    item
    for item in results

    if not item[
        "blind_best_is_unique_diffraction_pareto"
    ]
]


print_agreement_row(
    "blind best is unique diffraction Pareto candidate",
    unique_pareto,
)

print_agreement_row(
    "diffraction Pareto front not unique",
    nonunique_pareto,
)


# ============================================================
# Cell concordance
# ============================================================

print()
print("=" * 118)
print(
    "BIBLIOGRAPHY AGREEMENT BY "
    "CELL-DIFFRACTION CONCORDANCE"
)
print("=" * 118)

print(
    f"{'Condition':<48}"
    f"{'N':>8}"
    f"{'Agree':>12}"
    f"{'Fraction':>14}"
)


cell_exact = [
    item
    for item in results

    if item[
        "cell"
    ].get(
        "blind_best_is_minimum_length"
    )
]


cell_pareto = [
    item
    for item in results

    if item[
        "cell"
    ].get(
        "blind_best_on_cell_pareto"
    )
]


cell_not_pareto = [
    item
    for item in results

    if (
        item[
            "cell"
        ].get(
            "available"
        )
        and
        not item[
            "cell"
        ].get(
            "blind_best_on_cell_pareto"
        )
    )
]


print_agreement_row(
    "blind best = minimum-length-difference candidate",
    cell_exact,
)

print_agreement_row(
    "blind best lies on cell Pareto front",
    cell_pareto,
)

print_agreement_row(
    "blind best outside cell Pareto front",
    cell_not_pareto,
)


# ============================================================
# Cu-like joint evidence
#
# Main calibration is Cu-like because primary Mo reference
# support is extremely sparse.
#
# These are intersections of evidence features, not claims
# of correctness.
# ============================================================

cu = [
    item
    for item in results

    if item[
        "radiation_class"
    ]
    == "Cu-like"
]


joint_1 = [
    item
    for item in cu

    if item[
        "absolute_compatibility"
    ][
        "core_three_inside_p95"
    ]
]


joint_2 = [
    item
    for item in joint_1

    if item[
        "best_runner_separation"
    ][
        "median_nearest_difference"
    ]
    > 0.10
]


joint_3 = [
    item
    for item in joint_2

    if item[
        "blind_best_is_unique_diffraction_pareto"
    ]
]


joint_4 = [
    item
    for item in joint_3

    if item[
        "cell"
    ].get(
        "blind_best_on_cell_pareto"
    )
]


print()
print("=" * 118)
print(
    "CU-LIKE CUMULATIVE JOINT-EVIDENCE AUDIT"
)
print("=" * 118)

print(
    "These are descriptive evidence intersections, "
    "not automatic resolution rules."
)

print()

print(
    f"{'Evidence intersection':<62}"
    f"{'N':>8}"
    f"{'Agree':>12}"
    f"{'Fraction':>14}"
)


def print_joint_row(
    label,
    subset,
):

    n, agreement, fraction = (
        agreement_summary(
            subset
        )
    )

    print(
        f"{label:<62}"
        f"{n:>8}"
        f"{agreement:>12}"
        f"{fraction if fraction is not None else float('nan'):>14.3f}"
    )


print_joint_row(
    "Cu-like baseline",
    cu,
)

print_joint_row(
    "+ absolute core3 inside P95",
    joint_1,
)

print_joint_row(
    "+ best-runner separation > 0.10 deg",
    joint_2,
)

print_joint_row(
    "+ unique diffraction Pareto candidate",
    joint_3,
)

print_joint_row(
    "+ blind best on cell Pareto front",
    joint_4,
)


# ============================================================
# Exploratory relative-gap augmentation
#
# IMPORTANT:
# gap P50/P75 are derived and evaluated on the SAME data.
# They must NOT be treated as validated thresholds.
# ============================================================

print()
print("=" * 118)
print(
    "EXPLORATORY RELATIVE-ADVANTAGE AUGMENTATION"
)
print("=" * 118)

print(
    "IMPORTANT: P50/P75 gap cutoffs are derived "
    "from this same calibration set. "
    "These are exploratory, not validated thresholds."
)

print()


joint4_gap50 = [
    item
    for item in joint_4

    if item[
        "weighted_residual_gap"
    ]
    >= gap_p50
]


joint4_gap75 = [
    item
    for item in joint_4

    if item[
        "weighted_residual_gap"
    ]
    >= gap_p75
]


print_joint_row(
    "joint evidence + gap >= calibration P50",
    joint4_gap50,
)

print_joint_row(
    "joint evidence + gap >= calibration P75",
    joint4_gap75,
)


# ============================================================
# Strong disagreements for review
# ============================================================

disagreements = [
    item
    for item in results

    if not item[
        "bibliography_agreement"
    ]
]


disagreements.sort(
    key=lambda item: (
        -item[
            "best_runner_separation"
        ][
            "median_nearest_difference"
        ],
        -item[
            "weighted_residual_gap"
        ],
    )
)


print()
print("=" * 118)
print(
    "15 HIGH-SEPARATION BLIND DISAGREEMENTS"
)
print("=" * 118)

print(
    f"{'sample':<12}"
    f"{'mineral':<24}"
    f"{'bibliography':<14}"
    f"{'blind best':<14}"
    f"{'runner':<14}"
    f"{'sep':>12}"
    f"{'gap':>12}"
    f"{'abs':>9}"
    f"{'cell':>8}"
)


for item in disagreements[:15]:

    print(
        f"{item['sample_id']:<12}"
        f"{str(item.get('mineral'))[:22]:<24}"
        f"{item['bibliography_selected_source_id']:<14}"
        f"{item['blind_best_source_id']:<14}"
        f"{item['blind_runner_source_id']:<14}"
        f"{item['best_runner_separation']['median_nearest_difference']:>12.5f}"
        f"{item['weighted_residual_gap']:>12.5f}"
        f"{item['absolute_compatibility']['minimum_core_compatibility']:>9.3f}"
        f"{str(item['cell'].get('blind_best_on_cell_pareto')):>8}"
    )


# ============================================================
# Save
# ============================================================

output = {
    "version":
        "1.0",

    "purpose":
        (
            "Blind joint-evidence calibration using "
            "bibliography-resolved records as hidden "
            "provenance references."
        ),

    "important_note":
        (
            "Bibliography agreement is not accuracy. "
            "Evidence intersections are descriptive. "
            "Exploratory residual-gap cutoffs are "
            "derived on the same calibration data "
            "and are not independently validated."
        ),

    "inputs": {
        "contrast":
            "data/mappings/"
            "rruff_candidate_contrast_calibration_v1.json",

        "resolution":
            "data/mappings/"
            "rruff_experimental_resolution_v1.json",

        "positive_calibration":
            "data/mappings/"
            "rruff_diffraction_calibration_v1.json",
    },

    "gap_percentiles": {
        "p25":
            gap_p25,

        "p50":
            gap_p50,

        "p75":
            gap_p75,
    },

    "counts": {
        "requested":
            len(
                record_results
            ),

        "joint_evidence_evaluable":
            len(
                results
            ),

        "non_evaluable":
            len(
                non_evaluable_records
            ),

        "errors":
            len(
                errors
            ),

        "bibliography_agreement":
            sum(
                item[
                    "bibliography_agreement"
                ]
                for item in results
            ),
    },
    "records":
        results,
    "non_evaluable_records":
        non_evaluable_records,
    "errors":
        errors,
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
print("=" * 118)
print(
    "BLIND JOINT-EVIDENCE CALIBRATION V1 COMPLETE"
)
print("=" * 118)

