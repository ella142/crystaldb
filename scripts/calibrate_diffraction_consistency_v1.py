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
    / "rruff_diffraction_calibration_v1.json"
)


CU_WAVELENGTH = 1.541838
MO_WAVELENGTH = 0.710730

# ------------------------------------------------------------
# Frozen pilot settings for calibration v1.
#
# IMPORTANT:
# These are algorithm settings, NOT scientific pass/fail
# thresholds.
# ------------------------------------------------------------

TOP_THEORETICAL = 20

INITIAL_WINDOW = 0.35
FINAL_WINDOW = 0.15

SMOOTH_RADIUS = 2
MIN_EXPERIMENTAL_INTENSITY = 1.0
MIN_PEAK_SEPARATION = 0.12
MAX_EXPERIMENTAL_PEAKS = 200


# ============================================================
# General helpers
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

    if not values:
        return []

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


def smooth(
    values,
    radius,
):
    output = []

    n = len(values)

    for index in range(n):

        start = max(
            0,
            index - radius,
        )

        end = min(
            n,
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
            value
            >= smoothed[index - 1]
            and
            value
            > smoothed[index + 1]
        ):

            candidates.append(
                {
                    "two_theta":
                        x[index],

                    "intensity":
                        value,
                }
            )

    # Strongest peaks are retained first.
    # Nearby duplicate maxima are suppressed.
    candidates.sort(
        key=lambda item:
            item["intensity"],
        reverse=True,
    )

    retained = []

    for candidate in candidates:

        too_close = any(
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
        )

        if too_close:
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
    peaks = (
        dif.get(
            "diffraction",
            {},
        ).get(
            "peaks",
            [],
        )
        or []
    )

    values = []

    for peak in peaks:

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

        value = implied_wavelength(
            d_spacing,
            two_theta,
        )

        if value > 0:
            values.append(
                value
            )

    if len(values) < 3:
        raise RuntimeError(
            "Insufficient DIF peak geometry "
            "for wavelength derivation."
        )

    implied_median = median(
        values
    )

    cu_distance = abs(
        implied_median
        - CU_WAVELENGTH
    )

    mo_distance = abs(
        implied_median
        - MO_WAVELENGTH
    )

    if cu_distance < mo_distance:

        radiation_class = (
            "Cu-like"
        )

        wavelength = (
            CU_WAVELENGTH
        )

    else:

        radiation_class = (
            "Mo-like"
        )

        wavelength = (
            MO_WAVELENGTH
        )

    deviations = [
        abs(
            value
            - implied_median
        )
        for value in values
    ]

    implied_mad = median(
        deviations
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

        "implied_peak_count":
            len(values),
    }


# ============================================================
# CIF -> theoretical diffraction
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
        + cos(two_theta_rad) ** 2
    ) / denominator


