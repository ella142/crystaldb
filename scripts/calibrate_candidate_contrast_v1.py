import json
from math import asin, cos, degrees, radians, sin
from pathlib import Path
from statistics import mean, median

import gemmi

from crystaldb.mongo import get_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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
    / "rruff_candidate_contrast_calibration_v1.json"
)


CU_WAVELENGTH = 1.541838
MO_WAVELENGTH = 0.710730

TOP_THEORETICAL = 20

INITIAL_WINDOW = 0.35
FINAL_WINDOW = 0.15

SMOOTH_RADIUS = 2
MIN_EXPERIMENTAL_INTENSITY = 1.0
MIN_PEAK_SEPARATION = 0.12
MAX_EXPERIMENTAL_PEAKS = 200


# ============================================================
# Generic helpers
# ============================================================

def percentile(values, q):
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

    low = int(position)

    high = min(
        low + 1,
        len(values) - 1,
    )

    fraction = (
        position - low
    )

    return (
        values[low]
        * (1.0 - fraction)
        +
        values[high]
        * fraction
    )


def normalize(values):
    values = [
        float(value)
        for value in values
    ]

    minimum = min(values)

    shifted = [
        value - minimum
        for value in values
    ]

    maximum = max(shifted)

    if maximum <= 0:

        return [
            0.0
            for _ in shifted
        ]

    return [
        value
        / maximum
        * 100.0
        for value in shifted
    ]


def smooth(values, radius):
    result = []

    for index in range(
        len(values)
    ):

        start = max(
            0,
            index - radius,
        )

        end = min(
            len(values),
            index + radius + 1,
        )

        result.append(
            sum(
                values[start:end]
            )
            / (
                end - start
            )
        )

    return result


# ============================================================
# Experimental peak detection
# ============================================================

def detect_experimental_peaks(
    x,
    y,
):
    smoothed = smooth(
        y,
        SMOOTH_RADIUS,
    )

    candidates = []

    for index in range(
        1,
        len(smoothed) - 1,
    ):

        value = smoothed[index]

        if (
            value
            < MIN_EXPERIMENTAL_INTENSITY
        ):
            continue

        if (
            value >= smoothed[index - 1]
            and
            value > smoothed[index + 1]
        ):

            candidates.append(
                {
                    "two_theta":
                        x[index],

                    "intensity":
                        value,
                }
            )

    candidates.sort(
        key=lambda item:
            item["intensity"],
        reverse=True,
    )

    retained = []

    for candidate in candidates:

        if any(
            abs(
                candidate[
                    "two_theta"
                ]
                - existing[
                    "two_theta"
                ]
            )
            < MIN_PEAK_SEPARATION

            for existing in retained
        ):
            continue

        retained.append(
            candidate
        )

        if (
            len(retained)
            >= MAX_EXPERIMENTAL_PEAKS
        ):
            break

    retained.sort(
        key=lambda item:
            item["two_theta"]
    )

    return retained


# ============================================================
# Radiation
# ============================================================

def implied_wavelength(
    d_spacing,
    two_theta,
):
    theta = radians(
        float(two_theta)
        / 2.0
    )

    return (
        2.0
        * float(d_spacing)
        * sin(theta)
    )


def derive_validation_wavelength(
    dif,
):
    values = []

    for peak in (
        dif.get(
            "diffraction",
            {},
        ).get(
            "peaks",
            [],
        )
        or []
    ):

        d_spacing = peak.get(
            "d_spacing"
        )

        two_theta = peak.get(
            "two_theta"
        )

        if (
            d_spacing is None
            or two_theta is None
        ):
            continue

        values.append(
            implied_wavelength(
                d_spacing,
                two_theta,
            )
        )

    if len(values) < 3:

        raise RuntimeError(
            "Insufficient DIF peak geometry."
        )

    implied_median = median(
        values
    )

    implied_mad = median(
        abs(
            value
            - implied_median
        )
        for value in values
    )

    if (
        abs(
            implied_median
            - CU_WAVELENGTH
        )
        <
        abs(
            implied_median
            - MO_WAVELENGTH
        )
    ):

        radiation_class = "Cu-like"

        wavelength = (
            CU_WAVELENGTH
        )

    else:

        radiation_class = "Mo-like"

        wavelength = (
            MO_WAVELENGTH
        )

    return {
        "radiation_class":
            radiation_class,

        "validation_wavelength":
            wavelength,

        "implied_wavelength_median":
            implied_median,

        "implied_wavelength_mad":
            implied_mad,
    }


