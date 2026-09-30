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
    / "rruff_group_diffraction_annotation_v1.json"
)


CU_WAVELENGTH = 1.541838
MO_WAVELENGTH = 0.710730

# Frozen from diffraction calibration v1.
# These are algorithm settings, not pass/fail thresholds.
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

    lower = int(position)

    upper = min(
        lower + 1,
        len(values) - 1,
    )

    fraction = (
        position - lower
    )

    return (
        values[lower]
        * (1.0 - fraction)
        +
        values[upper]
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
    output = []

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

        output.append(
            sum(
                values[start:end]
            )
            / (
                end - start
            )
        )

    return output


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
                candidate["two_theta"]
                - existing["two_theta"]
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
# Radiation provenance
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
            value - implied_median
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
        wavelength = CU_WAVELENGTH

    else:
        radiation_class = "Mo-like"
        wavelength = MO_WAVELENGTH

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
# CIF diffraction
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
                for value in transformed
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
        spacegroup = structure.spacegroup

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

    strongest = sorted(
        reflections,
        key=lambda item:
            item[
                "relative_intensity"
            ],
        reverse=True,
    )[:TOP_THEORETICAL]

    return {
        "total_reflection_count":
            len(reflections),

        "top_reflections":
            strongest,

        "space_group":
            spacegroup.xhm(),

        "cell": {
            "a":
                structure.cell.a,
            "b":
                structure.cell.b,
            "c":
                structure.cell.c,
            "alpha":
                structure.cell.alpha,
            "beta":
                structure.cell.beta,
            "gamma":
                structure.cell.gamma,
        },
    }


# ============================================================
# One-to-one matching + zero shift
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
        return median(values)

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

            if abs(residual) <= window:

                pair_candidates.append(
                    {
                        "theory_index":
                            theory_index,

                        "exp_index":
                            exp_index,

                        "residual":
                            residual,

                        "abs_residual":
                            abs(residual),

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

        theory_index = pair[
            "theory_index"
        ]

        exp_index = pair[
            "exp_index"
        ]

        if theory_index in used_theory:
            continue

        if exp_index in used_experimental:
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
    first_pass = one_to_one_match(
        theoretical,
        experimental,
        shift=0.0,
        window=INITIAL_WINDOW,
    )

    if not first_pass:
        return 0.0

    deltas = []
    weights = []

    for match in first_pass:

        theory = match[
            "theoretical"
        ]

        exp = match[
            "experimental"
        ]

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


def residual_slope(
    matches,
):
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
    zero_shift = estimate_zero_shift(
        theoretical,
        experimental,
    )

    matches = one_to_one_match(
        theoretical,
        experimental,
        shift=zero_shift,
        window=FINAL_WINDOW,
    )

    matched_count = len(
        matches
    )

    matched_fraction = (
        matched_count
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

            "mean_abs_residual":
                None,

            "weighted_mean_abs_residual":
                None,

            "max_abs_residual":
                None,

            "residual_slope":
                None,
        }

    residuals = [
        match[
            "abs_residual"
        ]
        for match in matches
    ]

    weights = [
        match[
            "theory_intensity"
        ]
        for match in matches
    ]

    if sum(weights) > 0:

        weighted = (
            sum(
                residual * weight

                for residual, weight
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
            matched_count,

        "matched_fraction":
            matched_fraction,

        "median_abs_residual":
            median(
                residuals
            ),

        "mean_abs_residual":
            mean(
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
# Candidate separability
# ============================================================

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
                    peak["two_theta"]
                    - other["two_theta"]
                )
                for other in target
            )

            distances.append(
                nearest
            )

    return {
        "mean_nearest_difference":
            mean(distances),

        "median_nearest_difference":
            median(distances),

        "max_nearest_difference":
            max(distances),
    }


def separation_bin(value):
    # Descriptive bins inherited from
    # contrast calibration v1.1.
    # NOT resolution thresholds.

    if value <= 0.02:
        return "le_0.02"

    if value <= 0.05:
        return "0.02_to_0.05"

    if value <= 0.10:
        return "0.05_to_0.10"

    return "gt_0.10"


# ============================================================
# Pareto annotation
# ============================================================

def pareto_front(
    candidate_results,
):
    """
    Candidate A dominates candidate B if:
      A has >= matched fraction
      A has <= weighted residual
    and at least one metric is strictly better.

    This is descriptive only.
    """

    valid = [
        item
        for item in candidate_results
        if item[
            "metrics"
        ][
            "weighted_mean_abs_residual"
        ]
        is not None
    ]

    front = []

    for candidate in valid:

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

        for other in valid:

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
# Load group records
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
            "resolution_level"
        )
        == "group"
    )
]


print()
print("=" * 108)
print(
    "RRUFF GROUP DIFFRACTION "
    "ANNOTATION V1"
)
print("=" * 108)

print(
    "Group records:",
    len(records),
)


db = get_database(
    database_name="rruff"
)

group_results = []
candidate_errors = []
sample_errors = []


# ============================================================
# Main group evaluation
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

    candidates = (
        resolution[
            "bibliographic_candidates"
        ]
    )

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
            for value
            in raw[
                "xrd"
            ][
                "two_theta"
            ]
        ]

        raw_y = normalize(
            raw[
                "xrd"
            ][
                "intensity"
            ]
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

        candidate_results = []

        reflection_cache = {}

        local_candidate_errors = []


        # ----------------------------------------------------
        # Evaluate every bibliography-supported CIF
        # ----------------------------------------------------

        for candidate in candidates:

            source_id = str(
                candidate[
                    "source_id"
                ]
            )

            try:

                calculated = (
                    calculate_reflections(
                        PROJECT_ROOT
                        / candidate[
                            "file_path"
                        ],
                        wavelength,
                        raw_x[0],
                        raw_x[-1],
                    )
                )

                reflections = (
                    calculated[
                        "top_reflections"
                    ]
                )

                metrics = (
                    summarize_candidate(
                        reflections,
                        experimental_peaks,
                    )
                )

                reflection_cache[
                    source_id
                ] = reflections

                candidate_results.append(
                    {
                        "source":
                            candidate.get(
                                "source"
                            ),

                        "source_id":
                            source_id,

                        "file_path":
                            candidate.get(
                                "file_path"
                            ),

                        "space_group":
                            calculated[
                                "space_group"
                            ],

                        "cell":
                            calculated[
                                "cell"
                            ],

                        "generated_reflection_count":
                            calculated[
                                "total_reflection_count"
                            ],

                        "metrics":
                            metrics,
                    }
                )

            except Exception as exc:

                error = {
                    "sample_id":
                        sample_id,

                    "mineral":
                        record.get(
                            "mineral"
                        ),

                    "candidate_source_id":
                        source_id,

                    "candidate_file_path":
                        candidate.get(
                            "file_path"
                        ),

                    "error":
                        (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                }

                candidate_errors.append(
                    error
                )

                local_candidate_errors.append(
                    error
                )


        # ----------------------------------------------------
        # Pairwise theoretical separability
        # ----------------------------------------------------

        pairwise = []

        for left_index in range(
            len(candidate_results)
        ):

            for right_index in range(
                left_index + 1,
                len(candidate_results),
            ):

                left = candidate_results[
                    left_index
                ]

                right = candidate_results[
                    right_index
                ]

                separation = (
                    theoretical_separation(
                        reflection_cache[
                            left[
                                "source_id"
                            ]
                        ],
                        reflection_cache[
                            right[
                                "source_id"
                            ]
                        ],
                    )
                )

                separation[
                    "left_source_id"
                ] = left[
                    "source_id"
                ]

                separation[
                    "right_source_id"
                ] = right[
                    "source_id"
                ]

                separation[
                    "separability_bin"
                ] = separation_bin(
                    separation[
                        "median_nearest_difference"
                    ]
                )

                pairwise.append(
                    separation
                )


        # ----------------------------------------------------
        # Diagnostic ranking only
        # ----------------------------------------------------

        valid_by_residual = [
            item
            for item in candidate_results

            if item[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
            is not None
        ]

        valid_by_residual.sort(
            key=lambda item:
                item[
                    "metrics"
                ][
                    "weighted_mean_abs_residual"
                ]
        )

        best_residual = (
            valid_by_residual[0]
            if valid_by_residual
            else None
        )

        runner_up = (
            valid_by_residual[1]
            if len(
                valid_by_residual
            ) >= 2
            else None
        )

        residual_gap = None
        best_runner_separation = None

        if (
            best_residual is not None
            and runner_up is not None
        ):

            residual_gap = (
                runner_up[
                    "metrics"
                ][
                    "weighted_mean_abs_residual"
                ]
                -
                best_residual[
                    "metrics"
                ][
                    "weighted_mean_abs_residual"
                ]
            )

            best_runner_separation = (
                theoretical_separation(
                    reflection_cache[
                        best_residual[
                            "source_id"
                        ]
                    ],
                    reflection_cache[
                        runner_up[
                            "source_id"
                        ]
                    ],
                )
            )

            best_runner_separation[
                "separability_bin"
            ] = separation_bin(
                best_runner_separation[
                    "median_nearest_difference"
                ]
            )


        # ----------------------------------------------------
        # Highest matched fraction
        # ----------------------------------------------------

        max_matched_fraction = None
        highest_matched = []

        if candidate_results:

            max_matched_fraction = max(
                item[
                    "metrics"
                ][
                    "matched_fraction"
                ]
                for item in candidate_results
            )

            highest_matched = [
                item[
                    "source_id"
                ]
                for item in candidate_results

                if item[
                    "metrics"
                ][
                    "matched_fraction"
                ]
                == max_matched_fraction
            ]


        pareto = pareto_front(
            candidate_results
        )


        # ----------------------------------------------------
        # Group-level separation summary
        # ----------------------------------------------------

        pairwise_values = [
            item[
                "median_nearest_difference"
            ]
            for item in pairwise
        ]

        if pairwise_values:

            separation_summary = {
                "minimum":
                    min(
                        pairwise_values
                    ),

                "median":
                    median(
                        pairwise_values
                    ),

                "maximum":
                    max(
                        pairwise_values
                    ),
            }

        else:

            separation_summary = None


        group_results.append(
            {
                "sample_id":
                    sample_id,

                "mineral":
                    record.get(
                        "mineral"
                    ),

                "measurement_id":
                    measurement_id,

                "bibliographic_candidate_count":
                    len(
                        candidates
                    ),

                "evaluable_candidate_count":
                    len(
                        candidate_results
                    ),

                "failed_candidate_count":
                    len(
                        local_candidate_errors
                    ),

                "all_candidates_evaluable":
                    (
                        len(
                            local_candidate_errors
                        )
                        == 0
                    ),

                "radiation":
                    radiation,

                "experimental_peak_count":
                    len(
                        experimental_peaks
                    ),

                "candidate_results":
                    candidate_results,

                "pairwise_theoretical_separation":
                    pairwise,

                "pairwise_separation_summary":
                    separation_summary,

                # Diagnostic only.
                # NOT an automatic structure call.
                "lowest_weighted_residual_candidate":
                    (
                        best_residual[
                            "source_id"
                        ]
                        if best_residual
                        else None
                    ),

                "runner_up_weighted_residual_candidate":
                    (
                        runner_up[
                            "source_id"
                        ]
                        if runner_up
                        else None
                    ),

                "weighted_residual_gap":
                    residual_gap,

                "best_vs_runner_up_separation":
                    best_runner_separation,

                "highest_matched_fraction":
                    max_matched_fraction,

                "highest_matched_fraction_candidates":
                    highest_matched,

                "lowest_residual_also_highest_matched":
                    (
                        best_residual[
                            "source_id"
                        ]
                        in highest_matched

                        if best_residual
                        else False
                    ),

                "pareto_front_candidates":
                    pareto,

                "pareto_front_size":
                    len(
                        pareto
                    ),

                "annotation_status":
                    (
                        "evaluated"
                        if len(
                            candidate_results
                        ) >= 2
                        else
                        "insufficient_evaluable_candidates"
                    ),
            }
        )

    except Exception as exc:

        sample_errors.append(
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

        evaluated_candidates = sum(
            item[
                "evaluable_candidate_count"
            ]
            for item in group_results
        )

        print(
            f"[{index:>3}/"
            f"{len(records)}] "
            f"groups_ok="
            f"{len(group_results)} "
            f"candidates="
            f"{evaluated_candidates} "
            f"candidate_errors="
            f"{len(candidate_errors)} "
            f"sample_errors="
            f"{len(sample_errors)}"
        )


# ============================================================
# Global summaries
# ============================================================

pairwise_all = [
    pair

    for group in group_results

    for pair in group[
        "pairwise_theoretical_separation"
    ]
]


pairwise_values = [
    item[
        "median_nearest_difference"
    ]
    for item in pairwise_all
]


residual_gaps = [
    item[
        "weighted_residual_gap"
    ]
    for item in group_results

    if item[
        "weighted_residual_gap"
    ]
    is not None
]


best_runner_separations = [
    item[
        "best_vs_runner_up_separation"
    ][
        "median_nearest_difference"
    ]
    for item in group_results

    if item[
        "best_vs_runner_up_separation"
    ]
    is not None
]


print()
print("=" * 108)
print(
    "GROUP ANNOTATION COMPLETENESS"
)
print("=" * 108)

print(
    "Groups requested:            ",
    len(records),
)

print(
    "Groups successful:           ",
    len(
        group_results
    ),
)

print(
    "Sample errors:               ",
    len(
        sample_errors
    ),
)

print(
    "Candidate evaluations:       ",
    sum(
        item[
            "evaluable_candidate_count"
        ]
        for item in group_results
    ),
)

print(
    "Candidate errors:            ",
    len(
        candidate_errors
    ),
)

print(
    "Pairwise CIF comparisons:    ",
    len(
        pairwise_all
    ),
)

print(
    "Groups with Pareto size = 1: ",
    sum(
        item[
            "pareto_front_size"
        ]
        == 1
        for item in group_results
    ),
)

print(
    "Groups with Pareto size > 1: ",
    sum(
        item[
            "pareto_front_size"
        ]
        > 1
        for item in group_results
    ),
)

print(
    "Lowest residual also highest matched:",
    sum(
        item[
            "lowest_residual_also_highest_matched"
        ]
        for item in group_results
    ),
)


print()
print("=" * 108)
print(
    "PAIRWISE THEORETICAL SEPARABILITY"
)
print("=" * 108)

print(
    f"{'Metric':<32}"
    f"{'P50':>12}"
    f"{'P75':>12}"
    f"{'P90':>12}"
    f"{'P95':>12}"
)

print(
    f"{'median peak separation':<32}"
    f"{percentile(pairwise_values, 0.50):>12.5f}"
    f"{percentile(pairwise_values, 0.75):>12.5f}"
    f"{percentile(pairwise_values, 0.90):>12.5f}"
    f"{percentile(pairwise_values, 0.95):>12.5f}"
)


print()
print("=" * 108)
print(
    "BEST-vs-RUNNER-UP DIAGNOSTICS"
)
print("=" * 108)

print(
    f"{'Metric':<32}"
    f"{'P50':>12}"
    f"{'P75':>12}"
    f"{'P90':>12}"
    f"{'P95':>12}"
)

print(
    f"{'weighted residual gap':<32}"
    f"{percentile(residual_gaps, 0.50):>12.5f}"
    f"{percentile(residual_gaps, 0.75):>12.5f}"
    f"{percentile(residual_gaps, 0.90):>12.5f}"
    f"{percentile(residual_gaps, 0.95):>12.5f}"
)

print(
    f"{'best-runner separation':<32}"
    f"{percentile(best_runner_separations, 0.50):>12.5f}"
    f"{percentile(best_runner_separations, 0.75):>12.5f}"
    f"{percentile(best_runner_separations, 0.90):>12.5f}"
    f"{percentile(best_runner_separations, 0.95):>12.5f}"
)


# ============================================================
# Descriptive bins
# ============================================================

print()
print("=" * 108)
print(
    "BEST-vs-RUNNER-UP BY THEORETICAL "
    "SEPARABILITY"
)
print("=" * 108)

print(
    "NOTE: descriptive bins only; "
    "no group is automatically resolved."
)

print()

print(
    f"{'Stratum':<20}"
    f"{'Groups':>10}"
    f"{'Median residual gap':>24}"
)


strata = [
    "le_0.02",
    "0.02_to_0.05",
    "0.05_to_0.10",
    "gt_0.10",
]

stratum_summary = {}


for stratum in strata:

    subset = [
        item
        for item in group_results

        if (
            item[
                "best_vs_runner_up_separation"
            ]
            is not None

            and

            item[
                "best_vs_runner_up_separation"
            ][
                "separability_bin"
            ]
            == stratum
        )
    ]

    gaps = [
        item[
            "weighted_residual_gap"
        ]
        for item in subset

        if item[
            "weighted_residual_gap"
        ]
        is not None
    ]

    median_gap = (
        median(gaps)
        if gaps
        else None
    )

    stratum_summary[
        stratum
    ] = {
        "group_count":
            len(subset),

        "median_weighted_residual_gap":
            median_gap,
    }

    print(
        f"{stratum:<20}"
        f"{len(subset):>10d}"
        f"{median_gap if median_gap is not None else float('nan'):>24.5f}"
    )


# ============================================================
# Largest and smallest diagnostic gaps
# ============================================================

rankable = [
    item
    for item in group_results
    if item[
        "weighted_residual_gap"
    ]
    is not None
]


largest_gap = sorted(
    rankable,
    key=lambda item:
        item[
            "weighted_residual_gap"
        ],
    reverse=True,
)


smallest_gap = sorted(
    rankable,
    key=lambda item:
        item[
            "weighted_residual_gap"
        ],
)


def print_examples(
    title,
    items,
):
    print()
    print("=" * 108)
    print(title)
    print("=" * 108)

    print(
        f"{'sample':<12}"
        f"{'mineral':<24}"
        f"{'best':<12}"
        f"{'runner':<12}"
        f"{'gap':>12}"
        f"{'separation':>14}"
        f"{'pareto':>9}"
    )

    for item in items[:10]:

        separation = (
            item[
                "best_vs_runner_up_separation"
            ][
                "median_nearest_difference"
            ]
            if item[
                "best_vs_runner_up_separation"
            ]
            else float("nan")
        )

        print(
            f"{item['sample_id']:<12}"
            f"{str(item.get('mineral'))[:22]:<24}"
            f"{str(item['lowest_weighted_residual_candidate']):<12}"
            f"{str(item['runner_up_weighted_residual_candidate']):<12}"
            f"{item['weighted_residual_gap']:>12.5f}"
            f"{separation:>14.5f}"
            f"{item['pareto_front_size']:>9d}"
        )


print_examples(
    "10 LARGEST DIAGNOSTIC RESIDUAL GAPS",
    largest_gap,
)

print_examples(
    "10 SMALLEST DIAGNOSTIC RESIDUAL GAPS",
    smallest_gap,
)


# ============================================================
# Save
# ============================================================

output = {
    "version":
        "1.0",

    "purpose":
        (
            "Diffraction evidence annotation "
            "for bibliography-supported "
            "RRUFF candidate groups."
        ),

    "important_note":
        (
            "This file does not automatically "
            "resolve candidate groups. "
            "Lowest residual, Pareto front, "
            "and separability strata are "
            "descriptive evidence only."
        ),

    "calibration_basis": {
        "diffraction_calibration":
            "data/mappings/"
            "rruff_diffraction_calibration_v1.json",

        "contrast_calibration":
            "data/mappings/"
            "rruff_candidate_contrast_calibration_v1.json",
    },

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
        "groups_requested":
            len(records),

        "groups_successful":
            len(
                group_results
            ),

        "sample_errors":
            len(
                sample_errors
            ),

        "candidate_evaluations":
            sum(
                item[
                    "evaluable_candidate_count"
                ]
                for item in group_results
            ),

        "candidate_errors":
            len(
                candidate_errors
            ),

        "pairwise_comparisons":
            len(
                pairwise_all
            ),
    },

    "best_runner_strata":
        stratum_summary,

    "groups":
        group_results,

    "candidate_errors":
        candidate_errors,

    "sample_errors":
        sample_errors,
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
    "GROUP DIFFRACTION ANNOTATION V1 COMPLETE"
)
print("=" * 108)