def calculate_reflections(
    cif_path,
    wavelength,
    raw_min,
    raw_max,
):
    document = (
        gemmi.cif.read_file(
            str(cif_path)
        )
    )

    block = (
        document.sole_block()
    )

    structure = (
        gemmi.make_small_structure_from_block(
            block
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
            "Unable to determine CIF space group."
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

        structure_factor = (
            sf_calculator
            .calculate_sf_from_small_structure(
                structure,
                hkl,
            )
        )

        intensity = (
            abs(
                structure_factor
            ) ** 2
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
            "No theoretical reflections "
            "generated in experimental range."
        )

    maximum = max(
        item["intensity"]
        for item in reflections
    )

    if maximum <= 0:

        raise RuntimeError(
            "All calculated reflection "
            "intensities are zero."
        )

    for item in reflections:

        item[
            "relative_intensity"
        ] = (
            item["intensity"]
            / maximum
            * 100.0
        )

    return {
        "structure":
            structure,

        "spacegroup":
            spacegroup,

        "reflections":
            reflections,
    }


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

    total = sum(
        weights
    )

    if total <= 0:
        return median(
            values
        )

    cumulative = 0.0

    for value, weight in pairs:

        cumulative += weight

        if (
            cumulative
            >= total / 2.0
        ):
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

    # Smallest angular residual first.
    # Neither side can be reused.
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

        theoretical_peak = (
            match[
                "theoretical"
            ]
        )

        experimental_peak = (
            match[
                "experimental"
            ]
        )

        deltas.append(
            experimental_peak[
                "two_theta"
            ]
            - theoretical_peak[
                "two_theta"
            ]
        )

        weights.append(
            theoretical_peak[
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

    theoretical_count = len(
        theoretical
    )

    matched_count = len(
        matches
    )

    matched_fraction = (
        matched_count
        / theoretical_count
        if theoretical_count
        else 0.0
    )

    if not matches:

        return {
            "zero_shift":
                zero_shift,

            "theoretical_peak_count":
                theoretical_count,

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

            "within_0_03":
                0,

            "within_0_05":
                0,

            "within_0_10":
                0,

            "residual_slope":
                None,
        }

    abs_residuals = [
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

    weight_total = sum(
        weights
    )

    if weight_total > 0:

        weighted_mean = (
            sum(
                residual * weight

                for residual, weight
                in zip(
                    abs_residuals,
                    weights,
                )
            )
            / weight_total
        )

    else:

        weighted_mean = mean(
            abs_residuals
        )

    return {
        "zero_shift":
            zero_shift,

        "theoretical_peak_count":
            theoretical_count,

        "matched_count":
            matched_count,

        "matched_fraction":
            matched_fraction,

        "median_abs_residual":
            median(
                abs_residuals
            ),

        "mean_abs_residual":
            mean(
                abs_residuals
            ),

        "weighted_mean_abs_residual":
            weighted_mean,

        "max_abs_residual":
            max(
                abs_residuals
            ),

        "within_0_03":
            sum(
                value <= 0.03
                for value
                in abs_residuals
            ),

        "within_0_05":
            sum(
                value <= 0.05
                for value
                in abs_residuals
            ),

        "within_0_10":
            sum(
                value <= 0.10
                for value
                in abs_residuals
            ),

        "residual_slope":
            residual_slope(
                matches
            ),
    }


# ============================================================
# Calibration summaries
# ============================================================

def metric_values(
    records,
    key,
):
    values = []

    for record in records:

        value = (
            record.get(
                "metrics",
                {},
            ).get(
                key
            )
        )

        if value is not None:
            values.append(
                float(value)
            )

    return values


def make_distribution_summary(
    records,
):
    metrics = {}

    keys = [
        "matched_fraction",
        "zero_shift",
        "median_abs_residual",
        "mean_abs_residual",
        "weighted_mean_abs_residual",
        "max_abs_residual",
        "residual_slope",
    ]

    for key in keys:

        values = metric_values(
            records,
            key,
        )

        if not values:
            continue

        if key in {
            "zero_shift",
            "residual_slope",
        }:

            absolute_values = [
                abs(value)
                for value in values
            ]

            metrics[
                f"abs_{key}"
            ] = {
                "n":
                    len(
                        absolute_values
                    ),

                "p50":
                    percentile(
                        absolute_values,
                        0.50,
                    ),

                "p75":
                    percentile(
                        absolute_values,
                        0.75,
                    ),

                "p90":
                    percentile(
                        absolute_values,
                        0.90,
                    ),

                "p95":
                    percentile(
                        absolute_values,
                        0.95,
                    ),
            }

        else:

            metrics[key] = {
                "n":
                    len(values),

                "p50":
                    percentile(
                        values,
                        0.50,
                    ),

                "p75":
                    percentile(
                        values,
                        0.75,
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

    return metrics


def print_distribution(
    title,
    records,
):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    print(
        "Records:",
        len(records),
    )

    summary = (
        make_distribution_summary(
            records
        )
    )

    ordered_keys = [
        "matched_fraction",
        "median_abs_residual",
        "weighted_mean_abs_residual",
        "max_abs_residual",
        "abs_zero_shift",
        "abs_residual_slope",
    ]

    print()

    print(
        f"{'Metric':<32}"
        f"{'P50':>12}"
        f"{'P75':>12}"
        f"{'P90':>12}"
        f"{'P95':>12}"
    )

    for key in ordered_keys:

        if key not in summary:
            continue

        item = summary[key]

        print(
            f"{key:<32}"
            f"{item['p50']:>12.5f}"
            f"{item['p75']:>12.5f}"
            f"{item['p90']:>12.5f}"
            f"{item['p95']:>12.5f}"
        )

    return summary


# ============================================================
# Load frozen experimental resolution v1
# ============================================================

data = json.loads(
    RESOLUTION_FILE.read_text(
        encoding="utf-8"
    )
)

all_records = (
    data["records"]
)

calibration_records = []

for record in all_records:

    resolution = record.get(
        "structure_resolution",
        {},
    )

    if (
        resolution.get(
            "resolution_level"
        )
        == "record"
        and
        resolution.get(
            "selected_candidate"
        )
        is not None
    ):

        calibration_records.append(
            record
        )


print()
print("=" * 100)
print(
    "RRUFF DIFFRACTION CONSISTENCY "
    "CALIBRATION V1"
)
print("=" * 100)

print(
    "Record-level calibration inputs:",
    len(
        calibration_records
    ),
)

status_counts = {}

for record in calibration_records:

    status = (
        record[
            "structure_resolution"
        ].get(
            "resolution_status"
        )
    )

    status_counts[
        status
    ] = (
        status_counts.get(
            status,
            0,
        )
        + 1
    )

for key, value in sorted(
    status_counts.items()
):

    print(
        f"  {key:<36}",
        value,
    )


# ============================================================
# Run calibration
# ============================================================

db = get_database(
    database_name="rruff"
)

results = []

errors = []


for index, record in enumerate(
    calibration_records,
    start=1,
):

    sample_id = (
        record["sample_id"]
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

        if raw is None:

            raise RuntimeError(
                "Missing XY_RAW."
            )

        dif = db.dif.find_one(
            {
                "sample_id":
                    sample_id
            }
        )

        if dif is None:

            raise RuntimeError(
                "Missing DIF."
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

        if (
            len(raw_x) < 3
            or len(raw_y) != len(raw_x)
        ):

            raise RuntimeError(
                "Invalid experimental profile."
            )

        experimental_peaks = (
            detect_experimental_peaks(
                raw_x,
                raw_y,
            )
        )

        if not experimental_peaks:

            raise RuntimeError(
                "No experimental peaks detected."
            )

        radiation = (
            derive_validation_wavelength(
                dif
            )
        )

        cif_path = (
            PROJECT_ROOT
            / selected[
                "file_path"
            ]
        )

        if not cif_path.exists():

            raise RuntimeError(
                f"CIF not found: "
                f"{cif_path}"
            )

        calculated = (
            calculate_reflections(
                cif_path,
                radiation[
                    "validation_wavelength"
                ],
                raw_x[0],
                raw_x[-1],
            )
        )

        theoretical = sorted(
            calculated[
                "reflections"
            ],
            key=lambda item:
                item[
                    "relative_intensity"
                ],
            reverse=True,
        )[
            :TOP_THEORETICAL
        ]

        metrics = (
            summarize_candidate(
                theoretical,
                experimental_peaks,
            )
        )

        result = {
            "sample_id":
                sample_id,

            "mineral":
                record.get(
                    "mineral"
                ),

            "measurement_id":
                measurement_id,

            "resolution_status":
                resolution.get(
                    "resolution_status"
                ),

            "selected_source":
                selected.get(
                    "source"
                ),

            "selected_source_id":
                selected.get(
                    "source_id"
                ),

            "selected_file_path":
                selected.get(
                    "file_path"
                ),

            "radiation":
                radiation,

            "experimental_peak_count":
                len(
                    experimental_peaks
                ),

            "generated_reflection_count":
                len(
                    calculated[
                        "reflections"
                    ]
                ),

            "metrics":
                metrics,
        }

        results.append(
            result
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
                    f"{type(exc).__name__}: "
                    f"{exc}",
            }
        )

    if (
        index % 25 == 0
        or index
        == len(
            calibration_records
        )
    ):

        print(
            f"[{index:>3}/"
            f"{len(calibration_records)}] "
            f"ok={len(results)} "
            f"errors={len(errors)}"
        )


# ============================================================
# Stratified summaries
# ============================================================

unique_bibliographic = [
    item
    for item in results
    if item[
        "resolution_status"
    ]
    == "unique_bibliographic_match"
]

single_candidate = [
    item
    for item in results
    if item[
        "resolution_status"
    ]
    == "single_candidate_after_filtering"
]

cu_like = [
    item
    for item in results
    if item[
        "radiation"
    ][
        "radiation_class"
    ]
    == "Cu-like"
]

mo_like = [
    item
    for item in results
    if item[
        "radiation"
    ][
        "radiation_class"
    ]
    == "Mo-like"
]


overall_summary = (
    print_distribution(
        "ALL RECORD-LEVEL PAIRS",
        results,
    )
)

bibliographic_summary = (
    print_distribution(
        "PRIMARY CALIBRATION: "
        "UNIQUE BIBLIOGRAPHIC MATCHES",
        unique_bibliographic,
    )
)

single_summary = (
    print_distribution(
        "SECONDARY STRATUM: "
        "SINGLE CANDIDATE AFTER FILTERING",
        single_candidate,
    )
)

cu_summary = (
    print_distribution(
        "Cu-LIKE RECORDS",
        cu_like,
    )
)

mo_summary = (
    print_distribution(
        "Mo-LIKE RECORDS",
        mo_like,
    )
)


# ============================================================
# Extra counts
# ============================================================

print()
print("=" * 100)
print(
    "CALIBRATION COMPLETENESS"
)
print("=" * 100)

print(
    "Requested:",
    len(
        calibration_records
    ),
)

print(
    "Successful:",
    len(results),
)

print(
    "Errors:",
    len(errors),
)

print(
    "Unique bibliographic:",
    len(
        unique_bibliographic
    ),
)

print(
    "Single candidate:",
    len(
        single_candidate
    ),
)

print(
    "Cu-like:",
    len(cu_like),
)

print(
    "Mo-like:",
    len(mo_like),
)


# ============================================================
# Save frozen calibration output
# ============================================================

output = {
    "version":
        "1.0",

    "purpose":
        (
            "Empirical diffraction-consistency "
            "calibration for independently resolved "
            "RRUFF experimental PXRD-CIF associations."
        ),

    "input_resolution_file":
        str(
            RESOLUTION_FILE.relative_to(
                PROJECT_ROOT
            )
        ).replace(
            "\\",
            "/",
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

        "cu_reference_wavelength":
            CU_WAVELENGTH,

        "mo_reference_wavelength":
            MO_WAVELENGTH,
    },

    "counts": {
        "requested":
            len(
                calibration_records
            ),

        "successful":
            len(results),

        "errors":
            len(errors),

        "unique_bibliographic_match":
            len(
                unique_bibliographic
            ),

        "single_candidate_after_filtering":
            len(
                single_candidate
            ),

        "cu_like":
            len(cu_like),

        "mo_like":
            len(mo_like),
    },

    "summaries": {
        "all":
            overall_summary,

        "unique_bibliographic_match":
            bibliographic_summary,

        "single_candidate_after_filtering":
            single_summary,

        "cu_like":
            cu_summary,

        "mo_like":
            mo_summary,
    },

    "records":
        results,

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
print("=" * 100)
print(
    "CALIBRATION V1 COMPLETE"
)
print("=" * 100)