# ============================================================
# CIF -> theoretical reflections
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


def calculate_reflections(
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
                    raw_max
                    / 2.0
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
                    raw_min
                    / 2.0
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
            for value in hkl_array
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
                "hkl":
                    hkl,

                "two_theta":
                    two_theta,

                "intensity":
                    intensity,
            }
        )

    if not reflections:

        raise RuntimeError(
            "No calculated reflections."
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


# ============================================================
# One-to-one matching
# ============================================================

def weighted_median(
    values,
    weights,
):
    pairs = sorted(
        zip(
            values,
            weights,
        ),
        key=lambda item:
            item[0],
    )

    total = sum(weights)

    if total <= 0:

        return median(
            values
        )

    cumulative = 0.0

    for value, weight in pairs:

        cumulative += weight

        if cumulative >= total / 2.0:

            return value

    return pairs[-1][0]


def one_to_one_match(
    theoretical,
    experimental,
    shift,
    window,
):
    pair_candidates = []

    for theory_index, theory in enumerate(
        theoretical
    ):

        corrected = (
            theory["two_theta"]
            + shift
        )

        for exp_index, exp in enumerate(
            experimental
        ):

            residual = (
                exp["two_theta"]
                - corrected
            )

            if (
                abs(residual)
                <= window
            ):

                pair_candidates.append(
                    {
                        "theory_index":
                            theory_index,

                        "exp_index":
                            exp_index,

                        "residual":
                            residual,

                        "abs_residual":
                            abs(
                                residual
                            ),

                        "theory_intensity":
                            theory[
                                "relative_intensity"
                            ],

                        "experimental_intensity":
                            exp[
                                "intensity"
                            ],
                    }
                )

    pair_candidates.sort(
        key=lambda item: (
            item[
                "abs_residual"
            ],
            -item[
                "theory_intensity"
            ],
            -item[
                "experimental_intensity"
            ],
        )
    )

    used_theory = set()
    used_experimental = set()

    matches = []

    for pair in pair_candidates:

        theory_index = (
            pair[
                "theory_index"
            ]
        )

        exp_index = (
            pair[
                "exp_index"
            ]
        )

        if (
            theory_index
            in used_theory
        ):
            continue

        if (
            exp_index
            in used_experimental
        ):
            continue

        used_theory.add(
            theory_index
        )

        used_experimental.add(
            exp_index
        )

        matches.append(
            {
                **pair,

                "theoretical":
                    theoretical[
                        theory_index
                    ],

                "experimental":
                    experimental[
                        exp_index
                    ],
            }
        )

    return matches


def estimate_zero_shift(
    theoretical,
    experimental,
):
    first_pass = (
        one_to_one_match(
            theoretical,
            experimental,
            shift=0.0,
            window=INITIAL_WINDOW,
        )
    )

    if not first_pass:
        return 0.0

    deltas = []

    weights = []

    for match in first_pass:

        theory = (
            match[
                "theoretical"
            ]
        )

        exp = (
            match[
                "experimental"
            ]
        )

        deltas.append(
            exp["two_theta"]
            - theory["two_theta"]
        )

        weights.append(
            theory[
                "relative_intensity"
            ]
        )

    return weighted_median(
        deltas,
        weights,
    )


def residual_slope(matches):
    if len(matches) < 2:
        return None

    x = [
        match[
            "theoretical"
        ][
            "two_theta"
        ]
        for match in matches
    ]

    y = [
        match[
            "residual"
        ]
        for match in matches
    ]

    mean_x = mean(x)
    mean_y = mean(y)

    denominator = sum(
        (
            value - mean_x
        ) ** 2
        for value in x
    )

    if denominator == 0:
        return None

    numerator = sum(
        (
            x_value - mean_x
        )
        * (
            y_value - mean_y
        )
        for x_value, y_value
        in zip(
            x,
            y,
        )
    )

    return (
        numerator
        / denominator
    )


def summarize_candidate(
    theoretical,
    experimental,
):
    zero_shift = (
        estimate_zero_shift(
            theoretical,
            experimental,
        )
    )

    matches = (
        one_to_one_match(
            theoretical,
            experimental,
            shift=zero_shift,
            window=FINAL_WINDOW,
        )
    )

    count = len(
        matches
    )

    fraction = (
        count
        / len(theoretical)
        if theoretical
        else 0.0
    )

    if not matches:

        return {
            "zero_shift":
                zero_shift,

            "matched_count":
                0,

            "matched_fraction":
                0.0,

            "median_abs_residual":
                None,

            "weighted_mean_abs_residual":
                None,

            "max_abs_residual":
                None,

            "residual_slope":
                None,
        }

    residuals = [
        item[
            "abs_residual"
        ]
        for item in matches
    ]

    weights = [
        item[
            "theory_intensity"
        ]
        for item in matches
    ]

    if sum(weights) > 0:

        weighted = (
            sum(
                value * weight
                for value, weight
                in zip(
                    residuals,
                    weights,
                )
            )
            / sum(weights)
        )

    else:

        weighted = mean(
            residuals
        )

    return {
        "zero_shift":
            zero_shift,

        "matched_count":
            count,

        "matched_fraction":
            fraction,

        "median_abs_residual":
            median(
                residuals
            ),

        "weighted_mean_abs_residual":
            weighted,

        "max_abs_residual":
            max(
                residuals
            ),

        "residual_slope":
            residual_slope(
                matches
            ),
    }


# ============================================================
# Candidate-vs-candidate theoretical separability
# ============================================================

def theoretical_separation(
    selected,
    alternative,
):
    distances = []

    for source, target in [
        (
            selected,
            alternative,
        ),
        (
            alternative,
            selected,
        ),
    ]:

        for peak in source:

            nearest = min(
                abs(
                    peak["two_theta"]
                    - other["two_theta"]
                )
                for other in target
            )

            distances.append(
                nearest
            )

    return {
        "comparison_count":
            len(distances),

        "mean_nearest_difference":
            mean(distances),

        "median_nearest_difference":
            median(distances),

        "max_nearest_difference":
            max(distances),

        "within_0_02":
            sum(
                value <= 0.02
                for value in distances
            ),

        "within_0_05":
            sum(
                value <= 0.05
                for value in distances
            ),

        "within_0_10":
            sum(
                value <= 0.10
                for value in distances
            ),
    }


def separability_bin(
    median_difference,
):
    # Descriptive strata only.
    # NOT decision thresholds.

    if median_difference <= 0.02:
        return "le_0.02"

    if median_difference <= 0.05:
        return "0.02_to_0.05"

    if median_difference <= 0.10:
        return "0.05_to_0.10"

    return "gt_0.10"


# ============================================================
# Load records
# ============================================================

data = json.loads(
    RESOLUTION_FILE.read_text(
        encoding="utf-8"
    )
)

records = [
    record
    for record in data["records"]

    if (
        record.get(
            "structure_resolution",
            {},
        ).get(
            "resolution_status"
        )
        == "unique_bibliographic_match"
    )
]


print()
print("=" * 108)
print(
    "RRUFF CANDIDATE CONTRAST "
    "CALIBRATION V1"
)
print("=" * 108)

print(
    "Unique bibliographic records:",
    len(records),
)


db = get_database(
    database_name="rruff"
)


pair_results = []

record_results = []

errors = []

candidate_errors = []

# ============================================================
# Main analysis
# ============================================================

for index, record in enumerate(
    records,
    start=1,
):

    sample_id = (
        record[
            "sample_id"
        ]
    )

    resolution = (
        record[
            "structure_resolution"
        ]
    )

    selected = (
        resolution[
            "selected_candidate"
        ]
    )

    all_candidates = (
        resolution[
            "all_sample_structure_candidates"
        ]
    )

    alternatives = [
        candidate
        for candidate
        in all_candidates

        if str(
            candidate.get(
                "source_id"
            )
        )
        != str(
            selected.get(
                "source_id"
            )
        )
    ]

    try:

        measurement_id = (
            record[
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

        dif = db.dif.find_one(
            {
                "sample_id":
                    sample_id
            }
        )

        if raw is None:
            raise RuntimeError(
                "Missing XY_RAW"
            )

        if dif is None:
            raise RuntimeError(
                "Missing DIF"
            )

        raw_x = [
            float(value)
            for value in
            raw["xrd"]["two_theta"]
        ]

        raw_y = normalize(
            raw["xrd"]["intensity"]
        )

        experimental_peaks = (
            detect_experimental_peaks(
                raw_x,
                raw_y,
            )
        )

        if not experimental_peaks:

            raise RuntimeError(
                "No experimental peaks detected"
            )

        radiation = (
            derive_validation_wavelength(
                dif
            )
        )

        wavelength = (
            radiation[
                "validation_wavelength"
            ]
        )

        selected_reflections = (
            calculate_reflections(
                PROJECT_ROOT
                / selected[
                    "file_path"
                ],
                wavelength,
                raw_x[0],
                raw_x[-1],
            )
        )

        selected_metrics = (
            summarize_candidate(
                selected_reflections,
                experimental_peaks,
            )
        )

        sample_pairs = []

        sample_candidate_errors = []


        for alternative in alternatives:

            try:

                alternative_reflections = (
                    calculate_reflections(
                        PROJECT_ROOT
                        / alternative[
                            "file_path"
                        ],
                        wavelength,
                        raw_x[0],
                        raw_x[-1],
                    )
                )

                alternative_metrics = (
                    summarize_candidate(
                        alternative_reflections,
                        experimental_peaks,
                    )
                )

                separation = (
                    theoretical_separation(
                        selected_reflections,
                        alternative_reflections,
                    )
                )

                selected_weighted = (
                    selected_metrics[
                        "weighted_mean_abs_residual"
                    ]
                )

                alternative_weighted = (
                    alternative_metrics[
                        "weighted_mean_abs_residual"
                    ]
                )

                selected_median = (
                    selected_metrics[
                        "median_abs_residual"
                    ]
                )

                alternative_median = (
                    alternative_metrics[
                        "median_abs_residual"
                    ]
                )

                pair = {
                    "sample_id":
                        sample_id,

                    "mineral":
                        record.get(
                            "mineral"
                        ),

                    "measurement_id":
                        measurement_id,

                    "selected_source_id":
                        selected[
                            "source_id"
                        ],

                    "alternative_source_id":
                        alternative[
                            "source_id"
                        ],

                    "radiation_class":
                        radiation[
                            "radiation_class"
                        ],

                    "selected_metrics":
                        selected_metrics,

                    "alternative_metrics":
                        alternative_metrics,

                    "selected_advantage": {

                        "weighted_residual":
                            (
                                alternative_weighted
                                - selected_weighted
                            )
                            if (
                                alternative_weighted
                                is not None
                                and selected_weighted
                                is not None
                            )
                            else None,

                        "median_residual":
                            (
                                alternative_median
                                - selected_median
                            )
                            if (
                                alternative_median
                                is not None
                                and selected_median
                                is not None
                            )
                            else None,

                        "matched_fraction":
                            (
                                selected_metrics[
                                    "matched_fraction"
                                ]
                                - alternative_metrics[
                                    "matched_fraction"
                                ]
                            ),
                    },

                    "theoretical_separation":
                        separation,

                    "separability_bin":
                        separability_bin(
                            separation[
                                "median_nearest_difference"
                            ]
                        ),
                }

                sample_pairs.append(
                    pair
                )

            except Exception as exc:

                candidate_error = {
                    "sample_id":
                        sample_id,

                    "mineral":
                        record.get(
                            "mineral"
                        ),

                    "selected_source_id":
                        selected.get(
                            "source_id"
                        ),

                    "candidate_source_id":
                        alternative.get(
                            "source_id"
                        ),

                    "candidate_file_path":
                        alternative.get(
                            "file_path"
                        ),

                    "evaluation_status":
                        "numerical_error",

                    "error":
                        (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                }

                sample_candidate_errors.append(
                    candidate_error
                )

                candidate_errors.append(
                    candidate_error
                )

                continue


        # Commit pair-level results only after
        # this sample has finished evaluating.
        pair_results.extend(
            sample_pairs
        )


        valid_weighted_pairs = [
            pair
            for pair in sample_pairs
            if pair[
                "selected_advantage"
            ][
                "weighted_residual"
            ]
            is not None
        ]

        better_count = sum(
            pair[
                "selected_advantage"
            ][
                "weighted_residual"
            ]
            > 0

            for pair in valid_weighted_pairs
        )

        worse_count = sum(
            pair[
                "selected_advantage"
            ][
                "weighted_residual"
            ]
            < 0

            for pair in valid_weighted_pairs
        )

        equal_count = (
            len(
                valid_weighted_pairs
            )
            - better_count
            - worse_count
        )

        candidate_weighted = []

        if (
            selected_metrics[
                "weighted_mean_abs_residual"
            ]
            is not None
        ):

            candidate_weighted.append(
                (
                    str(
                        selected[
                            "source_id"
                        ]
                    ),
                    selected_metrics[
                        "weighted_mean_abs_residual"
                    ],
                )
            )

        for pair in sample_pairs:

            value = pair[
                "alternative_metrics"
            ][
                "weighted_mean_abs_residual"
            ]

            if value is not None:

                candidate_weighted.append(
                    (
                        str(
                            pair[
                                "alternative_source_id"
                            ]
                        ),
                        value,
                    )
                )

        candidate_weighted.sort(
            key=lambda item:
                item[1]
        )

        selected_rank = None

        for rank, (
            source_id,
            value,
        ) in enumerate(
            candidate_weighted,
            start=1,
        ):

            if (
                source_id
                == str(
                    selected[
                        "source_id"
                    ]
                )
            ):

                selected_rank = rank
                break


        record_results.append(
            {
                "sample_id":
                    sample_id,

                "mineral":
                    record.get(
                        "mineral"
                    ),

                "selected_source_id":
                    selected[
                        "source_id"
                    ],

                "alternative_count":
                    len(
                        alternatives
                    ),

                "evaluable_alternative_count":
                    len(
                        valid_weighted_pairs
                    ),

                "failed_alternative_count":
                    len(
                        sample_candidate_errors
                    ),

                "all_alternatives_evaluable":
                    (
                        len(
                            sample_candidate_errors
                        )
                        == 0
                    ),

                "selected_metrics":
                    selected_metrics,

                "selected_rank_by_weighted_residual":
                    selected_rank,

                "selected_better_than_alternatives":
                    better_count,

                "selected_worse_than_alternatives":
                    worse_count,

                "selected_equal_to_alternatives":
                    equal_count,

                "selected_better_fraction":
                    (
                        better_count
                        / len(
                            valid_weighted_pairs
                        )
                    )
                    if valid_weighted_pairs
                    else None,

                "radiation":
                    radiation,
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
        index % 10 == 0
        or index == len(records)
    ):

        print(
            f"[{index:>3}/"
            f"{len(records)}] "
            f"records_ok="
            f"{len(record_results)} "
            f"pairs="
            f"{len(pair_results)} "
            f"errors="
            f"{len(errors)}"
        )


# ============================================================
# Summaries
# ============================================================

print()
print("=" * 108)
print(
    "CONTRAST CALIBRATION COMPLETENESS"
)
print("=" * 108)

print(
    "Records requested:     ",
    len(records),
)

print(
    "Records successful:    ",
    len(
        record_results
    ),
)

print(
    "Pair comparisons:      ",
    len(
        pair_results
    ),
)

print(
    "Errors:                ",
    len(errors),
)

print(
    "Candidate errors:      ",
    len(
        candidate_errors
    ),
)


# ------------------------------------------------------------
# Theoretical separability
# ------------------------------------------------------------

separation_values = [
    pair[
        "theoretical_separation"
    ][
        "median_nearest_difference"
    ]
    for pair in pair_results
]


print()
print("=" * 108)
print(
    "SELECTED-vs-ALTERNATIVE "
    "THEORETICAL SEPARATION"
)
print("=" * 108)

print(
    f"{'Metric':<28}"
    f"{'P50':>12}"
    f"{'P75':>12}"
    f"{'P90':>12}"
    f"{'P95':>12}"
)

print(
    f"{'median peak separation':<28}"
    f"{percentile(separation_values, 0.50):>12.5f}"
    f"{percentile(separation_values, 0.75):>12.5f}"
    f"{percentile(separation_values, 0.90):>12.5f}"
    f"{percentile(separation_values, 0.95):>12.5f}"
)


# ------------------------------------------------------------
# Descriptive separability strata
# ------------------------------------------------------------

print()
print("=" * 108)
print(
    "DIFFRACTION CONTRAST BY "
    "THEORETICAL SEPARABILITY STRATUM"
)
print("=" * 108)

print(
    "NOTE: these bins are descriptive only, "
    "not decision thresholds."
)

print()

print(
    f"{'Stratum':<20}"
    f"{'Pairs':>10}"
    f"{'Selected better':>18}"
    f"{'Fraction':>12}"
    f"{'Median advantage':>20}"
)


strata = [
    "le_0.02",
    "0.02_to_0.05",
    "0.05_to_0.10",
    "gt_0.10",
]


stratum_summaries = {}


for stratum in strata:

    subset = [
        pair
        for pair in pair_results
        if pair[
            "separability_bin"
        ]
        == stratum
    ]

    advantages = [
        pair[
            "selected_advantage"
        ][
            "weighted_residual"
        ]

        for pair in subset

        if pair[
            "selected_advantage"
        ][
            "weighted_residual"
        ]
        is not None
    ]

    selected_better = sum(
        value > 0
        for value in advantages
    )

    fraction = (
        selected_better
        / len(advantages)
        if advantages
        else 0.0
    )

    median_advantage = (
        median(advantages)
        if advantages
        else None
    )

    stratum_summaries[
        stratum
    ] = {
        "pair_count":
            len(subset),

        "valid_advantage_count":
            len(advantages),

        "selected_better_count":
            selected_better,

        "selected_better_fraction":
            fraction,

        "median_selected_advantage_weighted_residual":
            median_advantage,
    }

    print(
        f"{stratum:<20}"
        f"{len(subset):>10d}"
        f"{selected_better:>18d}"
        f"{fraction:>12.3f}"
        f"{median_advantage if median_advantage is not None else float('nan'):>20.5f}"
    )


# ------------------------------------------------------------
# Record-balanced summary
# ------------------------------------------------------------

better_fractions = [
    record[
        "selected_better_fraction"
    ]
    for record in record_results
    if record[
        "selected_better_fraction"
    ]
    is not None
]


selected_rank_one = sum(
    record[
        "selected_rank_by_weighted_residual"
    ]
    == 1

    for record in record_results
)


selected_better_all = sum(
    (
        record[
            "all_alternatives_evaluable"
        ]
        and
        record[
            "selected_better_than_alternatives"
        ]
        == record[
            "alternative_count"
        ]
        and
        record[
            "alternative_count"
        ]
        > 0
    )

    for record in record_results
)


selected_better_majority = sum(
    (
        record[
            "selected_better_fraction"
        ]
        is not None
        and
        record[
            "selected_better_fraction"
        ]
        > 0.5
    )

    for record in record_results
)


print()
print("=" * 108)
print(
    "RECORD-BALANCED SUMMARY"
)
print("=" * 108)

print(
    "Records analysed:                         ",
    len(
        record_results
    ),
)

print(
    "Selected CIF lowest weighted residual:     ",
    selected_rank_one,
)

print(
    "Selected better than every alternative:    ",
    selected_better_all,
)

print(
    "Selected better than majority alternatives:",
    selected_better_majority,
)

print(
    "Median per-record selected-better fraction:",
    f"{median(better_fractions):.3f}",
)


# ------------------------------------------------------------
# Useful review cases
# ------------------------------------------------------------

review_records = sorted(
    record_results,
    key=lambda item:
        (
            item[
                "selected_better_fraction"
            ]
            if item[
                "selected_better_fraction"
            ]
            is not None
            else 1.0
        )
)


print()
print("=" * 108)
print(
    "FIRST 15 RECORDS FOR CONTRAST REVIEW"
)
print("=" * 108)

print(
    f"{'sample':<12}"
    f"{'mineral':<24}"
    f"{'selected':<12}"
    f"{'alts':>6}"
    f"{'rank':>7}"
    f"{'better fraction':>18}"
)


for item in review_records[:15]:

    print(
        f"{item['sample_id']:<12}"
        f"{str(item.get('mineral'))[:22]:<24}"
        f"{str(item['selected_source_id']):<12}"
        f"{item['alternative_count']:>6d}"
        f"{item['selected_rank_by_weighted_residual']:>7}"
        f"{item['selected_better_fraction']:>18.3f}"
    )


# ============================================================
# Save
# ============================================================

output = {
    "version":
        "1.0",

    "purpose":
        (
            "Contrast calibration comparing "
            "bibliography-selected CIF records "
            "against crystallographically plausible "
            "alternative CIF candidates using "
            "experimental diffraction."
        ),

    "important_note":
        (
            "Separability bins are descriptive. "
            "No automatic diffraction winner or "
            "scientific pass/fail threshold is "
            "defined in v1."
        ),

    "settings": {
        "top_theoretical":
            TOP_THEORETICAL,

        "initial_window_deg":
            INITIAL_WINDOW,

        "final_window_deg":
            FINAL_WINDOW,

        "smooth_radius":
            SMOOTH_RADIUS,

        "min_experimental_intensity":
            MIN_EXPERIMENTAL_INTENSITY,

        "min_peak_separation_deg":
            MIN_PEAK_SEPARATION,

        "max_experimental_peaks":
            MAX_EXPERIMENTAL_PEAKS,
    },

    "counts": {
        "records_requested":
            len(records),

        "records_successful":
            len(
                record_results
            ),

        "pair_comparisons":
            len(
                pair_results
            ),
        "candidate_errors":
            len(
                candidate_errors
            ),
        "errors":
            len(errors),

        "selected_rank_one":
            selected_rank_one,

        "selected_better_all_alternatives":
            selected_better_all,

        "selected_better_majority":
            selected_better_majority,
    },

    "separation_percentiles": {
        "p50":
            percentile(
                separation_values,
                0.50,
            ),

        "p75":
            percentile(
                separation_values,
                0.75,
            ),

        "p90":
            percentile(
                separation_values,
                0.90,
            ),

        "p95":
            percentile(
                separation_values,
                0.95,
            ),
    },

    "separability_strata":
        stratum_summaries,

    "record_results":
        record_results,

    "pair_results":
        pair_results,

    "errors":
        errors,

    "candidate_errors":
        candidate_errors,
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
print("=" * 108)
print(
    "CONTRAST CALIBRATION V1 COMPLETE"
)
print("=" * 108)

